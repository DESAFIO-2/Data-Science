import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Platform, Pressable, ScrollView, TextInput, View } from 'react-native';

import { Screen } from '@/components/layout/screen';
import { Icon } from '@/components/ui/icon';
import { Button, Card, Image, LinearGradient, Pill } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import {
  auditPrescription,
  autocompleteMedications,
  type AutocompleteMedicationItem,
} from '@/services/api';
import { type ReceitaItem, useApp } from '@/state/app-state';
import { accentBorder, shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';

type Filtro = 'ativas' | 'vencendo' | 'historico';

const STATUS = {
  ativa: { label: 'Válida', tone: 'success' as const, barra: 'bg-secondary' },
  vencendo: { label: 'Vence em breve', tone: 'warning' as const, barra: 'bg-on-tertiary-container' },
  vencida: { label: 'Vencida', tone: 'neutral' as const, barra: 'bg-outline' },
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days: number) {
  const d = new Date(Date.now() - days * 86400_000);
  return d.toISOString().slice(0, 10);
}

/** Desenho de QR code ilustrativo (identificador único da receita na carteira digital). */
function QrIlustrativo({ seed }: { seed: string }) {
  const n = 21;
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const cells: boolean[] = [];
  for (let i = 0; i < n * n; i++) {
    h = (h * 1103515245 + 12345) >>> 0;
    cells.push(((h >> 16) & 1) === 1);
  }
  const finder = (r: number, c: number) => {
    const inBox = (r0: number, c0: number) => r >= r0 && r < r0 + 7 && c >= c0 && c < c0 + 7;
    const box = inBox(0, 0) ? [0, 0] : inBox(0, n - 7) ? [0, n - 7] : inBox(n - 7, 0) ? [n - 7, 0] : null;
    if (!box) return null;
    const rr = r - box[0];
    const cc = c - box[1];
    return rr === 0 || rr === 6 || cc === 0 || cc === 6 || (rr >= 2 && rr <= 4 && cc >= 2 && cc <= 4);
  };
  return (
    <View className="rounded-xl bg-surface-container-lowest p-3" style={{ width: 21 * 9 + 24 }}>
      {Array.from({ length: n }).map((_, r) => (
        <View key={r} className="flex-row">
          {Array.from({ length: n }).map((__, c) => {
            const f = finder(r, c);
            const on = f ?? cells[r * n + c];
            return <View key={c} style={{ width: 9, height: 9, backgroundColor: on ? colors.primary : 'transparent' }} />;
          })}
        </View>
      ))}
    </View>
  );
}

function ReceitaCard({
  r,
  onMostrar,
  onRenovar,
  onPerguntarZelo,
}: {
  r: ReceitaItem;
  onMostrar: () => void;
  onRenovar: () => void;
  onPerguntarZelo: () => void;
}) {
  const st = STATUS[r.status];
  const pct = r.diasTotais > 0 ? Math.max(0, Math.min(1, r.diasRestantes / r.diasTotais)) : 0;
  const vencida = r.status === 'vencida';
  return (
    <View
      className={`gap-3 overflow-hidden rounded-xl bg-surface-container-lowest p-4 ${vencida ? 'opacity-75' : ''}`}
      style={[r.status === 'vencendo' ? shadow.lg : shadow.sm, accentBorder(r.status === 'vencendo' ? 0.3 : 0.2)]}>
      {r.status === 'vencendo' && (
        <LinearGradient
          colors={[colors.tertiary, colors['tertiary-fixed-dim'], colors.tertiary]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          className="absolute inset-x-0 top-0 h-1"
        />
      )}
      <View className="flex-row items-start justify-between gap-2">
        <View className="flex-1 flex-row items-start gap-3">
          <View className="h-11 w-11 items-center justify-center rounded-xl bg-surface-container-high">
            <Icon name="prescriptions" size={22} />
          </View>
          <View className="flex-1">
            <Txt v="title-md" className="text-primary">
              {r.medicamento}
            </Txt>
            <Txt v="body-sm" className="text-on-surface-variant">
              {r.posologia}
            </Txt>
          </View>
        </View>
        <Pill label={st.label} tone={st.tone} upper />
      </View>

      {r.localSugerido && (
        <View className="gap-1 rounded-lg bg-secondary-container/25 px-3 py-2">
          <Txt v="label-sm" w="bold" className="text-secondary">
            Rota SUS-DF: {r.viaRetirada?.replace(/_/g, ' ')}
          </Txt>
          <Txt v="body-sm" className="text-on-surface">
            {r.localSugerido}
          </Txt>
          {r.citacaoNormativa && (
            <Txt v="label-sm" w="medium" className="text-on-surface-variant">
              Fonte: {r.citacaoNormativa}
            </Txt>
          )}
        </View>
      )}

      {r.fotoUri && (
        <View className="h-24 overflow-hidden rounded-lg bg-surface-container">
          <Image source={{ uri: r.fotoUri }} contentFit="cover" className="h-full w-full" />
        </View>
      )}

      <View className="flex-row items-center gap-2 rounded-lg bg-surface-container-low px-3 py-2">
        <Icon name="stethoscope" size={16} color="secondary" />
        <Txt v="label-sm" w="medium" className="flex-1 text-on-surface" numberOfLines={1}>
          {r.medico} • {r.crm}
        </Txt>
        <Txt v="label-sm" w="medium" className="text-on-surface-variant">
          {r.tipo}
        </Txt>
      </View>

      <View className="gap-1.5">
        <View className="flex-row items-center justify-between">
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            Emitida {r.emitida}
          </Txt>
          <Txt
            v="label-sm"
            className={r.status === 'vencendo' ? 'text-on-tertiary-container' : vencida ? 'text-on-surface-variant' : 'text-secondary'}>
            {vencida ? `Venceu em ${r.validade}` : `Válida até ${r.validade} • ${r.diasRestantes} dias`}
          </Txt>
        </View>
        <View className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
          <View className={`h-1.5 rounded-full ${st.barra}`} style={{ width: `${pct * 100}%` }} />
        </View>
      </View>

      <View className="flex-row flex-wrap gap-2">
        {!vencida && (
          <Button label="Código farmácia" icon="qr_code" size="sm" className="flex-1" onPress={onMostrar} />
        )}
        <Button label="Perguntar à Zelo" icon="spa" size="sm" variant="surface" className="flex-1" onPress={onPerguntarZelo} />
        {r.status === 'vencendo' && (
          <Button label="Renovar" icon="sync_saved_loc" size="sm" variant="container" onPress={onRenovar} />
        )}
      </View>
    </View>
  );
}

export default function Receitas() {
  const {
    receitas,
    regiaoAdministrativa,
    apiBaseUrl,
    adicionarReceitaAuditoria,
    setZeloDraftPrompt,
    toast,
  } = useApp();

  const [filtro, setFiltro] = useState<Filtro>('ativas');
  const [aberta, setAberta] = useState<ReceitaItem | null>(null);

  // Modal: Nova Receita / Autocomplete 1.775 itens + Auditoria RAG v9
  const [novaAberta, setNovaAberta] = useState(false);
  const [buscaMed, setBuscaMed] = useState('');
  const [sugestoes, setSugestoes] = useState<AutocompleteMedicationItem[]>([]);
  const [buscandoAuto, setBuscandoAuto] = useState(false);
  const [selecionado, setSelecionado] = useState<AutocompleteMedicationItem | null>(null);
  const [dataEmissao, setDataEmissao] = useState(todayIso());
  const [posologia, setPosologia] = useState('');
  const [medico, setMedico] = useState('');
  const [fotoUri, setFotoUri] = useState<string | undefined>(undefined);
  const [auditando, setAuditando] = useState(false);
  const [erroAuditoria, setErroAuditoria] = useState<string | null>(null);
  const fotoInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const q = buscaMed.trim();
    if (!novaAberta || q.length < 2 || selecionado?.texto_exibicao === buscaMed) {
      return;
    }
    const timer = setTimeout(() => {
      setBuscandoAuto(true);
      void autocompleteMedications(q, 8, apiBaseUrl)
        .then((res) => setSugestoes(res.resultados))
        .catch(() => setSugestoes([]))
        .finally(() => setBuscandoAuto(false));
    }, 220);
    return () => clearTimeout(timer);
  }, [apiBaseUrl, buscaMed, novaAberta, selecionado]);

  async function handleAuditarReceita() {
    const nomeItem = buscaMed.trim();
    if (!nomeItem) {
      setErroAuditoria('Digite ou selecione o medicamento/exame da receita.');
      return;
    }
    setAuditando(true);
    setErroAuditoria(null);
    try {
      const resp = await auditPrescription(
        {
          itens: [
            {
              nome_digitado: selecionado
                ? `${selecionado.dcb_principio_ativo} ${selecionado.concentracao}`.trim()
                : nomeItem,
              principio_ativo_dcb: selecionado?.dcb_principio_ativo,
              concentracao: selecionado?.concentracao,
              forma_farmaceutica: selecionado?.forma_farmaceutica,
              posologia: posologia.trim() || undefined,
            },
          ],
          data_emissao: dataEmissao || undefined,
          regiao_administrativa: regiaoAdministrativa,
        },
        apiBaseUrl,
      );

      if (!resp.sucesso) {
        setErroAuditoria(resp.resumo_acolhedor);
        return;
      }

      const adicionadas = adicionarReceitaAuditoria(resp, {
        fotoUri,
        medico: medico.trim() || undefined,
        posologia: posologia.trim() || undefined,
        dataEmissaoIso: dataEmissao,
      });

      setNovaAberta(false);
      setBuscaMed('');
      setSelecionado(null);
      setPosologia('');
      setMedico('');
      setFotoUri(undefined);
      toast(`Receita auditada! ${adicionadas[0]?.viaRetirada?.replace(/_/g, ' ') ?? 'Adicionada'}.`, 'verified');
    } catch (err) {
      setErroAuditoria(err instanceof Error ? err.message : 'Erro ao auditar receita na API.');
    } finally {
      setAuditando(false);
    }
  }

  const lista = receitas.filter((r) =>
    filtro === 'ativas' ? r.status !== 'vencida' : filtro === 'vencendo' ? r.status === 'vencendo' : r.status === 'vencida',
  );
  const qtd = {
    ativas: receitas.filter((r) => r.status !== 'vencida').length,
    vencendo: receitas.filter((r) => r.status === 'vencendo').length,
    historico: receitas.filter((r) => r.status === 'vencida').length,
  };

  const FILTROS: { id: Filtro; label: string }[] = [
    { id: 'ativas', label: `Válidas (${qtd.ativas})` },
    { id: 'vencendo', label: `Vencendo (${qtd.vencendo})` },
    { id: 'historico', label: `Histórico (${qtd.historico})` },
  ];

  return (
    <Screen>
      {/* Título */}
      <View className="gap-2">
        <Pill label="Carteira Digital SUS • v9 Auditada" upper className="bg-surface-container-high" />
        <Txt v="headline-lg-mobile" className="text-primary">
          Minhas Receitas
        </Txt>
        <Txt v="body-sm" className="text-on-surface-variant">
          Organize suas receitas locais com validade automática (180d PFPB / 90d CEAF / alertas 15d e 7d) e roteamento oficial DF.
        </Txt>
      </View>

      {/* Resumo */}
      <View className="flex-row gap-2.5">
        <Card className="flex-1 gap-1 p-3">
          <View className="flex-row items-center justify-between">
            <Icon name="task_alt" size={18} color="secondary" />
            <Txt v="headline-sm" className="text-primary">
              {String(qtd.ativas).padStart(2, '0')}
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            Receitas válidas
          </Txt>
        </Card>
        <View className="flex-1 gap-1 rounded-xl bg-tertiary-fixed/50 p-3" style={shadow.sm}>
          <View className="flex-row items-center justify-between">
            <Icon name="schedule" size={18} color="on-tertiary-container" />
            <Txt v="headline-sm" className="text-on-tertiary-container">
              {String(qtd.vencendo).padStart(2, '0')}
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="text-tertiary-container">
            Alerta 15d / 7d
          </Txt>
        </View>
        <Card className="flex-1 gap-1 p-3">
          <View className="flex-row items-center justify-between">
            <Icon name="history" size={18} color="on-surface-variant" />
            <Txt v="headline-sm" className="text-primary">
              {String(qtd.historico).padStart(2, '0')}
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            No histórico
          </Txt>
        </Card>
      </View>

      {/* Adicionar & Auditar Receita */}
      <Pressable
        accessibilityRole="button"
        onPress={() => {
          setErroAuditoria(null);
          setNovaAberta(true);
        }}
        className="min-h-[64px] flex-row items-center gap-3 rounded-xl border-2 border-dashed border-primary-fixed-dim bg-surface-container-low p-4 active:opacity-80">
        <View className="h-11 w-11 items-center justify-center rounded-xl bg-primary">
          <Icon name="document_scanner" size={22} color="tertiary-fixed" />
        </View>
        <View className="flex-1">
          <Txt v="title-md" className="text-primary">
            Cadastrar & Auditar Receita
          </Txt>
          <Txt v="body-sm" className="text-on-surface-variant">
            Busca nos 1.775 itens do SUS + guarda foto local (ADR-0002)
          </Txt>
        </View>
        <Icon name="add_circle" size={24} color="secondary" />
      </Pressable>

      {/* Filtros */}
      <View className="flex-row flex-wrap gap-2">
        {FILTROS.map((f) => {
          const ativo = filtro === f.id;
          return (
            <Pressable
              key={f.id}
              accessibilityRole="tab"
              accessibilityState={{ selected: ativo }}
              onPress={() => setFiltro(f.id)}
              className={`min-h-[38px] justify-center rounded-full px-4 py-2 ${ativo ? 'bg-primary' : 'bg-surface-container-high'}`}>
              <Txt v="label-md" className={ativo ? 'text-on-primary' : 'text-on-surface-variant'}>
                {f.label}
              </Txt>
            </Pressable>
          );
        })}
      </View>

      <View className="gap-3.5">
        {lista.map((r) => (
          <ReceitaCard
            key={r.id}
            r={r}
            onMostrar={() => setAberta(r)}
            onRenovar={() => toast(`Pedido de renovação registrado em ${regiaoAdministrativa}.`, 'task_alt')}
            onPerguntarZelo={() => {
              setZeloDraftPrompt(
                `Tenho uma receita de ${r.medicamento} emitida em ${r.emitida} na região ${regiaoAdministrativa}. Onde retiro e o que devo levar?`,
              );
              router.navigate('/zelo');
            }}
          />
        ))}
        {lista.length === 0 && (
          <Card className="items-center gap-2 py-8">
            <Icon name="inbox" size={32} color="outline" />
            <Txt v="body-md" className="text-on-surface-variant">
              Nenhuma receita nesta categoria.
            </Txt>
          </Card>
        )}
      </View>

      {/* Guia de validade */}
      <View className="gap-2.5 rounded-xl bg-surface-container-high p-4" style={[shadow.sm, accentBorder()]}>
        <View className="flex-row items-center gap-2">
          <View className="h-7 w-7 items-center justify-center rounded-full bg-primary">
            <Icon name="info" size={16} color="primary-fixed" />
          </View>
          <Txt v="title-md" serif className="flex-1 text-primary">
            Quanto tempo vale uma receita no SUS?
          </Txt>
        </View>
        {[
          ['Uso contínuo (pressão, diabetes)', 'Até 180 dias na Farmácia Popular / UBS'],
          ['Alto Custo (CEAF / LME)', '90 dias de validade do Laudo LME'],
          ['Antimicrobianos e Controle Especial', '10 dias (antibióticos) ou 30 dias (Portaria 344)'],
        ].map(([t, d]) => (
          <View key={t} className="flex-row items-center gap-2.5 rounded-lg bg-surface-container-lowest p-2.5">
            <Icon name="schedule" size={18} color="secondary" />
            <View className="flex-1">
              <Txt v="label-lg" className="text-primary">
                {t}
              </Txt>
              <Txt v="body-sm" className="text-on-surface-variant">
                {d}
              </Txt>
            </View>
          </View>
        ))}
      </View>

      {/* Modal do QR code */}
      <Modal visible={!!aberta} transparent animationType="fade" onRequestClose={() => setAberta(null)}>
        <Pressable className="flex-1 items-center justify-center bg-primary/70 px-6" onPress={() => setAberta(null)}>
          <Pressable className="w-full max-w-sm items-center gap-4 rounded-2xl bg-surface-container-lowest p-6" style={shadow.xl}>
            <View className="items-center gap-1">
              <Txt v="label-sm" upper className="text-on-surface-variant">
                Carteira Digital SUS-DF
              </Txt>
              <Txt v="title-lg" className="text-center text-primary">
                {aberta?.medicamento}
              </Txt>
            </View>
            {aberta && <QrIlustrativo seed={aberta.codigo} />}
            <View className="items-center gap-1">
              <Txt v="label-md" className="tracking-widest text-primary">
                {aberta?.codigo}
              </Txt>
              <Txt v="body-sm" className="text-center text-on-surface-variant">
                Apresente com documento oficial com foto e CPF. {aberta?.oQueLevar?.join(' • ')}
              </Txt>
            </View>
            <Button label="Fechar" variant="surface" className="w-full" onPress={() => setAberta(null)} />
          </Pressable>
        </Pressable>
      </Modal>

      {/* Modal: Nova Receita com Autocomplete v9 */}
      <Modal visible={novaAberta} transparent animationType="slide" onRequestClose={() => setNovaAberta(false)}>
        <View className="flex-1 justify-end bg-primary/60">
          <View className="max-h-[90%] rounded-t-3xl bg-surface-container-lowest p-5" style={shadow.xl}>
            <ScrollView keyboardShouldPersistTaps="handled" contentContainerClassName="gap-3.5">
              <View className="flex-row items-center justify-between">
                <Txt v="headline-sm" className="text-primary">
                  Nova Receita / Exame
                </Txt>
                <Pressable onPress={() => setNovaAberta(false)} hitSlop={8}>
                  <Icon name="close" size={22} color="on-surface-variant" />
                </Pressable>
              </View>

              <Txt v="body-sm" className="text-on-surface-variant">
                Digite o nome do medicamento para buscar nos 1.775 itens oficiais (RENAME / REME-DF / PFPB):
              </Txt>

              <View className="gap-1.5">
                <Txt v="label-sm" upper className="text-on-surface-variant">
                  Medicamento ou exame *
                </Txt>
                <View className="h-12 flex-row items-center rounded-xl bg-surface-container-low px-3">
                  <TextInput
                    value={buscaMed}
                    onChangeText={(t) => {
                      setBuscaMed(t);
                      setSelecionado(null);
                      if (t.trim().length < 2) setSugestoes([]);
                    }}
                    placeholder="Ex.: Losartana, Metformina, Adalimumabe..."
                    placeholderTextColor={colors['on-surface-variant']}
                    className="h-full flex-1 font-sans text-body-md text-primary"
                  />
                  {buscandoAuto && <ActivityIndicator size="small" color={colors.primary} />}
                </View>

                {sugestoes.length > 0 && (
                  <View className="overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest">
                    {sugestoes.map((item) => (
                      <Pressable
                        key={item.medication_id}
                        onPress={() => {
                          setSelecionado(item);
                          setBuscaMed(item.texto_exibicao);
                          setSugestoes([]);
                        }}
                        className="border-b border-surface-container p-2.5 active:bg-surface-container-low">
                        <View className="flex-row items-center justify-between gap-2">
                          <Txt v="label-lg" className="flex-1 text-primary">
                            {item.texto_exibicao}
                          </Txt>
                          <Pill
                            label={item.via_retirada.replace(/_/g, ' ').slice(0, 14)}
                            tone={item.dispensacao_gratuita_prevista ? 'success' : 'info'}
                          />
                        </View>
                      </Pressable>
                    ))}
                  </View>
                )}
              </View>

              <View className="gap-1.5">
                <Txt v="label-sm" upper className="text-on-surface-variant">
                  Data de emissão (AAAA-MM-DD)
                </Txt>
                <TextInput
                  value={dataEmissao}
                  onChangeText={setDataEmissao}
                  placeholder="2026-11-17"
                  className="h-11 rounded-xl bg-surface-container-low px-3 font-sans text-body-md text-primary"
                />
                <View className="flex-row gap-2">
                  <Pressable
                    onPress={() => setDataEmissao(todayIso())}
                    className="rounded-full bg-surface-container px-3 py-1">
                    <Txt v="label-sm" className="text-primary">
                      Emitida hoje
                    </Txt>
                  </Pressable>
                  <Pressable
                    onPress={() => setDataEmissao(daysAgoIso(170))}
                    className="rounded-full bg-tertiary-fixed/50 px-3 py-1">
                    <Txt v="label-sm" className="text-tertiary-container">
                      Simular alerta 15d/7d (170d)
                    </Txt>
                  </Pressable>
                </View>
              </View>

              <View className="flex-row gap-2">
                <TextInput
                  value={posologia}
                  onChangeText={setPosologia}
                  placeholder="Posologia (opcional)"
                  className="h-11 flex-1 rounded-xl bg-surface-container-low px-3 font-sans text-body-sm text-primary"
                />
                <TextInput
                  value={medico}
                  onChangeText={setMedico}
                  placeholder="Médico / UBS (opcional)"
                  className="h-11 flex-1 rounded-xl bg-surface-container-low px-3 font-sans text-body-sm text-primary"
                />
              </View>

              {Platform.OS === 'web' && (
                <View className="gap-2">
                  <input
                    ref={(el) => {
                      fotoInputRef.current = el;
                    }}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    style={{ display: 'none' }}
                    onChange={(ev) => {
                      const f = ev.target.files?.[0];
                      if (f) setFotoUri(URL.createObjectURL(f));
                    }}
                  />
                  <Button
                    label={fotoUri ? 'Foto da receita anexada (local)' : 'Anexar foto local da receita (ADR-0002)'}
                    icon="photo_camera"
                    variant="surface"
                    size="sm"
                    onPress={() => fotoInputRef.current?.click()}
                  />
                </View>
              )}

              {erroAuditoria && (
                <View className="rounded-xl bg-error-container/50 p-3">
                  <Txt v="body-sm" className="text-on-error-container">
                    {erroAuditoria}
                  </Txt>
                </View>
              )}

              <Button
                label={auditando ? 'Auditando via RAG v9...' : 'Auditar & Salvar na Carteira'}
                icon="verified_user"
                disabled={auditando}
                onPress={() => void handleAuditarReceita()}
              />
            </ScrollView>
          </View>
        </View>
      </Modal>
    </Screen>
  );
}
