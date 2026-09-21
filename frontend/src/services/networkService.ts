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
// converted to snake_case query params before being sent to the API. Array
// values (e.g. `cost`) are sent as repeated params so the API can OR them.
export interface OrganizationFilters {
    search?: string | null;
    organizationType?: string | null;
    region?: string | null;
    // Cost chips: any of "pro_bono" | "free" | "low-cost" | "sliding-scale".
    cost?: string[] | null;
    // DRF OrderingFilter value, e.g. "name", "-last_verified".
    ordering?: string | null;
    proBono?: boolean | null;
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

// A DOJ-accredited representative. The roster gives a rep no contact details or
// location of their own, so the API fills organization_name/phone and city/state
// in from the linked organization, and computes days_left from the expiry.
export interface Representative {
    id: number;
    name: string;
    provider_type: string;
    credential: string;
    organization: number | null;
    organization_name: string | null;
    organization_phone: string | null;
    email: string;
    phone: string;
    website: string;
    address: OrganizationAddress | null;
    city: string | null;
    state: string | null;
    dhs_only: boolean;
    accreditation_expiration: string | null;
    days_left: number | null;
    is_active: boolean;
    source_url: string;
    last_verified: string | null;
}

// Filters accepted by getRepresentatives (see api/network/views.py).
export interface RepresentativeFilters {
    search?: string | null;
    // Organization's state (subdivision name, e.g. "Arizona").
    region?: string | null;
    dhsOnly?: boolean | null;
    // Accreditation lapses within N days (backs the "expiring soon" chip).
    expiresWithin?: number | null;
    ordering?: string | null;
    providerType?: string | null;
}

type FilterValue = string | number | boolean | string[] | null | undefined;

// Build query params, converting camelCase → snake_case, dropping empty values,
// and expanding arrays into repeated params (cost=free&cost=low-cost).
function buildParams(page: number, filters: Record<string, FilterValue>): URLSearchParams {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    for (const [key, value] of Object.entries(filters)) {
        if (value === null || value === undefined || value === "") continue;
        const apiKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
        if (Array.isArray(value)) {
            for (const item of value) {
                if (item !== null && item !== undefined && item !== "") {
                    params.append(apiKey, String(item));
                }
            }
        } else {
            params.append(apiKey, String(value));
        }
    }
    return params;
}

// Path is relative to apiClient's baseURL (which already includes /api).
const BASE_URL = "/network";

export const networkService = {
    async getOrganizations(
        page = 1,
        filters: OrganizationFilters = {},
    ): Promise<PaginatedResponse<Organization>> {
        const params = buildParams(page, filters as Record<string, FilterValue>);
        const res = await apiClient.get<PaginatedResponse<Organization>>(
            `${BASE_URL}/organizations/?${params.toString()}`,
        );
        return res.data;
    },

    async getRepresentatives(
        page = 1,
        filters: RepresentativeFilters = {},
    ): Promise<PaginatedResponse<Representative>> {
        // The reps directory only lists DOJ-accredited reps (not bar attorneys).
        const merged = {providerType: "doj-accredited-rep", ...filters};
        const params = buildParams(page, merged as Record<string, FilterValue>);
        const res = await apiClient.get<PaginatedResponse<Representative>>(
            `${BASE_URL}/representatives/?${params.toString()}`,
        );
        return res.data;
    },
};
