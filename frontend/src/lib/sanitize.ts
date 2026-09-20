import {marked} from "marked";
import DOMPurify from "dompurify";

// Assistant replies are Markdown, rendered to HTML and injected with `v-html`.
// That HTML is NOT trusted: the reply text is model-generated and grounded in
// content we don't control — a community-curated corpus chunk, a resource-
// directory row, or (for a shared anonymous conversation) a message another
// person injected via the link. Any of those could smuggle a <script>, an
// `onerror=` handler, or a remote <img> whose request beacons the (sensitive)
// transcript to an attacker. So every rendered string is sanitized here before
// it reaches the DOM. The CSP baked into the built index.html (see
// vite.config.ts) is the second layer, for the day a sanitizer bypass surfaces.

// Force any link the model emits to open safely and to never leak the referrer:
// the URL of an anonymous conversation is itself a bearer key, so it must not
// travel in an outbound Referer header.
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A" && node.hasAttribute("href")) {
        node.setAttribute("target", "_blank");
        node.setAttribute("rel", "noopener noreferrer nofollow");
    }
});

const PURIFY_CONFIG = {
    // Strip anything that can load a remote resource or execute — Markdown never
    // needs these, and allowing them is exactly what turns a poisoned reply into
    // a data-exfiltration beacon. (DOMPurify already blocks javascript:/vbscript:
    // hrefs and inline event handlers; this narrows the surface further.)
    FORBID_TAGS: [
        "img", "svg", "math", "style", "iframe", "object", "embed", "form",
        "input", "button", "textarea", "audio", "video", "source", "link",
    ],
    FORBID_ATTR: ["style"],
    ALLOW_DATA_ATTR: false,
    // Keep `target` so the anchor hook's addition survives sanitization.
    ADD_ATTR: ["target"],
};

/** Render trusted-as-text Markdown to sanitized, safe-to-inject HTML. */
export function renderMarkdown(src: string | null | undefined): string {
    if (!src) return "";
    const html = marked.parse(src, {async: false}) as string;
    return DOMPurify.sanitize(html, PURIFY_CONFIG);
}
