import { Linking, Platform } from 'react-native';

/** Abre o app de mapas do celular com o endereço buscado. */
export function abrirRota(endereco: string) {
  const q = encodeURIComponent(`${endereco}, Brasília - DF`);
  const web = `https://www.google.com/maps/search/?api=1&query=${q}`;
  const url = Platform.OS === 'ios' ? `maps://?q=${q}` : web;
  Linking.openURL(url).catch(() => Linking.openURL(web));
}
