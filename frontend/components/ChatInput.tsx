'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

type Props = { onSend?: (text: string) => void; disabled?: boolean; placeholder?: string };

export default function ChatInput({ onSend, disabled, placeholder = '어디 갈지 물어보세요' }: Props) {
  const [text, setText] = useState('');
  const router = useRouter();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = text.trim();
    if (!q || disabled) return;
    setText('');
    if (onSend) onSend(q);
    else router.push(`/chat?q=${encodeURIComponent(q)}`);
  };

  return (
    <form className="composer" onSubmit={submit}>
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} aria-label="메시지" />
      <button type="submit" disabled={disabled || !text.trim()} aria-label="보내기">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M6 11l6-6 6 6" /></svg>
      </button>
    </form>
  );
}
