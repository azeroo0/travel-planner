import 'server-only';
import { ApiError } from './api';
import type { ExperimentMetricRow, PlaceDetail, PlaceProfile } from './api-types';

export async function serverRequest<T>(path: string): Promise<T> {
  const backend = process.env.API_SERVER_URL?.replace(/\/$/, '');
  if (!backend) throw new ApiError('API_SERVER_URL이 설정되지 않았습니다.', 0);
  let response: Response;
  try {
    response = await fetch(`${backend}/api/v1${path}`, { cache: 'no-store' });
  } catch {
    throw new ApiError('API 서버에 연결할 수 없습니다.', 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(body?.error?.message ?? 'API 요청에 실패했습니다.', response.status, body?.error?.code);
  if (body === null) throw new ApiError('API 응답이 JSON이 아닙니다.', response.status);
  return body as T;
}

export const getPlaceDetail = (id: number) => serverRequest<PlaceDetail>(`/places/${id}`);

// These endpoints are reserved in the backend contract but are not implemented yet.
export const getPlaceProfile = (id: number) => serverRequest<PlaceProfile>(`/places/${id}/profile`);
export const getExperimentMetrics = () => serverRequest<ExperimentMetricRow[]>('/experiments');
