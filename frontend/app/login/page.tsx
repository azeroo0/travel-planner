'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import AuthForm from '@/components/AuthForm';
import { getSession } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (getSession()) router.replace('/');
    else setReady(true);
  }, [router]);

  if (!ready) return null;
  return <div className="compare">
    <Link href="/">← 홈으로</Link>
    <h1>로그인</h1>
    <p className="muted">로그인하면 스크랩 같은 기능을 쓸 수 있어요.</p>
    <AuthForm onSuccess={() => router.replace('/')} />
  </div>;
}
