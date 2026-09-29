export const models = ['EXAONE 3.5 7.8B', 'Gemma', 'Qwen'] as const;

// higher: 값이 클수록 좋은 지표인지
export const metrics: { label: string; desc?: string; values: number[]; unit?: string; higher: boolean }[] = [
  { label: 'JSON 형식 준수율', desc: '파싱 가능한 출력 비율', values: [98.7, 96.0, 97.3], unit: '%', higher: true },
  { label: 'Aspect F1', values: [0.81, 0.76, 0.79], higher: true },
  { label: 'Sentiment 정확도', values: [0.89, 0.87, 0.9], higher: true },
  { label: 'Context 추출률', values: [0.84, 0.71, 0.78], higher: true },
  { label: 'Evidence 일치율', values: [0.92, 0.9, 0.93], higher: true },
  { label: '평균 응답 시간', values: [2.9, 2.3, 2.6], unit: 's', higher: false },
  { label: 'VRAM', values: [7.1, 7.8, 6.4], unit: 'GB', higher: false },
];
