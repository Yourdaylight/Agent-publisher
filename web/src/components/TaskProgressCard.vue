<template>
  <div class="task-card" :class="{ active }">
    <div class="task-head">
      <div>
        <div class="task-title">{{ title }}</div>
        <div class="task-subtitle">{{ subtitle }}</div>
      </div>
      <t-tag :theme="statusTheme" variant="light">{{ statusLabel }}</t-tag>
    </div>

    <div class="pipeline">
      <div v-for="step in displaySteps" :key="step.key" class="pipeline-step">
        <div class="pipeline-dot" :class="step.state" />
        <div class="pipeline-label">{{ step.label }}</div>
      </div>
    </div>

    <div class="task-footer">
      <span>{{ currentStepLabel }}</span>
      <span>{{ task.steps?.length || 0 }}/{{ displaySteps.length }} 步</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  task: any;
  active?: boolean;
}>();

const articleSteps = [
  { key: 'rss_fetch', label: '素材' },
  { key: 'llm_generate', label: '成文' },
  { key: 'image_generate', label: '配图' },
  { key: 'save_article', label: '入库' },
];

const slideshowSteps = [
  { key: 'llm_outline', label: '大纲' },
  { key: 'orchestrator', label: '拆分' },
  { key: 'assembly', label: '组装' },
  { key: 'build_html', label: '预览' },
];

const baseSteps = computed(() => props.task?.task_type === 'slideshow_generate' ? slideshowSteps : articleSteps);
const finishedNames = computed(() => new Set((props.task?.steps || []).map((step: any) => step.name)));
const currentStepName = computed(() => props.task?.steps?.[props.task.steps.length - 1]?.name);

const displaySteps = computed(() => baseSteps.value.map((step) => ({
  ...step,
  state: finishedNames.value.has(step.key)
    ? 'done'
    : currentStepName.value === step.key || (!finishedNames.value.size && step === baseSteps.value[0])
      ? 'current'
      : 'todo',
})));

const statusTheme = computed(() => props.task?.status === 'running' ? 'primary' : props.task?.status === 'pending' ? 'warning' : 'default');
const statusLabel = computed(() => props.task?.status === 'running' ? 'AI 执行中' : props.task?.status === 'pending' ? '等待中' : (props.task?.status || '-'));
const title = computed(() => props.task?.task_type === 'slideshow_generate' ? `演示文稿 #${props.task.id}` : `文章草稿 #${props.task.id}`);
const subtitle = computed(() => `Agent ${props.task?.agent_id || '-'} · ${props.task?.created_at ? new Date(props.task.created_at).toLocaleString('zh-CN') : ''}`);
const currentStepLabel = computed(() => {
  const map: Record<string, string> = {
    rss_fetch: '正在抓取素材',
    llm_generate: '正在由 AI 生成正文',
    image_generate: '正在生成配图',
    save_article: '正在保存草稿',
    llm_outline: '正在生成大纲',
    orchestrator: '正在拆分章节',
    assembly: '正在组装内容',
    build_html: '正在生成预览',
  };
  return map[currentStepName.value || ''] || '等待 AI 开始';
});
</script>

<style scoped>
.task-card {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--td-component-stroke);
  background: linear-gradient(180deg, #fff 0%, #fbfcff 100%);
  cursor: pointer;
  transition: all .2s ease;
}
.task-card.active {
  border-color: var(--td-brand-color);
  box-shadow: 0 0 0 1px var(--td-brand-color-3);
}
.task-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.task-title { font-size: 15px; font-weight: 700; color: var(--td-text-color-primary); }
.task-subtitle { margin-top: 4px; font-size: 12px; color: var(--td-text-color-secondary); }
.pipeline { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.pipeline-step { display: flex; flex-direction: column; align-items: center; gap: 8px; text-align: center; }
.pipeline-dot { width: 12px; height: 12px; border-radius: 999px; background: var(--td-gray-color-5); }
.pipeline-dot.done { background: var(--td-success-color); }
.pipeline-dot.current { background: var(--td-brand-color); box-shadow: 0 0 0 4px var(--td-brand-color-1); }
.pipeline-label { font-size: 12px; color: var(--td-text-color-secondary); }
.task-footer { margin-top: 14px; display: flex; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--td-text-color-secondary); }
</style>
