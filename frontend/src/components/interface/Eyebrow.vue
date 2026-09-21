<script setup lang="ts">
import {computed} from "vue";

// The small uppercase kicker above a heading (and the muted meta line on cards),
// with sunflower diamonds between parts. Empty parts are dropped.
const props = withDefaults(
  defineProps<{
    parts: (string | null | undefined | false)[];
    variant?: "default" | "muted" | "onband";
  }>(),
  {variant: "default"},
);

const shown = computed(() => props.parts.filter(Boolean) as string[]);
</script>

<template>
  <p
    class="flex flex-wrap items-center gap-x-2 gap-y-1 font-bold uppercase leading-4 tracking-[0.08em]"
    :class="{
      'text-xs text-eyebrow': variant === 'default',
      'text-[11px] text-muted-foreground': variant === 'muted',
      'text-xs text-band-quiet': variant === 'onband',
    }"
  >
    <template
      v-for="(part, i) in shown"
      :key="i"
    >
      <span
        v-if="i > 0"
        aria-hidden="true"
        class="text-[9px] text-[color:var(--vn-sunflower-500)]"
      >◆</span>
      <span>{{ part }}</span>
    </template>
  </p>
</template>
