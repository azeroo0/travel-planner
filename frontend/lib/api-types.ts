export type Category = 'hotel' | 'restaurant' | 'attraction';
export type Model = 'base' | 'lora' | 'qlora';
export type Region = 'haeundae' | 'gwangan' | 'seomyeon' | 'wondo' | 'west';
export type Sentiment = 'positive' | 'negative' | 'neutral';

export type Place = {
  place_id: number;
  name: string;
  category: Category;
  region: Region;
  district: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  summary: string;
  main_image_url: string | null;
  review_count: number;
};
export type PlaceDetail = Place & {
  images: { image_url: string; is_main: boolean; sort_order: number }[];
  tags: { category: string; tag_name: string }[];
};
export type PlaceProfile = {
  place_id: number;
  aspects: { aspect: string; polarity: Sentiment; share: number; mentions: number }[];
  contexts: { context: string; ratio: number }[];
  context_satisfaction: Record<string, number>;
};
export type EvidenceReview = {
  review_id: number;
  text: string;
  context: string;
  sentiment: Sentiment;
  evidence_start: number;
  evidence_end: number;
};
export type FitResult = {
  place: Pick<Place, 'place_id' | 'name' | 'category' | 'region'>;
  fit: number;
  reason: string;
  strengths: FitFactor[];
  cautions: FitFactor[];
};
export type FitFactor = { aspect: string; polarity: Sentiment; share: number; weight: number; delta: number };
export type RecommendationQuery = {
  with?: 'solo' | 'friends' | 'couple' | 'parents' | 'kids';
  walk?: 'ok' | 'moderate' | 'low';
  pri?: string;
  avoid?: string;
  category?: Category;
  limit?: number;
};
export type AnalyzeRequest = { review: string; category: Category; model: Model };
export type AnalysisResult = {
  traveler_context: string[];
  aspects: { category: string; attribute: string; sentiment: Sentiment; evidence: string }[];
};
export type ExperimentMetricRow = {
  metric: string;
  unit: string;
  scores: Record<'base' | 'lora_gold' | 'qlora_gold' | 'lora_gs' | 'qlora_gs', number | null>;
};
export type Page<T> = { items: T[]; page: number; size: number; total: number };
