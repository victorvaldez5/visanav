/**
 * Client-side PII scrubber for chat messages.
 *
 * Runs in the browser BEFORE a message is sent, so identifiers never reach our
 * server, logs, or the LLM/embedding providers. Pure and framework-free.
 *
 * Design rules (see the spec):
 *  - Strip identifiers, keep legally meaningful context (form names, dollar
 *    amounts, month+year or year alone, durations/counts, and the year inside a
 *    redacted full date).
 *  - When unsure, over-redact — a lost number is fine, a leaked A-number is not.
 *  - Most specific patterns first (email, receipt, A-number, SSN, phones), then
 *    dates, addresses, and the 7+-digit catch-all last.
 *  - Return counts by type only; never return, store, or log matched values.
 *  - No regex lookbehind anywhere (older Safari support). Lookahead is fine.
 *
 * OUT OF SCOPE here (handled server-side later): people's names, and
 * Spanish-format street addresses. This module only does the patterns above.
 */

export interface PiiSummary {
  email?: number;
  receiptNumber?: number;
  aNumber?: number;
  ssn?: number;
  phone?: number;
  date?: number;
  address?: number;
  idNumber?: number;
}

export interface ScrubResult {
  /** The message with identifiers replaced by typed placeholders. */
  text: string;
  /** Counts by type only — never the matched values. */
  summary: PiiSummary;
  /** True when anything was redacted. */
  changed: boolean;
}

type Key = keyof PiiSummary;

// ── Patterns ─────────────────────────────────────────────────────────────────
// Each entry replaces its matches with a typed placeholder and counts them. They
// run in this order; earlier (more specific) matches protect later ones.

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

// USCIS receipt: a known 3-letter service center prefix + 10 digits.
const RECEIPT = /\b(?:IOE|EAC|WAC|LIN|SRC|NBC|MSC)[- ]?\d{10}\b/gi;

// A-number: "A" (optionally "#"/space or a hyphen) + 8 or 9 digits, digits
// optionally grouped by spaces/hyphens. Requires the leading A, so it does not
// swallow bare phone numbers. A plain "a <space> digits" (no #) is NOT matched,
// which avoids the Spanish word "a" + a number.
const A_NUMBER = /\bA(?:#\s*|-)?\d(?:[-\s]?\d){7,8}\b/gi;

// SSN / ITIN in formatted form: 3-2-4 with hyphen or space separators.
const SSN = /\b\d{3}[-\s]\d{2}[-\s]\d{4}\b/g;

// Phone — international (leading +country code) first, then US formats. A bare
// 10-digit run with no separators is intentionally left to the catch-all.
const PHONE_INTL = /\+\d{1,3}[\s.-]?\d{1,4}(?:[\s.-]?\d{2,4}){1,4}/g;
// The word boundary sits on the bare-digits branch only; a leading "(" (as in
// "(816) 555-1234") is not a word char, so a leading \b would reject it.
const PHONE_US = /(?:1[\s.-]?)?(?:\(\d{3}\)|\b\d{3})[\s.-]\d{3}[\s.-]\d{4}\b/g;

// Dates. We redact a *specific* day (full date or day+month), keeping any
// 4-digit year, but we KEEP a bare year or month+year (those carry legal
// meaning). `(?!\d)` (lookahead, allowed) stops a day from eating a year, so
// "March 2019" is never treated as "March 20".
const DATE_ISO = /\b(\d{4})[/-]\d{2}[/-]\d{2}\b/g; // YYYY-MM-DD / YYYY/MM/DD
const DATE_NUMERIC = /\b\d{1,2}[/-]\d{1,2}[/-](\d{2,4})\b/g; // M/D/Y or D/M/Y
const EN_MONTHS =
  "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?";
const ES_MONTHS =
  "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre";
// "March 14, 2019" / "Mar 14" / "March 14 2019"
const DATE_EN_MD = new RegExp(
  `\\b(?:${EN_MONTHS})\\.?\\s+\\d{1,2}(?!\\d)(?:st|nd|rd|th)?(?:,?\\s+(\\d{4}))?\\b`,
  "gi",
);
// "14 March 2019" / "14 March"
const DATE_EN_DM = new RegExp(
  `\\b\\d{1,2}(?!\\d)(?:st|nd|rd|th)?\\s+(?:${EN_MONTHS})\\.?(?:,?\\s+(\\d{4}))?\\b`,
  "gi",
);
// "14 de marzo de 2019" / "3 de mayo"
const DATE_ES = new RegExp(
  `\\b\\d{1,2}(?!\\d)\\s+de\\s+(?:${ES_MONTHS})(?:\\s+de\\s+(\\d{4}))?\\b`,
  "gi",
);

// US street address, best effort: number + (words) + street type + optional unit.
const ADDRESS =
  /\b\d{1,6}\s+(?:[A-Za-z0-9.'#-]+\s+){0,5}?(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Place|Pl|Terrace|Ter|Way|Highway|Hwy|Parkway|Pkwy|Trail|Trl|Square|Sq)\b\.?(?:\s+(?:Apt|Apartment|Suite|Ste|Unit|Rm|Room|#)\.?\s*[A-Za-z0-9-]+)?/gi;

// Passport-style ID: 1-2 letters + 7-9 digits (form numbers like I-130 have a
// hyphen and only 3 digits, so they are not matched).
const PASSPORT = /\b[A-Za-z]{1,2}\d{7,9}\b/g;

// Catch-all: any remaining run of 7+ digits.
const CATCHALL = /\d{7,}/g;

function bump(summary: PiiSummary, key: Key): void {
  summary[key] = (summary[key] ?? 0) + 1;
}

/** Replace a simple pattern with a fixed placeholder, counting matches. */
function pass(
  text: string,
  re: RegExp,
  key: Key,
  placeholder: string,
  summary: PiiSummary,
): string {
  return text.replace(re, () => {
    bump(summary, key);
    return placeholder;
  });
}

/** Date replacer: keep a captured 4-digit year as [DATE, YYYY], else [DATE]. */
function datePass(text: string, re: RegExp, summary: PiiSummary): string {
  return text.replace(re, (...args) => {
    // The year is the first capture group (may be undefined / a 2-digit year).
    const groups = args.slice(1, -2);
    const year = groups.find((g) => typeof g === "string" && g.length === 4);
    bump(summary, "date");
    return year ? `[DATE, ${year}]` : "[DATE]";
  });
}

/**
 * Scrub personal identifiers from `text`. Returns the redacted text, counts by
 * type, and whether anything changed. Never returns the matched values.
 */
export function scrubPII(text: string): ScrubResult {
  const summary: PiiSummary = {};
  let out = text ?? "";

  // Most specific first.
  out = pass(out, EMAIL, "email", "[EMAIL]", summary);
  out = pass(out, RECEIPT, "receiptNumber", "[RECEIPT-NUMBER]", summary);
  out = pass(out, A_NUMBER, "aNumber", "[A-NUMBER]", summary);
  out = pass(out, SSN, "ssn", "[SSN]", summary);
  out = pass(out, PHONE_INTL, "phone", "[PHONE]", summary);
  out = pass(out, PHONE_US, "phone", "[PHONE]", summary);

  // Dates (keep the year).
  out = datePass(out, DATE_ISO, summary);
  out = datePass(out, DATE_NUMERIC, summary);
  out = datePass(out, DATE_EN_MD, summary);
  out = datePass(out, DATE_EN_DM, summary);
  out = datePass(out, DATE_ES, summary);

  // Addresses, then passport-style ids, then the catch-all last.
  out = pass(out, ADDRESS, "address", "[ADDRESS]", summary);
  out = pass(out, PASSPORT, "idNumber", "[ID-NUMBER]", summary);
  out = pass(out, CATCHALL, "idNumber", "[ID-NUMBER]", summary);

  return { text: out, summary, changed: out !== (text ?? "") };
}

// ── Friendly notice ──────────────────────────────────────────────────────────

type Noun = { one: string; many: string };

const NOUNS: Record<Key, { en: Noun; es: Noun }> = {
  aNumber: {
    en: { one: "A-number", many: "A-numbers" },
    es: { one: "número A", many: "números A" },
  },
  ssn: {
    en: { one: "SSN", many: "SSNs" },
    es: { one: "número de seguro social", many: "números de seguro social" },
  },
  receiptNumber: {
    en: { one: "receipt number", many: "receipt numbers" },
    es: { one: "número de recibo", many: "números de recibo" },
  },
  email: {
    en: { one: "email address", many: "email addresses" },
    es: { one: "correo electrónico", many: "correos electrónicos" },
  },
  phone: {
    en: { one: "phone number", many: "phone numbers" },
    es: { one: "número de teléfono", many: "números de teléfono" },
  },
  date: {
    en: { one: "date", many: "dates" },
    es: { one: "fecha", many: "fechas" },
  },
  address: {
    en: { one: "address", many: "addresses" },
    es: { one: "dirección", many: "direcciones" },
  },
  idNumber: {
    en: { one: "ID number", many: "ID numbers" },
    es: { one: "número de identificación", many: "números de identificación" },
  },
};

// Stable order for listing removed items.
const ORDER: Key[] = [
  "aNumber", "ssn", "receiptNumber", "email", "phone", "date", "address", "idNumber",
];

function joinList(parts: string[], lang: "en" | "es"): string {
  if (parts.length <= 1) return parts.join("");
  const conj = lang === "es" ? "y" : "and";
  const head = parts.slice(0, -1).join(", ");
  return `${head} ${conj} ${parts[parts.length - 1]}`;
}

/**
 * Turn a scrub summary into a short, friendly notice in the given language.
 * Returns "" when nothing was removed. Uses counts only — never any value.
 */
export function describeScrub(
  summary: PiiSummary | null | undefined,
  lang: "en" | "es",
): string {
  if (!summary) return "";
  const parts: string[] = [];
  for (const key of ORDER) {
    const n = summary[key];
    if (!n) continue;
    const noun = NOUNS[key][lang];
    parts.push(`${n} ${n === 1 ? noun.one : noun.many}`);
  }
  if (parts.length === 0) return "";
  const list = joinList(parts, lang);
  return lang === "es"
    ? `Para proteger tu privacidad, quitamos ${list} antes de enviar.`
    : `For your privacy, we removed ${list} before sending.`;
}
