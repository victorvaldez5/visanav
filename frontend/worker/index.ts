// Markdown-for-Agents content negotiation for the VisaNav SPA.
//
// The site is a client-rendered Vue SPA, so its origin HTML carries no content
// for an agent to read. This Worker answers requests that opt in with
// `Accept: text/markdown` (the Cloudflare / agent convention) with a clean,
// formatting-stripped markdown representation of the public pages, and passes
// everything else through to the static assets untouched — HTML stays the
// default for browsers and crawlers.
//
// The formatting/negotiation helpers are exported as small pure functions so
// they can be unit-tested without a Worker runtime (see index.test.ts).

import formsRaw from "../src/data/forms.json";

export interface Env {
  /** Static-assets binding (see wrangler.jsonc `assets.binding`). */
  ASSETS: Fetcher;
  /** Django API base URL, INCLUDING the /api prefix. */
  API_BASE_URL: string;
}

// --- data shapes -----------------------------------------------------------

interface FormEntry {
  number: string;
  title: string;
  summary: string;
  category: string;
  url: string;
  fileOnline: boolean;
}

interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

interface OrgAddress {
  line1: string;
  line2: string;
  city: string;
  postal_code: string;
  subdivision: { code: string; name: string } | null;
}

interface Organization {
  name: string;
  organization_type: string;
  description: string;
  pro_bono: boolean;
  fee_model: string;
  services: string[];
  languages: string[];
  address: OrgAddress | null;
  websites: string[];
  emails: string[];
  phones: string[];
  source_url: string;
  last_verified: string | null;
}

interface Representative {
  name: string;
  provider_type: string;
  credential: string;
  organization_name: string | null;
  organization_phone: string | null;
  organization_city: string | null;
  organization_state: string | null;
  accreditation_expiration: string | null;
  source_url: string;
}

const forms = formsRaw as FormEntry[];

// How many rows to pull per directory page. The API caps far higher; this keeps
// the markdown bounded, and we link to the JSON API when there are more.
const DIRECTORY_PAGE_SIZE = 500;

// --- content negotiation ---------------------------------------------------

/** True when the request opts in to markdown (a safe GET/HEAD asking for it). */
export function wantsMarkdown(request: Request): boolean {
  if (request.method !== "GET" && request.method !== "HEAD") return false;
  const accept = request.headers.get("accept") ?? "";
  return accept.toLowerCase().includes("text/markdown");
}

/** Drop a single trailing slash so "/forms" and "/forms/" match one route. */
export function normalizePath(pathname: string): string {
  return pathname.length > 1 && pathname.endsWith("/")
    ? pathname.slice(0, -1)
    : pathname;
}

/** Rough token estimate for the optional x-markdown-tokens header (~4 chars/token). */
export function approxTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

export function markdownResponse(text: string): Response {
  return new Response(text, {
    headers: {
      "content-type": "text/markdown; charset=utf-8",
      // Caches must not serve a markdown body to an HTML request or vice-versa.
      vary: "Accept",
      "cache-control": "public, max-age=300",
      "x-markdown-tokens": String(approxTokens(text)),
    },
  });
}

// --- static builders -------------------------------------------------------

export function buildHome(env: Env): string {
  return `# VisaNav

VisaNav is a free immigration assistant. It helps immigrants understand their
status and options and connects them with free and low-cost legal help. Guidance
is informational and is not legal advice.

## What you can do here

- **Ask Javi, the chat assistant** — answers immigration questions in plain
  language, grounded in official USCIS material, and points you to free or
  low-cost help. Available in English and Spanish.
- **Browse USCIS forms** — a categorized index of common forms with plain-language
  summaries and links. See [/forms](/forms).
- **Find free & low-cost legal help** — a directory of nonprofits, pro-bono
  providers and DOJ-recognized organizations. See [/resources](/resources).
- **Find DOJ-accredited representatives** — a roster of accredited (non-attorney)
  representatives you reach through their recognized organization. See
  [/representatives](/representatives).

## Your privacy

VisaNav scrubs personally identifiable information (names, phone numbers, email
addresses, and similar) from your message **in your browser, before it is sent**,
so sensitive details are not transmitted with your question.

## For agents

Every public page also answers \`Accept: text/markdown\` with a markdown version
of this page. The underlying data is available as JSON from the public API at
\`${env.API_BASE_URL}\` (e.g. \`${env.API_BASE_URL}/network/organizations/\`).
See [/llms.txt](/llms.txt) for an index.
`;
}

export function buildForms(): string {
  const byCategory = new Map<string, FormEntry[]>();
  for (const form of forms) {
    const list = byCategory.get(form.category) ?? [];
    list.push(form);
    byCategory.set(form.category, list);
  }

  const sections: string[] = [];
  for (const category of [...byCategory.keys()].sort()) {
    const lines = byCategory
      .get(category)!
      .map(
        (f) =>
          `- **${f.number}** — ${f.title}\n` +
          `  ${f.summary}\n` +
          `  File online: ${f.fileOnline ? "yes" : "no"} · ${f.url}`,
      );
    sections.push(`## ${category}\n\n${lines.join("\n")}`);
  }

  return `# USCIS forms

A plain-language index of common USCIS immigration forms. Links go to the
official USCIS page for each form.

${sections.join("\n\n")}
`;
}

export function buildLlmsIndex(env: Env): string {
  return `# VisaNav

> Free immigration guidance and a directory of free and low-cost legal help.

Every page below also answers \`Accept: text/markdown\` with a markdown version.

## Pages

- [Home](/): what VisaNav is and how to use it
- [USCIS forms](/forms): categorized index of common forms
- [Legal-help directory](/resources): free and low-cost organizations
- [Accredited representatives](/representatives): DOJ-accredited (non-attorney) reps

## Data (JSON API)

- Organizations: ${env.API_BASE_URL}/network/organizations/
- Representatives: ${env.API_BASE_URL}/network/representatives/
`;
}

// --- live directory builders ----------------------------------------------

function formatAddress(a: OrgAddress | null): string | null {
  if (!a) return null;
  const region = a.subdivision?.name ?? "";
  const parts = [a.line1, a.line2, a.city, region, a.postal_code].filter(Boolean);
  return parts.length ? parts.join(", ") : null;
}

function costLabel(org: Organization): string {
  const parts: string[] = [];
  if (org.pro_bono) parts.push("pro bono");
  if (org.fee_model) parts.push(org.fee_model);
  return parts.length ? parts.join(", ") : "not specified";
}

export function formatResources(data: Paginated<Organization>, env: Env): string {
  const entries = data.results.map((org) => {
    const lines = [`### ${org.name}`];
    if (org.organization_type) lines.push(`- Type: ${org.organization_type}`);
    lines.push(`- Cost: ${costLabel(org)}`);
    if (org.description) lines.push(`- ${org.description}`);
    if (org.services?.length) lines.push(`- Services: ${org.services.join(", ")}`);
    if (org.languages?.length) lines.push(`- Languages: ${org.languages.join(", ")}`);
    const addr = formatAddress(org.address);
    if (addr) lines.push(`- Address: ${addr}`);
    if (org.phones?.length) lines.push(`- Phone: ${org.phones.join(", ")}`);
    if (org.emails?.length) lines.push(`- Email: ${org.emails.join(", ")}`);
    if (org.websites?.length) lines.push(`- Website: ${org.websites.join(", ")}`);
    if (org.source_url) lines.push(`- Source: ${org.source_url}`);
    return lines.join("\n");
  });

  const more =
    data.count > data.results.length
      ? `\n\n_Showing ${data.results.length} of ${data.count}. Full, paginated ` +
        `data: ${env.API_BASE_URL}/network/organizations/_`
      : "";

  return `# Free & low-cost legal help

Nonprofits, pro-bono providers and DOJ-recognized organizations offering free or
low-cost immigration help. A listing is not an endorsement — contact an
organization directly to confirm current availability.

${entries.join("\n\n")}${more}
`;
}

export function formatRepresentatives(
  data: Paginated<Representative>,
  env: Env,
): string {
  const entries = data.results.map((rep) => {
    const lines = [`### ${rep.name}`];
    const type = [rep.provider_type, rep.credential].filter(Boolean).join(" · ");
    if (type) lines.push(`- Type: ${type}`);
    if (rep.organization_name) lines.push(`- Organization: ${rep.organization_name}`);
    const place = [rep.organization_city, rep.organization_state]
      .filter(Boolean)
      .join(", ");
    if (place) lines.push(`- Location: ${place}`);
    if (rep.organization_phone) lines.push(`- Phone (organization): ${rep.organization_phone}`);
    if (rep.accreditation_expiration)
      lines.push(`- Accreditation expires: ${rep.accreditation_expiration}`);
    if (rep.source_url) lines.push(`- Source: ${rep.source_url}`);
    return lines.join("\n");
  });

  const more =
    data.count > data.results.length
      ? `\n\n_Showing ${data.results.length} of ${data.count}. Full, paginated ` +
        `data: ${env.API_BASE_URL}/network/representatives/_`
      : "";

  return `# DOJ-accredited representatives

Accredited representatives are not attorneys; you reach them through their
recognized organization. Expired accreditations are excluded. Always confirm a
representative's current standing against the official DOJ roster.

${entries.join("\n\n")}${more}
`;
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`API ${res.status} for ${url}`);
  return (await res.json()) as T;
}

export async function buildResources(env: Env): Promise<string> {
  const url = `${env.API_BASE_URL}/network/organizations/?page_size=${DIRECTORY_PAGE_SIZE}&ordering=name`;
  try {
    const data = await fetchJson<Paginated<Organization>>(url);
    return formatResources(data, env);
  } catch {
    return `# Free & low-cost legal help

The live directory is temporarily unavailable. The data is available as JSON at
${env.API_BASE_URL}/network/organizations/
`;
  }
}

export async function buildRepresentatives(env: Env): Promise<string> {
  const url = `${env.API_BASE_URL}/network/representatives/?page_size=${DIRECTORY_PAGE_SIZE}`;
  try {
    const data = await fetchJson<Paginated<Representative>>(url);
    return formatRepresentatives(data, env);
  } catch {
    return `# DOJ-accredited representatives

The live roster is temporarily unavailable. The data is available as JSON at
${env.API_BASE_URL}/network/representatives/
`;
  }
}

// --- request handler -------------------------------------------------------

async function buildMarkdown(path: string, env: Env): Promise<string | null> {
  switch (path) {
    case "/":
      return buildHome(env);
    case "/forms":
      return buildForms();
    case "/resources":
      return buildResources(env);
    case "/representatives":
      return buildRepresentatives(env);
    default:
      return null;
  }
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const path = normalizePath(url.pathname);

    // llms.txt is a discovery file served to everyone, regardless of Accept.
    if (path === "/llms.txt") {
      return new Response(buildLlmsIndex(env), {
        headers: {
          "content-type": "text/plain; charset=utf-8",
          "cache-control": "public, max-age=300",
          vary: "Accept",
        },
      });
    }

    if (wantsMarkdown(request)) {
      // Cache composed markdown at the edge so agent traffic doesn't hit the API
      // (or rebuild the page) on every request. Keyed by URL + the markdown Accept.
      const cache = caches.default;
      const cacheKey = new Request(url.toString(), {
        headers: { accept: "text/markdown" },
      });
      const cached = await cache.match(cacheKey);
      if (cached) return cached;

      const markdown = await buildMarkdown(path, env);
      if (markdown !== null) {
        const response = markdownResponse(markdown);
        ctx.waitUntil(cache.put(cacheKey, response.clone()));
        return response;
      }
      // Unknown route: fall through and serve the SPA as usual.
    }

    // Default: serve the static asset, but flag that the response varies on
    // Accept so shared caches keep HTML and markdown apart.
    const assetResponse = await env.ASSETS.fetch(request);
    const response = new Response(assetResponse.body, assetResponse);
    response.headers.append("Vary", "Accept");
    return response;
  },
};
