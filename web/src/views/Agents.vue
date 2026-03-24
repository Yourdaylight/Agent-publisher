<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <div>
        <h3 style="margin: 0 0 8px 0">Agent 配置管理</h3>
        <p style="margin: 0; color: var(--td-text-color-secondary); font-size: 13px">
          Agent 根据配置自动生成文章到
          <router-link to="/articles" style="color: var(--td-brand-color)">文章管理</router-link>
          页面。也可以点击"立即生成"手动触发。
        </p>
      </div>
      <t-button theme="primary" @click="openDialog()">创建 Agent</t-button>
    </div>

    <!-- Stats Cards -->
    <div style="display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap">
      <t-card :bordered="true" style="flex: 1; min-width: 150px; padding: 16px">
        <div style="text-align: center">
          <div style="font-size: 24px; font-weight: 600; color: var(--td-brand-color)">{{ agents.length }}</div>
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">总 Agent 数</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px; padding: 16px">
        <div style="text-align: center">
          <div style="font-size: 24px; font-weight: 600; color: var(--td-success-color)">{{ activeAgentCount }}</div>
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">活跃中</div>
        </div>
      </t-card>
    </div>

    <t-table :data="agents" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #default_style="{ row }">
        <t-tag v-if="row.default_style_id" theme="primary" variant="light" size="small">
          {{ getStyleName(row.default_style_id) }}
        </t-tag>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #role="{ row }">
        <t-tag :theme="row.role === 'full_pipeline' ? 'primary' : row.role === 'collector' ? 'success' : row.role === 'processor' ? 'warning' : 'default'" variant="light" size="small">
          {{ roleLabelMap[row.role as keyof typeof roleLabelMap] || row.role }}
        </t-tag>
      </template>
      <template #source_mode="{ row }">
        <t-tag :theme="row.source_mode === 'rss' ? 'primary' : row.source_mode === 'skills_feed' ? 'success' : 'warning'" variant="light" size="small">
          {{ sourceModeLabelMap[row.source_mode as keyof typeof sourceModeLabelMap] || row.source_mode }}
        </t-tag>
      </template>
      <template #is_active="{ row }">
        <t-tag :theme="row.is_active ? 'success' : 'default'" variant="light">
          {{ row.is_active ? '启用' : '停用' }}
        </t-tag>
      </template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openDialog(row)">编辑</t-link>
          <t-link
            theme="primary"
            :disabled="generatingIds.has(row.id)"
            @click="onGenerate(row)"
            title="立即触发生成任务。通常 Agent 会根据定时配置(schedule_cron)自动生成。"
          >
            <t-loading v-if="generatingIds.has(row.id)" size="small" style="margin-right: 4px" />
            {{ generatingIds.has(row.id) ? '生成中...' : '⚡ 生成' }}
          </t-link>
          <t-link theme="danger" @click="deleteAgent(row)">删除</t-link>
        </t-space>
      </template>
    </t-table>

    <t-dialog
      v-model:visible="dialogVisible"
      :header="editingAgent ? '编辑 Agent' : '创建 Agent'"
      :footer="false"
      width="700px"
    >
      <AgentForm
        :edit-id="editingAgent?.id"
        :initial-data="editingAgent"
        @success="onFormSuccess"
      />
    </t-dialog>

    <!-- Generation Notification -->
    <t-notification
      v-if="generationNotification"
      theme="success"
      title="文章生成中"
      :content="generationNotification"
      :close-btn="true"
      duration="0"
      @close="generationNotification = null"
    >
      <template #default>
        <div>
          {{ generationNotification }}
          <t-link to="/articles" style="margin-left: 8px" @click="generationNotification = null">
            查看文章 →
          </t-link>
        </div>
      </template>
    </t-notification>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getAgents, generateForAgent, getStylePresets, deleteAgent as deleteAgentAPI } from '@/api';
import AgentForm from '@/components/AgentForm.vue';
import { MessagePlugin } from 'tdesign-vue-next';

const router = useRouter();
const loading = ref(false);
const agents = ref<any[]>([]);
const dialogVisible = ref(false);
const editingAgent = ref<any>(null);
const generatingIds = ref<Set<number>>(new Set());
const stylePresets = ref<any[]>([]);
const generationNotification = ref<string | null>(null);

const roleLabelMap = {
  collector: '采集',
  processor: '加工',
  publisher: '发布',
  full_pipeline: '全流程',
};

const sourceModeLabelMap = {
  rss: 'RSS',
  skills_feed: 'Skills',
  independent_search: '独立采集',
};

const activeAgentCount = computed(() => agents.value.filter(a => a.is_active).length);

const getStyleName = (styleId: string | null): string => {
  if (!styleId) return '-';
  const preset = stylePresets.value.find(s => s.style_id === styleId);
  return preset ? preset.name : styleId;
};

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'name', title: '名称' },
  { colKey: 'topic', title: '主题', width: 120 },
  { colKey: 'role', title: '角色', width: 90 },
  { colKey: 'source_mode', title: '来源', width: 100 },
  { colKey: 'default_style', title: '默认风格', width: 100 },
  { colKey: 'schedule_cron', title: '定时', width: 120 },
  { colKey: 'is_active', title: '状态', width: 80 },
  { colKey: 'op', title: '操作', width: 160 },
]

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getAgents()
    agents.value = res.data
  } catch {
    MessagePlugin.error('加载 Agent 列表失败')
  } finally {
    loading.value = false
  }
}

const openDialog = (agent?: any) => {
  editingAgent.value = agent || null
  dialogVisible.value = true
}

const onFormSuccess = () => {
  dialogVisible.value = false
  MessagePlugin.success('操作成功')
  fetchData()
}

const onGenerate = async (agent: any) => {
  if (generatingIds.value.has(agent.id)) return;

  generatingIds.value.add(agent.id);
  try {
    const res = await generateForAgent(agent.id);
    const taskId = res.data?.task_id;

    generationNotification.value = `Agent "${agent.name}" 的文章正在生成中...`;

    MessagePlugin.success({
      content: `生成任务已创建 (ID: ${taskId})`,
      duration: 3000,
      closeBtn: true,
    });

    console.log(`[Agent Generate] Agent ID: ${agent.id}, Task ID: ${taskId}`);
  } catch (err: any) {
    console.error('[Agent Generate] Error:', err);
    const errorMsg = err?.response?.data?.detail
      || err?.message
      || '生成任务创建失败，请重试';
    MessagePlugin.error(errorMsg);
  } finally {
    generatingIds.value.delete(agent.id);
  }
};

const deleteAgent = async (agent: any) => {
  MessagePlugin.confirm({
    header: `删除 Agent`,
    content: `确定要删除 Agent "${agent.name}" 吗？此操作无法撤销。`,
    onConfirm: async () => {
      try {
        await deleteAgentAPI(agent.id);
        MessagePlugin.success('删除成功');
        fetchData();
      } catch (err: any) {
        MessagePlugin.error(err?.response?.data?.detail || '删除失败');
      }
    },
  });
};

onMounted(async () => {
  try {
    const styleRes = await getStylePresets();
    stylePresets.value = styleRes.data;
  } catch {}
  fetchData();
})
</script>
