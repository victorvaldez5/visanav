import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approxTokens,
  buildForms,
  buildHome,
  buildLlmsIndex,
  buildRepresentatives,
  buildResources,
  formatRepresentatives,
  formatResources,
  markdownResponse,
  normalizePath,
  wantsMarkdown,
  type Env,
} from "./index";

const env: Env = {
  ASSETS: { fetch: async () => new Response("") } as unknown as Env["ASSETS"],
  API_BASE_URL: "https://api.example.test/api",
};

function req(headers: Record<string, string> = {}, method = "GET"): Request {
  return new Request("https://visanav.test/", { method, headers });
}

describe("wantsMarkdown", () => {
  it("is true for a GET asking for text/markdown", () => {
    expect(wantsMarkdown(req({ accept: "text/markdown" }))).toBe(true);
    expect(wantsMarkdown(req({ accept: "text/markdown, text/html" }))).toBe(true);
    // case-insensitive
    expect(wantsMarkdown(req({ accept: "TEXT/MARKDOWN" }))).toBe(true);
  });

  it("is false without the header or with a browser Accept", () => {
    expect(wantsMarkdown(req())).toBe(false);
    expect(wantsMarkdown(req({ accept: "text/html,application/xhtml+xml" }))).toBe(false);
  });

  it("is false for unsafe methods even with the header", () => {
    expect(wantsMarkdown(req({ accept: "text/markdown" }, "POST"))).toBe(false);
  });
});

describe("normalizePath", () => {
  it("drops a single trailing slash but keeps root", () => {
    expect(normalizePath("/forms/")).toBe("/forms");
    expect(normalizePath("/forms")).toBe("/forms");
    expect(normalizePath("/")).toBe("/");
  });
});

describe("markdownResponse", () => {
  it("sets the markdown content type, Vary, and token headers", () => {
    const res = markdownResponse("# hi");
    expect(res.headers.get("content-type")).toBe("text/markdown; charset=utf-8");
    expect(res.headers.get("vary")).toBe("Accept");
    expect(res.headers.get("x-markdown-tokens")).toBe(String(approxTokens("# hi")));
  });
});

describe("buildForms", () => {
  it("renders category headings and a known form from forms.json", () => {
    const md = buildForms();
    expect(md).toMatch(/^# USCIS forms/);
    expect(md).toContain("## Family & sponsorship");
    expect(md).toContain("**I-130** — Petition for Alien Relative");
    expect(md).toContain("File online: yes");
  });
});

describe("buildHome / buildLlmsIndex", () => {
  it("home mentions the assistant, privacy scrubbing, and the API base", () => {
    const md = buildHome(env);
    expect(md).toContain("Javi");
    expect(md).toContain("in your browser");
    expect(md).toContain(env.API_BASE_URL);
  });

  it("llms.txt links every markdown route and the JSON endpoints", () => {
    const md = buildLlmsIndex(env);
    expect(md).toContain("/forms");
    expect(md).toContain("/resources");
    expect(md).toContain("/representatives");
    expect(md).toContain(`${env.API_BASE_URL}/network/organizations/`);
  });
});

describe("formatResources", () => {
  it("renders org fields and a 'showing N of M' note when truncated", () => {
    const md = formatResources(
      {
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            name: "Immigrant Aid Society",
            organization_type: "nonprofit",
            description: "Free help with asylum cases.",
            pro_bono: true,
            fee_model: "free",
            services: ["asylum", "family petitions"],
            languages: ["English", "Spanish"],
            address: {
              line1: "1 Main St",
              line2: "",
              city: "Phoenix",
              postal_code: "85001",
              subdivision: { code: "AZ", name: "Arizona" },
            },
            websites: ["https://example.org"],
            emails: ["help@example.org"],
            phones: ["+1 555 0100"],
            source_url: "https://source.example/org",
            last_verified: "2026-01-01",
          },
        ],
      },
      env,
    );
    expect(md).toContain("### Immigrant Aid Society");
    expect(md).toContain("Cost: pro bono, free");
    expect(md).toContain("Services: asylum, family petitions");
    expect(md).toContain("1 Main St, Phoenix, Arizona, 85001");
    expect(md).toContain("Showing 1 of 2");
  });
});

describe("formatRepresentatives", () => {
  it("renders rep fields reached through the organization", () => {
    const md = formatRepresentatives(
      {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            name: "Jordan Rep",
            provider_type: "accredited_representative",
            credential: "DOJ accredited",
            organization_name: "Immigrant Aid Society",
            organization_phone: "+1 555 0100",
            organization_city: "Phoenix",
            organization_state: "Arizona",
            accreditation_expiration: "2027-06-30",
            source_url: "https://source.example/rep",
          },
        ],
      },
      env,
    );
    expect(md).toContain("### Jordan Rep");
    expect(md).toContain("Organization: Immigrant Aid Society");
    expect(md).toContain("Location: Phoenix, Arizona");
    expect(md).toContain("Accreditation expires: 2027-06-30");
  });
});

describe("live builders (mocked fetch)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("buildResources fetches the org endpoint and formats it", async () => {
    const fetchMock = vi.fn(async () =>
      Response.json({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            name: "Test Org",
            organization_type: "nonprofit",
            description: "",
            pro_bono: false,
            fee_model: "low-cost",
            services: [],
            languages: [],
            address: null,
            websites: [],
            emails: [],
            phones: [],
            source_url: "",
            last_verified: null,
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const md = await buildResources(env);
    expect(fetchMock).toHaveBeenCalledWith(
      `${env.API_BASE_URL}/network/organizations/?page_size=500&ordering=name`,
      { headers: { accept: "application/json" } },
    );
    expect(md).toContain("### Test Org");
    expect(md).toContain("Cost: low-cost");
  });

  it("degrades gracefully to a JSON pointer when the API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 502 })),
    );
    const md = await buildRepresentatives(env);
    expect(md).toContain("temporarily unavailable");
    expect(md).toContain(`${env.API_BASE_URL}/network/representatives/`);
  });
});
