'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import AuthForm from '@/components/AuthForm';
import { getSession, safeNext } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [next, setNext] = useState('/');
  const [needLogin, setNeedLogin] = useState(false);

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get('next');
    const target = safeNext(raw);
    if (getSession()) { router.replace(target); return; }
    setNext(target);
    setNeedLogin(raw !== null);
    setReady(true);
  }, [router]);

  if (!ready) return null;
  return <div className="compare login-page">
    <Link href="/">← 홈으로</Link>
    <div className="login-body">
      <h1>로그인</h1>
      {needLogin && <p className="login-notice" role="status">로그인이 필요해요</p>}
      <p className="muted">로그인하면 스크랩 같은 기능을 쓸 수 있어요.</p>
      <AuthForm onSuccess={() => router.replace(next)} />
    </div>
  </div>;
}
