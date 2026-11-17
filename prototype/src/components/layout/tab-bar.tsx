import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { Pressable, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon } from '@/components/ui/icon';
import { Txt } from '@/components/ui/txt';
import { shadow } from '@/theme/shadows';

const TABS: Record<string, { label: string; icon: string }> = {
  inicio: { label: 'Início', icon: 'grid_view' },
  farmacias: { label: 'Farmácias', icon: 'local_pharmacy' },
  remedios: { label: 'Remédios', icon: 'medication' },
  receitas: { label: 'Receitas', icon: 'prescriptions' },
  zelo: { label: 'Zelo', icon: 'graphic_eq' },
};

/** Barra de navegação flutuante em formato de pílula (igual aos HTMLs). */
export function FloatingTabBar({ state, navigateToTab }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  return (
    <View
      pointerEvents="box-none"
      className="absolute inset-x-0 bottom-0 items-center px-4"
      style={{ paddingBottom: Math.max(insets.bottom, 12) }}>
      <View
        className="w-full max-w-md flex-row items-center justify-around rounded-full bg-surface-container-lowest/95 px-2 py-2"
        style={shadow.nav}>
        {state.routes.map((route, index) => {
          const tab = TABS[route.name];
          if (!tab) return null;
          const focused = state.index === index;
          return (
            <Pressable
              key={route.key}
              accessibilityRole="tab"
              accessibilityState={{ selected: focused }}
              accessibilityLabel={tab.label}
              onPress={() => {
                if (!focused) navigateToTab(route.key);
              }}
              className={`h-12 min-w-[60px] items-center justify-center rounded-full px-1.5 ${
                focused ? 'bg-surface-container-high' : ''
              }`}>
              <Icon name={tab.icon} size={20} color={focused ? 'primary' : 'on-surface-variant'} />
              <Txt v="label-sm" w={focused ? 'bold' : 'semibold'} className={focused ? 'text-primary' : 'text-on-surface-variant'} style={{ fontSize: 10, letterSpacing: 0.4 }}>
                {tab.label}
              </Txt>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
