import { Image as ExpoImage } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { cssInterop } from 'nativewind';
import { useEffect } from 'react';
import { Pressable, View, type PressableProps } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { Icon, type ColorToken } from './icon';
import { Txt } from './txt';
import { shadow } from '@/theme/shadows';

// Permite usar className nos componentes de terceiros.
cssInterop(LinearGradient, { className: 'style' });
cssInterop(ExpoImage, { className: 'style' });

export { ExpoImage as Image, LinearGradient };

/* ------------------------------------------------------------------ */
/* Pill / Badge                                                        */
/* ------------------------------------------------------------------ */

type PillTone = 'success' | 'warning' | 'danger' | 'neutral' | 'info' | 'primary' | 'gold';

const PILL_BG: Record<PillTone, string> = {
  success: 'bg-secondary-container',
  warning: 'bg-tertiary-fixed',
  danger: 'bg-error',
  neutral: 'bg-surface-container',
  info: 'bg-primary-fixed',
  primary: 'bg-primary',
  gold: 'bg-tertiary-fixed',
};

const PILL_TEXT: Record<PillTone, string> = {
  success: 'text-on-secondary-container',
  warning: 'text-on-tertiary-fixed-variant',
  danger: 'text-on-error',
  neutral: 'text-on-surface-variant',
  info: 'text-on-primary-fixed',
  primary: 'text-on-primary',
  gold: 'text-on-tertiary-fixed',
};

export function Pill({
  label,
  tone = 'neutral',
  dot,
  upper,
  className = '',
}: {
  label: string;
  tone?: PillTone;
  dot?: boolean;
  upper?: boolean;
  className?: string;
}) {
  return (
    <View
      className={`flex-row items-center self-start gap-1.5 rounded-full px-2 py-0.5 ${PILL_BG[tone]} ${className}`}>
      {dot && <PulseDot />}
      <Txt v="label-sm" upper={upper} className={PILL_TEXT[tone]}>
        {label}
      </Txt>
    </View>
  );
}

/* ------------------------------------------------------------------ */
/* Ponto pulsante ("ao vivo")                                          */
/* ------------------------------------------------------------------ */

export function PulseDot({ color = 'bg-secondary', size = 6 }: { color?: string; size?: number }) {
  const opacity = useSharedValue(1);
  useEffect(() => {
    opacity.value = withRepeat(withTiming(0.35, { duration: 900 }), -1, true);
  }, [opacity]);
  const style = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return (
    <Animated.View
      className={`rounded-full ${color}`}
      style={[{ width: size, height: size }, style]}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Botão                                                               */
/* ------------------------------------------------------------------ */

type ButtonVariant = 'primary' | 'success' | 'surface' | 'white' | 'container' | 'danger';

const BTN_BG: Record<ButtonVariant, string> = {
  primary: 'bg-primary',
  success: 'bg-secondary',
  surface: 'bg-surface-container',
  white: 'bg-surface-container-lowest',
  container: 'bg-primary-container',
  danger: 'bg-error',
};

const BTN_FG: Record<ButtonVariant, ColorToken> = {
  primary: 'on-primary',
  success: 'on-secondary',
  surface: 'primary',
  white: 'primary',
  container: 'primary-fixed',
  danger: 'on-error',
};

const BTN_TEXT: Record<ButtonVariant, string> = {
  primary: 'text-on-primary',
  success: 'text-on-secondary',
  surface: 'text-primary',
  white: 'text-primary',
  container: 'text-primary-fixed',
  danger: 'text-on-error',
};

export function Button({
  label,
  icon,
  iconRight,
  iconColor,
  variant = 'primary',
  size = 'md',
  className = '',
  disabled,
  ...rest
}: PressableProps & {
  label: string;
  icon?: string;
  iconRight?: string;
  iconColor?: ColorToken;
  variant?: ButtonVariant;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}) {
  const pad = size === 'lg' ? 'py-4 px-5' : size === 'sm' ? 'py-2 px-3' : 'py-3 px-3';
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      {...rest}
      className={`flex-row items-center justify-center gap-1.5 rounded-lg ${pad} ${BTN_BG[variant]} ${
        disabled ? 'opacity-50' : 'active:opacity-80'
      } ${className}`}>
      {icon && <Icon name={icon} size={18} color={iconColor ?? BTN_FG[variant]} />}
      <Txt v={size === 'sm' ? 'label-md' : 'label-lg'} className={BTN_TEXT[variant]} numberOfLines={1}>
        {label}
      </Txt>
      {iconRight && <Icon name={iconRight} size={16} color={BTN_FG[variant]} />}
    </Pressable>
  );
}

/* ------------------------------------------------------------------ */
/* Botão redondo só com ícone                                          */
/* ------------------------------------------------------------------ */

export function IconButton({
  icon,
  label,
  size = 40,
  iconSize = 20,
  color = 'primary',
  className = 'bg-surface-container',
  ...rest
}: PressableProps & {
  icon: string;
  label: string;
  size?: number;
  iconSize?: number;
  color?: ColorToken;
  className?: string;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={6}
      {...rest}
      style={{ width: size, height: size }}
      className={`items-center justify-center rounded-full active:opacity-70 ${className}`}>
      <Icon name={icon} size={iconSize} color={color} />
    </Pressable>
  );
}

/* ------------------------------------------------------------------ */
/* Card                                                                */
/* ------------------------------------------------------------------ */

export function Card({
  children,
  className = '',
  elevation = 'sm',
  style,
}: {
  children: React.ReactNode;
  className?: string;
  elevation?: keyof typeof shadow | 'none';
  style?: object;
}) {
  return (
    <View
      className={`rounded-xl bg-surface-container-lowest p-3.5 ${className}`}
      style={[elevation !== 'none' ? shadow[elevation] : null, style]}>
      {children}
    </View>
  );
}

/* ------------------------------------------------------------------ */
/* Cabeçalho de seção                                                  */
/* ------------------------------------------------------------------ */

export function SectionHeader({
  icon,
  title,
  right,
}: {
  icon?: string;
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <View className="flex-row items-center justify-between">
      <View className="flex-1 flex-row items-center gap-2">
        {icon && <Icon name={icon} size={22} />}
        <Txt v="headline-sm" w="medium" className="text-primary">
          {title}
        </Txt>
      </View>
      {right}
    </View>
  );
}

/* ------------------------------------------------------------------ */
/* Bloco de horário (08 / 00)                                          */
/* ------------------------------------------------------------------ */

export function TimeBlock({ time, className, textClass }: { time: string; className: string; textClass: string }) {
  const [h, m] = time.split(':');
  return (
    <View className={`h-11 w-11 items-center justify-center rounded-xl ${className}`}>
      <Txt v="title-md" w="bold" className={`leading-none ${textClass}`}>
        {h}
      </Txt>
      <Txt v="label-sm" w="semibold" className={textClass}>
        {m}
      </Txt>
    </View>
  );
}
