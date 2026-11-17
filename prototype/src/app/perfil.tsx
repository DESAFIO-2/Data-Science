import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, Switch, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BackHeader } from '@/components/layout/app-header';
import { Icon } from '@/components/ui/icon';
import { Button, Card, LinearGradient, Pill } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { checkHealth, getDefaultApiBaseUrl, type HealthResponse } from '@/services/api';
import { REGIOES_DF, useApp } from '@/state/app-state';
import { shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';

function Linha({ icon, label, valor }: { icon: string; label: string; valor?: string }) {
  return (
    <View className="flex-row items-center gap-3 py-2.5">
      <Icon name={icon} size={20} color="on-surface-variant" />
      <View className="flex-1">
        <Txt v="label-sm" w="medium" className="text-on-surface-variant">
          {label}
        </Txt>
        <Txt v="body-md" className="text-primary">
          {valor || '—'}
        </Txt>
      </View>
    </View>
  );
}

function Preferencia({ icon, label, value, onChange }: { icon: string; label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View className="min-h-[44px] flex-row items-center gap-3 py-2">
      <Icon name={icon} size={20} />
      <Txt v="label-lg" className="flex-1 text-on-surface">
        {label}
      </Txt>
      <Switch
        value={value}
        onValueChange={onChange}
        accessibilityLabel={label}
        trackColor={{ false: colors['surface-container-highest'], true: colors.primary }}
        thumbColor={colors['surface-container-lowest']}
      />
    </View>
  );
}

export default function Perfil() {
  const insets = useSafeAreaInsets();
  const {
    usuario,
    sair,
    regiaoAdministrativa,
    setRegiaoAdministrativa,
    letrasMaiores,
    setLetrasMaiores,
    zeloRespondeVoz,
    setZeloRespondeVoz,
    apiBaseUrl,
    setApiBaseUrl,
    zeloSessionId,
    resetZeloSession,
    toast,
  } = useApp();
  const [alarmes, setAlarmes] = useState(true);
  const [pulseira, setPulseira] = useState(true);
  const [urlDraft, setUrlDraft] = useState(apiBaseUrl);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [testingApi, setTestingApi] = useState(false);

  async function handleTestApi(targetUrl?: string) {
    const clean = (targetUrl ?? urlDraft).trim().replace(/\/+$/, '');
    if (clean) {
      setApiBaseUrl(clean);
      setUrlDraft(clean);
    }
    setTestingApi(true);
    try {
      const h = await checkHealth(clean || apiBaseUrl);
      setHealth(h);
      toast(`API conectada! Voz: ${h.tts_voice ?? 'PT-BR'}`, 'verified');
    } catch (err) {
      setHealth(null);
      toast(err instanceof Error ? err.message : 'API Multiagentes offline.', 'error_outline');
    } finally {
      setTestingApi(false);
    }
  }

  return (
    <View className="flex-1 bg-canvas">
      <BackHeader title="Meu Perfil" />
      <ScrollView contentContainerClassName="gap-4 px-4 pt-4" contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}>
        <LinearGradient
          colors={[colors.primary, colors['primary-container'], colors.primary]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          className="flex-row items-center gap-4 overflow-hidden rounded-2xl p-5"
          style={shadow.xl}>
          <View className="h-16 w-16 items-center justify-center rounded-full bg-primary-fixed">
            <Txt v="headline-md" className="text-primary">
              {usuario?.nome.charAt(0)}
            </Txt>
          </View>
          <View className="flex-1">
            <Txt v="title-lg" className="text-on-primary">
              {usuario?.nomeCompleto}
            </Txt>
            <Txt v="body-sm" className="text-primary-fixed">
              CNS {usuario?.cns}
            </Txt>
            <View className="mt-1 flex-row items-center gap-1">
              <Icon name="location_on" size={14} color="secondary-fixed" />
              <Txt v="label-sm" className="text-surface-bright">
                {regiaoAdministrativa} • {usuario?.ubs}
              </Txt>
            </View>
          </View>
        </LinearGradient>

        <Card className="px-4 py-2">
          <Linha icon="badge" label="CPF" valor={usuario?.cpf} />
          <Linha icon="cake" label="Data de nascimento" valor={usuario?.nascimento} />
          <Linha icon="smartphone" label="Celular" valor={usuario?.celular} />
          <Linha icon="mail" label="E-mail" valor={usuario?.email} />
        </Card>

        {/* Região Administrativa DF para UBS/CEAF/Farmácia Popular */}
        <Card className="gap-2.5 p-4">
          <Txt v="label-md" upper className="text-on-surface-variant">
            Região Administrativa (DF)
          </Txt>
          <Txt v="body-sm" className="text-on-surface-variant">
            Usada pelos Multiagentes para indicar a UBS, Policlínica e farmácia CEAF mais próximas.
          </Txt>
          <View className="flex-row flex-wrap gap-1.5">
            {REGIOES_DF.slice(0, 8).map((ra) => {
              const ativo = regiaoAdministrativa === ra;
              return (
                <Pressable
                  key={ra}
                  onPress={() => {
                    setRegiaoAdministrativa(ra);
                    toast(`Região alterada para ${ra}`, 'location_on');
                  }}
                  className={`min-h-[36px] justify-center rounded-full px-3 py-1.5 ${
                    ativo ? 'bg-primary' : 'bg-surface-container'
                  }`}>
                  <Txt v="label-sm" className={ativo ? 'text-on-primary' : 'text-on-surface-variant'}>
                    {ra.replace(' - DF', '')}
                  </Txt>
                </Pressable>
              );
            })}
          </View>
        </Card>

        <Card className="px-4 py-2">
          <Txt v="label-md" upper className="pt-2 text-on-surface-variant">
            Acessibilidade & Voz
          </Txt>
          <Preferencia icon="volume_up" label="Alarme sonoro dos remédios" value={alarmes} onChange={setAlarmes} />
          <Preferencia icon="watch" label="Alertas na pulseira" value={pulseira} onChange={setPulseira} />
          <Preferencia icon="record_voice_over" label="Zelo responde por voz" value={zeloRespondeVoz} onChange={setZeloRespondeVoz} />
          <Preferencia
            icon="text_increase"
            label="Letras maiores (+16%)"
            value={letrasMaiores}
            onChange={(v) => {
              setLetrasMaiores(v);
              toast(v ? 'Letras maiores ativadas.' : 'Tamanho padrão restaurado.', 'text_increase');
            }}
          />
        </Card>

        {/* Conexão Backend Multiagentes RAG + Voz */}
        <Card className="gap-3 p-4">
          <View className="flex-row items-center justify-between">
            <Txt v="label-md" upper className="text-on-surface-variant">
              Motor Multiagentes RAG & Voz
            </Txt>
            <Pill label={health ? 'Online' : 'Verificar'} tone={health ? 'success' : 'neutral'} dot />
          </View>
          <View className="rounded-lg bg-surface-container-low px-3 py-2">
            <Txt v="label-sm" w="medium" className="text-on-surface-variant">
              URL da API FastAPI
            </Txt>
            <TextInput
              value={urlDraft}
              onChangeText={setUrlDraft}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder={getDefaultApiBaseUrl()}
              className="mt-1 font-sans text-body-md text-primary"
            />
          </View>
          <View className="flex-row gap-2">
            <Button
              label={testingApi ? 'Testando...' : 'Conectar & Testar API'}
              icon="sync"
              size="sm"
              className="flex-1"
              onPress={() => handleTestApi()}
            />
            <Button
              label="Nova Sessão Zelo"
              icon="refresh"
              size="sm"
              variant="surface"
              onPress={() => void resetZeloSession()}
            />
          </View>
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            Sessão LGPD: {zeloSessionId}
            {health?.tts_voice ? ` • Voz: ${health.tts_voice}` : ''}
          </Txt>
        </Card>

        <Pressable
          onPress={() => router.push('/alerta-pulseira')}
          className="min-h-[48px] flex-row items-center gap-3 rounded-xl bg-surface-container p-4 active:opacity-80">
          <Icon name="watch" size={22} />
          <Txt v="label-lg" className="flex-1 text-primary">
            Configurar pulseira ou relógio
          </Txt>
          <Icon name="chevron_right" size={22} color="on-surface-variant" />
        </Pressable>

        <Button label="Sair da conta" icon="logout" variant="white" iconColor="error" style={shadow.sm} onPress={sair} />
        <Txt v="label-sm" w="medium" className="text-center text-on-surface-variant">
          SUS Digital • v9 RAG Multiagentes + Voz
        </Txt>
      </ScrollView>
    </View>
  );
}
