<template>
  <div>
    <div style="display: flex; gap: 12px; margin-bottom: 16px">
      <t-select v-model="filterStatus" placeholder="筛选状态" clearable style="width: 160px" @change="fetchData">
        <t-option label="等待中" value="pending" />
        <t-option label="运行中" value="running" />
        <t-option label="成功" value="success" />
        <t-option label="失败" value="failed" />
      </t-select>
      <t-button theme="primary" @click="onBatchRun">批量执行所有 Agent</t-button>
    </div>

    <t-table
      :data="tasks"
      :columns="columns"
      row-key="id"
      :loading="loading"
      stripe
      @row-click="onRowClick"
      style="cursor: pointer"
    >
      <template #status="{ row }">
        <t-tag :theme="statusTheme(row.status)" variant="light">
          {{ statusLabel(row.status) }}
        </t-tag>
      </template>
      <template #result="{ row }">
        <span v-if="row.result" style="font-size: 12px; color: var(--td-text-color-secondary)">
          {{ JSON.stringify(row.result).slice(0, 80) }}
        </span>
        <span v-else>-</span>
      </template>
    </t-table>

    <!-- Task detail drawer -->
    <t-drawer v-model:visible="drawerVisible" header="任务详情" size="680px" @close="closeDrawer">
      <div v-if="detailTask">
        <div style="margin-bottom: 16px">
          <t-descriptions :column="2" bordered>
            <t-descriptions-item label="任务 ID">{{ detailTask.id }}</t-descriptions-item>
            <t-descriptions-item label="Agent ID">{{ detailTask.agent_id || '-' }}</t-descriptions-item>
            <t-descriptions-item label="类型">{{ detailTask.task_type }}</t-descriptions-item>
            <t-descriptions-item label="状态">
              <t-tag :theme="statusTheme(detailTask.status)" variant="light">
                {{ statusLabel(detailTask.status) }}
              </t-tag>
            </t-descriptions-item>
            <t-descriptions-item label="开始时间">{{ detailTask.started_at ? new Date(detailTask.started_at).toLocaleString() : '-' }}</t-descriptions-item>
            <t-descriptions-item label="结束时间">{{ detailTask.finished_at ? new Date(detailTask.finished_at).toLocaleString() : '-' }}</t-descriptions-item>
          </t-descriptions>
        </div>

        <!-- Steps timeline -->
        <h4 style="margin-bottom: 12px">执行步骤</h4>
        <div v-if="detailSteps.length > 0" class="step-timeline">
          <div v-for="(step, idx) in detailSteps" :key="idx" class="step-item">
            <div class="step-dot" :class="stepDotClass(step.status)" />
            <div class="step-line" v-if="idx < detailSteps.length - 1" />
            <div class="step-content">
              <div style="display: flex; align-items: center; gap: 8px">
                <strong>{{ stepNameMap[step.name] || step.name }}</strong>
                <t-tag size="small" :theme="step.status === 'success' ? 'success' : step.status === 'failed' ? 'danger' : 'warning'" variant="light">
                  {{ step.status === 'success' ? '完成' : step.status === 'failed' ? '失败' : '进行中' }}
                </t-tag>
              </div>
              <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">
                {{ step.started_at ? new Date(step.started_at).toLocaleTimeString() : '' }}
                <span v-if="step.finished_at"> → {{ new Date(step.finished_at).toLocaleTimeString() }}</span>
              </div>
              <!-- Step output summary -->
              <div v-if="step.output" style="font-size: 12px; margin-top: 4px; background: var(--td-bg-color-container); padding: 8px; border-radius: 4px">
                <template v-if="step.name === 'rss_fetch'">
                  抓取到 {{ step.output.count }} 条新闻
                  <div v-if="step.output.titles" style="margin-top: 4px">
                    <div v-for="(title, i) in step.output.titles.slice(0, 5)" :key="i">• {{ title }}</div>
                    <div v-if="step.output.titles.length > 5" style="color: var(--td-text-color-placeholder)">...及其他 {{ step.output.titles.length - 5 }} 条</div>
                  </div>
                </template>
                <template v-else-if="step.name === 'llm_generate'">
                  模型: {{ step.output.provider }}/{{ step.output.model }}，标题: {{ step.output.title }}，内容长度: {{ step.output.content_length }} 字
                </template>
                <template v-else-if="step.name === 'image_generate'">
                  {{ step.output.has_image ? '封面图已生成' : '封面图生成失败' }}
                </template>
                <template v-else-if="step.name === 'save_article'">
                  文章已保存，ID: {{ step.output.article_id }}
                </template>
                <template v-else>
                  {{ JSON.stringify(step.output).slice(0, 200) }}
                </template>
              </div>
            </div>
          </div>
        </div>
        <t-loading v-else-if="detailTask.status === 'running' || detailTask.status === 'pending'" text="等待执行..." />
        <p v-else style="color: var(--td-text-color-secondary)">无步骤记录</p>

        <!-- LLM streaming output -->
        <div v-if="llmStreamText" style="margin-top: 20px">
          <h4 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px">
            AI 生成内容
            <t-loading v-if="isStreaming" size="small" />
          </h4>
          <div class="llm-output" v-text="llmStreamText" />
        </div>

        <!-- Final result -->
        <div v-if="detailTask.result && (detailTask.status === 'success' || detailTask.status === 'failed')" style="margin-top: 20px">
          <h4 style="margin-bottom: 8px">最终结果</h4>
          <t-alert
            :theme="detailTask.status === 'success' ? 'success' : 'error'"
            :message="detailTask.status === 'success' ? '任务执行成功' : '任务执行失败'"
            :description="JSON.stringify(detailTask.result, null, 2)"
          />
        </div>
      </div>
    </t-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { getTasks, batchRun } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const tasks = ref<any[]>([]);
const filterStatus = ref<string | undefined>();
const drawerVisible = ref(false);
const detailTask = ref<any>(null);
const detailSteps = ref<any[]>([]);
const llmStreamText = ref('');
const isStreaming = ref(false);
let eventSource: EventSource | null = null;

const stepNameMap: Record<string, string> = {
  rss_fetch: 'RSS 新闻抓取',
  llm_generate: 'AI 文章生成',
  image_generate: '封面图片生成',
  save_article: '保存文章',
};

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'agent_id', title: 'Agent ID', width: 90 },
  { colKey: 'task_type', title: '类型', width: 100 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'result', title: '结果' },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
];

const statusTheme = (s: string) => {
  if (s === 'success') return 'success';
  if (s === 'failed') return 'danger';
  if (s === 'running') return 'warning';
  return 'default';
};

const statusLabel = (s: string) => {
  const map: Record<string, string> = { pending: '等待中', running: '运行中', success: '成功', failed: '失败' };
  return map[s] || s;
};

const stepDotClass = (status: string) => {
  if (status === 'success') return 'dot-success';
  if (status === 'failed') return 'dot-error';
  return 'dot-running';
};

const fetchData = async () => {
  loading.value = true;
  try {
    const params: any = {};
    if (filterStatus.value) params.status = filterStatus.value;
    const res = await getTasks(params);
    tasks.value = res.data;
  } catch {} finally {
    loading.value = false;
  }
};

const onBatchRun = async () => {
  try {
    await batchRun();
    MessagePlugin.success('批量任务已创建');
    fetchData();
  } catch {
    MessagePlugin.error('触发失败');
  }
};

const onRowClick = ({ row }: any) => {
  openDetail(row);
};

const openDetail = (task: any) => {
  detailTask.value = { ...task };
  detailSteps.value = task.steps || [];
  llmStreamText.value = '';
  isStreaming.value = false;
  drawerVisible.value = true;

  // Connect SSE if task is still active
  if (task.status === 'running' || task.status === 'pending') {
    connectSSE(task.id);
  }
};

const connectSSE = (taskId: number) => {
  closeSSE();
  isStreaming.value = true;
  eventSource = new EventSource(`/api/tasks/${taskId}/stream`);

  eventSource.addEventListener('progress', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data);
      detailTask.value = { ...detailTask.value, ...data };
      detailSteps.value = data.steps || [];
    } catch {}
  });

  eventSource.addEventListener('llm_chunk', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data);
      llmStreamText.value += data.chunk;
    } catch {}
  });

  eventSource.addEventListener('done', (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data);
      detailTask.value = { ...detailTask.value, ...data };
      detailSteps.value = data.steps || [];
    } catch {}
    isStreaming.value = false;
    closeSSE();
    fetchData();
  });

  eventSource.addEventListener('error', () => {
    isStreaming.value = false;
    closeSSE();
  });
};

const closeSSE = () => {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
};

const closeDrawer = () => {
  closeSSE();
  isStreaming.value = false;
};

onMounted(fetchData);

onBeforeUnmount(() => {
  closeSSE();
});
</script>

<style scoped>
.step-timeline {
  position: relative;
  padding-left: 24px;
}

.step-item {
  position: relative;
  padding-bottom: 20px;
}

.step-dot {
  position: absolute;
  left: -24px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  z-index: 1;
}

.dot-success {
  background-color: var(--td-success-color);
}

.dot-error {
  background-color: var(--td-error-color);
}

.dot-running {
  background-color: var(--td-warning-color);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.step-line {
  position: absolute;
  left: -19px;
  top: 18px;
  width: 2px;
  bottom: 0;
  background-color: var(--td-component-border);
}

.step-content {
  padding-left: 4px;
}

.llm-output {
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-component-border);
  border-radius: 8px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
