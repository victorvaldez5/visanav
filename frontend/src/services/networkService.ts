import apiClient from "@/plugins/axios";
import type {PaginatedResponse} from "@/composables/usePagination.ts";

// The API serializes phone numbers, emails, and websites as objects (see
// api/network/serializers.py), not bare strings.
export interface OrganizationPhoneNumber {
    id: number;
    phone_number: string;
    is_primary: boolean;
}

export interface OrganizationEmail {
    id: number;
    email: string;
    is_primary: boolean;
}

export interface OrganizationWebsite {
    id: number;
    website: string;
}

// Filters accepted by getOrganizations. All optional; camelCase keys are
// converted to snake_case query params before being sent to the API.
export interface OrganizationFilters {
    hasProBono?: boolean | null;
    search?: string | null;
    organizationType?: string | null;
    subdivision?: string | null;
    language?: string | null;
}

export interface Organization {
    id: number;
    name: string;
    slug: string;
    organization_type: string;
    addresses: any[];
    websites: OrganizationWebsite[];
    phone_numbers: OrganizationPhoneNumber[];
    emails: OrganizationEmail[];
    notes: string
    is_active: boolean;
}

// Path is relative to apiClient's baseURL (which already includes /api).
const BASE_URL = '/network'
export const networkService = {
    async getOrganizations(page = 1, filters: OrganizationFilters = {
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

        const res = await apiClient.get<PaginatedResponse<Organization>>(
            `${BASE_URL}/organizations/?${params.toString()}`
        );
        return res.data;
    }
}