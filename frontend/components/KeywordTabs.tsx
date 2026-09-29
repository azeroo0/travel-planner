'use client';

import { useState } from 'react';
import type { Keyword } from '@/lib/types';

export default function KeywordTabs({ good, bad }: { good: Keyword[]; bad: Keyword[] }) {
  const [tab, setTab] = useState<'good' | 'bad'>('good');
  const list = tab === 'good' ? good : bad;
  return (
    <>
      <div className="seg">
        <button aria-pressed={tab === 'good'} onClick={() => setTab('good')}>좋았어요</button>
        <button aria-pressed={tab === 'bad'} onClick={() => setTab('bad')}>아쉬웠어요</button>
      </div>
      {list.map((k) => (
        <div key={k.text} className="kw"><span>{k.text}</span><b>{k.count}</b></div>
      ))}
    </>
  );
}
