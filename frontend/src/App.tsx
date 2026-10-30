import { useCallback, useEffect, useState } from 'react';
import { api, endGuestSession, identity, activateGuestSession, workspaceList } from './api';
import type { Identity, Workspace } from './api';
import Authentication from './Authentication';
import WorkspaceView from './Workspace';

export default function App() {
  const [me, setMe] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loginOpen, setLoginOpen] = useState(window.location.pathname === '/login');
  async function beginGuest() {
    return activateGuestSession(await api('/auth/guest', { method: 'POST', body: '{}' }));
  }
  const navigate = useCallback((login: boolean) => {
    window.history.pushState(null, '', login ? '/login' : '/'); setLoginOpen(login); setError('');
  }, []);
  useEffect(() => {
    let active = true;
    api('/me').then(identity).catch(beginGuest).then((who) => { if (active) setMe(who); })
      .catch((e: unknown) => { if (active) setError(message(e)); })
      .finally(() => { if (active) setLoading(false); });
    const leave = () => { void endGuestSession(); };
    const back = () => setLoginOpen(window.location.pathname === '/login');
    const restore = (event: PageTransitionEvent) => { if (event.persisted) window.location.reload(); };
    window.addEventListener('pagehide', leave); window.addEventListener('popstate', back);
    window.addEventListener('pageshow', restore);
    return () => { active = false; window.removeEventListener('pagehide', leave); window.removeEventListener('popstate', back); window.removeEventListener('pageshow', restore); };
  }, []);
  useEffect(() => {
    if (!me) { setWorkspaces([]); setSelected(null); return; }
    let active = true;
    api('/workspaces').then((data) => {
      if (!active) return;
      const items = workspaceList(data); setWorkspaces(items); setSelected(items[0] ?? null);
    }).catch((e: unknown) => { if (active) setError(message(e)); });
    return () => { active = false; };
  }, [me]);
  async function createWorkspace(name: string) {
    if (!me || busy) return;
    setBusy(true); setError('');
    try {
      const data = await api('/workspaces', { method: 'POST', body: JSON.stringify({ name }) }, me.csrf_token);
      const created = workspaceList([data])[0];
      setWorkspaces((items) => [...items, created]); setSelected(created);
    } catch (e: unknown) { setError(message(e)); throw e; }
    finally { setBusy(false); }
  }
  async function logout() {
    if (!me || busy) return;
    setBusy(true); setError('');
    try {
      await api('/auth/logout', { method: 'POST' }, me.csrf_token);
      window.google?.accounts.id.disableAutoSelect();
      setWorkspaces([]); setSelected(null); setMe(null);
      setMe(await beginGuest()); navigate(false);
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }
  const signedIn = useCallback((who: Identity) => {
    // Theo lựa chọn của chủ dự án: mở dữ liệu tài khoản, không nhập phiên khách.
    void endGuestSession(); setWorkspaces([]); setSelected(null); setMe(who); navigate(false);
  }, [navigate]);
  if (loading) return <main className="login"><p role="status">Đang mở không gian dữ liệu…</p></main>;
  if (loginOpen) return <Authentication onLogin={signedIn} onBack={() => navigate(false)} />;
  if (!me) return <main className="login"><p className="error" role="alert">{error || 'Chưa mở được phiên khách.'}</p><button onClick={() => window.location.reload()}>Thử lại</button></main>;
  return <WorkspaceView key={`${me.id}:${selected?.id ?? 'empty'}`} me={me} workspaces={workspaces}
    selected={selected} onSelect={setSelected} onCreate={createWorkspace}
    onLogout={logout} onLogin={() => navigate(true)} busy={busy} error={error} />;
}
function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Chưa thể xử lý yêu cầu. Vui lòng thử lại.';
}
