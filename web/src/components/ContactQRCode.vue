<template>
  <t-card :bordered="true">
    <div style="display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap">
      <div style="width: 180px; height: 180px; border: 1px dashed var(--td-border-level-2-color); border-radius: 8px; display: flex; align-items: center; justify-content: center; background: var(--td-bg-color-container-hover); overflow: hidden">
        <img v-if="resolvedQr" :src="resolvedQr" alt="联系微信二维码" style="width: 100%; height: 100%; object-fit: contain" />
        <div v-else style="text-align: center; color: var(--td-text-color-placeholder); font-size: 12px; line-height: 1.6">
          请稍后放入二维码图片
          <br />
          storage/qrcode/contact.png
        </div>
      </div>
      <div style="flex: 1; min-width: 260px">
        <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px">联系开通会员</div>
        <div style="color: var(--td-text-color-secondary); line-height: 1.8; margin-bottom: 12px">
          {{ description || '当前支付能力建设中，请联系管理员微信完成开通。' }}
        </div>
        <t-descriptions :column="1" bordered size="small">
          <t-descriptions-item label="微信号">{{ wechatId || '待补充' }}</t-descriptions-item>
          <t-descriptions-item label="二维码路径">{{ qrPathDisplay }}</t-descriptions-item>
        </t-descriptions>
      </div>
    </div>
  </t-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  qr?: string;
  wechatId?: string;
  description?: string;
}>();

const qrPathDisplay = computed(() => props.qr || '/storage/qrcode/contact.png');
const resolvedQr = computed(() => {
  if (!props.qr) return '';
  if (props.qr.startsWith('http') || props.qr.startsWith('/')) return props.qr;
  return `/${props.qr.replace(/^\/+/, '')}`;
});
</script>
