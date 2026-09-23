<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { SUPPORTED_LOCALES } from "@/i18n";
import { useLocaleSync } from "@/composables/useLocaleSync";

// Stable language control for every visitor (anonymous or signed in). Each
// option is labelled in its own language (`lang.<code>`), so a user can find
// theirs whatever the current UI language is.
const { locale } = useI18n();
const { changeLocale } = useLocaleSync();
</script>

<template>
  <div
    class="flex items-center justify-center gap-1"
    role="group"
    :aria-label="$t('lang.label')"
  >
    <button
      v-for="loc in SUPPORTED_LOCALES"
      :key="loc"
      type="button"
      :lang="loc"
      class="rounded px-2 py-0.5 text-xs font-semibold transition-colors"
      :class="locale === loc
        ? 'bg-sidebar-accent text-sidebar-accent-foreground'
        : 'text-muted-foreground hover:bg-sidebar-accent/60'"
      :aria-pressed="locale === loc"
      @click="changeLocale(loc)"
    >
      {{ $t(`lang.${loc}`) }}
    </button>
  </div>
</template>
