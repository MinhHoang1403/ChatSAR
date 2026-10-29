import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api, record } from './api';
import type { Dataset } from './Datasets';
import Result from './Result';

export type Conversation = { id: string; title: string };
export type Answer = { status: string; display_text: string; facts: Record<string, unknown>;
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

export default function Chat({ workspaceId, csrf, scope, selected, onSelect, onList, onBusy, onManageData }: {
  workspaceId: string; csrf: string; scope: Dataset | null; selected: string;
  onSelect: (id: string) => void; onList: (items: Conversation[]) => void;
  onBusy: (busy: boolean) => void; onManageData: () => void;
}) {
  const [list, setList] = useState<Conversation[]>([]);
  const setSelected = onSelect;
  const [history, setHistory] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [provider, setProvider] = useState('gemini');
  const [allowFallback, setAllowFallback] = useState(false);
  const [fallbackAvailable, setFallbackAvailable] = useState(false);
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

  useEffect(() => { onList(list); }, [list, onList]);
  useEffect(() => { onBusy(busy); }, [busy, onBusy]);
  useEffect(() => {
    let active = true;
    api('/providers').then((data) => { if (active) setFallbackAvailable(record(data) && data.knowledge_fallback_available === true); }).catch(() => {});
    return () => { active = false; };
  }, []);

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
      const body = JSON.stringify({ question: question.trim(), dataset_revision_id: scope.revision_id, provider, allow_fallback: provider === 'gemini' && allowFallback });
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

  const stale = Boolean(scope && history.some((item) => item.envelope?.status === 'answered' && item.revision_id !== scope.revision_id));
  return <section className="chat" aria-label="Hỏi dữ liệu">
    <div className="messages" aria-live="polite">
      {loading && <p role="status">Đang tải lịch sử…</p>}
      {!loading && !history.length && !busy && <div className="empty-chat"><span className="empty-symbol">C</span>
        <h1>Bạn muốn biết điều gì từ dữ liệu?</h1><p>{scope ? `Đang sử dụng ${scope.name}. Hãy đặt câu hỏi về số liệu, điều kiện hoặc nhóm dữ liệu.` : 'Tải CSV hoặc Excel, kiểm tra đề xuất và chọn dữ liệu để bắt đầu.'}</p>
        {!scope && <button className="secondary" onClick={onManageData}>Tải dữ liệu lên</button>}</div>}
      {history.map((item) => <article key={item.id} className="message">
        <div className="user-message"><span>Bạn</span><p>{item.question}</p></div>
        <div className="assistant-message"><span className="assistant-label">ChatSAR</span>
          {scope && item.revision_id !== scope.revision_id && <p className="scope-note">Kết quả này thuộc nguồn trước đó. Tạo cuộc trò chuyện mới để hỏi nguồn hiện tại.</p>}
          {item.envelope ? <Result value={item.envelope} /> : <p>Yêu cầu đang xử lý. Dùng “Cập nhật lịch sử” để xem kết quả, không cần gửi lại.</p>}
        </div></article>)}
      {busy && <div className="pending-message"><p className="user-message">{question}</p><p role="status">ChatSAR đang hiểu câu hỏi và lấy kết quả. Có thể mất tối đa khoảng một phút…</p></div>}
    </div>
    <div className="composer-area">
      {error && <p className="error" role="alert">{error}</p>}
      {stale && <p className="scope-note">Nguồn đã đổi. <button className="secondary" disabled={busy} onClick={() => onSelect('')}>Tạo cuộc trò chuyện mới</button></p>}
      <form className="composer" onSubmit={send}>
        <label htmlFor="question" className="sr-only">Câu hỏi của bạn</label>
        <textarea id="question" value={question} maxLength={4000} required disabled={busy}
          placeholder={scope ? 'Hỏi một câu về dữ liệu của bạn…' : 'Chọn dữ liệu trước khi đặt câu hỏi'} onChange={(e) => setQuestion(e.target.value)} />
        <div className="composer-actions"><label>Mô hình<select value={provider} disabled={busy} onChange={(e) => { setProvider(e.target.value); setAllowFallback(false); }}><option value="gemini">Gemini</option><option value="knowledge">Knowledge</option></select></label>
          {selected && <button type="button" className="quiet" disabled={busy || loading} onClick={async () => { setLoading(true); try { setHistory(await readHistory(selected)); } catch (e: unknown) { setError(message(e)); } finally { setLoading(false); } }}>Cập nhật lịch sử</button>}
          <button className="send-button" disabled={busy || loading || !scope || stale || !question.trim()}>{busy ? 'Đang xử lý…' : 'Gửi ↑'}</button></div>
      </form>
      <label className="check fallback-choice"><input type="checkbox" checked={allowFallback} disabled={busy || !fallbackAvailable || provider !== 'gemini'} onChange={(e) => setAllowFallback(e.target.checked)} />Dùng Knowledge nếu Gemini tạm lỗi{!fallbackAvailable ? ' (chưa xác nhận kết nối Knowledge)' : ''}</label>
      <p className="composer-note">{!scope ? 'Chưa chọn dữ liệu. Mở Quản lý dữ liệu để chuẩn bị nguồn.' : 'Kết quả có nguồn đối chiếu. Hãy kiểm tra điều kiện khi câu hỏi có nhiều cách hiểu.'}</p>
    </div>
  </section>;
}
function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Chưa thể lấy kết quả. Vui lòng thử lại.';
}
