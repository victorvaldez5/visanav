import apiClient from "@/plugins/axios.ts";

const API_BASE = "/auth";

interface TokenResponse {
    access: string;
    refresh: string;
}

async function getToken(email: string, password: string) {
    const resp = await apiClient.post<TokenResponse>(`${API_BASE}/token/`, {
        username: email,
        password
    }, {headers: {"Content-Type": "application/x-www-form-urlencoded"}});
    localStorage.setItem("access_token", resp.data.access);
    localStorage.setItem("refresh_token", resp.data.refresh);
    return resp.data;
}


export const authService = {
    async login(email: string, password: string) {
        const {access, refresh} = await getToken(email, password);
        localStorage.setItem("access_token", access);
        localStorage.setItem("refresh_token", refresh);
        apiClient.defaults.headers["Authorization"] = `Bearer ${access}`;
        return {access, refresh};
    },

    logout() {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        delete apiClient.defaults.headers["Authorization"];
    },

    async register(email: string, password: string, password2: string) {
        await apiClient.post(
            `${API_BASE}/register/`,
            {email: email, password: password, password2: password2},
            {headers: {"Content-Type": "application/x-www-form-urlencoded"}},
        );
        const {access, refresh} = await getToken(email, password);
        localStorage.setItem("access_token", access);
        localStorage.setItem("refresh_token", refresh);
        apiClient.defaults.headers["Authorization"] = `Bearer ${access}`;
        return {access, refresh};
    },
    getAccessToken() {
        return localStorage.getItem("access_token");
    },

    async refreshToken() {
        const refresh = localStorage.getItem("refresh_token");
        if (!refresh) throw new Error("No refresh token");
        const res = await apiClient.post<TokenResponse>(`${API_BASE}/token/refresh/`, {
            refresh,
        });
        localStorage.setItem("access_token", res.data.access);
        if (res.data.refresh)
            localStorage.setItem("refresh_token", res.data.refresh);
        apiClient.defaults.headers["Authorization"] = `Bearer ${res.data.access}`;
        return {access: res.data.access, refresh: res.data.refresh || refresh};
    },

    async getProfile(userId: number) {
        const res = await apiClient.get<any>(`${API_BASE}/profiles/${userId}/`);
        return res.data;
    },

    async getUser(userId: number) {
        const res = await apiClient.get<any>(`${API_BASE}/users/${userId}/`);
        return res.data;
    },

    async updateUser(userId: number, data: any) {
        const res = await apiClient.patch<any>(`${API_BASE}/users/${userId}/`, data);
        return res.data;
    },

    async updateProfile(userId: number, data: any) {
        const res = await apiClient.patch<any>(`${API_BASE}/profiles/${userId}/`, data);
        return res.data;
    },

    async deleteUser(userId: number) {
        const res = await apiClient.delete<any>(`${API_BASE}/users/${userId}/`);
        return res.data;
    }

};
