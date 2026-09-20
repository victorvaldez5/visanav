// Normalizes the recognized-organization + pro-bono fixtures maintained in the
// API app into ONE slim, public, build-time dataset the static directory embeds.
//
// Source of truth stays in api/network/fixtures (same data the DB import migration
// consumes). This just projects it into the shape the marketing site needs.
//
// Refresh after the fixtures change:  node scripts/build-directory.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES = resolve(__dirname, "../../api/network/fixtures");
const OUT = resolve(__dirname, "../src/data/organizations.json");

const read = (name) => JSON.parse(readFileSync(resolve(FIXTURES, name), "utf8"));

const slugify = (s) =>
  s
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);

const normName = (s) => (s || "").trim().replace(/\s+/g, " ").toLowerCase();

// (617) 445-6000 from a bare 10-digit string; leave anything already formatted.
const fmtPhone = (p) => {
  if (!p) return "";
  const digits = String(p).replace(/\D/g, "");
  if (digits.length === 10) return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  if (digits.length === 11 && digits[0] === "1")
    return `(${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`;
  return String(p).trim();
};

const fmtSite = (w) => {
  if (!w) return "";
  let u = String(w).trim().replace(/\s+/g, "");
  if (!/^https?:\/\//i.test(u)) u = "https://" + u;
  return u;
};

const HEADER_JUNK = new Set(["recognized organization address", ""]);

// key -> merged org record
const byName = new Map();

const upsert = (rec) => {
  const key = normName(rec.name);
  if (!key || HEADER_JUNK.has(key)) return;
  const existing = byName.get(key);
  if (!existing) {
    byName.set(key, rec);
    return;
  }
  // Merge: keep richer fields, OR the pro-bono flag together.
  existing.proBono = existing.proBono || rec.proBono;
  for (const f of ["city", "state", "line1", "postalCode", "phone", "email", "website", "notes"]) {
    if (!existing[f] && rec[f]) existing[f] = rec[f];
  }
  if (rec.proBono) existing.lists = Array.from(new Set([...(existing.lists || []), "pro-bono"]));
};

// --- Recognized organizations (DOJ/EOIR recognized-org list) ---
for (const r of read("ra-orgs.json")) {
  const name = (r.organization_name || "").trim();
  if (!name) continue;
  const addrs = Array.isArray(r.addresses) ? r.addresses : [];
  const primary =
    addrs.find((a) => (a.address_name || "").toLowerCase().includes("principal")) || addrs[0] || {};
  upsert({
    name,
    proBono: false,
    lists: ["recognized"],
    city: (primary.city || "").trim(),
    state: (primary.state || "").trim(),
    line1: (primary.line1 || "").trim(),
    postalCode: (primary.postal_code || "").trim(),
    phone: fmtPhone(primary.phone_number),
    email: "",
    website: "",
    notes: "",
  });
}

// --- Pro-bono legal service providers ---
for (const r of read("probono_clean.json")) {
  const name = (r.organization_name || "").trim();
  if (!name) continue;
  const notes = Array.isArray(r.notes)
    ? r.notes.join(" ").replace(/\s+/g, " ").replace(/[•·]\s*/g, "").trim()
    : "";
  upsert({
    name,
    proBono: true,
    lists: ["pro-bono"],
    city: (r.city || "").trim(),
    state: (r.state || "").trim(),
    line1: (r.address || "").trim(),
    postalCode: (r.zip_code || "").trim(),
    phone: fmtPhone((r.telephone_numbers || [])[0]),
    email: ((r.email_addresses || [])[0] || "").trim(),
    website: fmtSite((r.websites || [])[0]),
    notes: notes.slice(0, 240),
  });
}

// Assign stable, unique slugs and finalize.
const used = new Set();
const orgs = Array.from(byName.values())
  .sort((a, b) => a.name.localeCompare(b.name))
  .map((o) => {
    let slug = slugify(o.name) || "org";
    let base = slug;
    let n = 2;
    while (used.has(slug)) slug = `${base}-${n++}`;
    used.add(slug);
    return { id: slug, ...o };
  });

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(orgs, null, 0) + "\n");

const withState = orgs.filter((o) => o.state).length;
const proBono = orgs.filter((o) => o.proBono).length;
console.log(
  `Wrote ${orgs.length} organizations -> ${OUT}\n` +
    `  pro-bono: ${proBono}   with state: ${withState}   ` +
    `states: ${new Set(orgs.map((o) => o.state).filter(Boolean)).size}`
);
