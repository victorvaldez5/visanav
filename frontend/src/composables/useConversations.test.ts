import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref } from "vue";

// `onUnmounted` needs an active component instance; stub just that named export
// and keep the real reactivity (ref/watch) so the composable runs standalone.
vi.mock("vue", async (importOriginal) => {
  const actual = await importOriginal<typeof import("vue")>();
  return { ...actual, onUnmounted: vi.fn() };
});

// Router / i18n / toast are injection- or plugin-backed; mock them so the
// composable's own logic (streaming orchestration, PII, navigation) is what's
// under test. `push` is created via vi.hoisted so the factory can close over it.
const { push } = vi.hoisted(() => ({ push: vi.fn(() => Promise.resolve()) }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));
vi.mock("vue-i18n", () => ({ useI18n: () => ({ locale: { value: "en" } }) }));

const { toast } = vi.hoisted(() => ({ toast: vi.fn() }));
vi.mock("vue-sonner", () => ({ toast }));

// Scrubbing is covered by usePiiScrubber.test.ts / pii.test.ts; here we stub it
// so we can drive the "changed" branch deterministically.
const { scrub } = vi.hoisted(() => ({ scrub: vi.fn() }));
vi.mock("@/composables/usePiiScrubber", () => ({ usePiiScrubber: () => ({ scrub }) }));

const convSvc = vi.hoisted(() => ({
  getConversation: vi.fn(),
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
}));
vi.mock("@/services/conversationService", () => ({ conversationService: convSvc }));

// The SSE transport is covered by messageService.test.ts; here it's a seam we
// drive by invoking the handlers it's given.
const msgSvc = vi.hoisted(() => ({ streamMessage: vi.fn() }));
vi.mock("@/services/messageService", () => ({ messageService: msgSvc }));

import { useConversation } from "@/composables/useConversations";

const ANON_KEY = "visanav.anonConversationUuid";

// A minimal in-memory sessionStorage stub for the anonymous-resume tests (the
// node test env has no sessionStorage; the composable guards every access).
function stubSessionStorage(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial));
  vi.stubGlobal("sessionStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => store.set(k, String(v)),
    removeItem: (k: string) => store.delete(k),
  });
  return store;
}

// Flush pending micro/macrotasks (awaited service calls inside watch/postMessage).
const flush = () => new Promise((r) => setTimeout(r, 0));

// Build the composable with a given route uuid ref (null = no immediate fetch).
function setup(uuid: string | null = null) {
  const u = ref<string | null>(uuid);
  return { u, ...useConversation(u) };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
  scrub.mockImplementation((text: string) => ({ text, summary: {}, changed: false }));
});

describe("useConversation — loading on route change", () => {
  it("fetches the conversation and hydrates history when the uuid is set", async () => {
    convSvc.getConversation.mockResolvedValue({ id: 5, uuid: "u1", messages: [{ a: 1 }] });

    const c = setup("u1");
    await flush();

    expect(convSvc.getConversation).toHaveBeenCalledWith("u1");
    expect(c.conversationId.value).toBe(5);
    expect(c.messageHistory.value).toEqual([{ a: 1 }]);
  });

  it("clears history without fetching when the uuid is null", async () => {
    const c = setup(null);
    await flush();

    expect(convSvc.getConversation).not.toHaveBeenCalled();
    expect(c.messageHistory.value).toEqual([]);
  });

  it("toasts and redirects home when the fetch is rejected", async () => {
    convSvc.getConversation.mockRejectedValue(new Error("forbidden"));

    setup("u1");
    await flush();

    expect(toast).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith({ name: "Home" });
  });
});

describe("useConversation — createConversation", () => {
  it("creates, stores the id/key, and returns the conversation", async () => {
    convSvc.createConversation.mockResolvedValue({ id: 9, uuid: "new-uuid", title: "t", messages: [] });

    const c = setup(null);
    const conv = await c.createConversation(1, "My chat");

    expect(convSvc.createConversation).toHaveBeenCalledWith("My chat", 1);
    expect(conv.uuid).toBe("new-uuid");
    expect(c.conversationId.value).toBe(9);
  });
});

describe("useConversation — postMessage guards", () => {
  it("does nothing when there is no conversation key yet", async () => {
    const c = setup(null);
    await c.postMessage("hello");
    expect(msgSvc.streamMessage).not.toHaveBeenCalled();
  });

  it("does nothing for a blank prompt", async () => {
    convSvc.createConversation.mockResolvedValue({ id: 1, uuid: "k", title: "", messages: [] });
    const c = setup(null);
    await c.createConversation(1);

    await c.postMessage("   ");

    expect(msgSvc.streamMessage).not.toHaveBeenCalled();
  });
});

describe("useConversation — postMessage streaming", () => {
  async function withKey() {
    convSvc.createConversation.mockResolvedValue({ id: 1, uuid: "k", title: "", messages: [] });
    const c = setup(null);
    await c.createConversation(1);
    return c;
  }

  it("sends the scrubbed payload and syncs with the server on success", async () => {
    msgSvc.streamMessage.mockImplementation(async (_payload, h) => {
      h.onStatus("writing");
      h.onDelta("Hi ");
      h.onDelta("there");
      h.onSources([{ id: "s1" }]);
      h.onDone({ conversation: "k" });
    });
    convSvc.getConversation.mockResolvedValue({ id: 1, uuid: "k", messages: [{ server: true }] });

    const c = await withKey();
    await c.postMessage("Question?");

    expect(msgSvc.streamMessage).toHaveBeenCalledOnce();
    expect(msgSvc.streamMessage.mock.calls[0][0]).toEqual({
      user_message: "Question?",
      conversation: "k",
    });
    // On a successful turn, history is replaced with the server's canonical rows.
    expect(convSvc.getConversation).toHaveBeenCalledWith("k");
    expect(c.messageHistory.value).toEqual([{ server: true }]);
    expect(c.isStreaming.value).toBe(false);
    expect(c.streamStatus.value).toBe(null);
  });

  it("accumulates deltas and sources into the optimistic assistant bubble", async () => {
    msgSvc.streamMessage.mockImplementation(async (_payload, h) => {
      h.onDelta("Hi ");
      h.onDelta("there");
      h.onSources([{ id: "s1" }]);
      h.onDone({});
    });
    // Refresh fails, so the optimistic bubbles remain to be asserted.
    convSvc.getConversation.mockRejectedValue(new Error("refresh failed"));

    const c = await withKey();
    await c.postMessage("Q");

    const hist = c.messageHistory.value;
    expect(hist).toHaveLength(2);
    expect(hist[0].parts[0].content).toBe("Q"); // user bubble (scrubbed text)
    expect(hist[1].parts[0].content).toBe("Hi there");
    expect(hist[1].sources).toEqual([{ id: "s1" }]);
  });

  it("sends only the scrubbed text and records a scrub notice when PII is removed", async () => {
    scrub.mockReturnValue({ text: "REDACTED", summary: { emails: 1 }, changed: true });
    msgSvc.streamMessage.mockImplementation(async (_payload, h) => h.onDone({}));
    convSvc.getConversation.mockResolvedValue({ id: 1, uuid: "k", messages: [] });

    const c = await withKey();
    await c.postMessage("my email is a@b.com");

    expect(msgSvc.streamMessage.mock.calls[0][0].user_message).toBe("REDACTED");
    expect(c.scrubNotices.value.get("REDACTED")).toEqual({ emails: 1 });
  });

  it("shows the error in the assistant bubble and does not refresh on onError", async () => {
    msgSvc.streamMessage.mockImplementation(async (_payload, h) => h.onError("boom"));

    const c = await withKey();
    await c.postMessage("Q");

    expect(c.messageHistory.value[1].parts[0].content).toBe("⚠️ boom");
    expect(toast).toHaveBeenCalledWith("Something went wrong", { description: "boom" });
    expect(convSvc.getConversation).not.toHaveBeenCalled(); // turn didn't succeed
    expect(c.isStreaming.value).toBe(false);
  });

  it("toasts and resets streaming when the stream itself rejects (abort/network)", async () => {
    msgSvc.streamMessage.mockRejectedValue(new DOMException("aborted", "AbortError"));

    const c = await withKey();
    await c.postMessage("Q");

    expect(toast).toHaveBeenCalledWith("Something went wrong", { description: "Please try again later" });
    expect(c.isStreaming.value).toBe(false);
    expect(convSvc.getConversation).not.toHaveBeenCalled();
  });
});

describe("useConversation — deleteConversation", () => {
  it("deletes the active conversation via the service and resets state", async () => {
    convSvc.createConversation.mockResolvedValue({ id: 3, uuid: "kdel", title: "", messages: [] });
    convSvc.deleteConversation.mockResolvedValue(undefined);

    const c = setup(null);
    await c.createConversation(1);
    expect(c.conversationKey.value).toBe("kdel");

    await c.deleteConversation();

    expect(convSvc.deleteConversation).toHaveBeenCalledWith("kdel");
    expect(c.conversationKey.value).toBe(null);
    expect(c.conversationId.value).toBe(null);
    expect(c.messageHistory.value).toEqual([]);
  });

  it("no-ops when there is no active conversation", async () => {
    const c = setup(null);
    await c.deleteConversation();
    expect(convSvc.deleteConversation).not.toHaveBeenCalled();
  });
});

describe("useConversation — anonymous resume (uuid never in the URL)", () => {
  it("persists a created anonymous conversation and resumes it on reload", async () => {
    const store = stubSessionStorage();
    convSvc.createConversation.mockResolvedValue({ id: 7, uuid: "anon-uuid", title: "", messages: [] });

    // Anonymous is the default (no isAuthenticated getter): creating writes the key.
    const first = setup(null);
    await first.createConversation();
    expect(store.get(ANON_KEY)).toBe("anon-uuid");

    // A "reload" — a fresh composable with no route uuid — resumes from storage.
    convSvc.getConversation.mockResolvedValue({ id: 7, uuid: "anon-uuid", messages: [{ r: 1 }] });
    const reloaded = setup(null);
    await flush();

    expect(convSvc.getConversation).toHaveBeenCalledWith("anon-uuid");
    expect(reloaded.conversationKey.value).toBe("anon-uuid");
    expect(reloaded.messageHistory.value).toEqual([{ r: 1 }]);

    vi.unstubAllGlobals();
  });

  it("clears the stored key and resets when the resumed chat is gone", async () => {
    const store = stubSessionStorage({ [ANON_KEY]: "stale-uuid" });
    convSvc.getConversation.mockRejectedValue(new Error("404"));

    const c = setup(null);
    await flush();

    expect(convSvc.getConversation).toHaveBeenCalledWith("stale-uuid");
    expect(store.get(ANON_KEY)).toBeUndefined(); // stale key cleared
    expect(c.messageHistory.value).toEqual([]);
    // A dead resume must NOT trigger the "not allowed" toast/redirect path.
    expect(toast).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it("does not resume from storage for a signed-in user", async () => {
    stubSessionStorage({ [ANON_KEY]: "anon-uuid" });

    const u = ref<string | null>(null);
    const c = useConversation(u, { isAuthenticated: () => true });
    await flush();

    expect(convSvc.getConversation).not.toHaveBeenCalled();
    expect(c.messageHistory.value).toEqual([]);

    vi.unstubAllGlobals();
  });
});
