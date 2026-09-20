import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock @/plugins/axios BEFORE importing messageService: CHAT_URL is frozen from
// API_BASE_URL at module load. Mocking also avoids import.meta.env and the real
// axios<->authService import cycle.
vi.mock("@/plugins/axios", () => ({ API_BASE_URL: "/api", default: {} }));

const svc = vi.hoisted(() => ({
  getAccessToken: vi.fn<() => string | null>(),
  refreshToken: vi.fn<() => Promise<{ access: string }>>(),
  logout: vi.fn(),
}));
vi.mock("@/services/authService", () => ({ authService: svc }));

import { messageService, type Source } from "@/services/messageService";

const fetchMock = vi.fn();

// --- helpers -----------------------------------------------------------------

/** One SSE frame, terminated with the blank line the parser splits on. */
function frame(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** A streaming Response whose reader yields the given chunks (strings encoded to
 *  UTF-8) in order, then done. */
function streamResponse(chunks: (string | Uint8Array)[]) {
  const encoded = chunks.map((c) => (typeof c === "string" ? new TextEncoder().encode(c) : c));
  let i = 0;
  const reader = {
    read: vi.fn(async () =>
      i < encoded.length ? { done: false, value: encoded[i++] } : { done: true, value: undefined },
    ),
  };
  return { status: 200, ok: true, body: { getReader: () => reader }, json: async () => ({}) };
}

function errorResponse(status: number, json: () => Promise<unknown>) {
  return { status, ok: false, body: null, json };
}

// Each handler is a typed vi.fn: the signatures match StreamHandlers (so the
// object is a valid StreamHandlers when passed to streamMessage) while keeping
// `.mock` available in assertions.
function handlers() {
  return {
    onStatus: vi.fn<(step: string) => void>(),
    onDelta: vi.fn<(text: string) => void>(),
    onSources: vi.fn<(sources: Source[]) => void>(),
    onDone: vi.fn<(data: unknown) => void>(),
    onError: vi.fn<(detail: string) => void>(),
  };
}

const PAYLOAD = { user_message: "hi", conversation: "conv-uuid" };

beforeEach(() => {
  vi.clearAllMocks();
  svc.getAccessToken.mockReturnValue(null);
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("window", { location: { href: "" } });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamMessage — happy path", () => {
  it("dispatches status/delta/sources/done frames to the handlers in order", async () => {
    svc.getAccessToken.mockReturnValue("tok");
    fetchMock.mockResolvedValueOnce(
      streamResponse([
        frame("status", { step: "writing" }),
        frame("delta", { text: "Hi " }),
        frame("delta", { text: "there" }),
        frame("sources", { sources: [{ id: "s1", title: "USCIS" }] }),
        frame("done", { conversation: "conv-uuid" }),
      ]),
    );
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onStatus).toHaveBeenCalledWith("writing");
    expect(h.onDelta.mock.calls.map((c) => c[0])).toEqual(["Hi ", "there"]);
    expect(h.onSources).toHaveBeenCalledWith([{ id: "s1", title: "USCIS" }]);
    expect(h.onDone).toHaveBeenCalledWith({ conversation: "conv-uuid" });
    expect(h.onError).not.toHaveBeenCalled();
  });

  it("POSTs to /api/chat/ with JSON + Bearer header and the payload as body", async () => {
    svc.getAccessToken.mockReturnValue("tok");
    fetchMock.mockResolvedValueOnce(streamResponse([frame("done", {})]));

    await messageService.streamMessage(PAYLOAD, handlers());

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/chat/");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(JSON.parse(init.body)).toEqual(PAYLOAD);
  });

  it("omits the Authorization header when there is no token", async () => {
    svc.getAccessToken.mockReturnValue(null);
    fetchMock.mockResolvedValueOnce(streamResponse([frame("done", {})]));

    await messageService.streamMessage(PAYLOAD, handlers());

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it("passes the AbortSignal through to fetch", async () => {
    fetchMock.mockResolvedValueOnce(streamResponse([frame("done", {})]));
    const ctrl = new AbortController();

    await messageService.streamMessage(PAYLOAD, handlers(), ctrl.signal);

    expect(fetchMock.mock.calls[0][1].signal).toBe(ctrl.signal);
  });
});

describe("streamMessage — frame buffering", () => {
  it("reassembles a frame split across two reads", async () => {
    const f = frame("delta", { text: "hello" });
    fetchMock.mockResolvedValueOnce(streamResponse([f.slice(0, 12), f.slice(12)]));
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onDelta).toHaveBeenCalledExactlyOnceWith("hello");
  });

  it("reassembles a multibyte character split across reads", async () => {
    const bytes = new TextEncoder().encode(frame("delta", { text: "café" }));
    // "é" is 2 bytes; cut the buffer inside it so decode must span both reads.
    const cut = bytes.indexOf(0xc3) + 1; // first byte of the é sequence
    fetchMock.mockResolvedValueOnce(streamResponse([bytes.slice(0, cut), bytes.slice(cut)]));
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onDelta).toHaveBeenCalledExactlyOnceWith("café");
  });

  it("parses multiple frames delivered in a single read", async () => {
    fetchMock.mockResolvedValueOnce(
      streamResponse([frame("delta", { text: "a" }) + frame("delta", { text: "b" })]),
    );
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onDelta.mock.calls.map((c) => c[0])).toEqual(["a", "b"]);
  });
});

describe("streamMessage — error handling", () => {
  it("calls onError with the detail from an error frame", async () => {
    fetchMock.mockResolvedValueOnce(streamResponse([frame("error", { detail: "boom" })]));
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onError).toHaveBeenCalledWith("boom");
  });

  it("falls back to a default message when an error frame has no detail", async () => {
    fetchMock.mockResolvedValueOnce(streamResponse([frame("error", {})]));
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onError).toHaveBeenCalledWith("The assistant failed to respond.");
  });

  it("calls onError with the server detail on a non-OK response", async () => {
    fetchMock.mockResolvedValueOnce(errorResponse(400, async () => ({ detail: "bad request" })));
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onError).toHaveBeenCalledWith("bad request");
  });

  it("uses a generic message when the error body is not JSON", async () => {
    fetchMock.mockResolvedValueOnce(
      errorResponse(500, async () => {
        throw new Error("not json");
      }),
    );
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onError).toHaveBeenCalledWith("Request failed. Please try again.");
  });

  it("silently ignores malformed JSON and unknown/bare event frames", async () => {
    fetchMock.mockResolvedValueOnce(
      streamResponse([
        "event: delta\ndata: {not valid json}\n\n", // bad JSON
        "event: message\ndata: {}\n\n", // unknown event kind
        "data: {}\n\n", // bare data, defaults to "message"
      ]),
    );
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(h.onDelta).not.toHaveBeenCalled();
    expect(h.onError).not.toHaveBeenCalled();
    expect(h.onDone).not.toHaveBeenCalled();
  });

  it("rejects when fetch itself rejects (abort / network error)", async () => {
    fetchMock.mockRejectedValueOnce(new DOMException("aborted", "AbortError"));

    await expect(messageService.streamMessage(PAYLOAD, handlers())).rejects.toThrow();
  });
});

describe("streamMessage — 401 refresh", () => {
  it("refreshes once and retries the stream on a 401", async () => {
    fetchMock
      .mockResolvedValueOnce(errorResponse(401, async () => ({})))
      .mockResolvedValueOnce(streamResponse([frame("delta", { text: "ok" }), frame("done", {})]));
    svc.refreshToken.mockResolvedValue({ access: "new" });
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(svc.refreshToken).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(h.onDelta).toHaveBeenCalledWith("ok");
  });

  it("logs out and redirects when the refresh fails, firing no handlers", async () => {
    fetchMock.mockResolvedValueOnce(errorResponse(401, async () => ({})));
    svc.refreshToken.mockRejectedValue(new Error("refresh failed"));
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(svc.logout).toHaveBeenCalledOnce();
    expect(window.location.href).toBe("/login");
    expect(h.onError).not.toHaveBeenCalled();
    expect(h.onDelta).not.toHaveBeenCalled();
  });

  it("reports an error when a second 401 arrives after the retry", async () => {
    fetchMock
      .mockResolvedValueOnce(errorResponse(401, async () => ({})))
      .mockResolvedValueOnce(errorResponse(401, async () => ({ detail: "still unauthorized" })));
    svc.refreshToken.mockResolvedValue({ access: "new" });
    const h = handlers();

    await messageService.streamMessage(PAYLOAD, h);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(h.onError).toHaveBeenCalledWith("still unauthorized");
  });
});
