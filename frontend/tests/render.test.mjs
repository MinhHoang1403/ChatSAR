import { after, test } from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

// SSR trong process test, không mở port hoặc tạo runtime/login bypass.
const vite = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
after(() => vite.close());
const render = async (name, props) => renderToStaticMarkup(createElement((await vite.ssrLoadModule(`/src/${name}.tsx`)).default, props));
const noop = () => {};
const preview = { dataset_id: 'source', revision_id: 'revision', status: 'needs_review', name: 'data.csv',
  sheets: [], sheet_name: '', columns: [], rows: [], row_count: 3, description: '', grain: 'Một dòng', timezone: 'UTC', sharing_providers: [], data_classification: 'private' };

test('workspace exposes one data manager, history and account without internal IDs', async () => {
  const html = await render('Workspace', { me: { id: 'private-user-id', display_name: 'QA', csrf_token: 'never-render-token' }, workspaces: [{ id: 'private-workspace-id', name: 'Kiểm thử' }], selected: { id: 'private-workspace-id', name: 'Kiểm thử' }, onSelect: noop, onCreate: noop, onLogout: noop, busy: false, error: '' });
  assert.match(html, /Lịch sử cuộc trò chuyện/);
  assert.match(html, /Quản lý dữ liệu/);
  assert.match(html, /Đăng xuất/);
  assert.doesNotMatch(html, /never-render-token|private-user-id|RAG|Hybrid/);
});
test('composer requires a ready source and Gemini is the default', async () => {
  const html = await render('Chat', { workspaceId: 'workspace', csrf: 'csrf', scope: null, selected: '', onSelect: noop, onList: noop, onBusy: noop, onManageData: noop });
  assert.match(html, /value="gemini" selected=""/);
  assert.match(html, /send-button" disabled=""/);
  assert.match(html, /Tải dữ liệu lên/);
});
test('result preserves exact numeric text, NULL and escapes untrusted text', async () => {
  const html = await render('Result', { value: { status: 'partial', display_text: 'Đang hiển thị một phần', display_rows: [['9007199254740993', '300.15', null, '<script>attack</script>']], facts: { columns: [{ name: 'Mã' }, { name: 'Tiền' }, { name: 'Trống' }, { name: 'Văn bản' }] }, limitations: ['Còn kết quả chưa hiển thị'] } });
  assert.match(html, /9007199254740993/); assert.match(html, /300\.15/);
  assert.match(html, /Chưa có giá trị/); assert.doesNotMatch(html, /<script>/);
  assert.match(html, /Còn kết quả chưa hiển thị/);
});
test('private AI setup starts with explicit consent and disabled cloud action', async () => {
  const html = await render('AIReview', { preview, csrf: 'never-render-token', onBusy: noop, onProposal: noop });
  assert.match(html, /Cho phép gửi tên cột và thống kê/);
  assert.match(html, /<button disabled="">Nhận đề xuất AI/);
  assert.match(html, /Phân tích local/); assert.doesNotMatch(html, /never-render-token/);
});
test('data manager offers only working CSV/XLSX input', async () => {
  const html = await render('Datasets', { workspaceId: 'w', csrf: 'csrf', onReady: noop });
  assert.match(html, /accept="\.csv,\.xlsx"/); assert.match(html, /Tải lên và xem trước/);
  assert.doesNotMatch(html, /RAG|HYBRID|PDF/);
});
test('API DTO rejects unknown data shape and preserves catalog metadata', async () => {
  const { datasetList, parsePreview } = await vite.ssrLoadModule('/src/data.ts');
  assert.throws(() => datasetList([{ id: 'x' }]));
  assert.throws(() => parsePreview({}));
  const col = { id: 'column', name: 'Mã', data_type: 'text', nullable: true, description: 'Mã đối tượng', aliases: ['mã'], role: 'identifier', value_mappings: [{ phrase: 'đầu', value: '0007' }] };
  const parsed = parsePreview({ ...preview, columns: [col], rows: [['0007']] });
  assert.equal(parsed.columns[0].description, col.description);
  assert.equal(parsed.columns[0].value_mappings[0].value, '0007');
});
