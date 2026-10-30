import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { api, record } from './api';
import AIReview from './AIReview';

import { datasetList, parsePreview, kinds, kindNames } from './data';
import type { Column, Dataset, Preview, Kind } from './data';
export { datasetList } from './data';
export type { Column, Dataset, Preview } from './data';

export default function Datasets({ workspaceId, csrf, onReady, onBusy }: {
  workspaceId: string; csrf: string; onReady?: (dataset: Dataset) => void; onBusy?: (busy: boolean) => void;
}) {
  const [list, setList] = useState<Dataset[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [grain, setGrain] = useState('Một dòng dữ liệu');
  const [timezone, setTimezone] = useState('Asia/Ho_Chi_Minh');
  const [synthetic, setSynthetic] = useState(false);
  const [description, setDescription] = useState('');
  const [sharing, setSharing] = useState<string[]>([]);
  const [mappingDraft, setMappingDraft] = useState<Record<string, string>>({});
  useEffect(() => { onBusy?.(busy); }, [busy, onBusy]);

  async function refresh() {
    const data = await api(`/workspaces/${workspaceId}/datasets`);
    setList(datasetList(data));
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
      setMappingDraft({});
      setDescription(result.description); setGrain(result.grain || 'Một dòng dữ liệu');
      setTimezone(result.timezone); setSharing(result.sharing_providers); setSynthetic(result.data_classification === 'synthetic');
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
        decimal_separator: column.decimal_separator, unit: column.unit,
        description: column.description ?? '', aliases: column.aliases ?? [], role: column.role ?? 'other',
        value_mappings: mappingDraft[column.id] === undefined ? column.value_mappings ?? [] : parseMappings(mappingDraft[column.id]), aggregation_policy: column.aggregation_policy ?? 'unspecified' }));
      await api(`/datasets/${preview.dataset_id}/confirm`, { method: 'POST', body: JSON.stringify({
        revision_id: preview.revision_id, columns, sheet_name: preview.sheet_name || null,
        timezone, grain, description, sharing_providers: sharing, data_classification: synthetic ? 'synthetic' : 'private',
      }) }, csrf);
      await refresh(); await open(preview.dataset_id);
    } catch (e: unknown) { setError(message(e)); }
    finally { setBusy(false); }
  }

  return <section className="dataset-panel">
    <ol className="setup-steps"><li>1. Tải file</li><li>2. Kiểm tra đề xuất</li><li>3. Xác nhận và sử dụng</li></ol>
    <form onSubmit={upload} className="upload-form">
      <label>Chọn CSV hoặc XLSX (tối đa 20 MiB)<input type="file" accept=".csv,.xlsx"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
      {file && <p>{file.name} · {(file.size / 1024).toFixed(1)} KB</p>}
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
        {preview.status !== 'ready' && <AIReview key={`${preview.revision_id}:${preview.sheet_name}`} preview={preview} csrf={csrf}
          onBusy={setBusy} onProposal={(columns, desc, rowMeaning) => { setPreview((old) => old ? { ...old, columns } : old); setMappingDraft({}); setDescription(desc); setGrain(rowMeaning); }} />}
        <div className="review-summary"><strong>{preview.row_count} dòng · {preview.columns.length} cột</strong><span>File nguồn được giữ nguyên</span></div>
        <div className="column-summary">{preview.columns.map((column) => <div key={column.id}><strong>{column.name}</strong><span>{kindNames[column.data_type]}{column.unit ? ` · ${column.unit}` : ''}</span>
          <small>{(column.null_count ?? 0) + (column.empty_count ?? 0) > 0 ? 'Có ô trống, cần kiểm tra cách xử lý' : 'Đã nhận diện kiểu dữ liệu'}{column.primary_key ? ' · Mã duy nhất được đề xuất' : ''}</small></div>)}</div>
        <details className="advanced"><summary>Chỉnh sửa chi tiết</summary>
        <label>Mô tả dữ liệu<input value={description} disabled={preview.status === 'ready'} maxLength={1000} onChange={(e) => setDescription(e.target.value)} /></label>
        <div className="table-scroll"><table><thead><tr><th>Cột</th><th>Kiểu</th><th>Cho phép NULL</th>
          <th>Ô trống → NULL</th><th>Khóa</th><th>Đơn vị</th><th>Kiểm kê</th></tr></thead>
          <tbody>{preview.columns.map((column, index) => <tr key={column.id}>
            <td><input aria-label={`Tên cột ${index + 1}`} value={column.name}
              disabled={preview.status === 'ready'} onChange={(event) => edit(index, { name: event.target.value })} /></td>
            <td><select value={column.data_type} disabled={preview.status === 'ready'}
              onChange={(event) => edit(index, { data_type: event.target.value as Kind })}>
              {kinds.map((kind) => <option key={kind} value={kind}>{kindNames[kind]}</option>)}</select>
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
        {preview.columns.map((column, index) => <fieldset key={column.id}><legend>{column.name}</legend>
          <label>Ý nghĩa cột<input value={column.description ?? ''} maxLength={500} disabled={preview.status === 'ready'} onChange={(e) => edit(index, { description: e.target.value })} /></label>
          <label>Tên gọi tương đương (ngăn bằng dấu phẩy)<input key={`${column.id}:${(column.aliases ?? []).join(',')}`} defaultValue={(column.aliases ?? []).join(', ')} disabled={preview.status === 'ready'} onBlur={(e) => edit(index, { aliases: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} /></label>
          <label>Vai trò<select value={column.role ?? 'other'} disabled={preview.status === 'ready'} onChange={(e) => edit(index, { role: e.target.value })}>
            <option value="other">Chưa xác định</option><option value="identifier">Mã đối tượng</option><option value="status">Trạng thái</option><option value="time">Thời gian</option><option value="amount">Số tiền</option><option value="quantity">Số lượng</option><option value="name">Tên đối tượng</option></select></label>
          <label>Cách tổng hợp<select value={column.aggregation_policy ?? 'unspecified'} disabled={preview.status === 'ready'} onChange={(e) => edit(index, { aggregation_policy: e.target.value })}><option value="unspecified">Chưa có hạn chế được xác nhận</option><option value="additive">Có thể cộng theo mỗi dòng</option><option value="non_additive">Không cộng hoặc lấy trung bình</option></select></label>
          <label>Tên gọi của giá trị (mỗi dòng: cách gọi=giá trị thật)<textarea value={mappingDraft[column.id] ?? (column.value_mappings ?? []).map((m) => `${m.phrase}=${m.value}`).join('\n')} disabled={preview.status === 'ready'}
            onChange={(e) => setMappingDraft((old) => ({ ...old, [column.id]: e.target.value }))} /></label>
        </fieldset>)}
        <label>Mỗi dòng đại diện cho<input value={grain} disabled={preview.status === 'ready'} maxLength={300} onChange={(e) => setGrain(e.target.value)} /></label>
        <label>Múi giờ<input value={timezone} disabled={preview.status === 'ready'} onChange={(e) => setTimezone(e.target.value)} /></label>
        <label className="check"><input type="checkbox" checked={synthetic} disabled={preview.status === 'ready'} onChange={(e) => setSynthetic(e.target.checked)} />Đây thực sự là dữ liệu tổng hợp dùng để kiểm thử AI</label>
        </details>
        <div className="table-scroll"><table><thead><tr>{preview.columns.map((c) => <th key={c.id}>{c.name}</th>)}</tr></thead>
          <tbody>{preview.rows.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j}>{display(value)}</td>)}</tr>)}</tbody></table></div>
        {preview.status !== 'ready' ? <div className="publish-fields">
          <p>Cho phép gửi tên cột, thống kê, một số giá trị giới hạn và câu hỏi tới mô hình để hỏi dữ liệu. File gốc không được gửi.</p>
          {['gemini', 'knowledge'].map((provider) => <label className="check" key={provider}><input type="checkbox" checked={sharing.includes(provider)}
            onChange={(e) => setSharing((old) => e.target.checked ? [...old, provider] : old.filter((p) => p !== provider))} />{provider === 'gemini' ? 'Gemini (Google)' : 'Knowledge (dịch vụ công ty)'}</label>)}
          <p className="muted">Xác nhận nghĩa các cột và cách xử lý ô trống trước khi sử dụng. Bạn có thể giữ dữ liệu riêng tư và chỉ xem trước local.</p>
          <button disabled={busy || !grain.trim()} onClick={publish}>Xác nhận và sử dụng dữ liệu</button>
        </div> : <p role="status" className="success">Dữ liệu đã sẵn sàng. Đóng cửa sổ để bắt đầu hỏi.</p>}
      </>}
    </div>}
  </section>;
}

function message(error: unknown): string { return error instanceof Error ? error.message : 'Chưa thể xử lý yêu cầu.'; }
function parseMappings(text: string): { phrase: string; value: string }[] {
  return text.split('\n').filter((line) => line.trim()).map((line) => {
    const at = line.indexOf('=');
    if (at < 1 || !line.slice(0, at).trim()) throw new Error('Tên gọi giá trị cần đúng dạng: cách gọi=giá trị thật.');
    return { phrase: line.slice(0, at).trim(), value: line.slice(at + 1) };
  });
}
function display(value: unknown): string {
  if (value === null) return 'NULL';
  if (value === '') return '“”';
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : '—';
}
