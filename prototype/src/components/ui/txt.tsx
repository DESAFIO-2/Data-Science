import { createContext, useContext } from 'react';
import { Text, type TextProps } from 'react-native';

export const FontScaleContext = createContext<number>(1);

type Variant =
  | 'label-sm'
  | 'label-md'
  | 'label-lg'
  | 'body-sm'
  | 'body-md'
  | 'body-lg'
  | 'title-md'
  | 'title-lg'
  | 'headline-sm'
  | 'headline-md'
  | 'headline-lg-mobile'
  | 'display-lg-mobile';

type Weight = 'regular' | 'medium' | 'semibold' | 'bold';

// Strings literais para o Tailwind/NativeWind conseguir gerar as classes.
const SIZE: Record<Variant, string> = {
  'label-sm': 'text-label-sm',
  'label-md': 'text-label-md',
  'label-lg': 'text-label-lg',
  'body-sm': 'text-body-sm',
  'body-md': 'text-body-md',
  'body-lg': 'text-body-lg',
  'title-md': 'text-title-md',
  'title-lg': 'text-title-lg',
  'headline-sm': 'text-headline-sm',
  'headline-md': 'text-headline-md',
  'headline-lg-mobile': 'text-headline-lg-mobile',
  'display-lg-mobile': 'text-display-lg-mobile',
};

const BASE_PX: Record<Variant, number> = {
  'label-sm': 11,
  'label-md': 12,
  'label-lg': 14,
  'body-sm': 12,
  'body-md': 14,
  'body-lg': 16,
  'title-md': 16,
  'title-lg': 18,
  'headline-sm': 20,
  'headline-md': 22,
  'headline-lg-mobile': 24,
  'display-lg-mobile': 28,
};

const SANS: Record<Weight, string> = {
  regular: 'font-sans',
  medium: 'font-sans-medium',
  semibold: 'font-sans-semibold',
  bold: 'font-sans-bold',
};

const SERIF: Record<Weight, string> = {
  regular: 'font-serif',
  medium: 'font-serif-medium',
  semibold: 'font-serif-semibold',
  bold: 'font-serif-semibold',
};

// Pesos padrão de cada variante, como no design system dos HTMLs.
const DEFAULT_WEIGHT: Record<Variant, Weight> = {
  'label-sm': 'bold',
  'label-md': 'semibold',
  'label-lg': 'semibold',
  'body-sm': 'regular',
  'body-md': 'regular',
  'body-lg': 'regular',
  'title-md': 'semibold',
  'title-lg': 'semibold',
  'headline-sm': 'semibold',
  'headline-md': 'medium',
  'headline-lg-mobile': 'medium',
  'display-lg-mobile': 'regular',
};

export type TxtProps = TextProps & {
  v?: Variant;
  w?: Weight;
  /** Força Newsreader (serifada). Por padrão, headline/display já usam. */
  serif?: boolean;
  upper?: boolean;
  className?: string;
};

export function Txt({ v = 'body-md', w, serif, upper, className = '', style, children, ...rest }: TxtProps) {
  const fontScale = useContext(FontScaleContext);
  const isSerif = serif ?? (v.startsWith('headline') || v.startsWith('display'));
  const weight = w ?? DEFAULT_WEIGHT[v];
  const family = isSerif ? SERIF[weight] : SANS[weight];
  const scaledStyle =
    fontScale > 1.01
      ? [{ fontSize: Math.round(BASE_PX[v] * fontScale), lineHeight: Math.round(BASE_PX[v] * fontScale * 1.35) }, style]
      : style;

  return (
    <Text
      {...rest}
      style={scaledStyle}
      className={`${SIZE[v]} ${family} ${upper ? 'uppercase' : ''} text-on-surface ${className}`}>
      {children}
    </Text>
  );
}
