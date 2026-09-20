<script setup lang="ts">
import { Moon, Sun } from "@lucide/vue";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/composables/useTheme";

const { isDark, toggleTheme } = useTheme();
</script>

<template>
  <Button
    variant="ghost"
    size="icon"
    :aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
    :title="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
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
