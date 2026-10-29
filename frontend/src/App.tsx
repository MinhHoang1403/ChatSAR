import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api, identity, record, workspaceList } from './api';
import type { Identity, Workspace } from './api';
import Datasets from './Datasets';

export default function App() {
  const [me, setMe] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [googleReady, setGoogleReady] = useState<boolean | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const googleButton = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api('/me').then((data) => setMe(identity(data))).catch(() => setMe(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!me) { setWorkspaces([]); setSelected(null); return; }
    let active = true;
    api('/workspaces').then((data) => {
      if (active) setWorkspaces(workspaceList(data));
    }).catch((e: unknown) => { if (active) setError(message(e)); });
    return () => { active = false; };
  }, [me]);

  useEffect(() => {
    if (loading || me) return;
    let active = true;
    api('/auth/config').then((config) => {
      if (!record(config) || typeof config.google_client_id !== 'string'
        || typeof config.nonce !== 'string' || typeof config.csrf_token !== 'string') {
        throw new Error('Cấu hình đăng nhập không hợp lệ.');
      }
      const clientId = config.google_client_id;
      const nonce = config.nonce;
      const csrf = config.csrf_token;
      if (!active) return;
      setGoogleReady(Boolean(clientId));
      if (!clientId) return;
      const initialize = () => {
        if (!active || !window.google || !googleButton.current) return;
        window.google.accounts.id.initialize({ client_id: clientId, nonce,
          callback: (response) => {
            setBusy(true); setError('');
            api('/auth/google', { method: 'POST', body: JSON.stringify({
              credential: response.credential, g_csrf_token: csrf,
            }) }).then(() => api('/me')).then((data) => setMe(identity(data)))
              .catch((e: unknown) => setError(message(e))).finally(() => setBusy(false));
          },
        });
        window.google.accounts.id.renderButton(googleButton.current,
          { theme: 'outline', size: 'large', text: 'signin_with' });
      };
      if (window.google) initialize();
      else {
        const script = document.createElement('script');
        script.src = 'https://accounts.google.com/gsi/client'; script.async = true;
        script.onload = initialize;
        script.onerror = () => setError('Không tải được đăng nhập Google. Vui lòng thử lại.');
        document.head.appendChild(script);
      }
    }).catch((e: unknown) => { if (active) setError(message(e)); });
    return () => { active = false; };
  }, [loading, me]);

  async function createWorkspace(event: FormEvent) {
    event.preventDefault();
    if (!me || busy) return;
    setBusy(true); setError('');
    try {
      const data = await api('/workspaces', { method: 'POST', body: JSON.stringify({ name }) }, me.csrf_token);
      const created = workspaceList([data])[0];
      setWorkspaces((items) => [...items, created]); setSelected(created); setName('');
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }

  async function logout() {
    if (!me || busy) return;
    setBusy(true); setError('');
    try {
      await api('/auth/logout', { method: 'POST' }, me.csrf_token);
      window.google?.accounts.id.disableAutoSelect(); setMe(null); setSelected(null);
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }

  return <div className="shell">
    <aside>
      <a className="brand" href="/"><span className="brand-mark">C</span> ChatSAR</a>
      <p className="aside-note">Dữ liệu rõ ràng.<br />Câu trả lời có căn cứ.</p>
      {me && <>
        <div className="workspace-list">{workspaces.map((workspace) => <button key={workspace.id}
          className={selected?.id === workspace.id ? 'selected' : ''}
          onClick={() => { setSelected(workspace); setError(''); }}>{workspace.name}</button>)}</div>
        <div className="account"><span>{me.display_name}</span><button onClick={logout} disabled={busy}>Đăng xuất</button></div>
      </>}
      {!me && <div className="connection">Không gian dữ liệu riêng của bạn</div>}
    </aside>
    <main>
      <div className="eyebrow">KHÔNG GIAN DỮ LIỆU CỦA BẠN</div>
      {error && <div className="error" role="alert">{error}</div>}
      {loading ? <p role="status">Đang kiểm tra phiên đăng nhập…</p> : !me ? <>
        <h1>Hỏi dữ liệu.<br /><span>Hiểu có căn cứ.</span></h1>
        <p className="intro">Đăng nhập để tạo không gian làm việc và quản lý dữ liệu của riêng bạn.</p>
        <section className="notice"><div>
          <h2>Đăng nhập bằng Google</h2>
          {googleReady === false ? <p>Đăng nhập đang chờ hoàn tất cấu hình. Chưa có phiên đăng nhập nào được tạo.</p>
            : googleReady === null ? <p>Đang kiểm tra cấu hình đăng nhập…</p> : null}
          <div ref={googleButton} hidden={!googleReady} />
        </div></section>
      </> : <>
        <h1 className="workspace-title">{selected?.name ?? 'Không gian làm việc'}</h1>
        <p className="intro">{selected ? 'Dữ liệu và các cuộc trò chuyện chỉ thuộc không gian đang chọn.'
          : 'Chọn một không gian ở bên trái hoặc tạo không gian mới để bắt đầu.'}</p>
        <form className="workspace-form" onSubmit={createWorkspace}>
          <label htmlFor="workspace-name">Tạo không gian làm việc</label>
          <div><input id="workspace-name" value={name} maxLength={120} required
            placeholder="Ví dụ: Báo cáo vận hành" onChange={(event) => setName(event.target.value)} />
            <button disabled={busy || !name.trim()}>Tạo mới</button></div>
        </form>
        {!workspaces.length && <p>Chưa có không gian làm việc. Hãy tạo không gian đầu tiên.</p>}
        {selected && <Datasets key={selected.id} workspaceId={selected.id} csrf={me.csrf_token} />}
      </>}
      <footer>ChatSAR · Dữ liệu có nguồn, câu trả lời có căn cứ</footer>
    </main>
  </div>;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Chưa thể xử lý yêu cầu. Vui lòng thử lại.';
}
