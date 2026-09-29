type Props = { pins: { x: number; y: number }[]; active?: number; height?: number };

// 실제 지도 API(카카오맵 등) 붙이기 전 임시 지도
export default function MiniMap({ pins, active = 0, height = 130 }: Props) {
  return (
    <svg className="minimap" viewBox="0 0 400 170" preserveAspectRatio="xMidYMid slice" style={{ height }} role="img" aria-label="지도">
      <rect width="400" height="170" fill="var(--land)" />
      <path d="M250 0 C270 40 300 70 330 90 S400 120 400 120 V0Z" fill="var(--sea)" />
      <g stroke="var(--road)" strokeLinecap="round" fill="none">
        <path d="M0 110 C90 100 170 95 250 70 S330 40 360 0" strokeWidth="7" />
        <path d="M60 0 L140 170 M0 60 L240 125 M190 0 L215 170" strokeWidth="4" />
      </g>
      {pins.map((p, i) => {
        const on = i === active;
        return (
          <g key={i} transform={`translate(${p.x * 400} ${p.y * 170})`}>
            <circle r={on ? 13 : 10} fill={on ? 'var(--ac)' : 'var(--ink)'} stroke="var(--sf)" strokeWidth="2.5" />
            <text y="4.5" textAnchor="middle" fontSize="11" fontWeight="700" fill={on ? '#fff' : 'var(--sf)'}>{i + 1}</text>
          </g>
        );
      })}
    </svg>
  );
}
