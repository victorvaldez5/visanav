import {createApp} from 'vue'
import './style.css'
import App from './App.vue'
import {createPinia} from "pinia";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import router from './router.ts';
import {i18n} from "@/i18n";

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
const auth = useAuthStore()
auth.init()
app.mount('#app')
