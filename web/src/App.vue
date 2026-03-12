<template>
  <!-- Login page: no layout chrome -->
  <router-view v-if="isLoginPage" />

  <!-- Main layout with sidebar -->
  <t-layout v-else>
    <t-aside style="width: 220px; border-right: 1px solid var(--td-component-stroke); display: flex; flex-direction: column">
      <div style="padding: 20px 16px; font-size: 18px; font-weight: 600; color: var(--td-brand-color)">
        Agent Publisher
      </div>
      <t-menu :value="activeMenu" @change="onMenuChange" theme="light" style="flex: 1">
        <t-menu-item value="/dashboard">
          <template #icon><t-icon name="dashboard" /></template>
          仪表盘
        </t-menu-item>
        <t-menu-item value="/guide">
          <template #icon><t-icon name="rocket" /></template>
          快速配置
        </t-menu-item>
        <t-menu-item value="/accounts">
          <template #icon><t-icon name="user-circle" /></template>
          公众号管理
        </t-menu-item>
        <t-menu-item value="/agents">
          <template #icon><t-icon name="robot" /></template>
          Agent 管理
        </t-menu-item>
        <t-menu-item value="/materials">
          <template #icon><t-icon name="folder-open" /></template>
          素材库
        </t-menu-item>
        <t-menu-item value="/articles">
          <template #icon><t-icon name="file" /></template>
          文章管理
        </t-menu-item>
        <t-menu-item value="/publishes">
          <template #icon><t-icon name="send" /></template>
          发布管理
        </t-menu-item>
        <t-menu-item value="/tasks">
          <template #icon><t-icon name="task" /></template>
          任务管理
        </t-menu-item>
        <t-menu-item value="/settings">
          <template #icon><t-icon name="setting" /></template>
          全局配置
        </t-menu-item>
      </t-menu>
      <div style="padding: 12px 16px; border-top: 1px solid var(--td-component-stroke)">
        <t-button theme="default" variant="text" block @click="onLogout">
          <template #icon><t-icon name="poweroff" /></template>
          退出登录
        </t-button>
      </div>
    </t-aside>
    <t-layout>
      <t-header style="padding: 12px 24px; border-bottom: 1px solid var(--td-component-stroke); display: flex; align-items: center">
        <h3 style="margin: 0">{{ currentTitle }}</h3>
      </t-header>
      <t-content style="padding: 24px; background: var(--td-bg-color-page); min-height: calc(100vh - 56px); overflow-y: auto">
        <router-view />
      </t-content>
    </t-layout>
  </t-layout>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';

const router = useRouter();
const route = useRoute();

const isLoginPage = computed(() => route.path === '/login');
const activeMenu = computed(() => route.path);
const currentTitle = computed(() => (route.meta?.title as string) || 'Agent Publisher');

const onMenuChange = (value: string) => {
  router.push(value);
};

const onLogout = () => {
  localStorage.removeItem('ap_token');
  MessagePlugin.success('已退出登录');
  router.replace('/login');
};
</script>

<style>
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
