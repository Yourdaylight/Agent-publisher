<template>
  <t-form :data="formData" :rules="rules" ref="formRef" label-width="120px" @submit="onSubmit">
    <t-form-item label="Agent 名称" name="name">
      <t-input v-model="formData.name" placeholder="如：科技前沿观察员" />
    </t-form-item>
    <t-form-item label="主题" name="topic">
      <t-select v-model="formData.topic" placeholder="选择或输入主题" filterable creatable>
        <t-option v-for="t in topicPresets" :key="t" :label="t" :value="t" />
      </t-select>
    </t-form-item>
    <t-form-item label="描述" name="description">
      <t-textarea v-model="formData.description" placeholder="Agent 的职责描述" :autosize="{ minRows: 2 }" />
    </t-form-item>
    <t-form-item label="关联公众号" name="account_id">
      <t-select v-model="formData.account_id" placeholder="选择公众号">
        <t-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
      </t-select>
    </t-form-item>
    <t-form-item label="Agent 角色" name="role">
      <t-select v-model="formData.role" placeholder="选择角色">
        <t-option value="collector" label="采集型 - 仅负责素材收集" />
        <t-option value="processor" label="加工型 - 仅负责内容加工" />
        <t-option value="publisher" label="发布型 - 仅负责发布" />
        <t-option value="full_pipeline" label="全流程 - 采集+加工+发布" />
      </t-select>
    </t-form-item>
    <t-form-item label="来源模式" name="source_mode">
      <t-select v-model="formData.source_mode" placeholder="选择来源模式">
        <t-option value="rss" label="RSS 聚合 - 订阅 RSS 源自动采集" />
        <t-option value="skills_feed" label="Skills 供稿 - 由外部 Skills 推送素材" />
        <t-option value="independent_search" label="独立采集 - Agent 自主搜索网络" />
      </t-select>
      <div style="margin-top: 4px; font-size: 12px; color: var(--td-text-color-placeholder)">
        <template v-if="formData.source_mode === 'rss'">适用于有稳定 RSS 源的新闻/博客订阅场景</template>
        <template v-else-if="formData.source_mode === 'skills_feed'">适用于有外部数据管道或 Skills Agent 供稿的场景</template>
        <template v-else-if="formData.source_mode === 'independent_search'">适用于垂直领域的主动搜索采集（功能开发中）</template>
      </div>
    </t-form-item>
    <t-form-item label="RSS 源" v-show="formData.source_mode === 'rss'">
      <div style="width: 100%">
        <div v-for="(rss, idx) in formData.rss_sources" :key="idx" style="display: flex; gap: 8px; margin-bottom: 8px">
          <t-input v-model="rss.name" placeholder="源名称" style="width: 150px" />
          <t-input v-model="rss.url" placeholder="RSS URL" style="flex: 1" />
          <t-button theme="danger" variant="text" @click="formData.rss_sources.splice(idx, 1)">
            <t-icon name="delete" />
          </t-button>
        </div>
        <t-button variant="dashed" @click="formData.rss_sources.push({ name: '', url: '' })">
          <t-icon name="add" /> 添加 RSS 源
        </t-button>
      </div>
    </t-form-item>
    <t-form-item label="Skills 白名单" v-show="formData.source_mode === 'skills_feed'">
      <div style="width: 100%">
        <div v-for="(src, idx) in formData.allowed_skill_sources" :key="idx" style="display: flex; gap: 8px; margin-bottom: 8px">
          <t-input v-model="formData.allowed_skill_sources[idx]" placeholder="Skill 邮箱/身份" style="flex: 1" />
          <t-button theme="danger" variant="text" @click="formData.allowed_skill_sources.splice(idx, 1)">
            <t-icon name="delete" />
          </t-button>
        </div>
        <t-button variant="dashed" @click="formData.allowed_skill_sources.push('')">
          <t-icon name="add" /> 添加 Skill 来源
        </t-button>
      </div>
    </t-form-item>
    <t-form-item label="搜索配置" v-show="formData.source_mode === 'independent_search'">
      <t-card :bordered="true" style="width: 100%">
        <t-alert theme="info" message="独立搜索采集功能正在开发中，当前仅做配置存储" style="margin-bottom: 12px" />
        <t-form-item label="领域" style="margin-bottom: 8px">
          <t-input v-model="formData.search_config.domain" placeholder="如：人工智能" />
        </t-form-item>
        <t-form-item label="关键词" style="margin-bottom: 8px">
          <t-input v-model="formData.search_config.keywords_text" placeholder="逗号分隔，如：LLM,GPT,大模型" />
        </t-form-item>
        <t-form-item label="限定站点">
          <t-input v-model="formData.search_config.sites_text" placeholder="逗号分隔，如：arxiv.org,github.com" />
        </t-form-item>
      </t-card>
    </t-form-item>
    <t-form-item label="LLM Provider">
      <t-select v-model="formData.llm_provider" style="width: 300px">
        <t-option label="OpenAI 兼容" value="openai" />
        <t-option label="Claude (Anthropic)" value="claude" />
        <t-option label="MiniMax" value="minimax" />
      </t-select>
    </t-form-item>
    <t-form-item label="LLM 模型">
      <t-input v-model="formData.llm_model" placeholder="如：gpt-4o, claude-sonnet-4-6" style="width: 300px" />
    </t-form-item>
    <t-form-item label="API Base URL">
      <t-input v-model="formData.llm_base_url" placeholder="自定义 API 地址（留空使用默认）" />
    </t-form-item>
    <t-form-item label="API Key">
      <t-input v-model="formData.llm_api_key" type="password" placeholder="LLM API Key（留空使用全局默认）" />
    </t-form-item>
    <t-form-item label="默认变体风格">
      <t-select v-model="formData.default_style_id" placeholder="选择默认预设风格（可选）" clearable filterable>
        <t-option v-for="s in stylePresets" :key="s.style_id" :label="s.name" :value="s.style_id">
          <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
            <span>{{ s.name }}</span>
            <span style="font-size: 12px; color: var(--td-text-color-placeholder)">{{ s.style_id }}</span>
          </div>
        </t-option>
      </t-select>
    </t-form-item>
    <t-form-item label="配图风格">
      <t-input v-model="formData.image_style" placeholder="如：现代简约风格，色彩鲜明" />
    </t-form-item>
    <t-form-item label="定时计划">
      <t-select v-model="formData.schedule_cron">
        <t-option label="每天 8:00" value="0 8 * * *" />
        <t-option label="每天 12:00" value="0 12 * * *" />
        <t-option label="每天 18:00" value="0 18 * * *" />
        <t-option label="每 6 小时" value="0 */6 * * *" />
        <t-option label="工作日 9:00" value="0 9 * * 1-5" />
      </t-select>
    </t-form-item>
    <t-form-item v-if="!hideSubmit">
      <t-button theme="primary" type="submit" :loading="loading">
        {{ editId ? '更新' : '创建' }}
      </t-button>
    </t-form-item>
  </t-form>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue';
import { createAgent, updateAgent, getAccounts, getStylePresets } from '@/api';

const topicPresets = ['AI与科技', '金融投资', '健康养生', '教育成长', '娱乐文化', '体育竞技', '汽车出行', '美食烹饪'];

const props = defineProps<{
  editId?: number;
  initialData?: any;
  hideSubmit?: boolean;
  presetAccountId?: number;
}>();

const emit = defineEmits<{
  success: [data: any];
}>();

const formRef = ref();
const loading = ref(false);
const accounts = ref<any[]>([]);
const stylePresets = ref<any[]>([]);

const formData = reactive({
  name: '',
  topic: '',
  description: '',
  account_id: undefined as number | undefined,
  role: 'full_pipeline',
  source_mode: 'rss',
  rss_sources: [] as { name: string; url: string }[],
  allowed_skill_sources: [] as string[],
  search_config: { domain: '', keywords_text: '', sites_text: '' } as any,
  llm_provider: 'openai',
  llm_model: 'gpt-4o',
  llm_api_key: '',
  llm_base_url: '',
  prompt_template: '',
  image_style: '现代简约风格，色彩鲜明',
  default_style_id: null as string | null,
  schedule_cron: '0 8 * * *',
  is_active: true,
});

const rules = {
  name: [{ required: true, message: '请输入 Agent 名称' }],
  topic: [{ required: true, message: '请选择主题' }],
  account_id: [{ required: true, message: '请选择关联公众号' }],
};

watch(() => props.initialData, (val) => {
  if (val) {
    Object.assign(formData, val);
    if (!formData.role) formData.role = 'full_pipeline';
    if (!formData.source_mode) formData.source_mode = 'rss';
    if (!formData.allowed_skill_sources) formData.allowed_skill_sources = [];
    if (!formData.search_config) formData.search_config = { domain: '', keywords_text: '', sites_text: '' };
  }
}, { immediate: true });

watch(() => props.presetAccountId, (val) => {
  if (val) formData.account_id = val;
}, { immediate: true });

onMounted(async () => {
  try {
    const [accRes, styleRes] = await Promise.all([getAccounts(), getStylePresets()]);
    accounts.value = accRes.data;
    stylePresets.value = styleRes.data;
  } catch {}
});

const onSubmit = async ({ validateResult }: any) => {
  if (validateResult !== true) return;
  loading.value = true;
  try {
    const payload = { ...formData } as any;
    if (payload.search_config) {
      payload.search_config = {
        domain: payload.search_config.domain || '',
        keywords: (payload.search_config.keywords_text || '').split(',').map((k: string) => k.trim()).filter(Boolean),
        site_constraints: (payload.search_config.sites_text || '').split(',').map((s: string) => s.trim()).filter(Boolean),
      };
    }
    if (payload.allowed_skill_sources) {
      payload.allowed_skill_sources = payload.allowed_skill_sources.filter((s: string) => s.trim());
    }
    let res;
    if (props.editId) {
      res = await updateAgent(props.editId, payload);
    } else {
      res = await createAgent(payload);
    }
    emit('success', res.data);
  } catch (e: any) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const submit = () => formRef.value?.submit();
const validate = () => formRef.value?.validate();

defineExpose({ submit, validate, formData });
</script>
