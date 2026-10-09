<template>
  <!--
    The chat composer. One borderless field surface (elevation at rest, an
    ocean/sunflower focus glow) holding the message textarea over a footer row:
    a privacy reassurance on the left, and the send action on the right. While
    Javi is answering (`streaming`), Send becomes a neutral Stop that aborts the
    stream. Styling uses the VisaNav design-system tokens defined in style.css.
  -->
  <div
    class="rounded-xl border border-transparent bg-field px-3 pt-3 pb-2 shadow-elevation-1-control transition-shadow focus-within:shadow-glow-focus"
  >
    <label
      :for="fieldId"
      class="sr-only"
    >{{ $t("chat.placeholder") }}</label>
    <textarea
      :id="fieldId"
      v-model="prompt"
      rows="1"
      :placeholder="$t('chat.placeholder')"
      class="field-sizing-content max-h-40 w-full resize-none border-0 bg-transparent p-0 text-base leading-6 text-foreground outline-none placeholder:text-field-placeholder"
      @keydown="onKeydown"
    />

    <div class="mt-1.5 flex items-end justify-between gap-2">
      <p class="flex items-center gap-1 text-xs leading-4 text-muted-foreground">
        <svg
          class="block"
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <rect
            x="3"
            y="11"
            width="18"
            height="11"
            rx="2"
          />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
        <span>{{ $t("chat.privacy") }}</span>
      </p>

      <button
        v-if="streaming"
        type="button"
        :aria-label="$t('chat.stop')"
        class="grid size-6 shrink-0 place-items-center rounded border border-transparent bg-raised text-foreground shadow-elevation-1-control transition hover:-translate-y-0.5 hover:shadow-elevation-2 focus-visible:shadow-[var(--button-focus)] focus-visible:outline-none active:translate-y-0"
        @click="emit('stop')"
      >
        <svg
          class="block"
          width="11"
          height="11"
          viewBox="0 0 24 24"
          fill="currentColor"
          aria-hidden="true"
        >
          <rect
            x="6"
            y="6"
            width="12"
            height="12"
            rx="2"
          />
        </svg>
      </button>
      <button
        v-else
        type="submit"
        :aria-label="$t('chat.send')"
        :disabled="!canSend"
        class="grid size-6 shrink-0 place-items-center rounded border border-transparent bg-primary text-primary-foreground shadow-button-primary-rest transition hover:-translate-y-0.5 hover:shadow-elevation-2 focus-visible:shadow-[var(--button-focus)] focus-visible:outline-none active:translate-y-0 disabled:pointer-events-none disabled:opacity-45 disabled:shadow-none"
        @click="sendPrompt"
      >
        <svg
          class="block"
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.25"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M12 19V5" />
          <path d="M5 12l7-7 7 7" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

const props = withDefaults(
  defineProps<{
    /** True while Javi is answering: swaps Send for a Stop that aborts. */
    streaming?: boolean;
    /** Text to start the composer with (a question handed off in the URL). */
    initial?: string;
  }>(),
  { streaming: false, initial: "" },
);

const emit = defineEmits<{
  (e: "submit-prompt", value: string): void;
  (e: "stop"): void;
}>();

const prompt = ref(props.initial);

// Unique id so the visually-hidden <label> ties to this instance's textarea.
const fieldId = `prompt-${Math.random().toString(36).slice(2, 9)}`;

const canSend = computed(
  () => prompt.value.trim().length > 0 && !props.streaming,
);

function sendPrompt() {
  if (!canSend.value) return;
  emit("submit-prompt", prompt.value.trim());
  prompt.value = "";
}

// Enter sends; Shift+Enter inserts a newline. During IME composition (e.g.
// entering accented or non-Latin text), Enter is left to the input method.
function onKeydown(e: KeyboardEvent) {
  if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
  e.preventDefault();
  if (props.streaming) return;
  sendPrompt();
}
</script>
