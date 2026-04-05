<template>
  <t-form :data="formData" :rules="rules" ref="formRef" label-width="120px" @submit="onSubmit">
    <t-form-item label="公众号名称" name="name">
      <t-input v-model="formData.name" placeholder="如：AI看公司" />
    </t-form-item>
    <t-form-item label="AppID" name="appid">
      <t-input v-model="formData.appid" placeholder="在微信公众平台 -> 基本配置中获取" />
    </t-form-item>
    <t-form-item label="AppSecret" name="appsecret">
      <t-input v-model="formData.appsecret" type="password" placeholder="重置后复制，注意保密" />
    </t-form-item>
    <t-form-item label="IP 白名单" name="ip_whitelist">
      <t-input v-model="formData.ip_whitelist" placeholder="服务器公网 IP，多个用逗号分隔" />
    </t-form-item>
    <t-form-item v-if="!hideSubmit">
      <t-button theme="primary" type="submit" :loading="loading">
        {{ editId ? '更新' : '添加' }}
      </t-button>
    </t-form-item>
  </t-form>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { createAccount, updateAccount } from '@/api'
import { MessagePlugin } from 'tdesign-vue-next'

const props = defineProps<{
  editId?: number
  initialData?: any
  hideSubmit?: boolean
}>()

const emit = defineEmits<{
  success: [data: any]
}>()

const formRef = ref()
const loading = ref(false)

const formData = reactive({
  name: '',
  appid: '',
  appsecret: '',
  ip_whitelist: '',
})

const rules = {
  name: [{ required: true, message: '请输入公众号名称' }],
  appid: [{ required: true, message: '请输入 AppID' }],
  appsecret: [{ required: true, message: '请输入 AppSecret' }],
}

watch(() => props.initialData, (val) => {
  if (val) {
    Object.assign(formData, val)
  }
}, { immediate: true })

const onSubmit = async ({ validateResult }: any) => {
  if (validateResult !== true) return
  loading.value = true
  try {
    let res
    if (props.editId) {
      res = await updateAccount(props.editId, formData)
    } else {
      res = await createAccount(formData)
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
