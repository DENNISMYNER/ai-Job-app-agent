import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, qs } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("parses backend error payloads into ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "approval_required", message: "Needs approval", detail: { a: 1 } }), { status: 403 })));
    const err = await api.post("/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 403, code: "approval_required", message: "Needs approval", detail: { a: 1 } });
  });

  it("explains when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("failed"); }));
    await expect(api.get("/x")).rejects.toThrow(/Cannot reach the local backend/);
  });

  it("copes with non-JSON error bodies", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>boom</html>", { status: 502 })));
    await expect(api.get("/x")).rejects.toMatchObject({ status: 502, message: "Request failed (502)" });
  });

  it("sends JSON bodies and relative /api URLs", async () => {
    const f = vi.fn(async () => new Response("{}", { headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", f);
    await api.put("/profile", { a: 1 });
    expect(f).toHaveBeenCalledWith("/api/profile", expect.objectContaining({ method: "PUT", body: '{"a":1}', headers: { "Content-Type": "application/json" } }));
  });

  it("builds query strings, skipping empty values", () => {
    expect(qs({ a: 1, b: "", c: undefined, d: false, e: "x y" })).toBe("?a=1&d=false&e=x+y");
    expect(qs({})).toBe("");
  });
});
