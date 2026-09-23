import { createI18n } from "vue-i18n";
import en from "@/locales/en.json";

/**
 * App i18n. The initial locale is resolved once at boot (see `resolveLocale`),
 * persisted per-viewer in localStorage, and switchable from the sidebar's
 * LanguageSwitcher. `setLocale` is the single writer.
 *
 * SUPPORTED_LOCALES and DEFAULT_LOCALE mirror /i18n/supported-locales.json, and
 * each locale's catalog lives in src/locales/<code>.json. CI
 * (scripts/check_i18n_parity.mjs) fails if the lists drift or a catalog's keys
 * differ from the default one.
 *
 * Only the default (fallback) catalog is bundled; every other catalog is a
 * separate chunk fetched by `loadLocaleMessages` the first time it is needed.
 */
export const SUPPORTED_LOCALES = ["en", "es"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

const STORAGE_KEY = "visanav_locale";
/** Query param the marketing site appends on outbound links to hand off its locale. */
export const HANDOFF_PARAM = "lang";

/** Official DOJ EOIR Recognition & Accreditation roster (verified 2026-09). */
export const EOIR_ROSTER_URL =
  "https://www.justice.gov/eoir/recognition-accreditation-roster-reports";

export function isLocale(v: unknown): v is Locale {
  return (SUPPORTED_LOCALES as readonly unknown[]).includes(v);
}

/**
 * Map a raw language tag onto the allowlist: an exact (case-insensitive) match
 * first, so "zh-Hans" survives, then its base language ("es-MX" -> "es").
 */
export function toLocale(raw: string | null | undefined): Locale | null {
  if (!raw) return null;
  const lower = raw.trim().toLowerCase();
  const exact = SUPPORTED_LOCALES.find((l) => l.toLowerCase() === lower);
  if (exact) return exact;
  const base = lower.split("-")[0];
  return SUPPORTED_LOCALES.find((l) => l.toLowerCase() === base) ?? null;
}

/**
 * First-load precedence, as documented in docs/i18n-architecture.md:
 * `?lang=` handoff > saved choice > browser language > default.
 */
export function resolveLocale(sources: {
  param?: string | null;
  saved?: string | null;
  browser?: string | null;
}): Locale {
  return (
    toLocale(sources.param) ??
    (isLocale(sources.saved) ? sources.saved : null) ??
    toLocale(sources.browser) ??
    DEFAULT_LOCALE
  );
}

function readSaved(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null; // blocked/unavailable storage (private mode, SSR, tests)
  }
}

function writeSaved(locale: Locale) {
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    /* ignore blocked/unavailable storage */
  }
}

/** Whether this viewer has an explicitly chosen (persisted) locale. */
export function hasSavedLocale(): boolean {
  return isLocale(readSaved());
}

/**
 * The cross-origin `?lang=` handoff, read once when this module loads (before
 * the router's first navigation settles). The router strips the param from the
 * address bar (see `HANDOFF_PARAM` in router.ts), so a shared or bookmarked URL
 * doesn't keep overriding a later choice.
 */
const handoffParam: string | null = (() => {
  try {
    return new URL(window.location.href).searchParams.get(HANDOFF_PARAM);
  } catch {
    return null; // no window (SSR, tests)
  }
})();

function detectLocale(): Locale {
  const param = handoffParam;
  const locale = resolveLocale({
    param,
    saved: readSaved(),
    browser: typeof navigator !== "undefined" ? navigator.language : null,
  });
  // A valid handoff is an explicit choice made on the marketing site: keep it.
  if (toLocale(param)) writeSaved(locale);
  return locale;
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true, // $t / <i18n-t> available in templates without useI18n
  locale: DEFAULT_LOCALE, // switched to the detected locale by initLocale()
  fallbackLocale: DEFAULT_LOCALE,
  // Typed as covering every Locale (only "en" is bundled) so lazily-loaded
  // catalogs can be registered and selected; `en` is their shared schema.
  messages: { en } as Record<Locale, typeof en>,
});

// Every non-default catalog, as a lazily-imported chunk.
const loaders = import.meta.glob<{ default: Record<string, unknown> }>([
  "../locales/*.json",
  "!../locales/en.json", // bundled above as the fallback
]);

/** Fetch and register a locale's catalog if it isn't loaded yet. */
export async function loadLocaleMessages(locale: Locale): Promise<void> {
  if (i18n.global.availableLocales.includes(locale)) return;
  const load = loaders[`../locales/${locale}.json`];
  if (!load) throw new Error(`No catalog for locale "${locale}"`);
  const mod = await load();
  i18n.global.setLocaleMessage(locale, mod.default as typeof en);
}

/**
 * The active locale, for non-component callers (the axios client and the native
 * `fetch` SSE stream) that set the `Accept-Language` header on API requests. The
 * backend's LocaleMiddleware negotiates this into `request.LANGUAGE_CODE`.
 */
export function currentLocale(): Locale {
  return i18n.global.locale.value as Locale;
}

function applyLocale(locale: Locale) {
  i18n.global.locale.value = locale;
  try {
    document.documentElement.setAttribute("lang", locale);
  } catch {
    /* SSR / no document */
  }
}

/**
 * Resolve the initial locale and load its catalog. Awaited before mount so the
 * first paint is already in the right language. A failed catalog fetch leaves
 * the app in the default locale rather than blocking boot.
 */
export async function initLocale(): Promise<void> {
  const locale = detectLocale();
  try {
    await loadLocaleMessages(locale);
    applyLocale(locale);
  } catch {
    applyLocale(DEFAULT_LOCALE);
  }
}

/** Change the active locale and remember it for next time. */
export async function setLocale(locale: Locale): Promise<void> {
  await loadLocaleMessages(locale);
  applyLocale(locale);
  writeSaved(locale);
}
