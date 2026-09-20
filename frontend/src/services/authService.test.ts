import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock the axios client the service talks to. Mocking the module also breaks the
// real axios.ts <-> authService import cycle and avoids touching import.meta.env,
// so these tests stay pure and DOM-free.
vi.mock("@/plugins/axios.ts", () => {
  const apiClient = {
    post: vi.fn(),
    get: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    defaults: { headers: {} as Record<string, string> },
  };
  return { default: apiClient, API_BASE_URL: "/api" };
});

import apiClient from "@/plugins/axios.ts";
import { authService } from "@/services/authService";

const post = apiClient.post as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => store.set(k, String(v)),
    removeItem: (k: string) => store.delete(k),
    clear: () => store.clear(),
  });
  post.mockReset();
  (apiClient as unknown as { defaults: { headers: Record<string, string> } }).defaults.headers = {};
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("authService.login", () => {
  it("posts credentials, persists both tokens, and sets the auth header", async () => {
    post.mockResolvedValueOnce({ data: { access: "acc", refresh: "ref" } });

    const result = await authService.login("jose@example.com", "pw", "ts-token");

    expect(result).toEqual({ access: "acc", refresh: "ref" });
    expect(post).toHaveBeenCalledTimes(1);
    const [url, body] = post.mock.calls[0];
    expect(url).toBe("/auth/token/");
    expect(body).toMatchObject({
      username: "jose@example.com",
      password: "pw",
      turnstile_token: "ts-token",
    });
    expect(localStorage.getItem("access_token")).toBe("acc");
    expect(localStorage.getItem("refresh_token")).toBe("ref");
    expect(apiClient.defaults.headers["Authorization"]).toBe("Bearer acc");
  });

  it("defaults the turnstile token to an empty string when omitted", async () => {
    post.mockResolvedValueOnce({ data: { access: "a", refresh: "r" } });
    await authService.login("u", "p");
    expect(post.mock.calls[0][1]).toMatchObject({ turnstile_token: "" });
  });

  it("propagates a rejected request without writing tokens", async () => {
    post.mockRejectedValueOnce(new Error("401"));
    await expect(authService.login("u", "bad")).rejects.toThrow("401");
    expect(localStorage.getItem("access_token")).toBe(null);
  });
});

describe("authService.register", () => {
  it("posts to the register endpoint and returns the body without a session", async () => {
    // Registration no longer issues tokens — the account is created inactive.
    post.mockResolvedValueOnce({ data: { email: "new@example.com", detail: "Check your email." } });

    const result = await authService.register("new@example.com", "pw", "pw", "ts");

    expect(result).toEqual({ email: "new@example.com", detail: "Check your email." });
    const [url, body] = post.mock.calls[0];
    expect(url).toBe("/auth/register/");
    expect(body).toMatchObject({
      email: "new@example.com",
      password: "pw",
      password2: "pw",
      turnstile_token: "ts",
    });
    // No tokens are stored and no auth header is set.
    expect(localStorage.getItem("access_token")).toBe(null);
    expect(apiClient.defaults.headers["Authorization"]).toBeUndefined();
  });
});

describe("authService.verify", () => {
  it("posts uid/token, stores the returned session, and sets the auth header", async () => {
    post.mockResolvedValueOnce({ data: { userId: 7, access: "vacc", refresh: "vref" } });

    const result = await authService.verify("uid-123", "tok-456");

    expect(result).toEqual({ userId: 7, access: "vacc", refresh: "vref" });
    expect(post).toHaveBeenCalledWith("/auth/verify", { uid: "uid-123", token: "tok-456" });
    expect(localStorage.getItem("access_token")).toBe("vacc");
    expect(localStorage.getItem("refresh_token")).toBe("vref");
    expect(apiClient.defaults.headers["Authorization"]).toBe("Bearer vacc");
  });
});

describe("authService.logout", () => {
  it("clears both tokens and the auth header", () => {
    localStorage.setItem("access_token", "a");
    localStorage.setItem("refresh_token", "r");
    apiClient.defaults.headers["Authorization"] = "Bearer a";

    authService.logout();

    expect(localStorage.getItem("access_token")).toBe(null);
    expect(localStorage.getItem("refresh_token")).toBe(null);
    expect(apiClient.defaults.headers["Authorization"]).toBeUndefined();
  });
});

describe("authService.getAccessToken", () => {
  it("returns the stored token, or null when absent", () => {
    expect(authService.getAccessToken()).toBe(null);
    localStorage.setItem("access_token", "here");
    expect(authService.getAccessToken()).toBe("here");
  });
});

describe("authService.refreshToken", () => {
  it("throws when there is no refresh token", async () => {
    await expect(authService.refreshToken()).rejects.toThrow("No refresh token");
    expect(post).not.toHaveBeenCalled();
  });

  it("exchanges the refresh token and rotates the access token", async () => {
    localStorage.setItem("refresh_token", "old-ref");
    post.mockResolvedValueOnce({ data: { access: "new-acc", refresh: "new-ref" } });

    const result = await authService.refreshToken();

    expect(post).toHaveBeenCalledWith("/auth/token/refresh/", { refresh: "old-ref" });
    expect(result).toEqual({ access: "new-acc", refresh: "new-ref" });
    expect(localStorage.getItem("access_token")).toBe("new-acc");
    expect(localStorage.getItem("refresh_token")).toBe("new-ref");
    expect(apiClient.defaults.headers["Authorization"]).toBe("Bearer new-acc");
  });

  it("keeps the existing refresh token when the server omits a new one", async () => {
    localStorage.setItem("refresh_token", "keep-me");
    post.mockResolvedValueOnce({ data: { access: "fresh" } });

    const result = await authService.refreshToken();

    expect(result).toEqual({ access: "fresh", refresh: "keep-me" });
    expect(localStorage.getItem("refresh_token")).toBe("keep-me");
  });
});
