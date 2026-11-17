import '../global.css';

import {
  Newsreader_400Regular,
  Newsreader_500Medium,
  Newsreader_600SemiBold,
} from '@expo-google-fonts/newsreader';
import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_500Medium,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
} from '@expo-google-fonts/plus-jakarta-sans';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { Platform, View } from 'react-native';

import { AppStateProvider, useApp } from '@/state/app-state';
import { ACAO_ADIAR, ACAO_TOMEI, configurarAlarmes } from '@/utils/alarms';
import { shadow } from '@/theme/shadows';

SplashScreen.preventAutoHideAsync();

let webGuardInstalled = false;

/** Evita que extensões/Google Translate quebrem a árvore DOM do React (NotFoundError removeChild). */
function installWebTranslationAndDomGuard() {
  if (webGuardInstalled || Platform.OS !== 'web' || typeof document === 'undefined' || typeof Node === 'undefined') {
    return;
  }
  webGuardInstalled = true;

  const html = document.documentElement;
  if (html) {
    html.lang = 'pt-BR';
    html.setAttribute('translate', 'no');
    html.classList.add('notranslate');
  }
  if (document.body) {
    document.body.setAttribute('translate', 'no');
    document.body.classList.add('notranslate');
  }
  if (!document.querySelector('meta[name="google"][content="notranslate"]')) {
    const meta = document.createElement('meta');
    meta.name = 'google';
    meta.content = 'notranslate';
    document.head?.appendChild(meta);
  }

  const origRemoveChild = Node.prototype.removeChild;
  Node.prototype.removeChild = function guardedRemoveChild<T extends Node>(this: Node, child: T): T {
    if (child.parentNode !== this) {
      if (child.parentNode) {
        return origRemoveChild.call(child.parentNode, child) as T;
      }
      return child;
    }
    return origRemoveChild.call(this, child) as T;
  };

  const origInsertBefore = Node.prototype.insertBefore;
  Node.prototype.insertBefore = function guardedInsertBefore<T extends Node>(
    this: Node,
    newNode: T,
    referenceNode: Node | null,
  ): T {
    if (referenceNode && referenceNode.parentNode !== this) {
      return this.appendChild(newNode);
    }
    return origInsertBefore.call(this, newNode, referenceNode) as T;
  };
}

installWebTranslationAndDomGuard();

function RootNavigator() {
  const { usuario, registrarDose, adiarDose } = useApp();
  const logado = usuario !== null;

  // Respostas tocadas na notificação (no celular ou na pulseira/relógio).
  useEffect(() => {
    if (Platform.OS === 'web') return;
    configurarAlarmes();
    const sub = Notifications.addNotificationResponseReceivedListener((resp) => {
      const { medId, nome } = (resp.notification.request.content.data ?? {}) as { medId?: string; nome?: string };
      if (!medId) return;
      if (resp.actionIdentifier === ACAO_TOMEI) registrarDose(medId, nome);
      if (resp.actionIdentifier === ACAO_ADIAR) adiarDose(medId);
    });
    return () => sub.remove();
  }, [registrarDose, adiarDose]);

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#f8fafc' } }}>
      <Stack.Protected guard={!logado}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
      <Stack.Protected guard={logado}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="notificacoes" />
        <Stack.Screen name="perfil" />
        <Stack.Screen name="alerta-pulseira" options={{ presentation: 'modal' }} />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({
    Newsreader_400Regular,
    Newsreader_500Medium,
    Newsreader_600SemiBold,
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
  });

  useEffect(() => {
    if (fontsLoaded || fontError) SplashScreen.hideAsync();
  }, [fontsLoaded, fontError]);

  if (!fontsLoaded && !fontError) return null;

  const content = (
    <AppStateProvider>
      <StatusBar style="dark" />
      <RootNavigator />
    </AppStateProvider>
  );

  if (Platform.OS === 'web') {
    return (
      <View className="flex-1 items-center bg-surface-container-high">
        <View
          className="w-full flex-1 overflow-hidden bg-canvas"
          style={[{ maxWidth: 448 }, shadow.xl]}>
          {content}
        </View>
      </View>
    );
  }

  return content;
}
