import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { api, record } from './api';

type Kind = 'text' | 'integer' | 'numeric' | 'boolean' | 'date' | 'timestamp';
type Column = {
  id: string; name: string; data_type: Kind; nullable: boolean; primary_key: boolean;
  null_values: string[]; date_format: string; decimal_separator: string; unit: string | null;
  null_count?: number; empty_count?: number; duplicate_count?: number;
};
export type Dataset = { id: string; name: string; revision_id: string; status: string };
type Preview = { dataset_id: string; revision_id: string; status: string; name: string;
  sheets: string[]; sheet_name: string; columns: Column[]; rows: unknown[][]; row_count: number };
const kinds: Kind[] = ['text', 'integer', 'numeric', 'boolean', 'date', 'timestamp'];

function parsePreview(data: unknown): Preview {
  if (!record(data) || typeof data.dataset_id !== 'string' || typeof data.revision_id !== 'string'
    || typeof data.status !== 'string' || typeof data.name !== 'string' || !Array.isArray(data.sheets)
    || !data.sheets.every((v: unknown) => typeof v === 'string') || typeof data.sheet_name !== 'string'
    || !Array.isArray(data.columns) || !Array.isArray(data.rows) || !data.rows.every(Array.isArray)
    || typeof data.row_count !== 'number') throw new Error('Preview chưa đúng định dạng.');
  const columns = data.columns.map((value: unknown): Column => {
    if (!record(value) || typeof value.id !== 'string' || typeof value.name !== 'string'
      || !kinds.includes(value.data_type as Kind) || typeof value.nullable !== 'boolean') {
      throw new Error('Thông tin cột chưa đúng định dạng.');
    }
    return { id: value.id, name: value.name, data_type: value.data_type as Kind,
      nullable: value.nullable, primary_key: value.primary_key === true,
      null_values: Array.isArray(value.null_values) ? value.null_values.filter((v): v is string => typeof v === 'string') : [],
      date_format: typeof value.date_format === 'string' ? value.date_format : '%Y-%m-%d',
      decimal_separator: value.decimal_separator === ',' ? ',' : '.',
      unit: typeof value.unit === 'string' ? value.unit : null,
      null_count: typeof value.null_count === 'number' ? value.null_count : undefined,
      empty_count: typeof value.empty_count === 'number' ? value.empty_count : undefined,
      duplicate_count: typeof value.duplicate_count === 'number' ? value.duplicate_count : undefined };
  });
  return { dataset_id: data.dataset_id, revision_id: data.revision_id, status: data.status,
    name: data.name, sheets: data.sheets as string[], sheet_name: data.sheet_name,
    columns, rows: data.rows as unknown[][], row_count: data.row_count };
}

export default function Datasets({ workspaceId, csrf, onReady }: {
  workspaceId: string; csrf: string; onReady?: (dataset: Dataset) => void;
}) {
  const [list, setList] = useState<Dataset[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [grain, setGrain] = useState('Một dòng dữ liệu');
  const [timezone, setTimezone] = useState('Asia/Ho_Chi_Minh');
  const [synthetic, setSynthetic] = useState(false);

  async function refresh() {
    const data = await api(`/workspaces/${workspaceId}/datasets`);
    if (!Array.isArray(data)) throw new Error('Danh sách dữ liệu chưa đúng định dạng.');
    setList(data.map((value: unknown) => {
      if (!record(value) || typeof value.id !== 'string' || typeof value.name !== 'string'
        || typeof value.revision_id !== 'string' || typeof value.status !== 'string') {
        throw new Error('Thông tin dữ liệu chưa đúng định dạng.');
      }
      return { id: value.id, name: value.name, revision_id: value.revision_id, status: value.status };
    }));
  }

  useEffect(() => {
    refresh().catch((e: unknown) => setError(message(e)));
  }, [workspaceId]);

  async function open(datasetId: string, sheet?: string) {
    setBusy(true); setError('');
    try {
      const query = sheet ? `?sheet_name=${encodeURIComponent(sheet)}` : '';
      const result = parsePreview(await api(`/datasets/${datasetId}/preview${query}`));
      setPreview(result);
      if (result.status === 'ready') onReady?.({ id: result.dataset_id, name: result.name,
        revision_id: result.revision_id, status: 'ready' });
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError('');
    try {
      const body = new FormData(); body.append('file', file);
      const result = await api(`/workspaces/${workspaceId}/datasets`, { method: 'POST', body }, csrf);
      if (!record(result) || typeof result.dataset_id !== 'string') throw new Error('Upload chưa trả về dữ liệu hợp lệ.');
      await refresh(); await open(result.dataset_id);
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }

  function edit(index: number, change: Partial<Column>) {
    setPreview((old) => old ? { ...old, columns: old.columns.map((column, i) =>
      i === index ? { ...column, ...change } : column) } : old);
  }

  async function publish() {
    if (!preview || busy) return;
    setBusy(true); setError('');
    try {
      const columns = preview.columns.map((column) => ({ id: column.id, name: column.name,
        data_type: column.data_type, nullable: column.nullable, primary_key: column.primary_key,
        null_values: column.null_values, date_format: column.date_format,
        decimal_separator: column.decimal_separator, unit: column.unit }));
      await api(`/datasets/${preview.dataset_id}/confirm`, { method: 'POST', body: JSON.stringify({
        revision_id: preview.revision_id, columns, sheet_name: preview.sheet_name || null,
        timezone, grain, data_classification: synthetic ? 'synthetic' : 'private',
      }) }, csrf);
      await refresh(); await open(preview.dataset_id);
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }

  return <section className="dataset-panel">
    <h2>Dữ liệu trong không gian làm việc</h2>
    <form onSubmit={upload} className="upload-form">
      <label>Chọn CSV hoặc XLSX (tối đa 20 MiB)<input type="file" accept=".csv,.xlsx"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
      <button disabled={busy || !file}>Tải lên và xem trước</button>
    </form>
    {error && <p role="alert" className="error">{error}</p>}
    {busy && <p role="status">Đang xử lý yêu cầu…</p>}
    {!list.length && <p>Chưa có bảng dữ liệu. File tải lên được lưu riêng trong không gian này.</p>}
    <div className="dataset-list">{list.map((dataset) => <button key={dataset.id}
      onClick={() => open(dataset.id)} disabled={busy}>{dataset.name} · {dataset.status === 'ready'
        ? 'Sẵn sàng' : dataset.status === 'failed' ? 'Cần kiểm tra' : 'Chờ xác nhận'}</button>)}</div>
    {preview && <div className="review">
      <h3>{preview.name} · {preview.row_count} dòng</h3>
      {preview.sheets.length > 0 && <label>Sheet: <select value={preview.sheet_name} disabled={busy || preview.status === 'ready'}
        onChange={(event) => open(preview.dataset_id, event.target.value)}>
        <option value="" disabled>Chọn sheet để xem trước</option>
        {preview.sheets.map((sheet) => <option key={sheet}>{sheet}</option>)}</select></label>}
      {preview.columns.length > 0 && <>
        <p>Kiểu tự nhận diện chỉ là đề xuất. Hãy kiểm tra khóa, NULL và kiểu trước khi công bố.</p>
        <div className="table-scroll"><table><thead><tr><th>Cột</th><th>Kiểu</th><th>Cho phép NULL</th>
          <th>Ô trống → NULL</th><th>Khóa</th><th>Đơn vị</th><th>Kiểm kê</th></tr></thead>
          <tbody>{preview.columns.map((column, index) => <tr key={column.id}>
            <td><input aria-label={`Tên cột ${index + 1}`} value={column.name}
              disabled={preview.status === 'ready'} onChange={(event) => edit(index, { name: event.target.value })} /></td>
            <td><select value={column.data_type} disabled={preview.status === 'ready'}
              onChange={(event) => edit(index, { data_type: event.target.value as Kind })}>
              {kinds.map((kind) => <option key={kind}>{kind}</option>)}</select>
              {column.data_type === 'date' && <select value={column.date_format} disabled={preview.status === 'ready'}
                onChange={(event) => edit(index, { date_format: event.target.value })}>
                <option>%Y-%m-%d</option><option>%d/%m/%Y</option><option>%m/%d/%Y</option></select>}
              {column.data_type === 'numeric' && <select value={column.decimal_separator} disabled={preview.status === 'ready'}
                onChange={(event) => edit(index, { decimal_separator: event.target.value })}>
                <option value=".">Thập phân: dấu chấm</option><option value=",">Thập phân: dấu phẩy</option></select>}</td>
            <td><input type="checkbox" checked={column.nullable} disabled={preview.status === 'ready'}
              onChange={(event) => edit(index, { nullable: event.target.checked })} /></td>
            <td><input type="checkbox" checked={column.null_values.includes('')} disabled={preview.status === 'ready'}
              onChange={(event) => edit(index, { null_values: event.target.checked ? [''] : [] })} /></td>
            <td><input type="checkbox" checked={column.primary_key} disabled={preview.status === 'ready'}
              onChange={(event) => edit(index, { primary_key: event.target.checked })} /></td>
            <td><input value={column.unit ?? ''} disabled={preview.status === 'ready'}
              onChange={(event) => edit(index, { unit: event.target.value || null })} /></td>
            <td>{column.null_count ?? '—'} NULL / {column.empty_count ?? '—'} trống / {column.duplicate_count ?? '—'} trùng</td>
          </tr>)}</tbody></table></div>
        <div className="table-scroll"><table><thead><tr>{preview.columns.map((c) => <th key={c.id}>{c.name}</th>)}</tr></thead>
          <tbody>{preview.rows.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j}>{display(value)}</td>)}</tr>)}</tbody></table></div>
        {preview.status !== 'ready' ? <div className="publish-fields">
          <label>Một dòng đại diện cho <input value={grain} onChange={(event) => setGrain(event.target.value)} /></label>
          <label>Múi giờ <input value={timezone} onChange={(event) => setTimezone(event.target.value)} /></label>
          <label><input type="checkbox" checked={synthetic} onChange={(event) => setSynthetic(event.target.checked)} />
            Đây là dữ liệu tổng hợp, được phép dùng trong kiểm thử AI có giới hạn</label>
          <p>Chưa có quan hệ bảng được xác nhận. Truy vấn hiện áp dụng một bảng.</p>
          <button disabled={busy || !grain.trim()} onClick={publish}>Xác nhận và công bố</button>
        </div> : <p role="status">Đã công bố revision; dữ liệu sẵn sàng và không sửa ngầm.</p>}
      </>}
    </div>}
  </section>;
}

function message(error: unknown): string { return error instanceof Error ? error.message : 'Chưa thể xử lý yêu cầu.'; }
function display(value: unknown): string {
  if (value === null) return 'NULL';
  if (value === '') return '“”';
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : '—';
}
