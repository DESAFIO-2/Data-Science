import { router } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Platform, Pressable, ScrollView, TextInput, View } from 'react-native';

import { Screen } from '@/components/layout/screen';
import { Icon } from '@/components/ui/icon';
import { Button, Image, LinearGradient, Pill, PulseDot } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { farmacias as farmaciasMock } from '@/data/mock';
import {
  fetchCeafStock,
  fetchNearbyPharmacies,
  type CeafStockItemDTO,
  type NearbyPharmacyDTO,
} from '@/services/api';
import { REGIOES_DF, useApp } from '@/state/app-state';
import { accentBorder, shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';
import { abrirRota } from '@/utils/maps';

const MAPA_URL =
  'https://lh3.googleusercontent.com/aida/AEtjO1ULJJwzv2tpPZQ0TOKrsIwn1oa_dpomJ6wFKuu9HSALzRn5-1DrQhj322P3oDs1WQ8U3G_12st2T5OQ_ahIdvbMjuFaMTv3pC6PHTjzE7gE264rz40cM_w1pgx51T2YrpCOV-dlIWLY_bvFLi35uAX9n-dyiJC60QxiY_UCgi8UuJmeXTNvZZK_McndGVKYOR-vHsFMrnqogEabcT3gJyC-DyImXbDnsMqA6euNml_i';

const LOCAIS = [
  { id: 'ra', label: 'Minha RA', icon: 'home' },
  { id: 'gps', label: 'Usar GPS', icon: 'my_location' },
  { id: 'ceaf', label: 'Alto Custo CEAF', icon: 'apartment' },
];

const DOCUMENTOS = [
  { icon: 'assignment_turned_in', titulo: 'Receita médica válida (SUS ou particular)', texto: 'Até 180 dias na Farmácia Popular • LME para Alto Custo (90d)' },
  { icon: 'badge', titulo: 'Documento com foto e CPF (RG, CNH)', texto: 'Físico ou digital oficial' },
  { icon: 'credit_card', titulo: 'Cartão Nacional de Saúde (CNS)', texto: 'Disponível também no app SUS Digital' },
];

function UnidadeCard({
  item,
  destaque,
  onPerguntarZelo,
}: {
  item: NearbyPharmacyDTO;
  destaque?: boolean;
  onPerguntarZelo: () => void;
}) {
  const isAltoCusto = item.pharmacy_type.toLowerCase().includes('alto custo') || item.pharmacy_type.toLowerCase().includes('ceaf');
  return (
    <View
      className="gap-3 overflow-hidden rounded-xl bg-surface-container-lowest p-4"
      style={[destaque ? shadow.lg : shadow.sm, accentBorder(destaque ? 0.3 : 0.22)]}>
      <View className="flex-row items-start justify-between gap-2">
        <View className="flex-1 gap-1">
          <View className="flex-row flex-wrap items-center gap-1.5">
            <Txt v="title-md" w="bold" className="text-primary">
              {item.name}
            </Txt>
            <Pill label={isAltoCusto ? 'CEAF / Alto Custo' : item.pharmacy_type || 'Unidade SUS'} tone={isAltoCusto ? 'info' : 'success'} />
          </View>
          <Txt v="body-sm" className="text-on-surface-variant">
            {item.address} • {item.neighborhood_or_ra}
          </Txt>
        </View>
        {item.distance_km !== undefined && (
          <View className="items-end">
            <Txt v="title-md" className="text-primary">
              {item.distance_km.toFixed(1)} km
            </Txt>
            <Txt v="label-sm" w="medium" className="text-secondary">
              GPS
            </Txt>
          </View>
        )}
      </View>

      <View className="flex-row items-center gap-2 rounded-lg bg-surface-container-low px-2.5 py-2">
        <Icon name="local_hospital" size={17} color="secondary" />
        <Txt v="label-sm" w="medium" className="flex-1 text-on-surface" numberOfLines={2}>
          CNES {item.cnes} • Cobre: {item.covered_ras?.slice(0, 3).join(', ') || item.neighborhood_or_ra}
        </Txt>
      </View>

      <View className="flex-row gap-2">
        <Button
          label="Como Chegar"
          icon="directions"
          className="flex-1"
          onPress={() => {
            if (item.google_maps_url) {
              void Linking.openURL(item.google_maps_url);
            } else {
              abrirRota(`${item.name}, ${item.address}, Distrito Federal`);
            }
          }}
        />
        <Button
          label="Falar c/ Zelo"
          icon="spa"
          variant="surface"
          className="flex-1"
          onPress={onPerguntarZelo}
        />
      </View>
    </View>
  );
}

export default function Farmacias() {
  const { regiaoAdministrativa, setRegiaoAdministrativa, apiBaseUrl, setZeloDraftPrompt, toast } = useApp();

  const [busca, setBusca] = useState('Adalimumabe');
  const [local, setLocal] = useState('ra');
  const [coords, setCoords] = useState<{ lat: number; lng: number } | undefined>(undefined);
  const [unidades, setUnidades] = useState<NearbyPharmacyDTO[]>([]);
  const [estoques, setEstoques] = useState<CeafStockItemDTO[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [usandoFallback, setUsandoFallback] = useState(false);

  const carregarDados = useCallback(
    async (queryText: string, mode: string, gpsCoords?: { lat: number; lng: number }) => {
      setCarregando(true);
      try {
        const raQuery = regiaoAdministrativa.replace(' - DF', '');
        const [phRes, stRes] = await Promise.all([
          fetchNearbyPharmacies(
            {
              ra: raQuery,
              q: mode === 'ceaf' ? 'CEAF Alto Custo' : undefined,
              lat: mode === 'gps' ? gpsCoords?.lat : undefined,
              lng: mode === 'gps' ? gpsCoords?.lng : undefined,
              limite: 6,
            },
            apiBaseUrl,
          ),
          fetchCeafStock(
            {
              q: queryText.trim() || undefined,
              limite: 8,
            },
            apiBaseUrl,
          ),
        ]);
        setUnidades(phRes.items);
        setEstoques(stRes.items);
        setUpdatedAt(stRes.updated_at ?? null);
        setUsandoFallback(false);
      } catch {
        setUsandoFallback(true);
        setUnidades([]);
        setEstoques([]);
      } finally {
        setCarregando(false);
      }
    },
    [apiBaseUrl, regiaoAdministrativa],
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      void carregarDados(busca, local, coords);
    }, 240);
    return () => clearTimeout(timer);
  }, [busca, carregarDados, coords, local]);

  function ativarGps() {
    setLocal('gps');
    if (Platform.OS === 'web' && typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
          toast('Localização GPS atualizada para ordenar farmácias por distância.', 'my_location');
        },
        () => {
          toast('GPS não autorizado; filtrando por Região Administrativa.', 'location_on');
        },
      );
    }
  }

  return (
    <Screen>
      {/* Status InfoSaúde DF */}
      <View className="flex-row items-center justify-between rounded-xl bg-surface-container-high/80 p-3" style={shadow.sm}>
        <View className="flex-1 flex-row items-center gap-2.5">
          <View className="h-7 w-7 items-center justify-center rounded-lg bg-primary-container">
            <Icon name="verified_user" size={18} color="primary-fixed" />
          </View>
          <View className="flex-1">
            <Txt v="label-sm" className="text-primary" numberOfLines={1}>
              InfoSaúde-DF & Farmácia Popular
            </Txt>
            <View className="flex-row items-center gap-1">
              <PulseDot />
              <Txt v="label-sm" w="medium" className="text-secondary">
                {usandoFallback ? 'Modo offline (exemplos locais)' : '231 unidades + estoque CEAF ao vivo'}
              </Txt>
            </View>
          </View>
        </View>
        <View className="rounded-full bg-surface-container-lowest px-2 py-0.5">
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            {updatedAt ? updatedAt.slice(0, 10) : 'SES-DF'}
          </Txt>
        </View>
      </View>

      {/* Busca no estoque & unidades + voz */}
      <View className="gap-2.5">
        <View className="h-14 flex-row items-center rounded-xl bg-surface-container-lowest pl-3.5 pr-2" style={shadow.sm}>
          <Icon name="search" size={20} color="on-tertiary-container" />
          <TextInput
            accessibilityLabel="Consultar estoque CEAF ou medicamento"
            value={busca}
            onChangeText={setBusca}
            placeholder="Consultar estoque CEAF (ex.: Adalimumabe, Insulina)"
            placeholderTextColor={colors['on-surface-variant']}
            className="h-full flex-1 px-2.5 font-sans text-body-md text-primary"
          />
          {carregando ? (
            <ActivityIndicator size="small" color={colors.primary} />
          ) : (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Perguntar estoque por voz para a Zelo"
              onPress={() => {
                setZeloDraftPrompt(
                  `Moro em ${regiaoAdministrativa}. Onde posso retirar ${busca.trim() || 'losartana'} e como está o atendimento?`,
                );
                router.navigate('/zelo');
              }}
              className="h-10 w-10 items-center justify-center rounded-lg bg-surface-container active:opacity-70">
              <Icon name="mic" size={20} color="primary" />
            </Pressable>
          )}
        </View>

        <View className="flex-row gap-1 rounded-xl bg-surface-container-low p-1">
          {LOCAIS.map((l) => {
            const ativo = l.id === local;
            return (
              <Pressable
                key={l.id}
                accessibilityRole="tab"
                accessibilityState={{ selected: ativo }}
                onPress={() => (l.id === 'gps' ? ativarGps() : setLocal(l.id))}
                className={`min-h-[38px] flex-1 flex-row items-center justify-center gap-1.5 rounded-lg px-2 py-2 ${
                  ativo ? 'bg-surface-container-lowest' : ''
                }`}
                style={ativo ? shadow.sm : undefined}>
                <Icon name={l.icon} size={16} color={ativo ? 'secondary' : 'on-surface-variant'} />
                <Txt v="label-sm" className={ativo ? 'text-primary' : 'text-on-surface-variant'} numberOfLines={1}>
                  {l.label}
                </Txt>
              </Pressable>
            );
          })}
        </View>

        {/* Seletor rápido de Região Administrativa DF */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-1.5 py-0.5">
          {REGIOES_DF.slice(0, 7).map((ra) => {
            const ativo = regiaoAdministrativa === ra;
            return (
              <Pressable
                key={ra}
                onPress={() => setRegiaoAdministrativa(ra)}
                className={`rounded-full px-3 py-1.5 ${ativo ? 'bg-primary' : 'bg-surface-container-high'}`}>
                <Txt v="label-sm" className={ativo ? 'text-on-primary' : 'text-on-surface-variant'}>
                  {ra.replace(' - DF', '')}
                </Txt>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {/* Banner Mapa */}
      <View className="h-40 overflow-hidden rounded-xl bg-surface-container" style={[shadow.md, accentBorder(0.3)]}>
        <Image
          source={{ uri: MAPA_URL }}
          contentFit="cover"
          accessibilityLabel={`Mapa do Distrito Federal — ${regiaoAdministrativa}`}
          className="absolute inset-0"
        />
        <LinearGradient
          colors={['transparent', 'rgba(0, 37, 77, 0.2)', 'rgba(0, 37, 77, 0.85)']}
          className="absolute inset-0"
        />
        <View className="absolute inset-x-3 bottom-3 flex-row items-center justify-between gap-2 rounded-lg bg-surface-container-lowest/95 p-2.5">
          <View className="flex-1 flex-row items-center gap-2">
            <PulseDot size={10} />
            <Txt v="label-sm" w="medium" className="flex-1 text-primary" numberOfLines={1}>
              {regiaoAdministrativa} • Rede SUS-DF
            </Txt>
          </View>
          <Pressable onPress={() => abrirRota(`Farmácia Popular ou UBS em ${regiaoAdministrativa}`)}>
            <Txt v="label-sm" w="bold" className="text-secondary underline">
              Abrir Mapa
            </Txt>
          </Pressable>
        </View>
      </View>

      {/* Estoque CEAF ao Vivo (857 itens InfoSaúde) */}
      {estoques.length > 0 && (
        <View className="gap-2.5">
          <View className="flex-row items-center justify-between">
            <Txt v="title-lg" className="text-primary">
              Estoque Alto Custo (CEAF-DF)
            </Txt>
            <Pill label={`${estoques.length} registro(s)`} tone="info" />
          </View>
          <View className="gap-2">
            {estoques.map((st, idx) => {
              const qtd = Number(st.disp_estoque ?? 0);
              const disponivel = Number.isFinite(qtd) ? qtd > 0 : Boolean(st.disp_estoque);
              return (
                <View
                  key={`${st.cod_produto ?? idx}-${st.unidade ?? idx}`}
                  className="flex-row items-center justify-between gap-2 rounded-xl bg-surface-container-lowest p-3"
                  style={shadow.sm}>
                  <View className="flex-1">
                    <Txt v="label-lg" className="text-primary" numberOfLines={2}>
                      {st.desc_produto || st.medicamento || 'Item CEAF'}
                    </Txt>
                    <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                      Unidade: {st.unidade ?? 'SES-DF'}
                    </Txt>
                  </View>
                  <Pill
                    label={disponivel ? `Disp.: ${st.disp_estoque}` : 'Sem estoque'}
                    tone={disponivel ? 'success' : 'warning'}
                  />
                </View>
              );
            })}
          </View>
        </View>
      )}

      {/* Lista de Farmácias & UBSs geolocalizadas */}
      <View className="flex-row items-center justify-between">
        <View className="flex-1">
          <Txt v="headline-sm" className="text-primary">
            Farmácias & UBSs da Região
          </Txt>
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            {unidades.length > 0 ? `${unidades.length} pontos próximos em ${regiaoAdministrativa}` : 'Farmácia Popular & SUS gratuito'}
          </Txt>
        </View>
        <Pill label="100% SUS" tone="success" upper />
      </View>

      <View className="gap-3.5">
        {unidades.length > 0
          ? unidades.map((item, i) => (
              <UnidadeCard
                key={item.cnes}
                item={item}
                destaque={i === 0}
                onPerguntarZelo={() => {
                  setZeloDraftPrompt(
                    `Qual o horário, documentos necessários e como funciona a retirada na unidade ${item.name} (${item.address})?`,
                  );
                  router.navigate('/zelo');
                }}
              />
            ))
          : farmaciasMock.map((f, i) => (
              <UnidadeCard
                key={f.id}
                destaque={i === 0}
                onPerguntarZelo={() => {
                  setZeloDraftPrompt(
                    `Qual o documento necessário para retirar medicamento gratuito na farmácia ${f.nome} (${f.endereco})?`,
                  );
                  router.navigate('/zelo');
                }}
                item={{
                  cnes: f.id.toUpperCase(),
                  name: f.nome,
                  address: f.endereco,
                  neighborhood_or_ra: regiaoAdministrativa,
                  pharmacy_type: f.selo,
                  latitude: null,
                  longitude: null,
                  covered_ras: [regiaoAdministrativa],
                }}
              />
            ))}
      </View>

      {/* O que levar */}
      <View className="gap-3 rounded-xl bg-surface-container-high p-4" style={[shadow.sm, accentBorder(0.3)]}>
        <View className="flex-row items-center gap-2">
          <View className="h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Icon name="badge" size={18} color="primary-fixed" />
          </View>
          <View className="flex-1">
            <Txt v="title-md" w="bold" className="text-primary">
              O que levar para retirar de graça
            </Txt>
            <Txt v="label-sm" w="medium" className="text-on-surface-variant">
              Documentos obrigatórios na farmácia
            </Txt>
          </View>
        </View>
        {DOCUMENTOS.map((d) => (
          <View key={d.titulo} className="flex-row items-center gap-2.5 rounded-lg bg-surface-container-lowest p-2.5">
            <Icon name={d.icon} size={20} color="secondary" />
            <View className="flex-1">
              <Txt v="label-lg" className="text-primary">
                {d.titulo}
              </Txt>
              <Txt v="body-sm" className="text-on-surface-variant">
                {d.texto}
              </Txt>
            </View>
          </View>
        ))}
      </View>

      {/* Disque Saúde */}
      <View
        className="flex-row items-center justify-between rounded-xl bg-primary p-4"
        style={[shadow.lg, { borderWidth: 1, borderColor: 'rgba(167, 200, 255, 0.35)' }]}>
        <View className="flex-1 flex-row items-center gap-3">
          <View className="h-10 w-10 items-center justify-center rounded-full bg-primary-container">
            <Icon name="support_agent" size={22} color="secondary-fixed" />
          </View>
          <View className="flex-1">
            <Txt v="title-md" w="bold" className="text-on-primary">
              Disque Saúde 136
            </Txt>
            <Txt v="body-sm" className="text-primary-fixed">
              Canal oficial SUS • 24h
            </Txt>
          </View>
        </View>
        <Button label="Ligar" icon="call" variant="success" size="sm" onPress={() => Linking.openURL('tel:136')} />
      </View>
    </Screen>
  );
}
