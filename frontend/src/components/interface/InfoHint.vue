<script setup lang="ts">
import {Tooltip, TooltipContent, TooltipProvider, TooltipTrigger} from "@/components/ui/tooltip";
import LineIcon from "@/components/interface/LineIcon.vue";

// A small info (ⓘ) affordance that reveals a tooltip on hover/focus — a visible
// cue that a nearby label/control has an explanation worth reading.
defineProps<{text: string; label?: string}>();
</script>

<template>
  <TooltipProvider :delay-duration="150">
    <Tooltip>
      <TooltipTrigger as-child>
        <button
          type="button"
          :aria-label="label ?? 'More information'"
          class="inline-flex items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:shadow-glow-focus focus-visible:outline-none"
        >
          <LineIcon
            name="info"
            class="h-3.5 w-3.5"
          />
        </button>
      </TooltipTrigger>
      <TooltipContent class="max-w-[280px] text-[12.5px] font-normal leading-[17px]">
        {{ text }}
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
