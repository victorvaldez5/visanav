import {onBeforeUnmount, onMounted, ref, type ShallowRef} from "vue";
import {loadTurnstile, TURNSTILE_SITE_KEY} from "@/lib/turnstile";

/**
 * Renders a Turnstile widget into the given element ref and tracks the current
 * token. Explicit render (not the implicit auto-scan) so it works with SPA
 * components that mount/unmount. Pass the element ref from `useTemplateRef`:
 *
 *   const el = useTemplateRef<HTMLElement>("turnstile");
 *   const { token, reset } = useTurnstile(el);
 *   <div ref="turnstile" />
 */
export function useTurnstile(el: Readonly<ShallowRef<HTMLElement | null>>) {
    const token = ref("");
    let widgetId: string | undefined;

    onMounted(async () => {
        try {
            await loadTurnstile();
            if (!el.value || !window.turnstile) return;
            widgetId = window.turnstile.render(el.value, {
                sitekey: TURNSTILE_SITE_KEY,
                theme: "auto",
                callback: (t: string) => (token.value = t),
                "error-callback": () => (token.value = ""),
                "expired-callback": () => (token.value = ""),
            });
        } catch {
            // Fail open on load error; the API still enforces when configured.
        }
    });

    onBeforeUnmount(() => {
        try {
            if (widgetId) window.turnstile?.remove(widgetId);
        } catch {
            /* ignore */
        }
    });

    /** Clear the token and refresh the widget (Turnstile tokens are single-use). */
    function reset() {
        token.value = "";
        try {
            if (widgetId) window.turnstile?.reset(widgetId);
        } catch {
            /* ignore */
        }
    }

    return {token, reset};
}
