import {defineStore} from "pinia";
import {computed, ref} from "vue";
import apiClient from "@/plugins/axios";
import {authService} from "@/services/authService";
import {useRouter} from "vue-router";
import {toast} from "vue-sonner";
import {currentLocale, hasSavedLocale, i18n} from "@/i18n";
import {syncLocaleOnLogin} from "@/services/profileLocale";

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
    // What to call the signed-in user: their username, else their email.
    const displayName = computed(() => username.value || userEmail.value || "");

    // helpers
    function setFromToken(token: string) {
        accessToken.value = token;
        apiClient.defaults.headers["Authorization"] = `Bearer ${token}`;
        const payload = decodeJwt(token);
        userId.value = payload?.user_id ?? null;
        userEmail.value = payload?.email ?? null;
        username.value = payload?.username ?? null;
        // A token minted without the identity claims (older sessions) would leave
        // the account menu blank, so look the user up instead.
        if (userId.value !== null && !userEmail.value && !username.value) {
            void loadIdentity(userId.value);
        }
    }

    // Best effort: a failed lookup just leaves the menu on its fallback label.
    async function loadIdentity(id: number) {
        try {
            const user = await authService.getUser(id);
            if (userId.value !== id) return; // signed out or switched meanwhile
            username.value = user?.username || null;
            userEmail.value = user?.email || null;
        } catch {
            /* ignore */
        }
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
            // Reconcile the UI language with the profile before routing, so the
            // next page renders in it. Best effort: it never throws.
            if (userId.value !== null) {
                await syncLocaleOnLogin(userId.value, hasSavedLocale(), currentLocale());
            }
            await router.push({name: "Home"}); // remove if you prefer to navigate in the component
        } catch (e: any) {
            error.value =
                e?.response?.data?.detail || i18n.global.t("auth.invalidCredentials");
            throw e;
        } finally {
            loading.value = false;
        }
    }

    async function register(email: string, password: string, password2: string, turnstileToken?: string) {
        loading.value = true;
        error.value = null;

        try {
            // Registration creates an inactive account; the user must confirm
            // their email before they can sign in, so we don't log them in here.
            await authService.register(email, password, password2, turnstileToken);
            toast(i18n.global.t("auth.accountCreated"), {
                description: i18n.global.t("auth.checkEmail"),
            });
            await router.push({name: "Login"});
        } catch (e: any) {
            error.value =
                e?.response?.data?.detail || i18n.global.t("auth.registrationFailed");
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
        displayName,

        // actions
        init,
        login,
        logout,
        refresh,
        register,
    };
});
