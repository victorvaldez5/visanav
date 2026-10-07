import {createApp} from 'vue'
// Self-host the design-system fonts (frontend/src/style.css declares them as
// --font-sans / --font-serif / --font-mono). Self-hosted rather than a
// third-party CDN so no visitor data leaks to a font host — VisaNav serves a
// privacy-sensitive audience. Open Sans is the variable weight-axis build
// (covers 400–700 in one file, upright + italic); Noto Serif and Ubuntu Sans
// Mono ship the weights the UI actually uses.
import '@fontsource-variable/open-sans/wght.css'
import '@fontsource-variable/open-sans/wght-italic.css'
import '@fontsource/noto-serif/400.css'
import '@fontsource/noto-serif/700.css'
import '@fontsource/ubuntu-sans-mono/400.css'
import '@fontsource/ubuntu-sans-mono/700.css'
import './style.css'
import App from './App.vue'
import {createPinia} from "pinia";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import router from './router.ts';
import {i18n, initLocale} from "@/i18n";

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
const auth = useAuthStore()
auth.init()
// Load the initial locale's catalog before the first paint so the app never
// flashes English for a Spanish-speaking visitor. initLocale never rejects.
initLocale().then(() => app.mount('#app'))
