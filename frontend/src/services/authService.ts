import apiClient from "@/plugins/axios.ts";

const API_BASE = "/auth";

interface TokenResponse {
    access: string;
    refresh: string;
}

interface RegisterResponse {
    email: string;
    detail?: string;
}

interface VerifyResponse {
    userId: number;
    access: string;
    refresh: string;
}

async function getToken(email: string, password: string, turnstileToken?: string) {
    const resp = await apiClient.post<TokenResponse>(`${API_BASE}/token/`, {
        username: email,
        password,
        turnstile_token: turnstileToken ?? ""
    }, {headers: {"Content-Type": "application/x-www-form-urlencoded"}});
    localStorage.setItem("access_token", resp.data.access);
    localStorage.setItem("refresh_token", resp.data.refresh);
    return resp.data;
}


export const authService = {
    async login(email: string, password: string, turnstileToken?: string) {
        const {access, refresh} = await getToken(email, password, turnstileToken);
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

    async register(email: string, password: string, password2: string, turnstileToken?: string) {
        // Registration no longer issues a session: the account is created
        // inactive and must be confirmed via the emailed link (see verify()).
        const resp = await apiClient.post<RegisterResponse>(
            `${API_BASE}/register/`,
            {email, password, password2, turnstile_token: turnstileToken ?? ""},
            {headers: {"Content-Type": "application/x-www-form-urlencoded"}},
        );
        return resp.data;
    },

    async verify(uid: string, token: string) {
        // Activates the account from the emailed link and signs the user in.
        const resp = await apiClient.post<VerifyResponse>(`${API_BASE}/verify`, {uid, token});
        localStorage.setItem("access_token", resp.data.access);
        localStorage.setItem("refresh_token", resp.data.refresh);
        apiClient.defaults.headers["Authorization"] = `Bearer ${resp.data.access}`;
        return resp.data;
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
