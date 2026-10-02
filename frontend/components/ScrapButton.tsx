'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { BookmarkIcon } from './ScrapLink';
import { ApiError } from '@/lib/api';
import { isLoggedIn, loginHref } from '@/lib/auth';
import { createScrap, deleteScrap, listScraps } from '@/lib/scraps';

type Check = 'checking' | 'ready' | 'failed';

/** 장소 상세 appbar의 스크랩 토글. 서버 응답을 받은 뒤에만 상태를 바꾼다(낙관적 업데이트 없음). */
export default function ScrapButton({ placeId, placeName }: { placeId: number; placeName?: string }) {
  const router = useRouter();
  // 같은 장소가 중복 저장돼 있을 수 있어 id를 모두 들고 있다가 해제할 때 함께 지운다.
  const [scrapIds, setScrapIds] = useState<number[]>([]);
  const [check, setCheck] = useState<Check>('checking');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const scraped = scrapIds.length > 0;

  useEffect(() => {
    if (!isLoggedIn()) { setCheck('ready'); return; }
    let active = true;
    listScraps()
      .then((items) => {
        if (!active) return;
        setScrapIds(items.filter((scrap) => scrap.place_id === placeId).map((scrap) => scrap.scrap_id));
        setCheck('ready');
      })
      .catch((err) => {
        if (!active || (err instanceof ApiError && err.status === 401)) return; // 401은 로그인 화면으로 이동 중
        setCheck('failed');
        setError('스크랩 상태를 불러오지 못했어요');
      });
    return () => { active = false; };
  }, [placeId]);

  const toggle = async () => {
    if (!isLoggedIn()) { router.push(loginHref(location.pathname + location.search)); return; }
    setPending(true);
    setError('');
    try {
      if (scraped) {
        const results = await Promise.allSettled(scrapIds.map(deleteScrap));
        const left = scrapIds.filter((_, i) => results[i].status === 'rejected');
        setScrapIds(left);
        if (left.length) throw new Error('delete');
      } else {
        const scrap = await createScrap(placeId, placeName || undefined);
        setScrapIds([scrap.scrap_id]);
      }
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setError(scraped ? '스크랩을 해제하지 못했어요' : '스크랩하지 못했어요');
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="scrap-toggle">
      <button type="button" className="scrap-btn" aria-pressed={scraped} onClick={toggle} disabled={pending || check !== 'ready'}>
        <BookmarkIcon filled={scraped} />
        {scraped ? '스크랩됨' : '스크랩'}
      </button>
      {error && <p className="scrap-error" role="alert">{error}</p>}
    </div>
  );
}
