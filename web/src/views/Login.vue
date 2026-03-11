<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <t-icon name="robot" size="48px" style="color: var(--td-brand-color)" />
        <h1>Agent Publisher</h1>
        <p style="color: var(--td-text-color-secondary); margin-top: 4px">AI 驱动的多账号微信公众号文章发布系统</p>
      </div>
      <t-form ref="formRef" :data="formData" @submit="onSubmit" label-align="top">
        <t-form-item label="访问密钥" name="accessKey">
          <t-input
            v-model="formData.accessKey"
            type="password"
            placeholder="请输入访问密钥"
            size="large"
            :disabled="banned"
            @keyup.enter="onSubmit"
          >
            <template #prefix-icon><t-icon name="lock-on" /></template>
          </t-input>
        </t-form-item>
        <t-alert
          v-if="errorMsg"
          theme="error"
          :message="errorMsg"
          style="margin-bottom: 16px"
          close
          @close="errorMsg = ''"
        />
        <t-alert
          v-if="banned"
          theme="warning"
          message="由于多次登录失败，您的 IP 已被临时封禁，请稍后再试。"
          style="margin-bottom: 16px"
        />
        <t-form-item>
          <t-button theme="primary" type="submit" block size="large" :loading="loading" :disabled="banned">
            登录
          </t-button>
        </t-form-item>
      </t-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { login } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const router = useRouter();
const loading = ref(false);
const banned = ref(false);
const errorMsg = ref('');
const formData = ref({ accessKey: '' });

const onSubmit = async () => {
  if (!formData.value.accessKey) {
    errorMsg.value = '请输入访问密钥';
    return;
  }
  loading.value = true;
  errorMsg.value = '';
  try {
    const res = await login(formData.value.accessKey);
    const { token } = res.data;
    localStorage.setItem('ap_token', token);
    MessagePlugin.success('登录成功');
    router.replace('/dashboard');
  } catch (err: any) {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail || '登录失败';
    if (status === 403) {
      banned.value = true;
      errorMsg.value = detail;
    } else {
      errorMsg.value = detail;
    }
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 420px;
  padding: 48px 40px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  margin: 12px 0 0;
  font-size: 24px;
  color: var(--td-text-color-primary);
}
</style>
