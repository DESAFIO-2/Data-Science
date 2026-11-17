import { router } from 'expo-router';
import { Pressable, View } from 'react-native';

import { Screen } from '@/components/layout/screen';
import { Icon } from '@/components/ui/icon';
import {
  Button,
  Card,
  IconButton,
  LinearGradient,
  Pill,
  PulseDot,
  SectionHeader,
  TimeBlock,
} from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { agenda } from '@/data/mock';
import { useApp } from '@/state/app-state';
import { shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';

function saudacao() {
  const h = new Date().getHours();
  if (h < 12) return 'Bom dia';
  if (h < 18) return 'Boa tarde';
  return 'Boa noite';
}

export default function Inicio() {
  const { usuario, doses, horaTomada, registrarDose, adiarDose, receitas, regiaoAdministrativa, setZeloDraftPrompt, toast } = useApp();
  const metforminaTomada = doses.metformina === 'tomada';
  const metforminaAdiada = doses.metformina === 'adiada';
  const receitaAlerta = receitas.find((r) => r.status === 'vencendo') ?? receitas[0];

  return (
    <Screen>
      {/* Saudação + Cartão CNS */}
      <View className="gap-3">
        <View className="flex-row items-end justify-between">
          <View className="flex-1">
            <Txt v="label-sm" w="medium" upper className="text-on-surface-variant">
              Acompanhamento SUS
            </Txt>
            <Txt v="headline-lg-mobile" className="text-primary">
              {saudacao()}, <Txt v="headline-lg-mobile" w="semibold" className="text-primary">{usuario?.nome}</Txt>
            </Txt>
          </View>
          <Pill label="Ativo" tone="success" dot upper />
        </View>

        <LinearGradient
          colors={[colors.primary, colors['primary-container'], colors.primary]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          className="overflow-hidden rounded-xl"
          style={shadow.xl}>
          <View className="absolute bottom-6 right-3 opacity-10">
            <Icon name="health_and_safety" size={100} color="on-primary" />
          </View>
          <View className="gap-3 p-4">
            <View className="flex-row items-center justify-between">
              <View className="flex-row items-center gap-2">
                <Icon name="shield_person" size={20} color="tertiary-fixed" />
                <Txt v="label-sm" upper className="text-tertiary-fixed">
                  Cartão Nacional de Saúde
                </Txt>
              </View>
              <View className="rounded-full bg-surface-container-lowest/15 px-2 py-0.5">
                <Txt v="label-sm" className="text-surface-bright">
                  CNS Ativo
                </Txt>
              </View>
            </View>
            <View>
              <Txt v="label-sm" className="text-primary-fixed-dim/80">
                REGISTRO DO CIDADÃO
              </Txt>
              <View className="flex-row items-center justify-between">
                <Txt v="title-lg" w="medium" className="tracking-widest text-surface-container-lowest">
                  {usuario?.cns}
                </Txt>
                <Icon name="verified" size={20} color="secondary-fixed" />
              </View>
            </View>
          </View>
          <View className="flex-row items-center justify-between bg-primary/40 px-4 py-2">
            <View className="flex-1 flex-row items-center gap-1.5">
              <Icon name="location_on" size={15} color="secondary-fixed" />
              <Txt v="label-sm" className="text-surface-bright" numberOfLines={1}>
                {usuario?.ubs} • {regiaoAdministrativa}
              </Txt>
            </View>
            <Txt v="label-sm" className="text-tertiary-fixed">
              SUS Digital
            </Txt>
          </View>
        </LinearGradient>
      </View>

      {/* Atalho para a Zelo */}
      <Pressable
        accessibilityRole="button"
        onPress={() => router.navigate('/zelo')}
        className="flex-row items-center justify-between rounded-xl bg-surface-container-lowest p-3.5 active:bg-surface-container-low"
        style={shadow.md}>
        <View className="flex-1 flex-row items-center gap-3">
          <LinearGradient
            colors={[colors.primary, colors['primary-container']]}
            start={{ x: 0, y: 1 }}
            end={{ x: 1, y: 0 }}
            className="h-11 w-11 items-center justify-center rounded-xl">
            <Icon name="graphic_eq" size={24} color="tertiary-fixed" />
            <View className="absolute -right-0.5 -top-0.5">
              <PulseDot size={10} />
            </View>
          </LinearGradient>
          <View className="flex-1">
            <View className="flex-row items-center gap-1.5">
              <Txt v="title-md" className="text-primary">
                Fale com a Zelo
              </Txt>
              <View className="rounded bg-tertiary-fixed px-1.5">
                <Txt v="label-sm" className="text-on-tertiary-fixed">
                  24h
                </Txt>
              </View>
            </View>
            <Txt v="body-sm" className="text-on-surface-variant" numberOfLines={1}>
              Dúvidas sobre seus remédios, receitas e consultas
            </Txt>
          </View>
        </View>
        <View className="ml-2 h-8 w-8 items-center justify-center rounded-full bg-surface-container">
          <Icon name="mic" size={18} />
        </View>
      </Pressable>

      {/* Alerta de renovação de receita */}
      <LinearGradient
        colors={[colors['tertiary-fixed'], 'rgba(255, 183, 125, 0.9)']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        className="overflow-hidden rounded-xl p-4"
        style={shadow.lg}>
        <View className="flex-row items-start justify-between">
          <View className="flex-1 flex-row items-center gap-2">
            <View className="h-7 w-7 items-center justify-center rounded-lg bg-tertiary">
              <Icon name="prescriptions" size={18} color="tertiary-fixed" />
            </View>
            <View>
              <Txt v="label-sm" upper className="text-on-tertiary-fixed-variant">
                Renovação de Receita
              </Txt>
              <Txt v="title-md" className="leading-tight text-tertiary">
                {receitaAlerta ? `Expira em ${receitaAlerta.diasRestantes} dias` : 'Expira em breve'}
              </Txt>
            </View>
          </View>
          <Pill label="Urgente" tone="danger" upper />
        </View>
        <View className="mt-3 flex-row items-center justify-between rounded-lg bg-surface-container-lowest/80 p-3">
          <View className="flex-1">
            <Txt v="label-sm" w="medium" className="text-on-surface-variant">
              Medicamento Essencial Contínuo
            </Txt>
            <Txt v="title-md" w="bold" className="text-primary">
              {receitaAlerta?.medicamento ?? 'Losartana Potássica 50mg'}
            </Txt>
            <Txt v="body-sm" className="text-on-surface-variant">
              {receitaAlerta?.localSugerido ?? 'Retirada 100% gratuita na Farmácia Popular (PFPB) ou UBS da sua região'}
            </Txt>
          </View>
          <View className="ml-2 h-10 w-10 items-center justify-center rounded-lg bg-secondary-container">
            <Icon name="inventory_2" size={22} color="on-secondary-container" />
          </View>
        </View>
        <View className="mt-3 flex-row gap-2">
          <Button
            label="Pedir Renovação na UBS"
            icon="sync_saved_loc"
            iconColor="tertiary-fixed"
            className="flex-1"
            onPress={() => toast('Pedido de renovação enviado para a UBS 1 - Asa Sul.', 'task_alt')}
          />
          <Button label="Ver Guia" variant="white" iconRight="arrow_forward" onPress={() => router.navigate('/receitas')} />
        </View>
      </LinearGradient>

      {/* Remédios de hoje */}
      <View className="gap-3">
        <SectionHeader
          icon="pace"
          title="Seus Remédios de Hoje"
          right={
            <Txt v="label-md" upper className="text-on-surface-variant">
              4 tomadas
            </Txt>
          }
        />

        {/* 1. Losartana — concluído */}
        <Card className="flex-row items-start justify-between">
          <View className="flex-1 flex-row items-start gap-3">
            <TimeBlock time="08:00" className="bg-secondary-container" textClass="text-on-secondary-container" />
            <View className="flex-1">
              <View className="flex-row items-center gap-1.5">
                <Txt v="title-md" className="shrink text-primary" numberOfLines={1}>
                  Losartana Potássica
                </Txt>
                <Pill label="50mg" />
              </View>
              <View className="mt-1 flex-row items-center gap-1.5">
                <Icon name="check_circle" size={16} color="secondary" />
                <Txt v="body-sm" w="medium" className="text-secondary">
                  Tomado às {horaTomada.losartana}
                </Txt>
              </View>
            </View>
          </View>
          <Pill label="Pontual" tone="success" upper />
        </Card>

        {/* 2. Metformina — atrasada (destaque) */}
        {metforminaTomada ? (
          <Card className="flex-row items-start justify-between">
            <View className="flex-1 flex-row items-start gap-3">
              <TimeBlock time="12:30" className="bg-secondary-container" textClass="text-on-secondary-container" />
              <View className="flex-1">
                <Txt v="title-md" className="text-primary" numberOfLines={1}>
                  Metformina Cloridrato
                </Txt>
                <View className="mt-1 flex-row items-center gap-1.5">
                  <Icon name="check_circle" size={16} color="secondary" />
                  <Txt v="body-sm" w="medium" className="text-secondary">
                    Tomado às {horaTomada.metformina}
                  </Txt>
                </View>
              </View>
            </View>
            <Pill label="Registrado" tone="success" upper />
          </Card>
        ) : (
          <View className="rounded-xl bg-error-container p-4" style={shadow.md}>
            <View className="flex-row items-start justify-between gap-2">
              <View className="flex-1 flex-row items-start gap-3">
                <TimeBlock time="12:30" className="bg-error" textClass="text-on-error" />
                <View className="flex-1">
                  <Txt v="title-md" w="bold" className="text-on-error-container">
                    Metformina Cloridrato
                  </Txt>
                  <View className="mt-1 flex-row items-center gap-1.5">
                    <Icon name={metforminaAdiada ? 'snooze' : 'timer_off'} size={18} color="error" />
                    <Txt v="body-sm" w="semibold" className="text-error">
                      {metforminaAdiada ? 'Adiado por 15 min' : 'Atrasado há 42 min'}
                    </Txt>
                  </View>
                  <Txt v="label-sm" w="medium" className="mt-0.5 text-on-surface-variant">
                    Tomar com 200ml de água após o almoço
                  </Txt>
                </View>
              </View>
              <Pill label="Alta prioridade" tone="danger" upper />
            </View>
            <View className="mt-4 flex-row gap-2">
              <Button
                label="Confirmar que tomei"
                icon="check"
                variant="success"
                className="flex-1"
                onPress={() => registrarDose('metformina', 'Metformina 850mg')}
              />
              <Button label="+15m" icon="snooze" variant="white" onPress={() => adiarDose('metformina')} />
            </View>
          </View>
        )}

        {/* 3. Sinvastatina */}
        <Card className="flex-row items-start justify-between">
          <View className="flex-1 flex-row items-start gap-3">
            <TimeBlock time="19:00" className="bg-surface-container" textClass="text-primary" />
            <View className="flex-1">
              <View className="flex-row items-center gap-1.5">
                <Txt v="title-md" className="shrink text-primary" numberOfLines={1}>
                  Sinvastatina
                </Txt>
                <Pill label="20mg" />
              </View>
              <View className="mt-1 flex-row items-center gap-1">
                <Icon name="restaurant" size={16} color="on-surface-variant" />
                <Txt v="body-sm" className="text-on-surface-variant">
                  Depois do jantar
                </Txt>
              </View>
            </View>
          </View>
          <Pill label="Aguardando" />
        </Card>

        {/* 4. Insulina */}
        <Card className="flex-row items-start justify-between">
          <View className="flex-1 flex-row items-start gap-3">
            <TimeBlock time="22:00" className="bg-surface-container-high" textClass="text-primary" />
            <View className="flex-1">
              <View className="flex-row items-center gap-1.5">
                <Txt v="title-md" className="shrink text-primary" numberOfLines={1}>
                  Insulina Humana NPH
                </Txt>
                <Pill label="18 UI" tone="info" />
              </View>
              <View className="mt-1 flex-row items-center gap-1">
                <Icon name="volume_up" size={16} color="on-tertiary-container" />
                <Txt v="body-sm" className="text-on-surface-variant" numberOfLines={1}>
                  Lembrete sonoro ativo
                </Txt>
              </View>
            </View>
          </View>
          <Pill label="Noturno" />
        </Card>
      </View>

      {/* Agenda clínica */}
      <View className="gap-3">
        <SectionHeader
          icon="event_upcoming"
          title="Agenda Clínica & Exames"
          right={
            <Pressable onPress={() => toast('A agenda completa chega na próxima versão.', 'event')} hitSlop={8}>
              <Txt v="label-md" className="text-primary">
                Ver todos
              </Txt>
            </Pressable>
          }
        />
        {agenda.map((item) => {
          const exame = item.tipo === 'exame';
          return (
            <Card key={item.id} className="flex-row items-center">
              <View
                className={`mr-3 h-14 w-12 items-center justify-center rounded-xl ${
                  exame ? 'bg-tertiary-container' : 'bg-primary'
                }`}>
                <Txt v="label-sm" className={exame ? 'text-tertiary-fixed' : 'text-primary-fixed-dim'}>
                  {item.diaSemana}
                </Txt>
                <Txt v="title-lg" w="bold" className={`leading-none ${exame ? 'text-on-tertiary-container' : 'text-on-primary'}`}>
                  {item.dia}
                </Txt>
                <Txt v="label-sm" className={exame ? 'text-tertiary-fixed' : 'text-primary-fixed-dim'}>
                  {item.mes}
                </Txt>
              </View>
              <View className="flex-1">
                <View className="flex-row items-center justify-between">
                  <Pill label={item.especialidade} tone={exame ? 'gold' : 'info'} upper />
                  <Txt v="label-md" className={exame ? 'text-tertiary' : 'text-primary'}>
                    {item.hora}
                  </Txt>
                </View>
                <Txt v="title-md" className="mt-0.5 text-primary" numberOfLines={1}>
                  {item.titulo}
                </Txt>
                <View className="flex-row items-center gap-1">
                  <Icon name={exame ? 'warning' : 'apartment'} size={14} color={exame ? 'error' : 'secondary'} />
                  <Txt
                    v="body-sm"
                    w={exame ? 'medium' : 'regular'}
                    className={exame ? 'text-error' : 'text-on-surface-variant'}
                    numberOfLines={1}>
                    {item.local}
                  </Txt>
                </View>
              </View>
              <IconButton
                icon={exame ? 'info' : 'calendar_add_on'}
                label={exame ? 'Perguntar preparo pré-exame para a Zelo' : 'Adicionar ao calendário'}
                size={36}
                iconSize={18}
                className="ml-2 bg-surface-container"
                onPress={() => {
                  if (exame) {
                    setZeloDraftPrompt(
                      `Quais são os cuidados e o preparo de jejum para o exame ${item.titulo} (${item.especialidade}) no SUS-DF?`,
                    );
                    router.navigate('/zelo');
                  } else {
                    toast('Consulta adicionada ao seu calendário.', 'event_available');
                  }
                }}
              />
            </Card>
          );
        })}
      </View>

      {/* Remédio em Casa */}
      <View className="flex-row items-center justify-between rounded-xl bg-surface-container p-4">
        <View className="flex-1 flex-row items-center gap-3">
          <View className="h-10 w-10 items-center justify-center rounded-full bg-surface-container-lowest" style={shadow.sm}>
            <Icon name="local_shipping" size={20} />
          </View>
          <View className="flex-1">
            <Txt v="title-md" className="leading-tight text-primary">
              Remédio em Casa
            </Txt>
            <Txt v="body-sm" className="text-on-surface-variant">
              Entrega gratuita pelo SUS na sua casa
            </Txt>
          </View>
        </View>
        <Button label="Rastrear" size="sm" onPress={() => toast('Sua entrega chega até sexta-feira.', 'local_shipping')} />
      </View>
    </Screen>
  );
}
