#!/usr/bin/env node
// i18n consistency gate. Checks, with zero runtime dependencies (Node built-ins):
//   1. /i18n/supported-locales.json is well-formed (a "default" that is one of
//      the listed "locales").
//   2. Each surface's declared locale list AND default match that allowlist: the
//      Vue app's SUPPORTED_LOCALES + DEFAULT_LOCALE, Django's LANGUAGES +
//      LANGUAGE_CODE, and the marketing site's SUPPORTED_LOCALES + Astro i18n config.
//   3. Per-locale JSON catalogs (frontend/src/locales, marketing/src/i18n) share
//      an identical key set with the default locale's catalog.
//   4. Django gettext catalogs (api/locale/<locale>/LC_MESSAGES/*.po) cover every
//      non-default locale with no missing, fuzzy or obsolete entries (gettext's
//      equivalent of missing/orphaned keys).
//
// A surface whose files are absent is skipped rather than failed. Exits non-zero
// on any problem.

import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const errors = [];

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));
const rel = (p) => p.slice(ROOT.length + 1);

// Collect dotted paths of leaf values so nested catalogs compare structurally.
function flatten(obj, prefix = "", out = new Set()) {
  for (const [k, v] of Object.entries(obj)) {
    if (k.startsWith("$")) continue; // skip $comment / $schema style metadata
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) flatten(v, key, out);
    else out.add(key);
  }
  return out;
}

// Minimal .po reader: enough to tell whether each entry is translated. Returns
// one record per entry: { obsolete } or { msgid, msgstrs, fuzzy }.
function parsePo(text) {
  const entries = [];
  for (const block of text.split(/\r?\n\s*\r?\n/)) {
    const lines = block.split(/\r?\n/).filter((l) => l.trim());
    if (!lines.length) continue;
    if (lines.every((l) => l.startsWith("#"))) {
      if (lines.some((l) => l.startsWith("#~"))) entries.push({ obsolete: true });
      continue;
    }
    const entry = { msgid: "", msgstrs: [], fuzzy: false };
    let field = null;
    for (const line of lines) {
      if (line.startsWith("#,")) {
        if (line.includes("fuzzy")) entry.fuzzy = true;
        continue;
      }
      if (line.startsWith("#")) continue;
      const start = line.match(/^(msgctxt|msgid|msgid_plural|msgstr(?:\[\d+\])?)\s+"(.*)"$/);
      if (start) {
        field = start[1];
        if (field === "msgid") entry.msgid = start[2];
        else if (field.startsWith("msgstr")) entry.msgstrs.push(start[2]);
        continue;
      }
      const more = line.match(/^"(.*)"$/);
      if (more && field === "msgid") entry.msgid += more[1];
      else if (more && field?.startsWith("msgstr")) entry.msgstrs[entry.msgstrs.length - 1] += more[1];
    }
    entries.push(entry);
  }
  return entries;
}

// ── 1. canonical allowlist ──────────────────────────────────────────────────
const canonicalPath = join(ROOT, "i18n", "supported-locales.json");
if (!existsSync(canonicalPath)) {
  console.error("FAIL: missing i18n/supported-locales.json");
  process.exit(1);
}
const canonical = readJson(canonicalPath);
if (typeof canonical.default !== "string" || !Array.isArray(canonical.locales)) {
  errors.push('supported-locales.json needs a string "default" and array "locales"');
}
const codes = (canonical.locales || []).map((l) => l.code);
const codeSet = new Set(codes);
if (!codeSet.has(canonical.default)) {
  errors.push(`default locale "${canonical.default}" is not present in locales[]`);
}

function assertSameSet(label, declared) {
  const d = new Set(declared);
  const missing = [...codeSet].filter((c) => !d.has(c));
  const extra = [...d].filter((c) => !codeSet.has(c));
  if (missing.length) errors.push(`${label} is missing locales: ${missing.join(", ")}`);
  if (extra.length) errors.push(`${label} has locales not in the allowlist: ${extra.join(", ")}`);
}

function assertDefault(label, declared) {
  if (declared !== canonical.default) {
    errors.push(`${label} is "${declared}" but the allowlist default is "${canonical.default}"`);
  }
}

// Extract one declaration from a source file; a missing declaration is an error,
// because an undeclared list can't be checked.
function extract(file, label, pattern) {
  const m = readFileSync(file, "utf8").match(pattern);
  if (!m) errors.push(`could not locate ${label} in ${rel(file)}`);
  return m;
}

const quoted = (s) => [...s.matchAll(/["'`]([^"'`]+)["'`]/g)].map((x) => x[1]);

// ── 2. per-surface declared locale lists and defaults ───────────────────────
const feI18n = join(ROOT, "frontend", "src", "i18n", "index.ts");
if (existsSync(feI18n)) {
  const list = extract(feI18n, "SUPPORTED_LOCALES", /SUPPORTED_LOCALES\s*=\s*\[([^\]]*)\]/);
  if (list) assertSameSet("frontend SUPPORTED_LOCALES", quoted(list[1]));
  const def = extract(feI18n, "DEFAULT_LOCALE", /DEFAULT_LOCALE\s*(?::\s*\w+\s*)?=\s*["'`]([^"'`]+)["'`]/);
  if (def) assertDefault("frontend DEFAULT_LOCALE", def[1]);
}

const mkI18n = join(ROOT, "marketing", "src", "i18n", "index.ts");
if (existsSync(mkI18n)) {
  const list = extract(mkI18n, "SUPPORTED_LOCALES", /SUPPORTED_LOCALES\s*=\s*\[([^\]]*)\]/);
  if (list) assertSameSet("marketing SUPPORTED_LOCALES", quoted(list[1]));
  const def = extract(mkI18n, "DEFAULT_LOCALE", /DEFAULT_LOCALE\s*(?::\s*\w+\s*)?=\s*["'`]([^"'`]+)["'`]/);
  if (def) assertDefault("marketing DEFAULT_LOCALE", def[1]);
}

const beSettings = join(ROOT, "api", "api_project", "base.py");
if (existsSync(beSettings)) {
  const list = extract(beSettings, "LANGUAGES", /^LANGUAGES\s*=\s*\[([\s\S]*?)\]/m);
  if (list) assertSameSet("Django LANGUAGES", [...list[1].matchAll(/\(\s*["']([^"']+)["']/g)].map((x) => x[1]));
  const def = extract(beSettings, "LANGUAGE_CODE", /^LANGUAGE_CODE\s*=\s*["']([^"']+)["']/m);
  if (def) assertDefault("Django LANGUAGE_CODE", def[1]);
}

const astroConfig = join(ROOT, "marketing", "astro.config.mjs");
if (existsSync(astroConfig)) {
  const block = readFileSync(astroConfig, "utf8").match(/i18n\s*:\s*\{[\s\S]*?locales\s*:\s*\[([^\]]*)\]/);
  if (block) assertSameSet("Astro i18n.locales", quoted(block[1]));
}

// ── 3. JSON catalog key parity ───────────────────────────────────────────────
for (const root of [
  join(ROOT, "frontend", "src", "locales"),
  join(ROOT, "marketing", "src", "i18n"),
]) {
  if (!existsSync(root)) continue;
  const files = readdirSync(root).filter((f) => f.endsWith(".json"));
  if (files.length === 0) continue;

  for (const code of codeSet) {
    if (!files.includes(`${code}.json`)) {
      errors.push(`${rel(root)}: missing catalog "${code}.json" for allowlisted locale "${code}"`);
    }
  }

  const defaultFile = join(root, `${canonical.default}.json`);
  if (!existsSync(defaultFile)) continue;
  const defaultKeys = flatten(readJson(defaultFile));
  for (const f of files) {
    const code = basename(f, ".json");
    if (!codeSet.has(code)) {
      errors.push(`${rel(root)}/${f}: locale "${code}" is not in the allowlist`);
      continue;
    }
    if (code === canonical.default) continue;
    const keys = flatten(readJson(join(root, f)));
    for (const k of [...defaultKeys].filter((k) => !keys.has(k))) {
      errors.push(`${rel(root)}/${f}: missing key "${k}"`);
    }
    for (const k of [...keys].filter((k) => !defaultKeys.has(k))) {
      errors.push(`${rel(root)}/${f}: orphan key "${k}" (not in ${canonical.default}.json)`);
    }
  }
}

// ── 4. Django gettext catalogs ───────────────────────────────────────────────
const poRoot = join(ROOT, "api", "locale");
const localeDirs = existsSync(poRoot)
  ? readdirSync(poRoot, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name)
  : [];
if (localeDirs.length) {
  // Django's locale directory for a code: "es" -> "es", "zh-Hans" -> "zh_Hans".
  const dirFor = (code) => code.replace("-", "_");
  const allowedDirs = new Set(codes.map(dirFor));
  for (const dir of localeDirs) {
    if (!allowedDirs.has(dir)) errors.push(`api/locale/${dir}: locale is not in the allowlist`);
  }
  for (const code of codes) {
    if (code === canonical.default) continue; // the source language needs no catalog
    const lcDir = join(poRoot, dirFor(code), "LC_MESSAGES");
    const poFiles = existsSync(lcDir) ? readdirSync(lcDir).filter((f) => f.endsWith(".po")) : [];
    if (!poFiles.length) {
      errors.push(`api/locale: missing catalog for "${code}" (${dirFor(code)}/LC_MESSAGES/django.po)`);
      continue;
    }
    for (const f of poFiles) {
      const where = `api/locale/${dirFor(code)}/LC_MESSAGES/${f}`;
      const entries = parsePo(readFileSync(join(lcDir, f), "utf8"));
      const obsolete = entries.filter((e) => e.obsolete).length;
      if (obsolete) errors.push(`${where}: ${obsolete} obsolete "#~" entr${obsolete === 1 ? "y" : "ies"}`);
      for (const e of entries) {
        if (e.obsolete || e.msgid === "") continue; // "" is the catalog header
        const label = e.msgid.length > 60 ? `${e.msgid.slice(0, 57)}...` : e.msgid;
        if (e.fuzzy) errors.push(`${where}: fuzzy translation for "${label}"`);
        else if (!e.msgstrs.length || e.msgstrs.some((s) => s === "")) {
          errors.push(`${where}: missing translation for "${label}"`);
        }
      }
    }
  }
}

// ── report ──────────────────────────────────────────────────────────────────
if (errors.length) {
  console.error(`\ni18n parity check FAILED (${errors.length} problem(s)):`);
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`i18n parity OK: locales [${codes.join(", ")}], default "${canonical.default}".`);
