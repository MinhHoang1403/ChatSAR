import { useCallback, useEffect, useRef, useState } from 'react';
import type { Identity, Workspace } from './api';
import { api, record } from './api';
import Chat from './Chat';
import type { Conversation } from './Chat';
import Datasets, { datasetList } from './Datasets';
import type { Dataset } from './Datasets';

type Props = { me: Identity; workspaces: Workspace[]; selected: Workspace | null;
  onSelect: (workspace: Workspace) => void; onCreate: (name: string) => Promise<void>;
  onLogout: () => Promise<void>; busy: boolean; error: string };

export default function WorkspaceView({ me, workspaces, selected, onSelect, onCreate, onLogout, busy, error }: Props) {
  const [scope, setScope] = useState<Dataset | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState('');
  const [search, setSearch] = useState('');
  const [name, setName] = useState('');
  const [dataOpen, setDataOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [health, setHealth] = useState('Đang kiểm tra kết nối');
  const [dataError, setDataError] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const refreshDatasets = useCallback(async () => {
    if (!selected) return;
    try {
      const items = datasetList(await api(`/workspaces/${selected.id}/datasets`));
      setDatasets(items);
      setScope((old) => old ?? items.find((item) => item.status === 'ready') ?? null);
    } catch (e: unknown) { setDataError(e instanceof Error ? e.message : 'Chưa tải được dữ liệu.'); }
  }, [selected]);
  useEffect(() => { void refreshDatasets(); }, [refreshDatasets]);
  useEffect(() => {
    let active = true;
    api('/health').then((data) => { if (active) setHealth(record(data) && data.status === 'ok' ? 'Hệ thống sẵn sàng' : 'Chưa kết nối hệ thống'); })
      .catch(() => { if (active) setHealth('Chưa kết nối hệ thống'); });
    return () => { active = false; };
  }, []);
  useEffect(() => { if (dataOpen) dialog.current?.showModal(); else dialog.current?.close(); }, [dataOpen]);
  return <div className={`shell ${menuOpen ? 'menu-open' : ''}`}>
    <aside className="sidebar" aria-label="Điều hướng chính">
      <div className="brand"><span className="brand-mark">C</span><div>ChatSAR<small>Trợ lý dữ liệu</small></div>
        <button className="mobile-menu quiet" aria-label="Đóng điều hướng" onClick={() => setMenuOpen(false)}>×</button></div>
      <button className="new-chat" disabled={!selected || pending} onClick={() => { setConversationId(''); setMenuOpen(false); }}>＋ Cuộc trò chuyện mới</button>
      <label className="search">Tìm cuộc trò chuyện<input type="search" value={search} placeholder="Tìm trong lịch sử…" onChange={(e) => setSearch(e.target.value)} /></label>
      <nav className="history" aria-label="Lịch sử cuộc trò chuyện"><p className="nav-caption">GẦN ĐÂY</p>
        {!conversations.length && <p className="muted">Các cuộc trò chuyện sẽ xuất hiện ở đây.</p>}
        {conversations.filter((item) => item.title.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi'))).map((item) => <button
          key={item.id} title={item.title} className={conversationId === item.id ? 'selected' : 'quiet'} disabled={pending}
          onClick={() => { setConversationId(item.id); setMenuOpen(false); }}>{item.title}</button>)}
      </nav>
      <button className="data-nav" disabled={!selected || pending} onClick={() => { setDataOpen(true); setMenuOpen(false); }}>▦ Quản lý dữ liệu</button>
      <label>Không gian làm việc<select value={selected?.id ?? ''} disabled={busy || pending}
        onChange={(e) => { const item = workspaces.find((w) => w.id === e.target.value); if (item) onSelect(item); }}>
        {!selected && <option value="">Tạo không gian đầu tiên</option>}{workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
      <details className="workspace-create"><summary>Tạo không gian mới</summary><form onSubmit={(e) => { e.preventDefault(); void onCreate(name); }}>
        <label>Tên không gian<input value={name} required maxLength={120} onChange={(e) => setName(e.target.value)} /></label><button disabled={busy || pending || !name.trim()}>Tạo không gian</button></form></details>
      <div className="account"><span className="avatar">{me.display_name.slice(0, 1).toUpperCase()}</span><span>{me.display_name}</span>
        <button className="quiet" disabled={busy || pending} onClick={() => void onLogout()}>Đăng xuất</button></div>
    </aside>
    <main className="workspace-main">
      <header className="workspace-header"><button className="mobile-menu quiet" aria-label="Mở điều hướng" onClick={() => setMenuOpen(true)}>☰</button>
        <div><strong>{conversations.find((c) => c.id === conversationId)?.title ?? 'Cuộc trò chuyện mới'}</strong><small>{selected?.name ?? 'Chưa có không gian làm việc'}</small></div>
        <label className="source-select">Nguồn dữ liệu<select value={scope?.revision_id ?? ''} disabled={pending} onChange={(e) => setScope(datasets.find((d) => d.revision_id === e.target.value) ?? null)}>
          <option value="">Chọn dữ liệu</option>{datasets.filter((d) => d.status === 'ready').map((d) => <option key={d.revision_id} value={d.revision_id}>{d.name}</option>)}</select></label>
        <span className="health" role="status">{health}</span></header>
      {(error || dataError) && <p className="error" role="alert">{error || dataError}</p>}
      {selected ? <Chat workspaceId={selected.id} csrf={me.csrf_token} scope={scope}
        selected={conversationId} onSelect={setConversationId} onList={setConversations} onBusy={setPending}
        onManageData={() => setDataOpen(true)} /> : <div className="empty-chat"><span className="empty-symbol">▦</span><h1>Bắt đầu với dữ liệu của bạn</h1><p>Tạo không gian làm việc ở bên trái để tải dữ liệu và đặt câu hỏi.</p></div>}
    </main>
    <dialog ref={dialog} onCancel={() => setDataOpen(false)} onClose={() => setDataOpen(false)} aria-labelledby="data-title">
      <header className="dialog-header"><div><h2 id="data-title">Quản lý dữ liệu</h2><p>Tải lên, kiểm tra và bắt đầu hỏi.</p></div><button className="quiet" aria-label="Đóng quản lý dữ liệu" onClick={() => { setDataOpen(false); void refreshDatasets(); }}>×</button></header>
      {dataOpen && selected && <Datasets workspaceId={selected.id} csrf={me.csrf_token} onReady={(dataset) => { setScope(dataset); void refreshDatasets(); }} />}
    </dialog>
  </div>;
}
