#!/usr/bin/env node
// i18n consistency gate. Checks, with zero runtime dependencies (Node built-ins):
//   1. /i18n/supported-locales.json is well-formed (a "default" that is one of
//      the listed "locales").
//   2. Each surface's declared locale list matches that canonical allowlist:
//      the Vue app's SUPPORTED_LOCALES, the Django LANGUAGES, and (once it
//      exists) the Astro i18n config.
//   3. Per-locale JSON catalogs, once a surface has them, share an identical key
//      set with the default locale, so no translation key is missing or orphaned.
//
// It is forward-looking: catalog directories that do not exist yet are skipped,
// so this passes today and becomes stricter as catalogs land in later phases.
// Exits non-zero on any mismatch.

import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const errors = [];
const notes = [];

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));

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

// ── 2. per-surface declared locale lists ────────────────────────────────────
const feI18n = join(ROOT, "frontend", "src", "i18n", "index.ts");
if (existsSync(feI18n)) {
  const src = readFileSync(feI18n, "utf8");
  const m = src.match(/SUPPORTED_LOCALES\s*=\s*\[([^\]]*)\]/);
  if (m) {
    const declared = [...m[1].matchAll(/["'`]([^"'`]+)["'`]/g)].map((x) => x[1]);
    assertSameSet("frontend SUPPORTED_LOCALES", declared);
  } else {
    notes.push("could not locate SUPPORTED_LOCALES in frontend/src/i18n/index.ts");
  }
}

const beSettings = join(ROOT, "api", "api_project", "base.py");
if (existsSync(beSettings)) {
  const src = readFileSync(beSettings, "utf8");
  const m = src.match(/\nLANGUAGES\s*=\s*\[([\s\S]*?)\]/);
  if (m) {
    const declared = [...m[1].matchAll(/\(\s*["']([^"']+)["']/g)].map((x) => x[1]);
    assertSameSet("Django LANGUAGES", declared);
  } else {
    notes.push("could not locate LANGUAGES in api/api_project/base.py");
  }
}

const astroConfig = join(ROOT, "marketing", "astro.config.mjs");
if (existsSync(astroConfig)) {
  const src = readFileSync(astroConfig, "utf8");
  const block = src.match(/i18n\s*:\s*\{[\s\S]*?locales\s*:\s*\[([^\]]*)\]/);
  if (block) {
    const declared = [...block[1].matchAll(/["'`]([^"'`]+)["'`]/g)].map((x) => x[1]);
    assertSameSet("Astro i18n.locales", declared);
  }
  // No note if absent: Astro i18n is added in the marketing phase.
}

// ── 3. catalog key parity (skipped until a surface has catalogs) ─────────────
const catalogRoots = [
  join(ROOT, "frontend", "src", "locales"),
  join(ROOT, "marketing", "src", "i18n"),
];
for (const root of catalogRoots) {
  if (!existsSync(root)) continue;
  const files = readdirSync(root).filter((f) => f.endsWith(".json"));
  if (files.length === 0) continue;
  const rel = root.slice(ROOT.length + 1);

  for (const code of codeSet) {
    if (!files.includes(`${code}.json`)) {
      errors.push(`${rel}: missing catalog "${code}.json" for allowlisted locale "${code}"`);
    }
  }

  const defaultFile = join(root, `${canonical.default}.json`);
  if (!existsSync(defaultFile)) continue;
  const defaultKeys = flatten(readJson(defaultFile));
  for (const f of files) {
    const code = basename(f, ".json");
    if (!codeSet.has(code)) {
      errors.push(`${rel}/${f}: locale "${code}" is not in the allowlist`);
      continue;
    }
    if (code === canonical.default) continue;
    const keys = flatten(readJson(join(root, f)));
    for (const k of [...defaultKeys].filter((k) => !keys.has(k))) {
      errors.push(`${rel}/${f}: missing key "${k}"`);
    }
    for (const k of [...keys].filter((k) => !defaultKeys.has(k))) {
      errors.push(`${rel}/${f}: orphan key "${k}" (not in ${canonical.default}.json)`);
    }
  }
}

// ── report ──────────────────────────────────────────────────────────────────
for (const n of notes) console.log(`note: ${n}`);
if (errors.length) {
  console.error(`\ni18n parity check FAILED (${errors.length} problem(s)):`);
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`i18n parity OK: locales [${codes.join(", ")}], default "${canonical.default}".`);
