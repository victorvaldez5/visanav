// Marketing-site i18n. Locale lives in the URL (`/` is English, `/es/` Spanish) and
// the URL is authoritative: no Accept-Language redirect, which hurts SEO and
// surprises people. SUPPORTED_LOCALES and DEFAULT_LOCALE mirror
// /i18n/supported-locales.json (CI-checked against astro.config.mjs, and the
// catalogs next to this file are checked key-for-key against en.json).
import en from "./en.json";
import es from "./es.json";

export const SUPPORTED_LOCALES = ["en", "es"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

/** Each locale's name in its own language, for the switcher. */
export const LOCALE_NAMES: Record<Locale, string> = { en: "English", es: "Español" };

const catalogs: Record<Locale, Record<string, unknown>> = { en, es };

export function isLocale(v: unknown): v is Locale {
  return (SUPPORTED_LOCALES as readonly unknown[]).includes(v);
}

/** The locale a URL path is in: a leading `/es/` segment, else the default. */
export function localeFromPath(pathname: string): Locale {
  const first = pathname.split("/")[1];
  return isLocale(first) && first !== DEFAULT_LOCALE ? first : DEFAULT_LOCALE;
}

/** Drop a leading locale segment: `/es/directory` -> `/directory`, `/es` -> `/`. */
export function stripLocale(pathname: string): string {
  const first = pathname.split("/")[1];
  if (isLocale(first) && first !== DEFAULT_LOCALE) {
    return pathname.slice(first.length + 1) || "/";
  }
  return pathname || "/";
}

/** A path in a locale: the default locale keeps its bare URLs, others get a prefix. */
export function localePath(locale: Locale, path: string): string {
  const bare = stripLocale(path.startsWith("/") ? path : `/${path}`);
  if (locale === DEFAULT_LOCALE) return bare;
  return bare === "/" ? `/${locale}/` : `/${locale}${bare}`;
}

function lookup(locale: Locale, key: string): unknown {
  return key.split(".").reduce<unknown>(
    (o, k) => (o as Record<string, unknown> | undefined)?.[k],
    catalogs[locale],
  );
}

const interpolate = (s: string, vars?: Record<string, string | number>) =>
  vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s;

export interface Translator {
  /** A string, with `{name}` placeholders filled from `vars`. */
  (key: string, vars?: Record<string, string | number>): string;
  /** A list of strings (eyebrows, bullet lists). */
  list(key: string): string[];
  /** A list of objects (steps, cards). */
  items<T = Record<string, string>>(key: string): T[];
  /** `key.one` / `key.other` by the locale's plural rules; `{count}` is filled in. */
  plural(key: string, count: number, vars?: Record<string, string | number>): string;
  locale: Locale;
}

/** A translator for one locale. Any missing key falls back to English, then to the key. */
export function useTranslations(locale: Locale): Translator {
  const get = (key: string): unknown => lookup(locale, key) ?? lookup(DEFAULT_LOCALE, key);
  const t = ((key: string, vars?: Record<string, string | number>) => {
    const v = get(key);
    return typeof v === "string" ? interpolate(v, vars) : key;
  }) as Translator;
  t.list = (key) => {
    const v = get(key);
    return Array.isArray(v) ? (v as string[]) : [];
  };
  t.items = <T,>(key: string) => {
    const v = get(key);
    return Array.isArray(v) ? (v as T[]) : [];
  };
  t.plural = (key, count, vars) => {
    const form = new Intl.PluralRules(locale).select(count) === "one" ? "one" : "other";
    return t(`${key}.${form}`, { count: count.toLocaleString(locale), ...vars });
  };
  t.locale = locale;
  return t;
}
