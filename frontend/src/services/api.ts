export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public detail: Record<string, unknown> = {}) {
    super(message);
  }
}

const BASE = "/api";

async function request<T>(method: string, path: string, body?: unknown, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body instanceof FormData || body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
      ...init,
    });
  } catch {
    throw new ApiError(0, "network", "Cannot reach the local backend. Is it running on http://127.0.0.1:8000?");
  }
  if (!res.ok) {
    let data: { error?: string; message?: string; detail?: unknown } = {};
    try { data = await res.json(); } catch { /* non-JSON error */ }
    const msg = data.message ?? (Array.isArray(data.detail) ? "Please check the highlighted fields." : `Request failed (${res.status})`);
    throw new ApiError(res.status, data.error ?? "error", msg, (data.detail as Record<string, unknown>) ?? {});
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("json") ? res.json() : res.blob()) as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string, body?: unknown) => request<T>("DELETE", path, body),
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, form),
};

export const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") u.set(k, String(v)); });
  const s = u.toString();
  return s ? `?${s}` : "";
};

export const downloadUrl = (path: string) => `${BASE}${path}`;
