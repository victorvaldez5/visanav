// /llms.txt: a plain Markdown map of the site for LLMs and AI agents
// (https://llmstxt.org). Built at build time so the directory figures stay in
// step with src/data/organizations.json. The chat app serves its own index at
// app.visanav.org/llms.txt (frontend/worker/index.ts).
import type { APIRoute } from "astro";
import { API_URL, APP_URL, SITE_URL } from "../config";
import orgs from "../data/organizations.json";

export const GET: APIRoute = () => {
  const total = orgs.length;
  const proBono = orgs.filter((o) => o.proBono).length;
  const states = new Set(orgs.map((o) => o.state).filter(Boolean)).size;
  const page = (path: string) => new URL(path, SITE_URL).href;

  const body = `# VisaNav

> VisaNav is a free, private immigration help tool for people in the United States. It explains immigration options in plain language (English and Spanish) and connects people to recognized nonprofits and pro-bono legal help. It is informational, not legal advice, not a law firm, and not affiliated with USCIS or ICE.

Key facts:

- Free to use. No account is needed to chat, and no data is sold.
- Personal identifiers (A-numbers, case and receipt numbers, SSNs, emails, phone numbers, addresses, dates) are removed from a question in the browser before it is sent.
- The legal-help directory lists ${total.toLocaleString("en")} organizations in ${states} states and territories: DOJ/EOIR recognized organizations (from the official EOIR roster) plus ${proBono} pro-bono providers.
- The chat assistant, Javi, answers from official sources such as USCIS, the INA and the Code of Federal Regulations.

## Pages

- [Home](${page("/")}): what VisaNav is, how it works, and its privacy promises
- [Legal-help directory](${page("/directory/")}): free and low-cost immigration legal help, searchable by state
- [For organizations](${page("/partners/")}): how nonprofits can request to be listed
- [Spanish site](${page("/es/")}): the same pages in Spanish

## Chat app

- [Ask Javi](${APP_URL}/): the chat assistant, plus public pages for USCIS forms, legal-help organizations and DOJ-accredited representatives. Its own index: ${APP_URL}/llms.txt

## Data (public JSON API)

- Organizations: ${API_URL}/api/network/organizations/
- Representatives: ${API_URL}/api/network/representatives/

## Optional

- [Privacy policy](${page("/privacy/")})
- [Terms of use](${page("/terms/")})
`;

  return new Response(body, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};
