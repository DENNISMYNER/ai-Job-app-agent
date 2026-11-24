import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";

export function renderApp(ui: ReactElement, route = "/") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><ToastProvider><MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter></ToastProvider></QueryClientProvider>,
  );
}

export interface Call { method: string; path: string; body: unknown }
type Handler = unknown | ((body: unknown) => unknown);

/** Route-based fetch mock. Keys are "METHOD /path" (query string ignored). Unmatched calls fail loudly. */
export function mockApi(routes: Record<string, Handler | { status: number; body: unknown }>) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = (init.method ?? "GET").toUpperCase();
    const path = url.replace(/^\/api/, "").split("?")[0];
    const body = typeof init.body === "string" ? JSON.parse(init.body) : init.body;
    calls.push({ method, path, body });
    const key = `${method} ${path}`;
    if (!(key in routes)) return new Response(JSON.stringify({ error: "unmocked", message: `Unmocked request ${key}` }), { status: 500, headers: { "content-type": "application/json" } });
    let h = routes[key] as Handler | { status: number; body: unknown };
    if (typeof h === "function") h = (h as (b: unknown) => unknown)(body);
    const status = h && typeof h === "object" && "status" in (h as object) && "body" in (h as object) ? (h as { status: number }).status : 200;
    const payload = status !== 200 ? (h as { body: unknown }).body : h;
    return new Response(JSON.stringify(payload), { status, headers: { "content-type": "application/json" } });
  }));
  return calls;
}
