<template>
  <div>
    <!-- Running tasks section -->
    <div v-if="runningTasks.length > 0" style="margin-bottom: 20px">
      <h3 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px">
        <t-loading size="small" />
        生成中的任务（{{ runningTasks.length }}）
      </h3>
      <div style="display: flex; gap: 12px; flex-wrap: wrap">
        <t-card v-for="task in runningTasks" :key="task.id" style="width: 320px" :bordered="true" hover-shadow>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>任务 #{{ task.id }}</span>
              <t-tag theme="warning" variant="light">
                {{ task.status === 'pending' ? '等待中' : '生成中' }}
              </t-tag>
            </div>
          </template>
          <div style="font-size: 13px; color: var(--td-text-color-secondary)">
            <p>Agent ID: {{ task.agent_id }}</p>
            <p v-if="task.steps && task.steps.length > 0">
              当前步骤: {{ stepNameMap[task.steps[task.steps.length - 1].name] || task.steps[task.steps.length - 1].name }}
            </p>
            <p v-else>准备中...</p>
            <t-progress
              :percentage="getTaskProgress(task)"
              :status="task.status === 'running' ? 'active' : 'warning'"
              style="margin-top: 8px"
            />
          </div>
        </t-card>
      </div>
    </div>

    <div style="display: flex; gap: 12px; margin-bottom: 16px">
      <t-select v-model="filterAgentId" placeholder="筛选 Agent" clearable style="width: 200px" @change="fetchData">
        <t-option v-for="a in agentOptions" :key="a.id" :label="a.name" :value="a.id" />
      </t-select>
      <t-select v-model="filterStatus" placeholder="筛选状态" clearable style="width: 160px" @change="fetchData">
        <t-option label="草稿" value="draft" />
        <t-option label="已发布" value="published" />
      </t-select>
    </div>

    <t-table :data="articles" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #status="{ row }">
        <t-tag :theme="row.status === 'published' ? 'success' : 'default'" variant="light">
          {{ row.status === 'published' ? '已发布' : '草稿' }}
        </t-tag>
      </template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openPreview(row)">预览</t-link>
          <t-link v-if="row.status !== 'published'" theme="primary" @click="onPublish(row)">发布</t-link>
        </t-space>
      </template>
    </t-table>

    <t-drawer v-model:visible="drawerVisible" header="文章预览" size="640px">
      <div v-if="previewArticle">
        <h2>{{ previewArticle.title }}</h2>
        <p style="color: var(--td-text-color-secondary)">{{ previewArticle.digest }}</p>
        <img v-if="previewArticle.cover_image_url" :src="previewArticle.cover_image_url" style="max-width: 100%; border-radius: 8px; margin: 12px 0" />
        <t-divider />
        <div v-html="previewArticle.html_content" style="line-height: 1.8" />
      </div>
    </t-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { getArticles, getArticle, getAgents, publishArticle, getRunningTasks, getPendingTasks } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const articles = ref<any[]>([]);
const agentOptions = ref<any[]>([]);
const filterAgentId = ref<number | undefined>();
const filterStatus = ref<string | undefined>();
const drawerVisible = ref(false);
const previewArticle = ref<any>(null);
const runningTasks = ref<any[]>([]);
let pollTimer: ReturnType<typeof setInterval> | null = null;

const stepNameMap: Record<string, string> = {
  rss_fetch: 'RSS 抓取',
  llm_generate: 'AI 生成文章',
  image_generate: '生成封面图',
  save_article: '保存文章',
};

const getTaskProgress = (task: any): number => {
  const steps = task.steps || [];
  const totalSteps = 4;
  return Math.round((steps.length / totalSteps) * 100);
};

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'agent_id', title: 'Agent ID', width: 90 },
  { colKey: 'status', title: '状态', width: 80 },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
  { colKey: 'op', title: '操作', width: 140 },
]

const fetchData = async () => {
  loading.value = true
  try {
    const params: any = {}
    if (filterAgentId.value) params.agent_id = filterAgentId.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await getArticles(params)
    articles.value = res.data
  } catch {} finally {
    loading.value = false
  }
}

const openPreview = async (row: any) => {
  try {
    const res = await getArticle(row.id)
    previewArticle.value = res.data
    drawerVisible.value = true
  } catch {}
}

const onPublish = async (row: any) => {
  try {
    await publishArticle(row.id)
    MessagePlugin.success('发布成功')
    fetchData()
  } catch {
    MessagePlugin.error('发布失败')
  }
}

const fetchRunningTasks = async () => {
  try {
    const [runningRes, pendingRes] = await Promise.all([
      getRunningTasks(),
      getPendingTasks(),
    ]);
    const allActive = [...(pendingRes.data || []), ...(runningRes.data || [])];
    const hadTasks = runningTasks.value.length > 0;
    runningTasks.value = allActive;

    // If tasks just finished, refresh article list
    if (hadTasks && allActive.length === 0) {
      fetchData();
    }

    // Manage polling
    if (allActive.length > 0 && !pollTimer) {
      pollTimer = setInterval(fetchRunningTasks, 5000);
    } else if (allActive.length === 0 && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  } catch {
    // ignore
  }
};

onMounted(async () => {
  try {
    const res = await getAgents();
    agentOptions.value = res.data;
  } catch {}
  fetchData();
  fetchRunningTasks();
});

onBeforeUnmount(() => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
});
</script>
