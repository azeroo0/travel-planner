'use client';

import { useLayoutEffect, useRef } from 'react';
import Image from 'next/image';
import AuthForm from './AuthForm';
import type { LoginResponse } from '@/lib/auth';

type Props = {
  /** true면 로고만 가운데에 보이는 스플래시 단계, false면 로고·제목·로그인 폼이 모두 보이는 최종 화면 */
  splash: boolean;
  onSuccess: (response: LoginResponse) => void;
  onGuest: () => void;
};

export default function Splash({ splash, onSuccess, onGuest }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const logo = useRef<HTMLDivElement>(null);

  // 최종 레이아웃에서 로고 중심이 화면 중심까지 얼마나 떨어져 있는지 재서, 스플래시의 로고 위치로 쓴다.
  useLayoutEffect(() => {
    if (!splash || !root.current || !logo.current) return;
    const box = root.current.getBoundingClientRect();
    const mark = logo.current.getBoundingClientRect();
    root.current.style.setProperty('--shift', `${box.top + box.height / 2 - (mark.top + mark.height / 2)}px`);
  }, [splash]);

  return (
    <div ref={root} className={`start intro${splash ? ' is-splash' : ''}`}>
      <div className="intro-body">
        <div ref={logo} className="intro-logo">
          <Image src="/logo.png" alt="어디갈건호? 로고" width={250} height={213} priority />
        </div>
        <div className="intro-text" aria-hidden={splash}>
          <h1>어디 갈지 고민될 땐,<br />리뷰한테 물어봐요</h1>
          <p>부산 리뷰를 읽고 조건에 맞는 곳을 찾아드려요</p>
        </div>
        <div className="intro-form" inert={splash}>
          <AuthForm onSuccess={onSuccess} onGuest={onGuest} />
        </div>
      </div>
    </div>
  );
}
