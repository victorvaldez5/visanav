import apiClient from "@/plugins/axios";
import type {PaginatedResponse} from "@/composables/usePagination.ts";

// The API serializes contact details as flat string arrays (see
// api/network/serializers.py); only the address is a nested object.
export interface OrganizationAddress {
    line1: string;
    line2: string;
    city: string;
    postal_code: string;
    subdivision: { code: string; name: string } | null;
}

// Filters accepted by getOrganizations. All optional; camelCase keys are
// converted to snake_case query params before being sent to the API.
export interface OrganizationFilters {
    proBono?: boolean | null;
    search?: string | null;
    organizationType?: string | null;
    region?: string | null;
    service?: string | null;
    language?: string | null;
}

export interface Organization {
    id: number;
    name: string;
    slug: string;
    organization_type: string;
    description: string;
    pro_bono: boolean;
    fee_model: string;
    accreditation: string;
    services: string[];
    languages: string[];
    address: OrganizationAddress | null;
    websites: string[];
    emails: string[];
    phones: string[];
    country: string;
    source_url: string;
    last_verified: string | null;
    is_active: boolean;
}

// Path is relative to apiClient's baseURL (which already includes /api).
const BASE_URL = '/network'
export const networkService = {
    async getOrganizations(page = 1, filters: OrganizationFilters = {
        proBono: null,
        search: null,
        organizationType: null,
        region: null,
        service: null,
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
