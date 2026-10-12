<script setup lang="ts">
import {computed, ref} from "vue";
import {useI18n} from "vue-i18n";
import {breakpointsTailwind, useBreakpoints} from "@vueuse/core";
import {Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle} from "@/components/ui/sheet";
import {Button} from "@/components/ui/button";
import LineIcon from "@/components/interface/LineIcon.vue";

// The resource-directory filter panel. On desktop it's an inline card: a search
// row on top and the filter controls below. On phones (< md) the search row
// sticks to the top and the controls move into a bottom sheet opened by a
// "Filters" button that shows how many filters are active — so results start
// above the fold. Slots: #search (always visible) and default (the controls).
const props = defineProps<{activeCount?: number; title?: string}>();
const {t} = useI18n();
const sheetTitle = computed(() => props.title ?? t("common.filters"));

const breakpoints = useBreakpoints(breakpointsTailwind);
const isMobile = breakpoints.smaller("md");
const open = ref(false);

const countBadge =
  "inline-flex h-[19px] min-w-[19px] items-center justify-center rounded-[3px] bg-primary px-1.5 text-[11px] font-bold text-primary-foreground tabular-nums";
</script>

<template>
  <!-- Desktop: everything inline in one card. -->
  <div
    v-if="!isMobile"
    class="grid gap-4 rounded-xl bg-card p-[18px] shadow-elevation-1"
    role="search"
  >
    <slot name="search" />
    <slot />
  </div>

  <!-- Phone: sticky search row + a Filters button that opens a bottom sheet. -->
  <template v-else>
    <div class="sticky top-0 z-40 -mx-4 flex items-end gap-2.5 bg-background px-4 pb-3 pt-2.5">
      <div class="min-w-0 flex-1">
        <slot name="search" />
      </div>
      <Button
        type="button"
        variant="outline"
        class="h-[46px] flex-none gap-2"
        :aria-expanded="open"
        @click="open = true"
      >
        <LineIcon
          name="filter"
          class="h-[15px] w-[15px]"
        />
        {{ t("common.filters") }}
        <span
          v-if="activeCount"
          :class="countBadge"
        >{{ activeCount }}</span>
      </Button>
    </div>

    <Sheet v-model:open="open">
      <SheetContent
        side="bottom"
        class="max-h-[85vh] gap-0 overflow-y-auto rounded-t-xl px-4 pb-[calc(1rem+env(safe-area-inset-bottom))]"
      >
        <SheetHeader class="px-0 pt-1">
          <SheetTitle class="font-serif text-lg">
            {{ sheetTitle }}
          </SheetTitle>
        </SheetHeader>
        <div
          class="grid gap-[18px] py-2"
          role="search"
        >
          <slot />
        </div>
        <SheetFooter class="sticky bottom-0 bg-background px-0 pt-2">
          <Button
            type="button"
            class="h-12 w-full"
            @click="open = false"
          >
            {{ t("common.showResults") }}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  </template>
</template>
