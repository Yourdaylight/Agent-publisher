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
    <t-form-item label="RSS 源">
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
import { ref, reactive, watch, onMounted } from 'vue'
import { createAgent, updateAgent, getAccounts } from '@/api'

const topicPresets = ['AI与科技', '金融投资', '健康养生', '教育成长', '娱乐文化', '体育竞技', '汽车出行', '美食烹饪']

const props = defineProps<{
  editId?: number
  initialData?: any
  hideSubmit?: boolean
  presetAccountId?: number
}>()

const emit = defineEmits<{
  success: [data: any]
}>()

const formRef = ref()
const loading = ref(false)
const accounts = ref<any[]>([])

const formData = reactive({
  name: '',
  topic: '',
  description: '',
  account_id: undefined as number | undefined,
  rss_sources: [] as { name: string; url: string }[],
  llm_provider: 'openai',
  llm_model: 'gpt-4o',
  llm_api_key: '',
  llm_base_url: '',
  prompt_template: '',
  image_style: '现代简约风格，色彩鲜明',
  schedule_cron: '0 8 * * *',
  is_active: true,
})

const rules = {
  name: [{ required: true, message: '请输入 Agent 名称' }],
  topic: [{ required: true, message: '请选择主题' }],
  account_id: [{ required: true, message: '请选择关联公众号' }],
}

watch(() => props.initialData, (val) => {
  if (val) Object.assign(formData, val)
}, { immediate: true })

watch(() => props.presetAccountId, (val) => {
  if (val) formData.account_id = val
}, { immediate: true })

onMounted(async () => {
  try {
    const res = await getAccounts()
    accounts.value = res.data
  } catch {}
})

const onSubmit = async ({ validateResult }: any) => {
  if (validateResult !== true) return
  loading.value = true
  try {
    let res
    if (props.editId) {
      res = await updateAgent(props.editId, formData)
    } else {
      res = await createAgent(formData)
    }
    emit('success', res.data)
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const submit = () => formRef.value?.submit()
const validate = () => formRef.value?.validate()

defineExpose({ submit, validate, formData })
</script>
