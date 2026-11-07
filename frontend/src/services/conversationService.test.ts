import { describe, it, expect, vi, beforeEach } from "vitest";

const api = vi.hoisted(() => ({ post: vi.fn(), get: vi.fn() }));
vi.mock("@/plugins/axios", () => ({ default: api }));

import { conversationService } from "@/services/conversationService";

beforeEach(() => vi.clearAllMocks());

describe("conversationService.setFeedback", () => {
  it("posts the rating to the conversation's feedback endpoint", async () => {
    api.post.mockResolvedValue({ data: { message: 7, is_helpful: true } });

    const res = await conversationService.setFeedback("u1", 7, true);

    expect(api.post).toHaveBeenCalledWith("/conversations/u1/feedback/", {
      message: 7,
      is_helpful: true,
    });
    expect(res).toEqual({ message: 7, is_helpful: true });
  });

  it("sends null to clear a rating", async () => {
    api.post.mockResolvedValue({ data: { message: 7, is_helpful: null } });
    await conversationService.setFeedback("u1", 7, null);
    expect(api.post.mock.calls[0][1]).toEqual({ message: 7, is_helpful: null });
  });
});
