'use client';

// [임시] 튜닝 전 원본 모델과 튜닝 모델의 추천 결과 비교 화면. chat 화면과 같은 UI를 쓴다.
import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import ChatInput from './ChatInput';
import { apiRequest } from '@/lib/api';
import { parseConditions } from '@/lib/conditions';
import type { RecommendationQuery } from '@/lib/api-types';

type Evidence = { aspect: string; label: string; review_id: number; sentiment: string; text: string };
type Item = {
  place: { place_id: number; name: string; category: 'hotel' | 'restaurant' | 'attraction'; region: string };
  fit: number;
  reason: string;
  evidence: Evidence[];
};
type Condition = {
  key: string;
  name: string;
  detail: string;
  ready: boolean;
  stats: { reviews: number; parse_ok: number; labels: number; rejected: number } | null;
  items: Item[];
};
type Message = { role: 'user' | 'bot'; text: string; labels?: string[]; conditions?: Condition[] };

const GREETING: Message = { role: 'bot', text: '같은 조건으로 원본 모델과 튜닝 모델의 라벨에서 나온 추천을 비교해요. 조건을 입력해 주세요.' };
const categoryName = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };
const sentimentName: Record<string, string> = { positive: '긍정', negative: '부정', neutral: '중립' };

function compare(query: RecommendationQuery): Promise<Condition[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  return apiRequest<Condition[]>(`/model-compare/recommendations?${params}`);
}

function Results({ conditions }: { conditions: Condition[] }) {
  const [active, setActive] = useState(conditions[conditions.length - 1].key);
  const current = conditions.find((c) => c.key === active)!;
  return (
    <>
      <div className="seg">
        {conditions.map((c) => (
          <button key={c.key} type="button" aria-pressed={c.key === active} onClick={() => setActive(c.key)}>
            {c.name} {c.ready ? `(${c.items.length})` : ''}
          </button>
        ))}
      </div>
      <p className="muted compare-stats">
        {current.detail}
        {current.stats && <><br />형식 통과 {current.stats.parse_ok}/{current.stats.reviews}건 · 유효 라벨 {current.stats.labels}개 · 버린 라벨 {current.stats.rejected}개</>}
      </p>
      {!current.ready && <p className="muted">이 조건의 라벨 파일이 아직 없습니다.</p>}
      {current.ready && !current.items.length && <p className="muted">이 조건에 맞는 장소가 없습니다.</p>}
      {!!current.items.length && <div className="results">{current.items.map((item, rank) => (
        <Link key={item.place.place_id} href={`/place/${item.place.place_id}`} className="item">
          <span className="rank">{rank + 1}</span>
          <span><b>{item.place.name}</b><span className="meta">{categoryName[item.place.category]} · {item.place.region}</span></span>
          <span className="pct">{Math.round(item.fit)}<small>적합도</small></span>
          <span className="why">{item.reason}</span>
          {item.evidence.slice(0, 3).map((e, i) => (
            <span key={i} className="why">근거 · {e.label} {sentimentName[e.sentiment]}: “{e.text}”</span>
          ))}
        </Link>
      ))}</div>}
    </>
  );
}

export default function ModelCompare() {
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [loading, setLoading] = useState(false);

  const send = async (text: string) => {
    setMessages((m) => [...m, { role: 'user', text }]);
    const { query, labels } = parseConditions(text);
    if (!labels.length) {
      setMessages((m) => [...m, { role: 'bot', text: '지원하는 조건을 찾지 못했습니다. 예: 아이와 가기 좋은 곳' }]);
      return;
    }
    setLoading(true);
    try {
      const conditions = await compare(query);
      setMessages((m) => [...m, { role: 'bot', text: '모델별 추천입니다. 위 버튼으로 모델을 바꿔 보세요.', labels, conditions }]);
    } catch (e) {
      setMessages((m) => [...m, { role: 'bot', text: (e as Error).message }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <header className="appbar">
        <Link href="/" className="brand" aria-label="메인 화면으로 이동">
          <Image src="/avatar.png" alt="" width={30} height={30} className="avatar" />
          <h1>모델별 추천 비교</h1>
        </Link>
        <button type="button" className="reset" onClick={() => setMessages([GREETING])} disabled={loading}>초기화</button>
      </header>
      <div className="thread">
        {messages.map((m, i) => m.role === 'user' ? (
          <div key={i} className="me">{m.text}</div>
        ) : (
          <div key={i} className="bot-group">
            <div className="bot"><Image src="/avatar.png" alt="" width={34} height={34} className="avatar" /><p>{m.text}</p></div>
            {m.labels && <div className="conditions">{m.labels.map((label) => <span key={label}>{label}</span>)}</div>}
            {m.conditions && <Results conditions={m.conditions} />}
          </div>
        ))}
        {loading && <div className="bot"><p>모델별 추천을 계산하고 있어요…</p></div>}
      </div>
      <ChatInput onSend={send} disabled={loading} placeholder="예: 아이와 가기 좋은 곳" />
    </>
  );
}
