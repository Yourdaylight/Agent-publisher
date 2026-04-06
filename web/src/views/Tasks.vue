<template>
  <div>
    <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center">
      <t-select v-model="filterStatus" placeholder="筛选状态" clearable style="width: 160px" @change="fetchData">
        <t-option label="等待中" value="pending" />
        <t-option label="运行中" value="running" />
        <t-option label="成功" value="success" />
        <t-option label="失败" value="failed" />
      </t-select>
      <t-select v-model="filterType" placeholder="筛选类型" clearable style="width: 180px" @change="fetchData">
        <t-option label="文章生成" value="generate" />
        <t-option label="演示文稿" value="slideshow_generate" />
        <t-option label="短视频" value="video_generate" />
        <t-option label="批量执行" value="batch_all" />
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
      <template #task_type="{ row }">
        <t-tag
          size="small"
          :theme="row.task_type === 'slideshow_generate' ? 'primary' : 'default'"
          variant="light"
        >
          {{ typeLabel(row.task_type) }}
        </t-tag>
      </template>
      <template #status="{ row }">
        <t-tag :theme="statusTheme(row.status)" variant="light">
          {{ statusLabel(row.status) }}
        </t-tag>
      </template>
      <template #result_summary="{ row }">
        <!-- Slideshow task: show quick action buttons directly in list -->
        <div v-if="row.task_type === 'slideshow_generate' && row.status === 'success'" style="display: flex; gap: 8px" @click.stop>
          <t-button size="small" theme="primary" @click="openSlideshowPreviewById(row)">
            🎬 在线预览
          </t-button>
        </div>
        <!-- Video task: show download button in list -->
        <div v-else-if="row.task_type === 'video_generate' && row.status === 'success'" style="display: flex; gap: 8px" @click.stop>
          <t-button size="small" theme="success" @click="downloadVideoById(row)">
            🎥 下载 MP4
          </t-button>
        </div>
        <span v-else-if="row.result" style="font-size: 12px; color: var(--td-text-color-secondary)">
          {{ resultSummary(row) }}
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
            <t-descriptions-item label="类型">
              <t-tag size="small" :theme="detailTask.task_type === 'slideshow_generate' ? 'primary' : 'default'" variant="light">
                {{ typeLabel(detailTask.task_type) }}
              </t-tag>
            </t-descriptions-item>
            <t-descriptions-item label="状态">
              <t-tag :theme="statusTheme(detailTask.status)" variant="light">
                {{ statusLabel(detailTask.status) }}
              </t-tag>
            </t-descriptions-item>
            <t-descriptions-item label="开始时间">{{ detailTask.started_at ? new Date(detailTask.started_at).toLocaleString() : '-' }}</t-descriptions-item>
            <t-descriptions-item label="结束时间">{{ detailTask.finished_at ? new Date(detailTask.finished_at).toLocaleString() : '-' }}</t-descriptions-item>
          </t-descriptions>
        </div>

        <!-- Slideshow quick actions (most prominent) -->
        <div v-if="detailTask.task_type === 'slideshow_generate' && detailTask.status === 'success'" style="margin-bottom: 20px">
          <div style="font-weight: 600; margin-bottom: 12px">🎬 演示文稿已生成</div>
          <div style="display: flex; gap: 12px; flex-wrap: wrap">
            <t-button theme="primary" @click="openSlideshowPreviewById(detailTask)">
              在线预览演示文稿
            </t-button>
          </div>
        </div>

        <!-- Video quick actions -->
        <div v-if="detailTask.task_type === 'video_generate' && detailTask.status === 'success'" style="margin-bottom: 20px">
          <div style="font-weight: 600; margin-bottom: 12px">🎥 短视频已生成</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 12px">
            {{ detailTask.result?.scene_count }} 个场景 · 约 {{ detailTask.result?.total_duration_s }} 秒 · {{ (detailTask.result?.mp4_path || '').split('/').pop() }}
          </div>
          <div style="display: flex; gap: 12px; flex-wrap: wrap">
            <t-button theme="success" @click="downloadVideoById(detailTask)">
              下载 MP4
            </t-button>
          </div>
        </div>

        <!-- Steps timeline -->
        <h4 style="margin-bottom: 12px">执行步骤</h4>
        <div v-if="detailSteps.length > 0" class="step-timeline">
          <div v-for="(step, idx) in detailSteps" :key="idx" class="step-item">
            <div class="step-dot" :class="stepDotClass(step.status)" />
            <div class="step-line" v-if="idx < detailSteps.length - 1" />
            <div class="step-content">
              <div style="display: flex; align-items: center; gap: 8px">
                <strong>{{ formatStepName(step.name) }}</strong>
                <t-tag size="small" :theme="step.status === 'success' ? 'success' : step.status === 'failed' ? 'danger' : 'warning'" variant="light">
                  {{ step.status === 'success' ? '完成' : step.status === 'failed' ? '失败' : '进行中' }}
                </t-tag>
              </div>
              <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">
                {{ step.finished_at ? new Date(step.finished_at).toLocaleTimeString() : '' }}
              </div>
              <div v-if="step.output && Object.keys(step.output).length" style="font-size: 12px; margin-top: 4px; background: var(--td-bg-color-container); padding: 8px; border-radius: 4px">
                <template v-if="step.name === 'rss_fetch'">抓取到 {{ step.output.count }} 条新闻</template>
                <template v-else-if="step.name === 'llm_generate'">模型: {{ step.output.provider }}/{{ step.output.model }}，标题: {{ step.output.title }}</template>
                <template v-else-if="step.name === 'image_generate'">{{ step.output.has_image ? '封面图已生成' : '封面图生成失败' }}</template>
                <template v-else-if="step.name === 'save_article'">文章已保存，ID: {{ step.output.article_id }}</template>
                <template v-else-if="step.name === 'llm_outline'">生成了 {{ step.output.slide_count }} 张幻灯片大纲</template>
                <template v-else-if="step.name === 'orchestrator'">拆分为 {{ step.output.chapter_count }} 个章节，共 {{ step.output.total_slides }} 张幻灯片</template>
                <template v-else-if="step.name && step.name.startsWith('chapter_')">生成了 {{ step.output.slide_count }} 张幻灯片</template>
                <template v-else-if="step.name === 'assembly'">组装了 {{ step.output.chapter_count }} 个章节的 HTML 演示文稿</template>
                <template v-else-if="step.name === 'tts_generate'">语音时长: {{ Math.round((step.output.duration_ms || 0) / 1000) }} 秒</template>
                <template v-else-if="step.name === 'build_html'">演示文稿 HTML 构建完成</template>
                <template v-else>{{ JSON.stringify(step.output).slice(0, 200) }}</template>
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

        <!-- Final result — only for non-slideshow/video or failed -->
        <div v-if="detailTask.result && !['slideshow_generate', 'video_generate'].includes(detailTask.task_type) && (detailTask.status === 'success' || detailTask.status === 'failed')" style="margin-top: 20px">
          <h4 style="margin-bottom: 8px">最终结果</h4>
          <t-alert
            :theme="detailTask.status === 'success' ? 'success' : 'error'"
            :message="detailTask.status === 'success' ? '任务执行成功' : '任务执行失败'"
            :description="JSON.stringify(detailTask.result, null, 2)"
          />
        </div>
        <div v-else-if="detailTask.result?.error && detailTask.task_type === 'slideshow_generate'" style="margin-top: 20px">
          <t-alert theme="error" :message="'生成失败'" :description="detailTask.result.error" />
        </div>
        <div v-else-if="detailTask.result?.error && detailTask.task_type === 'video_generate'" style="margin-top: 20px">
          <t-alert theme="error" :message="'视频生成失败'" :description="detailTask.result.error" />
        </div>
      </div>
    </t-drawer>

    <!-- Slideshow preview iframe drawer -->
    <t-drawer
      v-model:visible="slideshowPreviewVisible"
      header="演示文稿预览"
      size="85%"
      placement="right"
      :footer="false"
    >
      <div style="height: calc(100vh - 80px); position: relative">
        <t-loading v-if="previewLoading" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center" />
        <div v-if="previewError" style="padding: 60px; text-align: center">
          <t-result theme="error" title="预览加载失败" :description="previewError" />
        </div>
        <iframe
          v-else
          :src="previewUrl"
          style="width: 100%; height: 100%; border: none; border-radius: 8px"
          @load="previewLoading = false"
          @error="previewError = '演示文稿加载失败'; previewLoading = false"
        />
      </div>
    </t-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { getTasks, batchRun, getSlideshowPreviewUrl, getVideoDownloadUrl } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const tasks = ref<any[]>([]);
const filterStatus = ref<string | undefined>();
const filterType = ref<string | undefined>();
const drawerVisible = ref(false);
const detailTask = ref<any>(null);
const detailSteps = ref<any[]>([]);
const llmStreamText = ref('');
const isStreaming = ref(false);
let eventSource: EventSource | null = null;

// Slideshow preview state
const slideshowPreviewVisible = ref(false);
const previewUrl = ref('');
const previewLoading = ref(false);
const previewError = ref('');
const previewTask = ref<any>(null);

const stepNameMap: Record<string, string> = {
  rss_fetch: 'RSS 新闻抓取',
  llm_generate: 'AI 文章生成',
  image_generate: '封面图片生成',
  save_article: '保存文章',
  llm_outline: 'AI 生成幻灯片大纲',
  orchestrator: '拆分章节大纲',
  assembly: '组装演示文稿',
  tts_generate: 'edge-tts 配音合成',
  build_html: '构建演示文稿',
  script_generation: 'AI 脚本生成',
  props_ready: '脚本写入完成',
  remotion_render: 'Remotion 渲染 MP4',
};

function formatStepName(name: string): string {
  if (stepNameMap[name]) return stepNameMap[name];
  if (name && name.startsWith('chapter_')) {
    const chId = name.replace('chapter_', '').toUpperCase().replace('_', ' ');
    return `生成章节 ${chId}`;
  }
  return name;
}

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'task_type', title: '类型', width: 120 },
  { colKey: 'agent_id', title: 'Agent', width: 80, cell: (_h: any, { row }: any) => row.agent_id || '-' },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'result_summary', title: '结果 / 操作' },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
];

const typeLabel = (t: string) => {
  const map: Record<string, string> = {
    generate: '文章生成',
    slideshow_generate: '演示文稿',
    video_generate: '短视频',
    batch_all: '批量执行',
    batch_variants: '变体生成',
  };
  return map[t] || t;
};

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

const resultSummary = (row: any) => {
  const r = row.result || {};
  if (row.task_type === 'generate' && r.article_id) return `文章 #${r.article_id} 已生成`;
  if (row.task_type === 'video_generate' && r.title) return `🎥 ${r.title} · ${r.scene_count || 0}场景`;
  if (r.error) return `失败: ${String(r.error).slice(0, 60)}`;
  return JSON.stringify(r).slice(0, 60);
};

function downloadVideoById(row: any) {
  const taskId = row.id;
  if (!taskId) return;
  window.open(getVideoDownloadUrl(taskId), '_blank');
}

const stepDotClass = (status: string) => {
  if (status === 'success') return 'dot-success';
  if (status === 'failed') return 'dot-error';
  return 'dot-running';
};

const openSlideshowPreviewById = (task: any) => {
  previewTask.value = task;
  previewUrl.value = getSlideshowPreviewUrl(task.id);
  previewLoading.value = true;
  previewError.value = '';
  slideshowPreviewVisible.value = true;
};

const fetchData = async () => {
  loading.value = true;
  try {
    const params: any = {};
    if (filterStatus.value) params.status = filterStatus.value;
    if (filterType.value) params.task_type = filterType.value;
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
  if (eventSource) { eventSource.close(); eventSource = null; }
};

const closeDrawer = () => {
  closeSSE();
  isStreaming.value = false;
};

onMounted(fetchData);
onBeforeUnmount(() => closeSSE());
</script>

<style scoped>
.step-timeline { position: relative; padding-left: 24px; }
.step-item { position: relative; padding-bottom: 20px; }
.step-dot { position: absolute; left: -24px; top: 4px; width: 12px; height: 12px; border-radius: 50%; z-index: 1; }
.dot-success { background-color: var(--td-success-color); }
.dot-error { background-color: var(--td-error-color); }
.dot-running { background-color: var(--td-warning-color); animation: pulse 1.5s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.step-line { position: absolute; left: -19px; top: 18px; width: 2px; bottom: 0; background-color: var(--td-component-border); }
.step-content { padding-left: 4px; }
.llm-output { background: var(--td-bg-color-container); border: 1px solid var(--td-component-border); border-radius: 8px; padding: 16px; max-height: 400px; overflow-y: auto; font-size: 13px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; }
</style>
