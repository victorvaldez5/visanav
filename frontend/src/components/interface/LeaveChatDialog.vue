<script setup lang="ts">
// Confirms leaving an open conversation for the landing page. Leaving starts a
// new chat, so it offers the conversation's link (with a copy button) for
// coming back to it later: for an anonymous visitor that link is the only way
// back.
import {ref, watch} from "vue";
import {useI18n} from "vue-i18n";
import {
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
} from "reka-ui";
import {buttonVariants} from "@/components/ui/button";

const props = defineProps<{
  /** Full URL of the conversation being left. */
  url: string;
}>();

const open = defineModel<boolean>("open", {default: false});
const emit = defineEmits<{ (e: "leave"): void }>();

const {t} = useI18n();
const linkInput = ref<HTMLInputElement | null>(null);
const copyState = ref<"idle" | "copied" | "failed">("idle");
let resetTimer: ReturnType<typeof setTimeout> | undefined;

watch(open, (isOpen) => {
  if (isOpen) copyState.value = "idle";
});

async function copyLink() {
  clearTimeout(resetTimer);
  try {
    await navigator.clipboard.writeText(props.url);
    copyState.value = "copied";
    resetTimer = setTimeout(() => (copyState.value = "idle"), 2000);
  } catch {
    // No clipboard access (insecure context, denied permission): select the
    // link so it can be copied by hand.
    linkInput.value?.select();
    copyState.value = "failed";
  }
}
</script>

<template>
  <AlertDialogRoot v-model:open="open">
    <AlertDialogPortal>
      <AlertDialogOverlay
        class="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0"
      />
      <AlertDialogContent
        class="fixed top-1/2 left-1/2 z-50 grid w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl bg-background p-6 shadow-elevation-3 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
      >
        <div class="grid gap-2">
          <AlertDialogTitle class="text-lg font-semibold">
            {{ t("leaveChat.title") }}
          </AlertDialogTitle>
          <AlertDialogDescription class="text-sm text-muted-foreground">
            {{ t("leaveChat.description") }}
          </AlertDialogDescription>
        </div>

        <div class="grid gap-1.5">
          <label
            for="leave-chat-link"
            class="text-sm font-medium"
          >{{ t("leaveChat.linkLabel") }}</label>
          <div class="flex gap-2">
            <input
              id="leave-chat-link"
              ref="linkInput"
              :value="url"
              readonly
              class="h-10 min-w-0 flex-1 rounded-lg border border-transparent bg-field px-3 text-sm text-foreground shadow-elevation-1-control outline-none focus-visible:shadow-glow-focus"
              @focus="($event.target as HTMLInputElement).select()"
            >
            <button
              type="button"
              :class="buttonVariants({variant: 'outline'})"
              @click="copyLink"
            >
              {{ copyState === "copied" ? t("leaveChat.copied") : t("leaveChat.copy") }}
            </button>
          </div>
          <p
            class="min-h-4 text-xs text-muted-foreground"
            aria-live="polite"
          >
            <template v-if="copyState === 'copied'">
              {{ t("leaveChat.copiedNotice") }}
            </template>
            <template v-else-if="copyState === 'failed'">
              {{ t("leaveChat.copyError") }}
            </template>
          </p>
        </div>

        <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <AlertDialogCancel :class="buttonVariants({variant: 'ghost'})">
            {{ t("leaveChat.stay") }}
          </AlertDialogCancel>
          <AlertDialogAction
            :class="buttonVariants()"
            @click="emit('leave')"
          >
            {{ t("leaveChat.leave") }}
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
