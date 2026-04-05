import { createRouter, createWebHistory } from 'vue-router';
import { getUserInfo } from '@/api';

const routes = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { title: '登录', public: true } },
  { path: '/', redirect: '/create' },
  { path: '/trending', name: 'Trending', component: () => import('@/views/Trending.vue'), meta: { title: '每日热榜' } },
  { path: '/create', name: 'Create', component: () => import('@/views/Create.vue'), meta: { title: 'AI 创作控制台' } },
  { path: '/dashboard', redirect: '/create' },
  { path: '/guide', name: 'Guide', component: () => import('@/views/Guide.vue'), meta: { title: '快速配置' } },
  { path: '/hotspots', name: 'Hotspots', component: () => import('@/views/Hotspots.vue'), meta: { title: '热点发现' } },
  { path: '/workbench', name: 'Workbench', component: () => import('@/views/Workbench.vue'), meta: { title: '创作工作台' } },
  { path: '/accounts', name: 'Accounts', component: () => import('@/views/Accounts.vue'), meta: { title: '公众号管理' } },
  { path: '/agents', name: 'Agents', component: () => import('@/views/Agents.vue'), meta: { title: 'Agent 管理' } },
  { path: '/llm-profiles', name: 'LLMProfiles', component: () => import('@/views/LLMProfiles.vue'), meta: { title: 'LLM 配置' } },
  { path: '/sources', name: 'Sources', component: () => import('@/views/Sources.vue'), meta: { title: '数据源管理' } },
  { path: '/materials', name: 'Materials', component: () => import('@/views/Materials.vue'), meta: { title: '素材库' } },
  { path: '/prompts', name: 'Prompts', component: () => import('@/views/Prompts.vue'), meta: { title: '提示词库' } },
  { path: '/articles', name: 'Articles', component: () => import('@/views/Articles.vue'), meta: { title: '文章管理' } },
  { path: '/articles/:id/edit', redirect: (to: any) => ({ path: '/create', query: { article_id: to.params.id } }) },
  { path: '/membership', name: 'Membership', component: () => import('@/views/Membership.vue'), meta: { title: '会员中心' } },
  { path: '/publishes', name: 'Publishes', component: () => import('@/views/Publishes.vue'), meta: { title: '发布管理' } },
  { path: '/tasks', name: 'Tasks', component: () => import('@/views/Tasks.vue'), meta: { title: '任务管理' } },
  { path: '/settings', name: 'Settings', component: () => import('@/views/Settings.vue'), meta: { title: '全局配置', requiresAdmin: true } },
  { path: '/groups', name: 'Groups', component: () => import('@/views/Groups.vue'), meta: { title: '权限组管理', requiresAdmin: true } },
  { path: '/invite-codes', name: 'InviteCodes', component: () => import('@/views/InviteCodes.vue'), meta: { title: '邀请码管理', requiresAdmin: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Navigation guard: redirect to login if no token; restrict admin pages
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('ap_token');
  if (to.meta?.public) {
    // Public pages (login) - redirect to create page if already logged in
    if (token && to.path === '/login') {
      next('/create');
    } else {
      next();
    }
  } else if (!token) {
    next('/login');
  } else {
    // Check admin-only routes
    if (to.meta?.requiresAdmin) {
      const userInfo = getUserInfo();
      if (!userInfo?.is_admin) {
        next('/home');
        return;
      }
    }
    next();
  }
});

export default router;
