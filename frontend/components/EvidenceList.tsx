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
      {reviews.map((review) => {
        const start = Math.max(0, Math.min(review.text.length, review.evidence_start));
        const end = Math.max(start, Math.min(review.text.length, review.evidence_end));
        return <div key={review.review_id} className="review">
          <div className="who"><span className="ctx">{review.context}</span><span>{review.sentiment}</span></div>
          <p>{review.text.slice(0, start)}<mark>{review.text.slice(start, end)}</mark>{review.text.slice(end)}</p>
        </div>;
      })}
    </>
  );
}
