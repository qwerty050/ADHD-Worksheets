// Single API client for the whole app. Base URL comes from VITE_API_URL
// (set in web/.env.local), falling back to the local dev server.
export const API_BASE: string =
  (import.meta as any).env?.VITE_API_URL ?? 'http://localhost:8000/api';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch(path: string, init?: RequestInit): Promise<any> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, `${res.status}: ${detail}`);
  }
  return res.json();
}

export async function apiPostForm(path: string, form: FormData): Promise<any> {
  return apiFetch(path, { method: 'POST', body: form });
}
