import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Connection = 'checking' | 'available' | 'unavailable';

function App() {
  const [connection, setConnection] = useState<Connection>('checking');
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/health', { signal: controller.signal })
      .then(async (response) => {
        const body: unknown = await response.json();
        const ready = response.ok && typeof body === 'object' && body !== null
          && 'status' in body && body.status === 'ok';
        setConnection(ready ? 'available' : 'unavailable');
      })
      .catch(() => {
        if (!controller.signal.aborted) setConnection('unavailable');
      });
    return () => controller.abort();
  }, []);

  const connectionText = {
    checking: 'Đang kiểm tra kết nối…',
    available: 'Kết nối hệ thống sẵn sàng',
    unavailable: 'Chưa kết nối được hệ thống',
  }[connection];

  return (
    <div className="shell">
      <aside>
        <a className="brand" href="/" aria-label="ChatSAR trang chủ">
          <span className="brand-mark">C</span> ChatSAR
        </a>
        <p className="aside-note">Dữ liệu rõ ràng.<br />Câu trả lời có căn cứ.</p>
        <div className="connection" role="status" aria-live="polite">
          <span className={`dot ${connection}`} />{connectionText}
        </div>
      </aside>
      <main>
        <div className="eyebrow">KHÔNG GIAN DỮ LIỆU CỦA BẠN</div>
        <h1>Hỏi dữ liệu.<br /><span>Hiểu có căn cứ.</span></h1>
        <p className="intro">ChatSAR đang được chuẩn bị để giúp bạn tìm câu trả lời
          từ bảng dữ liệu, kiểm tra nguồn và hiểu cách tính bằng tiếng Việt.</p>
        <section className="notice" aria-labelledby="preparation-title">
          <div className="notice-icon" aria-hidden="true">↗</div>
          <div>
            <h2 id="preparation-title">Đang chuẩn bị không gian làm việc</h2>
            <p>Đăng nhập và tải dữ liệu sẽ khả dụng sau khi hoàn tất thiết lập.
              Chưa có dữ liệu nào được tải lên từ trang này.</p>
          </div>
        </section>
        <div className="principles">
          <div><span>01</span><h3>Hỏi bằng tiếng Việt</h3><p>Bắt đầu từ câu hỏi bạn cần giải đáp.</p></div>
          <div><span>02</span><h3>Kiểm tra nguồn</h3><p>Biết số liệu đến từ đâu và cách tính.</p></div>
          <div><span>03</span><h3>Giữ đúng ngữ cảnh</h3><p>Phân biệt thông tin đã có và điều còn thiếu.</p></div>
        </div>
        <footer>ChatSAR · Bản đang phát triển</footer>
      </main>
    </div>
  );
}

const root = document.getElementById('root');
if (!root) throw new Error('Không tìm thấy phần tử gốc của ứng dụng.');
createRoot(root).render(<App />);
