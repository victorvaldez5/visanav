<script setup lang="ts">
import { Moon, Sun } from "@lucide/vue";
import { Button } from "@/components/ui/button";
import { useI18n } from "vue-i18n";
import { useTheme } from "@/composables/useTheme";

const { t } = useI18n();
const { isDark, toggleTheme } = useTheme();
</script>

<template>
  <Button
    variant="ghost"
    size="icon"
    :aria-label="isDark ? t('nav.themeLight') : t('nav.themeDark')"
    :title="isDark ? t('nav.themeLight') : t('nav.themeDark')"
    @click="toggleTheme()"
  >
    <Sun
      v-if="isDark"
      class="size-5"
      aria-hidden="true"
    />
    <Moon
      v-else
      class="size-5"
      aria-hidden="true"
    />
  </Button>
</template>
