import { describe, it, expect } from "vitest";
import {
  currentLocale,
  DEFAULT_LOCALE,
  i18n,
  loadLocaleMessages,
  resolveLocale,
  setLocale,
  toLocale,
} from "@/i18n";

describe("toLocale", () => {
  it("maps exact and case-insensitive tags onto the allowlist", () => {
    expect(toLocale("es")).toBe("es");
    expect(toLocale("EN")).toBe("en");
  });

  it("falls back from a regional variant to its base language", () => {
    expect(toLocale("es-MX")).toBe("es");
    expect(toLocale("en-GB")).toBe("en");
  });

  it("rejects unsupported or empty values", () => {
    expect(toLocale("fr")).toBeNull();
    expect(toLocale("")).toBeNull();
    expect(toLocale(null)).toBeNull();
  });
});

describe("resolveLocale precedence", () => {
  it("prefers the ?lang= handoff over everything else", () => {
    expect(resolveLocale({ param: "es", saved: "en", browser: "en-US" })).toBe("es");
  });

  it("ignores an invalid handoff and uses the saved choice", () => {
    expect(resolveLocale({ param: "xx", saved: "es", browser: "en-US" })).toBe("es");
  });

  it("uses the browser language when nothing was chosen", () => {
    expect(resolveLocale({ browser: "es-419" })).toBe("es");
  });

  it("ignores a tampered saved value", () => {
    expect(resolveLocale({ saved: "<script>", browser: "fr-FR" })).toBe(DEFAULT_LOCALE);
  });

  it("defaults to English", () => {
    expect(resolveLocale({})).toBe("en");
  });
});

describe("lazy catalogs", () => {
  it("bundles only the default catalog up front", () => {
    expect(i18n.global.availableLocales).toEqual(["en"]);
  });

  it("loads a catalog on demand and switches to it", async () => {
    await loadLocaleMessages("es");
    expect(i18n.global.availableLocales).toContain("es");

    await setLocale("es");
    expect(currentLocale()).toBe("es");
    expect(i18n.global.t("lang.label")).toBe("Idioma");

    await setLocale("en");
    expect(i18n.global.t("lang.label")).toBe("Language");
  });
});
