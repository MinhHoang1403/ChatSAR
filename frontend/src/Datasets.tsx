import { useEffect, useMemo, useRef, useState } from 'react';
import { api, record } from './api';
import AIReview, { analyzeDataset } from './AIReview';
import { datasetList, parsePreview, parseNormalization, datasetModels, kinds, kindNames } from './data';
import type { Column, Dataset, Preview, Kind, Normalization } from './data';
export { datasetList } from './data';
export type { Column, Dataset, Preview } from './data';

export default function Datasets({ workspaceId, csrf, onReady, onSaved, onBusy }: {
  workspaceId: string; csrf: string; onReady?: (dataset: Dataset) => void;
  onSaved?: (dataset: Dataset) => void; onBusy?: (busy: boolean) => void;
}) {
  const [list, setList] = useState<Dataset[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [notes, setNotes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [analysisPending, setAnalysisPending] = useState(false);
  const [canRetry, setCanRetry] = useState(false);
  const [grain, setGrain] = useState('Một dòng dữ liệu');
  const [timezone, setTimezone] = useState('Asia/Ho_Chi_Minh');
  const [description, setDescription] = useState('');
  const [mappingDraft, setMappingDraft] = useState<Record<string, string>>({});
  const [normalized, setNormalized] = useState<Normalization | null>(null);
  const [validationError, setValidationError] = useState('');
  const [validating, setValidating] = useState(false);
  const [validatedDraft, setValidatedDraft] = useState('');
  const sequence = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const uploading = useRef(false);
  const saving = useRef(false);
  const keys = useRef(new Map<string, string>());
  const currentWorkspace = useRef(workspaceId);
  currentWorkspace.current = workspaceId;
  const unavailable = busy || analysisPending;
  useEffect(() => { onBusy?.(unavailable || validating); }, [unavailable, validating, onBusy]);
  useEffect(() => () => { ++sequence.current; onBusy?.(false); }, [onBusy]);

  async function refresh() {
    const ownerWorkspace = workspaceId;
    const data = datasetList(await api(`/workspaces/${ownerWorkspace}/datasets`));
    if (currentWorkspace.current === ownerWorkspace) setList(data);
  }
  useEffect(() => {
    ++sequence.current; setPreview(null); setNormalized(null); setAnalysisPending(false); setError('');
    void refresh().catch((e: unknown) => setError(message(e)));
  }, [workspaceId]);

  async function open(datasetId: string, sheet?: string, force = false) {
    const version = ++sequence.current;
    setBusy(true); setValidating(false); setError(''); setValidationError(''); setNotice('Đang đọc dữ liệu…');
    setNotes([]); setNormalized(null); setValidatedDraft(''); setCanRetry(false); setAnalysisPending(false);
    try {
      const query = sheet ? `?sheet_name=${encodeURIComponent(sheet)}` : '';
      const result = parsePreview(await api(`/datasets/${datasetId}/preview${query}`));
      if (version !== sequence.current) return;
      setPreview(result); setMappingDraft({});
      setDescription(result.description); setGrain(result.grain || 'Một dòng dữ liệu'); setTimezone(result.timezone);
      if (result.status === 'ready') {
        setNotice('');
        setNormalized({ revision_id: result.revision_id, checksum: result.checksum || '',
          sheet_name: result.sheet_name, row_count: result.row_count,
          original_headers: result.original_headers || result.columns.map((c) => c.name),
          original_rows: result.original_rows || result.rows, rows: result.rows });
        onReady?.({ id: result.dataset_id, name: result.name, revision_id: result.revision_id,
          status: 'ready', sharing_providers: result.sharing_providers });
        return;
      }
      if (!result.columns.length) { setNotice('Chọn trang dữ liệu cần phân tích.'); return; }
      const status = record(result.setup_proposal) ? result.setup_proposal.status : null;
      if (status === 'pending') {
        setAnalysisPending(true); setNotice('AI đang phân tích bộ dữ liệu. Kết quả sẽ tự cập nhật.'); return;
      }
      const keyId = `${result.revision_id}:${result.sheet_name}`;
      if (force || !keys.current.has(keyId)) keys.current.set(keyId, crypto.randomUUID());
      setNotice('AI đang nhận diện ý nghĩa cột và gợi ý chuẩn hoá…');
      const prepared = await analyzeDataset(result, csrf, keys.current.get(keyId)!,
        { force, localOnly: status === 'interrupted' && !force });
      if (version !== sequence.current) return;
      setPreview({ ...result, columns: prepared.columns });
      setDescription(prepared.description); setGrain(prepared.grain); setNotes(prepared.notes);
      setNotice(prepared.mode === 'ai_proposal'
        ? 'AI đã gợi ý chuẩn hoá. Xem hai bảng bên dưới trước khi lưu.'
        : 'AI chưa khả dụng. Bản gợi ý hiện được nhận diện từ file; bạn vẫn có thể kiểm tra và lưu.');
      setCanRetry(status === 'interrupted' || ['PROVIDER_TEMPORARY', 'PROVIDER_TIMEOUT', 'PROVIDER_NETWORK'].includes(prepared.error_code || ''));
    } catch (e: unknown) {
      if (version === sequence.current) { setError(message(e)); setNotice(''); setCanRetry(true); }
    } finally { if (version === sequence.current) setBusy(false); }
  }

  useEffect(() => {
    if (!analysisPending || !preview || busy) return;
    const timer = window.setTimeout(() => { void open(preview.dataset_id, preview.sheet_name || undefined); }, 2500);
    return () => window.clearTimeout(timer);
  }, [analysisPending, preview, busy]);

  async function upload(selectedFile: File) {
    if (uploading.current || unavailable) return;
    uploading.current = true;
    const version = ++sequence.current;
    setBusy(true); setError(''); setNotice(`Đang tải ${selectedFile.name} và kiểm tra file…`);
    setPreview(null); setNormalized(null);
    try {
      const body = new FormData(); body.append('file', selectedFile);
      const result = await api(`/workspaces/${workspaceId}/datasets`, { method: 'POST', body }, csrf);
      if (version !== sequence.current) return;
      if (!record(result) || typeof result.dataset_id !== 'string') throw new Error('Upload chưa trả về dữ liệu hợp lệ.');
      await refresh(); await open(result.dataset_id);
    } catch (e: unknown) { if (version === sequence.current) setError(message(e)); }
    finally { uploading.current = false; setBusy(false); }
  }

  function edit(index: number, change: Partial<Column>) {
    setPreview((old) => old ? { ...old, columns: old.columns.map((column, i) =>
      i === index ? { ...column, ...change } : column) } : old);
  }
  const draft = useMemo(() => {
    if (!preview || preview.status === 'ready' || !preview.columns.length) return { body: '', error: '' };
    try {
      const columns = preview.columns.map((column) => ({ id: column.id, name: column.name,
        data_type: column.data_type, nullable: column.nullable, primary_key: column.primary_key,
        null_values: column.null_values, date_format: column.date_format,
        decimal_separator: column.decimal_separator, unit: column.unit,
        description: column.description || '', aliases: column.aliases || [], role: column.role || 'other',
        value_mappings: mappingDraft[column.id] === undefined ? column.value_mappings || [] : parseMappings(mappingDraft[column.id]),
        aggregation_policy: column.aggregation_policy || 'unspecified' }));
      return { body: JSON.stringify({ revision_id: preview.revision_id, columns,
        sheet_name: preview.sheet_name || null, timezone, grain, description,
        sharing_providers: datasetModels, data_classification: preview.data_classification }), error: '' };
    } catch (e: unknown) { return { body: '', error: message(e) }; }
  }, [preview, description, grain, timezone, mappingDraft]);

  useEffect(() => {
    if (!preview || preview.status === 'ready' || !draft.body || unavailable) return;
    let active = true;
    setValidationError('');
    const timer = window.setTimeout(() => {
      setValidating(true);
      void api(`/datasets/${preview.dataset_id}/normalization-preview`, { method: 'POST', body: draft.body }, csrf)
        .then((data) => { if (active) { setNormalized(parseNormalization(data, preview)); setValidatedDraft(draft.body); } })
        .catch((e: unknown) => { if (active) { setNormalized(null); setValidatedDraft(''); setValidationError(message(e)); } })
        .finally(() => { if (active) setValidating(false); });
    }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [draft.body, unavailable, preview, csrf]);

  async function publish() {
    if (!preview || saving.current || unavailable || validating || !draft.body || validatedDraft !== draft.body) return;
    saving.current = true;
    setBusy(true); setError('');
    try {
      await api(`/datasets/${preview.dataset_id}/confirm`, { method: 'POST', body: draft.body }, csrf);
      const saved: Dataset = { id: preview.dataset_id, name: preview.name, revision_id: preview.revision_id,
        status: 'ready', sharing_providers: datasetModels };
      await refresh(); onReady?.(saved);
      if (onSaved) onSaved(saved); else await open(preview.dataset_id);
    } catch (e: unknown) { setError(message(e)); }
    finally { saving.current = false; setBusy(false); }
  }

  return <section className="dataset-panel">
    <ol className="setup-steps"><li>1. Tải dữ liệu</li><li>2. Xem trước và sau</li><li>3. Lưu vào không gian</li></ol>
    <div className={`upload-form ${preview ? 'upload-compact' : ''}`}>
      <input ref={fileInput} type="file" accept=".csv,.xlsx" hidden disabled={unavailable || validating}
        onChange={(event) => { const selectedFile = event.target.files?.[0]; event.target.value = ''; if (selectedFile) void upload(selectedFile); }} />
      <button type="button" className={preview ? 'secondary' : ''} disabled={unavailable || validating}
        onClick={() => fileInput.current?.click()}>{preview ? 'Đổi file' : 'Chọn CSV hoặc XLSX'}</button>
      <span className="upload-limit">CSV / XLSX · Tối đa 20 MiB</span>
      {!preview && <p>AI tự phân tích tên cột, thống kê và một số giá trị giới hạn để gợi ý chuẩn hoá. File gốc được giữ nguyên.</p>}
    </div>
    {busy && !preview && <p role="status">{notice}</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {!list.length && !preview && <p className="muted">Tải dataset để bắt đầu. Bạn sẽ xem lại trước khi lưu.</p>}
    {preview && <div className="review">
      <h3>{preview.name} {preview.columns.length > 0 && <span className="muted">· {preview.row_count} dòng</span>}</h3>
      {preview.sheets.length > 1 && <label>Trang dữ liệu<select aria-label="Trang dữ liệu" value={preview.sheet_name}
        disabled={unavailable || validating || preview.status === 'ready'} onChange={(event) => void open(preview.dataset_id, event.target.value)}>
        <option value="" disabled>Chọn trang cần sử dụng</option>{preview.sheets.map((sheet) => <option key={sheet}>{sheet}</option>)}</select></label>}
      <AIReview busy={unavailable} notice={notice} notes={notes}
        onRetry={canRetry && !unavailable ? () => void open(preview.dataset_id, preview.sheet_name || undefined, true) : undefined} />
      {preview.columns.length > 0 && <>
        <div className="review-summary"><strong>{preview.row_count} dòng · {preview.columns.length} cột</strong>
          <span>{preview.status === 'ready' ? 'Đã lưu trong không gian làm việc' : validating ? 'Đang kiểm tra toàn bộ dữ liệu…' : normalized && validatedDraft === draft.body ? 'Đã kiểm tra toàn bộ dữ liệu' : 'Đang chuẩn bị bản xem trước'}</span></div>
        <DataComparison preview={preview} normalized={preview.status === 'ready' || validatedDraft === draft.body ? normalized : null} />
        {(draft.error || validationError) && <p role="alert" className="error">{draft.error || validationError} Mở chỉnh sửa chi tiết để kiểm tra.</p>}
        <details className="advanced"><summary>Chỉnh sửa chi tiết</summary>
        <label>Mô tả dữ liệu<input value={description} disabled={unavailable || preview.status === 'ready'} maxLength={1000} onChange={(e) => setDescription(e.target.value)} /></label>
        <div className="table-scroll"><table><thead><tr><th>Cột</th><th>Kiểu</th><th>Cho phép NULL</th>
          <th>Ô trống → NULL</th><th>Khóa</th><th>Đơn vị</th><th>Kiểm kê</th></tr></thead>
          <tbody>{preview.columns.map((column, index) => <tr key={column.id}>
            <td><input aria-label={`Tên cột ${index + 1}`} value={column.name}
              disabled={unavailable || preview.status === 'ready'} onChange={(event) => edit(index, { name: event.target.value })} /></td>
            <td><select value={column.data_type} disabled={unavailable || preview.status === 'ready'}
              onChange={(event) => edit(index, { data_type: event.target.value as Kind })}>
              {kinds.map((kind) => <option key={kind} value={kind}>{kindNames[kind]}</option>)}</select>
              {column.data_type === 'date' && <select value={column.date_format} disabled={unavailable || preview.status === 'ready'}
                onChange={(event) => edit(index, { date_format: event.target.value })}>
                <option>%Y-%m-%d</option><option>%d/%m/%Y</option><option>%m/%d/%Y</option></select>}
              {column.data_type === 'numeric' && <select value={column.decimal_separator} disabled={unavailable || preview.status === 'ready'}
                onChange={(event) => edit(index, { decimal_separator: event.target.value })}>
                <option value=".">Thập phân: dấu chấm</option><option value=",">Thập phân: dấu phẩy</option></select>}</td>
            <td><input type="checkbox" checked={column.nullable} disabled={unavailable || preview.status === 'ready'}
              onChange={(event) => edit(index, { nullable: event.target.checked })} /></td>
            <td><input type="checkbox" checked={column.null_values.includes('')} disabled={unavailable || preview.status === 'ready'}
              onChange={(event) => edit(index, { null_values: event.target.checked ? [''] : [] })} /></td>
            <td><input type="checkbox" checked={column.primary_key} disabled={unavailable || preview.status === 'ready'}
              onChange={(event) => edit(index, { primary_key: event.target.checked })} /></td>
            <td><input value={column.unit ?? ''} disabled={unavailable || preview.status === 'ready'}
              onChange={(event) => edit(index, { unit: event.target.value || null })} /></td>
            <td>{column.null_count ?? '—'} NULL / {column.empty_count ?? '—'} trống / {column.duplicate_count ?? '—'} trùng</td>
          </tr>)}</tbody></table></div>
        {preview.columns.map((column, index) => <fieldset key={column.id}><legend>{column.name}</legend>
          <label>Ý nghĩa cột<input value={column.description ?? ''} maxLength={500} disabled={unavailable || preview.status === 'ready'} onChange={(e) => edit(index, { description: e.target.value })} /></label>
          <label>Tên gọi tương đương (ngăn bằng dấu phẩy)<input key={`${column.id}:${(column.aliases ?? []).join(',')}`} defaultValue={(column.aliases ?? []).join(', ')} disabled={unavailable || preview.status === 'ready'} onBlur={(e) => edit(index, { aliases: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} /></label>
          <label>Vai trò<select value={column.role ?? 'other'} disabled={unavailable || preview.status === 'ready'} onChange={(e) => edit(index, { role: e.target.value })}>
            <option value="other">Chưa xác định</option><option value="identifier">Mã đối tượng</option><option value="status">Trạng thái</option><option value="time">Thời gian</option><option value="amount">Số tiền</option><option value="quantity">Số lượng</option><option value="name">Tên đối tượng</option></select></label>
          <label>Cách tổng hợp<select value={column.aggregation_policy ?? 'unspecified'} disabled={unavailable || preview.status === 'ready'} onChange={(e) => edit(index, { aggregation_policy: e.target.value })}><option value="unspecified">Chưa có hạn chế được xác nhận</option><option value="additive">Có thể cộng theo mỗi dòng</option><option value="non_additive">Không cộng hoặc lấy trung bình</option></select></label>
          <label>Tên gọi của giá trị (mỗi dòng: cách gọi=giá trị thật)<textarea value={mappingDraft[column.id] ?? (column.value_mappings ?? []).map((m) => `${m.phrase}=${m.value}`).join('\n')} disabled={unavailable || preview.status === 'ready'}
            onChange={(e) => setMappingDraft((old) => ({ ...old, [column.id]: e.target.value }))} /></label>
        </fieldset>)}
        <label>Mỗi dòng đại diện cho<input value={grain} disabled={unavailable || preview.status === 'ready'} maxLength={300} onChange={(e) => setGrain(e.target.value)} /></label>
        <label>Múi giờ<input value={timezone} disabled={unavailable || preview.status === 'ready'} onChange={(e) => setTimezone(e.target.value)} /></label>
        </details>
        {preview.status !== 'ready' && <div className="publish-actions">
          <p>Bấm lưu để xác nhận bản chuẩn hoá và sử dụng dataset trong không gian này.</p>
          <button disabled={unavailable || validating || !grain.trim() || !normalized || !draft.body || validatedDraft !== draft.body}
            onClick={() => void publish()}>Lưu vào không gian làm việc</button>
        </div>}
      </>}
    </div>}
    {list.length > 0 && <details className="existing-datasets"><summary>Dữ liệu trong không gian ({list.length})</summary>
      <div className="dataset-list">{list.map((dataset) => <button key={dataset.id} disabled={unavailable || validating}
        onClick={() => void open(dataset.id)}>{dataset.name} · {dataset.status === 'ready' ? 'Đã lưu' : 'Chờ xem lại'}</button>)}</div>
    </details>}
  </section>;
}

export function DataComparison({ preview, normalized }: { preview: Preview; normalized: Normalization | null }) {
  const original = normalized?.original_rows || preview.original_rows || preview.rows;
  const headers = normalized?.original_headers || preview.original_headers || preview.columns.map((column) => column.name);
  return <div className="comparison-grid">
    <section aria-label="Dữ liệu gốc" className="comparison-pane">
      <div className="comparison-title"><h4>Dữ liệu gốc</h4><span>Giữ nguyên file tải lên</span></div>
      <div className="table-scroll"><table><thead><tr>{headers.map((name, index) => <th key={index}>{name}</th>)}</tr></thead>
        <tbody>{original.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j}>{display(value)}</td>)}</tr>)}</tbody></table></div>
    </section>
    <section aria-label="Sau chuẩn hoá" className="comparison-pane normalized-pane">
      <div className="comparison-title"><h4>Sau chuẩn hoá</h4><span>{normalized ? preview.status === 'ready' ? 'Bản dữ liệu đã lưu' : 'Bản dữ liệu sẽ được lưu' : 'Đang kiểm tra đề xuất'}</span></div>
      {normalized ? <div className="table-scroll"><table><thead><tr>{preview.columns.map((column) => <th key={column.id}>{column.name}<small>{kindNames[column.data_type]}{column.unit ? ` · ${column.unit}` : ''}</small></th>)}</tr></thead>
        <tbody>{normalized.rows.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j}
          className={JSON.stringify(value) !== JSON.stringify(original[i]?.[j]) ? 'normalized-cell' : undefined}>{display(value)}</td>)}</tr>)}</tbody></table></div>
        : <p className="comparison-empty">Bản chuẩn hoá sẽ hiện sau khi đề xuất được kiểm tra. Dữ liệu nguồn không thay đổi.</p>}
    </section>
    <p className="comparison-footnote">Xem trước {original.length}/{preview.row_count} dòng. Ô tô màu thể hiện thay đổi kiểu hoặc định dạng; ô trống và NULL được phân biệt.</p>
  </div>;
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
