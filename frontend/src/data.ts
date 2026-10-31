import { api, record } from './api';

export type Kind = 'text' | 'integer' | 'numeric' | 'boolean' | 'date' | 'timestamp';
export type Column = {
  id: string; name: string; data_type: Kind; nullable: boolean; primary_key: boolean;
  null_values: string[]; date_format: string; decimal_separator: string; unit: string | null;
  null_count?: number; empty_count?: number; duplicate_count?: number;
  description?: string; aliases?: string[]; role?: string;
  value_mappings?: { phrase: string; value: string }[]; aggregation_policy?: string;
};
export type Dataset = { id: string; name: string; revision_id: string; status: string; sharing_providers?: string[] };
export type Preview = { dataset_id: string; revision_id: string; status: string; name: string;
  sheets: string[]; sheet_name: string; columns: Column[]; rows: unknown[][]; row_count: number;
  description: string; grain: string; timezone: string; sharing_providers: string[]; data_classification: string;
  checksum?: string; setup_proposal?: unknown; original_rows?: unknown[][]; original_headers?: string[] };
export const datasetModels = ['gemini', 'knowledge'];
export type Normalization = { revision_id: string; checksum: string; sheet_name: string; row_count: number;
  original_headers: string[]; original_rows: unknown[][]; rows: unknown[][] };
export const kinds: Kind[] = ['text', 'integer', 'numeric', 'boolean', 'date', 'timestamp'];
export const kindNames: Record<Kind, string> = { text: 'Văn bản / mã', integer: 'Số nguyên', numeric: 'Số thập phân', boolean: 'Có / không', date: 'Ngày', timestamp: 'Ngày và giờ' };

export function datasetList(data: unknown): Dataset[] {
  if (!Array.isArray(data)) throw new Error('Danh sách dữ liệu chưa đúng định dạng.');
  return data.map((value: unknown) => {
    if (!record(value) || typeof value.id !== 'string' || typeof value.name !== 'string'
      || typeof value.revision_id !== 'string' || typeof value.status !== 'string') throw new Error('Thông tin dữ liệu chưa đúng định dạng.');
    return { id: value.id, name: value.name, revision_id: value.revision_id, status: value.status,
      sharing_providers: Array.isArray(value.sharing_providers) ? value.sharing_providers.filter((p): p is string => typeof p === 'string') : [] };
  });
}

export function parsePreview(data: unknown): Preview {
  if (!record(data) || typeof data.dataset_id !== 'string' || typeof data.revision_id !== 'string'
    || typeof data.status !== 'string' || typeof data.name !== 'string' || !Array.isArray(data.sheets)
    || !data.sheets.every((v: unknown) => typeof v === 'string') || typeof data.sheet_name !== 'string'
    || !Array.isArray(data.columns) || !Array.isArray(data.rows) || !data.rows.every(Array.isArray)
    || typeof data.row_count !== 'number') throw new Error('Preview chưa đúng định dạng.');
  const columns = data.columns.map(parseColumn);
  return { dataset_id: data.dataset_id, revision_id: data.revision_id, status: data.status,
    name: data.name, sheets: data.sheets as string[], sheet_name: data.sheet_name,
    columns, rows: data.rows as unknown[][], row_count: data.row_count,
    description: typeof data.description === 'string' ? data.description : '',
    grain: typeof data.grain === 'string' ? data.grain : 'Một dòng dữ liệu',
    timezone: typeof data.timezone === 'string' ? data.timezone : 'Asia/Ho_Chi_Minh',
    sharing_providers: Array.isArray(data.sharing_providers) ? data.sharing_providers.filter((v): v is string => typeof v === 'string') : [],
    data_classification: typeof data.data_classification === 'string' ? data.data_classification : 'private',
    checksum: typeof data.checksum === 'string' ? data.checksum : '', setup_proposal: data.setup_proposal,
    original_rows: Array.isArray(data.original_rows) && data.original_rows.every(Array.isArray) ? data.original_rows as unknown[][] : undefined,
    original_headers: Array.isArray(data.original_headers) && data.original_headers.every((v) => typeof v === 'string') ? data.original_headers as string[] : undefined };
}

export function parseNormalization(data: unknown, preview: Preview): Normalization {
  if (!record(data) || data.revision_id !== preview.revision_id || data.checksum !== preview.checksum
    || data.sheet_name !== preview.sheet_name || data.row_count !== preview.row_count
    || !Array.isArray(data.original_headers) || !data.original_headers.every((v) => typeof v === 'string')
    || data.original_headers.length !== preview.columns.length
    || !Array.isArray(data.original_rows) || !Array.isArray(data.rows)
    || data.rows.length !== data.original_rows.length
    || ![...data.rows, ...data.original_rows].every((row) => Array.isArray(row) && row.length === preview.columns.length)) {
    throw new Error('Bản chuẩn hoá chưa khớp phiên bản nguồn. Vui lòng kiểm tra lại.');
  }
  return data as unknown as Normalization;
}

export async function prepareDatasetForQuery(source: Dataset, csrf: string): Promise<void> {
  if (datasetModels.every((provider) => source.sharing_providers?.includes(provider))) return;
  // Hỏi một nguồn đã chọn là thao tác sử dụng dataset với mô hình theo chính sách mới.
  // Dùng API owner/CSRF/audit hiện có; không backfill hoặc chia sẻ các nguồn khác.
  await api(`/datasets/${source.id}/sharing`, { method: 'PATCH', body: JSON.stringify({
    revision_id: source.revision_id, sharing_providers: datasetModels,
  }) }, csrf);
}


export function parseColumn(value: unknown): Column {
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
      description: typeof value.description === 'string' ? value.description : '',
      aliases: Array.isArray(value.aliases) ? value.aliases.filter((v): v is string => typeof v === 'string') : [],
      role: typeof value.role === 'string' ? value.role : 'other',
      aggregation_policy: typeof value.aggregation_policy === 'string' ? value.aggregation_policy : 'unspecified',
      value_mappings: Array.isArray(value.value_mappings) ? value.value_mappings.filter(record).filter((v) => typeof v.phrase === 'string' && typeof v.value === 'string').map((v) => ({ phrase: String(v.phrase), value: String(v.value) })) : [],
      null_count: typeof value.null_count === 'number' ? value.null_count : undefined,
      empty_count: typeof value.empty_count === 'number' ? value.empty_count : undefined,
      duplicate_count: typeof value.duplicate_count === 'number' ? value.duplicate_count : undefined };
}

export function mergeProposalColumn(source: Column, proposal: Column): Column {
  if (source.id !== proposal.id) throw new Error('Đề xuất không khớp cột nguồn.');
  // Thống kê thuộc file gốc, đề xuất metadata không được ghi đè bằng undefined.
  return { ...proposal, null_count: source.null_count, empty_count: source.empty_count,
    duplicate_count: source.duplicate_count };
}
