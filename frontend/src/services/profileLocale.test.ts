import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/services/authService", () => ({
  authService: { getProfile: vi.fn(), updateProfile: vi.fn() },
}));

import { authService } from "@/services/authService";
import { currentLocale, setLocale } from "@/i18n";
import { syncLocaleOnLogin } from "@/services/profileLocale";

const svc = authService as unknown as Record<string, ReturnType<typeof vi.fn>>;

beforeEach(async () => {
  vi.clearAllMocks();
  await setLocale("en");
});

describe("syncLocaleOnLogin", () => {
  it("adopts the profile's language when the browser has no saved choice", async () => {
    svc.getProfile.mockResolvedValue({ preferred_language: "es" });

    await syncLocaleOnLogin(1, false, "en");

    expect(currentLocale()).toBe("es");
    expect(svc.updateProfile).not.toHaveBeenCalled();
  });

  it("writes the browser's choice through when one was saved", async () => {
    await syncLocaleOnLogin(1, true, "es");

    expect(svc.getProfile).not.toHaveBeenCalled();
    expect(svc.updateProfile).toHaveBeenCalledWith(1, { preferred_language: "es" });
  });

  it("writes through when the profile has no usable language", async () => {
    svc.getProfile.mockResolvedValue({ preferred_language: null });

    await syncLocaleOnLogin(1, false, "en");

    expect(currentLocale()).toBe("en");
    expect(svc.updateProfile).toHaveBeenCalledWith(1, { preferred_language: "en" });
  });

  it("never throws when the API fails", async () => {
    svc.getProfile.mockRejectedValue(new Error("offline"));

    await expect(syncLocaleOnLogin(1, false, "en")).resolves.toBeUndefined();
  });
});
