import * as Haptics from 'expo-haptics';
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { Platform, View } from 'react-native';
import Animated, { FadeInDown, FadeOutDown } from 'react-native-reanimated';

import { Icon } from '@/components/ui/icon';
import { FontScaleContext, Txt } from '@/components/ui/txt';
import {
  notificacoes as notificacoesMock,
  receitas as receitasMock,
  usuario as usuarioMock,
  type Notificacao,
  type Receita,
} from '@/data/mock';
import { clearSession, getDefaultApiBaseUrl, type PrescriptionAuditResponseDTO } from '@/services/api';
import { shadow } from '@/theme/shadows';

type Usuario = typeof usuarioMock;
type DoseState = 'tomada' | 'adiada' | undefined;

export const REGIOES_DF = [
  'Asa Sul - DF',
  'Asa Norte - DF',
  'Ceilândia - DF',
  'Taguatinga - DF',
  'Gama - DF',
  'Samambaia - DF',
  'Planaltina - DF',
  'Guará - DF',
  'Sobradinho - DF',
  'Recanto das Emas - DF',
  'Águas Claras - DF',
  'Santa Maria - DF',
] as const;

export type ReceitaItem = Receita & {
  viaRetirada?: string;
  localSugerido?: string;
  citacaoNormativa?: string;
  oQueLevar?: string[];
  fotoUri?: string;
  auditadaPorIA?: boolean;
};

type AppState = {
  usuario: Usuario | null;
  entrar: (cpf: string, senha: string) => boolean;
  entrarDemo: () => void;
  cadastrar: (dados: Partial<Usuario>) => void;
  sair: () => void;
  doses: Record<string, DoseState>;
  horaTomada: Record<string, string>;
  registrarDose: (medId: string, nome?: string) => void;
  adiarDose: (medId: string) => void;
  regiaoAdministrativa: string;
  setRegiaoAdministrativa: (ra: string) => void;
  receitas: ReceitaItem[];
  adicionarReceitaAuditoria: (
    audit: PrescriptionAuditResponseDTO,
    opts?: { fotoUri?: string; medico?: string; posologia?: string; dataEmissaoIso?: string },
  ) => ReceitaItem[];
  notificacoes: Notificacao[];
  adicionarNotificacao: (item: Omit<Notificacao, 'id'>) => void;
  marcarNotificacaoLida: (id: string) => void;
  marcarTodasLidas: () => void;
  zeloSessionId: string;
  resetZeloSession: () => Promise<void>;
  zeloDraftPrompt: string | null;
  setZeloDraftPrompt: (prompt: string | null) => void;
  zeloRespondeVoz: boolean;
  setZeloRespondeVoz: (v: boolean) => void;
  letrasMaiores: boolean;
  setLetrasMaiores: (v: boolean) => void;
  apiBaseUrl: string;
  setApiBaseUrl: (url: string) => void;
  toast: (mensagem: string, icone?: string) => void;
};

const Ctx = createContext<AppState | null>(null);

function agora() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function formatBrDate(isoOrDate?: string | null) {
  if (!isoOrDate) return new Date().toLocaleDateString('pt-BR');
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoOrDate);
  if (!m) return isoOrDate;
  return `${m[3]}/${m[2]}/${m[1]}`;
}

function novoSessionId() {
  return `zelo-${Math.random().toString(36).slice(2, 10)}`;
}

function vibrar() {
  if (Platform.OS !== 'web') Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
}

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [doses, setDoses] = useState<Record<string, DoseState>>({ losartana: 'tomada' });
  const [horaTomada, setHoraTomada] = useState<Record<string, string>>({ losartana: '08:05' });
  const [regiaoAdministrativa, setRegiaoAdministrativa] = useState<string>('Asa Sul - DF');
  const [receitas, setReceitas] = useState<ReceitaItem[]>(() => [...receitasMock]);
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>(() => [...notificacoesMock]);
  const [zeloSessionId, setZeloSessionId] = useState<string>(() => novoSessionId());
  const [zeloDraftPrompt, setZeloDraftPrompt] = useState<string | null>(null);
  const [zeloRespondeVoz, setZeloRespondeVoz] = useState<boolean>(true);
  const [letrasMaiores, setLetrasMaiores] = useState<boolean>(false);
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(() => getDefaultApiBaseUrl());
  const [toastMsg, setToastMsg] = useState<{ id: number; texto: string; icone: string } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toast = useCallback((texto: string, icone = 'check_circle') => {
    if (timer.current) clearTimeout(timer.current);
    setToastMsg({ id: Date.now(), texto, icone });
    timer.current = setTimeout(() => setToastMsg(null), 3000);
  }, []);

  const adicionarNotificacao = useCallback((item: Omit<Notificacao, 'id'>) => {
    const id = `n-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setNotificacoes((prev) => [{ id, ...item }, ...prev]);
  }, []);

  const registrarDose = useCallback(
    (medId: string, nome?: string) => {
      setDoses((d) => ({ ...d, [medId]: 'tomada' }));
      setHoraTomada((h) => ({ ...h, [medId]: agora() }));
      vibrar();
      toast(`Dose de ${nome ?? medId} registrada no seu prontuário.`);
    },
    [toast],
  );

  const adiarDose = useCallback(
    (medId: string) => {
      setDoses((d) => ({ ...d, [medId]: 'adiada' }));
      toast('Lembrete adiado por 15 minutos.', 'snooze');
    },
    [toast],
  );

  const adicionarReceitaAuditoria = useCallback(
    (
      audit: PrescriptionAuditResponseDTO,
      opts?: { fotoUri?: string; medico?: string; posologia?: string; dataEmissaoIso?: string },
    ) => {
      const novas: ReceitaItem[] = audit.itens.map((it, idx) => {
        const diasTotais = it.dias_validade_receita ?? 180;
        const diasRestantes = it.dias_restantes ?? diasTotais;
        const status: Receita['status'] =
          diasRestantes <= 0 ? 'vencida' : it.alerta_vencimento_proximo || diasRestantes <= 15 ? 'vencendo' : 'ativa';

        const tipo: Receita['tipo'] =
          it.via_retirada === 'ALTO_CUSTO_CEAF'
            ? 'Controle Especial'
            : it.via_retirada === 'FARMACIA_POPULAR' || it.via_retirada === 'UBS_ATENCAO_PRIMARIA'
              ? 'Uso Contínuo'
              : 'Simples';

        return {
          id: `r-ia-${Date.now()}-${idx}`,
          medicamento: it.medicamento,
          posologia: opts?.posologia?.trim() || `${it.via_retirada.replace(/_/g, ' ')} • ${audit.regiao_administrativa}`,
          medico: opts?.medico?.trim() || 'Prescrição SUS-DF Auditada',
          crm: it.principio_ativo_dcb,
          emitida: formatBrDate(opts?.dataEmissaoIso),
          validade: formatBrDate(it.data_limite_validade),
          diasRestantes,
          diasTotais,
          tipo,
          status,
          codigo: `SUS-DF-${new Date().getFullYear()}-${String(Math.floor(100000 + Math.random() * 899999))}`,
          viaRetirada: it.via_retirada,
          localSugerido: it.local_sugerido,
          citacaoNormativa: it.citacao_normativa,
          oQueLevar: it.o_que_levar,
          fotoUri: opts?.fotoUri,
          auditadaPorIA: true,
        };
      });

      if (novas.length > 0) {
        setReceitas((prev) => [...novas, ...prev]);
        for (const rec of novas) {
          if (rec.status === 'vencendo' || rec.status === 'vencida') {
            adicionarNotificacao({
              icone: 'prescriptions',
              tone: rec.status === 'vencida' ? 'danger' : 'warning',
              titulo:
                rec.status === 'vencida'
                  ? `Receita vencida: ${rec.medicamento}`
                  : `Alerta RF08: ${rec.medicamento} vence em ${rec.diasRestantes}d`,
              texto: rec.localSugerido ?? 'Solicite renovação na UBS ou Farmácia de referência.',
              quando: 'Agora',
              lida: false,
            });
          }
        }
      }
      return novas;
    },
    [adicionarNotificacao],
  );

  const resetZeloSession = useCallback(async () => {
    const oldId = zeloSessionId;
    setZeloSessionId(novoSessionId());
    try {
      await clearSession(oldId, apiBaseUrl);
    } catch {
      // Se backend offline, limpa apenas localmente.
    }
    toast('Nova conversa iniciada com a Zelo (memória LGPD reiniciada).', 'refresh');
  }, [apiBaseUrl, toast, zeloSessionId]);

  const value = useMemo<AppState>(
    () => ({
      usuario,
      entrar: (cpf, senha) => {
        if (cpf.replace(/\D/g, '').length !== 11 || senha.length < 4) return false;
        setUsuario(usuarioMock);
        return true;
      },
      entrarDemo: () => {
        setUsuario(usuarioMock);
        toast('Bem-vinda, Dona Maria Helena! Modo demonstração ativo.', 'verified_user');
      },
      cadastrar: (dados) => {
        const nomeCompleto = dados.nomeCompleto?.trim() || usuarioMock.nomeCompleto;
        setUsuario({
          ...usuarioMock,
          ...dados,
          nomeCompleto,
          nome: nomeCompleto.split(' ').slice(0, 2).join(' '),
        });
      },
      sair: () => setUsuario(null),
      doses,
      horaTomada,
      registrarDose,
      adiarDose,
      regiaoAdministrativa,
      setRegiaoAdministrativa,
      receitas,
      adicionarReceitaAuditoria,
      notificacoes,
      adicionarNotificacao,
      marcarNotificacaoLida: (id) =>
        setNotificacoes((prev) => prev.map((n) => (n.id === id ? { ...n, lida: true } : n))),
      marcarTodasLidas: () => setNotificacoes((prev) => prev.map((n) => ({ ...n, lida: true }))),
      zeloSessionId,
      resetZeloSession,
      zeloDraftPrompt,
      setZeloDraftPrompt,
      zeloRespondeVoz,
      setZeloRespondeVoz,
      letrasMaiores,
      setLetrasMaiores,
      apiBaseUrl,
      setApiBaseUrl,
      toast,
    }),
    [
      usuario,
      doses,
      horaTomada,
      registrarDose,
      adiarDose,
      regiaoAdministrativa,
      receitas,
      adicionarReceitaAuditoria,
      notificacoes,
      adicionarNotificacao,
      zeloSessionId,
      resetZeloSession,
      zeloDraftPrompt,
      zeloRespondeVoz,
      letrasMaiores,
      apiBaseUrl,
      toast,
    ],
  );

  return (
    <Ctx.Provider value={value}>
      <FontScaleContext.Provider value={letrasMaiores ? 1.16 : 1}>
        {children}
        {toastMsg && (
          <Animated.View
            key={toastMsg.id}
            entering={FadeInDown}
            exiting={FadeOutDown}
            pointerEvents="none"
            className="absolute inset-x-4 bottom-24 z-50 items-center">
            <View
              className="flex-row items-center gap-2 rounded-full bg-inverse-surface px-4 py-2.5"
              style={shadow.xl}>
              <Icon name={toastMsg.icone} size={18} color="secondary-fixed" />
              <Txt v="label-md" className="shrink text-inverse-on-surface">
                {toastMsg.texto}
              </Txt>
            </View>
          </Animated.View>
        )}
      </FontScaleContext.Provider>
    </Ctx.Provider>
  );
}

export function useApp() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useApp precisa estar dentro de <AppStateProvider>');
  return ctx;
}
