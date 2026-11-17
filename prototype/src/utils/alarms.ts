import * as Notifications from 'expo-notifications';
import { AndroidImportance, AndroidNotificationVisibility } from 'expo-notifications';
import { Platform } from 'react-native';

/**
 * Alarmes de dose via notificações locais.
 *
 * Pulseiras e relógios pareados (Mi Band, Galaxy Fit/Watch, Amazfit, Apple Watch,
 * Wear OS...) espelham automaticamente as notificações do celular. Por isso o
 * "alerta mini" da pulseira é a própria notificação: título curto, texto curto,
 * vibração forte e dois botões de ação (Tomei / Adiar).
 */

export const CATEGORIA_DOSE = 'dose';
export const ACAO_TOMEI = 'tomei';
export const ACAO_ADIAR = 'adiar';
const CANAL_ANDROID = 'alarmes-remedios';

let configurado = false;
let canalPronto = false;

export async function configurarAlarmes() {
  if (configurado || Platform.OS === 'web') return;
  configurado = true;

  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });

  if (Platform.OS === 'android') {
    try {
      // Sem "sound": no Android ele espera um arquivo de som do app; omitido = som padrão.
      await Notifications.setNotificationChannelAsync(CANAL_ANDROID, {
        name: 'Alarmes de remédios',
        importance: AndroidImportance.MAX,
        vibrationPattern: [0, 600, 250, 600, 250, 600],
        lockscreenVisibility: AndroidNotificationVisibility.PUBLIC,
      });
      canalPronto = true;
    } catch (e) {
      console.warn('[alarmes] não foi possível criar o canal; usando o canal padrão.', e);
    }
  }

  try {
    // Botões que aparecem na notificação — e na tela da pulseira/relógio.
    await Notifications.setNotificationCategoryAsync(CATEGORIA_DOSE, [
      { identifier: ACAO_TOMEI, buttonTitle: '✓ Tomei', options: { opensAppToForeground: false } },
      { identifier: ACAO_ADIAR, buttonTitle: 'Adiar 15 min', options: { opensAppToForeground: false } },
    ]);
  } catch (e) {
    console.warn('[alarmes] não foi possível registrar os botões da notificação.', e);
  }
}

async function temPermissao() {
  const atual = await Notifications.getPermissionsAsync();
  if (atual.granted) return true;
  const pedido = await Notifications.requestPermissionsAsync();
  return pedido.granted;
}

export type DoseAlerta = { id?: string; nome: string; dose: string; horario: string };

/** Agenda o alerta de dose para daqui a `segundos` (usado no "Testar alarme"). */
export async function dispararAlertaDose(dose: DoseAlerta, segundos = 5): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  try {
    await configurarAlarmes();
    if (!(await temPermissao())) return false;
    await agendar(dose, segundos);
    return true;
  } catch (e) {
    console.warn('[alarmes] falha ao agendar o alerta.', e);
    return false;
  }
}

async function agendar(dose: DoseAlerta, segundos: number) {
  await Notifications.scheduleNotificationAsync({
    content: {
      // Texto curto de propósito: telas de pulseira mostram ~2 linhas.
      title: `💊 ${dose.nome} ${dose.dose}`,
      body: `Hora do remédio • ${dose.horario}`,
      categoryIdentifier: CATEGORIA_DOSE,
      sound: 'default',
      priority: Notifications.AndroidNotificationPriority.MAX,
      data: { medId: dose.id ?? dose.nome.toLowerCase(), nome: `${dose.nome} ${dose.dose}` },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
      seconds: segundos,
      ...(canalPronto ? { channelId: CANAL_ANDROID } : {}),
    },
  });
}
