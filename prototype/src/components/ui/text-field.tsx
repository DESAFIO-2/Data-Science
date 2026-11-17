import { useState } from 'react';
import { Pressable, TextInput, View, type TextInputProps } from 'react-native';

import { Icon } from './icon';
import { Txt } from './txt';
import { colors } from '@/theme/tokens';

type Props = TextInputProps & {
  label: string;
  icon?: string;
  hint?: string;
  error?: string;
  /** Campo de senha com botão de mostrar/ocultar. */
  password?: boolean;
};

export function TextField({ label, icon, hint, error, password, ...input }: Props) {
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(true);
  const border = error ? 'border-error' : focused ? 'border-primary' : 'border-transparent';

  return (
    <View className="gap-1.5">
      <Txt v="label-md" className="text-on-surface-variant" upper>
        {label}
      </Txt>
      <View
        className={`h-14 flex-row items-center gap-2.5 rounded-xl border-2 bg-surface-container-lowest px-3.5 ${border}`}
        style={{ boxShadow: '0 1px 3px rgba(0, 37, 77, 0.06)' }}>
        {icon && <Icon name={icon} size={20} color={focused ? 'primary' : 'on-surface-variant'} />}
        <TextInput
          placeholderTextColor={colors.outline}
          selectionColor={colors.primary}
          secureTextEntry={password && hidden}
          {...input}
          accessibilityLabel={label}
          onFocus={(e) => {
            setFocused(true);
            input.onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            input.onBlur?.(e);
          }}
          className="h-full flex-1 font-sans text-body-md text-primary"
        />
        {password && (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={hidden ? 'Mostrar senha' : 'Ocultar senha'}
            hitSlop={8}
            onPress={() => setHidden((h) => !h)}>
            <Icon name={hidden ? 'visibility' : 'visibility_off'} size={20} color="on-surface-variant" />
          </Pressable>
        )}
      </View>
      {error ? (
        <View className="flex-row items-center gap-1">
          <Icon name="error_outline" size={14} color="error" />
          <Txt v="body-sm" className="text-error">
            {error}
          </Txt>
        </View>
      ) : hint ? (
        <Txt v="body-sm" className="text-on-surface-variant">
          {hint}
        </Txt>
      ) : null}
    </View>
  );
}

/* Máscaras simples de digitação */

export function maskCpf(v: string) {
  return v
    .replace(/\D/g, '')
    .slice(0, 11)
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
}

export function maskPhone(v: string) {
  return v
    .replace(/\D/g, '')
    .slice(0, 11)
    .replace(/(\d{2})(\d)/, '($1) $2')
    .replace(/(\d{5})(\d{1,4})$/, '$1-$2');
}

export function maskDate(v: string) {
  return v
    .replace(/\D/g, '')
    .slice(0, 8)
    .replace(/(\d{2})(\d)/, '$1/$2')
    .replace(/(\d{2})(\d)/, '$1/$2');
}

export function maskCns(v: string) {
  return v
    .replace(/\D/g, '')
    .slice(0, 15)
    .replace(/(\d{3})(\d)/, '$1 $2')
    .replace(/(\d{4})(\d)/, '$1 $2')
    .replace(/(\d{4})(\d)/, '$1 $2');
}
