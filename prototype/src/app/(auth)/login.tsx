import { Link, router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Logo } from '@/components/layout/app-header';
import { Icon } from '@/components/ui/icon';
import { Button, LinearGradient, Pill } from '@/components/ui/primitives';
import { maskCpf, TextField } from '@/components/ui/text-field';
import { Txt } from '@/components/ui/txt';
import { useApp } from '@/state/app-state';
import { shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';

export default function Login() {
  const insets = useSafeAreaInsets();
  const { entrar, entrarDemo, toast } = useApp();
  const [cpf, setCpf] = useState('');
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState<{ cpf?: string; senha?: string }>({});

  function handleEntrar() {
    const e: typeof erro = {};
    if (cpf.replace(/\D/g, '').length !== 11) e.cpf = 'Digite os 11 números do seu CPF.';
    if (senha.length < 4) e.senha = 'A senha precisa ter pelo menos 4 caracteres.';
    setErro(e);
    if (Object.keys(e).length) return;
    if (entrar(cpf, senha)) router.replace('/inicio');
  }

  function handleDemo() {
    entrarDemo();
    router.replace('/inicio');
  }

  return (
    <KeyboardAvoidingView className="flex-1 bg-canvas" behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerClassName="gap-6 px-4"
        contentContainerStyle={{ paddingTop: insets.top + 16, paddingBottom: insets.bottom + 24 }}>
        {/* Topo: marca */}
        <View className="flex-row items-center justify-between">
          <View className="flex-row items-center gap-2.5">
            <Logo />
            <View>
              <Txt v="title-md" className="text-primary">
                SUS Digital
              </Txt>
              <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                Ministério da Saúde
              </Txt>
            </View>
          </View>
          <Pill label="Seguro" tone="success" dot upper />
        </View>

        {/* Cartão de boas-vindas */}
        <LinearGradient
          colors={[colors.primary, colors['primary-container'], colors.primary]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          className="overflow-hidden rounded-2xl p-5"
          style={shadow.xl}>
          <View className="absolute -bottom-3 right-2 opacity-10">
            <Icon name="health_and_safety" size={120} color="on-primary" />
          </View>
          <View className="flex-row items-center gap-2">
            <Icon name="shield_person" size={20} color="tertiary-fixed" />
            <Txt v="label-sm" upper className="text-tertiary-fixed">
              Acesso do Cidadão
            </Txt>
          </View>
          <Txt v="headline-lg-mobile" className="mt-2 text-on-primary">
            Que bom ter você aqui
          </Txt>
          <Txt v="body-sm" className="mt-1 text-primary-fixed">
            Seus remédios, receitas e consultas do SUS em um só lugar, com a Zelo te acompanhando 24h.
          </Txt>
        </LinearGradient>

        {/* Formulário */}
        <View className="gap-4">
          <TextField
            label="CPF"
            icon="badge"
            placeholder="000.000.000-00"
            keyboardType="number-pad"
            value={cpf}
            onChangeText={(t) => setCpf(maskCpf(t))}
            error={erro.cpf}
            autoComplete="off"
          />
          <TextField
            label="Senha"
            icon="lock"
            placeholder="Digite sua senha"
            password
            value={senha}
            onChangeText={setSenha}
            error={erro.senha}
            onSubmitEditing={handleEntrar}
          />
          <Pressable
            accessibilityRole="link"
            className="self-end py-1"
            onPress={() => toast('Enviamos um código de recuperação para o seu celular.', 'sms')}>
            <Txt v="label-lg" className="text-primary underline">
              Esqueci minha senha
            </Txt>
          </Pressable>

          <Button label="Entrar" icon="login" size="lg" iconColor="tertiary-fixed" onPress={handleEntrar} />

          <Button
            label="Testar protótipo agora (Dona Maria Helena)"
            icon="auto_awesome"
            variant="container"
            onPress={handleDemo}
          />

          <View className="flex-row items-center gap-3 py-1">
            <View className="h-px flex-1 bg-outline-variant" />
            <Txt v="label-md" className="text-on-surface-variant">
              OU
            </Txt>
            <View className="h-px flex-1 bg-outline-variant" />
          </View>

          <View className="flex-row gap-2">
            <Button
              label="Entrar com gov.br"
              icon="account_balance"
              variant="white"
              className="flex-1"
              style={shadow.sm}
              onPress={() => toast('Login pelo gov.br estará disponível em breve.', 'info')}
            />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Entrar com biometria"
              onPress={() => toast('Biometria será ativada após o primeiro acesso.', 'fingerprint')}
              className="h-12 w-14 items-center justify-center rounded-lg bg-surface-container active:opacity-70">
              <Icon name="fingerprint" size={26} />
            </Pressable>
          </View>
        </View>

        {/* Criar conta */}
        <View
          className="flex-row items-center justify-between rounded-xl bg-surface-container p-4">
          <View className="flex-1 pr-3">
            <Txt v="title-md" className="text-primary">
              Primeiro acesso?
            </Txt>
            <Txt v="body-sm" className="text-on-surface-variant">
              Crie sua conta em 3 passos com CPF e Cartão SUS.
            </Txt>
          </View>
          <Link href="/cadastro" asChild>
            <Pressable
              accessibilityRole="button"
              className="rounded-lg bg-secondary px-3.5 py-2.5 active:opacity-80">
              <Txt v="label-lg" className="text-on-secondary">
                Criar conta
              </Txt>
            </Pressable>
          </Link>
        </View>

        {/* Rodapé */}
        <View className="items-center gap-3">
          <Pressable
            accessibilityRole="button"
            onPress={() => Linking.openURL('tel:136')}
            className="flex-row items-center gap-1.5 rounded-full bg-surface-container-highest px-3 py-1.5 active:opacity-70">
            <Icon name="phone_in_talk" size={14} />
            <Txt v="label-sm" className="text-primary">
              Precisa de ajuda? Disque Saúde 136
            </Txt>
          </Pressable>
          <View className="flex-row items-center gap-1">
            <Icon name="verified_user" size={13} color="secondary" />
            <Txt v="label-sm" w="medium" className="text-on-surface-variant">
              Seus dados protegidos pela LGPD
            </Txt>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
