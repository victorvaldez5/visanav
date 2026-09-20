import { computed, ref, toValue, type MaybeRefOrGetter } from "vue";
import {
  scrubPII,
  describeScrub,
  type PiiSummary,
  type ScrubResult,
} from "@/lib/pii";

/**
 * Reactive wrapper around the pure PII scrubber.
 *
 * `lang` may be a ref, a getter, or a plain value; the `notice` re-renders when
 * it changes, so switching locale re-localizes the last notice.
 *
 * Returns:
 *  - scrub(text): scrub a message; records the summary and returns the result.
 *  - notice: friendly, localized "we removed …" string ("" when nothing removed).
 *  - lastSummary: counts from the last scrub (null when nothing removed / cleared).
 *  - clearNotice(): drop the current notice (e.g. after it has been shown).
 */
export function usePiiScrubber(lang: MaybeRefOrGetter<string>) {
  const lastSummary = ref<PiiSummary | null>(null);

  function scrub(text: string): ScrubResult {
    const result = scrubPII(text);
    // Only surface a notice when something was actually removed.
    lastSummary.value = result.changed ? result.summary : null;
    return result;
  }

  const notice = computed(() =>
    describeScrub(lastSummary.value, toValue(lang) === "es" ? "es" : "en"),
  );

  function clearNotice() {
    lastSummary.value = null;
  }

  return { scrub, notice, lastSummary, clearNotice };
}
