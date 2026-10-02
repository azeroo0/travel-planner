import { apiRequest } from './api';

export type AuthUser = {
  user_id: number;
  email: string;
  name: string | null;
  role: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
};

type Session = { access_token: string; expires_at: number; user: AuthUser };

// 저장소는 이 파일에서만 다룬다. 쿠키로 바꿀 때는 아래 read/write/remove만 교체하면 된다.
const SESSION_KEY = 'tripfit.auth';
const GUEST_KEY = 'tripfit.guest';
const SPLASH_KEY = 'tripfit.splash';

function read(store: 'local' | 'session', key: string): string | null {
  try { return (store === 'local' ? localStorage : sessionStorage).getItem(key); } catch { return null; }
}
function write(store: 'local' | 'session', key: string, value: string) {
  try { (store === 'local' ? localStorage : sessionStorage).setItem(key, value); } catch { /* 저장소를 못 쓰면 이번 방문에만 유지 */ }
}
function remove(store: 'local' | 'session', key: string) {
  try { (store === 'local' ? localStorage : sessionStorage).removeItem(key); } catch { /* 무시 */ }
}

export function saveSession(response: LoginResponse) {
  const session: Session = {
    access_token: response.access_token,
    expires_at: Date.now() + response.expires_in * 1000,
    user: response.user,
  };
  write('local', SESSION_KEY, JSON.stringify(session));
  clearGuest();
}

/** 만료 전 세션만 돌려준다. 만료됐거나 깨졌으면 지우고 null. */
export function getSession(): Session | null {
  const raw = read('local', SESSION_KEY);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as Session;
    if (typeof session.access_token === 'string' && session.expires_at > Date.now()) return session;
  } catch { /* 아래에서 지운다 */ }
  remove('local', SESSION_KEY);
  return null;
}

export const getToken = () => getSession()?.access_token ?? null;
export const clearSession = () => remove('local', SESSION_KEY);

export const isGuest = () => read('session', GUEST_KEY) === '1';
export const startGuest = () => write('session', GUEST_KEY, '1');
export const clearGuest = () => remove('session', GUEST_KEY);

export const hasSeenSplash = () => read('session', SPLASH_KEY) === '1';
export const markSplashSeen = () => write('session', SPLASH_KEY, '1');

/** 로그아웃: 토큰과 게스트 상태를 모두 지운다. */
export function logout() {
  clearSession();
  clearGuest();
}

/** 로그인이 필요한 기능(스크랩 등)이 호출하는 가드. 로그인 상태가 아니면 false. */
export const isLoggedIn = () => getSession() !== null;

/** next는 "/"로 시작하는 내부 경로만 허용한다. "//"·"/\\"·제어문자는 브라우저가 외부 주소로 해석할 수 있어 "/"로 처리한다. */
export function safeNext(next: string | null | undefined): string {
  return next && /^\/(?![/\\])[^\u0000-\u001f]*$/.test(next) ? next : '/';
}

export const loginHref = (next: string) => `/login?next=${encodeURIComponent(next)}`;

/** 현재 경로를 next로 달아 로그인 화면으로 보낸다. 이미 로그인 화면이면 그대로 둔다. */
export function redirectToLogin() {
  if (typeof window === 'undefined' || location.pathname === '/login') return;
  location.assign(loginHref(location.pathname + location.search));
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>('/auth/login', json({ email, password }));
}

/** 가입은 201에 사용자 정보만 돌려주고 토큰은 주지 않는다. */
export function signup(email: string, password: string, name?: string): Promise<AuthUser> {
  return apiRequest<AuthUser>('/auth/signup', json({ email, password, ...(name ? { name } : {}) }));
}
