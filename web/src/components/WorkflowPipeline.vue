<template>
  <div class="workflow-shell">
    <template v-if="task">
      <div class="workflow-head">
        <div>
          <div class="workflow-title">{{ task.task_type === 'slideshow_generate' ? 'AI 正在生成演示文稿' : 'AI 正在生成文章草稿' }}</div>
          <div class="workflow-subtitle">任务 #{{ task.id }} · Agent {{ task.agent_id || '-' }}</div>
        </div>
        <t-tag :theme="task.status === 'running' ? 'primary' : 'warning'" variant="light">
          {{ task.status === 'running' ? '实时执行中' : '等待调度' }}
        </t-tag>
      </div>

      <t-steps layout="vertical" :current="Math.max((task.steps?.length || 1) - 1, 0)">
        <t-step v-for="step in displaySteps" :key="step.key" :title="step.label" :content="step.content" />
      </t-steps>

      <div class="stream-box">
        <div class="stream-title">AI 输出预览</div>
        <div v-if="streamText" class="stream-content">{{ streamText }}</div>
        <div v-else class="stream-empty">当前还没有流式输出，任务进入正文生成阶段后会在这里显示。</div>
      </div>
    </template>

    <template v-else>
      <div class="workflow-title">AI 工作流会在这里实时显示</div>
      <div class="workflow-subtitle">从热点、素材或 Agent 发起生成后，你会看到 AI 如何一步步完成创作。</div>
      <div class="capability-grid">
        <div v-for="item in capabilities" :key="item.title" class="capability-card">
          <div class="capability-title">{{ item.title }}</div>
          <div class="capability-desc">{{ item.desc }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  task?: any | null;
  streamText?: string;
}>();

const capabilities = [
  { title: '热点成文', desc: '从热榜选题直接生成公众号草稿。' },
  { title: '素材重组', desc: '把 RSS、手动素材和热榜内容重新组织成文章。' },
  { title: '批量运行', desc: '一次性调度多个 Agent 自动生产。' },
  { title: '版本变体', desc: '围绕同一篇文章生成不同风格版本。' },
];

const displaySteps = computed(() => {
  const map: Record<string, string> = {
    rss_fetch: '收集素材并整理输入',
    llm_generate: '调用大模型生成文章正文',
    image_generate: '生成封面图或配图',
    save_article: '保存为草稿并进入文章库',
    llm_outline: '生成演示文稿大纲',
    orchestrator: '拆分章节与页面',
    assembly: '组装最终内容',
    build_html: '生成在线预览文件',
  };
  const steps = props.task?.steps || [];
  if (!steps.length) {
    return [{ key: 'pending', label: '准备中', content: '等待调度 AI 工作流。' }];
  }
  return steps.map((step: any) => ({
    key: step.name,
    label: map[step.name] || step.name,
    content: step.output?.title || step.output?.provider || (step.finished_at ? '本阶段已完成。' : '执行中...'),
  }));
});
</script>

<style scoped>
.workflow-shell { min-height: 100%; }
.workflow-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 16px; }
.workflow-title { font-size: 18px; font-weight: 700; color: var(--td-text-color-primary); }
.workflow-subtitle { margin-top: 6px; font-size: 13px; color: var(--td-text-color-secondary); line-height: 1.7; }
.stream-box { margin-top: 18px; padding: 14px; border-radius: 14px; background: var(--td-bg-color-container); }
.stream-title { font-size: 13px; font-weight: 700; margin-bottom: 10px; color: var(--td-text-color-primary); }
.stream-content { white-space: pre-wrap; font-size: 13px; line-height: 1.75; color: var(--td-text-color-primary); max-height: 280px; overflow: auto; }
.stream-empty { font-size: 13px; line-height: 1.75; color: var(--td-text-color-secondary); }
.capability-grid { margin-top: 18px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.capability-card { padding: 14px; border-radius: 14px; border: 1px solid var(--td-component-stroke); background: linear-gradient(180deg, #fff 0%, #fbfcff 100%); }
.capability-title { font-size: 14px; font-weight: 700; color: var(--td-text-color-primary); margin-bottom: 8px; }
.capability-desc { font-size: 12px; line-height: 1.7; color: var(--td-text-color-secondary); }
</style>
