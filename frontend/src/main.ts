import {createApp} from 'vue'
import './style.css'
import App from './App.vue'
import {createPinia} from "pinia";
import {useAuthStore} from "@/stores/useAuthStore.ts";
import router from './router.ts';

const app = createApp(App)
app.use(createPinia())
app.use(router)
const auth = useAuthStore()
auth.init()
app.mount('#app')
