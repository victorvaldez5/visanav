<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { EOIR_ROSTER_URL, setLocale, SUPPORTED_LOCALES, type Locale } from "@/i18n";
import LineIcon from "@/components/interface/LineIcon.vue";

// Persistent (non-dismissible) beta + legal-information disclaimer. The
// "accredited representative" phrase links to the official DOJ EOIR roster.
const { locale } = useI18n();
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
      <div
        class="flex shrink-0 items-center gap-1"
        role="group"
        :aria-label="$t('lang.label')"
      >
        <button
          v-for="loc in SUPPORTED_LOCALES"
          :key="loc"
          type="button"
          class="rounded px-2 py-0.5 text-xs font-semibold transition-colors"
          :class="locale === loc
            ? 'bg-status text-status-foreground'
            : 'text-warn-foreground/70 hover:bg-warn-foreground/10'"
          :aria-pressed="locale === loc"
          @click="setLocale(loc as Locale)"
        >
          {{ $t(`lang.${loc}`) }}
        </button>
      </div>
    </div>
  </div>
</template>
