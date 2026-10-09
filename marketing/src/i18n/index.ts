// Marketing-site i18n. Locale lives in the URL (`/` is English, `/es/` Spanish) and
// the URL is authoritative: no Accept-Language redirect, which hurts SEO and
// surprises people. SUPPORTED_LOCALES and DEFAULT_LOCALE mirror
// /i18n/supported-locales.json: CI (scripts/check_i18n_parity.mjs) checks them, and
// the astro.config.mjs locale list, against that file, and checks the catalogs next
// to this file key-for-key against en.json.
//
// Adding a locale here: add its catalog import, its SUPPORTED_LOCALES entry, and its
// LOCALE_NAMES / OG_LOCALE rows (the Record types make a missing row a type error),
// then the two lists in astro.config.mjs. Pages, the header's language links and the
// 404 all derive from SUPPORTED_LOCALES.
import en from "./en.json";
import es from "./es.json";

export const SUPPORTED_LOCALES = ["en", "es"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

/** Each locale's name in its own language, for the switcher. */
export const LOCALE_NAMES: Record<Locale, string> = { en: "English", es: "Español" };

/** Open Graph wants language_TERRITORY, not a bare language code. */
export const OG_LOCALE: Record<Locale, string> = { en: "en_US", es: "es_LA" };

const catalogs: Record<Locale, Record<string, unknown>> = { en, es };

export function isLocale(v: unknown): v is Locale {
  return (SUPPORTED_LOCALES as readonly unknown[]).includes(v);
}

/** The locale a URL path is in: a leading `/es/` segment, else the default. */
export function localeFromPath(pathname: string): Locale {
  const first = pathname.split("/")[1];
  return isLocale(first) && first !== DEFAULT_LOCALE ? first : DEFAULT_LOCALE;
}

/**
 * The locale-free form of a path, with no trailing slash (except the root):
 * `/es/directory/` -> `/directory`, `/es` -> `/`. Used to compare pages.
 */
export function stripLocale(pathname: string): string {
  let path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  const first = path.split("/")[1];
  if (isLocale(first) && first !== DEFAULT_LOCALE) path = path.slice(first.length + 1);
  return path.replace(/\/+$/, "") || "/";
}

/**
 * The URL path of a page in a locale: the default locale keeps its bare URLs and
 * the others get a prefix. Always ends in a slash, because that is the URL the
 * static host serves (`directory/index.html` at `/directory/`, with the slashless
 * form redirecting) and the one the sitemap lists, so canonical, hreflang and
 * internal links must all agree with it.
 */
export function localePath(locale: Locale, path: string): string {
  const bare = stripLocale(path);
  const prefix = locale === DEFAULT_LOCALE ? "" : `/${locale}`;
  return bare === "/" ? `${prefix}/` : `${prefix}${bare}/`;
}

/**
 * `getStaticPaths` for a `[...lang]` page: the default locale at the bare URL
 * (`lang` undefined) and every other locale under its prefix.
 */
export function localeStaticPaths() {
  return SUPPORTED_LOCALES.map((l) => ({ params: { lang: l === DEFAULT_LOCALE ? undefined : l } }));
}

/** The locale a `[...lang]` page was rendered for, from `Astro.params.lang`. */
export function localeFromParam(lang: string | undefined): Locale {
  return isLocale(lang) ? lang : DEFAULT_LOCALE;
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
