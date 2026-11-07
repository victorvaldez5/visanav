// Shared schema.org helpers for the JSON-LD that Base.astro puts in every page
// head. Nodes reference each other by these @ids instead of repeating details.
import { SITE_URL } from "./config";

export const ORG_ID = `${SITE_URL}/#organization`;
export const WEBSITE_ID = `${SITE_URL}/#website`;

/**
 * Serialize JSON-LD for a <script type="application/ld+json"> body. `<` is
 * escaped so a value containing "</script>" can't end the tag early; JSON
 * parsers read < back as "<".
 */
export function jsonLdScript(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
