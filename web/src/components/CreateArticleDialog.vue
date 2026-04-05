<template>
  <t-dialog :visible="visible" header="快速创作" :footer="false" width="580px" @update:visible="emit('update:visible', $event)">
    <div class="quick-create-dialog">
      <!-- 素材来源 -->
      <div class="dialog-section source-section">
        <div class="source-title">{{ hotspot?.title || '未选择热点' }}</div>
        <div class="source-meta" v-if="hotspot">
          <t-tag size="small" theme="primary" variant="light">{{ hotspot?.metadata?.platform_name || hotspot?.metadata?.platform || '热点' }}</t-tag>
          <span v-if="hotspot?.quality_score != null">热度 {{ (hotspot.quality_score * 100).toFixed(0) }}</span>
        </div>
      </div>

      <t-form layout="vertical">
        <!-- 写作身份 -->
        <t-form-item label="写作身份" v-if="agents.length > 1">
          <t-select v-model="form.agent_id" placeholder="选择写作身份">
            <t-option v-for="agent in agents" :key="agent.id" :label="agentLabel(agent)" :value="agent.id" />
          </t-select>
        </t-form-item>
        <div v-else class="agent-auto-hint">
          <span>写作身份：</span>
          <t-tag theme="primary" variant="light" size="small">{{ agents[0]?.name || '锐评官（内置默认）' }}</t-tag>
        </div>

        <!-- 写作风格 -->
        <t-form-item v-if="stylePresets.length" label="写作风格">
          <t-select v-model="form.style_id" placeholder="不选则用 Agent 默认风格" clearable>
            <t-option v-for="style in stylePresets" :key="style.style_id" :label="style.name" :value="style.style_id" />
          </t-select>
        </t-form-item>

        <!-- 创作模式 -->
        <t-form-item label="创作模式">
          <t-radio-group v-model="form.mode" variant="default-filled">
            <t-radio-button value="rewrite">爆款二创</t-radio-button>
            <t-radio-button value="summary">热点总结</t-radio-button>
            <t-radio-button value="expand">观点扩写</t-radio-button>
          </t-radio-group>
          <div class="mode-desc">{{ modeDescriptions[form.mode] }}</div>
        </t-form-item>

        <!-- 创作指令 (用户提示词) -->
        <t-form-item label="创作指令">
          <t-textarea
            v-model="form.user_prompt"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="告诉 AI 你的特殊要求，如：重点分析技术突破点，对比 GPT-5……"
          />
          <div class="prompt-fusion-hint">
            系统会自动融合 Agent 风格 + 写作模板 + 你的指令来生成内容
          </div>
        </t-form-item>

        <!-- 操作 -->
        <div class="dialog-footer">
          <t-button variant="outline" @click="emit('update:visible', false)">取消</t-button>
          <t-button theme="primary" :loading="loading" @click="submit">🚀 开始生成</t-button>
        </div>
      </t-form>
    </div>
  </t-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';

const props = defineProps<{
  visible: boolean;
  loading?: boolean;
  hotspot: any;
  agents: any[];
  stylePresets: any[];
  prompts: any[];
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'submit', payload: { agent_id?: number; style_id?: string; prompt_template_id?: number; user_prompt?: string; mode?: string }): void;
}>();

const form = reactive({
  agent_id: undefined as number | undefined,
  style_id: undefined as string | undefined,
  prompt_template_id: undefined as number | undefined,
  user_prompt: '' as string,
  mode: 'rewrite' as string,
});

const modeDescriptions: Record<string, string> = {
  rewrite: '基于原文内容二次创作，保留核心信息，用全新角度重新表达',
  summary: '从多个信源角度综合总结，提炼关键信息',
  expand: '基于热点展开深度分析，加入独到观点和行业洞察',
};

const agentLabel = (agent: any) => {
  const suffix = agent.is_builtin ? '（内置默认）' : '';
  return `${agent.name}${suffix}`;
};

watch(() => props.visible, (visible) => {
  if (visible) {
    const builtin = props.agents.find((a) => a.is_builtin);
    form.agent_id = builtin?.id || props.agents[0]?.id;
    form.style_id = undefined;
    form.prompt_template_id = undefined;
    form.user_prompt = '';
    form.mode = 'rewrite';
  }
});

const submit = () => emit('submit', { ...form });
</script>

<style scoped>
.quick-create-dialog {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.source-section {
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--td-bg-color-container-hover);
  margin-bottom: 8px;
}
.source-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.5;
  color: var(--td-text-color-primary);
}
.source-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.agent-auto-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0 12px;
  font-size: 13px;
  color: var(--td-text-color-secondary);
}
.prompt-fusion-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  line-height: 1.5;
}
.mode-desc {
  margin-top: 6px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
  line-height: 1.5;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 8px;
}
</style>
