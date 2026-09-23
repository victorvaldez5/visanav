import {createRouter, createWebHistory} from "vue-router";
import {authService} from "@/services/authService.ts";
import {currentLocale, HANDOFF_PARAM, hasSavedLocale} from "@/i18n";
import {syncLocaleOnLogin} from "@/services/profileLocale";

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
                // Activates the account and signs the user in (stores the
                // returned tokens), then routes to their profile.
                const {userId} = await authService.verify(uid, token);
                if (userId) {
                    // A brand-new profile has no language yet: record the one
                    // they signed up in. Best effort, never throws.
                    await syncLocaleOnLogin(userId, hasSavedLocale(), currentLocale());
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
        path: "/forms",
        component: () => import("@/pages/FormsView.vue"),
        name: "Forms",
    },
    {
        path: "/resources",
        component: () => import("@/pages/NetworkListView.vue"),
        name: "Resources",
    },
    {
        path: "/representatives",
        component: () => import("@/pages/RepresentativesView.vue"),
        name: "Representatives",
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

// The marketing site hands its locale off as `?lang=` (consumed by @/i18n when
// it loads). Drop it from the URL so a bookmark or shared link doesn't keep
// overriding the visitor's later choice.
router.beforeEach((to) => {
    if (HANDOFF_PARAM in to.query) {
        const query = {...to.query};
        delete query[HANDOFF_PARAM];
        return {...to, query, replace: true};
    }
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
