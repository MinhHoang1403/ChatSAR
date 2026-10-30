import { useEffect, useRef, useState } from 'react';
import { api, identity, record } from './api';
import type { Identity } from './api';

export default function Authentication({ onLogin }: { onLogin: (me: Identity) => void }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [googleReady, setGoogleReady] = useState<boolean | null>(null);
  const googleButton = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    api('/auth/config').then((config) => {
      if (!record(config) || typeof config.google_client_id !== 'string'
        || typeof config.app_origin !== 'string'
        || typeof config.nonce !== 'string' || typeof config.csrf_token !== 'string') {
        throw new Error('Cấu hình đăng nhập không hợp lệ.');
      }
      const clientId = config.google_client_id;
      const nonce = config.nonce;
      const csrf = config.csrf_token;
      if (!active) return;
      if (window.location.origin !== config.app_origin) {
        window.location.replace(config.app_origin);
        return;
      }
      setGoogleReady(Boolean(clientId));
      if (!clientId) return;
      const initialize = () => {
        if (!active || !window.google || !googleButton.current) return;
        window.google.accounts.id.initialize({ client_id: clientId, nonce,
          callback: (response) => {
            setBusy(true); setError('');
            api('/auth/google', { method: 'POST', body: JSON.stringify({
              credential: response.credential, g_csrf_token: csrf,
            }) }).then(() => api('/me')).then((data) => onLogin(identity(data)))
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
  }, [onLogin]);


  return <main className="login"><div className="login-card">
    <div className="brand">ChatSAR</div>
    <h1>Không gian dữ liệu của bạn</h1>
    <p>Đặt câu hỏi, xem số liệu và kiểm tra nguồn trong cùng một nơi.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {googleReady === false && <p>Đăng nhập đang chờ hoàn tất cấu hình.</p>}
    {googleReady === null && <p role="status">Đang chuẩn bị đăng nhập…</p>}
    {busy && <p role="status">Đang xác minh tài khoản…</p>}
    <div ref={googleButton} hidden={!googleReady} />
    <p className="muted">Dữ liệu và lịch sử thuộc tài khoản của bạn.</p>
  </div></main>;
}
function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Chưa thể đăng nhập. Vui lòng thử lại.';
}
