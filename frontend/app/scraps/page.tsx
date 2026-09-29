import Link from 'next/link';
import { listDbPlaces } from '@/lib/place-db';

export const dynamic = 'force-dynamic';
const categoryName: Record<string, string> = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };

export default async function PlacesPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const raw = (await searchParams).page;
  const parsed = Number(raw ?? '1');
  const page = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
  let data: Awaited<ReturnType<typeof listDbPlaces>>;
  try { data = await listDbPlaces(page); }
  catch { return <div className="compare"><Link href="/">← 홈으로</Link><h1>장소 목록</h1><p role="alert">DB 장소 목록을 불러오지 못했습니다. DB 연결 설정과 서버 실행 상태를 확인해 주세요.</p></div>; }
  const pages = Math.max(1, Math.ceil(data.total / 20));

  return <div className="compare">
    <Link href="/">← 홈으로</Link>
    <h1>DB 장소 목록</h1>
    <p className="muted">전체 {data.total}곳 · 스크랩 저장 기능은 추후 연결합니다.</p>
    <p className="muted">현재 DB에 장소명이 없어 이름 대신 장소 ID와 원본 ID를 표시합니다.</p>
    {data.items.length ? <div className="scrap-list">{data.items.map((place) => (
      <article key={place.place_id} className="scrap-card">
        <b>{place.place_name || `장소 #${place.place_id}`}</b>
        <small>{categoryName[place.category_code] ?? place.category_code} · 리뷰 {place.review_count}건</small>
        <small>원본 ID: {place.source_place_id}</small>
      </article>
    ))}</div> : <p>표시할 장소가 없습니다.</p>}
    <div className="scrap-pagination">
      {page > 1 ? <Link href={`/scraps?page=${page - 1}`}>이전</Link> : <span />}
      <span>{page} / {pages}</span>
      {page < pages ? <Link href={`/scraps?page=${page + 1}`}>다음</Link> : <span />}
    </div>
  </div>;
}
