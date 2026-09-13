import {createRouter, createWebHistory} from "vue-router";
import {authService} from "@/services/authService.ts";
import apiClient from "@/plugins/axios.ts";

const routes = [
    {
        path: "/",
        component: () => import("@/components/interface/ChatInterface.vue"),
        name: "Home",
    },
    {
        path: "/login",
        component: () => import("@/pages/auth/LoginView.vue"),
        name: "Login",
    },
    {
        path: "/register",
        component: () => import("@/pages/auth/RegisterView.vue"),
        name: "Register",
    },
    {
        path: "/verify",
        name: "Verify",
        // Lightweight inline component; page will immediately redirect in beforeEnter
        component: {template: "<div>Verifying your account...</div>"},
        beforeEnter: async (to: any, _from: any, next: any) => {
            const uidParam = to.query.uid;
            const tokenParam = to.query.token;

            const uid = Array.isArray(uidParam) ? uidParam[0] : uidParam;
            const token = Array.isArray(tokenParam) ? tokenParam[0] : tokenParam;

            if (!uid || !token) {
                // Missing params; send to login or an error page
                return next({name: "Login"});
            }

            try {
                // Adjust URL/method/payload to match your backend
                // Example: Django endpoint that verifies email/activation
                const {data} = await apiClient.post("/api/auth/verify", {uid, token});

                // Expect backend to return the user's id to route to profile
                const userId = data?.userId;
                if (userId) {
                    return next({name: "Profile", params: {userId}});
                }

                // If no userId provided, choose a sensible fallback
                return next({name: "Home"});
            } catch (e: any) {
                // On failure, choose where to land; could also go to a dedicated error page
                console.error("Error verifying email:", e);
                return next({name: "Login"});
            }
        },
    },

    {
        path: `/profile/:userId`,
        component: () => import("@/pages/auth/UserProfile.vue"),
        name: 'Profile',
        meta: {requiresAuth: true},
    },
    {
        path: `/conversations/:conversationUuid`,
        component: () => import("@/components/interface/ChatInterface.vue"),
        name: "Conversation",
    },

    {
        path: "/documents",
        component: () => import("@/pages/DocumentsView.vue"),
        name: "Documents",
    },
    {
        path: "/forms",
        component: () => import("@/pages/FormsView.vue"),
        name: "Forms",
    },
    {
        path: "/attorneys",
        component: () => import("@/pages/NetworkListView.vue"),
        name: "Attorneys",
    },
    {
        path: "/error",
        component: () => import("@/pages/ServerError.vue"),
        name: "ServerError",
    },
    {
        path: "/permission-denied",
        component: () => import("@/pages/Forbidden.vue"),
        name: "PermissionDenied",
    },
    {
        path: "/forbidden",
        name: "forbidden",
        component: () => import("@/pages/Forbidden.vue"),
    },
    {
        path: "/:pathMatch(.*)*",
        name: "NotFound",
        component: () => import("@/pages/NotFound.vue"),
    },
];

const router = createRouter({
    history: createWebHistory(),
    routes,
});

router.beforeEach((to, _, next) => {
    const isAuth = !!authService.getAccessToken();
    if (to.meta.requiresAuth && !isAuth) {
        return next({name: "Login"});
    }
    if (to.name === "LoginView" && isAuth) {
        return next({name: "Home"});
    }
    next();
});

export default router;
