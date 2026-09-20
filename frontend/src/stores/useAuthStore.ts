import {defineStore} from "pinia";
import {computed, ref} from "vue";
import apiClient from "@/plugins/axios";
import {authService} from "@/services/authService";
import {useRouter} from "vue-router";

interface JwtPayload {
    user_id?: number;
    username?: string;
    email?: string;
}

function decodeJwt(token: string): JwtPayload | null {
    try {
        const base64Payload = token.split(".")[1];
        const json = atob(base64Payload);
        return JSON.parse(json);
    } catch (error) {
        console.error("Error decoding JWT:", error);
        return null;
    }
}

export const useAuthStore = defineStore("auth", () => {
    // state
    const loading = ref(false);
    const error = ref<string | null>(null);
    const userEmail = ref<string | null>(null);
    const userId = ref<number | null>(null);
    const username = ref<string | null>(null);
    const accessToken = ref<string>("");
    const router = useRouter();

    // getters
    const isAuthenticated = computed(() => !!accessToken.value);

    // helpers
    function setFromToken(token: string) {
        accessToken.value = token;
        apiClient.defaults.headers["Authorization"] = `Bearer ${token}`;
        const payload = decodeJwt(token);
        userId.value = payload?.user_id ?? null;
        userEmail.value = payload?.email ?? null;
        username.value = payload?.username ?? null;
    }

    // actions
    function init() {
        const token = authService.getAccessToken() || "";
        if (token) {
            setFromToken(token);
        } else {
            clearAuth();
        }
    }

    function clearAuth() {
        accessToken.value = "";
        delete apiClient.defaults.headers["Authorization"];
        userId.value = null;
        userEmail.value = null;
        username.value = null;
    }

    async function login(loginOrEmail: string, password: string, turnstileToken?: string) {
        loading.value = true;
        error.value = null;
        try {
            const {access} = await authService.login(loginOrEmail, password, turnstileToken);
            setFromToken(access);
            await router.push({name: "Home"}); // remove if you prefer to navigate in the component
        } catch (e: any) {
            error.value =
                e?.response?.data?.detail || "Invalid username or password.";
            throw e;
        } finally {
            loading.value = false;
        }
    }

    async function register(email: string, password: string, password2: string, turnstileToken?: string) {
        loading.value = true;
        error.value = null;

        try {
            const {access} = await authService.register(email, password, password2, turnstileToken);
            setFromToken(access);
            await router.push({name: "Home"});
        } catch (e: any) {
            error.value =
                e?.response?.data?.detail || "Invalid username or password.";
            throw e;
        } finally {
            loading.value = false;
        }
    }

    function logout() {
        authService.logout();
        clearAuth();
        error.value = null;
        router.push({name: "Login"}).catch(() => {
        });
    }

    async function refresh() {
        const {access} = await authService.refreshToken();
        setFromToken(access);
    }

    return {
        // state
        loading,
        error,
        userEmail,
        username,
        userId,
        accessToken,

        // getters
        isAuthenticated,

        // actions
        init,
        login,
        logout,
        refresh,
        register,
    };
});
