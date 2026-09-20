// src/services/conversationService.ts
import apiClient from "@/plugins/axios";
import type {PaginatedResponse} from "@/composables/usePagination.ts";

export interface Conversation {
    id: number;
    uuid: string;
    title: string;
    user?: number;
    messages: any[];
}

export const conversationService = {
    async getConversation(uuid: string): Promise<Conversation> {
        const res = await apiClient.get<Conversation>(`/conversations/${uuid}/`);
        return res.data;
    },

    async getAllConversations(page = 1): Promise<PaginatedResponse<Conversation>> {
        const res = await apiClient.get(`/conversations/?page=${page}`);
        return res.data;
    },

    async createConversation(
        title: string,
        user?: number,
    ): Promise<Conversation> {
        const res = await apiClient.post<Conversation>(`/conversations/`, {
            title,
            user,
        });
        return res.data;
    },

    async deleteConversation(uuid: string): Promise<void> {
        await apiClient.delete(`/conversations/${uuid}/`);
    },
};
