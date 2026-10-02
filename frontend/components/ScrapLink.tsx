'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { isLoggedIn, loginHref } from '@/lib/auth';

export function BookmarkIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 3h12v18l-6-4-6 4z" />
    </svg>
  );
}

/** appbar의 "내 스크랩" 아이콘 링크. 로그인하지 않았으면 이동 대신 로그인 화면으로 보낸다. */
export default function ScrapLink() {
  const router = useRouter();
  return (
    <Link
      href="/scraps"
      className="icon-link"
      aria-label="내 스크랩"
      onClick={(e) => {
        if (isLoggedIn()) return;
        e.preventDefault();
        router.push(loginHref('/scraps'));
      }}
    >
      <BookmarkIcon />
    </Link>
  );
}
