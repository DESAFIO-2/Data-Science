import type { ViewStyle } from 'react-native';

// Sombras azuladas das telas de referência (RN 0.76+ suporta boxShadow).
export const shadow = {
  sm: { boxShadow: '0 1px 3px rgba(0, 37, 77, 0.06)' },
  md: { boxShadow: '0 4px 14px rgba(0, 37, 77, 0.08)' },
  lg: { boxShadow: '0 8px 24px rgba(0, 37, 77, 0.10)' },
  xl: { boxShadow: '0 12px 32px rgba(0, 37, 77, 0.16)' },
  header: { boxShadow: '0 4px 24px rgba(0, 37, 77, 0.06)' },
  nav: { boxShadow: '0 12px 36px rgba(0, 37, 77, 0.14)' },
} satisfies Record<string, ViewStyle>;

// Borda azul fina usada nos cards "premium" (farmácias, remédios).
export const accentBorder = (opacity = 0.25): ViewStyle => ({
  borderWidth: 1,
  borderColor: `rgba(0, 91, 170, ${opacity})`,
});
