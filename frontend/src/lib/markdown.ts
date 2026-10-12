import DOMPurify from "dompurify";
import { Marked, type Tokens } from "marked";

// Markdown for chat answers. Absolute http(s) links, which in an answer are almost
// always the official uscis.gov / travel.state.gov / justice.gov pages Javi cites,
// open in a new tab so the conversation isn't lost. `noopener noreferrer` keeps the
// destination from reaching back through `window.opener` or seeing the app URL
// (which carries a conversation UUID). Relative and mailto links are left alone.
// A dedicated instance, so the global `marked` isn't mutated.
const escapeAttr = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const markdown = new Marked({
  renderer: {
    link(this: { parser: { parseInline: (t: Tokens.Link["tokens"]) => string } }, { href, title, tokens }: Tokens.Link) {
      const text = this.parser.parseInline(tokens);
      const titleAttr = title ? ` title="${escapeAttr(title)}"` : "";
      const external = /^https?:\/\//i.test(href);
      const target = external ? ' target="_blank" rel="noopener noreferrer"' : "";
      return `<a href="${escapeAttr(href)}"${titleAttr}${target}>${text}</a>`;
    },
  },
});

// The model's output is untrusted: it can echo text from retrieved sources, and a
// marked renderer passes raw HTML through. Every answer is sanitized before it
// reaches `v-html`. `target` is stripped by default, so it is allowed back here,
// and the hook below forces `rel` on every `_blank` link, including ones written
// as raw HTML in the answer rather than markdown.
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A" && node.getAttribute("target") === "_blank") {
    node.setAttribute("rel", "noopener noreferrer");
  }
});

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function renderMarkdown(src: string): string {
  const html = markdown.parse(src, { async: false });
  // No DOM (SSR, a non-browser test): fail closed rather than emit unsanitized HTML.
  if (!DOMPurify.isSupported) return escapeHtml(src);
  return DOMPurify.sanitize(html, { ADD_ATTR: ["target"] });
}
