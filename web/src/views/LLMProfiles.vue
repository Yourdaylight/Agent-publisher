<template>
  <div>
    <!-- LLM Profile Management -->
    <t-card title="LLM 配置管理" style="margin-bottom: 24px">
      <template #actions>
        <t-button theme="primary" @click="openCreate">
          <template #icon><t-icon name="add" /></template>
          新建配置
        </t-button>
      </template>

      <t-loading :loading="loading">
        <div v-if="profiles.length === 0 && !loading && !globalDefault" style="text-align: center; padding: 40px; color: var(--td-text-color-placeholder)">
          暂无 LLM 配置，点击右上角"新建配置"开始
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px">
          <!-- Global default from Settings -->
          <t-card
            v-if="globalDefault"
            :key="'global-default'"
            :bordered="true"
            :style="{ borderLeft: '4px solid var(--td-success-color)', opacity: 0.95 }"
          >
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px">
              <span style="font-size: 16px">&#9889;</span>
              <strong style="font-size: 15px">{{ globalDefault.name }}</strong>
              <t-tag size="small" theme="success" variant="light">全局默认</t-tag>
            </div>
            <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 4px">
              {{ globalDefault.provider }} / {{ globalDefault.model }}
            </div>
            <div v-if="globalDefault.base_url" style="font-size: 12px; color: var(--td-text-color-placeholder); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="globalDefault.base_url">
              {{ globalDefault.base_url }}
            </div>
            <div v-if="globalDefault.description" style="font-size: 12px; color: var(--td-text-color-placeholder); margin-bottom: 8px">
              {{ globalDefault.description }}
            </div>
            <div style="display: flex; align-items: center; gap: 8px; margin-top: 12px; font-size: 12px; color: var(--td-text-color-placeholder)">
              <span>API Key: {{ globalDefault.api_key ? (globalDefault.api_key.length > 8 ? globalDefault.api_key.slice(0, 4) + '****' + globalDefault.api_key.slice(-4) : '****') : '(未配置)' }}</span>
            </div>
            <div style="margin-top: 8px; font-size: 11px; color: var(--td-text-color-disabled)">
              此项来自全局 Settings，请在"全局配置"页面修改
            </div>
          </t-card>

          <t-card
            v-for="p in profiles"
            :key="p.id"
            :bordered="true"
            :style="{ borderLeft: p.is_default ? '4px solid var(--td-brand-color)' : '' }"
          >
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px">
              <span v-if="p.is_default" style="font-size: 16px">&#11088;</span>
              <strong style="font-size: 15px">{{ p.name }}</strong>
              <t-tag v-if="p.is_default" size="small" theme="primary" variant="light">默认</t-tag>
            </div>
            <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 4px">
              {{ p.provider }} / {{ p.model }}
            </div>
            <div v-if="p.base_url" style="font-size: 12px; color: var(--td-text-color-placeholder); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="p.base_url">
              {{ p.base_url }}
            </div>
            <div v-if="p.description" style="font-size: 12px; color: var(--td-text-color-placeholder); margin-bottom: 8px">
              {{ p.description }}
            </div>
            <div style="display: flex; gap: 8px; margin-top: 12px">
              <t-button size="small" variant="outline" @click="openEdit(p)">编辑</t-button>
              <t-popconfirm content="确定删除此配置？" @confirm="onDelete(p.id)">
                <t-button size="small" variant="outline" theme="danger">删除</t-button>
              </t-popconfirm>
              <t-button v-if="!p.is_default" size="small" variant="text" @click="onSetDefault(p.id)">设为默认</t-button>
            </div>
          </t-card>
        </div>
      </t-loading>
    </t-card>

    <!-- Skill CLI Tool Panel -->
    <t-card title="Skill CLI 工具">
      <template #subtitle>
        通过 Skill CLI，AI Agent 可以直接操控本系统。
      </template>
      <div style="margin-bottom: 16px">
        <div style="margin-bottom: 8px; font-weight: 500">安装命令：</div>
        <div style="background: var(--td-bg-color-container-hover); border-radius: 6px; padding: 16px; font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; position: relative">{{ installCommand }}</div>
      </div>
      <div style="display: flex; gap: 12px">
        <t-button theme="primary" variant="outline" @click="onCopyCommand">
          <template #icon><t-icon name="file-copy" /></template>
          复制安装命令
        </t-button>
        <t-button variant="outline" @click="onDownloadSkill">
          <template #icon><t-icon name="download" /></template>
          下载 Skill 包
        </t-button>
      </div>
    </t-card>

    <!-- Create/Edit Dialog -->
    <t-dialog
      v-model:visible="dialogVisible"
      :header="editingProfile ? '编辑 LLM 配置' : '新建 LLM 配置'"
      :confirm-btn="{ content: editingProfile ? '更新' : '创建', loading: saving }"
      @confirm="onSave"
      width="520px"
    >
      <t-form :data="formData" ref="formRef" label-width="100px" style="margin-top: 12px">
        <t-form-item label="名称" name="name">
          <t-input v-model="formData.name" placeholder="如：GPT-4o 生产" />
        </t-form-item>
        <t-form-item label="Provider" name="provider">
          <t-select v-model="formData.provider">
            <t-option label="OpenAI 兼容" value="openai" />
            <t-option label="Claude (Anthropic)" value="claude" />
            <t-option label="MiniMax" value="minimax" />
          </t-select>
        </t-form-item>
        <t-form-item label="模型" name="model">
          <t-input v-model="formData.model" placeholder="如：gpt-4o, claude-sonnet-4-6" />
        </t-form-item>
        <t-form-item label="API Key" name="api_key">
          <t-input v-model="formData.api_key" type="password" placeholder="留空使用全局默认" />
        </t-form-item>
        <t-form-item label="Base URL" name="base_url">
          <t-input v-model="formData.base_url" placeholder="自定义 API 地址（留空使用默认）" />
        </t-form-item>
        <t-form-item label="描述" name="description">
          <t-textarea v-model="formData.description" placeholder="可选描述" :autosize="{ minRows: 2 }" />
        </t-form-item>
        <t-form-item label="设为默认" name="is_default">
          <t-switch v-model="formData.is_default" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { MessagePlugin } from 'tdesign-vue-next';
import {
  getLLMProfiles,
  createLLMProfile,
  updateLLMProfile,
  deleteLLMProfile,
  setDefaultLLMProfile,
  getUserInfo,
  getSettings,
} from '@/api';

const loading = ref(false);
const saving = ref(false);
const profiles = ref<any[]>([]);
const dialogVisible = ref(false);
const editingProfile = ref<any>(null);
const formRef = ref();

// Global default LLM settings (from /api/settings)
const globalDefault = ref<any>(null);

const formData = ref({
  name: '',
  provider: 'openai',
  model: 'gpt-4o',
  api_key: '',
  base_url: '',
  description: '',
  is_default: false,
});

const userEmail = computed(() => {
  const info = getUserInfo();
  return info?.email || 'your@email.com';
});

const installCommand = computed(() => {
  const origin = window.location.origin;
  return `curl -o /tmp/ap-skill.zip ${origin}/api/skill-package/download && unzip -o /tmp/ap-skill.zip -d ~/.ap-skill && uv run ~/.ap-skill/scripts/agent_publisher.py --url ${origin} auth --email ${userEmail.value}`;
});

const fetchProfiles = async () => {
  loading.value = true;
  try {
    const [profileRes, settingsRes] = await Promise.all([
      getLLMProfiles().catch(() => ({ data: [] })),
      getSettings().catch(() => null),
    ]);
    profiles.value = profileRes?.data || [];

    // Show global default from Settings if available
    const s = settingsRes?.data;
    if (s && (s.default_llm_provider || s.default_llm_model)) {
      globalDefault.value = {
        id: -1,
        name: '全局默认配置',
        provider: s.default_llm_provider,
        model: s.default_llm_model,
        base_url: s.default_llm_base_url || '',
        api_key: s.default_llm_api_key || '',
        description: '来自全局配置（Settings），当前生效的默认模型',
        is_default: true,
        is_global: true,
      };
    } else {
      globalDefault.value = null;
    }
  } catch (e: any) {
    MessagePlugin.error('加载 LLM 配置失败');
  } finally {
    loading.value = false;
  }
};

const openCreate = () => {
  editingProfile.value = null;
  formData.value = {
    name: '',
    provider: 'openai',
    model: 'gpt-4o',
    api_key: '',
    base_url: '',
    description: '',
    is_default: false,
  };
  dialogVisible.value = true;
};

const openEdit = (p: any) => {
  editingProfile.value = p;
  formData.value = {
    name: p.name,
    provider: p.provider,
    model: p.model,
    api_key: '',  // Don't prefill masked key
    base_url: p.base_url || '',
    description: p.description || '',
    is_default: p.is_default,
  };
  dialogVisible.value = true;
};

const onSave = async () => {
  saving.value = true;
  try {
    const payload = { ...formData.value };
    // If editing and api_key is empty, don't send it (keep existing)
    if (editingProfile.value && !payload.api_key) {
      const { api_key, ...rest } = payload;
      if (editingProfile.value) {
        await updateLLMProfile(editingProfile.value.id, rest);
      }
    } else {
      if (editingProfile.value) {
        await updateLLMProfile(editingProfile.value.id, payload);
      } else {
        await createLLMProfile(payload);
      }
    }
    MessagePlugin.success(editingProfile.value ? '更新成功' : '创建成功');
    dialogVisible.value = false;
    await fetchProfiles();
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.detail || '操作失败');
  } finally {
    saving.value = false;
  }
};

const onDelete = async (id: number) => {
  try {
    await deleteLLMProfile(id);
    MessagePlugin.success('已删除');
    await fetchProfiles();
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.detail || '删除失败');
  }
};

const onSetDefault = async (id: number) => {
  try {
    await setDefaultLLMProfile(id);
    MessagePlugin.success('已设为默认');
    await fetchProfiles();
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.detail || '操作失败');
  }
};

const onCopyCommand = async () => {
  try {
    await navigator.clipboard.writeText(installCommand.value);
    MessagePlugin.success('安装命令已复制到剪贴板');
  } catch {
    MessagePlugin.warning('复制失败，请手动复制');
  }
};

const onDownloadSkill = () => {
  window.open(`${window.location.origin}/api/skill-package/download`, '_blank');
};

onMounted(fetchProfiles);
</script>
