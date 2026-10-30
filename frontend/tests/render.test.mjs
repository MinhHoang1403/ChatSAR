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
  assert.match(html, /aria-label="Tài khoản ChatSAR"/);
  assert.match(html, /aria-haspopup="menu"/);
  assert.doesNotMatch(html, /brand-mark|Trợ lý dữ liệu/);
  assert.doesNotMatch(html, /never-render-token|private-user-id|RAG|Hybrid/);
  assert.ok(html.indexOf('workspace-switch') < html.indexOf('class="search"'));
  assert.equal((html.match(/class="workspace-switch"/g) ?? []).length, 1);
});
test('composer requires a ready source and Gemini is the default', async () => {
  const html = await render('Chat', { workspaceId: 'workspace', csrf: 'csrf', scope: null, selected: '', onSelect: noop, onList: noop, onBusy: noop, onManageData: noop });
  assert.match(html, /value="gemini" selected=""/);
  assert.match(html, /send-button"[^>]*disabled=""/);
  assert.match(html, /aria-label="Thêm dữ liệu và không gian"/);
  assert.match(html, /rows="1"/);
  assert.doesNotMatch(html, /Cập nhật lịch sử|fallback-choice|composer-note|empty-symbol/);
});
test('history groups by immutable revision, including equal filenames and legacy records', async () => {
  const { historyGroups } = await vite.ssrLoadModule('/src/Workspace.tsx');
  const { conversation } = await vite.ssrLoadModule('/src/Chat.tsx');
  const items = [{ id: 'a', title: 'A', revision_id: 'r1', dataset_name: 'same.csv' },
    { id: 'b', title: 'B', revision_id: 'r2', dataset_name: 'same.csv' },
    { id: 'c', title: 'C', revision_id: 'r1', dataset_name: 'same.csv' }, { id: 'legacy', title: 'Old' }].map(conversation);
  const groups = historyGroups(items);
  assert.equal(groups.length, 3); assert.deepEqual(groups[0].items.map((c) => c.id), ['a', 'c']);
  assert.equal(groups[2].label, 'Chưa xác định nguồn');
  assert.throws(() => conversation({ id: 'x', title: 'X', revision_id: 7 }));
});
test('result preserves exact numeric text, NULL and escapes untrusted text', async () => {
  const html = await render('Result', { value: { status: 'partial', display_text: 'Đang hiển thị một phần', display_rows: [['9007199254740993', '300.15', null, '<script>attack</script>']], facts: { columns: [{ name: 'Mã' }, { name: 'Tiền' }, { name: 'Trống' }, { name: 'Văn bản' }] }, limitations: ['Còn kết quả chưa hiển thị'] } });
  assert.match(html, /9007199254740993/); assert.match(html, /300\.15/);
  assert.match(html, /Chưa có giá trị/); assert.doesNotMatch(html, /<script>/);
  assert.match(html, /Còn kết quả chưa hiển thị/);
});
test('friendly headings preserve underscores inside exact values and answer text', async () => {
  const html = await render('Result', { value: { status: 'answered', display_text: 'job_code: A_0007',
    display_rows: [['A_0007']], facts: { columns: [{ name: 'job_code', label: 'Mã lệnh' }] }, limitations: [] } });
  assert.match(html, /Mã lệnh: A_0007/); assert.match(html, /<td>A_0007<\/td>/);
  assert.doesNotMatch(html, /A 0007/);
});
test('answer tools are collapsed and never expose SQL or source identifiers by default', async () => {
  const html = await render('Result', { value: { status:'answered',display_text:'Có 2 bản ghi.',display_rows:[],facts:{},limitations:[],
    processing:{source:{revision_id:'private-revision'},sql:{compiled:true,statement:'SELECT secret_column FROM private_table',execution_status:'succeeded'}} } });
  assert.match(html,/Nguồn &amp; xử lý/); assert.match(html,/Xem SQL/);
  assert.equal((html.match(/aria-expanded="false"/g) ?? []).length,2);
  assert.doesNotMatch(html,/private-revision|private_table|secret_column/);
  const error = await render('Result',{value:{status:'provider_unavailable',display_text:'Chưa thể gọi mô hình.',display_rows:[],facts:{},limitations:[],processing:{sql:{compiled:false,statement:null}}}});
  assert.match(error,/Chi tiết lỗi/);assert.match(error,/SQL chưa tạo/);
  assert.doesNotMatch(error,/SELECT/);
});
test('SQL formatting changes only whitespace and preserves quoted identifiers and binds', async () => {
  const { formatSql } = await vite.ssrLoadModule('/src/Result.tsx');
  const sql='SELECT sum(data.r.c) AS "SELECT FROM", count(*) AS total \nFROM data.r \nWHERE data.r.c IN (%(codes_1)s, %(codes_2)s) AND data.r.d >= %(start)s GROUP BY data.r.c ORDER BY total DESC LIMIT %(limit)s';
  const formatted=formatSql(sql);
  assert.match(formatted,/SELECT\n/);assert.match(formatted,/FROM\n/);
  assert.ok(formatted.includes('"SELECT FROM"'));
  assert.equal(formatted.replace(/\s+/g,' '),sql.replace(/\s+/g,' '));
  assert.equal((formatted.match(/%\(/g) ?? []).length,4);
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
test('applying local or AI metadata preserves immutable empty/null/duplicate statistics', async () => {
  const { parseColumn, mergeProposalColumn } = await vite.ssrLoadModule('/src/data.ts');
  const source = parseColumn({ id: 'column', name: 'Value', data_type: 'numeric', nullable: true,
    empty_count: 1, null_count: 2, duplicate_count: 3 });
  const proposal = parseColumn({ id: 'column', name: 'Value', data_type: 'numeric', nullable: true,
    null_values: [''], description: 'Metadata mới' });
  const merged = mergeProposalColumn(source, proposal);
  assert.equal(merged.empty_count, 1); assert.equal(merged.null_count, 2);
  assert.equal(merged.duplicate_count, 3); assert.deepEqual(merged.null_values, ['']);
  assert.equal(merged.description, 'Metadata mới');
  assert.throws(() => mergeProposalColumn(source, { ...proposal, id: 'other' }));
});
test('saved setup is offered without another cloud call only for matching checksum and sheet', async () => {
  const p = { ...preview, checksum: 'file-hash', setup_proposal: { status: 'complete', response: { checksum: 'file-hash', sheet_name: '' } } };
  const props = { preview: p, csrf: 'csrf', onBusy: noop, onProposal: noop };
  assert.match(await render('AIReview', props), /Mở đề xuất đã lưu/);
  assert.doesNotMatch(await render('AIReview', { ...props, preview: { ...p, checksum: 'different-hash' } }), /Mở đề xuất đã lưu/);
});
