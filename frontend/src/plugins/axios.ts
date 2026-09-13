// src/plugins/axios.ts
import axios from 'axios'
import {authService} from '@/services/authService'

const apiClient = axios.create({
    baseURL: '/api',
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
