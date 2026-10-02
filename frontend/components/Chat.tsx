'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import ChatInput from './ChatInput';
import ScrapLink from './ScrapLink';
import { getRecommendations } from '@/lib/api';
import { parseConditions } from '@/lib/conditions';
import type { FitResult } from '@/lib/api-types';

type Message = { role: 'user' | 'bot'; text: string; results?: FitResult[]; labels?: string[]; shown?: number };
const GREETING: Message = { role: 'bot', text: '함께 갈 사람, 걷기 정도, 원하는 점과 피할 점을 알려주세요.' };
const categoryName = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };
// 장소 상세로 갔다가 뒤로 와도 대화가 남도록 탭 단위(sessionStorage)로 보관한다.
const STORAGE_KEY = 'chat-messages';
const PAGE_SIZE = 5; // 추천 결과를 처음에 보여 주는 개수이자 '더보기' 한 번에 늘어나는 개수

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [loading, setLoading] = useState(false);
  const [restored, setRestored] = useState(false);
  const q = useSearchParams().get('q');
  const router = useRouter();
  const sent = useRef(false);
  const thread = useRef<HTMLDivElement>(null);
  const focusNew = useRef(false);

  const send = async (text: string) => {
    focusNew.current = true;
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
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) setMessages(JSON.parse(saved));
    } catch { /* 저장소를 못 쓰면 새 대화로 시작 */ }
    setRestored(true);
  }, []);
  useEffect(() => {
    if (!restored) return;
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages)); } catch { /* 저장 실패는 무시 */ }
  }, [messages, restored]);
  useEffect(() => {
    // 새 요청을 보내면 그 질문이 화면 위쪽에 오도록 스크롤해 답변이 바로 아래에 보이게 한다.
    if (!focusNew.current) return;
    focusNew.current = false;
    const mine = thread.current?.querySelectorAll('.me');
    mine?.[mine.length - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [messages]);
  useEffect(() => {
    // 뒤로 가기로 돌아왔을 때 같은 질문을 다시 보내지 않도록 주소에서 q를 지운다.
    if (restored && q && !sent.current) { sent.current = true; router.replace('/chat'); void send(q); }
  }, [q, restored]);

  return (
    <>
      <header className="appbar">
        <Link href="/" className="brand" aria-label="메인 화면으로 이동">
          <Image src="/avatar.png" alt="" width={30} height={30} className="avatar" />
          <h1>어디갈건호?</h1>
        </Link>
        <ScrapLink />
        <button type="button" className="reset" onClick={() => setMessages([GREETING])} disabled={loading}>초기화</button>
      </header>
      <div className="thread" ref={thread}>
        {messages.map((m, i) => m.role === 'user' ? (
          <div key={i} className="me">{m.text}</div>
        ) : (
          <div key={i} className="bot-group">
            <div className="bot"><Image src="/avatar.png" alt="" width={34} height={34} className="avatar" /><p>{m.text}</p></div>
            {m.labels && <div className="conditions">{m.labels.map((label) => <span key={label}>{label}</span>)}</div>}
            {m.results && <div className="results">{m.results.slice(0, m.shown ?? PAGE_SIZE).map((result, rank) => (
              <Link key={result.place.place_id} href={`/place/${result.place.place_id}`} className="item">
                <span className="rank">{rank + 1}</span>
                <span><b>{result.place.name}</b><span className="meta">{categoryName[result.place.category]} · {result.place.region}</span></span>
                <span className="pct">{Math.round(result.fit)}<small>적합도</small></span>
                <span className="why">{result.reason}</span>
                {!!result.cautions.length && <span className="why">주의: {result.cautions.map((item) => item.aspect).join(', ')}</span>}
              </Link>
            ))}
            {m.results.length > (m.shown ?? PAGE_SIZE) && (
              <button type="button" className="more"
                onClick={() => setMessages((all) => all.map((x, j) => j === i ? { ...x, shown: (x.shown ?? PAGE_SIZE) + PAGE_SIZE } : x))}>
                더보기
              </button>
            )}</div>}
          </div>
        ))}
        {loading && <div className="bot"><p>장소를 찾고 있어요…</p></div>}
      </div>
      <ChatInput onSend={send} disabled={loading} />
    </>
  );
}
