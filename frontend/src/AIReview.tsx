import { api, record } from './api';
import { mergeProposalColumn, parseColumn } from './data';
import type { Column, Preview } from './data';

export type PreparedDataset = { columns: Column[]; description: string; grain: string;
  notes: string[]; mode: string; error_code: string | null };

export function savedSetupResponse(preview: Preview): Record<string, unknown> | null {
  const saved = preview.setup_proposal;
  return record(saved) && saved.status === 'complete' && record(saved.response)
    && Boolean(preview.checksum) && saved.response.checksum === preview.checksum
    && saved.response.sheet_name === preview.sheet_name ? saved.response : null;
}

export function readPreparedDataset(data: unknown, preview: Preview): PreparedDataset {
  if (!record(data) || !record(data.proposal) || !Array.isArray(data.proposal.columns)
    || typeof data.proposal.description !== 'string' || typeof data.proposal.grain !== 'string'
    || data.checksum !== preview.checksum || data.sheet_name !== preview.sheet_name
    || data.proposal.columns.length !== preview.columns.length) throw new Error('Đề xuất chưa khớp dữ liệu nguồn.');
  const columns = data.proposal.columns.map((value: unknown, index: number): Column => {
    const column = parseColumn(value);
    if (column.id !== preview.columns[index].id) throw new Error('Thứ tự cột đề xuất chưa khớp file nguồn.');
    return mergeProposalColumn(preview.columns[index], column);
  });
  return { columns, description: data.proposal.description, grain: data.proposal.grain,
    mode: typeof data.mode === 'string' ? data.mode : 'local',
    error_code: typeof data.error_code === 'string' ? data.error_code : null,
    notes: [...(Array.isArray(data.proposal.notes) ? data.proposal.notes.filter((v): v is string => typeof v === 'string') : []),
      ...(Array.isArray(data.issues) ? data.issues.filter(record).map((issue) => typeof issue.message === 'string' ? issue.message : '').filter(Boolean) : []),
      ...(Array.isArray(data.validation_errors) ? data.validation_errors.filter((v): v is string => typeof v === 'string') : [])] };
}

export async function analyzeDataset(preview: Preview, csrf: string, key: string,
  options: { force?: boolean; localOnly?: boolean } = {}): Promise<PreparedDataset> {
  const saved = options.force ? null : savedSetupResponse(preview);
  if (saved) return readPreparedDataset(saved, preview);
  const data = await api(`/datasets/${preview.dataset_id}/setup`, { method: 'POST',
    headers: { 'Idempotency-Key': key }, body: JSON.stringify({ revision_id: preview.revision_id,
      sheet_name: preview.sheet_name || null, use_ai: !options.localOnly, consent_metadata: !options.localOnly,
      consent_values: !options.localOnly, provider: 'gemini' }) }, csrf);
  return readPreparedDataset(data, preview);
}

export default function AIReview({ busy, notice, notes, onRetry }: {
  busy: boolean; notice: string; notes: string[]; onRetry?: () => void;
}) {
  if (!notice && !busy && !notes.length) return null;
  return <section className="ai-review" aria-label="Kết quả nhận diện dữ liệu">
    <div><h3>{busy ? 'Đang chuẩn bị dữ liệu…' : 'Gợi ý chuẩn hoá'}</h3>
      {notice && <p role="status">{notice}</p>}</div>
    {notes.length > 0 && <details className="review-notes"><summary>Lưu ý cần xem lại ({notes.length})</summary>
      {notes.map((note, index) => <p key={index}>{note}</p>)}</details>}
    {onRetry && <button className="secondary" disabled={busy} onClick={onRetry}>Thử phân tích lại</button>}
  </section>;
}
