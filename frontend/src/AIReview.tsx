import { useEffect, useRef, useState } from 'react';
import { api, record } from './api';
import type { Column, Preview } from './data';
import { mergeProposalColumn, parseColumn } from './data';

type Props = { preview: Preview; csrf: string; onBusy: (busy: boolean) => void;
  onProposal: (columns: Column[], description: string, grain: string) => void };

export default function AIReview({ preview, csrf, onBusy, onProposal }: Props) {
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [notes, setNotes] = useState<string[]>([]);
  const [provider, setProvider] = useState('gemini');
  const pending = useRef<{ body: string; key: string } | null>(null);
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const saved = record(preview.setup_proposal) && preview.setup_proposal.status === 'complete'
    && record(preview.setup_proposal.response) && preview.checksum
    && preview.setup_proposal.response.checksum === preview.checksum
    && preview.setup_proposal.response.sheet_name === preview.sheet_name ? preview.setup_proposal.response : null;
  function applyProposal(data: unknown) {
    if (!record(data) || !record(data.proposal) || !Array.isArray(data.proposal.columns)
      || typeof data.proposal.description !== 'string' || typeof data.proposal.grain !== 'string') throw new Error('Đề xuất chưa đúng định dạng.');
    const columns = data.proposal.columns.map((value: unknown): Column => {
      const column = parseColumn(value);
      const source = preview.columns.find((c) => c.id === column.id);
      if (!source) throw new Error('Đề xuất có mã cột không thuộc file nguồn.');
      return mergeProposalColumn(source, column);
    });
    onProposal(columns, data.proposal.description, data.proposal.grain);
    setNotes([...(Array.isArray(data.proposal.notes) ? data.proposal.notes.filter((v): v is string => typeof v === 'string') : []),
      ...(Array.isArray(data.issues) ? data.issues.filter(record).map((issue) => typeof issue.message === 'string' ? issue.message : '').filter(Boolean) : []),
      ...(Array.isArray(data.validation_errors) ? data.validation_errors.filter((v): v is string => typeof v === 'string') : [])]);
  }
  async function analyze(useAI: boolean) {
    if (busy || (useAI && !consent)) return;
    setBusy(true); onBusy(true); setNotice('');
    try {
      const body = JSON.stringify({ revision_id: preview.revision_id, sheet_name: preview.sheet_name || null,
        use_ai: useAI, consent_metadata: useAI && consent, provider });
      if (!pending.current || pending.current.body !== body) pending.current = { body, key: crypto.randomUUID() };
      const data = await api(`/datasets/${preview.dataset_id}/setup`, { method: 'POST', body,
        headers: { 'Idempotency-Key': pending.current.key } }, csrf);
      if (!active.current) return;
      applyProposal(data);
      if (!record(data)) throw new Error('Đề xuất chưa đúng định dạng.');
      setNotice(data.mode === 'ai_proposal' ? 'Đề xuất AI đã qua kiểm tra kiểu và khóa trên toàn bảng. Ý nghĩa cột và đơn vị vẫn cần bạn xác nhận.'
        : data.error_code ? 'AI chưa cung cấp đề xuất dùng được. Bạn có thể tiếp tục với phân tích local.' : 'Đã phân tích toàn bộ dữ liệu trên máy. Xem lại các đề xuất bên dưới.');
    } catch (e: unknown) { if (active.current) setNotice(e instanceof Error ? e.message : 'Chưa thể phân tích. Bạn vẫn có thể chỉnh thủ công.'); }
    finally { if (active.current) { setBusy(false); onBusy(false); } }
  }
  return <section className="ai-review" aria-label="Đề xuất chuẩn bị dữ liệu">
    <div><h3>Chuẩn bị dữ liệu thông minh</h3><p>Phân tích local giữ dữ liệu trên máy. AI có thể đề xuất tên gọi và ý nghĩa cột để bạn xem lại.</p></div>
    <button className="secondary" disabled={busy} onClick={() => void analyze(false)}>Phân tích local</button>
    {saved && <button className="secondary" disabled={busy} onClick={() => { try { applyProposal(saved); setNotice('Đã mở đề xuất đã lưu. Không gọi lại AI; hãy xem lại trước khi xác nhận.'); } catch (e: unknown) { setNotice(e instanceof Error ? e.message : 'Chưa mở được đề xuất.'); } }}>Mở đề xuất đã lưu</button>}
    <details className="setup-model"><summary>Mô hình đề xuất: {provider === 'gemini' ? 'Gemini' : 'Knowledge'}</summary><label>Chọn mô hình<select value={provider} disabled={busy} onChange={(e) => setProvider(e.target.value)}><option value="gemini">Gemini</option><option value="knowledge">Knowledge</option></select></label></details>
    <label className="check"><input type="checkbox" checked={consent} disabled={busy} onChange={(e) => setConsent(e.target.checked)} />Cho phép gửi tên cột và thống kê tới {provider === 'gemini' ? 'Gemini' : 'Knowledge'} cho lượt phân tích này; không gửi dòng dữ liệu.</label>
    <button disabled={busy || !consent} onClick={() => void analyze(true)}>{busy ? 'Đang phân tích dữ liệu…' : 'Nhận đề xuất AI'}</button>
    {busy && <p role="status">Đang xử lý yêu cầu. Có thể mất tối đa khoảng một phút.</p>}
    {notice && <p role="status">{notice}</p>}{notes.map((note, i) => <p className="review-note" key={i}>{note}</p>)}
  </section>;
}
