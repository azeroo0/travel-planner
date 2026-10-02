'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ApiError, apiRequest } from '@/lib/api';
import type { Place } from '@/lib/api-types';
import { isLoggedIn, loginHref } from '@/lib/auth';
import { deleteScrap, listScraps, type Scrap } from '@/lib/scraps';

const categoryName: Record<string, string> = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };

// 서버가 시간대 없는 값을 주면 UTC로 본다.
function formatDate(value: string): string {
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('ko-KR');
}

type Item = { scrap: Scrap; place: Place | null };

export default function MyScrapsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Item[] | null>(null);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState<number | null>(null);
  const [rowError, setRowError] = useState<{ id: number; message: string } | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace(loginHref('/scraps')); return; }
    let active = true;
    (async () => {
      const scraps = (await listScraps()).filter((scrap) => scrap.place_id !== null);
      const ids = [...new Set(scraps.map((scrap) => scrap.place_id as number))];
      // 장소마다 한 번씩만, 동시에 요청한다. 실패한 장소는 이름 없이 둔다.
      const places = new Map(await Promise.all(ids.map(async (id) => {
        const place = await apiRequest<Place>(`/places/${id}`).catch(() => null);
        return [id, place] as const;
      })));
      if (active) setItems(scraps.map((scrap) => ({ scrap, place: places.get(scrap.place_id as number) ?? null })));
    })().catch((err) => {
      if (!active || (err instanceof ApiError && err.status === 401)) return; // 401은 로그인 화면으로 이동 중
      setError('스크랩 목록을 불러오지 못했어요');
    });
    return () => { active = false; };
  }, [router]);

  const remove = async (scrapId: number) => {
    setDeleting(scrapId);
    setRowError(null);
    try {
      await deleteScrap(scrapId);
      setItems((current) => current && current.filter((item) => item.scrap.scrap_id !== scrapId));
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setRowError({ id: scrapId, message: '삭제하지 못했어요' });
    } finally {
      setDeleting(null);
    }
  };

  return (
    <>
      <header className="appbar center">
        <Link href="/" aria-label="홈으로">←</Link>
        <h1>내 스크랩</h1>
        <span />
      </header>
      <div className="scrap-page">
        {error ? <p className="scrap-load-error" role="alert">{error}</p>
          : items === null ? <p className="muted">불러오는 중…</p>
          : items.length === 0 ? (
            <div className="scrap-empty">
              <p>아직 스크랩한 장소가 없어요</p>
              <Link href="/chat">장소 찾으러 가기</Link>
            </div>
          ) : (
            <div className="results">
              {items.map(({ scrap, place }) => {
                const placeId = scrap.place_id as number;
                const meta = [place ? categoryName[place.category] : null, formatDate(scrap.created_at)].filter(Boolean).join(' · ');
                return (
                  <div key={scrap.scrap_id} className="scrap-row">
                    <Link href={`/place/${placeId}`}>
                      <b>{place?.name || `장소 #${placeId}`}</b>
                      <span className="meta">{meta}</span>
                    </Link>
                    <button type="button" onClick={() => remove(scrap.scrap_id)} disabled={deleting === scrap.scrap_id} aria-label="스크랩 삭제">삭제</button>
                    {rowError?.id === scrap.scrap_id && <p className="scrap-error" role="alert">{rowError.message}</p>}
                  </div>
                );
              })}
            </div>
          )}
      </div>
    </>
  );
}
