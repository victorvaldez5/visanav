import { describe, it, expect } from "vitest";
import { scrubPII, describeScrub } from "@/lib/pii";

const clean = (s: string) => scrubPII(s).text;

describe("scrubPII — patterns", () => {
  it("redacts emails", () => {
    const r = scrubPII("write me at jose.perez@example.com ok?");
    expect(r.text).toBe("write me at [EMAIL] ok?");
    expect(r.summary).toEqual({ email: 1 });
  });

  it("redacts USCIS receipt numbers", () => {
    expect(clean("case IOE1234567890")).toBe("case [RECEIPT-NUMBER]");
    expect(clean("EAC-0912345678 pending")).toBe("[RECEIPT-NUMBER] pending");
    expect(scrubPII("WAC1234567890").summary).toEqual({ receiptNumber: 1 });
  });

  it("redacts A-numbers in the common formats", () => {
    expect(clean("A123456789")).toBe("[A-NUMBER]");
    expect(clean("mine is A-123-456-789.")).toBe("mine is [A-NUMBER].");
    expect(clean("A# 12345678")).toBe("[A-NUMBER]");
    expect(scrubPII("A087654321").summary).toEqual({ aNumber: 1 });
  });

  it("redacts formatted SSNs / ITINs", () => {
    expect(clean("ssn 123-45-6789")).toBe("ssn [SSN]");
    expect(clean("900 45 6789")).toBe("[SSN]");
    expect(scrubPII("078-05-1120").summary).toEqual({ ssn: 1 });
  });

  it("redacts US phone numbers in several formats", () => {
    expect(clean("call 816-555-1234")).toBe("call [PHONE]");
    expect(clean("(816) 555-1234")).toBe("[PHONE]");
    expect(clean("816.555.1234")).toBe("[PHONE]");
    expect(clean("1-816-555-1234")).toBe("[PHONE]");
  });

  it("redacts international phone numbers (incl. Mexico / Central America)", () => {
    expect(clean("+52 55 1234 5678")).toBe("[PHONE]");
    expect(clean("+502 1234-5678")).toBe("[PHONE]");
    expect(clean("+1 816 555 1234")).toBe("[PHONE]");
  });

  it("redacts dates but keeps the 4-digit year", () => {
    expect(clean("on 3/14/2019")).toBe("on [DATE, 2019]");
    expect(clean("2019-03-14")).toBe("[DATE, 2019]");
    expect(clean("March 14, 2019")).toBe("[DATE, 2019]");
    expect(clean("Mar 14 2019")).toBe("[DATE, 2019]");
    expect(clean("14 de marzo de 2019")).toBe("[DATE, 2019]");
  });

  it("redacts dates with no year as [DATE]", () => {
    expect(clean("el 3 de mayo")).toBe("el [DATE]");
    expect(clean("on 3/14/19")).toBe("on [DATE]"); // 2-digit year dropped
    expect(clean("March 14")).toBe("[DATE]");
  });

  it("redacts US street addresses (best effort)", () => {
    expect(clean("1234 Main St Apt 2B")).toBe("[ADDRESS]");
    expect(clean("live at 500 Oak Avenue")).toBe("live at [ADDRESS]");
    expect(scrubPII("42 Elm Rd Suite 100").summary).toEqual({ address: 1 });
  });

  it("redacts passport-style ids and the 7+ digit catch-all", () => {
    expect(clean("passport AB1234567")).toBe("passport [ID-NUMBER]");
    expect(clean("number 12345678")).toBe("number [ID-NUMBER]");
    expect(scrubPII("X1234567").summary).toEqual({ idNumber: 1 });
  });
});

describe("scrubPII — must keep legally meaningful context", () => {
  it("keeps form names", () => {
    expect(scrubPII("I filed I-589, then I-130 and I-485").changed).toBe(false);
  });

  it("keeps dollar amounts", () => {
    expect(scrubPII("the fee was $1,225.50").changed).toBe(false);
  });

  it("keeps month+year and year alone", () => {
    expect(scrubPII("since March 2019").changed).toBe(false);
    expect(scrubPII("deported in 2018").changed).toBe(false);
  });

  it("keeps durations and small counts", () => {
    expect(scrubPII("here 7 years with 2 kids").changed).toBe(false);
  });

  it("keeps the year when it redacts a full date", () => {
    expect(clean("entered March 14, 2019")).toBe("entered [DATE, 2019]");
  });
});

describe("scrubPII — summary is counts only", () => {
  it("counts by type and never returns matched values", () => {
    const r = scrubPII("A123456789 and call 816-555-1234 or +52 55 1234 5678");
    expect(r.summary).toEqual({ aNumber: 1, phone: 2 });
    expect(r.changed).toBe(true);
    // No raw values anywhere in the returned summary.
    expect(JSON.stringify(r.summary)).not.toMatch(/\d{3,}/);
    expect(JSON.stringify(r.summary)).not.toContain("816");
  });

  it("reports changed=false and empty summary when nothing matches", () => {
    const r = scrubPII("how do I renew my green card?");
    expect(r.changed).toBe(false);
    expect(r.summary).toEqual({});
  });
});

describe("scrubPII — false positives", () => {
  it("treats '816 555 1234' as a phone, not an A-number", () => {
    const r = scrubPII("llamé a 816 555 1234");
    expect(r.text).toBe("llamé a [PHONE]");
    expect(r.summary.aNumber).toBeUndefined();
    expect(r.summary.phone).toBe(1);
  });

  it("leaves a year range untouched", () => {
    const r = scrubPII("de 2019 a 2020");
    expect(r.text).toBe("de 2019 a 2020");
    expect(r.changed).toBe(false);
  });
});

describe("describeScrub — friendly notice", () => {
  it("English, pluralized, with a list", () => {
    expect(describeScrub({ aNumber: 1, phone: 2 }, "en")).toBe(
      "For your privacy, we removed 1 A-number and 2 phone numbers before sending.",
    );
  });

  it("Spanish, single item", () => {
    expect(describeScrub({ aNumber: 1 }, "es")).toBe(
      "Para proteger tu privacidad, quitamos 1 número A antes de enviar.",
    );
  });

  it("pluralizes singular vs plural", () => {
    expect(describeScrub({ phone: 1 }, "en")).toContain("1 phone number ");
    expect(describeScrub({ phone: 2 }, "en")).toContain("2 phone numbers ");
    expect(describeScrub({ email: 2 }, "es")).toContain("2 correos electrónicos");
  });

  it("returns empty string when nothing was removed", () => {
    expect(describeScrub({}, "en")).toBe("");
    expect(describeScrub(null, "en")).toBe("");
    expect(describeScrub(undefined, "es")).toBe("");
  });
});
