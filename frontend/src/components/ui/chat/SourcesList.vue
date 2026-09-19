<script setup lang="ts">
import { computed } from "vue";
import type { Source } from "@/services/messageService";

const props = defineProps<{ sources: Source[] | null | undefined }>();

// Only real sources with something to show.
const items = computed(() => (props.sources ?? []).filter((s) => s && (s.title || s.source_url)));

// Format an ISO date (YYYY-MM-DD) without timezone drift (Date parsing of a bare
// ISO date is UTC, which can show the previous day in negative offsets).
function formatVerified(iso?: string | null): string | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
</script>

<template>
  <div
    v-if="items.length"
    class="mt-3 border-t pt-2 text-sm"
  >
    <p class="mb-1 font-medium text-muted-foreground">
      {{ $t("sources.title") }}
    </p>
    <ul class="space-y-1">
      <li
        v-for="source in items"
        :key="source.id"
        class="flex flex-wrap items-baseline gap-x-2"
      >
        <a
          v-if="source.source_url"
          :href="source.source_url"
          target="_blank"
          rel="noopener noreferrer nofollow"
          class="text-primary underline underline-offset-2 hover:no-underline break-words"
        >{{ source.title || source.source_url }}</a>
        <span v-else>{{ source.title }}</span>
        <span
          v-if="formatVerified(source.last_verified)"
          class="text-xs text-muted-foreground"
        >· {{ $t("sources.lastVerified", { date: formatVerified(source.last_verified) }) }}</span>
      </li>
    </ul>
  </div>
</template>
