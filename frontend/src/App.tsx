import { useEffect, useState } from 'react';
import { api, identity, workspaceList } from './api';
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
  useEffect(() => {
    api('/me').then((data) => setMe(identity(data))).catch(() => setMe(null))
      .finally(() => setLoading(false));
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
      window.google?.accounts.id.disableAutoSelect(); setMe(null);
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }
  if (loading) return <main className="login"><p role="status">Đang mở không gian dữ liệu…</p></main>;
  if (!me) return <Authentication onLogin={setMe} />;
  return <WorkspaceView key={selected?.id ?? 'empty'} me={me} workspaces={workspaces}
    selected={selected} onSelect={setSelected} onCreate={createWorkspace}
    onLogout={logout} busy={busy} error={error} />;
}
function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Chưa thể xử lý yêu cầu. Vui lòng thử lại.';
}
