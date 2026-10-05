<script setup lang="ts">
import { computed } from "vue";
import type { Source } from "@/services/messageService";
import { fmtDate } from "@/lib/format";

const props = defineProps<{ sources: Source[] | null | undefined }>();

// Only real sources with something to show.
const items = computed(() => (props.sources ?? []).filter((s) => s && (s.title || s.source_url)));

// A citation URL is model/corpus-derived, so never bind it to href raw: Vue does
// not strip javascript:/data: URLs. Only plain http(s) links become clickable;
// anything else falls back to rendering the title as plain text.
function safeHref(url?: string | null): string | null {
  if (!url) return null;
  try {
    // Parse as an ABSOLUTE URL (no origin base): a citation must carry its own
    // http(s) scheme. This mirrors the server's _safe_url (api/core/llm.py) so
    // the client is an independent gate — it never resolves a scheme-less or
    // relative string into a same-origin link, even if one reached it unsanitized.
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}

</script>

<template>
  <div
    v-if="items.length"
    class="mt-4 pt-2 text-sm"
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
          v-if="safeHref(source.source_url)"
          :href="safeHref(source.source_url) ?? undefined"
          target="_blank"
          rel="noopener noreferrer nofollow"
          class="text-primary underline underline-offset-2 hover:no-underline break-words"
        >{{ source.title || source.source_url }}</a>
        <span v-else>{{ source.title || source.source_url }}</span>
        <span
          v-if="fmtDate(source.last_verified)"
          class="text-xs text-muted-foreground"
        >· {{ $t("sources.lastVerified", { date: fmtDate(source.last_verified) }) }}</span>
      </li>
    </ul>
  </div>
</template>
