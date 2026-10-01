'use client';

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
  return (
    <div className={`start intro${splash ? ' is-splash' : ''}`}>
      <div className="intro-logo">
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
  );
}
