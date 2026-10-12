// @vitest-environment jsdom
// DOMPurify needs a DOM; the rest of the suite stays on the node environment.
import { describe, it, expect } from "vitest";
import { renderMarkdown } from "@/lib/markdown";

describe("renderMarkdown links", () => {
  it("opens absolute https links in a new tab without leaking the opener", () => {
    const html = renderMarkdown("See [USCIS](https://www.uscis.gov/i-485).");
    expect(html).toContain('<a href="https://www.uscis.gov/i-485" target="_blank" rel="noopener noreferrer">USCIS</a>');
  });

  it("also covers http links and keeps the title", () => {
    const html = renderMarkdown('[x](http://example.gov "Official")');
    expect(html).toContain('title="Official"');
    expect(html).toContain('target="_blank"');
  });

  it("leaves relative and mailto links in the same tab", () => {
    expect(renderMarkdown("[home](/resources)")).not.toContain("target=");
    expect(renderMarkdown("[mail](mailto:a@b.org)")).not.toContain("target=");
  });

  it("renders inline formatting inside the link text", () => {
    expect(renderMarkdown("[**bold**](https://uscis.gov)")).toContain("<strong>bold</strong></a>");
  });

  it("escapes quotes in the href so it can't break out of the attribute", () => {
    const html = renderMarkdown('[x](https://a.gov/?q="onmouseover=alert(1))');
    expect(html).not.toContain('"onmouseover');
  });
});

describe("renderMarkdown sanitizing", () => {
  it("strips script tags and inline event handlers", () => {
    const html = renderMarkdown('hi <script>alert(1)</script><img src=x onerror="alert(2)">');
    expect(html).not.toMatch(/<script/i);
    expect(html).not.toMatch(/onerror/i);
  });

  it("neutralizes javascript: links", () => {
    const html = renderMarkdown("[click](javascript:alert(1))");
    expect(html).not.toMatch(/javascript:/i);
  });

  it("forces rel on a raw-HTML _blank link the model wrote itself", () => {
    const html = renderMarkdown('<a href="https://uscis.gov" target="_blank">x</a>');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it("keeps normal markdown formatting", () => {
    const html = renderMarkdown("# Title\n\n- one\n- **two**");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain("<li><strong>two</strong></li>");
  });
});
