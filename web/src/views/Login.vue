<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <t-icon name="robot" size="48px" style="color: var(--td-brand-color)" />
        <h1>Agent Publisher</h1>
        <p style="color: var(--td-text-color-secondary); margin-top: 4px">AI 驱动的多账号微信公众号文章发布系统</p>
      </div>

      <t-tabs v-model="loginMode" style="margin-bottom: 24px">
        <t-tab-panel value="accessKey" label="管理员密钥" />
        <t-tab-panel value="email" label="Email 登录" />
        <t-tab-panel value="invite" label="邀请码体验" />
      </t-tabs>

      <!-- Access Key Login -->
      <t-form v-if="loginMode === 'accessKey'" ref="formRef" :data="formData" @submit="onSubmitAccessKey" label-align="top">
        <t-form-item label="访问密钥" name="accessKey">
          <t-input
            v-model="formData.accessKey"
            type="password"
            placeholder="请输入访问密钥"
            size="large"
            :disabled="banned"
            @keyup.enter="onSubmitAccessKey"
          >
            <template #prefix-icon><t-icon name="lock-on" /></template>
          </t-input>
        </t-form-item>
        <t-alert
          v-if="errorMsg"
          theme="error"
          :message="errorMsg"
          style="margin-bottom: 16px"
          close-btn
          @close-btn-click="errorMsg = ''"
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

      <!-- Email Login -->
      <t-form v-else-if="loginMode === 'email'" ref="emailFormRef" :data="emailFormData" @submit="onSubmitEmail" label-align="top">
        <t-form-item label="邮箱地址" name="email">
          <t-input
            v-model="emailFormData.email"
            type="text"
            placeholder="请输入白名单中的邮箱地址"
            size="large"
            :disabled="banned"
            @keyup.enter="onSubmitEmail"
          >
            <template #prefix-icon><t-icon name="mail" /></template>
          </t-input>
        </t-form-item>
        <t-alert
          v-if="errorMsg"
          theme="error"
          :message="errorMsg"
          style="margin-bottom: 16px"
          close-btn
          @close-btn-click="errorMsg = ''"
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

      <!-- Invite Code Login -->
      <t-form v-else ref="inviteFormRef" :data="inviteFormData" @submit="onSubmitInvite" label-align="top">
        <t-form-item label="邀请码" name="code">
          <t-input
            v-model="inviteFormData.code"
            placeholder="如：AP-DOUYIN-A3X7"
            size="large"
            :disabled="banned"
          >
            <template #prefix-icon><t-icon name="discount" /></template>
          </t-input>
        </t-form-item>
        <t-form-item label="邮箱地址" name="email">
          <t-input
            v-model="inviteFormData.email"
            placeholder="请输入邮箱地址"
            size="large"
            :disabled="banned"
            @keyup.enter="onSubmitInvite"
          >
            <template #prefix-icon><t-icon name="mail" /></template>
          </t-input>
        </t-form-item>
        <t-alert
          v-if="errorMsg"
          theme="error"
          :message="errorMsg"
          style="margin-bottom: 16px"
          close-btn
          @close-btn-click="errorMsg = ''"
        />
        <t-form-item>
          <t-button theme="primary" type="submit" block size="large" :loading="loading" :disabled="banned">
            🚀 立即体验 — 免费获得 AI 创作积分
          </t-button>
        </t-form-item>
        <div style="text-align: center; margin-top: 12px; font-size: 13px; color: var(--td-text-color-secondary)">
          还没有邀请码？关注公众号回复「体验」获取
        </div>
      </t-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { loginByAccessKey, loginByEmail, loginByInviteCode, saveUserInfo } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const router = useRouter();
const loading = ref(false);
const banned = ref(false);
const errorMsg = ref('');
const loginMode = ref<'accessKey' | 'email' | 'invite'>('accessKey');
const formData = ref({ accessKey: '' });
const emailFormData = ref({ email: '' });
const inviteFormData = ref({ code: '', email: '' });

// Tab 切换时清除错误信息
watch(loginMode, () => {
  errorMsg.value = '';
  banned.value = false;
});

const handleLoginSuccess = (data: { token: string; email?: string; is_admin?: boolean }) => {
  localStorage.setItem('ap_token', data.token);
  saveUserInfo({
    email: data.email || '__admin__',
    is_admin: data.is_admin ?? true,
  });
  MessagePlugin.success('登录成功');
  router.replace('/create');
};

const handleLoginError = (err: any) => {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;

  if (status === 403) {
    banned.value = true;
    errorMsg.value = detail || '由于多次登录失败，当前 IP 已被临时封禁';
    return;
  }

  if (status === 401) {
    errorMsg.value = detail || '登录信息无效，请检查后重试';
    return;
  }

  if (status && status >= 500) {
    errorMsg.value = detail || `后端服务异常（HTTP ${status}），请检查服务日志`;
    return;
  }

  if (err?.request && !err?.response) {
    errorMsg.value = '无法连接后端服务，请确认前端 3080 和后端 9099 已启动';
    return;
  }

  errorMsg.value = detail || err?.message || '登录失败';
};

const onSubmitAccessKey = async () => {
  if (!formData.value.accessKey) {
    errorMsg.value = '请输入访问密钥';
    return;
  }
  loading.value = true;
  errorMsg.value = '';
  try {
    const res = await loginByAccessKey(formData.value.accessKey);
    handleLoginSuccess(res.data);
  } catch (err: any) {
    handleLoginError(err);
  } finally {
    loading.value = false;
  }
};

const onSubmitEmail = async () => {
  if (!emailFormData.value.email) {
    errorMsg.value = '请输入邮箱地址';
    return;
  }
  loading.value = true;
  errorMsg.value = '';
  try {
    const res = await loginByEmail(emailFormData.value.email);
    handleLoginSuccess(res.data);
  } catch (err: any) {
    handleLoginError(err);
  } finally {
    loading.value = false;
  }
};

const onSubmitInvite = async () => {
  if (!inviteFormData.value.code) {
    errorMsg.value = '请输入邀请码';
    return;
  }
  if (!inviteFormData.value.email) {
    errorMsg.value = '请输入邮箱地址';
    return;
  }
  loading.value = true;
  errorMsg.value = '';
  try {
    const res = await loginByInviteCode(inviteFormData.value.code, inviteFormData.value.email);
    handleLoginSuccess(res.data);
    if (res.data.message) {
      MessagePlugin.success(res.data.message);
    }
  } catch (err: any) {
    handleLoginError(err);
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
