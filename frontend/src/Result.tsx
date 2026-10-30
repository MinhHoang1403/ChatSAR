import { useId, useRef, useState } from 'react';
import { record } from './api';
import type { Answer } from './Chat';

const stageNames: Record<string, string> = {
  authorization:'Kiểm tra quyền và nguồn dữ liệu', catalog:'Chuẩn bị danh mục dữ liệu',
  provider:'Chuẩn bị, gọi và nhận kế hoạch từ mô hình', provider_preparation:'Kiểm tra điều kiện gọi mô hình',
  provider_call:'Gọi mô hình', proposal_parse:'Nhận và đọc kế hoạch truy vấn',
  semantic_validation:'Kiểm tra kế hoạch truy vấn', sql_compilation:'Biên dịch SQL',
  execution:'Lấy dữ liệu bằng SQL', composition:'Diễn đạt kết quả', persistence:'Lưu kết quả',
  interrupted:'Lượt xử lý bị gián đoạn; chưa xác định bước cuối',
  session_and_result_retrieval:'Đọc phiên và kết quả đã lưu',
};
const states: Record<string, string> = {answered:'Đã xác minh',partial:'Chỉ hiển thị một phần',clarify:'Cần làm rõ',
  insufficient:'Chưa đủ điều kiện',unsupported:'Ngoài phạm vi hỗ trợ',provider_unavailable:'Chưa thể gọi mô hình',execution_error:'Chưa có kết quả được xác minh',pending:'Đang xử lý'};
const executions: Record<string,string> = {not_started:'Chưa thực thi',in_progress:'Đang thực thi',
  succeeded:'Thực thi thành công',failed:'Thực thi không thành công',unknown:'Không xác định sau gián đoạn'};
function cell(value: unknown): string {
  if (value === null) return 'Chưa có giá trị';
  if (typeof value === 'boolean') return value ? 'Có' : 'Không';
  return typeof value === 'string' || typeof value === 'number' ? String(value) : 'Chưa có thông tin';
}
function timing(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return 'Không có số liệu';
  return value >= 1000 ? `${(value / 1000).toLocaleString('vi-VN',{maximumFractionDigits:3})} giây` : `${value.toLocaleString('vi-VN',{maximumFractionDigits:2})} ms`;
}
export function formatSql(statement: string): string {
  // Chỉ đổi whitespace của SQL parameterized do server cung cấp; không execute.
  // Không chia keyword bên trong quoted identifiers hoặc literals.
  const tokens = statement.match(/"(?:""|[^"])*"|'(?:''|[^'])*'|%\([^)]+\)s|\bGROUP BY\b|\bORDER BY\b|\bSELECT\b|\bFROM\b|\bWHERE\b|\bLIMIT\b|\bAND\b|\bOR\b|[^\s"']+|\s+/g) ?? [];
  return tokens.map((token) => ['SELECT','FROM','WHERE','GROUP BY','ORDER BY','LIMIT'].includes(token)
    ? `\n${token}\n    ` : ['AND','OR'].includes(token) ? `\n    ${token} ` : token).join('').trim();
}
export default function Result({ value }: { value: Answer }) {
  const [panel,setPanel] = useState<'source'|'sql'|null>(null);
  const id = useId();
  const sourceButton = useRef<HTMLButtonElement>(null);
  const sqlButton = useRef<HTMLButtonElement>(null);
  const columns = Array.isArray(value.facts.columns) ? value.facts.columns.filter(record) : [];
  const scope = record(value.facts.scope) ? value.facts.scope : {};
  const processing = record(value.processing) ? value.processing : null;
  const source = processing && record(processing.source) ? processing.source : {};
  const sql = processing && record(processing.sql) ? processing.sql : null;
  const provider = processing && record(processing.provider) && typeof processing.provider.name === 'string'
    ? processing.provider : record(value.facts.provider) ? value.facts.provider : {};
  const stages = processing && record(processing.stages) ? processing.stages : {};
  const times = value.timings_ms ?? {};
  const failed = !['answered','partial','pending'].includes(value.status);
  const compiled = sql?.compiled === true && typeof sql.statement === 'string';
  const originalLabel = columns.length === 1 ? cell(columns[0].name) : '';
  const visibleLabel = columns.length === 1 ? cell(columns[0].label ?? columns[0].name).replace(/_/g,' ') : '';
  const displayText = originalLabel && value.display_text.startsWith(`${originalLabel}: `)
    ? visibleLabel + value.display_text.slice(originalLabel.length) : value.display_text;
  const sqlTitle = compiled ? 'Xem SQL' : processing && sql ? 'SQL chưa tạo' : 'SQL / trạng thái SQL';
  const sqlDuration = sql?.duration_ms;
  return <>
    <p>{displayText}</p>
    {value.display_rows.length > 0 && <div className="table-scroll"><table>
      <thead><tr>{columns.map((c,i) => <th key={i}>{cell(c.label ?? c.name).replace(/_/g,' ')}{c.unit ? ` (${cell(c.unit)})` : ''}</th>)}</tr></thead>
      <tbody>{value.display_rows.map((row,i) => <tr key={i}>{row.map((v,j) => <td key={j}>{cell(v)}</td>)}</tr>)}</tbody>
    </table></div>}
    <div className="answer-details" onKeyDown={(e) => { if (e.key === 'Escape' && panel) { const old=panel;setPanel(null);(old==='source'?sourceButton:sqlButton).current?.focus();e.stopPropagation(); } }}>
      <div className="answer-tools"><button ref={sourceButton} type="button" className="detail-button" aria-expanded={panel==='source'} aria-controls={`${id}-source`}
        onClick={() => setPanel(panel==='source'?null:'source')}>{failed?'Chi tiết lỗi':'Nguồn & xử lý'}</button>
        <button ref={sqlButton} type="button" className="detail-button" aria-expanded={panel==='sql'} aria-controls={`${id}-sql`}
          onClick={() => setPanel(panel==='sql'?null:'sql')}>{sqlTitle}</button></div>
      {panel==='source' && <section id={`${id}-source`} className="answer-panel" aria-label={failed?'Chi tiết lỗi':'Nguồn & xử lý'}>
        <dl><dt>Nguồn dữ liệu</dt><dd>{cell(source.name ?? scope.dataset_name)}</dd>
          <dt>Model thực tế</dt><dd>{typeof provider.name==='string' ? `${provider.name==='gemini'?'Gemini':provider.name==='knowledge'?'Knowledge':provider.name}${typeof provider.model==='string'?` · ${provider.model}`:''}` : 'Chưa có bằng chứng gọi mô hình'}</dd>
          <dt>Trạng thái</dt><dd>{states[value.status] ?? 'Chưa có thông tin'}</dd>
          <dt>Thời gian backend</dt><dd>{timing(times.server_processing)}</dd>
          <dt>Thời gian gọi mô hình</dt><dd>{timing(provider.latency_ms)}</dd>
          <dt>Thời gian SQL</dt><dd>{timing(sqlDuration)}</dd>
          {failed && <><dt>Bước lỗi</dt><dd>{processing && typeof processing.failed_stage==='string' ? stageNames[processing.failed_stage] ?? 'Chưa xác định được bước lỗi' : 'Không xác định được bước lỗi từ lịch sử cũ.'}</dd>
            <dt>Mã lỗi</dt><dd>{cell(processing?.error_code)}</dd></>}
          <dt>SQL</dt><dd>{compiled?'Đã biên dịch':sql?.compiled===false?'Chưa biên dịch':'Chưa lưu SQL'} · {sql && typeof sql.execution_status==='string'?executions[sql.execution_status] ?? 'Chưa có thông tin':'Chưa lưu trạng thái SQL'}</dd>
          {processing?.source_unchanged===true && <><dt>Dữ liệu nguồn</dt><dd>Không thay đổi</dd></>}
        </dl>
        <p className="muted">{typeof processing?.backend_timing_scope==='string'?processing.backend_timing_scope:'Thời gian backend đã lưu, không phải thời gian từ đầu đến cuối trên trình duyệt.'}</p>
        {sqlDuration===undefined && typeof value.facts.execution_latency_ms==='number' && <p className="muted">Thời gian lấy dữ liệu đã lưu (gồm kiểm nguồn/kết nối): {timing(value.facts.execution_latency_ms)}.</p>}
        <details className="advanced-evidence"><summary>Thông tin phiên bản và các bước</summary><dl>
          <dt>Phiên bản dữ liệu</dt><dd><code>{cell(source.revision_id ?? scope.source_revision)}</code></dd>
          <dt>Thời điểm xử lý</dt><dd>{typeof processing?.processed_at==='string'?new Date(processing.processed_at).toLocaleString('vi-VN'):'Chưa có thông tin'}</dd>
          <dt>Múi giờ nguồn</dt><dd>{cell(source.timezone ?? scope.timezone)}</dd>
          <dt>Grain đã xác nhận</dt><dd>{cell(source.grain ?? scope.grain)}</dd>
          <dt>Checksum nguồn</dt><dd><code>{cell(source.checksum ?? scope.checksum)}</code></dd>
          {Object.entries(stages).map(([name,detail])=>record(detail)?<div className="stage-row" key={name}><dt>{stageNames[name] ?? 'Bước xử lý'}</dt><dd>{detail.status==='succeeded'?'Hoàn tất':detail.status==='failed'?'Thất bại':detail.status==='in_progress'?'Đang xử lý':detail.status==='needs_clarification'?'Cần làm rõ':detail.status==='unsupported'?'Ngoài phạm vi':'Chưa xác định'}{typeof detail.duration_ms==='number'?` · ${timing(detail.duration_ms)}`:''}</dd></div>:null)}
        </dl></details>
      </section>}
      {panel==='sql' && <section id={`${id}-sql`} className="answer-panel" aria-label="SQL của lượt trả lời">
        {compiled?<><p>SQL PostgreSQL đã biên dịch cho lượt này. Giá trị tham số được giữ riêng.</p><pre className="sql-statement" tabIndex={0}><code>{formatSql(String(sql?.statement))}</code></pre>
          <p>{sql && typeof sql.execution_status==='string'?executions[sql.execution_status] ?? 'Chưa xác định trạng thái':'Chưa xác định trạng thái'}.</p>
          <p className="muted">LIMIT trong SQL bao gồm dòng kiểm tra cắt kết quả. Mở panel không chạy lại truy vấn.</p></>
          : <p>{processing && sql && sql.compiled===false?'SQL chưa được tạo cho lượt này.':'Câu lệnh SQL của lượt trả lời này chưa được lưu.'}</p>}
      </section>}
    </div>
    {value.limitations.filter((text)=>text!==value.display_text).map((text,i)=><p className="limitation" key={i}>{text}</p>)}
  </>;
}
