import {
  createMemoryHistory,
  createRouter,
  createWebHistory,
  type Router
} from "vue-router";

import WorkspaceLayout from "../layouts/WorkspaceLayout.vue";

// 路由级代码分割：各业务视图与认证页按需加载，KaTeX/Markdown 等重组件
// 只进入对话与诊断路由的共享 chunk，不再拖累首屏主包。
const AuthView = () => import("../views/AuthView.vue");
const AiopsView = () => import("../views/AiopsView.vue");
const ChatView = () => import("../views/ChatView.vue");
const KnowledgeView = () => import("../views/KnowledgeView.vue");
const McpView = () => import("../views/McpView.vue");

export interface AuthRouteAccess {
  initialize(): Promise<void>;
  isAuthenticated(): boolean;
}

export function createAppRouter(auth: AuthRouteAccess): Router {
  const router = createRouter({
    history: typeof window === "undefined" ? createMemoryHistory() : createWebHistory(),
    routes: [
      { path: "/", redirect: "/chat" },
      {
        path: "/login",
        name: "login",
        component: AuthView,
        props: { mode: "login" },
        meta: { publicOnly: true }
      },
      {
        path: "/register",
        name: "register",
        component: AuthView,
        props: { mode: "register" },
        meta: { publicOnly: true }
      },
      {
        path: "/",
        component: WorkspaceLayout,
        meta: { requiresAuth: true },
        children: [
          {
            path: "chat",
            name: "chat",
            component: ChatView,
            meta: { title: "对话" }
          },
          {
            path: "knowledge",
            name: "knowledge",
            component: KnowledgeView,
            meta: { title: "知识库" }
          },
          {
            path: "aiops",
            name: "aiops",
            component: AiopsView,
            meta: { title: "智能诊断" }
          },
          {
            path: "mcp",
            name: "mcp",
            component: McpView,
            meta: { title: "MCP 连接" }
          }
        ]
      },
      { path: "/:pathMatch(.*)*", redirect: "/chat" }
    ]
  });

  let initialization: Promise<void> | null = null;
  router.beforeEach(async (to) => {
    initialization ??= auth.initialize();
    await initialization;
    const requiresAuth = to.matched.some((record) => record.meta.requiresAuth === true);
    const publicOnly = to.matched.some((record) => record.meta.publicOnly === true);
    if (requiresAuth && !auth.isAuthenticated()) {
      return { path: "/login", query: { redirect: to.fullPath } };
    }
    if (publicOnly && auth.isAuthenticated()) {
      return { path: "/chat" };
    }
    return true;
  });

  return router;
}
