import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { AxiosResponse, InternalAxiosRequestConfig } from "axios";

// Stable mocks that survive vi.resetModules(), so the freshly-imported axios
// module's interceptor sees the same authService we configure per test. Mocking
// authService also severs the axios <-> authService import cycle, so the real
// service (and its localStorage access) never loads.
const svc = vi.hoisted(() => ({
  getAccessToken: vi.fn<() => string | null>(),
  refreshToken: vi.fn<() => Promise<{ access: string }>>(),
  logout: vi.fn(),
}));
vi.mock("@/services/authService", () => ({ authService: svc }));

// Import a pristine apiClient (fresh axios.create + interceptors + module-level
// isRefreshing/pendingRequests) for each test.
async function freshClient() {
  vi.resetModules();
  const mod = await import("@/plugins/axios");
  return mod.default;
}

// An adapter lets requests flow request-interceptor -> adapter -> response-
// interceptor with no real HTTP. A custom adapter is responsible for settling
// non-2xx itself (the built-in adapters call validateStatus; a custom one does
// not), so `fail` rejects with an axios-shaped error carrying { config, response }
// — exactly what the response *error* interceptor inspects.
function ok(config: InternalAxiosRequestConfig, data: unknown = {}) {
  return { data, status: 200, statusText: "OK", headers: {}, config };
}
function fail(config: InternalAxiosRequestConfig, code: number, data: unknown = {}) {
  return Promise.reject({
    config,
    response: { data, status: code, statusText: "", headers: {}, config },
    isAxiosError: true,
    message: `Request failed with status code ${code}`,
  });
}
const authHeader = (config: InternalAxiosRequestConfig) =>
  (config.headers as Record<string, unknown>)?.["Authorization"];

beforeEach(() => {
  vi.clearAllMocks();
  svc.getAccessToken.mockReturnValue(null);
  vi.stubGlobal("window", { location: { href: "" } });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request interceptor", () => {
  it("injects the Bearer header when a token exists", async () => {
    svc.getAccessToken.mockReturnValue("tok");
    const client = await freshClient();
    const adapter = vi.fn(async (c: InternalAxiosRequestConfig) => ok(c));
    client.defaults.adapter = adapter;

    await client.get("/conversations/");

    expect(authHeader(adapter.mock.calls[0][0])).toBe("Bearer tok");
  });

  it("leaves the header untouched when there is no token", async () => {
    svc.getAccessToken.mockReturnValue(null);
    const client = await freshClient();
    const adapter = vi.fn(async (c: InternalAxiosRequestConfig) => ok(c));
    client.defaults.adapter = adapter;

    await client.get("/conversations/");

    expect(authHeader(adapter.mock.calls[0][0])).toBeUndefined();
  });
});

describe("response interceptor — refresh on 401", () => {
  it("refreshes once and retries the original request with the new token", async () => {
    svc.getAccessToken.mockReturnValue("old");
    svc.refreshToken.mockImplementation(async () => {
      svc.getAccessToken.mockReturnValue("new"); // authService stores it
      return { access: "new" };
    });
    const client = await freshClient();
    const adapter = vi
      .fn<(c: InternalAxiosRequestConfig) => Promise<AxiosResponse>>()
      .mockImplementationOnce(async (c) => fail(c, 401))
      .mockImplementation(async (c) => ok(c, { ok: true }));
    client.defaults.adapter = adapter;

    const res = await client.get("/conversations/");

    expect(svc.refreshToken).toHaveBeenCalledOnce();
    expect(adapter).toHaveBeenCalledTimes(2);
    expect(authHeader(adapter.mock.calls[1][0])).toBe("Bearer new");
    expect(res.data).toEqual({ ok: true });
  });

  it("does not refresh on a 401 from an auth endpoint", async () => {
    const client = await freshClient();
    const adapter = vi.fn(async (c: InternalAxiosRequestConfig) => fail(c, 401));
    client.defaults.adapter = adapter;

    await expect(client.post("/auth/token/", {})).rejects.toBeTruthy();
    expect(svc.refreshToken).not.toHaveBeenCalled();
    expect(adapter).toHaveBeenCalledOnce();
  });

  it("does not refresh again when the request was already retried", async () => {
    const client = await freshClient();
    const adapter = vi.fn(async (c: InternalAxiosRequestConfig) => fail(c, 401));
    client.defaults.adapter = adapter;

    await expect(
      client.request({ url: "/conversations/", method: "get", _retry: true } as never),
    ).rejects.toBeTruthy();
    expect(svc.refreshToken).not.toHaveBeenCalled();
  });

  it("logs out and redirects to /login when the refresh itself fails", async () => {
    svc.getAccessToken.mockReturnValue("old");
    svc.refreshToken.mockRejectedValue(new Error("refresh 401"));
    const client = await freshClient();
    const adapter = vi.fn(async (c: InternalAxiosRequestConfig) => fail(c, 401));
    client.defaults.adapter = adapter;

    await expect(client.get("/conversations/")).rejects.toBeTruthy();

    expect(svc.logout).toHaveBeenCalledOnce();
    expect(window.location.href).toBe("/login");
  });
});

describe("response interceptor — pass-through", () => {
  it("passes non-401 errors straight through without refreshing", async () => {
    const client = await freshClient();
    const adapter = vi.fn(async (c: InternalAxiosRequestConfig) => fail(c, 500));
    client.defaults.adapter = adapter;

    await expect(client.get("/x")).rejects.toBeTruthy();
    expect(svc.refreshToken).not.toHaveBeenCalled();
    expect(adapter).toHaveBeenCalledOnce();
  });

  it("passes network errors (no response) through", async () => {
    const client = await freshClient();
    client.defaults.adapter = vi.fn(async () => {
      throw new Error("Network Error"); // no .response -> status is undefined
    });

    await expect(client.get("/x")).rejects.toThrow("Network Error");
    expect(svc.refreshToken).not.toHaveBeenCalled();
  });
});

describe("response interceptor — concurrent 401s", () => {
  it("refreshes once and retries every queued request", async () => {
    svc.getAccessToken.mockReturnValue("old");
    let resolveRefresh!: (v: { access: string }) => void;
    svc.refreshToken.mockReturnValue(
      new Promise((r) => {
        resolveRefresh = r;
      }),
    );
    const client = await freshClient();
    // Both first attempts 401; everything after refresh succeeds.
    const adapter = vi.fn(async (c: InternalAxiosRequestConfig) =>
      (c.headers as Record<string, unknown>)["Authorization"] === "Bearer new"
        ? ok(c, { ok: true })
        : fail(c, 401),
    );
    client.defaults.adapter = adapter;

    const p1 = client.get("/a");
    const p2 = client.get("/b");

    // Let both initial 401s be processed: p1 starts the refresh, p2 is queued.
    await new Promise((r) => setTimeout(r, 0));
    expect(svc.refreshToken).toHaveBeenCalledOnce();

    svc.getAccessToken.mockReturnValue("new");
    resolveRefresh({ access: "new" });

    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r1.data).toEqual({ ok: true });
    expect(r2.data).toEqual({ ok: true });
    expect(svc.refreshToken).toHaveBeenCalledOnce(); // still just one refresh
    expect(adapter).toHaveBeenCalledTimes(4); // 2 initial 401s + 2 retries
  });

  it("drops the Authorization header on a queued retry when no token is available", async () => {
    svc.getAccessToken.mockReturnValue("old");
    let resolveRefresh!: (v: { access: string }) => void;
    svc.refreshToken.mockReturnValue(
      new Promise((r) => {
        resolveRefresh = r;
      }),
    );
    const client = await freshClient();
    const seen: (unknown | undefined)[] = [];
    const adapter = vi.fn(async (c: InternalAxiosRequestConfig) => {
      const auth = (c.headers as Record<string, unknown>)["Authorization"];
      if (auth === "Bearer old") return fail(c, 401);
      seen.push(auth);
      return ok(c);
    });
    client.defaults.adapter = adapter;

    const p1 = client.get("/a"); // will start refresh
    const p2 = client.get("/b"); // will be queued
    await new Promise((r) => setTimeout(r, 0));

    svc.getAccessToken.mockReturnValue(null); // no token by flush time
    resolveRefresh({ access: "new" });
    await Promise.all([p1, p2]);

    // The queued retry (p2) had its Authorization header deleted.
    expect(seen).toContain(undefined);
  });
});
