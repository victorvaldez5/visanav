// src/composables/useConversation.ts
import {onUnmounted, type Ref, ref, watch} from "vue";
import type {Conversation} from "@/services/conversationService";
import {conversationService} from "@/services/conversationService";
import type {MessagePayload} from "@/services/messageService";
import {messageService} from "@/services/messageService";
import {useRouter} from "vue-router";
import {toast} from "vue-sonner";

export function useConversation(
    conversationUuid: Ref<string | null> = ref(null),
) {
    // state
    const conversationId = ref<number | null>(null);
    // the uuid the chat endpoint is keyed on; set on load and on create, so the
    // first message of a brand-new conversation streams before the route changes
    const conversationKey = ref<string | null>(null);
    const messageHistory = ref<any[]>([]);
    const router = useRouter();

    // --- streaming state ---
    const isStreaming = ref(false);
    // current step reported by the server: "thinking" | "researching" | "writing"
    const streamStatus = ref<string | null>(null);
    let streamAbort: AbortController | null = null;

    // when route params change, fetch that conversation
    watch(
        conversationUuid,
        async (uuid) => {
            try {
                if (uuid == null) {
                    messageHistory.value = [];
                    conversationKey.value = null;
                    return;
                }
                const conv = await conversationService.getConversation(uuid);
                conversationId.value = conv.id;
                conversationKey.value = conv.uuid;
                messageHistory.value = conv.messages;
            } catch (e) {
                console.error("Error fetching conversation:", e);
                toast("Oops, an error occurred", {
                    description: "You aren't allowed there!",
                });
                await router.push({name: "Home"});
            }
        },
        {immediate: true},
    );

    // create a new conversation and navigate into it
    async function createConversation(
        userId: number,
        title = "New Conversation",
    ): Promise<Conversation> {
        const conv = await conversationService.createConversation(title, userId);
        conversationId.value = conv.id;
        conversationKey.value = conv.uuid;
        return conv;
    }

    function stopStreaming() {
        if (streamAbort) {
            streamAbort.abort();
            streamAbort = null;
        }
        isStreaming.value = false;
        streamStatus.value = null;
    }

    // post a message and stream the assistant's reply token-by-token
    async function postMessage(prompt: string) {
        if (!prompt.trim() || conversationKey.value == null) return;

        const payload: MessagePayload = {
            user_message: prompt,
            conversation: conversationKey.value,
        };

        // optimistic render: user bubble + growing assistant bubble
        messageHistory.value.push({parts: [{part_kind: "user-prompt", content: prompt}]});
        const assistantIndex =
            messageHistory.value.push({parts: [{part_kind: "text", content: ""}]}) - 1;

        isStreaming.value = true;
        streamStatus.value = "thinking";
        streamAbort = new AbortController();

        let succeeded = false;
        try {
            await messageService.streamMessage(
                payload,
                {
                    onStatus: (step) => {
                        streamStatus.value = step;
                    },
                    onDelta: (text) => {
                        // mutate through the reactive proxy so Vue tracks it
                        messageHistory.value[assistantIndex].parts[0].content += text;
                    },
                    onDone: () => {
                        succeeded = true;
                    },
                    onError: (detail) => {
                        const part = messageHistory.value[assistantIndex].parts[0];
                        part.content = part.content || `⚠️ ${detail}`;
                        toast("Something went wrong", {description: detail});
                    },
                },
                streamAbort.signal,
            );
        } catch (e) {
            console.error("Error streaming message:", e);
            toast("Something went wrong", {
                description: "Please try again later",
            });
        } finally {
            isStreaming.value = false;
            streamStatus.value = null;
            streamAbort = null;
        }

        // On success, sync with the server's canonical, persisted messages.
        if (succeeded && conversationKey.value) {
            try {
                const {messages} = await conversationService.getConversation(
                    conversationKey.value,
                );
                messageHistory.value = messages;
            } catch (e) {
                console.error("Error refreshing conversation:", e);
            }
        }
    }

    onUnmounted(() => stopStreaming());

    return {
        // state
        conversationId,
        messageHistory,
        isStreaming,
        streamStatus,

        // actions
        createConversation,
        postMessage,
    };
}
