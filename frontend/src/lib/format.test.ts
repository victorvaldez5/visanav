import { describe, it, expect } from "vitest";
import { fmtDate, telHref } from "@/lib/format";

describe("fmtDate", () => {
  it("formats an ISO date as 'Mon D, YYYY'", () => {
    expect(fmtDate("2026-09-13")).toBe("Sep 13, 2026");
  });

  it("drops leading zeros from the day", () => {
    expect(fmtDate("2026-01-05")).toBe("Jan 5, 2026");
  });

  it("returns an empty string for a null or blank date", () => {
    expect(fmtDate(null)).toBe("");
    expect(fmtDate("")).toBe("");
  });
});

describe("telHref", () => {
  it("keeps only digits behind a tel: scheme", () => {
    expect(telHref("(415) 234-3380")).toBe("tel:4152343380");
  });

  it("preserves a leading + for international numbers", () => {
    expect(telHref("+1 202-555-0100")).toBe("tel:+12025550100");
  });
});
