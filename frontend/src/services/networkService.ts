import axios from "axios";
import type {PaginatedResponse} from "@/composables/usePagination.ts";

export interface Organization {
    id: number;
    name: string;
    slug: string;
    organization_type: string;
    addresses: any[];
    websites: string[];
    phone_numbers: string[];
    emails: string[];
    notes: string
    is_active: boolean;
}

const BASE_URL = '/api/network'
export const networkService = {
    async getOrganizations(page = 1, filters = {
        hasProBono: null,
        search: null,
        organizationType: null,
        subdivision: null,
        language: null,
    }): Promise<PaginatedResponse<Organization>> {
        // Create URLSearchParams object for query parameters
        const params = new URLSearchParams();

        // Add page parameter
        params.append('page', page.toString());

        // Add filters to query parameters, excluding null/undefined values
        Object.entries(filters).forEach(([key, value]) => {
            if (value !== null && value !== undefined) {
                // Convert camelCase to snake_case for API compatibility
                const apiKey = key.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
                params.append(apiKey, value.toString());
            }
        });

        const res = await axios.get<PaginatedResponse<Organization>>(
            `${BASE_URL}/organizations/?${params.toString()}`
        );
        return res.data;
    }
}