import Image from 'next/image';
import Link from 'next/link';
import ChatInput from '@/components/ChatInput';

const examples = [
  { q: '부모님과 가고, 걷기는 적게, 바다는 보고 싶고 계단은 피하고 싶어요', sub: '부모님 · 바다 · 계단 피하기' },
  { q: '친구랑 조용한 식당에 가고 싶어요', sub: '친구 · 식당 · 조용한 곳' },
  { q: '아이와 갈 관광지, 사진 찍기 좋은 곳', sub: '아이 · 관광지 · 사진' },
];

export default function Home() {
  return (
    <>
      <div className="start">
        <Link href="/login" className="home-login">로그인</Link>
        <Image src="/logo.png" alt="어디갈건호? 로고" width={250} height={213} priority />
        <h1>어디 갈지 고민될 땐,<br />리뷰한테 물어봐요</h1>
        <p>부산 리뷰를 읽고 조건에 맞는 곳을 찾아드려요</p>
        <div className="examples">
          {examples.map((e) => <Link key={e.q} href={`/chat?q=${encodeURIComponent(e.q)}`}>{e.q}<small>{e.sub}</small></Link>)}
        </div>
        <p><Link href="/scraps">장소 스크랩</Link></p>
      </div>
      <ChatInput />
    </>
  );
}
