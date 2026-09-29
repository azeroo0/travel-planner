import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '어디갈건호?',
  description: '리뷰로 찾는 부산 장소 추천',
  icons: { icon: '/avatar.png' },
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1, viewportFit: 'cover' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <main className="app">{children}</main>
      </body>
    </html>
  );
}
