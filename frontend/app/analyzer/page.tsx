'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { analyzeReview } from '@/lib/api';
import type { AnalysisResult, Category, Model } from '@/lib/api-types';

export default function AnalyzerPage() {
  const [review, setReview] = useState('');
  const [category, setCategory] = useState<Category>('attraction');
  const [model, setModel] = useState<Model>('base');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setResult(null); setError(''); setLoading(true);
    try { setResult(await analyzeReview({ review: review.trim(), category, model })); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  };
  return <div className="compare">
    <Link href="/chat">← 추천으로</Link>
    <h1>리뷰 분석</h1>
    <form onSubmit={submit} className="analyzer-form">
      <label>장소 종류 <select value={category} onChange={(e) => setCategory(e.target.value as Category)}>
        <option value="hotel">숙소</option><option value="restaurant">식당</option><option value="attraction">관광지</option>
      </select></label>
      <label>모델 <select value={model} onChange={(e) => setModel(e.target.value as Model)}>
        <option value="base">Base</option><option value="lora">LoRA</option><option value="qlora">QLoRA</option>
      </select></label>
      <label>리뷰 <textarea value={review} maxLength={2000} onChange={(e) => setReview(e.target.value)} rows={7} /></label>
      <button disabled={loading || !review.trim()}>{loading ? '분석 중…' : '분석하기'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {result && <section><h2>분석 결과</h2>
      <p>동행 유형: {result.traveler_context.join(', ') || '없음'}</p>
      {result.aspects.length ? result.aspects.map((aspect, i) => <div className="review" key={i}>
        <b>{aspect.category}</b> · {aspect.attribute} · {aspect.sentiment}<p>근거: {aspect.evidence}</p>
      </div>) : <p>추출된 항목이 없습니다.</p>}
    </section>}
  </div>;
}
