<script setup lang="ts">
import LineIcon from "@/components/interface/LineIcon.vue";
import {Tooltip, TooltipContent, TooltipProvider, TooltipTrigger} from "@/components/ui/tooltip";

// Multi-select toggle chips (cost / scope filters). An item may carry a `hint`,
// shown as a tooltip on hover/focus — used to explain the accreditation scopes
// without a separate block of explainer cards. The tick keeps its space when
// hidden, so a chip doesn't jump width as it's pressed.
const props = defineProps<{
  items: {id: string; label: string; hint?: string}[];
  modelValue: Record<string, boolean>;
  ariaLabel?: string;
}>();
const emit = defineEmits<{(e: "update:modelValue", value: Record<string, boolean>): void}>();

function toggle(id: string) {
  emit("update:modelValue", {...props.modelValue, [id]: !props.modelValue[id]});
}

const chipClass =
  "inline-flex items-center gap-[7px] rounded-lg border border-transparent bg-raised px-3 py-2 text-[13px] font-semibold text-foreground shadow-elevation-1-control transition-[transform,box-shadow,background-color] duration-150 hover:-translate-y-0.5 hover:shadow-button-hover focus-visible:shadow-glow-focus focus-visible:outline-none aria-pressed:bg-primary aria-pressed:text-primary-foreground max-md:px-3.5 max-md:py-3 max-md:text-sm";
</script>

<template>
  <TooltipProvider :delay-duration="200">
    <div
      class="flex flex-wrap gap-2"
      role="group"
      :aria-label="ariaLabel"
    >
      <Tooltip
        v-for="item in items"
        :key="item.id"
      >
        <TooltipTrigger as-child>
          <button
            type="button"
            :aria-pressed="!!modelValue[item.id]"
            :class="chipClass"
            @click="toggle(item.id)"
          >
            <LineIcon
              name="check"
              class="h-[13px] w-[13px] transition-opacity"
              :class="modelValue[item.id] ? 'opacity-100' : 'opacity-0'"
            />
            {{ item.label }}
          </button>
        </TooltipTrigger>
        <TooltipContent
          v-if="item.hint"
          class="max-w-[260px] text-[12.5px] font-normal leading-[17px]"
        >
          {{ item.hint }}
        </TooltipContent>
      </Tooltip>
    </div>
  </TooltipProvider>
</template>
