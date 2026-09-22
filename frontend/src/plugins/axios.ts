// src/plugins/axios.ts
import axios from 'axios'
import {authService} from '@/services/authService'
import {currentLocale} from '@/i18n'

// In dev, VITE_API_BASE_URL is unset and Vite proxies "/api" → http://api:8000
// (see vite.config.ts). In production (Cloudflare Pages) the API is a different
// origin (Railway), so this is set to the absolute API base incl. the /api prefix,
// e.g. https://api-frosty-rain-5363-production.up.railway.app/api. Cross-origin
// calls are covered by CORS on the Django side (CORS_ALLOWED_ORIGINS).
// Single source of truth for the API base URL. Everything that talks to the
// API — the axios apiClient below, and the native-fetch SSE chat stream in
// messageService — must use this so cross-origin production works.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {'Content-Type': 'application/json'}
})

let isRefreshing = false
let pendingRequests: (() => void)[] = []

function isAuthEndpoint(url?: string): boolean {
    if (!url) return false;
    // Adjust if your endpoints differ
    return url.includes("/auth/token/") || url.includes("/auth/token/refresh/");
}

apiClient.interceptors.request.use(config => {
    const token = authService.getAccessToken()
    if (token) config.headers!['Authorization'] = `Bearer ${token}`
    // Advertise the active UI locale so the API can localize responses (the
    // backend's LocaleMiddleware reads this into request.LANGUAGE_CODE).
    config.headers!['Accept-Language'] = currentLocale()
    return config
})

apiClient.interceptors.response.use(
    r => r,
    async err => {
        const status = err.response?.status
        const original = err?.config;
        // no response or not a 401, reject
        if (!original || status !== 401) {
            return Promise.reject(err);
        }

        // not a refresh endpoint, reject
        if (isAuthEndpoint(original?.url)) {
            return Promise.reject(err);
        }

        // already retried refresh token, reject
        if (original._retry) {
            return Promise.reject(err);
        }

        if (isRefreshing) {
            return new Promise((resolve) => {
                pendingRequests.push(() => {
                    const token = authService.getAccessToken();
                    const headers = {...(original.headers || {})};
                    if (token) {
                        headers["Authorization"] = `Bearer ${token}`;
                    } else {
                        delete headers["Authorization"];
                    }
                    resolve(apiClient({...original, headers}));
                });
            });
        }

        original._retry = true;
        isRefreshing = true;
        try {
            const {access} = await authService.refreshToken();

            // retry the original request with the new token
            const headers = {...(original.headers || {})};
            headers["Authorization"] = `Bearer ${access}`;

            // Flush queued requests
            pendingRequests.forEach(cb => cb());
            pendingRequests = [];

            return apiClient({...original, headers});
        } catch (err) {
            pendingRequests = [];
            authService.logout();
            window.location.href = "/login";
            return Promise.reject(err);
        } finally {
            isRefreshing = false;
        }

    }
)

export default apiClient
