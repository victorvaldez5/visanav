<script setup lang="ts">
import {computed, ref} from "vue";
import {useRoute, useRouter} from "vue-router";
import {useI18n} from "vue-i18n";
import AIResponse from "@/components/ui/chat/AIResponse.vue";
import SourcesList from "@/components/ui/chat/SourcesList.vue";
import ConversationDisclaimer from "@/components/interface/ConversationDisclaimer.vue";
import UserPromptInput from "@/components/interface/UserPromptInput.vue";
import {Button} from "@/components/ui/button";
import {useConversation} from "@/composables/useConversations.ts";
import {describeScrub} from "@/lib/pii";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import {storeToRefs} from "pinia";
import {toast} from "vue-sonner";

const router = useRouter();
const route = useRoute();
const {t, locale} = useI18n();
const authStore = useAuthStore();
const {userId, isAuthenticated} = storeToRefs(authStore);

// derive a reactive conversationId from the URL
const conversationUuid = computed<string | null>(() => {
  const param = route.params.conversationUuid;
  return param ? String(param) : null;
});

const {
  conversationKey,
  messageHistory,
  createConversation,
  deleteConversation,
  postMessage,
  isStreaming,
  streamStatus,
  scrubNotices,
} = useConversation(conversationUuid, {isAuthenticated: () => isAuthenticated.value});

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
    if (conversationKey.value == null) {
      const response = await createConversation(userId.value ?? undefined);
      // Stream the reply on the current view. Signed-in users then move to the
      // shareable /conversations/:uuid URL (and get a sidebar entry); anonymous
      // chats deliberately stay on "/" so the bearer link never lands in a
      // shared device's history — it's held in sessionStorage and offered via
      // the explicit "Copy link" button instead.
      await postMessage(prompt);
      if (isAuthenticated.value) {
        await router.push({path: `/conversations/${response.uuid}`});
      }
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

// Two-step, in-app confirm so deletion (irreversible) never fires on a stray tap.
const confirmingDelete = ref(false);

async function onDelete() {
  if (!confirmingDelete.value) {
    confirmingDelete.value = true;
    return;
  }
  confirmingDelete.value = false;
  try {
    await deleteConversation();
    toast(t("chat.deleted"));
    // Signed-in users were viewing a /conversations/:uuid URL; return Home.
    // Anonymous users are already on "/", now reset to the welcome view.
    if (conversationUuid.value) await router.push({name: "Home"});
  } catch (e) {
    console.error(e);
    toast(t("chat.deleteFailed"));
  }
}

// Anonymous only: the sole way to persist the (bearer) link, with a clear
// warning. A signed-in user's conversation is owner-scoped, so its URL isn't a
// bearer token and the address bar already holds it — no copy affordance needed.
async function copyLink() {
  const key = conversationKey.value;
  if (!key) return;
  const url = `${window.location.origin}/conversations/${key}`;
  try {
    await navigator.clipboard.writeText(url);
    toast(t("chat.linkCopied"), {description: t("chat.linkCopiedHint")});
  } catch {
    toast(t("chat.copyFailed"), {description: url});
  }
}
</script>

<template>
  <div
    v-if="messageHistory.length > 0 || isStreaming"
    class="max-w-3xl mx-auto flex flex-col h-screen"
  >
    <!-- Per-conversation controls: copy the bearer link (anonymous only) and
         delete. Kept lightweight; only shown once a conversation exists. -->
    <div
      v-if="conversationKey"
      class="flex items-center justify-end gap-2 px-4 pt-3"
    >
      <Button
        v-if="!isAuthenticated"
        variant="ghost"
        size="sm"
        @click="copyLink"
      >
        {{ t("chat.copyLink") }}
      </Button>
      <template v-if="!confirmingDelete">
        <Button
          variant="ghost"
          size="sm"
          class="text-destructive hover:text-destructive"
          @click="onDelete"
        >
          {{ t("chat.deleteChat") }}
        </Button>
      </template>
      <template v-else>
        <Button
          variant="destructive"
          size="sm"
          @click="onDelete"
        >
          {{ t("chat.deleteConfirm") }}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          @click="confirmingDelete = false"
        >
          {{ t("chat.cancel") }}
        </Button>
      </template>
    </div>
    <div class="flex-1 overflow-y-scroll my-4 mb-36 px-4">
      <!-- Short disclaimer at the start of the conversation -->
      <ConversationDisclaimer class="mb-4" />
      <!-- Render the chat history -->
      <div
        v-for="(message, i) in messageHistory"
        :key="i"
      >
        <template v-if="message.parts[0].part_kind === 'user-prompt'">
          <div class="p-3 bg-blue-100 rounded-lg text-right my-2">
            {{ message.parts[0].content }}
          </div>
          <p
            v-if="scrubNoticeFor(message.parts[0].content)"
            class="text-right text-xs text-gray-500 -mt-1 mb-2 px-1"
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
      {{ $t("chat.welcome") }}
    </h3>
    <UserPromptInput @submit-prompt="onSubmit($event)" />
    <ConversationDisclaimer class="mt-4" />
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
