import { Suspense } from 'react';
import Chat from '@/components/Chat';

export default function ChatPage() {
  return (
    <Suspense>
      <Chat />
    </Suspense>
  );
}
