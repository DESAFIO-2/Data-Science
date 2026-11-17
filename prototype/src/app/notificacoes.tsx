import { Pressable, ScrollView, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BackHeader } from '@/components/layout/app-header';
import { Icon, type ColorToken } from '@/components/ui/icon';
import { Card } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { type Notificacao } from '@/data/mock';
import { useApp } from '@/state/app-state';

const TONE: Record<Notificacao['tone'], { bg: string; fg: ColorToken }> = {
  danger: { bg: 'bg-error-container', fg: 'error' },
  warning: { bg: 'bg-tertiary-fixed', fg: 'on-tertiary-fixed-variant' },
  success: { bg: 'bg-secondary-container', fg: 'on-secondary-container' },
  info: { bg: 'bg-primary-fixed', fg: 'primary' },
};

export default function Notificacoes() {
  const insets = useSafeAreaInsets();
  const { notificacoes: lista, marcarNotificacaoLida, marcarTodasLidas } = useApp();
  const naoLidas = lista.filter((n) => !n.lida).length;

  return (
    <View className="flex-1 bg-canvas">
      <BackHeader title="Notificações" />
      <ScrollView contentContainerClassName="gap-3 px-4 pt-4" contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}>
        <View className="flex-row items-center justify-between">
          <Txt v="label-md" upper className="text-on-surface-variant">
            {naoLidas > 0 ? `${naoLidas} não lidas` : 'Tudo em dia'}
          </Txt>
          {naoLidas > 0 && (
            <Pressable hitSlop={8} onPress={marcarTodasLidas}>
              <Txt v="label-md" className="text-primary">
                Marcar todas como lidas
              </Txt>
            </Pressable>
          )}
        </View>
        {lista.map((n) => {
          const t = TONE[n.tone];
          return (
            <Pressable key={n.id} onPress={() => marcarNotificacaoLida(n.id)}>
              <Card className={`flex-row items-start gap-3 ${n.lida ? 'opacity-75' : ''}`}>
                <View className={`h-10 w-10 items-center justify-center rounded-xl ${t.bg}`}>
                  <Icon name={n.icone} size={20} color={t.fg} />
                </View>
                <View className="flex-1">
                  <View className="flex-row items-start justify-between gap-2">
                    <Txt v="title-md" className="flex-1 text-primary" style={{ fontSize: 16 }}>
                      {n.titulo}
                    </Txt>
                    {!n.lida && <View className="mt-1.5 h-2.5 w-2.5 rounded-full bg-on-tertiary-container" />}
                  </View>
                  <Txt v="body-sm" className="text-on-surface-variant">
                    {n.texto}
                  </Txt>
                  <Txt v="label-sm" w="medium" className="mt-1 text-outline">
                    {n.quando}
                  </Txt>
                </View>
              </Card>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
