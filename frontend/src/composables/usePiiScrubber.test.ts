import { describe, it, expect } from "vitest";
import { ref, nextTick } from "vue";
import { usePiiScrubber } from "@/composables/usePiiScrubber";

describe("usePiiScrubber", () => {
  it("scrubs, records the summary, and localizes the notice (ref lang)", async () => {
    const lang = ref<"en" | "es">("en");
    const { scrub, notice, lastSummary } = usePiiScrubber(lang);

    const result = scrub("my A-number is A123456789");
    expect(result.text).toBe("my A-number is [A-NUMBER]");
    expect(lastSummary.value).toEqual({ aNumber: 1 });
    expect(notice.value).toBe(
      "For your privacy, we removed 1 A-number before sending.",
    );

    // Switching locale re-localizes the existing notice.
    lang.value = "es";
    await nextTick();
    expect(notice.value).toBe(
      "Para proteger tu privacidad, quitamos 1 número A antes de enviar.",
    );
  });

  it("supports a (reactive) getter for lang", async () => {
    const l = ref<"en" | "es">("es");
    const { scrub, notice } = usePiiScrubber(() => l.value);
    scrub("correo test@example.com");
    expect(notice.value).toContain("Para proteger tu privacidad");
    l.value = "en";
    await nextTick();
    expect(notice.value).toContain("For your privacy");
  });

  it("gives no notice when nothing is removed, and clearNotice resets it", () => {
    const { scrub, notice, lastSummary, clearNotice } = usePiiScrubber(ref("en"));

    scrub("how do I renew my green card?");
    expect(lastSummary.value).toBeNull();
    expect(notice.value).toBe("");

    scrub("call 816-555-1234");
    expect(notice.value).not.toBe("");
    clearNotice();
    expect(lastSummary.value).toBeNull();
    expect(notice.value).toBe("");
  });
});
