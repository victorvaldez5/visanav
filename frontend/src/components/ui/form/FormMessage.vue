<script lang="ts" setup>
import type { HTMLAttributes } from "vue"
import { ErrorMessage } from "vee-validate"
import { CircleAlert } from "@lucide/vue"
import { toValue } from "vue"
import { cn } from "@/lib/utils"
import { useFormField } from "./useFormField"

const props = defineProps<{
  class?: HTMLAttributes["class"]
}>()

const { name, formMessageId } = useFormField()
</script>

<template>
  <ErrorMessage
    :id="formMessageId"
    v-slot="{ message }"
    data-slot="form-message"
    as="p"
    :name="toValue(name)"
    :class="cn('text-destructive-foreground text-sm flex items-center gap-1.5', props.class)"
  >
    <CircleAlert
      class="size-4 shrink-0"
      aria-hidden="true"
    />
    <span>{{ message }}</span>
  </ErrorMessage>
</template>
