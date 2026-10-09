import {authService} from "@/services/authService";
import {API_BASE_URL} from "@/plugins/axios";
import {currentLocale, i18n} from "@/i18n";

export interface MessagePayload {
    user_message: string;
    /** The conversation's public uuid (never its integer id). */
    conversation: string;
}

/** An official source that grounded an answer (from the RAG corpus). */
export interface Source {
    id: string;
    title?: string | null;
    source_url?: string | null;
    /** ISO date (YYYY-MM-DD) the source was last checked, if known. */
    last_verified?: string | null;
    score?: number | null;
    topic?: string | null;
}

export interface StreamHandlers {
    onStatus?: (step: string) => void;
    onDelta?: (text: string) => void;
    onSources?: (sources: Source[]) => void;
    onDone?: (data: any) => void;
    onError?: (detail: string) => void;
}

// Native fetch (not the axios apiClient) is used here so the SSE response body
// can be streamed. Keep the base URL in sync with apiClient (see API_BASE_URL)
// so cross-origin production (app.visanav.org → api.visanav.org) works.
const CHAT_URL = `${API_BASE_URL}/chat/`;

function parseFrame(raw: string, handlers: StreamHandlers) {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
            event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trim());
        }
    }
    if (dataLines.length === 0) return;

    let data: any;
    try {
        data = JSON.parse(dataLines.join("\n"));
    } catch {
        return;
    }

    switch (event) {
        case "status":
            handlers.onStatus?.(data.step);
            break;
        case "delta":
            handlers.onDelta?.(data.text);
            break;
        case "sources":
            handlers.onSources?.(data.sources ?? []);
            break;
        case "done":
            handlers.onDone?.(data);
            break;
        case "error":
            handlers.onError?.(data.detail ?? i18n.global.t("errors.assistantFailed"));
            break;
    }
}

async function runStream(
    payload: MessagePayload,
    handlers: StreamHandlers,
    signal: AbortSignal | undefined,
    retried: boolean,
): Promise<void> {
    const token = authService.getAccessToken();
    const res = await fetch(CHAT_URL, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            // Advertise the active UI locale so Javi replies in the chosen
            // language (the chat view reads request.LANGUAGE_CODE into Deps).
            "Accept-Language": currentLocale(),
            ...(token ? {Authorization: `Bearer ${token}`} : {}),
        },
        body: JSON.stringify(payload),
        signal,
    });

    // Mirror the axios interceptor: refresh the access token once on 401.
    if (res.status === 401 && !retried) {
        try {
            await authService.refreshToken();
        } catch {
            authService.logout();
            window.location.href = "/login";
            return;
        }
        return runStream(payload, handlers, signal, true);
    }

    if (!res.ok || !res.body) {
        let detail = "Request failed. Please try again.";
        try {
            detail = (await res.json()).detail ?? detail;
        } catch {
            /* non-JSON error body */
        }
        handlers.onError?.(detail);
        return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});

        let sep: number;
        while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const frame = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            parseFrame(frame, handlers);
        }
    }
}

export const messageService = {
    /**
     * Post a chat message and consume the server's Server-Sent Events stream,
     * invoking the provided handlers as status/token/done/error frames arrive.
     */
    async streamMessage(
        payload: MessagePayload,
        handlers: StreamHandlers,
        signal?: AbortSignal,
    ): Promise<void> {
        await runStream(payload, handlers, signal, false);
    },
};
