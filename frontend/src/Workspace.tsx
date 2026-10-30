import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { Identity, Workspace } from './api';
import { api, record } from './api';
import Chat, { conversation } from './Chat';
import type { Conversation } from './Chat';
import Datasets, { datasetList } from './Datasets';
import type { Dataset } from './Datasets';
import Menu from './Menu';

type Props = { me: Identity; workspaces: Workspace[]; selected: Workspace | null;
  onSelect: (workspace: Workspace) => void; onCreate: (name: string) => Promise<void>;
  onLogout: () => Promise<void>; busy: boolean; error: string };
type Profile = { display_name: string; phone: string; interests: string };
type Action = { kind: 'rename' | 'delete'; chat: Conversation } | { kind: 'bulk' } | null;
export function historyGroups(items: Conversation[]) {
  const groups = new Map<string, { label: string; items: Conversation[] }>();
  for (const item of items) {
    const key = item.revision_id ?? 'unknown';
    if (!groups.has(key)) groups.set(key, { label: item.dataset_name ?? 'Chưa xác định nguồn', items: [] });
    groups.get(key)!.items.push(item);
  }
  return Array.from(groups, ([key, value]) => ({ key, ...value }));
}
function Modal({ open, title, onClose, children, wide = false, error = '', closeDisabled = false }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; wide?: boolean; error?: string; closeDisabled?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => { if (open && !ref.current?.open) ref.current?.showModal(); else if (!open) ref.current?.close(); }, [open]);
  return <dialog ref={ref} className={wide ? '' : 'small-dialog'} aria-labelledby={id}
    onCancel={(e) => { e.preventDefault(); if (!closeDisabled) onClose(); }}>
    <header className="dialog-header"><h2 id={id}>{title}</h2><button className="quiet" disabled={closeDisabled} aria-label={`Đóng ${title}`} onClick={onClose}>×</button></header>
    {open && error && <p className="error" role="alert">{error}</p>}
    {open && children}
  </dialog>;
}
export default function WorkspaceView({ me, workspaces, selected, onSelect, onCreate, onLogout, busy, error }: Props) {
  const [scope, setScope] = useState<Dataset | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState('');
  const [search, setSearch] = useState('');
  const [hidden, setHidden] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dataOpen, setDataOpen] = useState(false);
  const [uploadFocus, setUploadFocus] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profile, setProfile] = useState<Profile>({ display_name: me.display_name, phone: '', interests: '' });
  const [draftProfile, setDraftProfile] = useState(profile);
  const [savedName, setSavedName] = useState(me.display_name);
  const [name, setName] = useState('');
  const [action, setAction] = useState<Action>(null);
  const [title, setTitle] = useState('');
  const [pending, setPending] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [dataBusy, setDataBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [localError, setLocalError] = useState('');
  const [health, setHealth] = useState('Đang kiểm tra kết nối');
  const mutation = useRef(false);
  const unavailable = busy || pending || mutating || dataBusy;
  const refreshDatasets = useCallback(async () => {
    if (!selected) return;
    const items = datasetList(await api(`/workspaces/${selected.id}/datasets`));
    setDatasets(items);
    setScope((old) => items.find((item) => item.revision_id === old?.revision_id) ?? items.find((item) => item.status === 'ready') ?? null);
  }, [selected]);
  const refreshConversations = useCallback(async () => {
    if (!selected) return;
    const data = await api(`/conversations?workspace_id=${encodeURIComponent(selected.id)}`);
    if (!Array.isArray(data)) throw new Error('Lịch sử chưa đúng định dạng.');
    setConversations(data.map(conversation));
  }, [selected]);
  useEffect(() => { void Promise.all([refreshDatasets(), refreshConversations()]).catch((e: unknown) => setLocalError(message(e))); }, [refreshDatasets, refreshConversations]);
  useEffect(() => {
    let active = true;
    api('/health').then((data) => { if (active) setHealth(record(data) && data.status === 'ok' ? 'Hệ thống sẵn sàng' : 'Chưa kết nối hệ thống'); }).catch(() => { if (active) setHealth('Chưa kết nối hệ thống'); });
    api('/profile').then((data) => {
      if (active && record(data) && typeof data.display_name === 'string' && typeof data.phone === 'string' && typeof data.interests === 'string') {
        setProfile({ display_name: data.display_name, phone: data.phone, interests: data.interests }); setSavedName(data.display_name);
      }
    }).catch((e: unknown) => { if (active) setLocalError(message(e)); });
    return () => { active = false; };
  }, []);
  useEffect(() => { if (dataOpen && uploadFocus) document.querySelector<HTMLDialogElement>('dialog[open]')?.querySelector<HTMLInputElement>('input[type=file]')?.focus(); }, [dataOpen, uploadFocus]);
  async function mutate(work: () => Promise<void>) {
    if (mutation.current || unavailable) return;
    mutation.current = true; setMutating(true); setLocalError(''); setNotice('');
    try { await work(); } catch (e: unknown) { setLocalError(message(e)); }
    finally { mutation.current = false; setMutating(false); }
  }
  function selectChat(item: Conversation) {
    setConversationId(item.id); setMobileOpen(false);
    const source = datasets.find((d) => d.revision_id === item.revision_id);
    if (source) setScope(source);
  }
  function manage(upload = false) { setUploadFocus(upload); setDataOpen(true); setMobileOpen(false); }
  function closeData() { if (!dataBusy) { setDataOpen(false); void refreshDatasets().catch((e: unknown) => setLocalError(message(e))); } }
  const groups = historyGroups(conversations.filter((item) => item.title.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi'))));
  return <div className={`shell ${collapsed ? 'sidebar-collapsed' : ''} ${mobileOpen ? 'menu-open' : ''}`}>
    <aside className="sidebar" aria-label="Điều hướng chính">
      <div className="brand">ChatSAR<button className="quiet collapse-button" aria-label="Thu gọn điều hướng" onClick={() => { setCollapsed(true); setMobileOpen(false); }}>◧</button></div>
      <div className="new-chat-row"><button className="new-chat" disabled={!selected || unavailable} onClick={() => { setConversationId(''); setMobileOpen(false); }}>＋ Đoạn chat mới</button>
        <Menu label="Tùy chọn lịch sử" disabled={unavailable} items={[
          { label: hidden ? 'Hiện tất cả đoạn chat' : 'Ẩn tất cả đoạn chat', action: () => setHidden(!hidden) },
          { label: 'Xóa tất cả đoạn chat', danger: true, action: () => setAction({ kind: 'bulk' }) },
        ]} /></div>
      <label className="search"><span className="sr-only">Tìm đoạn chat</span><input type="search" value={search} placeholder="Tìm đoạn chat…" onChange={(e) => setSearch(e.target.value)} /></label>
      <nav className="history" aria-label="Lịch sử cuộc trò chuyện">
        {hidden ? <button className="quiet" onClick={() => setHidden(false)}>Hiện tất cả đoạn chat</button> : <>
          {!groups.length && <p className="muted">Chưa có đoạn chat.</p>}
          {groups.map((group) => <details className="history-group" key={group.key} open><summary title={group.label}>{group.label}</summary>
            {group.items.map((item) => <div key={item.id} className={`history-row ${conversationId === item.id ? 'active' : ''}`}>
              <button className="quiet chat-title" title={item.title} disabled={unavailable} onClick={() => selectChat(item)}>{item.title}</button>
              <Menu label={`Tùy chọn ${item.title}`} className="chat-menu" disabled={unavailable} items={[
                { label: 'Đổi tên', action: () => { setTitle(item.title); setAction({ kind: 'rename', chat: item }); } },
                { label: 'Xóa đoạn chat', danger: true, action: () => setAction({ kind: 'delete', chat: item }) },
              ]} />
            </div>)}
          </details>)}
        </>}
      </nav>
      <label className="workspace-switch">Không gian làm việc<select value={selected?.id ?? ''} disabled={unavailable} onChange={(e) => {
        const item = workspaces.find((w) => w.id === e.target.value); if (item) onSelect(item);
      }}>{!selected && <option value="">Chưa có không gian</option>}{workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
      <div className="account"><Menu label="Tài khoản ChatSAR" text={savedName} className="account-menu" disabled={unavailable} items={[
        { label: 'Hồ sơ ChatSAR', action: () => { setDraftProfile(profile); setLocalError(''); setProfileOpen(true); } },
        { label: 'Đăng xuất', action: () => void onLogout() },
      ]} /></div>
    </aside>
    <main className="workspace-main">
      <header className="workspace-header"><button className="quiet open-sidebar" aria-label="Mở điều hướng" onClick={() => { setCollapsed(false); setMobileOpen(true); }}>☰</button>
        <strong>{conversations.find((c) => c.id === conversationId)?.title ?? 'Đoạn chat mới'}</strong>
        <label className="source-select"><span className="sr-only">Nguồn dữ liệu</span><select aria-label="Nguồn dữ liệu" value={scope?.revision_id ?? ''} disabled={unavailable} onChange={(e) => setScope(datasets.find((d) => d.revision_id === e.target.value) ?? null)}>
          <option value="">Chọn dữ liệu</option>{datasets.filter((d) => d.status === 'ready').map((d) => <option key={d.revision_id} value={d.revision_id}>{d.name}</option>)}</select></label>
        <span className="health" role="status">{health}</span></header>
      {(error || localError) && <p className="error" role="alert">{error || localError}</p>}
      {notice && <p className="status-notice" role="status">{notice}</p>}
      {selected ? <Chat workspaceId={selected.id} csrf={me.csrf_token} scope={scope} selected={conversationId} onSelect={setConversationId}
        onRefresh={refreshConversations} onBusy={setPending} onManageData={manage} onCreateWorkspace={() => setCreateOpen(true)} />
        : <div className="empty-chat"><h1>Bắt đầu với ChatSAR</h1><button onClick={() => setCreateOpen(true)}>Tạo không gian làm việc</button></div>}
    </main>
    <Modal open={dataOpen} title="Quản lý dữ liệu" onClose={closeData} closeDisabled={dataBusy} wide>
      {selected && <Datasets workspaceId={selected.id} csrf={me.csrf_token} onBusy={setDataBusy} onReady={(dataset) => { setScope(dataset); void refreshDatasets().catch((e: unknown) => setLocalError(message(e))); }} />}
    </Modal>
    <Modal open={createOpen} title="Tạo không gian làm việc" error={localError || error} closeDisabled={mutating} onClose={() => { if (!mutating) setCreateOpen(false); }}>
      <form className="dialog-body" onSubmit={(e) => { e.preventDefault(); void mutate(async () => { await onCreate(name.trim()); setName(''); setCreateOpen(false); }); }}>
        <label>Tên không gian<input autoFocus value={name} required maxLength={120} onChange={(e) => setName(e.target.value)} /></label>
        <div className="dialog-actions"><button type="button" className="secondary" disabled={mutating} onClick={() => setCreateOpen(false)}>Hủy</button><button disabled={mutating || !name.trim()}>Tạo</button></div>
      </form>
    </Modal>
    <Modal open={action !== null} error={localError} closeDisabled={mutating} title={action?.kind === 'rename' ? 'Đổi tên đoạn chat' : action?.kind === 'bulk' ? 'Xóa tất cả đoạn chat?' : 'Xóa đoạn chat?'} onClose={() => { if (!mutating) setAction(null); }}>
      <form className="dialog-body" onSubmit={(e) => { e.preventDefault(); void mutate(async () => {
        if (!action || !selected) return;
        if (action.kind === 'rename') {
          await api(`/conversations/${action.chat.id}`, { method: 'PATCH', body: JSON.stringify({ title: title.trim() }) }, me.csrf_token);
          setConversations((items) => items.map((item) => item.id === action.chat.id ? { ...item, title: title.trim() } : item));
        } else {
          const ids = action.kind === 'bulk' ? conversations.map((item) => item.id) : [action.chat.id];
          await api(action.kind === 'bulk' ? `/workspaces/${selected.id}/conversations` : `/conversations/${action.chat.id}`, { method: 'DELETE' }, me.csrf_token);
          setConversations((items) => items.filter((item) => !ids.includes(item.id)));
          if (ids.includes(conversationId)) setConversationId('');
        }
        setAction(null); setNotice('Đã cập nhật lịch sử.');
      }); }}>
        {action?.kind === 'rename' ? <label>Tên đoạn chat<input autoFocus value={title} required maxLength={120} onChange={(e) => setTitle(e.target.value)} /></label>
          : <p>{action?.kind === 'bulk' ? `Xóa toàn bộ đoạn chat và kết quả trong không gian “${selected?.name}”.` : `Xóa “${action?.kind === 'delete' ? action.chat.title : ''}” và kết quả của đoạn chat này.`} Dữ liệu nguồn và không gian làm việc được giữ lại.</p>}
        <div className="dialog-actions"><button type="button" className="secondary" disabled={mutating} onClick={() => setAction(null)}>Hủy</button>
          <button className={action?.kind === 'rename' ? '' : 'danger-button'} disabled={unavailable || (action?.kind === 'rename' && !title.trim())}>{action?.kind === 'rename' ? 'Lưu' : 'Xác nhận xóa'}</button></div>
      </form>
    </Modal>
    <Modal open={profileOpen} title="Hồ sơ ChatSAR" error={localError} closeDisabled={mutating} onClose={() => { if (!mutating) setProfileOpen(false); }}>
      <form className="dialog-body" onSubmit={(e) => { e.preventDefault(); void mutate(async () => {
        await api('/profile', { method: 'PATCH', body: JSON.stringify(draftProfile) }, me.csrf_token);
        setProfile(draftProfile); setSavedName(draftProfile.display_name.trim()); setProfileOpen(false); setNotice('Đã lưu hồ sơ ChatSAR.');
      }); }}>
        <p className="muted">Chỉ lưu tại ChatSAR; không thay đổi hồ sơ Google.</p>
        <label>Tên hiển thị<input autoFocus value={draftProfile.display_name} required maxLength={200} onChange={(e) => setDraftProfile({ ...draftProfile, display_name: e.target.value })} /></label>
        <label>Số điện thoại (tùy chọn)<input type="tel" value={draftProfile.phone} maxLength={40} onChange={(e) => setDraftProfile({ ...draftProfile, phone: e.target.value })} /></label>
        <label>Sở thích (tùy chọn)<textarea rows={3} value={draftProfile.interests} maxLength={1000} onChange={(e) => setDraftProfile({ ...draftProfile, interests: e.target.value })} /></label>
        <div className="dialog-actions"><button type="button" className="secondary" disabled={mutating} onClick={() => setProfileOpen(false)}>Hủy</button><button disabled={mutating || !draftProfile.display_name.trim()}>Lưu hồ sơ</button></div>
      </form>
    </Modal>
  </div>;
}
function message(error: unknown): string { return error instanceof Error ? error.message : 'Chưa thể xử lý yêu cầu.'; }
