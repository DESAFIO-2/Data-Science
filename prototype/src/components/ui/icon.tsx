import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import MaterialIcons from '@expo/vector-icons/MaterialIcons';

import { colors } from '@/theme/tokens';

export type ColorToken = keyof typeof colors;

/**
 * Os HTMLs usam Material Symbols. A maioria existe no MaterialIcons do Expo
 * (com "-" no lugar de "_"); os que não existem são mapeados aqui.
 */
const COMMUNITY: Record<string, string> = {
  calendar_add_on: 'calendar-plus',
  pace: 'clock-fast',
  prescriptions: 'clipboard-text',
  shield_person: 'shield-account',
  pill: 'pill',
  e911_emergency: 'alarm-light',
  cardiology: 'heart-pulse',
  shield_with_heart: 'shield-plus',
  ambulance: 'ambulance',
  qr_code: 'qrcode',
  stethoscope: 'stethoscope',
  water_drop: 'water',
};

const MATERIAL_ALIAS: Record<string, string> = {
  event_upcoming: 'event',
  sync_saved_loc: 'autorenew',
};

type Props = {
  name: string;
  size?: number;
  /** Nome de um token de cor (ex.: "primary") ou um valor CSS. */
  color?: ColorToken | (string & {});
};

export function Icon({ name, size = 20, color = 'primary' }: Props) {
  const resolved = (colors as Record<string, string>)[color] ?? color;
  const community = COMMUNITY[name];
  if (community) {
    return <MaterialCommunityIcons name={community as never} size={size} color={resolved} />;
  }
  const material = (MATERIAL_ALIAS[name] ?? name).replace(/_/g, '-');
  return <MaterialIcons name={material as never} size={size} color={resolved} />;
}
