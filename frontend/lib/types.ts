export type Aspect = { name: string; pos: number; neg: number };
export type Keyword = { text: string; count: number };
export type VisitContext = { label: string; ratio: number };

export type Review = {
  author: string;
  context: string;
  date: string;
  text: string;
  highlight: string;
  negative?: boolean;
};

export type Place = {
  id: string;
  name: string;
  category: string;
  price: string;
  distance: string;
  hours: string;
  pos: number;
  neg: number;
  reason: string;
  summary: string;
  aspects: Aspect[];
  good: Keyword[];
  bad: Keyword[];
  contexts: VisitContext[];
  reviews: Review[];
  info: { label: string; value: string }[];
  map: { x: number; y: number };
};

export type RecommendResponse = {
  reply: string;
  conditions: string[];
  reviewCount: number;
  places: Place[];
};

export type Message =
  | { role: 'user'; text: string }
  | { role: 'bot'; text: string; result?: RecommendResponse };
