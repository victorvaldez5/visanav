<script setup lang="ts">
import { marked } from "marked";
import {computed} from "vue";

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
    class="text-muted-foreground mb-6 prose dark:prose-invert max-w-none"
    v-html="marked.parse(thinking)"
  />
  <div
    class="prose dark:prose-invert max-w-none text-foreground"
    v-html="marked.parse(body)"
  />
</template>

<style scoped>

</style>
