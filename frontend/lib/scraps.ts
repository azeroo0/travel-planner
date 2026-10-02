import { apiRequest } from './api';

export type Scrap = {
  scrap_id: number;
  user_id: number;
  place_id: number | null;
  review_id: number | null;
  source_url: string | null;
  title: string | null;
  source_type: string;
  status: string;
  created_at: string;
};

const PAGE_SIZE = 100; // 서버 limit 상한

/** 내 스크랩 전체(최신순). 서버가 한 번에 100건까지만 주므로 끝날 때까지 이어서 읽는다. */
export async function listScraps(): Promise<Scrap[]> {
  const all: Scrap[] = [];
  for (let offset = 0; ; offset += PAGE_SIZE) {
    const page = await apiRequest<Scrap[]>(`/scraps?limit=${PAGE_SIZE}&offset=${offset}`, { auth: true });
    all.push(...page);
    if (page.length < PAGE_SIZE) return all;
  }
}

export function createScrap(placeId: number, title?: string): Promise<Scrap> {
  return apiRequest<Scrap>('/scraps', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ place_id: placeId, ...(title ? { title } : {}) }),
    auth: true,
  });
}

export function deleteScrap(scrapId: number): Promise<void> {
  return apiRequest<void>(`/scraps/${scrapId}`, { method: 'DELETE', auth: true });
}
