<script setup lang="ts">
import {computed} from "vue";
import {renderMarkdown} from "@/lib/sanitize";

const props = defineProps({
  source: {
    type: String,
    required: true
  }
})

const thinking = computed(() => {
  const thinkStart = props.source.search(">")
  const thinkEnd = props.source.search("</thinking>")
  return props.source.substring(thinkStart, thinkEnd)
})

const body = computed(() => {
  if (thinking.value === '') return props.source
  const searchStr = "<thinking>"
  const searchStrLen = searchStr.length
  const bodyStart = props.source.search("</thinking>")
  return props.source?.substring(bodyStart + searchStrLen)
})
</script>

<template>
  <div
    v-if="thinking !== ''"
    class="text-muted-foreground mb-6 prose"
    v-html="renderMarkdown(thinking)"
  />
  <div
    class="prose"
    v-html="renderMarkdown(body)"
  />
</template>

<style scoped>

</style>
