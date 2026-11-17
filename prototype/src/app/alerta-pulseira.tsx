import * as Haptics from 'expo-haptics';
import { useEffect, useState } from 'react';
import { Platform, ScrollView, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BackHeader } from '@/components/layout/app-header';
import { Icon } from '@/components/ui/icon';
import { Button, Card, Pill } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { useApp } from '@/state/app-state';
import { accentBorder, shadow } from '@/theme/shadows';
import { dispararAlertaDose } from '@/utils/alarms';

/**
 * Prévia do "alerta mini" como ele aparece numa pulseira inteligente.
 * O alerta real é a notificação do celular espelhada no pulso.
 */
function TelaPulseira({ tomado }: { tomado: boolean }) {
  const shake = useSharedValue(0);
  useEffect(() => {
    if (tomado) {
      shake.value = 0;
      return;
    }
    shake.value = withRepeat(
      withSequence(
        withTiming(-3, { duration: 60 }),
        withTiming(3, { duration: 60 }),
        withTiming(-3, { duration: 60 }),
        withTiming(0, { duration: 60 }),
        withTiming(0, { duration: 1400 }),
      ),
      -1,
    );
  }, [tomado, shake]);
  const vibra = useAnimatedStyle(() => ({ transform: [{ translateX: shake.value }] }));

  return (
    <View className="items-center">
      {/* pulseira (correia) */}
      <View className="h-14 w-24 rounded-t-3xl bg-inverse-surface/80" />
      <Animated.View style={vibra}>
        <View className="h-64 w-36 rounded-[36px] bg-on-background p-2" style={shadow.xl}>
          <View className="flex-1 items-center justify-between rounded-[28px] bg-black px-3 py-4">
            <Txt v="label-sm" className="text-white/60" style={{ fontSize: 10 }}>
              12:30
            </Txt>
            {tomado ? (
              <View className="items-center gap-1.5">
                <View className="h-12 w-12 items-center justify-center rounded-full bg-secondary">
                  <Icon name="check" size={30} color="#ffffff" />
                </View>
                <Txt v="label-md" className="text-center text-white">
                  Dose registrada
                </Txt>
              </View>
            ) : (
              <View className="items-center gap-1">
                <View className="h-11 w-11 items-center justify-center rounded-full bg-tertiary-fixed-dim">
                  <Icon name="pill" size={24} color="tertiary" />
                </View>
                <Txt v="label-lg" className="text-center text-white" style={{ fontSize: 13 }}>
                  Metformina
                </Txt>
                <Txt v="label-sm" w="medium" className="text-center text-white/70" style={{ fontSize: 10 }}>
                  850mg • após almoço
                </Txt>
              </View>
            )}
            {!tomado && (
              <View className="w-full gap-1.5">
                <View className="items-center rounded-full bg-secondary py-1.5">
                  <Txt v="label-sm" className="text-white">
                    ✓ TOMEI
                  </Txt>
                </View>
                <View className="items-center rounded-full bg-white/15 py-1.5">
                  <Txt v="label-sm" className="text-white">
                    +15 MIN
                  </Txt>
                </View>
              </View>
            )}
          </View>
        </View>
      </Animated.View>
      <View className="h-14 w-24 rounded-b-3xl bg-inverse-surface/80" />
    </View>
  );
}

const PASSOS = [
  { icon: 'bluetooth', titulo: 'Pareie a pulseira com o celular', texto: 'Use o app da sua pulseira (Mi Fitness, Zepp, Galaxy Wearable, Wear OS ou Apple Watch).' },
  { icon: 'notifications_active', titulo: 'Libere as notificações do SUS Digital', texto: 'No app da pulseira, ative "Notificações de apps" e marque o SUS Digital.' },
  { icon: 'vibration', titulo: 'Pronto! O alerta vibra no pulso', texto: 'Na hora da dose, a pulseira vibra e mostra o remédio. Toque em "Tomei" ali mesmo.' },
];

export default function AlertaPulseira() {
  const insets = useSafeAreaInsets();
  const { doses, registrarDose, toast } = useApp();
  const [enviado, setEnviado] = useState(false);
  const tomado = doses.metformina === 'tomada';

  async function testar() {
    if (Platform.OS !== 'web') Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
    const ok = await dispararAlertaDose({ id: 'metformina', nome: 'Metformina', dose: '850mg', horario: '12:30' }, 5);
    setEnviado(ok);
    toast(
      ok
        ? 'Alerta de teste chega em 5 segundos. Bloqueie a tela para ver na pulseira.'
        : 'Não foi possível agendar. Verifique se as notificações estão permitidas.',
      ok ? 'watch' : 'notifications_off',
    );
  }

  return (
    <View className="flex-1 bg-canvas">
      <BackHeader title="Alerta na Pulseira" />
      <ScrollView contentContainerClassName="gap-5 px-4 pt-4" contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}>
        <View className="gap-1.5">
          <Pill label="Versão mini do alerta" tone="gold" upper />
          <Txt v="headline-lg-mobile" className="text-primary">
            O lembrete vai até o seu pulso
          </Txt>
          <Txt v="body-sm" className="text-on-surface-variant">
            Quando chega a hora do remédio, sua pulseira ou relógio vibra e mostra só o essencial: o nome do remédio
            e dois botões grandes.
          </Txt>
        </View>

        <Card className="items-center gap-4 py-6" elevation="md" style={accentBorder(0.25)}>
          <TelaPulseira tomado={tomado} />
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            Prévia de como aparece na pulseira
          </Txt>
        </Card>

        <View className="flex-row gap-2">
          <Button label={enviado ? 'Enviar de novo' : 'Enviar alerta de teste'} icon="watch" iconColor="tertiary-fixed" className="flex-1" size="lg" onPress={testar} />
        </View>
        {!tomado && (
          <Button
            label="Simular toque em “Tomei” na pulseira"
            icon="touch_app"
            variant="surface"
            onPress={() => registrarDose('metformina', 'Metformina 850mg')}
          />
        )}

        <View className="gap-3">
          <Txt v="headline-sm" w="medium" className="text-primary">
            Como ativar
          </Txt>
          {PASSOS.map((p, i) => (
            <Card key={p.titulo} className="flex-row items-start gap-3">
              <View className="h-10 w-10 items-center justify-center rounded-xl bg-primary">
                <Icon name={p.icon} size={20} color="tertiary-fixed" />
              </View>
              <View className="flex-1">
                <Txt v="label-sm" upper className="text-on-surface-variant">
                  Passo {i + 1}
                </Txt>
                <Txt v="title-md" className="text-primary">
                  {p.titulo}
                </Txt>
                <Txt v="body-sm" className="text-on-surface-variant">
                  {p.texto}
                </Txt>
              </View>
            </Card>
          ))}
        </View>

        <View className="flex-row items-start gap-2.5 rounded-xl bg-surface-container p-4">
          <Icon name="info" size={20} />
          <Txt v="body-sm" className="flex-1 text-on-surface-variant">
            Funciona com qualquer pulseira ou relógio que mostra as notificações do celular. Os botões “Tomei” e
            “Adiar” aparecem nos modelos que aceitam respostas rápidas.
          </Txt>
        </View>
      </ScrollView>
    </View>
  );
}
