// Renders public/og.png, the 1200x630 social/link-preview image every page
// points at (og:image / twitter:image in src/layouts/Base.astro). The PNG is
// committed, so the build never runs this; re-run it after changing the copy:
//
//   node scripts/build-og.mjs
//
// sharp comes in with Astro. Text uses the system serif/sans through fontconfig,
// so the output can differ slightly between machines.
import sharp from "sharp";
import { fileURLToPath } from "node:url";

const out = fileURLToPath(new URL("../public/og.png", import.meta.url));

// Brand tokens (src/styles/global.css): paper-100 ground, ocean ink, sunflower diamond.
const paper = "#f0eeea";
const ocean = "#1b4b82";
const ink = "#072445";
const sunflower = "#e8b716";
const muted = "#4a5f78";

const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="${paper}"/>
  <rect y="598" width="1200" height="32" fill="${ocean}"/>
  <rect y="590" width="1200" height="8" fill="${sunflower}"/>

  <g transform="translate(88 92) scale(0.085)">
    <polygon points="611.88 0 328.37 275.09 328.37 275.21 611.88 517.33 895.39 275.21 895.39 275.09 611.88 0" fill="${sunflower}"/>
    <polygon points="895.51 275.09 895.39 275.09 895.39 275.21 611.88 992.46 328.37 275.21 328.37 275.09 328.24 275.09 0 57 469.75 1264.94 611.88 1264.94 754 1264.94 1223.75 57 895.51 275.09" fill="${ocean}"/>
  </g>
  <text x="200" y="168" font-family="Helvetica, Arial, sans-serif" font-size="46" font-weight="700" fill="${ink}">VisaNav</text>

  <text font-family="Georgia, 'Noto Serif', serif" font-size="76" font-weight="700" fill="${ink}">
    <tspan x="88" y="318">Free, private</tspan>
    <tspan x="88" y="406">immigration help.</tspan>
  </text>
  <text font-family="Helvetica, Arial, sans-serif" font-size="32" fill="${muted}">
    <tspan x="88" y="482">Plain-language answers and free or low-cost</tspan>
    <tspan x="88" y="526">legal help near you. English and Español.</tspan>
  </text>
</svg>`;

await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(out);
console.log(`wrote ${out}`);
