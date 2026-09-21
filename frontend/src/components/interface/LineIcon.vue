<script setup lang="ts">
// Stroked line icons (Lucide-style) that inherit `currentColor`, so they tint
// to the surrounding button or text. The app's default Icon set is duotone and
// locked to the ocean/sunflower fills, which washes out on a solid button — the
// resource-directory cards use these instead. Mirrors Icon.vue's v-html render.
const props = defineProps<{ name: string; class?: string }>();

const PATHS: Record<string, string> = {
  phone:
    '<path d="M5 3h4l2 5-2.5 1.5a12 12 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2.2 2A18 18 0 0 1 3 5.2 2 2 0 0 1 5 3z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18z"/>',
  check: '<path d="m20 6-11 11-5-5"/>',
  alert:
    '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18.1A2 2 0 0 0 3.5 21h17a2 2 0 0 0 1.7-2.9L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  filter: '<path d="M3 5h18M6 12h12M10 19h4"/>',
};
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    :class="props.class"
    v-html="PATHS[name] || ''"
  />
</template>
