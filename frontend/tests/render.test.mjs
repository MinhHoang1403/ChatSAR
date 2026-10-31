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
  assert.ok(html.indexOf('workspace-switch') > html.indexOf('workspace-header'));
  assert.doesNotMatch(html.split('</aside>')[0], /workspace-switch/);
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
test('guest home exposes login and concise guest status without account profile', async () => {
  const html = await render('Workspace', { me: { id: 'guest-user', display_name: 'Never show account', csrf_token: 'never-render-token', is_guest: true }, workspaces: [{ id: 'guest-ws', name: 'Không gian tạm' }], selected: { id: 'guest-ws', name: 'Không gian tạm' }, onSelect: noop, onCreate: noop, onLogout: noop, onLogin: noop, busy: false, error: '' });
  assert.match(html, /Đăng nhập<\/button>/);
  assert.match(html, /class="guest-notice">Chế độ khách<\/p>/);
  assert.doesNotMatch(html, /Never show account|Tài khoản cá nhân|Hồ sơ ChatSAR|never-render-token/);
  assert.match(html, /Bạn muốn tìm hiểu điều gì/);
});
test('guest credentials live only in memory and are removed when the page ends', async () => {
  const { activateGuestSession, endGuestSession, api } = await vite.ssrLoadModule('/src/api.ts');
  const oldFetch = globalThis.fetch;
  const oldWindow = globalThis.window;
  const calls = [];
  globalThis.window = { setTimeout, clearTimeout, localStorage: { setItem() { throw new Error('Must not persist guest credentials'); } } };
  globalThis.fetch = async (path, options) => { calls.push({ path, options }); return { status: 200, ok: true, json: async () => [] }; };
  try {
    assert.throws(() => activateGuestSession({}));
    const who = activateGuestSession({ id: 'guest', display_name: 'Khách', csrf_token: 'guest-csrf', guest_token: 'ephemeral-only', is_guest: true });
    assert.equal(who.is_guest, true); assert.equal(who.guest_token, undefined);
    await api('/workspaces', {}, who.csrf_token);
    assert.equal(calls[0].options.headers.get('X-Guest-Session'), 'ephemeral-only');
    await endGuestSession();
    assert.equal(calls[1].options.method, 'DELETE'); assert.equal(calls[1].options.keepalive, true);
    await api('/workspaces');
    assert.equal(calls[2].options.headers.has('X-Guest-Session'), false);
  } finally { globalThis.fetch = oldFetch; if (oldWindow === undefined) delete globalThis.window; else globalThis.window = oldWindow; }
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
  assert.match(html,/Nguồn &amp; xử lý/); assert.match(html,/Truy vấn SQL/);
  assert.equal((html.match(/aria-expanded="false"/g) ?? []).length,2);
  assert.doesNotMatch(html,/private-revision|private_table|secret_column/);
  const error = await render('Result',{value:{status:'provider_unavailable',display_text:'Chưa thể gọi mô hình.',display_rows:[],facts:{},limitations:[],processing:{sql:{compiled:false,statement:null}}}});
  assert.match(error,/Nguồn &amp; xử lý/);assert.match(error,/Truy vấn SQL/);
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
test('AI review explains the result without extra consent or analysis controls', async () => {
  const html = await render('AIReview', { busy: false, notice: 'AI đã gợi ý chuẩn hoá.', notes: [] });
  assert.match(html, /AI đã gợi ý chuẩn hoá/);
  assert.doesNotMatch(html, /checkbox|Nhận đề xuất AI|Phân tích local|Chọn mô hình/);
});
test('data manager offers only working CSV/XLSX input', async () => {
  const html = await render('Datasets', { workspaceId: 'w', csrf: 'csrf', onReady: noop });
  assert.match(html, /accept="\.csv,\.xlsx"/); assert.match(html, /AI tự phân tích/);
  assert.match(html, /Xem trước và sau/);
  assert.doesNotMatch(html, /Tải lên và xem trước|Quyền hỏi đáp|RAG|HYBRID|PDF/);
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
test('saved setup is reused automatically only for matching checksum and sheet', async () => {
  const { savedSetupResponse } = await vite.ssrLoadModule('/src/AIReview.tsx');
  const p = { ...preview, checksum: 'file-hash', setup_proposal: { status: 'complete', response: { checksum: 'file-hash', sheet_name: '' } } };
  assert.ok(savedSetupResponse(p));
  assert.equal(savedSetupResponse({ ...p, checksum: 'different-hash' }), null);
  assert.equal(savedSetupResponse({ ...p, sheet_name: 'Other' }), null);
});

test('automatic AI preparation sends one bounded request and reuses the saved response', async () => {
  const { analyzeDataset } = await vite.ssrLoadModule('/src/AIReview.tsx');
  const { parseColumn } = await vite.ssrLoadModule('/src/data.ts');
  const column = parseColumn({ id: 'code', name: 'code', data_type: 'text', nullable: false, empty_count: 2 });
  const source = { ...preview, checksum: 'hash', columns: [column], rows: [['0007']] };
  const response = { checksum: 'hash', sheet_name: '', mode: 'ai_proposal',
    proposal: { columns: [{ ...column, description: 'Mã', empty_count: undefined }], description: 'Dataset', grain: 'Một dòng', notes: [] } };
  const oldFetch = globalThis.fetch, oldWindow = globalThis.window;
  const calls = [];
  globalThis.window = { setTimeout, clearTimeout };
  globalThis.fetch = async (path, options) => { calls.push({ path, options }); return { ok: true, status: 200, json: async () => response }; };
  try {
    const prepared = await analyzeDataset(source, 'csrf', 'stable-key');
    assert.equal(calls.length, 1); assert.equal(calls[0].path, '/api/datasets/source/setup');
    const body = JSON.parse(calls[0].options.body);
    assert.equal(body.use_ai, true); assert.equal(body.consent_metadata, true); assert.equal(body.consent_values, true);
    assert.equal(body.provider, 'gemini'); assert.equal(calls[0].options.headers.get('Idempotency-Key'), 'stable-key');
    assert.equal(prepared.columns[0].empty_count, 2);
    const cached = await analyzeDataset({ ...source, setup_proposal: { status: 'complete', response } }, 'csrf', 'other-key');
    assert.equal(calls.length, 1); assert.equal(cached.columns[0].description, 'Mã');
    await assert.rejects(() => analyzeDataset({ ...source, checksum: 'wrong' }, 'csrf', 'new-key'));
    assert.equal(calls.length, 2); // Loại phản hồi sai nguồn, không confirm hoặc tự thử lại.
  } finally { globalThis.fetch = oldFetch; if (oldWindow === undefined) delete globalThis.window; else globalThis.window = oldWindow; }
});

test('before-after preview preserves identifiers, exact decimals, empty and NULL', async () => {
  const { DataComparison } = await vite.ssrLoadModule('/src/Datasets.tsx');
  const { parseColumn, parseNormalization } = await vite.ssrLoadModule('/src/data.ts');
  const columns = [parseColumn({ id: 'code', name: 'code', data_type: 'text', nullable: false }),
    parseColumn({ id: 'amount', name: 'amount', data_type: 'numeric', nullable: true })];
  const source = { ...preview, checksum: 'hash', row_count: 2, columns, rows: [['0007', '0,10'], ['0012', '']] };
  const result = { revision_id: 'revision', checksum: 'hash', sheet_name: '', row_count: 2,
    original_headers: ['code', 'amount'], original_rows: source.rows, rows: [['0007', '0.10'], ['0012', null]] };
  const normalized = parseNormalization(result, source);
  const html = renderToStaticMarkup(createElement(DataComparison, { preview: source, normalized }));
  assert.match(html, /Dữ liệu gốc/); assert.match(html, /Sau chuẩn hoá/);
  assert.match(html, /0007/); assert.match(html, /0,10/); assert.match(html, /0.10/);
  assert.match(html, /NULL/); assert.match(html, /“”/); assert.match(html, /normalized-cell/);
  assert.throws(() => parseNormalization({ ...result, revision_id: 'other' }, source));
  assert.throws(() => parseNormalization({ ...result, rows: [['0007']] }, source));
});

test('using a selected legacy dataset grants models with owner CSRF without another user step', async () => {
  const { prepareDatasetForQuery } = await vite.ssrLoadModule('/src/data.ts');
  const oldFetch = globalThis.fetch, oldWindow = globalThis.window;
  const calls = []; globalThis.window = { setTimeout, clearTimeout };
  globalThis.fetch = async (path, options) => { calls.push({ path, options }); return { ok: true, status: 200, json: async () => ({}) }; };
  try {
    await prepareDatasetForQuery({ id: 'source', revision_id: 'revision', sharing_providers: [] }, 'csrf');
    assert.equal(calls.length, 1); assert.equal(calls[0].path, '/api/datasets/source/sharing');
    assert.equal(calls[0].options.headers.get('X-CSRF-Token'), 'csrf');
    assert.deepEqual(JSON.parse(calls[0].options.body).sharing_providers, ['gemini', 'knowledge']);
    await prepareDatasetForQuery({ id: 'source', revision_id: 'revision', sharing_providers: ['gemini', 'knowledge'] }, 'csrf');
    assert.equal(calls.length, 1);
  } finally { globalThis.fetch = oldFetch; if (oldWindow === undefined) delete globalThis.window; else globalThis.window = oldWindow; }
});
