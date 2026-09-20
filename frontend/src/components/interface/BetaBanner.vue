<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { EOIR_ROSTER_URL, setLocale, SUPPORTED_LOCALES, type Locale } from "@/i18n";

// Persistent (non-dismissible) beta + legal-information disclaimer. The
// "accredited representative" phrase links to the official DOJ EOIR roster.
const { locale } = useI18n();
</script>

<template>
  <div
    class="w-full border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900"
    role="note"
  >
    <div class="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-1">
      <i18n-t
        keypath="banner.text"
        tag="p"
        scope="global"
        class="min-w-0 flex-1"
      >
        <template #rep>
          <a
            :href="EOIR_ROSTER_URL"
            target="_blank"
            rel="noopener noreferrer"
            class="font-semibold underline underline-offset-2 hover:no-underline"
          >{{ $t("rep") }}</a>
        </template>
      </i18n-t>
      <div
        class="flex shrink-0 items-center gap-1"
        role="group"
        :aria-label="$t('lang.label')"
      >
        <button
          v-for="loc in SUPPORTED_LOCALES"
          :key="loc"
          type="button"
          class="rounded px-2 py-0.5 text-xs font-medium transition-colors"
          :class="locale === loc
            ? 'bg-amber-200 text-amber-900'
            : 'text-amber-700 hover:bg-amber-100'"
          :aria-pressed="locale === loc"
          @click="setLocale(loc as Locale)"
        >
          {{ $t(`lang.${loc}`) }}
        </button>
      </div>
    </div>
  </div>
</template>
