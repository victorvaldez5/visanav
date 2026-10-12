<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { isLocale, SUPPORTED_LOCALES } from "@/i18n";
import { useLocaleSync } from "@/composables/useLocaleSync";
import {
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from "@/components/ui/dropdown-menu";

// The language options of the sidebar header's language menu (LanguageMenu.vue).
// Each option is labelled in its own language (`lang.<code>`), so a user can find
// theirs whatever the current UI language is. Place it inside a DropdownMenuContent.
const { locale } = useI18n();
const { changeLocale } = useLocaleSync();

function onChange(value: unknown) {
  if (isLocale(value)) changeLocale(value);
}
</script>

<template>
  <DropdownMenuLabel class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
    {{ $t("lang.label") }}
  </DropdownMenuLabel>
  <DropdownMenuRadioGroup
    :model-value="locale"
    @update:model-value="onChange"
  >
    <DropdownMenuRadioItem
      v-for="loc in SUPPORTED_LOCALES"
      :key="loc"
      :value="loc"
      :lang="loc"
      class="text-base"
    >
      {{ $t(`lang.${loc}`) }}
    </DropdownMenuRadioItem>
  </DropdownMenuRadioGroup>
</template>
