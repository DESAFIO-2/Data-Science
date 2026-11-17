import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useState } from 'react';
import { Platform, Pressable, Switch, View } from 'react-native';

import { Screen } from '@/components/layout/screen';
import { Icon } from '@/components/ui/icon';
import { Button, LinearGradient, Pill, PulseDot } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { useApp } from '@/state/app-state';
import { accentBorder, shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';
import { dispararAlertaDose } from '@/utils/alarms';

type Filtro = 'all' | 'priority' | 'continuous';

function AlarmRow({
  icon,
  iconColor,
  titulo,
  texto,
  value,
  onChange,
  trackOn = colors.primary,
}: {
  icon: string;
  iconColor: keyof typeof colors;
  titulo: string;
  texto: string;
  value: boolean;
  onChange: (v: boolean) => void;
  trackOn?: string;
}) {
  return (
    <View className="flex-row items-center justify-between gap-2 rounded-lg bg-surface-container-low p-3">
      <View className="flex-1 flex-row items-center gap-2.5">
        <Icon name={icon} size={20} color={iconColor} />
        <View className="flex-1">
          <Txt v="label-md" className="text-on-surface">
            {titulo}
          </Txt>
          <Txt v="body-sm" className="leading-tight text-on-surface-variant">
            {texto}
          </Txt>
        </View>
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        accessibilityLabel={titulo}
        trackColor={{ false: colors['surface-container-highest'], true: trackOn }}
        thumbColor={colors['surface-container-lowest']}
      />
    </View>
  );
}

function Ribbon({ from, via }: { from: string; via: string }) {
  return (
    <LinearGradient
      colors={[from, via, from]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 0 }}
      className="absolute inset-x-0 top-0 h-1"
    />
  );
}

export default function Remedios() {
  const { doses, registrarDose, toast } = useApp();
  const [filtro, setFiltro] = useState<Filtro>('all');
  const [alarmes, setAlarmes] = useState({ metformina: true, insulina: true });

  const mostrar = (grupo: Filtro) => filtro === 'all' || filtro === grupo;
  const metforminaTomada = doses.metformina === 'tomada';
  const insulinaTomada = doses.insulina === 'tomada';

  async function testarAlarme(nome: string) {
    if (Platform.OS !== 'web') Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
    const ok = await dispararAlertaDose({ id: 'metformina', nome, dose: '850mg', horario: '12:30' }, 5);
    toast(
      ok
        ? `Alarme de teste da ${nome} chega em 5 segundos (celular e pulseira).`
        : 'Não foi possível agendar. Verifique se as notificações estão permitidas.',
      ok ? 'volume_up' : 'notifications_off',
    );
  }

  const FILTROS: { id: Filtro; label: string }[] = [
    { id: 'all', label: 'Todos (4)' },
    { id: 'priority', label: 'Alta prioridade (2)' },
    { id: 'continuous', label: 'Uso contínuo (2)' },
  ];

  return (
    <Screen>
      {/* Título */}
      <View className="gap-2">
        <View className="flex-row flex-wrap items-center justify-between gap-2">
          <Pill label="Rotina de medicamentos" tone="neutral" upper className="bg-surface-container-high" />
          <View className="flex-row items-center gap-1.5 rounded-full bg-secondary-container/40 px-2.5 py-1">
            <PulseDot />
            <Txt v="label-sm" className="text-on-secondary-container">
              Lembretes ativos
            </Txt>
          </View>
        </View>
        <Txt v="headline-lg-mobile" className="text-primary">
          Meus Remédios & Alarmes
        </Txt>
        <Txt v="body-sm" className="text-on-surface-variant">
          Acompanhamento diário dos seus remédios com alarmes na hora certa, no celular e na pulseira.
        </Txt>
      </View>

      {/* Métricas */}
      <View className="flex-row gap-2.5">
        <View className="flex-1 gap-1 rounded-xl bg-surface-container-lowest p-3" style={shadow.sm}>
          <View className="flex-row items-center justify-between">
            <Icon name="medication" size={18} />
            <Txt v="headline-sm" className="text-primary">
              04
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="leading-tight text-on-surface-variant">
            Remédios monitorados
          </Txt>
        </View>
        <View className="flex-1 gap-1 rounded-xl bg-tertiary-fixed/50 p-3" style={shadow.sm}>
          <View className="flex-row items-center justify-between">
            <Icon name="priority_high" size={18} color="on-tertiary-container" />
            <Txt v="headline-sm" className="text-on-tertiary-container">
              02
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="leading-tight text-tertiary-container">
            Alta prioridade
          </Txt>
        </View>
        <View className="flex-1 gap-1 rounded-xl bg-surface-container-lowest p-3" style={shadow.sm}>
          <View className="flex-row items-center justify-between">
            <Icon name="offline_pin" size={18} color="secondary" />
            <Txt v="title-md" className="text-secondary">
              100%
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="leading-tight text-on-surface-variant">
            Funciona sem internet
          </Txt>
        </View>
      </View>

      {/* Pulseira */}
      <Pressable
        accessibilityRole="button"
        onPress={() => router.push('/alerta-pulseira')}
        className="flex-row items-center gap-3 rounded-xl bg-surface-container-lowest p-3.5 active:bg-surface-container-low"
        style={[shadow.sm, accentBorder(0.25)]}>
        <View className="h-11 w-11 items-center justify-center rounded-xl bg-primary">
          <Icon name="watch" size={24} color="tertiary-fixed" />
        </View>
        <View className="flex-1">
          <Txt v="title-md" className="text-primary">
            Alerta na pulseira
          </Txt>
          <Txt v="body-sm" className="text-on-surface-variant">
            Veja e teste o alerta mini que vibra no seu pulso
          </Txt>
        </View>
        <Icon name="chevron_right" size={22} color="on-surface-variant" />
      </Pressable>

      {/* CTA */}
      <Button
        label="Cadastrar nova receita"
        icon="add"
        iconColor="tertiary-fixed"
        variant="container"
        size="lg"
        style={{ boxShadow: '0 10px 25px rgba(0, 37, 77, 0.18)' }}
        onPress={() => router.navigate('/receitas')}
      />

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
              className={`rounded-full px-4 py-2 ${ativo ? 'bg-primary' : 'bg-surface-container-high'}`}>
              <Txt v="label-md" className={ativo ? 'text-on-primary' : 'text-on-surface-variant'}>
                {f.label}
              </Txt>
            </Pressable>
          );
        })}
      </View>

      <View className="gap-4">
        {/* Metformina */}
        {mostrar('priority') && (
          <View className="gap-3.5 overflow-hidden rounded-xl bg-surface-container-lowest p-4" style={[shadow.lg, accentBorder()]}>
            <Ribbon from={colors.tertiary} via={colors['tertiary-fixed-dim']} />
            <View className="flex-row items-start justify-between pt-1">
              <View className="flex-1 flex-row items-center gap-3">
                <View className="h-12 w-12 items-center justify-center rounded-xl bg-tertiary-container" style={shadow.md}>
                  <Icon name="pill" size={24} color="tertiary-fixed" />
                </View>
                <View className="flex-1">
                  <View className="flex-row items-center gap-1.5">
                    <Pill label="Crítico" tone="gold" upper />
                    <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                      Metabolismo
                    </Txt>
                  </View>
                  <Txt v="title-md" className="mt-0.5 text-primary">
                    Metformina Cloridrato
                  </Txt>
                  <Txt v="body-sm" w="medium" className="text-on-surface-variant">
                    850 mg • Comprimido revestido
                  </Txt>
                </View>
              </View>
              <View className="items-end">
                <Txt v="label-sm" upper className="text-on-tertiary-container">
                  Próxima dose
                </Txt>
                <Txt v="headline-sm" className="text-primary">
                  12:30
                </Txt>
                <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                  {metforminaTomada ? 'tomada ✓' : 'em 38 min'}
                </Txt>
              </View>
            </View>
            <AlarmRow
              icon="volume_up"
              iconColor="tertiary-fixed-dim"
              titulo="Alarme insistente"
              texto="Repete a cada 5 min até você confirmar"
              value={alarmes.metformina}
              onChange={(v) => setAlarmes((a) => ({ ...a, metformina: v }))}
            />
            <View className="flex-row gap-2">
              <Button
                label="Testar alarme"
                icon="e911_emergency"
                variant="surface"
                className="flex-1 bg-surface-container-high"
                onPress={() => testarAlarme('Metformina')}
              />
              <Button
                label={metforminaTomada ? 'Registrado!' : 'Tomei agora'}
                icon={metforminaTomada ? 'verified' : 'done_all'}
                variant="success"
                className="flex-1"
                disabled={metforminaTomada}
                onPress={() => registrarDose('metformina', 'Metformina 850mg')}
              />
            </View>
          </View>
        )}

        {/* Insulina */}
        {mostrar('priority') && (
          <View className="gap-3.5 overflow-hidden rounded-xl bg-surface-container-lowest p-4" style={[shadow.lg, accentBorder()]}>
            <Ribbon from={colors['primary-container']} via={colors['surface-tint']} />
            <View className="flex-row items-start justify-between pt-1">
              <View className="flex-1 flex-row items-center gap-3">
                <View className="h-12 w-12 items-center justify-center rounded-xl bg-primary-fixed-dim/30" style={shadow.md}>
                  <Icon name="vaccines" size={24} />
                </View>
                <View className="flex-1">
                  <View className="flex-row flex-wrap items-center gap-1.5">
                    <Pill label="Injetável" tone="info" upper />
                    <View className="flex-row items-center gap-0.5">
                      <Icon name="ac_unit" size={14} color="on-secondary-container" />
                      <Txt v="label-sm" className="text-on-secondary-container">
                        2°C a 8°C
                      </Txt>
                    </View>
                  </View>
                  <Txt v="title-md" className="mt-0.5 text-primary">
                    Insulina NPH Humana
                  </Txt>
                  <Txt v="body-sm" w="medium" className="text-on-surface-variant">
                    100 UI/mL • Caneta recarregável
                  </Txt>
                </View>
              </View>
              <View className="items-end">
                <Txt v="label-sm" upper className="text-on-surface-variant">
                  Noite
                </Txt>
                <Txt v="headline-sm" className="text-primary">
                  22:00
                </Txt>
                <Txt v="label-sm" w="medium" className="text-on-secondary-fixed-variant">
                  18 UI
                </Txt>
              </View>
            </View>
            <AlarmRow
              icon="screen_lock_portrait"
              iconColor="error"
              titulo="Alarme em tela cheia"
              texto="Toca e vibra mesmo no modo Não Perturbe"
              value={alarmes.insulina}
              onChange={(v) => setAlarmes((a) => ({ ...a, insulina: v }))}
              trackOn={colors.secondary}
            />
            <View className="flex-row items-center justify-between">
              <View className="flex-1">
                <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                  Caneta em uso
                </Txt>
                <Txt v="body-sm" w="semibold" className="text-primary">
                  64 UI restantes (3 aplicações)
                </Txt>
              </View>
              <Button
                label={insulinaTomada ? 'Registrado!' : 'Registrar 18 UI'}
                icon={insulinaTomada ? 'verified' : 'view_stream'}
                disabled={insulinaTomada}
                onPress={() => registrarDose('insulina', 'Insulina 18 UI')}
              />
            </View>
          </View>
        )}

        {/* Losartana */}
        {mostrar('continuous') && (
          <View className="gap-3 overflow-hidden rounded-xl bg-surface-container-lowest p-4" style={[shadow.sm, accentBorder(0.22)]}>
            <View className="flex-row items-start justify-between">
              <View className="flex-1 flex-row items-center gap-3">
                <View className="h-11 w-11 items-center justify-center rounded-lg bg-surface-container-high">
                  <Icon name="cardiology" size={22} />
                </View>
                <View className="flex-1">
                  <View className="flex-row items-center gap-1.5">
                    <Pill label="Cardiovascular" className="bg-surface-container-highest" />
                    <Txt v="label-sm" w="medium" className="text-secondary">
                      Uso contínuo
                    </Txt>
                  </View>
                  <Txt v="title-md" className="mt-0.5 text-primary">
                    Losartana Potássica
                  </Txt>
                  <Txt v="body-sm" w="medium" className="text-on-surface-variant">
                    50 mg • Manhã às 08:00
                  </Txt>
                </View>
              </View>
              <View className="items-end gap-1">
                <View className="flex-row items-center gap-1 rounded-full bg-secondary-container/40 px-2 py-0.5">
                  <Icon name="check" size={14} color="on-secondary-container" />
                  <Txt v="label-sm" className="text-on-secondary-container">
                    Tomado hoje
                  </Txt>
                </View>
                <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                  Amanhã 08:00
                </Txt>
              </View>
            </View>
            <View className="gap-1.5 rounded-lg bg-surface-container-low p-3">
              <View className="flex-row items-center justify-between">
                <View className="flex-row items-center gap-1.5">
                  <Icon name="inventory_2" size={16} color="tertiary-fixed-dim" />
                  <Txt v="label-md" className="text-on-surface">
                    Estoque em casa
                  </Txt>
                </View>
                <Txt v="label-sm" className="text-on-tertiary-container">
                  Repor em 6 dias
                </Txt>
              </View>
              <View className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
                <View className="h-1.5 rounded-full bg-on-tertiary-container" style={{ width: '32%' }} />
              </View>
              <View className="flex-row items-center justify-between">
                <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                  Restam 18 comprimidos
                </Txt>
                <Pressable onPress={() => router.navigate('/farmacias')} hitSlop={8}>
                  <Txt v="label-sm" className="text-primary underline">
                    Onde retirar
                  </Txt>
                </Pressable>
              </View>
            </View>
          </View>
        )}

        {/* Sinvastatina */}
        {mostrar('continuous') && (
          <View className="gap-3 overflow-hidden rounded-xl bg-surface-container-lowest p-4" style={[shadow.sm, accentBorder(0.22)]}>
            <View className="flex-row items-start justify-between">
              <View className="flex-1 flex-row items-center gap-3">
                <View className="h-11 w-11 items-center justify-center rounded-lg bg-surface-container-high">
                  <Icon name="water_drop" size={22} />
                </View>
                <View className="flex-1">
                  <View className="flex-row items-center gap-1.5">
                    <Pill label="Lipídios" className="bg-surface-container-highest" />
                    <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                      Noturno
                    </Txt>
                  </View>
                  <Txt v="title-md" className="mt-0.5 text-primary">
                    Sinvastatina
                  </Txt>
                  <Txt v="body-sm" w="medium" className="text-on-surface-variant">
                    20 mg • Noite às 19:00
                  </Txt>
                </View>
              </View>
              <View className="items-end">
                <Txt v="headline-sm" className="text-primary">
                  19:00
                </Txt>
                <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                  Lembrete suave
                </Txt>
              </View>
            </View>
            <View className="flex-row items-center justify-between rounded-lg bg-surface-container-low p-3">
              <View className="flex-1 flex-row items-center gap-2">
                <Icon name="verified" size={18} color="secondary" />
                <Txt v="body-sm" className="text-on-surface">
                  Estoque seguro: <Txt v="body-sm" w="bold">26 comprimidos</Txt>
                </Txt>
              </View>
              <Pill label="Sem risco de faltar" tone="success" />
            </View>
          </View>
        )}
      </View>

      {/* Aviso de segurança */}
      <View className="gap-2.5 rounded-xl bg-surface-container-high p-4" style={[shadow.sm, accentBorder()]}>
        <View className="flex-row items-center gap-2">
          <View className="h-7 w-7 items-center justify-center rounded-full bg-primary">
            <Icon name="shield_with_heart" size={16} color="primary-fixed" />
          </View>
          <Txt v="title-md" serif className="flex-1 text-primary">
            Segurança do Paciente
          </Txt>
        </View>
        <Txt v="body-sm" className="text-on-surface-variant">
          Os alarmes dos remédios de uso contínuo tocam de novo até você confirmar que tomou. Eles funcionam mesmo
          sem internet, e também vibram na sua pulseira ou relógio.
        </Txt>
      </View>
    </Screen>
  );
}
