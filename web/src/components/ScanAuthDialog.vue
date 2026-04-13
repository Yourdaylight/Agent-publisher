<template>
  <t-dialog v-model:visible="visible" header="扫码授权公众号" :footer="false" width="520px" @close="onClose">
    <div v-if="!configured" style="text-align: center; padding: 30px 20px">
      <t-icon name="info-circle" style="font-size: 48px; color: var(--td-warning-color)" />
      <div style="margin-top: 16px; font-size: 15px; color: var(--td-text-color-primary)">
        微信第三方平台未配置
      </div>
      <div style="margin-top: 8px; font-size: 13px; color: var(--td-text-color-secondary); line-height: 1.8">
        管理员需要在 .env 文件中配置 WECHAT_PLATFORM_* 相关参数，<br/>
        并在微信开放平台注册第三方平台。<br/>
        详见 <t-link theme="primary" href="/docs/wechat-platform-setup.md" target="_blank">配置文档</t-link>
      </div>
      <div style="margin-top: 20px">
        <t-button theme="primary" variant="outline" @click="visible = false">知道了</t-button>
      </div>
    </div>
    <div v-else-if="!ticketReady" style="text-align: center; padding: 30px 20px">
      <t-icon name="time" style="font-size: 48px; color: var(--td-warning-color)" />
      <div style="margin-top: 16px; font-size: 15px; color: var(--td-text-color-primary)">
        等待微信推送验证票据
      </div>
      <div style="margin-top: 8px; font-size: 13px; color: var(--td-text-color-secondary); line-height: 1.8">
        微信会每 10 分钟推送一次 component_verify_ticket，<br/>
        请确保回调地址已正确配置并可以接收微信推送。<br/>
        配置完成后等待下一次推送（最长约 10 分钟）。
      </div>
      <div style="margin-top: 20px">
        <t-button theme="primary" variant="outline" @click="checkStatus">刷新状态</t-button>
      </div>
    </div>
    <div v-else style="text-align: center; padding: 20px">
      <t-loading v-if="loading" size="medium" text="生成授权二维码..." />
      <template v-else-if="authUrl">
        <div style="margin-bottom: 12px; color: var(--td-text-color-secondary); font-size: 14px">
          请使用公众号管理员微信扫描下方二维码
        </div>
        <div
          style="
            display: inline-block;
            padding: 12px;
            border: 1px solid var(--td-border-level-2);
            border-radius: 12px;
            background: #fff;
          "
        >
          <img :src="qrCodeDataUrl" style="width: 260px; height: 260px" alt="授权二维码" />
        </div>
        <div style="margin-top: 12px; font-size: 12px; color: var(--td-text-color-placeholder); line-height: 1.6">
          扫码后按提示完成授权，授权成功后公众号将自动添加到列表中<br/>
          二维码有效期约 10 分钟
        </div>
        <div style="margin-top: 12px; display: flex; justify-content: center; gap: 12px">
          <t-button variant="text" theme="primary" @click="refreshAuthUrl">
            <t-icon name="refresh" style="margin-right: 4px" />刷新二维码
          </t-button>
          <t-button variant="text" @click="openInNewTab">
            <t-icon name="browse" style="margin-right: 4px" />新窗口打开
          </t-button>
        </div>
      </template>
      <template v-else-if="errorMsg">
        <t-alert theme="error" :message="errorMsg" style="margin-bottom: 12px" />
        <t-button theme="primary" @click="refreshAuthUrl">重试</t-button>
      </template>
    </div>
  </t-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { getWechatPlatformStatus, getWechatPlatformAuthUrl } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';
import QRCode from 'qrcode';

const visible = defineModel<boolean>('visible', { default: false });
const emit = defineEmits<{
  close: [];
}>();

const loading = ref(false);
const configured = ref(false);
const ticketReady = ref(false);
const authUrl = ref('');
const h5AuthUrl = ref('');
const errorMsg = ref('');
const qrCodeDataUrl = ref('');

// Check platform status
const checkStatus = async () => {
  try {
    const res = await getWechatPlatformStatus();
    configured.value = res.data.configured;
    ticketReady.value = res.data.ticket_available;
  } catch {
    configured.value = false;
    ticketReady.value = false;
  }
};

// Generate QR code from auth URL
const generateQrCode = async (url: string) => {
  try {
    qrCodeDataUrl.value = await QRCode.toDataURL(url, {
      width: 260,
      margin: 1,
      color: { dark: '#000000', light: '#ffffff' },
    });
  } catch (err) {
    console.error('QR code generation failed:', err);
    // Fallback: use a QR code API service
    qrCodeDataUrl.value = `https://api.qrserver.com/v1/create-qr-code/?size=260x260&data=${encodeURIComponent(url)}`;
  }
};

// Get auth URL and generate QR code
const refreshAuthUrl = async () => {
  loading.value = true;
  errorMsg.value = '';
  authUrl.value = '';
  qrCodeDataUrl.value = '';
  try {
    const res = await getWechatPlatformAuthUrl();
    authUrl.value = res.data.auth_url;
    h5AuthUrl.value = res.data.h5_auth_url;
    await generateQrCode(authUrl.value);
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || '获取授权链接失败';
    errorMsg.value = detail;
    MessagePlugin.error(detail);
  } finally {
    loading.value = false;
  }
};

// Open auth URL in new tab
const openInNewTab = () => {
  if (authUrl.value) {
    window.open(authUrl.value, '_blank', 'width=800,height=600');
  }
};

// Handle dialog close
const onClose = () => {
  authUrl.value = '';
  qrCodeDataUrl.value = '';
  errorMsg.value = '';
  emit('close');
};

// When dialog opens, check status and load auth URL
watch(visible, async (val) => {
  if (val) {
    await checkStatus();
    if (configured.value && ticketReady.value) {
      await refreshAuthUrl();
    }
  }
});
</script>
