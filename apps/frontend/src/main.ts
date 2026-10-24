import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import { createAppRouter } from "./router";
import { createAuthRouteAccess, useAuthStore } from "./stores/auth";
import "@fontsource-variable/noto-sans-sc";
import "katex/dist/katex.min.css";
import "./styles.css";

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
app.use(createAppRouter(createAuthRouteAccess(useAuthStore(pinia))));
app.mount("#app");
