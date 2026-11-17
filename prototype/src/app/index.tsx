import { Redirect } from 'expo-router';

import { useApp } from '@/state/app-state';

export default function Index() {
  const { usuario } = useApp();
  return <Redirect href={usuario ? '/inicio' : '/login'} />;
}
