<script setup lang="ts">
import { Moon, Sun } from "@lucide/vue";
import { useI18n } from "vue-i18n";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { useTheme } from "@/composables/useTheme";

// The light/dark toggle, as an item in a sidebar dropdown (the account menu when
// signed in, the Register / Login menu when signed out). Labelled with the theme
// it switches to. Place it inside a DropdownMenuContent.
const { t } = useI18n();
const { isDark, toggleTheme } = useTheme();
</script>

<template>
  <DropdownMenuItem
    class="text-base"
    @select="toggleTheme()"
  >
    <Sun
      v-if="isDark"
      class="size-4"
      aria-hidden="true"
    />
    <Moon
      v-else
      class="size-4"
      aria-hidden="true"
    />
    <span>{{ isDark ? t("nav.themeLight") : t("nav.themeDark") }}</span>
  </DropdownMenuItem>
</template>
