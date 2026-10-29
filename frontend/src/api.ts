export type RecordValue = Record<string, unknown>;
export type Identity = { id: string; display_name: string; csrf_token: string };
export type Workspace = { id: string; name: string };

export function record(value: unknown): value is RecordValue {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export async function api(path: string, options: RequestInit = {}, csrf?: string): Promise<unknown> {
  const headers = new Headers(options.headers);
  if (csrf) headers.set('X-CSRF-Token', csrf);
  if (typeof options.body === 'string') headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...options, headers, credentials: 'same-origin' });
  if (response.status === 204) return null;
  const data: unknown = await response.json();
  if (!response.ok) {
    const message = record(data) && record(data.error) && typeof data.error.message === 'string'
      ? data.error.message : 'Chưa thể xử lý yêu cầu. Vui lòng thử lại.';
    throw new Error(message);
  }
  return data;
}

export function identity(value: unknown): Identity {
  if (!record(value) || typeof value.id !== 'string' || typeof value.display_name !== 'string'
    || typeof value.csrf_token !== 'string') throw new Error('Thông tin phiên không hợp lệ.');
  return { id: value.id, display_name: value.display_name, csrf_token: value.csrf_token };
}

export function workspaceList(value: unknown): Workspace[] {
  if (!Array.isArray(value)) throw new Error('Danh sách không gian làm việc không hợp lệ.');
  return value.map((item: unknown) => {
    if (!record(item) || typeof item.id !== 'string' || typeof item.name !== 'string') {
      throw new Error('Thông tin không gian làm việc không hợp lệ.');
    }
    return { id: item.id, name: item.name };
  });
}
