'use client';

import { useEffect, useLayoutEffect, useState } from 'react';
import Splash from './Splash';
import StartHome from './StartHome';
import { clearGuest, getSession, hasSeenSplash, isGuest, logout, markSplashSeen, startGuest } from '@/lib/auth';

// boot: 저장소를 읽기 전(빈 화면) → 로그인/게스트 여부가 어긋난 화면이 잠깐 보이는 일을 막는다.
type Phase = 'boot' | 'splash' | 'auth' | 'home';

const useIsoLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;
const SPLASH_MS = 1200;

export default function HomeEntry() {
  const [phase, setPhase] = useState<Phase>('boot');
  const [guest, setGuest] = useState(false);

  useIsoLayoutEffect(() => {
    if (getSession()) { setPhase('home'); return; }
    if (isGuest()) { setGuest(true); setPhase('home'); return; }
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || hasSeenSplash()) { setPhase('auth'); return; }
    markSplashSeen();
    setPhase('splash');
  }, []);

  useEffect(() => {
    if (phase !== 'splash') return;
    const timer = setTimeout(() => setPhase('auth'), SPLASH_MS);
    return () => clearTimeout(timer);
  }, [phase]);

  if (phase === 'boot') return null;
  if (phase === 'home') {
    return (
      <StartHome
        guest={guest}
        onLogin={() => { clearGuest(); setGuest(false); setPhase('auth'); }}
        onLogout={() => { logout(); setPhase('auth'); }}
      />
    );
  }
  return (
    <Splash
      splash={phase === 'splash'}
      onSuccess={() => { setGuest(false); setPhase('home'); }}
      onGuest={() => { startGuest(); setGuest(true); setPhase('home'); }}
    />
  );
}
