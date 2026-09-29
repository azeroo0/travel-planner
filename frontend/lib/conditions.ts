import type { RecommendationQuery } from './api-types';

export function parseConditions(text: string): { query: RecommendationQuery; labels: string[] } {
  const query: RecommendationQuery = {};
  const labels: string[] = [];
  const match = (pattern: RegExp, value: string, label: string, key: keyof RecommendationQuery) => {
    if (pattern.test(text)) { (query as Record<string, string>)[key] = value; labels.push(label); }
  };
  match(/부모님|부모|어르신/, 'parents', '부모님과', 'with');
  if (!query.with) match(/아이|애기|자녀/, 'kids', '아이와', 'with');
  if (!query.with) match(/연인|커플/, 'couple', '연인과', 'with');
  if (!query.with) match(/친구/, 'friends', '친구와', 'with');
  if (!query.with) match(/혼자|홀로/, 'solo', '혼자', 'with');
  match(/걷\S*\s*(적게|싫|힘들)|적게\s*걷|걷기\s*힘들|도보\s*적게/, 'low', '걷기 적게', 'walk');
  if (!query.walk) match(/걷기\s*보통|적당히\s*걷/, 'moderate', '걷기 보통', 'walk');
  const priorities: [RegExp, string, string][] = [
    [/바다|바닷/, 'sea', '바다'], [/맛집|음식|먹거리/, 'food', '음식'], [/사진|포토/, 'photo', '사진'],
    [/문화|역사/, 'culture', '문화'], [/휴식|쉬고|힐링/, 'rest', '휴식'], [/조용|한적/, 'quiet', '조용한 곳'],
  ];
  const avoids: [RegExp, string, string][] = [
    [/대기|웨이팅|줄\s*서/, 'waiting', '대기 피하기'], [/계단/, 'stairs', '계단 피하기'],
    [/시끄|소음/, 'noise', '소음 피하기'], [/주차/, 'parking', '주차 불편 피하기'], [/붐비|혼잡|인파/, 'crowd', '혼잡 피하기'],
  ];
  const pri = priorities.filter(([pattern]) => pattern.test(text));
  if (pri.length) { query.pri = pri.map(([, value]) => value).join(','); labels.push(...pri.map(([, , label]) => label)); }
  const avoid = avoids.filter(([pattern]) => pattern.test(text));
  if (avoid.length) { query.avoid = avoid.map(([, value]) => value).join(','); labels.push(...avoid.map(([, , label]) => label)); }
  match(/식당|음식점|맛집/, 'restaurant', '식당', 'category');
  if (!query.category) match(/호텔|숙소|숙박/, 'hotel', '숙소', 'category');
  if (!query.category) match(/관광지|명소/, 'attraction', '관광지', 'category');
  return { query, labels };
}
