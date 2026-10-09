<script setup lang="ts">
import { Languages } from "@lucide/vue";
import { useI18n } from "vue-i18n";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import LanguageMenuItems from "@/components/interface/LanguageMenuItems.vue";

// The sidebar header's language control: an icon button that opens the language
// list. Each option is labelled in its own language, so it is findable whatever
// the current UI language is.
const { t } = useI18n();
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button
        variant="ghost"
        size="icon"
        :aria-label="t('lang.label')"
        :title="t('lang.label')"
      >
        <Languages
          class="size-5"
          aria-hidden="true"
        />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent
      align="end"
      class="w-48"
    >
      <LanguageMenuItems />
    </DropdownMenuContent>
  </DropdownMenu>
</template>
