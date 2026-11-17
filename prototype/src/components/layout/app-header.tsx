import { router } from 'expo-router';
import { Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon } from '@/components/ui/icon';
import { Txt } from '@/components/ui/txt';
import { useApp } from '@/state/app-state';
import { shadow } from '@/theme/shadows';

export function Logo({ size = 40 }: { size?: number }) {
  return (
    <View
      className="items-center justify-center rounded-xl bg-primary"
      style={[{ width: size, height: size }, { boxShadow: '0 4px 12px rgba(0, 37, 77, 0.2)' }]}>
      <Txt v="headline-sm" className="text-primary-fixed" style={{ fontSize: size * 0.55 }}>
        S
      </Txt>
    </View>
  );
}

/**
 * Cabeçalho fixo de todas as telas logadas: logo, nome do app,
 * notificações e atalho para o perfil.
 */
export function AppHeader({ subtitle }: { subtitle?: string }) {
  const insets = useSafeAreaInsets();
  const { notificacoes, regiaoAdministrativa } = useApp();
  const naoLidas = notificacoes.filter((n) => !n.lida).length;
  const displaySubtitle = subtitle ?? `${regiaoAdministrativa} • SUS-DF`;

  return (
    <View className="z-10 bg-surface-container-lowest/95" style={[{ paddingTop: insets.top }, shadow.header]}>
      <View className="h-16 flex-row items-center justify-between gap-3 px-4">
        <View className="min-w-0 flex-1 flex-row items-center gap-2.5">
          <Logo />
          <View className="min-w-0">
            <Txt v="title-md" className="leading-tight text-primary">
              SUS Digital
            </Txt>
            <View className="flex-row items-center gap-1.5">
              <View className="h-1.5 w-1.5 rounded-full bg-secondary" />
              <Txt v="label-sm" w="medium" className="text-on-surface-variant" numberOfLines={1}>
                {displaySubtitle}
              </Txt>
            </View>
          </View>
        </View>
        <View className="flex-row items-center gap-2">
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={naoLidas > 0 ? `Notificações (${naoLidas} não lidas)` : 'Notificações'}
            onPress={() => router.push('/notificacoes')}
            className="h-11 w-11 items-center justify-center rounded-full bg-surface-container active:opacity-70">
            <Icon name="notifications" size={22} />
            {naoLidas > 0 && (
              <View className="absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full border-2 border-surface bg-on-tertiary-container" />
            )}
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Meu perfil"
            onPress={() => router.push('/perfil')}
            className="h-9 w-9 items-center justify-center rounded-full bg-primary active:opacity-70">
            <Icon name="person" size={20} color="on-primary" />
          </Pressable>
        </View>
      </View>
    </View>
  );
}

/** Cabeçalho simples com botão de voltar (telas empilhadas). */
export function BackHeader({ title }: { title: string }) {
  const insets = useSafeAreaInsets();
  return (
    <View className="bg-surface-container-lowest/95" style={[{ paddingTop: insets.top }, shadow.header]}>
      <View className="h-16 flex-row items-center gap-3 px-4">
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Voltar"
          onPress={() => (router.canGoBack() ? router.back() : router.replace('/inicio'))}
          className="h-11 w-11 items-center justify-center rounded-full bg-surface-container active:opacity-70">
          <Icon name="arrow_back" size={22} />
        </Pressable>
        <Txt v="headline-sm" w="medium" className="text-primary">
          {title}
        </Txt>
      </View>
    </View>
  );
}
