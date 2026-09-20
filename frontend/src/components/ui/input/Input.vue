<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { useVModel } from "@vueuse/core"
import { cn } from "@/lib/utils"

const props = defineProps<{
  defaultValue?: string | number
  modelValue?: string | number
  class?: HTMLAttributes["class"]
}>()

const emits = defineEmits<{
  (e: "update:modelValue", payload: string | number): void
}>()

const modelValue = useVModel(props, "modelValue", emits, {
  passive: true,
  defaultValue: props.defaultValue,
})
</script>

<template>
  <input
    v-model="modelValue"
    data-slot="input"
    :class="cn(
      'file:text-foreground placeholder:text-field-placeholder selection:bg-primary selection:text-primary-foreground border-transparent bg-field shadow-elevation-1-control rounded-lg flex h-10 w-full min-w-0 border px-3 py-1 text-base transition-[color,box-shadow] outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:shadow-none disabled:opacity-55 md:text-sm',
      'focus-visible:outline-none focus-visible:shadow-glow-focus',
      'aria-invalid:bg-field-invalid aria-invalid:shadow-glow-error',
      props.class,
    )"
  >
</template>
