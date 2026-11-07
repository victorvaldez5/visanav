<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import Icon from "@/components/ui/Icon.vue";
import { conversationService } from "@/services/conversationService";

const props = defineProps<{
  conversationUuid: string;
  messageId: number;
  initial: boolean | null;
}>();

const { t } = useI18n();
const vote = ref<boolean | null>(props.initial ?? null);
const note = ref<"thanks" | "error" | null>(null);
let timer: ReturnType<typeof setTimeout> | undefined;

function flash(kind: "thanks" | "error") {
  note.value = kind;
  clearTimeout(timer);
  timer = setTimeout(() => (note.value = null), 3000);
}

async function choose(value: boolean) {
  const previous = vote.value;
  const next = previous === value ? null : value;
  vote.value = next; // optimistic
  try {
    await conversationService.setFeedback(props.conversationUuid, props.messageId, next);
    if (next !== null) flash("thanks");
    else note.value = null;
  } catch {
    vote.value = previous;
    flash("error");
  }
}

onBeforeUnmount(() => clearTimeout(timer));

const btn =
  "inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-pressed:bg-accent aria-pressed:text-foreground";
</script>

<template>
  <div class="mt-3 flex items-center gap-1 text-xs text-muted-foreground">
    <span>{{ t("chat.feedbackPrompt") }}</span>
    <button
      type="button"
      :class="btn"
      :aria-pressed="vote === true"
      :aria-label="t('chat.feedbackUp')"
      :title="t('chat.feedbackUp')"
      @click="choose(true)"
    >
      <span class="h-4 w-4"><Icon name="icon-thumbs-up" /></span>
    </button>
    <button
      type="button"
      :class="btn"
      :aria-pressed="vote === false"
      :aria-label="t('chat.feedbackDown')"
      :title="t('chat.feedbackDown')"
      @click="choose(false)"
    >
      <span class="h-4 w-4"><Icon name="icon-thumbs-down" /></span>
    </button>
    <span
      role="status"
      aria-live="polite"
    >{{ note ? t(note === "thanks" ? "chat.feedbackThanks" : "chat.feedbackError") : "" }}</span>
  </div>
</template>
