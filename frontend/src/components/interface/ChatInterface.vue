<script setup lang="ts">
import {computed} from "vue";
import {useRoute, useRouter} from "vue-router";
import AIResponse from "@/components/ui/chat/AIRespone.vue";
import UserPromptInput from "@/components/interface/UserPromptInput.vue";
import {useConversation} from "@/composables/useConversations.ts";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import {storeToRefs} from "pinia";
import {toast} from "vue-sonner";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const {userId} = storeToRefs(authStore);

// derive a reactive conversationId from the URL
const conversationUuid = computed<string | null>(() => {
  const param = route.params.conversationUuid;
  return param ? String(param) : null;
});

const {messageHistory, createConversation, postMessage, isStreaming, streamStatus} =
    useConversation(conversationUuid);

const STATUS_LABELS: Record<string, string> = {
  thinking: "Thinking for a good answer...",
  researching: "Researching official sources...",
  writing: "Writing your answer...",
};
const statusLabel = computed(
    () => STATUS_LABELS[streamStatus.value ?? "thinking"] ?? "Thinking...",
);

async function onSubmit(prompt: string) {
  try {
    if (!conversationUuid.value) {
      const response = await createConversation(userId.value!);
      // stream the reply on the current view, then navigate into the conversation
      await postMessage(prompt);
      await router.push({path: `/conversations/${response.uuid}`});
    } else {
      await postMessage(prompt);
    }
  } catch (e) {
    console.error(e);
    toast("Oops, an error occurred", {
      description: "Please try again later",
    });
  }
}
</script>

<template>
  <div
    v-if="messageHistory.length > 0 || isStreaming"
    class="max-w-3xl mx-auto flex flex-col h-screen"
  >
    <div class="flex-1 overflow-y-scroll my-4 mb-36 px-4">
      <!-- Render the chat history -->
      <div
        v-for="(message, i) in messageHistory"
        :key="i"
      >
        <div
          v-if="message.parts[0].part_kind === 'user-prompt'"
          class="p-3 bg-blue-100 rounded-lg text-right my-2"
        >
          {{ message.parts[0].content }}
        </div>
        <div
          v-else-if="message.parts[0].part_kind === 'text'"
          class="p-3 text-left my-2"
        >
          <AIResponse
            v-if="message.parts[0].content"
            :source="message.parts[0].content"
          />
          <div
            v-else-if="isStreaming"
            class="text-body font-semibold text-transparent bg-clip-text bg-gradient-to-r to-gray-300 via-gray-500 from-gray-800 bg-[length:200%_100%] animate-shimmer"
          >
            {{ statusLabel }}
          </div>
        </div>
      </div>
    </div>

    <UserPromptInput
      class="fixed bottom-3 w-full max-w-3xl bg-white p-4 shadow-lg z-10"
      @submit-prompt="onSubmit($event)"
    />
  </div>
  <div
    v-else
    class="md:max-w-3xl p-4 md:p-0 mx-auto h-screen flex flex-col justify-center"
  >
    <h3
      v-if="messageHistory?.length === 0"
      class="mb-4 text-center text-2xl font-medium tracking-tight"
    >
      Hello, I am here to answer all of your Visa and Immigration
      questions!
    </h3>
    <UserPromptInput @submit-prompt="onSubmit($event)" />
  </div>
</template>
<style scoped>
@keyframes shimmer {
  0% {
    background-position: 0% 0%;
  }
  100% {
    background-position: -100% 0%;
  }
}

.animate-shimmer {
  animation: shimmer 1.25s ease-out infinite;
  /* works with Tailwind's bg-[length:...] utility above */
  background-position: 0% 0%;
}
</style>
