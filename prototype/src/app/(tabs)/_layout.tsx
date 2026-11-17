import { Tabs } from 'expo-router/js-tabs';

import { FloatingTabBar } from '@/components/layout/tab-bar';

export default function TabsLayout() {
  return (
    <Tabs
      tabBar={(props) => <FloatingTabBar {...props} />}
      screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: '#f8fafc' } }}>
      <Tabs.Screen name="inicio" />
      <Tabs.Screen name="farmacias" />
      <Tabs.Screen name="remedios" />
      <Tabs.Screen name="receitas" />
      <Tabs.Screen name="zelo" />
    </Tabs>
  );
}
