import { createRouter, createWebHistory } from 'vue-router';
import { getUserInfo } from '@/api';

const routes = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { title: '登录', public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '仪表盘' } },
  { path: '/guide', name: 'Guide', component: () => import('@/views/Guide.vue'), meta: { title: '快速配置' } },
  { path: '/accounts', name: 'Accounts', component: () => import('@/views/Accounts.vue'), meta: { title: '公众号管理' } },
  { path: '/agents', name: 'Agents', component: () => import('@/views/Agents.vue'), meta: { title: 'Agent 管理' } },
  { path: '/materials', name: 'Materials', component: () => import('@/views/Materials.vue'), meta: { title: '素材库' } },
  { path: '/articles', name: 'Articles', component: () => import('@/views/Articles.vue'), meta: { title: '文章管理' } },
  { path: '/publishes', name: 'Publishes', component: () => import('@/views/Publishes.vue'), meta: { title: '发布管理' } },
  { path: '/tasks', name: 'Tasks', component: () => import('@/views/Tasks.vue'), meta: { title: '任务管理' } },
  { path: '/settings', name: 'Settings', component: () => import('@/views/Settings.vue'), meta: { title: '全局配置', requiresAdmin: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Navigation guard: redirect to login if no token; restrict admin pages
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('ap_token');
  if (to.meta?.public) {
    // Public pages (login) - redirect to dashboard if already logged in
    if (token && to.path === '/login') {
      next('/dashboard');
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
        next('/dashboard');
        return;
      }
    }
    next();
  }
});

export default router;
