import { createI18n } from "vue-i18n";
import en from "@/locales/en.json";
import es from "@/locales/es.json";

/**
 * App i18n. The current locale is detected from the browser (default English),
 * persisted per-viewer in localStorage, and switchable via the banner's language
 * toggle. `setLocale` is the single writer.
 *
 * SUPPORTED_LOCALES and DEFAULT_LOCALE mirror /i18n/supported-locales.json, and
 * each locale's catalog lives in src/locales/<code>.json. CI
 * (scripts/check_i18n_parity.mjs) fails if the lists drift or a catalog's keys
 * differ from the default one.
 */
export const SUPPORTED_LOCALES = ["en", "es"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

const STORAGE_KEY = "visanav_locale";

/** Official DOJ EOIR Recognition & Accreditation roster (verified 2026-09). */
export const EOIR_ROSTER_URL =
  "https://www.justice.gov/eoir/recognition-accreditation-roster-reports";

function isLocale(v: unknown): v is Locale {
  return (SUPPORTED_LOCALES as readonly unknown[]).includes(v);
}

function detectLocale(): Locale {
  // A previously chosen locale wins; storage may be unavailable (private mode).
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLocale(saved)) return saved;
  } catch {
    /* ignore blocked/unavailable storage */
  }
  // Otherwise the browser's base language ("es-MX" -> "es"), if supported.
  const base = (navigator.language || "").toLowerCase().split("-")[0];
  return isLocale(base) ? base : DEFAULT_LOCALE;
}

export const messages = { en, es };

export const i18n = createI18n({
  legacy: false,
  globalInjection: true, // $t / <i18n-t> available in templates without useI18n
  locale: detectLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages,
});

/**
 * The active locale, for non-component callers (the axios client and the native
 * `fetch` SSE stream) that set the `Accept-Language` header on API requests. The
 * backend's LocaleMiddleware negotiates this into `request.LANGUAGE_CODE`.
 */
export function currentLocale(): Locale {
  return i18n.global.locale.value as Locale;
}

/** Change the active locale and remember it for next time. */
export function setLocale(locale: Locale) {
  i18n.global.locale.value = locale;
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    /* ignore blocked/unavailable storage */
  }
  syncHtmlLang();
}

function syncHtmlLang() {
  try {
    document.documentElement.setAttribute("lang", i18n.global.locale.value);
  } catch {
    /* SSR / no document */
  }
}

syncHtmlLang();
