<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
      <h3 style="margin: 0">Agent 列表</h3>
      <t-button theme="primary" @click="openDialog()">创建 Agent</t-button>
    </div>

    <t-table :data="agents" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #is_active="{ row }">
        <t-tag :theme="row.is_active ? 'success' : 'default'" variant="light">
          {{ row.is_active ? '启用' : '停用' }}
        </t-tag>
      </template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openDialog(row)">编辑</t-link>
          <t-link theme="primary" :disabled="generatingIds.has(row.id)" @click="onGenerate(row)">
            <t-loading v-if="generatingIds.has(row.id)" size="small" style="margin-right: 4px" />
            {{ generatingIds.has(row.id) ? '生成中...' : '生成' }}
          </t-link>
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getAgents, generateForAgent } from '@/api';
import AgentForm from '@/components/AgentForm.vue';
import { MessagePlugin } from 'tdesign-vue-next';

const router = useRouter();
const loading = ref(false);
const agents = ref<any[]>([]);
const dialogVisible = ref(false);
const editingAgent = ref<any>(null);
const generatingIds = ref<Set<number>>(new Set());

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'name', title: '名称' },
  { colKey: 'topic', title: '主题', width: 120 },
  { colKey: 'llm_model', title: '模型', width: 200 },
  { colKey: 'schedule_cron', title: '定时', width: 120 },
  { colKey: 'is_active', title: '状态', width: 80 },
  { colKey: 'op', title: '操作', width: 140 },
]

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getAgents()
    agents.value = res.data
  } catch {} finally {
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
    const taskId = res.data.task_id;
    MessagePlugin.success({
      content: `任务已创建（ID: ${taskId}）`,
      duration: 5000,
      closeBtn: true,
    });
    // Provide a way to navigate to tasks page
    const goToTasks = await MessagePlugin.info({
      content: '点击此消息查看任务详情',
      duration: 4000,
      closeBtn: true,
    });
    // Navigate after a short delay to let user see the message
    setTimeout(() => {
      router.push('/tasks');
    }, 1500);
  } catch {
    MessagePlugin.error('触发失败');
  } finally {
    generatingIds.value.delete(agent.id);
  }
};

onMounted(fetchData)
</script>
