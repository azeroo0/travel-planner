'use client';

import { useId, useState } from 'react';
import { ApiError } from '@/lib/api';
import { login, saveSession, signup, type LoginResponse } from '@/lib/auth';

type Props = { onSuccess: (response: LoginResponse) => void; onGuest?: () => void };

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return '이메일 또는 비밀번호가 올바르지 않아요';
    if (error.status === 409) return '이미 가입된 이메일이에요';
    return error.message;
  }
  return '알 수 없는 오류가 발생했어요. 잠시 후 다시 시도해 주세요.';
}

export default function AuthForm({ onSuccess, onGuest }: Props) {
  const id = useId();
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const isSignup = mode === 'signup';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pending) return;
    setPending(true);
    setError('');
    const mail = email.trim();
    try {
      if (isSignup) await signup(mail, password, name.trim() || undefined);
      const response = await login(mail, password);
      saveSession(response);
      onSuccess(response);
    } catch (err) {
      setError(messageFor(err));
      setPending(false);
    }
  };

  const toggle = () => {
    setMode(isSignup ? 'login' : 'signup');
    setError('');
  };

  return (
    <div className="auth">
      <form onSubmit={submit} noValidate={false}>
        {isSignup && (
          <div className="auth-field">
            <label htmlFor={`${id}-name`}>이름 (선택)</label>
            <input id={`${id}-name`} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={100} />
          </div>
        )}
        <div className="auth-field">
          <label htmlFor={`${id}-email`}>이메일</label>
          <input id={`${id}-email`} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" maxLength={255} required />
        </div>
        <div className="auth-field">
          <label htmlFor={`${id}-password`}>비밀번호</label>
          <input
            id={`${id}-password`} type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete={isSignup ? 'new-password' : 'current-password'} minLength={isSignup ? 8 : undefined} maxLength={128} required
            aria-describedby={isSignup ? `${id}-hint` : undefined}
          />
          {isSignup && <small id={`${id}-hint`}>8자 이상 입력해 주세요</small>}
        </div>
        <p className="auth-error" role="alert">{error}</p>
        <button type="submit" className="auth-submit" disabled={pending}>
          {pending ? '잠시만요…' : isSignup ? '회원가입' : '로그인'}
        </button>
      </form>
      <p className="auth-switch">
        {isSignup ? '이미 계정이 있으신가요?' : '계정이 없으신가요?'}{' '}
        <button type="button" onClick={toggle} disabled={pending}>{isSignup ? '로그인' : '회원가입'}</button>
      </p>
      {onGuest && <button type="button" className="auth-guest" onClick={onGuest} disabled={pending}>로그인 없이 둘러보기</button>}
    </div>
  );
}
