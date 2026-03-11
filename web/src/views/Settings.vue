<template>
  <div>
    <t-card title="LLM 大模型配置" style="margin-bottom: 20px" :bordered="true">
      <t-form :data="llmForm" label-align="right" :label-width="140">
        <t-form-item label="Provider">
          <t-select v-model="llmForm.default_llm_provider" style="width: 300px">
            <t-option label="OpenAI (兼容)" value="openai" />
            <t-option label="Claude" value="claude" />
            <t-option label="MiniMax" value="minimax" />
          </t-select>
        </t-form-item>
        <t-form-item label="模型名称">
          <t-input v-model="llmForm.default_llm_model" placeholder="如 gpt-4o" style="width: 300px" />
        </t-form-item>
        <t-form-item label="API Key">
          <t-input v-model="llmForm.default_llm_api_key" type="password" placeholder="输入新值覆盖，留空不修改" style="width: 300px" />
        </t-form-item>
        <t-form-item label="API Base URL">
          <t-input v-model="llmForm.default_llm_base_url" placeholder="如 https://api.openai.com/v1" style="width: 400px" />
        </t-form-item>
        <t-form-item>
          <t-button theme="primary" :loading="llmSaving" @click="saveLLM">保存 LLM 配置</t-button>
        </t-form-item>
      </t-form>
    </t-card>

    <t-card title="文生图配置（腾讯云混元）" style="margin-bottom: 20px" :bordered="true">
      <t-form :data="imageForm" label-align="right" :label-width="140">
        <t-form-item label="Secret ID">
          <t-input v-model="imageForm.tencent_secret_id" type="password" placeholder="输入新值覆盖，留空不修改" style="width: 400px" />
        </t-form-item>
        <t-form-item label="Secret Key">
          <t-input v-model="imageForm.tencent_secret_key" type="password" placeholder="输入新值覆盖，留空不修改" style="width: 400px" />
        </t-form-item>
        <t-form-item>
          <t-button theme="primary" :loading="imageSaving" @click="saveImage">保存文生图配置</t-button>
        </t-form-item>
      </t-form>
    </t-card>

    <t-card title="访问密钥" :bordered="true">
      <t-form :data="keyForm" label-align="right" :label-width="140">
        <t-form-item label="当前密钥">
          <t-input v-model="keyForm.current_key" type="password" placeholder="输入当前密钥验证" style="width: 300px" />
        </t-form-item>
        <t-form-item label="新密钥">
          <t-input v-model="keyForm.new_key" type="password" placeholder="输入新密钥（至少6位）" style="width: 300px" />
        </t-form-item>
        <t-form-item>
          <t-button theme="warning" :loading="keySaving" @click="saveKey">修改访问密钥</t-button>
        </t-form-item>
      </t-form>
    </t-card>

    <!-- Current settings overview -->
    <t-card title="当前配置概览" style="margin-top: 20px" :bordered="true">
      <t-loading v-if="overviewLoading" />
      <t-descriptions v-else :column="1" bordered>
        <t-descriptions-item label="LLM Provider">{{ overview.default_llm_provider }}</t-descriptions-item>
        <t-descriptions-item label="LLM Model">{{ overview.default_llm_model }}</t-descriptions-item>
        <t-descriptions-item label="LLM API Key">{{ overview.default_llm_api_key || '未配置' }}</t-descriptions-item>
        <t-descriptions-item label="LLM Base URL">{{ overview.default_llm_base_url || '默认' }}</t-descriptions-item>
        <t-descriptions-item label="腾讯云 Secret ID">{{ overview.tencent_secret_id || '未配置' }}</t-descriptions-item>
        <t-descriptions-item label="腾讯云 Secret Key">{{ overview.tencent_secret_key || '未配置' }}</t-descriptions-item>
        <t-descriptions-item label="访问密钥">{{ overview.access_key_masked }}</t-descriptions-item>
      </t-descriptions>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { getSettings, updateLLMSettings, updateImageSettings, updateAccessKey } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';
import { useRouter } from 'vue-router';

const router = useRouter();

const llmForm = reactive({
  default_llm_provider: 'openai',
  default_llm_model: '',
  default_llm_api_key: '',
  default_llm_base_url: '',
});

const imageForm = reactive({
  tencent_secret_id: '',
  tencent_secret_key: '',
});

const keyForm = reactive({
  current_key: '',
  new_key: '',
});

const overview = ref<any>({});
const overviewLoading = ref(false);
const llmSaving = ref(false);
const imageSaving = ref(false);
const keySaving = ref(false);

const fetchOverview = async () => {
  overviewLoading.value = true;
  try {
    const res = await getSettings();
    overview.value = res.data;
    // Pre-fill form with current values (except masked keys)
    llmForm.default_llm_provider = res.data.default_llm_provider;
    llmForm.default_llm_model = res.data.default_llm_model;
    llmForm.default_llm_base_url = res.data.default_llm_base_url;
  } catch {
    // ignore
  } finally {
    overviewLoading.value = false;
  }
};

const saveLLM = async () => {
  llmSaving.value = true;
  try {
    const payload: any = {
      default_llm_provider: llmForm.default_llm_provider,
      default_llm_model: llmForm.default_llm_model,
      default_llm_base_url: llmForm.default_llm_base_url,
    };
    // Only send API key if user typed a new one
    if (llmForm.default_llm_api_key) {
      payload.default_llm_api_key = llmForm.default_llm_api_key;
    }
    await updateLLMSettings(payload);
    MessagePlugin.success('LLM 配置已保存');
    llmForm.default_llm_api_key = '';
    fetchOverview();
  } catch {
    MessagePlugin.error('保存失败');
  } finally {
    llmSaving.value = false;
  }
};

const saveImage = async () => {
  imageSaving.value = true;
  try {
    const payload: any = {};
    if (imageForm.tencent_secret_id) {
      payload.tencent_secret_id = imageForm.tencent_secret_id;
    }
    if (imageForm.tencent_secret_key) {
      payload.tencent_secret_key = imageForm.tencent_secret_key;
    }
    await updateImageSettings(payload);
    MessagePlugin.success('文生图配置已保存');
    imageForm.tencent_secret_id = '';
    imageForm.tencent_secret_key = '';
    fetchOverview();
  } catch {
    MessagePlugin.error('保存失败');
  } finally {
    imageSaving.value = false;
  }
};

const saveKey = async () => {
  if (!keyForm.current_key || !keyForm.new_key) {
    MessagePlugin.warning('请填写当前密钥和新密钥');
    return;
  }
  if (keyForm.new_key.length < 6) {
    MessagePlugin.warning('新密钥至少需要6位');
    return;
  }
  keySaving.value = true;
  try {
    await updateAccessKey(keyForm.current_key, keyForm.new_key);
    MessagePlugin.success('密钥已修改，请使用新密钥重新登录');
    localStorage.removeItem('ap_token');
    router.replace('/login');
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '修改失败';
    MessagePlugin.error(detail);
  } finally {
    keySaving.value = false;
  }
};

onMounted(fetchOverview);
</script>
