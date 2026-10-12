// Small formatting helpers shared by the resource-directory views
// (Organizations + Representatives) and chat source citations.

import { currentLocale } from "@/i18n";

// ISO date (YYYY-MM-DD) → a short date in the active UI locale ("Sep 13, 2026",
// "13 sept 2026"). Built from the date parts, not `new Date(iso)`, because a bare
// ISO date parses as UTC and can show the previous day in negative offsets.
// Empty string for a null/blank date; an unparseable value is returned as-is.
export function fmtDate(iso: string | null | undefined, locale: string = currentLocale()): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const date = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" }).format(date);
}

// ISO 639-1 codes → language names in the active UI locale, joined as a list
// ("Spanish, English" / "español, inglés"). A code Intl doesn't know is shown as
// the code itself; an empty list gives an empty string.
export function fmtLanguages(codes: string[] | null | undefined, locale: string = currentLocale()): string {
  if (!codes?.length) return "";
  let names: Intl.DisplayNames | null = null;
  try {
    names = new Intl.DisplayNames(locale, { type: "language" });
  } catch {
    /* unsupported locale: fall back to the raw codes */
  }
  const label = (code: string) => {
    try {
      return names?.of(code) ?? code;
    } catch {
      return code; // malformed code
    }
  };
  return new Intl.ListFormat(locale, { style: "narrow", type: "unit" }).format(codes.map(label));
}

// A phone number → a `tel:` href, keeping only digits and a leading "+".
export function telHref(phone: string): string {
  return "tel:" + phone.replace(/[^0-9+]/g, "");
}
