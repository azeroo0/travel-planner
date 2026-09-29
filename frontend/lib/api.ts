import type { AnalysisResult, AnalyzeRequest, EvidenceReview, ExperimentMetricRow, FitResult, Place, Page, RecommendationQuery } from './api-types';

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, { cache: 'no-store', ...init });
  } catch {
    throw new ApiError('API 서버에 연결할 수 없습니다. 서버 주소와 실행 상태를 확인해 주세요.', 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(
      typeof error?.message === 'string' ? error.message : 'API 요청에 실패했습니다. 서버 실행 상태를 확인해 주세요.',
      response.status,
      error?.code,
    );
  }
  if (body === null) throw new ApiError('API 응답이 JSON이 아닙니다.', response.status);
  return body as T;
}

export function getRecommendations(query: RecommendationQuery): Promise<FitResult[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  return apiRequest<FitResult[]>(`/recommendations?${params}`);
}

export function getEvidence(placeId: number, aspect: string, sentiment?: string): Promise<EvidenceReview[]> {
  const params = new URLSearchParams({ aspect });
  if (sentiment) params.set('sentiment', sentiment);
  return apiRequest<EvidenceReview[]>(`/places/${placeId}/evidence?${params}`);
}

export function analyzeReview(request: AnalyzeRequest): Promise<AnalysisResult> {
  return apiRequest<AnalysisResult>('/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
}

export function getExperiments(): Promise<ExperimentMetricRow[]> {
  return apiRequest<ExperimentMetricRow[]>('/experiments');
}

export function getPlaces(query: Record<string, string>): Promise<Page<Place>> {
  return apiRequest<Page<Place>>(`/places?${new URLSearchParams(query)}`);
}
