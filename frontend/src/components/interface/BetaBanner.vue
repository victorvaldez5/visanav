<script setup lang="ts">
import { EOIR_ROSTER_URL } from "@/i18n";
import LineIcon from "@/components/interface/LineIcon.vue";

// Persistent (non-dismissible) beta + legal-information disclaimer. The
// "accredited representative" phrase links to the official DOJ EOIR roster.
// The language switcher lives in the sidebar header (LanguageMenu.vue).
</script>

<template>
  <div
    class="w-full bg-warn px-4 py-2.5 text-sm text-warn-foreground"
    role="note"
  >
    <div class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-1">
      <div class="flex min-w-0 flex-1 items-start gap-3">
        <LineIcon
          name="alert"
          class="mt-0.5 h-[19px] w-[19px] shrink-0"
        />
        <i18n-t
          keypath="banner.text"
          tag="p"
          scope="global"
          class="min-w-0"
        >
          <template #rep>
            <a
              :href="EOIR_ROSTER_URL"
              target="_blank"
              rel="noopener noreferrer"
              class="font-semibold underline decoration-[color:var(--vn-sunflower-400)] decoration-2 underline-offset-2 hover:decoration-[3px]"
            >{{ $t("rep") }}</a>
          </template>
        </i18n-t>
      </div>
    </div>
  </div>
</template>
