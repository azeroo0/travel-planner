'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import ChatInput from './ChatInput';
import { getRecommendations } from '@/lib/api';
import { parseConditions } from '@/lib/conditions';
import type { FitResult } from '@/lib/api-types';

type Message = { role: 'user' | 'bot'; text: string; results?: FitResult[]; labels?: string[] };
const GREETING: Message = { role: 'bot', text: '함께 갈 사람, 걷기 정도, 원하는 점과 피할 점을 알려주세요.' };
const categoryName = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [loading, setLoading] = useState(false);
  const q = useSearchParams().get('q');
  const sent = useRef(false);
  const bottom = useRef<HTMLDivElement>(null);

  const send = async (text: string) => {
    setMessages((m) => [...m, { role: 'user', text }]);
    const { query, labels } = parseConditions(text);
    if (!labels.length) {
      setMessages((m) => [...m, { role: 'bot', text: '지원하는 조건을 찾지 못했습니다. 예: 부모님과 가고, 걷기는 적게, 바다는 보고 싶고 계단은 피하고 싶어요.' }]);
      return;
    }
    setLoading(true);
    try {
      const results = await getRecommendations(query);
      setMessages((m) => [...m, {
        role: 'bot',
        text: results.length ? '조건에 맞는 장소입니다. 리뷰 근거를 보려면 장소를 눌러주세요.' : '이 조건에 맞는 장소가 없습니다.',
        results,
        labels,
      }]);
    } catch (e) {
      setMessages((m) => [...m, { role: 'bot', text: (e as Error).message }]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (q && !sent.current) { sent.current = true; void send(q); }
  }, [q]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  return (
    <>
      <header className="appbar">
        <Link href="/"><Image src="/avatar.png" alt="" width={30} height={30} className="avatar" /></Link>
        <h1>어디갈건호?</h1>
        <Link href="/analyzer">리뷰 분석</Link>
      </header>
      <div className="thread">
        {messages.map((m, i) => m.role === 'user' ? (
          <div key={i} className="me">{m.text}</div>
        ) : (
          <div key={i} className="bot-group">
            <div className="bot"><Image src="/avatar.png" alt="" width={34} height={34} className="avatar" /><p>{m.text}</p></div>
            {m.labels && <div className="conditions">{m.labels.map((label) => <span key={label}>{label}</span>)}</div>}
            {m.results && <div className="results">{m.results.map((result, rank) => (
              <Link key={result.place.place_id} href={`/place/${result.place.place_id}`} className="item">
                <span className="rank">{rank + 1}</span>
                <span><b>{result.place.name}</b><span className="meta">{categoryName[result.place.category]} · {result.place.region}</span></span>
                <span className="pct">{Math.round(result.fit)}<small>적합도</small></span>
                <span className="why">{result.reason}</span>
                {!!result.cautions.length && <span className="why">주의: {result.cautions.map((item) => item.aspect).join(', ')}</span>}
              </Link>
            ))}</div>}
          </div>
        ))}
        {loading && <div className="bot"><p>장소를 찾고 있어요…</p></div>}
        <div ref={bottom} />
      </div>
      <ChatInput onSend={send} disabled={loading} />
    </>
  );
}
