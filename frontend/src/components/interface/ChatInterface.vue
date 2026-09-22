<script setup lang="ts">
import {computed} from "vue";
import {useRoute, useRouter} from "vue-router";
import {useI18n} from "vue-i18n";
import AIResponse from "@/components/ui/chat/AIResponse.vue";
import SourcesList from "@/components/ui/chat/SourcesList.vue";
import ConversationDisclaimer from "@/components/interface/ConversationDisclaimer.vue";
import UserPromptInput from "@/components/interface/UserPromptInput.vue";
import {useConversation} from "@/composables/useConversations.ts";
import {describeScrub} from "@/lib/pii";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import {storeToRefs} from "pinia";
import {toast} from "vue-sonner";

const router = useRouter();
const route = useRoute();
const {t, locale} = useI18n();
const authStore = useAuthStore();
const {userId} = storeToRefs(authStore);

// derive a reactive conversationId from the URL
const conversationUuid = computed<string | null>(() => {
  const param = route.params.conversationUuid;
  return param ? String(param) : null;
});

const {
  messageHistory,
  createConversation,
  postMessage,
  stopStreaming,
  isStreaming,
  streamStatus,
  scrubNotices,
} = useConversation(conversationUuid);

// Server steps: "thinking" | "researching" | "writing" -> localized label.
const statusLabel = computed(() => t(`chat.${streamStatus.value ?? "thinking"}`));

// Per-message "we removed X before sending" notice, keyed on the (scrubbed)
// content that is actually shown/persisted. Empty string when nothing was
// scrubbed for that message.
function scrubNoticeFor(content: string): string {
  const summary = scrubNotices.value.get(content);
  return summary ? describeScrub(summary, locale.value as "en" | "es") : "";
}

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
    class="relative mx-auto flex w-full max-w-3xl flex-col flex-1 min-h-0"
  >
    <!-- Fade the conversation out under the navbar to hint that it scrolls -->
    <div
      class="pointer-events-none absolute inset-x-0 top-0 z-10 h-6 bg-gradient-to-b from-background to-transparent"
    />

    <!-- The only scrollable region -->
    <div class="flex-1 min-h-0 overflow-y-auto px-4 pt-4">
      <!-- Render the chat history -->
      <div
        v-for="(message, i) in messageHistory"
        :key="i"
      >
        <template v-if="message.parts[0].part_kind === 'user-prompt'">
          <div class="my-2 rounded-lg bg-accent p-3 text-right text-accent-foreground">
            {{ message.parts[0].content }}
          </div>
          <p
            v-if="scrubNoticeFor(message.parts[0].content)"
            class="text-right text-xs text-muted-foreground -mt-1 mb-2 px-1"
          >
            {{ scrubNoticeFor(message.parts[0].content) }}
          </p>
        </template>
        <div
          v-else-if="message.parts[0].part_kind === 'text'"
          class="p-3 text-left my-2"
        >
          <template v-if="message.parts[0].content">
            <AIResponse :source="message.parts[0].content" />
            <SourcesList :sources="message.sources" />
          </template>
          <div
            v-else-if="isStreaming"
            class="text-body font-semibold text-transparent bg-clip-text bg-gradient-to-r to-gray-300 via-gray-500 from-gray-800 bg-[length:200%_100%] animate-shimmer"
          >
            {{ statusLabel }}
          </div>
        </div>
      </div>
    </div>

    <!-- Composer: in normal flow at the bottom, with a fade above it and the -->
    <!-- disclaimer beneath, mirroring the marketing hero. -->
    <div class="relative shrink-0 px-4 pt-2 pb-3 sm:px-6">
      <div
        class="pointer-events-none absolute inset-x-0 -top-6 h-6 bg-gradient-to-t from-background to-transparent"
      />
      <UserPromptInput
        :streaming="isStreaming"
        @submit-prompt="onSubmit($event)"
        @stop="stopStreaming"
      />
      <ConversationDisclaimer class="mt-2" />
    </div>
  </div>
  <div
    v-else
    class="mx-auto flex w-full max-w-3xl flex-1 min-h-0 flex-col justify-center px-4 sm:px-6"
  >
    <h3
      v-if="messageHistory?.length === 0"
      class="mb-4 text-center text-2xl font-medium tracking-tight"
    >
      {{ $t("chat.welcome") }}
    </h3>
    <UserPromptInput
      :streaming="isStreaming"
      @submit-prompt="onSubmit($event)"
      @stop="stopStreaming"
    />
    <ConversationDisclaimer class="mt-3" />
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
