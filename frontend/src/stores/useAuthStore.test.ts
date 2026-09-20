import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";

// `push` must exist before the hoisted vi.mock factory runs, so create it via
// vi.hoisted (a plain top-level const would be in the TDZ when the factory runs).
// It returns a resolved promise because the store both awaits it (login/register)
// and calls .catch() on it (logout).
const { push } = vi.hoisted(() => ({ push: vi.fn(() => Promise.resolve()) }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

// register() surfaces a "check your email" toast; mock it out.
vi.mock("vue-sonner", () => ({ toast: vi.fn() }));

// The store reads/writes apiClient.defaults.headers directly in setFromToken/clearAuth.
vi.mock("@/plugins/axios", () => ({
  default: { defaults: { headers: {} as Record<string, string> } },
  API_BASE_URL: "/api",
}));

// The network layer is exercised by authService.test.ts; here we mock it so the
// store's own logic (error mapping, token decode, navigation) is what's tested.
vi.mock("@/services/authService", () => ({
  authService: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshToken: vi.fn(),
    getAccessToken: vi.fn(),
  },
}));

import apiClient from "@/plugins/axios";
import { authService } from "@/services/authService";
import { useAuthStore } from "@/stores/useAuthStore";

const svc = authService as unknown as Record<string, ReturnType<typeof vi.fn>>;
const headers = () => (apiClient as unknown as { defaults: { headers: Record<string, string> } }).defaults.headers;

// A JWT whose payload round-trips through the store's atob(...) decode. btoa emits
// standard base64, which atob decodes — no base64url edge chars to trip on.
function jwt(payload: Record<string, unknown>) {
  return `h.${btoa(JSON.stringify(payload))}.s`;
}

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
  (apiClient as unknown as { defaults: { headers: Record<string, string> } }).defaults.headers = {};
});

describe("useAuthStore.init", () => {
  it("hydrates auth state from a stored token", () => {
    svc.getAccessToken.mockReturnValue(jwt({ user_id: 7, email: "a@b.com", username: "ana" }));
    const store = useAuthStore();

    store.init();

    expect(store.isAuthenticated).toBe(true);
    expect(store.userId).toBe(7);
    expect(store.userEmail).toBe("a@b.com");
    expect(store.username).toBe("ana");
    expect(headers()["Authorization"]).toMatch(/^Bearer /);
  });

  it("clears auth when there is no stored token", () => {
    svc.getAccessToken.mockReturnValue(null);
    const store = useAuthStore();

    store.init();

    expect(store.isAuthenticated).toBe(false);
    expect(headers()["Authorization"]).toBeUndefined();
  });
});

describe("useAuthStore.login", () => {
  it("stores the token, decodes the profile, and routes home on success", async () => {
    svc.login.mockResolvedValue({ access: jwt({ user_id: 1, email: "jose@example.com", username: "jose" }) });
    const store = useAuthStore();

    await store.login("jose@example.com", "pw", "ts");

    expect(svc.login).toHaveBeenCalledWith("jose@example.com", "pw", "ts");
    expect(store.isAuthenticated).toBe(true);
    expect(store.userEmail).toBe("jose@example.com");
    expect(push).toHaveBeenCalledWith({ name: "Home" });
    expect(store.loading).toBe(false);
    expect(store.error).toBe(null);
  });

  it("surfaces the server's detail message on failure and re-throws", async () => {
    svc.login.mockRejectedValue({ response: { data: { detail: "No active account found" } } });
    const store = useAuthStore();

    await expect(store.login("u", "bad")).rejects.toBeTruthy();

    expect(store.error).toBe("No active account found");
    expect(store.isAuthenticated).toBe(false);
    expect(store.loading).toBe(false);
    expect(push).not.toHaveBeenCalled();
  });

  it("falls back to a generic message when the error has no detail", async () => {
    svc.login.mockRejectedValue(new Error("network"));
    const store = useAuthStore();

    await expect(store.login("u", "p")).rejects.toThrow();
    expect(store.error).toBe("Invalid username or password.");
  });
});

describe("useAuthStore.register", () => {
  it("does not sign the user in and routes to Login on success", async () => {
    // Registration creates an inactive account (no session) — the user must
    // verify their email before signing in.
    svc.register.mockResolvedValue({ email: "new@example.com", detail: "Check your email." });
    const store = useAuthStore();

    await store.register("new@example.com", "pw", "pw", "ts");

    expect(svc.register).toHaveBeenCalledWith("new@example.com", "pw", "pw", "ts");
    expect(store.isAuthenticated).toBe(false);
    expect(push).toHaveBeenCalledWith({ name: "Login" });
    expect(store.loading).toBe(false);
  });

  // Regression guard for the `datail` -> `detail` typo: it must surface the
  // real server message, not the generic fallback.
  it("surfaces the server's detail message on failure (not the generic fallback)", async () => {
    svc.register.mockRejectedValue({ response: { data: { detail: "Email already in use." } } });
    const store = useAuthStore();

    await expect(store.register("dup@example.com", "pw", "pw")).rejects.toBeTruthy();

    expect(store.error).toBe("Email already in use.");
    expect(store.loading).toBe(false);
  });

  it("falls back to a generic message when the error has no detail", async () => {
    svc.register.mockRejectedValue(new Error("boom"));
    const store = useAuthStore();

    await expect(store.register("x@y.com", "pw", "pw")).rejects.toThrow();
    expect(store.error).toBe("Registration failed. Please try again.");
  });
});

describe("useAuthStore.logout", () => {
  it("clears service state, store state, and routes to Login", async () => {
    svc.login.mockResolvedValue({ access: jwt({ email: "a@b.com" }) });
    const store = useAuthStore();
    await store.login("a@b.com", "pw");
    expect(store.isAuthenticated).toBe(true);

    store.logout();

    expect(svc.logout).toHaveBeenCalledOnce();
    expect(store.isAuthenticated).toBe(false);
    expect(store.error).toBe(null);
    expect(headers()["Authorization"]).toBeUndefined();
    expect(push).toHaveBeenCalledWith({ name: "Login" });
  });
});

describe("useAuthStore.refresh", () => {
  it("swaps in the refreshed access token", async () => {
    svc.refreshToken.mockResolvedValue({ access: jwt({ email: "r@b.com" }) });
    const store = useAuthStore();

    await store.refresh();

    expect(store.isAuthenticated).toBe(true);
    expect(store.userEmail).toBe("r@b.com");
    expect(headers()["Authorization"]).toMatch(/^Bearer /);
  });
});

describe("useAuthStore — token decode", () => {
  it("stays authenticated but has no profile when the token can't be decoded", async () => {
    svc.login.mockResolvedValue({ access: "not-a-jwt" });
    const store = useAuthStore();

    await store.login("u", "p");

    expect(store.isAuthenticated).toBe(true); // token is still set
    expect(store.userId).toBe(null);
    expect(store.userEmail).toBe(null);
  });
});
