import { getExperimentMetrics } from '@/lib/server-api';

export const dynamic = 'force-dynamic';
const models = [
  ['base', 'Base'], ['lora_gold', 'LoRA Gold'], ['qlora_gold', 'QLoRA Gold'],
  ['lora_gs', 'LoRA Gold+Silver'], ['qlora_gs', 'QLoRA Gold+Silver'],
] as const;

export default async function ComparePage() {
  let rows;
  try { rows = await getExperimentMetrics(); }
  catch (error) { return <div className="compare"><h1>모델 비교</h1><p role="alert">{(error as Error).message}</p></div>; }
  return (
    <div className="compare">
      <h1>모델 비교</h1>
      {!rows.length ? <p>표시할 평가 결과가 없습니다.</p> : <div className="table-wrap"><table>
        <thead><tr><th>지표</th>{models.map(([key, label]) => <th key={key}>{label}</th>)}</tr></thead>
        <tbody>{rows.map((row) => <tr key={row.metric}>
          <th>{row.metric}<small>{row.unit}</small></th>
          {models.map(([key]) => <td key={key}>{row.scores[key] ?? '—'}</td>)}
        </tr>)}</tbody>
      </table></div>}
    </div>
  );
}
