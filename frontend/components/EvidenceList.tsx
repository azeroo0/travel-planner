'use client';

import { useState } from 'react';
import { getEvidence } from '@/lib/api';
import type { EvidenceReview, PlaceProfile } from '@/lib/api-types';

export default function EvidenceList({ placeId, aspects }: { placeId: number; aspects: PlaceProfile['aspects'] }) {
  const [reviews, setReviews] = useState<EvidenceReview[]>([]);
  const [active, setActive] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const load = async (aspect: string, sentiment: string) => {
    const key = `${aspect}:${sentiment}`;
    setActive(key);
    setError('');
    setLoading(true);
    try { setReviews(await getEvidence(placeId, aspect, sentiment)); }
    catch (e) { setReviews([]); setError((e as Error).message); }
    finally { setLoading(false); }
  };
  return (
    <>
      <div className="seg">
        {aspects.map((item) => (
          <button key={`${item.aspect}:${item.polarity}`} aria-pressed={active === `${item.aspect}:${item.polarity}`}
            onClick={() => void load(item.aspect, item.polarity)}>{item.aspect} · {item.polarity}</button>
        ))}
      </div>
      {!aspects.length && <p className="muted">조회할 분석 항목이 없습니다.</p>}
      {loading && <p>리뷰를 불러오는 중…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && active && !error && !reviews.length && <p className="muted">근거 리뷰가 없습니다.</p>}
      {groupByReview(reviews).map(({ review, spans }) => (
        <div key={review.review_id} className="review">
          <div className="who"><span className="ctx">{review.context}</span><span>{review.sentiment}</span></div>
          <p>{highlight(review.text, spans)}</p>
        </div>
      ))}
    </>
  );
}

// 한 리뷰에 같은 aspect·감정 라벨이 여러 개면 API는 라벨마다 한 행을 준다. 리뷰 하나당 카드 하나로 묶는다.
function groupByReview(rows: EvidenceReview[]) {
  const groups = new Map<number, { review: EvidenceReview; spans: [number, number][] }>();
  for (const row of rows) {
    const group = groups.get(row.review_id) ?? { review: row, spans: [] };
    const start = Math.max(0, Math.min(row.text.length, row.evidence_start));
    group.spans.push([start, Math.max(start, Math.min(row.text.length, row.evidence_end))]);
    groups.set(row.review_id, group);
  }
  return [...groups.values()];
}

// 겹치거나 맞닿은 구간은 합쳐서 <mark>가 중첩되지 않게 한다.
function highlight(text: string, spans: [number, number][]) {
  const merged: [number, number][] = [];
  for (const [start, end] of [...spans].sort((a, b) => a[0] - b[0])) {
    const last = merged[merged.length - 1];
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  const parts = [];
  let pos = 0;
  for (const [start, end] of merged) {
    parts.push(text.slice(pos, start), <mark key={start}>{text.slice(start, end)}</mark>);
    pos = end;
  }
  parts.push(text.slice(pos));
  return parts;
}
