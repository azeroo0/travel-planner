import Link from 'next/link';

export default function LoginPage() {
  return <div className="compare">
    <Link href="/">← 홈으로</Link>
    <h1>로그인</h1>
    <p className="muted">로그인 기능은 추후 연결합니다. DB 장소 목록은 로그인 없이 확인할 수 있습니다.</p>
    <form className="analyzer-form">
      <label>이메일<input type="email" autoComplete="email" disabled /></label>
      <label>비밀번호<input type="password" autoComplete="current-password" disabled /></label>
      <button type="button" disabled>로그인 준비 중</button>
    </form>
  </div>;
}
