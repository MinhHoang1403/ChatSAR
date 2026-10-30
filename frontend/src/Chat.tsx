import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api, record } from './api';
import type { Dataset } from './Datasets';
import Menu from './Menu';
import Result from './Result';

export type Conversation = { id: string; title: string; revision_id: string | null; dataset_name: string | null };
export type Answer = { status: string; display_text: string; facts: Record<string, unknown>;
  display_rows: unknown[][]; limitations: string[] };
type Message = { id: string; question: string; revision_id: string; envelope: Answer | null };
function answer(value: unknown): Answer {
  if (!record(value) || typeof value.status !== 'string' || typeof value.display_text !== 'string'
    || !record(value.facts) || !Array.isArray(value.display_rows)
    || !value.display_rows.every(Array.isArray) || !Array.isArray(value.limitations)
    || !value.limitations.every((v: unknown) => typeof v === 'string')) throw new Error('Câu trả lời chưa đúng định dạng.');
  return { status: value.status, display_text: value.display_text, facts: value.facts,
    display_rows: value.display_rows as unknown[][], limitations: value.limitations as string[] };
}
export function conversation(value: unknown): Conversation {
  if (!record(value) || typeof value.id !== 'string' || typeof value.title !== 'string') throw new Error('Cuộc trò chuyện chưa đúng định dạng.');
  if (value.revision_id != null && typeof value.revision_id !== 'string') throw new Error('Nguồn cuộc trò chuyện không hợp lệ.');
  return { id: value.id, title: value.title, revision_id: typeof value.revision_id === 'string' ? value.revision_id : null,
    dataset_name: typeof value.dataset_name === 'string' ? value.dataset_name : null };
}
export default function Chat({ workspaceId, csrf, scope, selected, onSelect, onRefresh, onBusy, onManageData, onCreateWorkspace }: {
  workspaceId: string; csrf: string; scope: Dataset | null; selected: string;
  onSelect: (id: string) => void; onRefresh: () => Promise<void>;
  onBusy: (busy: boolean) => void; onManageData: (upload?: boolean) => void; onCreateWorkspace: () => void;
}) {
  const [history, setHistory] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [provider, setProvider] = useState('gemini');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const textarea = useRef<HTMLTextAreaElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const sending = useRef(false);
  const pending = useRef<{ body: string; key: string; conversationId: string } | null>(null);
  const historyRequest = useRef(0);
  const serverPending = history.some((m) => m.envelope === null);
  const blocked = busy || serverPending;
  useEffect(() => { onBusy(blocked); }, [blocked, onBusy]);
  useEffect(() => {
    const field = textarea.current;
    if (field) { field.style.height = 'auto'; field.style.height = `${Math.min(field.scrollHeight, 180)}px`; }
  }, [question]);
  async function readHistory(id: string): Promise<Message[]> {
    const data = await api(`/conversations/${id}`);
    if (!record(data) || !Array.isArray(data.messages)) throw new Error('Lịch sử chưa đúng định dạng.');
    return data.messages.map((m: unknown) => {
      if (!record(m) || typeof m.id !== 'string' || typeof m.question !== 'string' || typeof m.revision_id !== 'string') throw new Error('Tin nhắn chưa đúng định dạng.');
      return { id: m.id, question: m.question, revision_id: m.revision_id, envelope: m.envelope === null ? null : answer(m.envelope) };
    });
  }
  useEffect(() => {
    let active = true;
    const version = ++historyRequest.current;
    setHistory([]); setError('');
    if (!selected) { setLoading(false); return; }
    setLoading(true);
    readHistory(selected).then((data) => { if (active && version === historyRequest.current) setHistory(data); })
      .catch((e: unknown) => { if (active) setError(message(e)); })
      .finally(() => { if (active && version === historyRequest.current) setLoading(false); });
    return () => { active = false; };
  }, [selected]);
  useEffect(() => {
    if (!serverPending || busy || !selected) return;
    let active = true;
    // Chỉ đọc trạng thái đã lưu; không tự gửi lại câu hỏi hoặc gọi provider.
    const timer = window.setInterval(() => { void readHistory(selected).then((rows) => {
      if (active) setHistory(rows);
    }).catch((e: unknown) => { if (active) setError(message(e)); }); }, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, [serverPending, busy, selected]);
  async function send(event: FormEvent) {
    event.preventDefault();
    if (sending.current || blocked || loading || !scope || !question.trim()) return;
    sending.current = true; setBusy(true); setError('');
    let id = selected;
    try {
      if (!id) {
        id = conversation(await api('/conversations', { method: 'POST', body: JSON.stringify({ workspace_id: workspaceId, title: question.trim().slice(0, 120) }) }, csrf)).id;
        onSelect(id);
      }
      const body = JSON.stringify({ question: question.trim(), dataset_revision_id: scope.revision_id, provider, allow_fallback: false });
      if (!pending.current || pending.current.body !== body || pending.current.conversationId !== id) pending.current = { body, key: crypto.randomUUID(), conversationId: id };
      await api(`/conversations/${id}/messages`, { method: 'POST', body, headers: { 'Idempotency-Key': pending.current.key } }, csrf).then(answer);
      pending.current = null; setQuestion('');
    } catch (e: unknown) { setError(message(e)); }
    finally {
      if (id) {
        ++historyRequest.current;
        try { setHistory(await readHistory(id)); await onRefresh(); } catch (e: unknown) { setError(message(e)); }
      }
      setLoading(false); sending.current = false; setBusy(false);
    }
  }
  const stale = Boolean(scope && history.some((item) => item.revision_id !== scope.revision_id));
  return <section className="chat" aria-label="Hỏi dữ liệu">
    <div className="messages" aria-live="polite">
      {loading && <p role="status">Đang tải lịch sử…</p>}
      {!loading && !history.length && !busy && <div className="empty-chat"><h1>Bạn muốn tìm hiểu điều gì?</h1><p>{scope ? `Hỏi dữ liệu trong ${scope.name}.` : 'Chọn nguồn dữ liệu để bắt đầu.'}</p></div>}
      {history.map((item) => <article key={item.id} className="message"><div className="user-message"><p>{item.question}</p></div>
        <div className="assistant-message"><span className="assistant-label">ChatSAR</span>
          {scope && item.revision_id !== scope.revision_id && <p className="scope-note">Kết quả thuộc nguồn trước đó.</p>}
          {item.envelope ? <Result value={item.envelope} /> : <p role="status">Đang xử lý…</p>}
        </div></article>)}
      {busy && !serverPending && <div className="pending-message"><p role="status">Đang xử lý…</p></div>}
    </div>
    <div className="composer-area">
      {error && <p className="error" role="alert">{error}</p>}
      {stale && <p className="scope-note">Nguồn đã đổi. <button className="secondary" disabled={blocked} onClick={() => onSelect('')}>Tạo đoạn chat mới</button></p>}
      <form ref={form} className="composer" onSubmit={send}>
        <Menu label="Thêm dữ liệu và không gian" text="＋" className="composer-menu" disabled={blocked} items={[
          { label: 'Tải dữ liệu lên', action: () => onManageData(true) },
          { label: 'Tạo không gian làm việc', action: onCreateWorkspace },
          { label: 'Quản lý dữ liệu', action: () => onManageData(false) },
        ]} />
        <label htmlFor="question" className="sr-only">Câu hỏi của bạn</label>
        <textarea ref={textarea} id="question" rows={1} value={question} maxLength={4000} required disabled={blocked}
          placeholder="Nhập câu hỏi…" onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); form.current?.requestSubmit(); } }} />
        <label className="model-select"><span className="sr-only">Mô hình</span><select aria-label="Mô hình" value={provider} disabled={blocked} onChange={(e) => setProvider(e.target.value)}><option value="gemini">Gemini</option><option value="knowledge">Knowledge</option></select></label>
        <button className="send-button" aria-label="Gửi câu hỏi" disabled={blocked || loading || !scope || stale || !question.trim()}>↑</button>
      </form>
    </div>
  </section>;
}
function message(error: unknown): string { return error instanceof Error ? error.message : 'Chưa thể lấy kết quả.'; }
