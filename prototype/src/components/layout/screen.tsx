import { ScrollView, View } from 'react-native';

import { AppHeader } from './app-header';

/** Espaço reservado no fim da rolagem para a barra de abas flutuante. */
export const TAB_BAR_SPACE = 112;

export function Screen({
  children,
  subtitle,
  header,
}: {
  children: React.ReactNode;
  subtitle?: string;
  /** Substitui o cabeçalho padrão. */
  header?: React.ReactNode;
}) {
  return (
    <View className="flex-1 bg-canvas">
      {header ?? <AppHeader subtitle={subtitle} />}
      <ScrollView
        className="flex-1"
        contentContainerClassName="gap-5 px-4 pt-4"
        contentContainerStyle={{ paddingBottom: TAB_BAR_SPACE }}
        showsVerticalScrollIndicator={false}>
        {children}
      </ScrollView>
    </View>
  );
}
