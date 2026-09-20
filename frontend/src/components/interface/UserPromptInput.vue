<template>
  <div class="rounded-lg p-4">
    <Textarea
      v-model="prompt"
      class="border-0"
      :placeholder="$t('chat.placeholder')"
    />
    <div class="flex space-x-2">
      <Button @click="sendPrompt">
        {{ $t("chat.submit") }}
      </Button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {ref} from "vue";

const emit = defineEmits(['submit-prompt']);

const prompt = ref('')

function sendPrompt() {
  emit('submit-prompt', prompt.value)
  prompt.value = ''
}
</script>
