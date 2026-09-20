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

const convSvc = vi.hoisted(() => ({ getConversation: vi.fn(), createConversation: vi.fn() }));
vi.mock("@/services/conversationService", () => ({ conversationService: convSvc }));

// The SSE transport is covered by messageService.test.ts; here it's a seam we
// drive by invoking the handlers it's given.
const msgSvc = vi.hoisted(() => ({ streamMessage: vi.fn() }));
vi.mock("@/services/messageService", () => ({ messageService: msgSvc }));

import { useConversation } from "@/composables/useConversations";

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
