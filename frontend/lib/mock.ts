import type { Place, RecommendResponse } from './types';

export const places: Place[] = [
  {
    id: 'cheongsapo-sotbap',
    name: '청사포 솥밥집',
    category: '한식 · 솥밥',
    price: '1인 13,000원대',
    distance: '해운대역 도보 12분',
    hours: '영업 중 · 21:00 마감',
    pos: 38,
    neg: 4,
    reason: '조용하다는 리뷰 38개 · 부모님과 방문 22개',
    summary: '조용하고 반찬이 정갈해서 부모님과 가기 좋다는 평이 많아요. 주말 점심엔 대기가 있어요.',
    aspects: [
      { name: '조용함', pos: 38, neg: 4 },
      { name: '가격', pos: 29, neg: 6 },
      { name: '부모님 동반', pos: 21, neg: 1 },
    ],
    good: [
      { text: '조용해서 대화하기 좋아요', count: 38 },
      { text: '가격이 합리적이에요', count: 29 },
      { text: '부모님이 좋아하세요', count: 21 },
    ],
    bad: [
      { text: '주말 점심엔 대기가 있어요', count: 17 },
      { text: '주차 공간이 좁아요', count: 6 },
    ],
    contexts: [
      { label: '가족', ratio: 46 },
      { label: '친구', ratio: 24 },
      { label: '연인', ratio: 18 },
      { label: '혼자', ratio: 12 },
    ],
    reviews: [
      { author: '김**', context: '부모님과', date: '2026.09', text: '창가 자리가 넓고 조용해서 어머니가 편하게 드셨어요.', highlight: '조용해서' },
      { author: '이**', context: '친구와', date: '2026.08', text: '이 가격에 반찬까지 정갈하게 나오는 곳 드물어요.', highlight: '반찬까지 정갈하게' },
      { author: '박**', context: '가족과', date: '2026.08', text: '맛은 좋은데 주말 점심엔 30분 정도 기다렸어요.', highlight: '30분 정도 기다렸어요', negative: true },
    ],
    info: [
      { label: '주소', value: '부산 해운대구 중동 달맞이길 00' },
      { label: '영업', value: '매일 11:00–21:00' },
      { label: '주차', value: '가게 앞 3대' },
    ],
    map: { x: 0.62, y: 0.42 },
  },
  {
    id: 'mipo-grill',
    name: '미포 생선구이',
    category: '한식 · 생선구이',
    price: '1인 15,000원대',
    distance: '해운대역 도보 9분',
    hours: '영업 중 · 22:00 마감',
    pos: 25,
    neg: 7,
    reason: '생선 굽기 칭찬 27개 · 부모님과 방문 15개',
    summary: '생선을 잘 굽는다는 평이 많아요. 저녁엔 단체 손님으로 붐빈다는 의견이 있어요.',
    aspects: [
      { name: '조용함', pos: 9, neg: 7 },
      { name: '가격', pos: 19, neg: 6 },
      { name: '부모님 동반', pos: 15, neg: 2 },
    ],
    good: [
      { text: '생선을 잘 구워요', count: 27 },
      { text: '가격이 합리적이에요', count: 19 },
    ],
    bad: [{ text: '저녁엔 시끄러워요', count: 7 }],
    contexts: [
      { label: '가족', ratio: 38 },
      { label: '회사', ratio: 28 },
      { label: '친구', ratio: 22 },
      { label: '혼자', ratio: 12 },
    ],
    reviews: [
      { author: '최**', context: '부모님과', date: '2026.09', text: '아버지가 생선 굽기가 딱 좋다고 하셨어요.', highlight: '생선 굽기가 딱 좋다고' },
      { author: '정**', context: '회사 동료와', date: '2026.07', text: '저녁엔 단체 손님이 많아 조금 시끄러웠어요.', highlight: '단체 손님이 많아', negative: true },
    ],
    info: [
      { label: '주소', value: '부산 해운대구 중동 미포길 00' },
      { label: '영업', value: '매일 11:30–22:00' },
      { label: '주차', value: '불가 · 인근 공영주차장' },
    ],
    map: { x: 0.48, y: 0.55 },
  },
];

export const getPlace = (id: string) => places.find((p) => p.id === id);

export const mockRecommend = (): RecommendResponse => ({
  reply: '이 조건으로 리뷰 1,284개를 살펴봤어요.',
  conditions: ['해운대 근처', '조용함', '1인 2만 원 이하', '부모님 동반'],
  reviewCount: 1284,
  places,
});
