<template>
  <!-- Login page: no layout chrome -->
  <router-view v-if="isLoginPage" />

  <!-- Main layout with sidebar -->
  <t-layout v-else>
    <t-aside class="app-sidebar">
      <!-- Logo -->
      <div class="sidebar-logo">
        <div class="logo-text">Agent Publisher</div>
        <div class="logo-sub">AI 内容经营工作台</div>
      </div>

      <!-- CTA -->
      <div class="sidebar-cta">
        <t-button theme="primary" size="large" block @click="router.push('/create')">
          <template #icon><t-icon name="add" /></template>
          开始创作
        </t-button>
      </div>

      <!-- Navigation -->
      <t-menu
        :value="activeMenu"
        :expanded="expandedGroups"
        expand-type="normal"
        @expand="onMenuExpand"
        @change="onMenuChange"
        theme="light"
        class="sidebar-menu"
      >
        <!-- ═══ 核心路径（所有用户可见） ═══ -->
        <t-menu-item value="/trending">
          <template #icon><t-icon name="trending-up" /></template>
          发现热点
        </t-menu-item>
        <t-menu-item value="/create">
          <template #icon><t-icon name="edit-1" /></template>
          AI 创作
        </t-menu-item>
        <t-menu-item value="/articles">
          <template #icon><t-icon name="file-paste" /></template>
          内容管理
        </t-menu-item>
        <t-menu-item value="/publishes">
          <template #icon><t-icon name="send" /></template>
          发布记录
        </t-menu-item>
        <t-menu-item value="/materials">
          <template #icon><t-icon name="image" /></template>
          素材库
        </t-menu-item>

        <!-- ═══ 我的（所有用户可见） ═══ -->
        <div class="menu-divider" />
        <t-submenu value="mine" title="我的">
          <template #icon><t-icon name="user-circle" /></template>
          <t-menu-item value="/accounts">公众号</t-menu-item>
          <t-menu-item value="/agents">写作身份</t-menu-item>
          <t-menu-item value="/membership">Credits / 会员</t-menu-item>
        </t-submenu>

        <!-- ═══ 管理（仅管理员可见） ═══ -->
        <template v-if="isAdmin">
          <div class="menu-divider" />
          <t-submenu value="admin" title="管理">
            <template #icon><t-icon name="setting" /></template>
            <t-menu-item value="/sources">数据源</t-menu-item>
            <t-menu-item value="/prompts">提示词库</t-menu-item>
            <t-menu-item value="/llm-profiles">LLM 配置</t-menu-item>
            <t-menu-item value="/tasks">任务</t-menu-item>
            <t-menu-item value="/settings">全局配置</t-menu-item>
            <t-menu-item value="/groups">权限组</t-menu-item>
            <t-menu-item value="/invite-codes">邀请码</t-menu-item>
          </t-submenu>
        </template>
      </t-menu>

      <!-- Bottom -->
      <div class="sidebar-bottom">
        <t-button theme="default" variant="text" size="small" block @click="router.push('/guide')">
          <template #icon><t-icon name="rocket" /></template>
          快速配置向导
        </t-button>
        <div class="user-info" v-if="userEmail" :title="userEmail">
          <t-icon name="user" size="14px" />
          <span class="user-email">{{ displayEmail }}</span>
          <t-tag v-if="isAdmin" size="small" theme="primary" variant="light">管理员</t-tag>
        </div>
        <t-button theme="default" variant="text" size="small" block @click="onLogout">
          <template #icon><t-icon name="poweroff" /></template>
          退出登录
        </t-button>
        <div v-if="versionDisplay" class="version-text">{{ versionDisplay }}</div>
      </div>
    </t-aside>

    <t-layout>
      <!-- Header（Create 页面自带 topbar，不需要全局 header） -->
      <t-header v-if="!isCreatePage" class="app-header">
        <h3 class="header-title">{{ currentTitle }}</h3>
        <div class="header-right">
          <t-popup trigger="click" placement="bottom-right" :overlay-style="{ padding: 0 }">
            <t-button variant="text" size="small" :class="creditsClass" style="font-weight: 700; font-size: 13px">
              💎 {{ creditsAvailable ?? '—' }}
            </t-button>
            <template #content>
              <div class="credits-popup">
                <div class="credits-popup-title">Credits 余额</div>
                <div class="credits-popup-body">
                  <div>免费额度：{{ creditsData?.free_credits ?? 0 }}</div>
                  <div>付费额度：{{ creditsData?.paid_credits ?? 0 }}</div>
                  <div>已使用：{{ creditsData?.used_credits ?? 0 }}</div>
                  <div class="credits-popup-divider">本月消耗：{{ creditsData?.monthly_stats?.total_consumed ?? 0 }} Credits</div>
                </div>
                <t-button theme="primary" size="small" block style="margin-top: 10px" @click="router.push('/membership')">购买 Credits</t-button>
              </div>
            </template>
          </t-popup>
          <span v-if="userEmail" class="header-email">{{ displayEmail }}</span>
          <t-tag v-if="isAdmin" size="small" theme="primary" variant="light">管理员</t-tag>
        </div>
      </t-header>

      <!-- Content -->
      <t-content class="app-content" :class="{ 'content-create': isCreatePage }">
        <router-view />
      </t-content>
    </t-layout>
  </t-layout>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { getUserInfo, clearAuth, getVersion, getCreditsBalance } from '@/api';

const router = useRouter();
const route = useRoute();

const versionDisplay = ref('');
const creditsData = ref<any>(null);
const creditsAvailable = computed(() => creditsData.value?.available ?? null);
const creditsClass = computed(() => {
  const v = creditsAvailable.value;
  if (v === null) return '';
  if (v <= 0) return 'credits-empty';
  if (v <= 10) return 'credits-low';
  return 'credits-normal';
});

const fetchCredits = async () => {
  try {
    const res = await getCreditsBalance();
    creditsData.value = res.data;
  } catch { /* ignore */ }
};

onMounted(async () => {
  try {
    const res = await getVersion();
    versionDisplay.value = res.data?.display || '';
  } catch { /* ignore */ }
  if (!isLoginPage.value) fetchCredits();
});

const isLoginPage = computed(() => route.path === '/login');
const isCreatePage = computed(() => route.path === '/create');
const expandedStorageKey = 'ap_menu_expanded_v2';

const menuGroupByPath: Array<[string, string]> = [
  ['/trending', ''],
  ['/create', ''],
  ['/articles', ''],
  ['/publishes', ''],
  ['/materials', ''],
  ['/accounts', 'mine'],
  ['/agents', 'mine'],
  ['/membership', 'mine'],
  ['/sources', 'admin'],
  ['/prompts', 'admin'],
  ['/llm-profiles', 'admin'],
  ['/tasks', 'admin'],
  ['/settings', 'admin'],
  ['/groups', 'admin'],
];

const getMenuGroup = (path: string) => menuGroupByPath.find(([prefix]) => path.startsWith(prefix))?.[1];
const getActiveMenuValue = (path: string) => {
  if (['/dashboard', '/create', '/workbench'].includes(path)) return '/create';
  if (path.startsWith('/articles/')) return '/articles';
  if (path === '/hotspots') return '/trending';
  return path;
};
const readExpandedGroups = () => {
  try {
    const raw = localStorage.getItem(expandedStorageKey);
    const parsed = raw ? JSON.parse(raw) : null;
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : [];
  } catch {
    return [];
  }
};

const activeMenu = computed(() => getActiveMenuValue(route.path));
const currentTitle = computed(() => (route.meta?.title as string) || 'Agent Publisher');
const expandedGroups = ref<string[]>(readExpandedGroups());

const userInfo = ref(getUserInfo());
watch(() => route.fullPath, () => {
  userInfo.value = getUserInfo();
  const group = getMenuGroup(route.path);
  if (group && !expandedGroups.value.includes(group)) {
    expandedGroups.value = [...expandedGroups.value, group];
    localStorage.setItem(expandedStorageKey, JSON.stringify(expandedGroups.value));
  }
}, { immediate: true });

const userEmail = computed(() => userInfo.value?.email || '');
const isAdmin = computed(() => userInfo.value?.is_admin ?? false);
const displayEmail = computed(() => {
  const email = userEmail.value;
  if (email === '__admin__') return '管理员';
  return email;
});

const onMenuChange = (value: string) => router.push(value);
const onMenuExpand = (value: string[]) => {
  expandedGroups.value = value;
  localStorage.setItem(expandedStorageKey, JSON.stringify(value));
};

const onLogout = () => {
  clearAuth();
  userInfo.value = null;
  MessagePlugin.success('已退出登录');
  router.replace('/login');
};
</script>

<style>
html, body, #app {
  margin: 0; padding: 0; height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ── Sidebar ── */
.app-sidebar {
  width: 216px; border-right: 1px solid var(--td-component-stroke);
  background: linear-gradient(180deg, #fff 0%, #f8f9fc 100%);
  display: flex; flex-direction: column;
  flex-shrink: 0; overflow: hidden;
}
.sidebar-logo { padding: 20px 18px 6px; }
.logo-text { font-size: 16px; font-weight: 800; color: var(--td-brand-color); letter-spacing: -0.3px; }
.logo-sub { font-size: 11px; color: var(--td-text-color-placeholder); margin-top: 3px; }
.sidebar-cta { padding: 6px 14px 14px; }
.sidebar-menu { flex: 1; overflow-y: auto; }
.menu-divider { height: 1px; background: var(--td-component-stroke); margin: 6px 16px; }

/* ── Sidebar Bottom ── */
.sidebar-bottom {
  padding: 10px 14px; border-top: 1px solid var(--td-component-stroke);
  display: flex; flex-direction: column; gap: 4px;
}
.user-info {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px; font-size: 11px; color: var(--td-text-color-secondary);
  overflow: hidden;
}
.user-email { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.version-text { font-size: 10px; color: var(--td-text-color-placeholder); text-align: center; padding-top: 2px; }

/* ── Header ── */
.app-header {
  padding: 10px 24px; border-bottom: 1px solid var(--td-component-stroke);
  display: flex; align-items: center; justify-content: space-between;
}
.header-title { margin: 0; font-size: 15px; font-weight: 700; }
.header-right { display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--td-text-color-secondary); }
.header-email { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Content ── */
.app-content { padding: 16px; background: var(--td-bg-color-page); min-height: calc(100vh - 52px); overflow-y: auto; }

/* Create 页面：无 header，全高，无 padding */
.app-content.content-create {
  padding: 0; height: 100vh; min-height: unset; overflow: hidden;
}

/* ── Credits ── */
.credits-normal { color: var(--td-brand-color) !important; }
.credits-low { color: var(--td-warning-color) !important; animation: credits-pulse 2s infinite; }
.credits-empty { color: var(--td-error-color) !important; }
@keyframes credits-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
.credits-popup { padding: 16px; min-width: 220px; }
.credits-popup-title { font-size: 14px; font-weight: 700; margin-bottom: 10px; }
.credits-popup-body { font-size: 12px; color: var(--td-text-color-secondary); line-height: 1.9; }
.credits-popup-divider { margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--td-component-stroke); }
</style>
