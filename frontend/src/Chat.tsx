import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api, record } from './api';
import type { Dataset } from './Datasets';

type Conversation = { id: string; title: string };
type Answer = { status: string; display_text: string; facts: Record<string, unknown>;
  display_rows: unknown[][]; limitations: string[] };
type Message = { id: string; question: string; revision_id: string; envelope: Answer | null };

function answer(value: unknown): Answer {
  if (!record(value) || typeof value.status !== 'string' || typeof value.display_text !== 'string'
    || !record(value.facts) || !Array.isArray(value.display_rows)
    || !value.display_rows.every(Array.isArray) || !Array.isArray(value.limitations)
    || !value.limitations.every((v: unknown) => typeof v === 'string')) {
    throw new Error('Câu trả lời chưa đúng định dạng.');
  }
  return { status: value.status, display_text: value.display_text, facts: value.facts,
    display_rows: value.display_rows as unknown[][], limitations: value.limitations as string[] };
}

function conversation(value: unknown): Conversation {
  if (!record(value) || typeof value.id !== 'string' || typeof value.title !== 'string') {
    throw new Error('Cuộc trò chuyện chưa đúng định dạng.');
  }
  return { id: value.id, title: value.title };
}

export default function Chat({ workspaceId, csrf, scope }: {
  workspaceId: string; csrf: string; scope: Dataset | null;
}) {
  const [list, setList] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState('');
  const [history, setHistory] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [provider, setProvider] = useState('gemini');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef<{ body: string; key: string; conversationId: string } | null>(null);
  const historyRequest = useRef(0);

  useEffect(() => {
    let active = true;
    api(`/conversations?workspace_id=${encodeURIComponent(workspaceId)}`).then((data) => {
      if (!Array.isArray(data)) throw new Error('Lịch sử chưa đúng định dạng.');
      if (active) setList(data.map(conversation));
    }).catch((e: unknown) => { if (active) setError(message(e)); });
    return () => { active = false; };
  }, [workspaceId]);

  async function readHistory(id: string): Promise<Message[]> {
    const data = await api(`/conversations/${id}`);
    if (!record(data) || !Array.isArray(data.messages)) throw new Error('Lịch sử chưa đúng định dạng.');
    return data.messages.map((m: unknown) => {
      if (!record(m) || typeof m.id !== 'string' || typeof m.question !== 'string'
        || typeof m.revision_id !== 'string') throw new Error('Lượt hỏi chưa đúng định dạng.');
      return { id: m.id, question: m.question, revision_id: m.revision_id,
        envelope: m.envelope === null ? null : answer(m.envelope) };
    });
  }

  useEffect(() => {
    let active = true;
    const version = ++historyRequest.current;
    setHistory([]); setError('');
    if (!selected) { setLoading(false); return; }
    setLoading(true);
    readHistory(selected).then((data) => { if (active && version === historyRequest.current) setHistory(data); })
      .catch((e: unknown) => { if (active && version === historyRequest.current) setError(message(e)); })
      .finally(() => { if (active && version === historyRequest.current) setLoading(false); });
    return () => { active = false; };
  }, [selected]);

  async function send(event: FormEvent) {
    event.preventDefault();
    if (busy || loading || !scope || !question.trim()) return;
    setBusy(true); setError('');
    try {
      let id = selected;
      if (!id) {
        const created = conversation(await api('/conversations', { method: 'POST',
          body: JSON.stringify({ workspace_id: workspaceId, title: question.trim().slice(0, 120) }) }, csrf));
        id = created.id; setList((items) => [created, ...items]); setSelected(id);
      }
      const body = JSON.stringify({ question: question.trim(), dataset_revision_id: scope.revision_id, provider });
      if (!pending.current || pending.current.body !== body || pending.current.conversationId !== id) {
        pending.current = { body, key: crypto.randomUUID(), conversationId: id };
      }
      await api(`/conversations/${id}/messages`, { method: 'POST', body,
        headers: { 'Idempotency-Key': pending.current.key } }, csrf).then(answer);
      pending.current = null; setQuestion('');
      ++historyRequest.current;
      setHistory(await readHistory(id)); setLoading(false);
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }

  return <section className="chat" aria-labelledby="chat-title">
    <h2 id="chat-title">Hỏi dữ liệu</h2>
    <p>{scope ? `Nguồn đang chọn: ${scope.name}` : 'Mở một bộ dữ liệu đã xác nhận ở phía trên để bắt đầu.'}</p>
    <div className="chat-controls">
      <label>Cuộc trò chuyện <select value={selected} disabled={busy} onChange={(e) => setSelected(e.target.value)}>
        <option value="">Cuộc trò chuyện mới</option>
        {list.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select></label>
      <label>Mô hình <select value={provider} disabled={busy} onChange={(e) => setProvider(e.target.value)}>
        <option value="gemini">Gemini</option><option value="knowledge">Knowledge</option>
      </select></label>
    </div>
    {loading && <p role="status">Đang tải lịch sử…</p>}
    {!loading && !history.length && <p>Chưa có lượt hỏi trong cuộc trò chuyện này.</p>}
    <div className="messages" aria-live="polite">{history.map((item) => <article key={item.id} className="message">
      <h3>{item.question}</h3>
      {scope && item.revision_id !== scope.revision_id && <p className="scope-note">Kết quả này thuộc phiên bản dữ liệu khác với nguồn đang chọn.</p>}
      {item.envelope ? <Result value={item.envelope} /> : <p>Yêu cầu đang xử lý. Tải lại lịch sử để xem kết quả; không cần gửi lại.</p>}
    </article>)}</div>
    {error && <p className="error" role="alert">{error}</p>}
    <form onSubmit={send}>
      <label htmlFor="question">Câu hỏi của bạn</label>
      <textarea id="question" value={question} maxLength={4000} required disabled={busy}
        placeholder="Ví dụ: Tổng số tiền trong dữ liệu là bao nhiêu?" onChange={(e) => setQuestion(e.target.value)} />
      <button disabled={busy || loading || !scope || !question.trim()}>{busy ? 'Đang lấy kết quả…' : 'Gửi câu hỏi'}</button>
    </form>
  </section>;
}

function Result({ value }: { value: Answer }) {
  const columns = Array.isArray(value.facts.columns) ? value.facts.columns.filter(record) : [];
  const scope = record(value.facts.scope) ? value.facts.scope : null;
  const filters = Array.isArray(value.facts.filters) ? value.facts.filters.filter(record) : [];
  return <>
    <p>{value.display_text}</p>
    {value.display_rows.length > 0 && <div className="table-scroll"><table>
      <thead><tr>{columns.map((c, i) => <th key={i}>{cell(c.name)}{c.unit ? ` (${cell(c.unit)})` : ''}</th>)}</tr></thead>
      <tbody>{value.display_rows.map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{cell(v)}</td>)}</tr>)}</tbody>
    </table></div>}
    {scope && <details><summary>Nguồn và cách tính</summary>
      <p>Phiên bản dữ liệu: <code>{cell(scope.source_revision)}</code></p>
      <p>Mỗi dòng nguồn: {cell(scope.grain)} · Múi giờ: {cell(scope.timezone)}</p>
      <p>Phép tính: {columns.map((c) => cell(c.name)).join(', ')}</p>
      {filters.length > 0 && <p>Giá trị lọc đã đối chiếu: {filters.map((f) => cell(f.raw_phrase)).join(', ')}</p>}
      <p>Mã đối chiếu nguồn: <code>{cell(scope.checksum)}</code></p>
      <p>Kết quả lấy từ dữ liệu đã xác nhận. Cần kiểm tra điều kiện lọc khi câu hỏi có nhiều nghĩa.</p>
    </details>}
    {value.limitations.map((text, i) => <p className="limitation" key={i}>{text}</p>)}
  </>;
}

function cell(value: unknown): string {
  if (value === null) return 'Chưa có giá trị';
  if (typeof value === 'boolean') return value ? 'Có' : 'Không';
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}
function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Chưa thể lấy kết quả. Vui lòng thử lại.';
}
