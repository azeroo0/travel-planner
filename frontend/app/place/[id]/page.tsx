import { notFound } from 'next/navigation';
import { getPlaceDetail, getPlaceProfile } from '@/lib/server-api';
import { ApiError } from '@/lib/api';
import PlaceDetail from '@/components/PlaceDetail';

export const dynamic = 'force-dynamic';

export default async function PlacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id) || !Number.isSafeInteger(Number(id))) notFound();
  try {
    const [place, profile] = await Promise.all([getPlaceDetail(Number(id)), getPlaceProfile(Number(id))]);
    return <PlaceDetail place={place} profile={profile} />;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <div className="compare"><h1>장소 정보를 불러오지 못했습니다.</h1><p role="alert">{(error as Error).message}</p></div>;
  }
}
