import apiClient from "@/plugins/axios.ts";

const API_BASE = "/locations"

// interface Country {
//     country_code: string;
//     name: string;
// }
//
// interface Subdivision {
//     code: string;
//     name: string;
//     type: string;
//     country: string;
// }


export const locationService = {
    async getCountries() {
        const resp = await apiClient.get<any>(`${API_BASE}/countries/?page_size=300`)
        return resp.data.results
    },

    async getSubdivisions(country: string) {
        const resp = await apiClient.get<any>(`${API_BASE}/subdivisions/?country=${country}&page_size=1000`)
        return resp.data.results
    },
    async getLanguages() {
        const resp = await apiClient.get<any>(`${API_BASE}/languages/?page_size=300`)
        return resp.data.results
    }
}
