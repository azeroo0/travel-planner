import Link from 'next/link';
import EvidenceList from './EvidenceList';
import type { PlaceDetail as Place, PlaceProfile } from '@/lib/api-types';

const categoryName = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };

export default function PlaceDetail({ place, profile }: { place: Place; profile: PlaceProfile }) {
  return (
    <>
      <header className="appbar center">
        <Link href="/chat" aria-label="뒤로">←</Link>
        <h1>{place.name}</h1>
        <span />
      </header>
      <div className="detail">
        <section className="hd">
          <span className="muted">{categoryName[place.category]} · {place.district}</span>
          <h2>{place.name}</h2>
          {place.address && <p className="summary">{place.address}</p>}
          {place.summary && <p className="summary">{place.summary}</p>}
        </section>
        <section>
          <h3>리뷰 분석 <small>{place.review_count}건</small></h3>
          {profile.aspects.length ? profile.aspects.map((aspect) => (
            <div key={`${aspect.aspect}-${aspect.polarity}`} className="aspect">
              <span>{aspect.aspect}</span>
              <div className="bar"><i style={{ width: `${Math.max(0, Math.min(100, aspect.share))}%` }} /></div>
              <span className="muted">{aspect.polarity === 'positive' ? '긍정' : aspect.polarity === 'negative' ? '부정' : '중립'} {aspect.share}% · {aspect.mentions}건</span>
            </div>
          )) : <p className="muted">분석된 리뷰가 없습니다.</p>}
        </section>
        <section>
          <h3>동행 유형</h3>
          {profile.contexts.length ? profile.contexts.map((context) => (
            <div key={context.context} className="kw"><span>{context.context}</span><b>{context.ratio}%</b></div>
          )) : <p className="muted">동행 유형 정보가 없습니다.</p>}
        </section>
        <section>
          <h3>근거 리뷰</h3>
          <EvidenceList placeId={place.place_id} aspects={profile.aspects} />
        </section>
        <section>
          <h3>기본 정보</h3>
          <dl className="info">
            <dt>주소</dt><dd>{place.address || '주소 정보 없음'}</dd>
            <dt>지역</dt><dd>{place.region}</dd>
          </dl>
          {!!place.tags.length && <p className="summary">태그: {place.tags.map((tag) => tag.tag_name).join(', ')}</p>}
        </section>
      </div>
    </>
  );
}
