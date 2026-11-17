import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Switch, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon } from '@/components/ui/icon';
import { Button, Card } from '@/components/ui/primitives';
import { maskCns, maskCpf, maskDate, maskPhone, TextField } from '@/components/ui/text-field';
import { Txt } from '@/components/ui/txt';
import { useApp } from '@/state/app-state';
import { colors } from '@/theme/tokens';

const PASSOS = [
  { titulo: 'Seus dados', descricao: 'Vamos começar pelo básico. Use os dados do seu documento.' },
  { titulo: 'Sua saúde', descricao: 'Conecte seu Cartão SUS e a sua unidade de saúde.' },
  { titulo: 'Segurança', descricao: 'Crie uma senha e escolha como quer ser avisado.' },
];

const UBS = ['UBS 1 - Asa Sul', 'UBS 2 - Asa Norte', 'UBS 1 - Cruzeiro', 'UBS 3 - Lago Sul'];

function PreferenceRow({
  icon,
  titulo,
  texto,
  value,
  onChange,
}: {
  icon: string;
  titulo: string;
  texto: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <View className="flex-row items-center justify-between gap-3 rounded-lg bg-surface-container-low p-3">
      <View className="flex-1 flex-row items-center gap-2.5">
        <Icon name={icon} size={20} />
        <View className="flex-1">
          <Txt v="label-lg" className="text-on-surface">
            {titulo}
          </Txt>
          <Txt v="body-sm" className="leading-tight text-on-surface-variant">
            {texto}
          </Txt>
        </View>
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        accessibilityLabel={titulo}
        trackColor={{ false: colors['surface-container-highest'], true: colors.primary }}
        thumbColor={colors['surface-container-lowest']}
      />
    </View>
  );
}

export default function Cadastro() {
  const insets = useSafeAreaInsets();
  const { cadastrar } = useApp();
  const [passo, setPasso] = useState(0);
  const [form, setForm] = useState({
    nomeCompleto: '',
    cpf: '',
    nascimento: '',
    celular: '',
    cns: '',
    email: '',
    ubs: UBS[0],
    senha: '',
    confirmar: '',
  });
  const [prefs, setPrefs] = useState({ alarmes: true, pulseira: true, termos: false });
  const [erros, setErros] = useState<Record<string, string>>({});

  const set = (campo: keyof typeof form) => (valor: string) => setForm((f) => ({ ...f, [campo]: valor }));

  function validar() {
    const e: Record<string, string> = {};
    if (passo === 0) {
      if (form.nomeCompleto.trim().split(' ').length < 2) e.nomeCompleto = 'Digite nome e sobrenome.';
      if (form.cpf.replace(/\D/g, '').length !== 11) e.cpf = 'CPF precisa ter 11 números.';
      if (form.nascimento.length !== 10) e.nascimento = 'Use o formato DD/MM/AAAA.';
      if (form.celular.replace(/\D/g, '').length < 10) e.celular = 'Digite o celular com DDD.';
    }
    if (passo === 1) {
      const cns = form.cns.replace(/\D/g, '');
      if (cns.length > 0 && cns.length !== 15) e.cns = 'O Cartão SUS tem 15 números.';
    }
    if (passo === 2) {
      if (form.senha.length < 6) e.senha = 'Use pelo menos 6 caracteres.';
      if (form.confirmar !== form.senha) e.confirmar = 'As senhas não são iguais.';
      if (!prefs.termos) e.termos = 'Você precisa aceitar os termos para continuar.';
    }
    setErros(e);
    return Object.keys(e).length === 0;
  }

  function avancar() {
    if (!validar()) return;
    if (passo < 2) {
      setPasso(passo + 1);
      return;
    }
    cadastrar({
      nomeCompleto: form.nomeCompleto,
      cpf: form.cpf,
      nascimento: form.nascimento,
      celular: form.celular,
      email: form.email,
      ubs: form.ubs,
      ...(form.cns ? { cns: form.cns } : {}),
    });
    router.replace('/inicio');
  }

  function voltar() {
    if (passo > 0) setPasso(passo - 1);
    else router.back();
  }

  return (
    <KeyboardAvoidingView className="flex-1 bg-canvas" behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {/* Cabeçalho com progresso */}
      <View className="gap-4 bg-surface-container-lowest px-4 pb-4" style={{ paddingTop: insets.top + 12, boxShadow: '0 4px 24px rgba(0, 37, 77, 0.06)' }}>
        <View className="flex-row items-center gap-3">
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Voltar"
            onPress={voltar}
            className="h-11 w-11 items-center justify-center rounded-full bg-surface-container active:opacity-70">
            <Icon name="arrow_back" size={22} />
          </Pressable>
          <View className="flex-1">
            <Txt v="label-sm" upper className="text-on-surface-variant">
              Criar conta • Passo {passo + 1} de 3
            </Txt>
            <Txt v="headline-sm" w="medium" className="text-primary">
              {PASSOS[passo].titulo}
            </Txt>
          </View>
        </View>
        <View className="flex-row gap-1.5">
          {PASSOS.map((p, i) => (
            <View
              key={p.titulo}
              className={`h-1.5 flex-1 rounded-full ${i <= passo ? 'bg-secondary' : 'bg-surface-container-highest'}`}
            />
          ))}
        </View>
      </View>

      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerClassName="gap-4 px-4 pt-5"
        contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}>
        <Txt v="body-md" className="text-on-surface-variant">
          {PASSOS[passo].descricao}
        </Txt>

        {passo === 0 && (
          <>
            <TextField
              label="Nome completo"
              icon="person"
              placeholder="Como está no seu documento"
              autoCapitalize="words"
              value={form.nomeCompleto}
              onChangeText={set('nomeCompleto')}
              error={erros.nomeCompleto}
            />
            <TextField
              label="CPF"
              icon="badge"
              placeholder="000.000.000-00"
              keyboardType="number-pad"
              value={form.cpf}
              onChangeText={(t) => set('cpf')(maskCpf(t))}
              error={erros.cpf}
            />
            <TextField
              label="Data de nascimento"
              icon="cake"
              placeholder="DD/MM/AAAA"
              keyboardType="number-pad"
              value={form.nascimento}
              onChangeText={(t) => set('nascimento')(maskDate(t))}
              error={erros.nascimento}
            />
            <TextField
              label="Celular"
              icon="smartphone"
              placeholder="(61) 90000-0000"
              keyboardType="phone-pad"
              value={form.celular}
              onChangeText={(t) => set('celular')(maskPhone(t))}
              error={erros.celular}
              hint="Usamos para enviar lembretes e o código de acesso."
            />
          </>
        )}

        {passo === 1 && (
          <>
            <TextField
              label="Cartão Nacional de Saúde (opcional)"
              icon="credit_card"
              placeholder="000 0000 0000 0000"
              keyboardType="number-pad"
              value={form.cns}
              onChangeText={(t) => set('cns')(maskCns(t))}
              error={erros.cns}
              hint="Não sabe o número? Encontramos pelo seu CPF depois."
            />
            <TextField
              label="E-mail (opcional)"
              icon="mail"
              placeholder="seuemail@exemplo.com"
              keyboardType="email-address"
              autoCapitalize="none"
              value={form.email}
              onChangeText={set('email')}
            />
            <View className="gap-2">
              <Txt v="label-md" upper className="text-on-surface-variant">
                Sua unidade de saúde (UBS)
              </Txt>
              {UBS.map((u) => {
                const ativo = form.ubs === u;
                return (
                  <Pressable
                    key={u}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: ativo }}
                    onPress={() => set('ubs')(u)}
                    className={`flex-row items-center gap-3 rounded-xl border-2 p-3.5 ${
                      ativo ? 'border-primary bg-primary-fixed/40' : 'border-transparent bg-surface-container-lowest'
                    }`}>
                    <Icon name="local_hospital" size={20} color={ativo ? 'primary' : 'on-surface-variant'} />
                    <Txt v="label-lg" className={`flex-1 ${ativo ? 'text-primary' : 'text-on-surface'}`}>
                      {u}
                    </Txt>
                    <Icon
                      name={ativo ? 'radio_button_checked' : 'radio_button_unchecked'}
                      size={20}
                      color={ativo ? 'primary' : 'outline'}
                    />
                  </Pressable>
                );
              })}
            </View>
          </>
        )}

        {passo === 2 && (
          <>
            <TextField
              label="Crie uma senha"
              icon="lock"
              placeholder="Mínimo de 6 caracteres"
              password
              value={form.senha}
              onChangeText={set('senha')}
              error={erros.senha}
            />
            <TextField
              label="Confirme a senha"
              icon="lock"
              placeholder="Digite a senha de novo"
              password
              value={form.confirmar}
              onChangeText={set('confirmar')}
              error={erros.confirmar}
            />
            <Card className="gap-2.5">
              <Txt v="title-md" className="text-primary">
                Como quer ser avisado?
              </Txt>
              <PreferenceRow
                icon="volume_up"
                titulo="Alarme sonoro dos remédios"
                texto="Toca até você confirmar que tomou."
                value={prefs.alarmes}
                onChange={(v) => setPrefs((p) => ({ ...p, alarmes: v }))}
              />
              <PreferenceRow
                icon="watch"
                titulo="Alertas na pulseira ou relógio"
                texto="Vibra no pulso na hora de cada dose."
                value={prefs.pulseira}
                onChange={(v) => setPrefs((p) => ({ ...p, pulseira: v }))}
              />
            </Card>
            <Pressable
              accessibilityRole="checkbox"
              accessibilityState={{ checked: prefs.termos }}
              onPress={() => setPrefs((p) => ({ ...p, termos: !p.termos }))}
              className="flex-row items-start gap-3 rounded-xl bg-surface-container p-3.5">
              <Icon
                name={prefs.termos ? 'check_box' : 'check_box_outline_blank'}
                size={22}
                color={erros.termos && !prefs.termos ? 'error' : 'primary'}
              />
              <Txt v="body-sm" className="flex-1 text-on-surface">
                Li e aceito os <Txt v="body-sm" w="semibold" className="text-primary underline">Termos de Uso</Txt> e
                a <Txt v="body-sm" w="semibold" className="text-primary underline">Política de Privacidade</Txt>, e
                autorizo o uso dos meus dados de saúde conforme a LGPD.
              </Txt>
            </Pressable>
            {erros.termos && (
              <Txt v="body-sm" className="-mt-2 text-error">
                {erros.termos}
              </Txt>
            )}
          </>
        )}

        <Button
          label={passo < 2 ? 'Continuar' : 'Criar minha conta'}
          iconRight={passo < 2 ? 'arrow_forward' : undefined}
          icon={passo === 2 ? 'how_to_reg' : undefined}
          iconColor="tertiary-fixed"
          size="lg"
          className="mt-2"
          onPress={avancar}
        />
        {passo === 0 && (
          <Pressable accessibilityRole="link" className="items-center py-2" onPress={() => router.back()}>
            <Txt v="label-lg" className="text-on-surface-variant">
              Já tenho conta. <Txt v="label-lg" className="text-primary underline">Entrar</Txt>
            </Txt>
          </Pressable>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
