import { router } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '@/components/layout/app-header';
import { Icon } from '@/components/ui/icon';
import { Button, IconButton, Image, LinearGradient, Pill, PulseDot } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { ZeloLiveModal } from '@/components/zelo-live-modal';
import {
  sendVoiceTurn,
  type ConversationTurnResponse,
} from '@/services/api';
import { useApp } from '@/state/app-state';
import { shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';
import { abrirRota } from '@/utils/maps';
import { playNeuralAudioOrFallback, stopBrowserSpeech, warmUpPtBrVoices } from '@/utils/speech';

type QuickSuggestion = { icon: string; texto: string };

const SUGESTOES_INICIAIS: QuickSuggestion[] = [
  { icon: 'science', texto: 'Preciso de jejum para ultrassom de abdômen total?' },
  { icon: 'pill', texto: 'Moro em Ceilândia, onde retiro losartana 50 mg de graça?' },
  { icon: 'local_hospital', texto: 'Como consigo adalimumabe 40 mg no Alto Custo (CEAF)?' },
  { icon: 'event_available', texto: 'Quais documentos levo para renovar minha receita?' },
];

type Msg =
  | { id: string; de: 'eu'; texto: string; hora: string; viaVoz?: boolean; anexoNome?: string }
  | { id: string; de: 'zelo'; tipo: 'saudacao'; hora: string }
  | { id: string; de: 'zelo'; tipo: 'lembrete'; hora: string }
  | { id: string; de: 'zelo'; tipo: 'ia'; hora: string; payload: ConversationTurnResponse }
  | { id: string; de: 'zelo'; tipo: 'erro'; hora: string; texto: string };

const INICIAIS: Msg[] = [
  { id: 'm1', de: 'zelo', tipo: 'saudacao', hora: 'Agora' },
  { id: 'm2', de: 'zelo', tipo: 'lembrete', hora: 'Agora' },
];

type SpeechRecInstance = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((ev: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function getSpeechRecognitionCtor(): (new () => SpeechRecInstance) | null {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecInstance;
    webkitSpeechRecognition?: new () => SpeechRecInstance;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function horaAgora() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function routeLabel(route: string): { label: string; tone: 'success' | 'warning' | 'info' | 'neutral' } {
  switch (route) {
    case 'FARMACIA_POPULAR':
      return { label: 'Farmácia Popular 100%', tone: 'success' };
    case 'UBS_ATENCAO_PRIMARIA':
      return { label: 'UBS / Atenção Básica', tone: 'success' };
    case 'ALTO_CUSTO_CEAF':
      return { label: 'Alto Custo • CEAF', tone: 'info' };
    case 'PRE_EXAME_PREPARO':
      return { label: 'Preparo Pré-Exame', tone: 'info' };
    case 'SISREG_EXAME_CONSULTA':
      return { label: 'SISREG / Regulação DF', tone: 'info' };
    case 'BLOQUEIO_CLINICO_ATO_MEDICO':
      return { label: 'Segurança • Ato Médico', tone: 'warning' };
    case 'CONVERSA_ACOLHIMENTO':
      return { label: 'Zelo Voz • Conversa', tone: 'info' };
    default:
      return { label: 'Protocolo Oficial SUS', tone: 'neutral' };
  }
}

function AvatarZelo({ icon = 'spa', bg = 'bg-primary' }: { icon?: string; bg?: string }) {
  return (
    <View className={`mt-0.5 h-8 w-8 items-center justify-center rounded-full ${bg}`} style={shadow.sm}>
      <Icon name={icon} size={16} color="on-primary" />
    </View>
  );
}

function BolhaEu({ texto, hora, viaVoz, anexoNome }: { texto: string; hora: string; viaVoz?: boolean; anexoNome?: string }) {
  return (
    <View className="ml-auto max-w-[88%] flex-row items-end gap-2">
      <View className="shrink rounded-2xl rounded-br-sm bg-accent p-3.5" style={shadow.sm}>
        {anexoNome && (
          <View className="mb-1.5 flex-row items-center gap-1.5 rounded-lg bg-primary px-2.5 py-1">
            <Icon name="photo_camera" size={14} color="tertiary-fixed" />
            <Txt v="label-sm" className="text-tertiary-fixed" numberOfLines={1}>
              {anexoNome}
            </Txt>
          </View>
        )}
        <Txt v="body-md" className="text-on-primary">
          {texto}
        </Txt>
        <Txt v="label-sm" w="medium" className="mt-1 text-right text-primary-fixed">
          {hora} • {viaVoz ? 'Voz PT-BR' : 'Enviado'}
        </Txt>
      </View>
      <View className="h-8 w-8 items-center justify-center rounded-full bg-primary-fixed" style={shadow.sm}>
        <Icon name="person" size={18} color="on-primary-fixed" />
      </View>
    </View>
  );
}

function Faixa({ cores }: { cores: [string, string, string] }) {
  return <LinearGradient colors={cores} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} className="absolute inset-x-0 top-0 h-1" />;
}

export default function Zelo() {
  const insets = useSafeAreaInsets();
  const {
    usuario,
    doses,
    registrarDose,
    adiarDose,
    regiaoAdministrativa,
    setRegiaoAdministrativa,
    zeloSessionId,
    resetZeloSession,
    zeloDraftPrompt,
    setZeloDraftPrompt,
    zeloRespondeVoz,
    setZeloRespondeVoz,
    apiBaseUrl,
    toast,
  } = useApp();

  const [msgs, setMsgs] = useState<Msg[]>(INICIAIS);
  const [texto, setTexto] = useState('');
  const [ouvindo, setOuvindo] = useState(false);
  const [gravandoAudio, setGravandoAudio] = useState(false);
  const [transcricaoParcial, setTranscricaoParcial] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [falandoId, setFalandoId] = useState<string | null>(null);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);
  const [liveOpen, setLiveOpen] = useState(false);

  // Carteira digital / foto local de receita ou pedido de exame (ADR-0002: zero OCR de caligrafia na nuvem)
  const [scanOpen, setScanOpen] = useState(false);
  const [fotoPreviewUri, setFotoPreviewUri] = useState<string | null>(null);
  const [fotoNome, setFotoNome] = useState<string | null>(null);
  const [scanTexto, setScanTexto] = useState('');

  const scroll = useRef<React.ComponentRef<typeof ScrollView>>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const speechRecRef = useRef<SpeechRecInstance | null>(null);
  const mediaRecRef = useRef<{ stop: () => void } | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<{ getTracks: () => { stop: () => void }[] } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const espacoTabBar = 64 + Math.max(insets.bottom, 12) + 8;
  const tomada = doses.metformina === 'tomada';
  const adiada = doses.metformina === 'adiada';

  useEffect(() => {
    warmUpPtBrVoices();
  }, []);

  const pararFala = useCallback(() => {
    if (audioRef.current) {
      try {
        audioRef.current.onended = null;
        audioRef.current.onerror = null;
        audioRef.current.pause();
      } catch {
        // Ignora erro ao pausar áudio encerrado.
      }
    }
    stopBrowserSpeech();
    setFalandoId(null);
  }, []);

  const reproduzirResposta = useCallback(
    (msgId: string, payload: ConversationTurnResponse) => {
      pararFala();
      if (Platform.OS !== 'web') {
        toast('Reprodução automática em áudio disponível na versão Web ou com expo-av nativo.', 'volume_up');
        return;
      }
      const speechText = payload.spoken_guidance || payload.synthesized_guidance;
      setFalandoId(msgId);
      playNeuralAudioOrFallback({
        text: speechText,
        audioBase64: payload.tts_audio_base64,
        mimeType: payload.tts_mime_type,
        audioElRef: audioRef,
        rate: 1.0,
        onEnd: () => setFalandoId(null),
      });
    },
    [pararFala, toast],
  );

  const executarTurnoBackend = useCallback(
    async (opts: {
      textoUsuario?: string;
      audioBlob?: Blob;
      viaVoz?: boolean;
      anexoNome?: string;
    }) => {
      const textoLimpo = opts.textoUsuario?.trim() ?? '';
      if (!textoLimpo && !opts.audioBlob) return;

      const userBubbleText = textoLimpo || 'Mensagem de voz enviada...';
      const userId = `u-${Date.now()}`;
      setMsgs((m) => [
        ...m,
        {
          id: userId,
          de: 'eu',
          texto: userBubbleText,
          hora: horaAgora(),
          viaVoz: opts.viaVoz,
          anexoNome: opts.anexoNome,
        },
      ]);
      setEnviando(true);
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 60);

      try {
        const queryComRa =
          textoLimpo && !/ceilandia|taguatinga|asa sul|asa norte|gama|samambaia|guara|planaltina|sobradinho/i.test(textoLimpo)
            ? `${textoLimpo} (Região do paciente: ${regiaoAdministrativa})`
            : textoLimpo;

        const resp = await sendVoiceTurn(
          {
            text: queryComRa || undefined,
            audioBlob: opts.audioBlob,
            session_id: zeloSessionId,
            days_since_emission: 166,
            synthesize_audio: zeloRespondeVoz,
          },
          apiBaseUrl,
        );

        if (resp.detected_ra && resp.detected_ra !== 'Distrito Federal (Geral)') {
          setRegiaoAdministrativa(resp.detected_ra);
        }

        const msgId = `ia-${Date.now()}`;
        setMsgs((m) => [...m, { id: msgId, de: 'zelo', tipo: 'ia', hora: horaAgora(), payload: resp }]);

        if (zeloRespondeVoz) {
          reproduzirResposta(msgId, resp);
        }
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : 'Erro inesperado ao consultar os Multiagentes.';
        setMsgs((m) => [
          ...m,
          {
            id: `err-${Date.now()}`,
            de: 'zelo',
            tipo: 'erro',
            hora: horaAgora(),
            texto: errMsg,
          },
        ]);
      } finally {
        setEnviando(false);
        setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
      }
    },
    [apiBaseUrl, regiaoAdministrativa, reproduzirResposta, setRegiaoAdministrativa, zeloRespondeVoz, zeloSessionId],
  );

  const enviarTexto = useCallback(
    (t?: string) => {
      const pergunta = (t ?? texto).trim();
      if (!pergunta || enviando) return;
      if (!t) setTexto('');
      void executarTurnoBackend({ textoUsuario: pergunta, viaVoz: false });
    },
    [enviando, executarTurnoBackend, texto],
  );

  // Recebe perguntas enviadas de outras telas (Início, Receitas, Farmácias).
  useEffect(() => {
    if (!zeloDraftPrompt) return;
    const prompt = zeloDraftPrompt;
    const timer = setTimeout(() => {
      setZeloDraftPrompt(null);
      void executarTurnoBackend({ textoUsuario: prompt, viaVoz: false });
    }, 0);
    return () => clearTimeout(timer);
  }, [executarTurnoBackend, setZeloDraftPrompt, zeloDraftPrompt]);

  useEffect(() => {
    return () => {
      pararFala();
      speechRecRef.current?.stop();
      streamRef.current?.getTracks().forEach((tr) => tr.stop());
    };
  }, [pararFala]);

  const pararCapturaVoz = useCallback(() => {
    if (speechRecRef.current) {
      try {
        speechRecRef.current.stop();
      } catch {
        // Ignora parada dupla.
      }
      speechRecRef.current = null;
    }
    if (mediaRecRef.current) {
      try {
        mediaRecRef.current.stop();
      } catch {
        // Ignora parada dupla.
      }
      mediaRecRef.current = null;
    }
    setOuvindo(false);
    setGravandoAudio(false);
    setTranscricaoParcial('');
  }, []);

  const iniciarCapturaVoz = useCallback(async () => {
    pararFala();
    if (ouvindo || gravandoAudio) {
      pararCapturaVoz();
      return;
    }

    if (Platform.OS !== 'web') {
      toast('No celular nativo, toque no teclado para usar o ditado do sistema ou teste no navegador Web.', 'mic');
      return;
    }

    const RecCtor = getSpeechRecognitionCtor();
    if (RecCtor) {
      const rec = new RecCtor();
      rec.lang = 'pt-BR';
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      speechRecRef.current = rec;
      setOuvindo(true);
      setTranscricaoParcial('');

      let finalCaptured = '';
      rec.onresult = (ev) => {
        let interim = '';
        for (let i = 0; i < ev.results.length; i += 1) {
          const item = ev.results[i];
          const textChunk = item[0]?.transcript ?? '';
          if (item.isFinal) {
            finalCaptured = `${finalCaptured} ${textChunk}`.trim();
          } else {
            interim += textChunk;
          }
        }
        setTranscricaoParcial((finalCaptured || interim).trim());
        if (finalCaptured) {
          rec.stop();
          speechRecRef.current = null;
          setOuvindo(false);
          setTranscricaoParcial('');
          void executarTurnoBackend({ textoUsuario: finalCaptured, viaVoz: true });
          finalCaptured = '';
        }
      };
      rec.onerror = () => {
        setOuvindo(false);
        setTranscricaoParcial('');
        toast('Não consegui capturar o áudio pelo navegador. Tente novamente ou digite.', 'mic_off');
      };
      rec.onend = () => {
        setOuvindo(false);
      };
      rec.start();
      return;
    }

    // Fallback Web MediaRecorder -> envia arquivo .webm para POST /v1/voice-turn (STT no servidor)
    if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined') {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        const recorder = new MediaRecorder(stream);
        audioChunksRef.current = [];
        recorder.ondataavailable = (ev) => {
          if (ev.data.size > 0) audioChunksRef.current.push(ev.data);
        };
        recorder.onstop = () => {
          stream.getTracks().forEach((tr) => tr.stop());
          streamRef.current = null;
          const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          audioChunksRef.current = [];
          setGravandoAudio(false);
          setOuvindo(false);
          if (blob.size > 200) {
            void executarTurnoBackend({ audioBlob: blob, viaVoz: true });
          }
        };
        mediaRecRef.current = recorder;
        recorder.start();
        setGravandoAudio(true);
        setOuvindo(true);
      } catch {
        toast('Permita o acesso ao microfone para conversar por voz com a Zelo.', 'mic_off');
      }
      return;
    }

    toast('Seu navegador não expõe microfone. Escreva sua dúvida abaixo!', 'keyboard');
  }, [executarTurnoBackend, gravandoAudio, ouvindo, pararCapturaVoz, pararFala, toast]);

  async function handleReiniciarConversa() {
    pararFala();
    await resetZeloSession();
    setMsgs(INICIAIS);
  }

  const ultimoPayloadIA = [...msgs].reverse().find((m): m is Extract<Msg, { tipo: 'ia' }> => 'tipo' in m && m.tipo === 'ia')?.payload;
  const sugestoesAtivas: QuickSuggestion[] =
    ultimoPayloadIA && ultimoPayloadIA.follow_up_suggestions.length > 0
      ? ultimoPayloadIA.follow_up_suggestions.map((textoSug) => ({ icon: 'chat_bubble_outline', texto: textoSug }))
      : SUGESTOES_INICIAIS;

  function renderMsg(m: Msg) {
    if (m.de === 'eu') {
      return <BolhaEu key={m.id} texto={m.texto} hora={m.hora} viaVoz={m.viaVoz} anexoNome={m.anexoNome} />;
    }

    if (m.tipo === 'saudacao') {
      return (
        <View key={m.id} className="max-w-[94%] flex-row items-start gap-2.5">
          <AvatarZelo />
          <View className="flex-1 rounded-2xl rounded-tl-sm bg-surface-container-lowest p-4" style={shadow.sm}>
            <Txt v="body-md" className="text-on-surface">
              Olá, <Txt v="body-md" w="semibold" className="text-primary">{usuario?.nome}</Txt>! Sou a{' '}
              <Txt v="body-md" w="semibold" className="text-primary">Zelo</Txt>, integrada ao motor{' '}
              <Txt v="body-md" w="semibold" className="text-secondary">Multiagentes RAG v9 (1.775 itens + Pré-Exames)</Txt>.
              Fale no microfone ou pergunte sobre medicamentos, farmácias em{' '}
              <Txt v="body-md" w="semibold" className="text-primary">{regiaoAdministrativa}</Txt> ou preparo de exames!
            </Txt>
            <Txt v="label-sm" w="medium" className="mt-2 text-right text-on-surface-variant">
              {m.hora} • Zelo Voz SUS-DF
            </Txt>
          </View>
        </View>
      );
    }

    if (m.tipo === 'lembrete') {
      return (
        <View key={m.id} className="max-w-[96%] flex-row items-start gap-2.5">
          <AvatarZelo icon="alarm" bg="bg-primary-container" />
          <View className="flex-1 overflow-hidden rounded-2xl rounded-tl-sm bg-surface-container-lowest p-4" style={shadow.md}>
            <Faixa cores={[colors.primary, colors['primary-container'], colors.secondary]} />
            <View className="mb-2 flex-row items-center justify-between pt-1">
              <View className="flex-row items-center gap-1.5">
                <Icon name="pill" size={18} color="secondary" />
                <Txt v="label-sm" upper className="text-secondary">
                  Lembrete ativo
                </Txt>
              </View>
              <Pill label={tomada ? 'Tomado' : 'Próxima 12:30'} tone="success" />
            </View>
            <Txt v="title-md" className="text-primary">
              Metformina 850mg • PFPB 100% Gratuito
            </Txt>
            <Txt v="body-sm" className="text-on-surface-variant">
              Tomar após o almoço com 200 mL de água. Deseja confirmar a dose ou consultar jejum para exames?
            </Txt>
            {tomada ? (
              <View className="mt-3 flex-row items-center gap-1.5 rounded-lg bg-secondary-container/50 p-2">
                <Icon name="task_alt" size={16} color="on-secondary-container" />
                <Txt v="label-sm" className="text-on-secondary-container">
                  Dose registrada no seu Diário SUS!
                </Txt>
              </View>
            ) : (
              <View className="mt-3 flex-row gap-2">
                <Button
                  label="Já tomei"
                  icon="check_circle"
                  variant="success"
                  className="flex-1 rounded-xl"
                  onPress={() => registrarDose('metformina', 'Metformina 850mg')}
                />
                <Button
                  label={adiada ? 'Adiado' : 'Adiar 15 min'}
                  icon="snooze"
                  variant="surface"
                  className="flex-1 rounded-xl"
                  disabled={adiada}
                  onPress={() => adiarDose('metformina')}
                />
              </View>
            )}
          </View>
        </View>
      );
    }

    if (m.tipo === 'erro') {
      return (
        <View key={m.id} className="max-w-[96%] flex-row items-start gap-2.5">
          <AvatarZelo icon="cloud_off" bg="bg-tertiary" />
          <View className="flex-1 gap-2 overflow-hidden rounded-2xl rounded-tl-sm border border-tertiary-fixed-dim bg-surface-container-lowest p-4" style={shadow.md}>
            <View className="flex-row items-center gap-2">
              <Icon name="wifi_off" size={18} color="tertiary" />
              <Txt v="title-md" className="text-primary">
                Servidor Multiagentes offline
              </Txt>
            </View>
            <Txt v="body-sm" className="text-on-surface-variant">
              {m.texto}
            </Txt>
            <View className="flex-row gap-2">
              <Button label="Configurar API" icon="settings" size="sm" variant="surface" onPress={() => router.push('/perfil')} />
              <Button label="Disque 136" icon="phone_in_talk" size="sm" onPress={() => Linking.openURL('tel:136')} />
            </View>
          </View>
        </View>
      );
    }

    const p = m.payload;
    const badge = routeLabel(p.primary_route);
    const isSpeaking = falandoId === m.id;
    const traceOpen = expandedTraceId === m.id;

    if (p.is_clinical_block) {
      return (
        <View key={m.id} className="max-w-[96%] flex-row items-start gap-2.5">
          <AvatarZelo icon="shield_with_heart" bg="bg-error" />
          <View
            className="flex-1 overflow-hidden rounded-2xl rounded-tl-sm border border-error/25 bg-surface-container-lowest p-4"
            style={shadow.md}>
            <Faixa cores={[colors.error, colors['error-container'], colors.error]} />
            <View className="mb-2 flex-row items-center justify-between gap-2 pt-1">
              <View className="flex-row items-center gap-1.5">
                <Icon name="e911_emergency" size={18} color="error" />
                <Txt v="label-sm" upper className="text-error">
                  {badge.label}
                </Txt>
              </View>
              <Pressable
                onPress={() => (isSpeaking ? pararFala() : reproduzirResposta(m.id, p))}
                className="flex-row items-center gap-1 rounded-full bg-surface-container px-2.5 py-1">
                <Icon name={isSpeaking ? 'stop' : 'volume_up'} size={14} color="primary" />
                <Txt v="label-sm" className="text-primary">
                  {isSpeaking ? 'Parar' : 'Ouvir'}
                </Txt>
              </Pressable>
            </View>
            <Txt v="body-md" w="medium" className="text-on-surface">
              {p.spoken_guidance || p.synthesized_guidance}
            </Txt>
            <View className="mt-3 gap-2 rounded-xl bg-error-container/35 p-3">
              <View className="flex-row gap-2">
                <Button
                  label="Ligar 192 SAMU"
                  icon="ambulance"
                  variant="danger"
                  size="sm"
                  className="flex-1"
                  onPress={() => Linking.openURL('tel:192')}
                />
                <Button
                  label="UPA Mais Próxima"
                  icon="near_me"
                  variant="surface"
                  size="sm"
                  className="flex-1"
                  onPress={() => abrirRota(`UPA 24h perto de ${p.detected_ra}`)}
                />
              </View>
              <Pressable onPress={() => Linking.openURL('tel:136')} className="flex-row items-center gap-1.5 px-1">
                <Icon name="phone_in_talk" size={14} color="primary" />
                <Txt v="label-sm" className="text-primary">
                  Atendimento gratuito 24h: Disque Saúde 136
                </Txt>
              </Pressable>
            </View>
            <Txt v="label-sm" w="medium" className="mt-2 text-right text-on-surface-variant">
              {m.hora} • Preservação do Ato Médico (Lei nº 12.842/2013)
            </Txt>
          </View>
        </View>
      );
    }

    return (
      <View key={m.id} className="max-w-[96%] flex-row items-start gap-2.5">
        <AvatarZelo />
        <View className="flex-1 overflow-hidden rounded-2xl rounded-tl-sm bg-surface-container-lowest p-4" style={shadow.md}>
          <Faixa cores={[colors.primary, colors['primary-container'], colors.secondary]} />
          <View className="mb-2 flex-row flex-wrap items-center justify-between gap-1.5 pt-1">
            <View className="flex-row flex-wrap items-center gap-1.5">
              <Pill label={badge.label} tone={badge.tone} />
              <Pill label={p.detected_ra.replace(' - DF', '')} tone="neutral" />
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={isSpeaking ? 'Parar fala da Zelo' : 'Ouvir resposta da Zelo'}
              onPress={() => (isSpeaking ? pararFala() : reproduzirResposta(m.id, p))}
              className={`flex-row items-center gap-1 rounded-full px-2.5 py-1 ${
                isSpeaking ? 'bg-secondary-container' : 'bg-surface-container'
              }`}>
              <Icon name={isSpeaking ? 'stop' : 'volume_up'} size={15} color={isSpeaking ? 'on-secondary-container' : 'primary'} />
              <Txt v="label-sm" className={isSpeaking ? 'text-on-secondary-container' : 'text-primary'}>
                {isSpeaking ? 'Parar' : 'Ouvir'}
              </Txt>
            </Pressable>
          </View>

          <Txt v="body-md" className="text-on-surface">
            {(p.audited_medications.length > 0 || p.sisreg_guidance.length > 0) && p.spoken_guidance
              ? p.spoken_guidance
              : p.synthesized_guidance}
          </Txt>

          {/* Medicamentos auditados via v9 + InfoSaúde */}
          {p.audited_medications.length > 0 && (
            <View className="mt-3 gap-2">
              {p.audited_medications.map((med, idx) => (
                <View key={`${med.dcb_name}-${idx}`} className="gap-1.5 rounded-xl bg-surface-container-low p-3">
                  <View className="flex-row items-center justify-between gap-2">
                    <Txt v="label-lg" className="flex-1 text-primary">
                      {med.dcb_name.toUpperCase()} {med.concentration}
                    </Txt>
                    {med.requires_lme && <Pill label="Exige LME" tone="warning" />}
                  </View>
                  <Txt v="body-sm" className="text-on-surface-variant">
                    {med.where_to_collect}
                  </Txt>
                  <View className="flex-row items-center justify-between pt-0.5">
                    <Txt v="label-sm" w="medium" className="text-secondary">
                      Receita: {med.validity_days} dias • {med.rename_component}
                    </Txt>
                    <Pressable onPress={() => router.navigate('/farmacias')} hitSlop={6}>
                      <Txt v="label-sm" className="text-primary underline">
                        Ver farmácias
                      </Txt>
                    </Pressable>
                  </View>
                </View>
              ))}
            </View>
          )}

          {/* Dicas de preparo pré-exame */}
          {p.preparation_tips.length > 0 && (
            <View className="mt-3 gap-1.5 rounded-xl border border-primary-fixed-dim/50 bg-primary-fixed/25 p-3">
              <View className="flex-row items-center gap-1.5">
                <Icon name="science" size={16} color="primary" />
                <Txt v="label-md" upper className="text-primary">
                  Preparo Pré-Exame SUS-DF
                </Txt>
              </View>
              {p.preparation_tips.map((tip, idx) => (
                <View key={idx} className="flex-row items-start gap-2">
                  <Icon name="check_circle" size={15} color="secondary" />
                  <Txt v="body-sm" className="flex-1 text-on-surface">
                    {tip}
                  </Txt>
                </View>
              ))}
            </View>
          )}

          {/* Checklist de documentos obrigatórios */}
          {p.checklist_documents.length > 0 && (
            <View className="mt-3 gap-1 rounded-xl bg-surface-container-low p-3">
              <View className="flex-row items-center gap-1.5">
                <Icon name="checklist" size={16} color="secondary" />
                <Txt v="label-md" upper className="text-primary">
                  O que levar
                </Txt>
              </View>
              {p.checklist_documents.map((doc, idx) => (
                <Txt key={idx} v="body-sm" className="text-on-surface-variant">
                  • {doc}
                </Txt>
              ))}
            </View>
          )}

          {/* Alertas de validade RF08 */}
          {p.validity_alerts.length > 0 && (
            <View className="mt-2.5 flex-row items-start gap-2 rounded-xl bg-tertiary-fixed/45 p-2.5">
              <Icon name="schedule" size={16} color="on-tertiary-container" />
              <Txt v="body-sm" w="medium" className="flex-1 text-tertiary-container">
                {p.validity_alerts.join(' ')}
              </Txt>
            </View>
          )}

          {/* Fontes oficiais & auditoria dos 4 agentes */}
          {(p.citations.length > 0 || p.agent_trace.length > 0) && (
            <View className="mt-3 border-t border-surface-container-high pt-2">
              <Pressable
                onPress={() => setExpandedTraceId(traceOpen ? null : m.id)}
                className="flex-row items-center justify-between py-0.5">
                <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                  {p.citations.length} fonte(s) oficiais • Turno {p.turn_count}
                </Txt>
                <Txt v="label-sm" className="text-primary">
                  {traceOpen ? 'Ocultar auditoria ▲' : 'Ver auditoria ▼'}
                </Txt>
              </Pressable>
              {traceOpen && (
                <View className="mt-2 gap-1 rounded-lg bg-surface-container-low p-2.5">
                  {p.citations.map((c, idx) => (
                    <Txt key={idx} v="label-sm" w="medium" className="text-primary">
                      • {c}
                    </Txt>
                  ))}
                  {p.agent_trace.map((tr, idx) => (
                    <Txt key={`tr-${idx}`} v="label-sm" w="regular" className="text-on-surface-variant">
                      {tr}
                    </Txt>
                  ))}
                </View>
              )}
            </View>
          )}

          <Txt v="label-sm" w="medium" className="mt-2 text-right text-on-surface-variant">
            {m.hora} • RAG Híbrido v9 • {p.tts_provider === 'disabled' ? 'Texto' : p.tts_voice}
          </Txt>
        </View>
      </View>
    );
  }

  function handleSelectLocalPhoto(file?: File) {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setFotoPreviewUri(url);
    setFotoNome(file.name);
  }

  return (
    <View className="flex-1 bg-canvas">
      <AppHeader />
      <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          ref={scroll}
          className="flex-1"
          contentContainerClassName="gap-4 px-4 pt-3"
          contentContainerStyle={{ paddingBottom: 16 }}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          {/* Barra de emergência */}
          <View className="flex-row items-center justify-between gap-2 rounded-xl bg-surface-container-low px-3 py-2" style={shadow.sm}>
            <View className="flex-1 flex-row items-center gap-1.5">
              <Icon name="health_and_safety" size={18} />
              <Txt v="label-sm" upper className="flex-1 text-primary" numberOfLines={1}>
                Apoio imediato
              </Txt>
            </View>
            <Pressable
              onPress={() => Linking.openURL('tel:136')}
              className="min-h-[34px] flex-row items-center gap-1 rounded-full bg-surface-container-highest px-2.5 py-1 active:opacity-70">
              <Icon name="phone_in_talk" size={14} />
              <Txt v="label-sm" className="text-primary">
                Disque 136
              </Txt>
            </Pressable>
            <Pressable
              onPress={() => Linking.openURL('tel:192')}
              className="min-h-[34px] flex-row items-center gap-1 rounded-full bg-error-container px-2.5 py-1 active:opacity-70">
              <Icon name="ambulance" size={14} color="on-error-container" />
              <Txt v="label-sm" className="text-on-error-container">
                192 SAMU
              </Txt>
            </Pressable>
          </View>

          {/* Cartão da Zelo */}
          <View className="overflow-hidden rounded-2xl bg-surface-container-lowest p-4" style={shadow.md}>
            <View className="flex-row items-center justify-between gap-2">
              <View className="flex-1 flex-row items-center gap-3">
                <View
                  className="h-12 w-12 items-center justify-center rounded-full bg-primary-container"
                  style={{ borderWidth: 3, borderColor: 'rgba(167, 200, 255, 0.6)' }}>
                  <Icon name="spa" size={26} color="on-primary" />
                  <View className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-2 border-surface-container-lowest bg-secondary" />
                </View>
                <View className="flex-1">
                  <View className="flex-row items-center gap-1.5">
                    <Txt v="title-md" className="text-primary">
                      Zelo Voz
                    </Txt>
                    <Pill label="RAG v9" className="bg-primary/10" />
                  </View>
                  <Txt v="body-sm" className="text-on-surface-variant" numberOfLines={1}>
                    Multiagentes SUS-DF • {regiaoAdministrativa.replace(' - DF', '')}
                  </Txt>
                  <View className="flex-row items-center gap-1">
                    <PulseDot />
                    <Txt v="label-sm" w="medium" className="text-secondary">
                      Sessão segura LGPD ativa
                    </Txt>
                  </View>
                </View>
              </View>
              <View className="flex-row items-center gap-1.5">
                <IconButton
                  icon="refresh"
                  label="Nova conversa"
                  size={38}
                  iconSize={19}
                  className="bg-surface-container"
                  onPress={() => void handleReiniciarConversa()}
                />
                <IconButton
                  icon={zeloRespondeVoz ? 'volume_up' : 'volume_off'}
                  label={zeloRespondeVoz ? 'Voz ativa — toque para silenciar' : 'Ativar resposta em voz'}
                  size={38}
                  iconSize={19}
                  color={zeloRespondeVoz ? 'on-secondary-container' : 'primary'}
                  className={zeloRespondeVoz ? 'bg-secondary-container' : 'bg-surface-container'}
                  onPress={() => {
                    pararFala();
                    setZeloRespondeVoz(!zeloRespondeVoz);
                  }}
                />
              </View>
            </View>
            <View className="mt-3 flex-row items-center justify-between gap-2 rounded-xl bg-surface-container-low p-2.5">
              <View className="flex-1 flex-row items-center gap-2">
                <Icon name="graphic_eq" size={18} color="secondary" />
                <Txt v="label-md" className="flex-1 text-primary" numberOfLines={1}>
                  Conversa interativa contínua estilo Gemini
                </Txt>
              </View>
              <Button
                label="Modo Ao Vivo"
                icon="graphic_eq"
                variant="success"
                size="sm"
                onPress={() => {
                  pararFala();
                  pararCapturaVoz();
                  setLiveOpen(true);
                }}
              />
            </View>
          </View>

          {msgs.map(renderMsg)}

          {enviando && (
            <View className="flex-row items-center gap-2.5 px-2">
              <AvatarZelo />
              <View className="flex-row items-center gap-2 rounded-2xl rounded-tl-sm bg-surface-container-lowest px-4 py-3" style={shadow.sm}>
                <ActivityIndicator size="small" color={colors.primary} />
                <Txt v="body-sm" className="text-on-surface-variant">
                  Consultando 4 agentes + base RENAME/SISREG...
                </Txt>
              </View>
            </View>
          )}

          {/* Sugestões contextuais */}
          <View className="gap-1.5 pt-1">
            <Txt v="label-sm" upper className="px-1 text-on-surface-variant">
              {ultimoPayloadIA ? 'Continuar conversa' : 'Perguntas rápidas'}
            </Txt>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-2 py-1">
              {sugestoesAtivas.map((s) => (
                <Pressable
                  key={s.texto}
                  onPress={() => enviarTexto(s.texto)}
                  className="min-h-[40px] flex-row items-center gap-1.5 rounded-full bg-surface-container-lowest px-3.5 py-2 active:bg-surface-container-high"
                  style={shadow.sm}>
                  <Icon name={s.icon} size={16} color="secondary" />
                  <Txt v="label-md" className="text-primary">
                    {s.texto}
                  </Txt>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </ScrollView>

        {/* Barra de texto e voz */}
        <View className="px-4 pb-2 pt-1" style={{ marginBottom: espacoTabBar }}>
          <View className="gap-2 rounded-2xl bg-surface-container-lowest p-2.5" style={shadow.lg}>
            {(ouvindo || gravandoAudio) && (
              <View className="flex-row items-center justify-between gap-2 rounded-xl bg-accent p-3">
                <View className="flex-1 flex-row items-center gap-2.5">
                  <PulseDot color="bg-error" size={12} />
                  <Txt v="body-sm" className="flex-1 text-on-primary">
                    {transcricaoParcial || (gravandoAudio ? 'Gravando áudio... toque em Enviar' : 'Ouvindo você em PT-BR... fale naturalmente')}
                  </Txt>
                </View>
                <Pressable onPress={pararCapturaVoz} hitSlop={8}>
                  <Txt v="label-sm" className="text-on-primary underline">
                    {gravandoAudio ? 'Enviar áudio' : 'Parar'}
                  </Txt>
                </Pressable>
              </View>
            )}
            <View className="flex-row items-center gap-2">
              <IconButton
                icon="document_scanner"
                label="Anexar foto local ou consultar receita"
                size={44}
                onPress={() => setScanOpen(true)}
              />
              <TextInput
                value={texto}
                onChangeText={setTexto}
                onSubmitEditing={() => enviarTexto()}
                returnKeyType="send"
                editable={!enviando}
                accessibilityLabel="Escreva sua dúvida ou exame"
                placeholder="Pergunte sobre remédio ou pré-exame..."
                placeholderTextColor={colors['on-surface-variant']}
                className="h-11 flex-1 rounded-xl bg-surface-container-low px-3.5 font-sans text-body-md text-on-surface"
              />
              <IconButton
                icon={ouvindo || gravandoAudio ? 'stop' : 'mic'}
                label={ouvindo || gravandoAudio ? 'Parar gravação' : 'Ditar pergunta'}
                size={44}
                iconSize={22}
                color="on-primary"
                className={`rounded-xl ${ouvindo || gravandoAudio ? 'bg-error' : 'bg-accent'}`}
                onPress={() => void iniciarCapturaVoz()}
              />
              {texto.trim() ? (
                <IconButton
                  icon="send"
                  label="Enviar mensagem"
                  size={44}
                  color="on-secondary"
                  className="rounded-xl bg-secondary"
                  onPress={() => enviarTexto()}
                />
              ) : (
                <IconButton
                  icon="graphic_eq"
                  label="Iniciar conversa por voz ao vivo com a Zelo"
                  size={44}
                  iconSize={22}
                  color="on-secondary"
                  className="rounded-xl bg-secondary"
                  onPress={() => {
                    pararFala();
                    pararCapturaVoz();
                    setLiveOpen(true);
                  }}
                />
              )}
            </View>
            <View className="flex-row items-center justify-between px-1">
              <View className="flex-row items-center gap-1">
                <Icon name="verified_user" size={13} color="secondary" />
                <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                  Conversa protegida pela LGPD • Modo Voz PT-BR
                </Txt>
              </View>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>

      {/* Modal: Carteira Digital Local / Consulta de Receita (ADR-0002) */}
      <Modal visible={scanOpen} transparent animationType="slide" onRequestClose={() => setScanOpen(false)}>
        <View className="flex-1 justify-end bg-primary/60">
          <View className="gap-4 rounded-t-3xl bg-surface-container-lowest p-5" style={shadow.xl}>
            <View className="flex-row items-center justify-between">
              <Txt v="headline-sm" className="text-primary">
                Digitalizar Receita ou Pedido
              </Txt>
              <IconButton icon="close" label="Fechar" onPress={() => setScanOpen(false)} />
            </View>
            <Txt v="body-sm" className="text-on-surface-variant">
              A foto fica salva apenas no seu aparelho (ADR-0002, sem OCR de caligrafia na nuvem). Descreva o item para a Zelo consultar a rota exata.
            </Txt>

            {Platform.OS === 'web' && (
              <View className="gap-2">
                <input
                  ref={(el) => {
                    fileInputRef.current = el;
                  }}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  style={{ display: 'none' }}
                  onChange={(ev) => handleSelectLocalPhoto(ev.target.files?.[0])}
                />
                <Button
                  label={fotoNome ? `Foto anexada: ${fotoNome}` : 'Escolher / Fotografar Receita'}
                  icon="photo_camera"
                  variant="surface"
                  onPress={() => fileInputRef.current?.click()}
                />
              </View>
            )}

            {fotoPreviewUri && (
              <View className="h-32 overflow-hidden rounded-xl bg-surface-container">
                <Image source={{ uri: fotoPreviewUri }} contentFit="cover" className="h-full w-full" />
              </View>
            )}

            <TextInput
              value={scanTexto}
              onChangeText={setScanTexto}
              placeholder="Ex.: Omalizumabe 150 mg ou Ultrassom de abdômen total"
              placeholderTextColor={colors['on-surface-variant']}
              className="h-12 rounded-xl bg-surface-container-low px-3.5 font-sans text-body-md text-on-surface"
            />

            <View className="flex-row gap-2">
              <Button
                label="Cadastrar na Carteira"
                icon="prescriptions"
                variant="surface"
                className="flex-1"
                onPress={() => {
                  setScanOpen(false);
                  router.navigate('/receitas');
                }}
              />
              <Button
                label="Consultar Zelo"
                icon="send"
                className="flex-1"
                onPress={() => {
                  const q = scanTexto.trim();
                  if (!q) {
                    toast('Digite o nome do remédio ou exame para consultar.', 'info');
                    return;
                  }
                  const nome = fotoNome ?? undefined;
                  setScanOpen(false);
                  setScanTexto('');
                  void executarTurnoBackend({
                    textoUsuario: q,
                    anexoNome: nome,
                    viaVoz: false,
                  });
                }}
              />
            </View>
          </View>
        </View>
      </Modal>

      <ZeloLiveModal
        visible={liveOpen}
        onClose={() => setLiveOpen(false)}
        sessionId={zeloSessionId}
        regiaoAdministrativa={regiaoAdministrativa}
        apiBaseUrl={apiBaseUrl}
        onToast={toast}
        onTurnComplete={(userText, resp) => {
          if (resp.detected_ra && resp.detected_ra !== 'Distrito Federal (Geral)') {
            setRegiaoAdministrativa(resp.detected_ra);
          }
          const stamp = horaAgora();
          setMsgs((m) => [
            ...m,
            { id: `u-live-${Date.now()}`, de: 'eu', texto: userText, hora: stamp, viaVoz: true },
            { id: `ia-live-${Date.now() + 1}`, de: 'zelo', tipo: 'ia', hora: stamp, payload: resp },
          ]);
          setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
        }}
      />
    </View>
  );
}
