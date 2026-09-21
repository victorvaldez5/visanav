// Small formatting helpers shared by the resource-directory views
// (Organizations + Representatives).

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// ISO date (YYYY-MM-DD) → "Mon D, YYYY". Empty string for a null/blank date.
export function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${MONTHS[+m - 1]} ${+d}, ${y}`;
}

// A phone number → a `tel:` href, keeping only digits and a leading "+".
export function telHref(phone: string): string {
  return "tel:" + phone.replace(/[^0-9+]/g, "");
}
