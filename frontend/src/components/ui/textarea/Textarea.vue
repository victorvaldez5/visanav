<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { useVModel } from '@vueuse/core'
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: HTMLAttributes['class']
  defaultValue?: string | number
  modelValue?: string | number
}>()

const emits = defineEmits<{
  (e: 'update:modelValue', payload: string | number): void
}>()

const modelValue = useVModel(props, 'modelValue', emits, {
  passive: true,
  defaultValue: props.defaultValue,
})
</script>

<template>
  <textarea
    v-model="modelValue"
    data-slot="textarea"
    :class="cn('border-transparent bg-field shadow-elevation-1-control rounded-lg placeholder:text-[var(--field-placeholder)] resize-none aria-invalid:bg-field-invalid aria-invalid:shadow-glow-error flex field-sizing-content min-h-16 w-full border px-3 py-2 text-base outline-none focus-visible:outline-none focus-visible:shadow-glow-focus disabled:cursor-not-allowed disabled:shadow-none disabled:opacity-55 md:text-sm', props.class)"
  />
</template>
