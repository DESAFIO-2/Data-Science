import { useCallback, useEffect, useRef, useState } from 'react';
import { Linking, Modal, Platform, Pressable, ScrollView, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon } from '@/components/ui/icon';
import { Button, Pill } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { sendVoiceTurn, type ConversationTurnResponse } from '@/services/api';
import { shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';
import { abrirRota } from '@/utils/maps';

export type LivePhase = 'listening' | 'thinking' | 'speaking' | 'paused';

type SpeechRecInstance = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous?: boolean;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((ev: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function getSpeechRecCtor(): (new () => SpeechRecInstance) | null {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecInstance;
    webkitSpeechRecognition?: new () => SpeechRecInstance;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

type Props = {
  visible: boolean;
  onClose: () => void;
  sessionId: string;
  regiaoAdministrativa: string;
  apiBaseUrl: string;
  onTurnComplete: (userText: string, resp: ConversationTurnResponse) => void;
  onToast: (msg: string, icon?: string) => void;
};

export function ZeloLiveModal({
  visible,
  onClose,
  sessionId,
  regiaoAdministrativa,
  apiBaseUrl,
  onTurnComplete,
  onToast,
}: Props) {
  const insets = useSafeAreaInsets();
  const [phase, setPhase] = useState<LivePhase>('listening');
  const [handsFree, setHandsFree] = useState(true);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [lastUserText, setLastUserText] = useState('');
  const [lastResponse, setLastResponse] = useState<ConversationTurnResponse | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);

  const visibleRef = useRef(visible);
  const phaseRef = useRef<LivePhase>('listening');
  const handsFreeRef = useRef(handsFree);
  const speechRecRef = useRef<SpeechRecInstance | null>(null);
  const audioRef = useRef<{ pause: () => void } | null>(null);
  const streamRef = useRef<{ getTracks: () => { stop: () => void }[] } | null>(null);
  const mediaRecRef = useRef<{ stop: () => void; state?: string } | null>(null);
  const audioCtxRef = useRef<{ close: () => Promise<void> } | null>(null);
  const rafRef = useRef<number | null>(null);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    visibleRef.current = visible;
    handsFreeRef.current = handsFree;
  }, [handsFree, visible]);

  const setPhaseSync = useCallback((next: LivePhase) => {
    phaseRef.current = next;
    setPhase(next);
  }, []);

  // Animação fluida do orbe estilo Gemini Live
  const orbScale = useSharedValue(1);
  const ringOpacity = useSharedValue(0.35);

  useEffect(() => {
    if (!visible) return;
    if (phase === 'listening') {
      orbScale.value = withRepeat(
        withSequence(
          withTiming(1.08, { duration: 750, easing: Easing.inOut(Easing.ease) }),
          withTiming(0.96, { duration: 750, easing: Easing.inOut(Easing.ease) }),
        ),
        -1,
        true,
      );
      ringOpacity.value = withRepeat(withTiming(0.65, { duration: 750 }), -1, true);
    } else if (phase === 'thinking') {
      orbScale.value = withRepeat(
        withSequence(
          withTiming(1.12, { duration: 420 }),
          withTiming(0.94, { duration: 420 }),
        ),
        -1,
        true,
      );
      ringOpacity.value = withRepeat(withTiming(0.8, { duration: 420 }), -1, true);
    } else if (phase === 'speaking') {
      orbScale.value = withRepeat(
        withSequence(
          withTiming(1.14, { duration: 300 }),
          withTiming(1.0, { duration: 300 }),
        ),
        -1,
        true,
      );
      ringOpacity.value = withRepeat(withTiming(0.75, { duration: 300 }), -1, true);
    } else {
      orbScale.value = withTiming(1, { duration: 250 });
      ringOpacity.value = withTiming(0.18, { duration: 250 });
    }
  }, [orbScale, phase, ringOpacity, visible]);

  const orbStyle = useAnimatedStyle(() => ({
    transform: [{ scale: orbScale.value }],
  }));

  const ringStyle = useAnimatedStyle(() => ({
    opacity: ringOpacity.value,
    transform: [{ scale: orbScale.value * 1.24 }],
  }));

  const stopAudioOutput = useCallback(() => {
    if (audioRef.current) {
      try {
        audioRef.current.pause();
      } catch {
        // Ignora erro ao interromper reprodução.
      }
      audioRef.current = null;
    }
    if (Platform.OS === 'web' && typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  }, []);

  const stopAudioInput = useCallback(() => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    if (rafRef.current !== null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (speechRecRef.current) {
      try {
        speechRecRef.current.onend = null;
        speechRecRef.current.onresult = null;
        speechRecRef.current.onerror = null;
        speechRecRef.current.stop();
      } catch {
        // Ignora parada repetida.
      }
      speechRecRef.current = null;
    }
    if (mediaRecRef.current && mediaRecRef.current.state !== 'inactive') {
      try {
        mediaRecRef.current.stop();
      } catch {
        // Ignora parada repetida.
      }
    }
    mediaRecRef.current = null;
    if (audioCtxRef.current) {
      void audioCtxRef.current.close().catch(() => undefined);
      audioCtxRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
    }
  }, []);

  const stopAll = useCallback(() => {
    stopAudioInput();
    stopAudioOutput();
  }, [stopAudioInput, stopAudioOutput]);

  const startListeningRef = useRef<() => void>(() => undefined);

  const speakAndContinue = useCallback(
    (resp: ConversationTurnResponse) => {
      if (!visibleRef.current) return;
      stopAudioOutput();
      setPhaseSync('speaking');
      const speechText = resp.spoken_guidance || resp.synthesized_guidance;

      const finishTurn = () => {
        if (!visibleRef.current || phaseRef.current !== 'speaking') return;
        if (handsFreeRef.current) {
          setPhaseSync('listening');
          restartTimerRef.current = setTimeout(() => {
            if (visibleRef.current && phaseRef.current === 'listening') {
              startListeningRef.current();
            }
          }, 320);
        } else {
          setPhaseSync('paused');
        }
      };

      if (Platform.OS !== 'web') {
        finishTurn();
        return;
      }

      if (resp.tts_audio_base64 && typeof Audio !== 'undefined') {
        try {
          const audio = new Audio(`data:${resp.tts_mime_type};base64,${resp.tts_audio_base64}`);
          audioRef.current = audio;
          audio.onended = finishTurn;
          audio.onerror = finishTurn;
          void audio.play().catch(() => {
            // Fallback para speechSynthesis se navegador bloquear autoplay
            if (typeof window !== 'undefined' && 'speechSynthesis' in window && speechText) {
              const utter = new SpeechSynthesisUtterance(speechText);
              utter.lang = 'pt-BR';
              utter.rate = 0.98;
              utter.onend = finishTurn;
              utter.onerror = finishTurn;
              window.speechSynthesis.speak(utter);
            } else {
              finishTurn();
            }
          });
          return;
        } catch {
          // Segue para speechSynthesis
        }
      }

      if (typeof window !== 'undefined' && 'speechSynthesis' in window && speechText) {
        const utter = new SpeechSynthesisUtterance(speechText);
        utter.lang = 'pt-BR';
        utter.rate = 0.98;
        utter.onend = finishTurn;
        utter.onerror = finishTurn;
        window.speechSynthesis.speak(utter);
        return;
      }

      finishTurn();
    },
    [setPhaseSync, stopAudioOutput],
  );

  const sendLiveTurn = useCallback(
    async (opts: { text?: string; audioBlob?: Blob }) => {
      if (!visibleRef.current) return;
      stopAudioInput();
      setPhaseSync('thinking');
      setLiveError(null);
      if (opts.text) setLastUserText(opts.text);
      setLiveTranscript('');

      try {
        const cleanText = opts.text?.trim() ?? '';
        const queryComRa =
          cleanText && !/ceilandia|taguatinga|asa sul|asa norte|gama|samambaia|guara|planaltina|sobradinho/i.test(cleanText)
            ? `${cleanText} (Região do paciente: ${regiaoAdministrativa})`
            : cleanText;

        const resp = await sendVoiceTurn(
          {
            text: queryComRa || undefined,
            audioBlob: opts.audioBlob,
            session_id: sessionId,
            days_since_emission: 166,
            synthesize_audio: true,
          },
          apiBaseUrl,
        );

        if (!visibleRef.current) return;
        const userTranscript = cleanText || resp.transcript || 'Mensagem de voz';
        setLastUserText(userTranscript);
        setLastResponse(resp);
        onTurnComplete(userTranscript, resp);
        speakAndContinue(resp);
      } catch (err) {
        if (!visibleRef.current) return;
        setLiveError(err instanceof Error ? err.message : 'Erro ao consultar a Zelo.');
        setPhaseSync('paused');
      }
    },
    [apiBaseUrl, onTurnComplete, regiaoAdministrativa, sessionId, setPhaseSync, speakAndContinue, stopAudioInput],
  );

  const startVadMediaRecorder = useCallback(async () => {
    if (
      Platform.OS !== 'web' ||
      typeof navigator === 'undefined' ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === 'undefined'
    ) {
      setLiveError('Seu navegador não liberou microfone para captura ao vivo.');
      setPhaseSync('paused');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!visibleRef.current || phaseRef.current !== 'listening') {
        stream.getTracks().forEach((tr) => tr.stop());
        return;
      }
      streamRef.current = stream;

      const chunks: Blob[] = [];
      const recorder = new MediaRecorder(stream);
      let speechDetected = false;
      let silenceStartedAt = 0;
      const startedAt = Date.now();

      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunks.push(ev.data);
      };
      recorder.onstop = () => {
        if (!visibleRef.current || phaseRef.current !== 'listening' || !speechDetected) return;
        const blob = new Blob(chunks, { type: 'audio/webm' });
        if (blob.size > 400) {
          void sendLiveTurn({ audioBlob: blob });
        }
      };

      mediaRecRef.current = recorder;
      recorder.start();

      // Detector automático de pausa na fala (VAD via AudioContext RMS)
      const AudioCtxCtor =
        (window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext })
          .AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

      if (AudioCtxCtor) {
        const ctx = new AudioCtxCtor();
        audioCtxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        const data = new Uint8Array(analyser.frequencyBinCount);

        const tick = () => {
          if (!visibleRef.current || phaseRef.current !== 'listening') return;
          analyser.getByteTimeDomainData(data);
          let sum = 0;
          for (let i = 0; i < data.length; i += 1) {
            const v = (data[i] - 128) / 128;
            sum += v * v;
          }
          const rms = Math.sqrt(sum / data.length);
          const now = Date.now();
          if (rms > 0.025) {
            speechDetected = true;
            silenceStartedAt = 0;
            setLiveTranscript('Capturando sua voz... (envia automático na pausa)');
          } else if (speechDetected) {
            if (silenceStartedAt === 0) silenceStartedAt = now;
            if (now - silenceStartedAt > 1350) {
              recorder.stop();
              return;
            }
          } else if (now - startedAt > 15000) {
            stopAudioInput();
            setPhaseSync('paused');
            return;
          }
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      }
    } catch {
      setLiveError('Permita o acesso ao microfone no navegador para usar o Modo Ao Vivo.');
      setPhaseSync('paused');
    }
  }, [sendLiveTurn, setPhaseSync, stopAudioInput]);

  const startListening = useCallback(() => {
    if (!visibleRef.current) return;
    stopAll();
    setLiveError(null);
    setLiveTranscript('');
    setPhaseSync('listening');

    if (Platform.OS !== 'web') {
      onToast('No celular nativo, use a versão Web para o loop de microfone ao vivo.', 'mic');
      setPhaseSync('paused');
      return;
    }

    const RecCtor = getSpeechRecCtor();
    if (!RecCtor) {
      void startVadMediaRecorder();
      return;
    }

    const rec = new RecCtor();
    rec.lang = 'pt-BR';
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    speechRecRef.current = rec;

    let finalCaptured = '';
    rec.onresult = (ev) => {
      if (!visibleRef.current || phaseRef.current !== 'listening') return;
      let interim = '';
      for (let i = 0; i < ev.results.length; i += 1) {
        const res = ev.results[i];
        const txtChunk = res[0]?.transcript ?? '';
        if (res.isFinal) {
          finalCaptured = `${finalCaptured} ${txtChunk}`.trim();
        } else {
          interim += txtChunk;
        }
      }
      setLiveTranscript((finalCaptured || interim).trim());
      if (finalCaptured) {
        const queryToSend = finalCaptured;
        finalCaptured = '';
        void sendLiveTurn({ text: queryToSend });
      }
    };

    rec.onerror = (ev) => {
      if (!visibleRef.current || phaseRef.current !== 'listening') return;
      if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
        setLiveError('Microfone bloqueado no navegador. Libere a permissão de áudio para conversar.');
        setPhaseSync('paused');
      }
    };

    rec.onend = () => {
      if (!visibleRef.current || phaseRef.current !== 'listening') return;
      if (finalCaptured.trim()) {
        const queryToSend = finalCaptured.trim();
        finalCaptured = '';
        void sendLiveTurn({ text: queryToSend });
      } else if (handsFreeRef.current) {
        restartTimerRef.current = setTimeout(() => {
          if (visibleRef.current && phaseRef.current === 'listening') {
            startListeningRef.current();
          }
        }, 250);
      } else {
        setPhaseSync('paused');
      }
    };

    try {
      rec.start();
    } catch {
      void startVadMediaRecorder();
    }
  }, [onToast, sendLiveTurn, setPhaseSync, startVadMediaRecorder, stopAll]);

  useEffect(() => {
    startListeningRef.current = startListening;
  }, [startListening]);

  useEffect(() => {
    if (!visible) {
      stopAll();
      return;
    }
    const timer = setTimeout(() => {
      if (Platform.OS === 'web' && typeof window !== 'undefined' && 'speechSynthesis' in window) {
        stopAudioOutput();
        setPhaseSync('speaking');
        const greet = new SpeechSynthesisUtterance(
          'Oi! Pode falar comigo, estou te ouvindo. Como posso te ajudar no SUS hoje?',
        );
        greet.lang = 'pt-BR';
        greet.rate = 1.02;
        const goListen = () => {
          if (visibleRef.current && phaseRef.current === 'speaking') {
            startListeningRef.current();
          }
        };
        greet.onend = goListen;
        greet.onerror = goListen;
        window.speechSynthesis.speak(greet);
        // Fallback se speechSynthesis não disparar onend em alguns navegadores
        restartTimerRef.current = setTimeout(() => {
          if (visibleRef.current && phaseRef.current === 'speaking') {
            window.speechSynthesis.cancel();
            startListeningRef.current();
          }
        }, 4800);
      } else {
        startListeningRef.current();
      }
    }, 120);
    return () => {
      clearTimeout(timer);
      stopAll();
    };
  }, [setPhaseSync, stopAll, stopAudioOutput, visible]);

  function handleOrbPress() {
    if (phase === 'speaking') {
      // Barge-in imediato: interrompe Zelo e volta a ouvir na hora!
      startListening();
    } else if (phase === 'listening') {
      if (mediaRecRef.current && mediaRecRef.current.state === 'recording') {
        mediaRecRef.current.stop();
      } else {
        stopAudioInput();
        setPhaseSync('paused');
      }
    } else if (phase === 'paused') {
      startListening();
    }
  }

  function handleCloseModal() {
    stopAll();
    setLiveTranscript('');
    setLiveError(null);
    onClose();
  }

  const orbBg =
    phase === 'speaking'
      ? colors.secondary
      : phase === 'thinking'
        ? colors['surface-tint']
        : phase === 'listening'
          ? colors.accent
          : colors['inverse-surface'];

  const phaseTitle =
    phase === 'listening'
      ? 'Ouvindo você...'
      : phase === 'thinking'
        ? 'Consultando SUS-DF...'
        : phase === 'speaking'
          ? 'Zelo falando • toque para interromper'
          : 'Microfone em pausa';

  const statusTone =
    phase === 'speaking'
      ? 'bg-secondary-container/20 border-secondary-fixed/40'
      : phase === 'listening'
        ? 'bg-primary-fixed/15 border-primary-fixed-dim/35'
        : 'bg-white/10 border-white/15';

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="fullScreen" onRequestClose={handleCloseModal}>
      <View
        className="flex-1 bg-primary"
        style={{ paddingTop: Math.max(insets.top, 16), paddingBottom: Math.max(insets.bottom, 20) }}>
        {/* Topo */}
        <View className="flex-row items-center justify-between px-5 py-2">
          <View className="flex-row items-center gap-2">
            <View className="h-2.5 w-2.5 rounded-full bg-secondary-fixed" />
            <Txt v="label-md" upper className="text-primary-fixed">
              Zelo Ao Vivo • {regiaoAdministrativa.replace(' - DF', '')}
            </Txt>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => setHandsFree((h) => !h)}
            className={`rounded-full px-3 py-1.5 ${handsFree ? 'bg-secondary' : 'bg-white/15'}`}>
            <Txt v="label-sm" className="text-on-primary">
              {handsFree ? 'Contínuo ON' : 'Contínuo OFF'}
            </Txt>
          </Pressable>
        </View>

        {/* Área Central com Orbe Pulsante & Cartão Vivo */}
        <ScrollView contentContainerClassName="flex-grow items-center justify-center gap-6 px-6 py-4">
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={phaseTitle}
            onPress={handleOrbPress}
            className="items-center justify-center py-4">
            <Animated.View
              style={[
                {
                  position: 'absolute',
                  width: 176,
                  height: 176,
                  borderRadius: 88,
                  backgroundColor: orbBg,
                },
                ringStyle,
              ]}
            />
            <Animated.View
              style={[
                {
                  width: 136,
                  height: 136,
                  borderRadius: 68,
                  backgroundColor: orbBg,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderWidth: 2,
                  borderColor: 'rgba(255,255,255,0.28)',
                },
                shadow.xl,
                orbStyle,
              ]}>
              <Icon
                name={
                  phase === 'speaking'
                    ? 'graphic_eq'
                    : phase === 'thinking'
                      ? 'auto_awesome'
                      : phase === 'listening'
                        ? 'mic'
                        : 'mic_off'
                }
                size={48}
                color="on-primary"
              />
            </Animated.View>
          </Pressable>

          <View className={`w-full max-w-md items-center gap-2 rounded-2xl border p-4 ${statusTone}`}>
            <Txt v="title-md" className="text-center text-on-primary">
              {phaseTitle}
            </Txt>

            {liveTranscript ? (
              <Txt v="body-lg" className="text-center text-secondary-fixed">
                “{liveTranscript}”
              </Txt>
            ) : lastUserText && phase !== 'listening' ? (
              <Txt v="body-sm" className="text-center text-primary-fixed">
                Você disse: “{lastUserText}”
              </Txt>
            ) : (
              <Txt v="body-sm" className="text-center text-primary-fixed">
                Fale sobre seu remédio, receita, farmácia ou preparo pré-exame.
              </Txt>
            )}
          </View>

          {liveError && (
            <View className="w-full max-w-md rounded-xl bg-error-container p-3.5">
              <Txt v="body-sm" w="medium" className="text-on-error-container">
                {liveError}
              </Txt>
            </View>
          )}

          {/* Legenda e Cartão Dinâmico da Última Resposta da Zelo */}
          {lastResponse && (
            <View className="w-full max-w-md gap-3 rounded-2xl bg-surface-container-lowest p-4" style={shadow.xl}>
              <View className="flex-row flex-wrap items-center justify-between gap-2">
                <Pill
                  label={
                    lastResponse.is_clinical_block
                      ? 'Alerta Médico / Urgência'
                      : lastResponse.primary_route === 'CONVERSA_ACOLHIMENTO'
                        ? 'Zelo Voz • Conversa'
                        : lastResponse.primary_route.replace(/_/g, ' ')
                  }
                  tone={
                    lastResponse.is_clinical_block
                      ? 'danger'
                      : lastResponse.primary_route === 'CONVERSA_ACOLHIMENTO'
                        ? 'info'
                        : 'success'
                  }
                />
                <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                  Turno {lastResponse.turn_count}
                </Txt>
              </View>

              <Txt v="body-md" className="text-on-surface">
                {lastResponse.spoken_guidance || lastResponse.synthesized_guidance}
              </Txt>

              {lastResponse.preparation_tips.length > 0 && (
                <View className="gap-1 rounded-xl bg-surface-container-low p-3">
                  <Txt v="label-sm" upper className="text-primary">
                    Preparo Pré-Exame
                  </Txt>
                  {lastResponse.preparation_tips.slice(0, 2).map((tip, i) => (
                    <Txt key={i} v="body-sm" className="text-on-surface">
                      • {tip}
                    </Txt>
                  ))}
                </View>
              )}

              {lastResponse.audited_medications.length > 0 && (
                <View className="gap-1 rounded-xl bg-surface-container-low p-3">
                  <Txt v="label-sm" upper className="text-primary">
                    Onde retirar ({lastResponse.audited_medications[0].validity_days}d)
                  </Txt>
                  <Txt v="body-sm" className="text-on-surface">
                    {lastResponse.audited_medications[0].where_to_collect}
                  </Txt>
                </View>
              )}

              {lastResponse.is_clinical_block && (
                <View className="flex-row gap-2">
                  <Button
                    label="Ligar 192 SAMU"
                    icon="ambulance"
                    variant="danger"
                    size="sm"
                    className="flex-1"
                    onPress={() => void Linking.openURL('tel:192')}
                  />
                  <Button
                    label="UPA Próxima"
                    icon="near_me"
                    variant="surface"
                    size="sm"
                    className="flex-1"
                    onPress={() => abrirRota(`UPA perto de ${regiaoAdministrativa}`)}
                  />
                </View>
              )}
            </View>
          )}

          {/* Sugestões interativas tocáveis durante a chamada ao vivo */}
          <View className="w-full max-w-md gap-2">
            <Txt v="label-sm" upper className="text-center text-primary-fixed">
              Ou toque para perguntar agora:
            </Txt>
            <View className="flex-row flex-wrap justify-center gap-2">
              {(lastResponse?.follow_up_suggestions?.length
                ? lastResponse.follow_up_suggestions
                : [
                    'O que você faz?',
                    'Onde retiro metformina 850 mg?',
                    'Preciso de jejum para ultrassom?',
                    'Como conseguir remédio no Alto Custo?',
                  ]
              ).map((sug) => (
                <Pressable
                  key={sug}
                  disabled={phase === 'thinking'}
                  onPress={() => {
                    stopAudioOutput();
                    void sendLiveTurn({ text: sug });
                  }}
                  className="rounded-full border border-primary-fixed-dim/30 bg-white/10 px-3.5 py-2 active:bg-white/20">
                  <Txt v="label-md" className="text-on-primary">
                    {sug}
                  </Txt>
                </Pressable>
              ))}
            </View>
          </View>
        </ScrollView>

        {/* Controles inferiores acessíveis (estilo Gemini Live) */}
        <View className="flex-row items-center justify-center gap-6 px-6 pt-2">
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={phase === 'paused' ? 'Retomar microfone' : 'Pausar microfone'}
            onPress={() => (phase === 'paused' ? startListening() : (stopAll(), setPhaseSync('paused')))}
            className="h-14 w-14 items-center justify-center rounded-full bg-white/15 active:opacity-75">
            <Icon name={phase === 'paused' ? 'mic' : 'pause'} size={26} color="on-primary" />
          </Pressable>

          {phase === 'speaking' && (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Interromper Zelo e falar agora"
              onPress={startListening}
              className="h-16 w-16 items-center justify-center rounded-full bg-secondary active:opacity-80"
              style={shadow.lg}>
              <Icon name="mic" size={30} color="on-primary" />
            </Pressable>
          )}

          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Encerrar conversa por voz e ver no chat"
            onPress={handleCloseModal}
            className="h-14 flex-row items-center justify-center gap-2 rounded-full bg-error px-5 active:opacity-80"
            style={shadow.md}>
            <Icon name="call_end" size={24} color="on-error" />
            <Txt v="label-lg" className="text-on-error">
              Encerrar
            </Txt>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}
