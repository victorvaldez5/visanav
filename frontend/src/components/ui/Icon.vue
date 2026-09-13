<template>
  <span v-if="svg" class="rfui-icon" v-html="svg" aria-hidden="true" />
  <span v-else class="rfui-icon-missing">⚠️ Icon "{{ name }}" not found</span>
</template>

<script setup lang="ts">
import { icons } from '@/icons'

const props = defineProps<{ name: string }>()
const svg = icons[props.name]
</script>

<style scoped>
.rfui-icon {
  display: inline-block;
  vertical-align: middle;
  line-height: 1;
}
.rfui-icon :deep(svg) {
  height: 100%;
  width: 100%;
  display: block;
}

/* Default fill colors — override per-component or globally */
.rfui-icon :deep(.primary)   { fill: var(--vn-blue-600)}
.rfui-icon :deep(.secondary) { fill: var(--vn-blue-400)}
</style>