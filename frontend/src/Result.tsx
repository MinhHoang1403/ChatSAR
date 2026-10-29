import { record } from './api';
import type { Answer } from './Chat';

export default function Result({ value }: { value: Answer }) {
  const columns = Array.isArray(value.facts.columns) ? value.facts.columns.filter(record) : [];
  const scope = record(value.facts.scope) ? value.facts.scope : null;
  const filters = Array.isArray(value.facts.filters) ? value.facts.filters.filter(record) : [];
  return <>
    <p>{value.display_text}</p>
    {value.display_rows.length > 0 && <div className="table-scroll"><table>
      <thead><tr>{columns.map((c, i) => <th key={i}>{cell(c.name)}{c.unit ? ` (${cell(c.unit)})` : ''}</th>)}</tr></thead>
      <tbody>{value.display_rows.map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{cell(v)}</td>)}</tr>)}</tbody>
    </table></div>}
    {scope && <details><summary>Nguồn và cách tính</summary>
      <p>Phiên bản dữ liệu: <code>{cell(scope.source_revision)}</code></p>
      <p>Mỗi dòng nguồn: {cell(scope.grain)} · Múi giờ: {cell(scope.timezone)}</p>
      <p>Phép tính: {columns.map((c) => cell(c.name)).join(', ')}</p>
      {filters.length > 0 && <p>Giá trị lọc đã đối chiếu: {filters.map((f) => cell(f.raw_phrase)).join(', ')}</p>}
      <p>Mã đối chiếu nguồn: <code>{cell(scope.checksum)}</code></p>
      <p>Kết quả lấy từ dữ liệu đã xác nhận. Cần kiểm tra điều kiện lọc khi câu hỏi có nhiều nghĩa.</p>
    </details>}
    {value.limitations.map((text, i) => <p className="limitation" key={i}>{text}</p>)}
  </>;
}

function cell(value: unknown): string {
  if (value === null) return 'Chưa có giá trị';
  if (typeof value === 'boolean') return value ? 'Có' : 'Không';
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}
