<template>
  <div>
    <t-card :bordered="true" style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: center">
        <div>
          <div style="font-size: 18px; font-weight: 600">当前会员状态</div>
          <div style="margin-top: 8px; color: var(--td-text-color-secondary)">
            <template v-if="current.plan">
              {{ current.plan.display_name }} · 状态：{{ statusLabel(current.status) }}
            </template>
          </div>
          <div v-if="current.expires_at" style="font-size: 12px; color: var(--td-text-color-placeholder); margin-top: 4px">
            到期时间：{{ formatDate(current.expires_at) }}
          </div>
        </div>
      </div>
    </t-card>

    <t-empty v-if="plans.length === 0" description="暂无可用的会员方案" style="margin-bottom: 16px" />
    <t-row v-else :gutter="16" style="margin-bottom: 16px">
      <t-col v-for="plan in plans" :key="plan.name" :span="3">
        <t-card :bordered="true" hover-shadow>
          <div style="font-size: 18px; font-weight: 700; margin-bottom: 8px">{{ plan.display_name }}</div>
          <div style="font-size: 28px; font-weight: 700; color: var(--td-brand-color)">
            ¥{{ displayPrice(plan) }}
          </div>
          <div style="margin: 8px 0 16px; color: var(--td-text-color-secondary); font-size: 12px">
            {{ plan.name === 'annual' ? '年付方案' : '月付方案' }}
          </div>
          <div style="min-height: 180px; display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px">
            <div v-for="(value, key) in plan.features" :key="String(key)" style="font-size: 13px; color: var(--td-text-color-secondary)">
              {{ featureLabel(String(key)) }}：{{ value }}
            </div>
          </div>
          <t-button
            theme="primary"
            block
            :loading="submittingPlan === plan.name"
            :disabled="current.plan?.name === plan.name || plan.name === 'free'"
            @click="createOrder(plan.name)"
          >
            {{ current.plan?.name === plan.name ? '当前方案' : plan.name === 'free' ? '免费方案' : '立即开通' }}
          </t-button>
        </t-card>
      </t-col>
    </t-row>

    <ContactQRCode :qr="contact.wechat_qr" :wechat-id="contact.wechat_id" :description="contact.contact_description" />

    <t-alert theme="warning" style="margin-top: 16px" message="当前已预留支付接口，现阶段下单后请联系管理员微信人工开通。后续可无缝接入微信支付/支付宝。" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { MessagePlugin } from 'tdesign-vue-next';
import { createMembershipOrder, getCurrentMembership, getMembershipContact, getMembershipPlans } from '@/api';
import ContactQRCode from '@/components/ContactQRCode.vue';

const plans = ref<any[]>([]);
const current = ref<any>({ plan: { name: 'free', display_name: '免费版' }, status: 'free' });
const contact = ref<any>({});
const submittingPlan = ref<string>('');

const displayPrice = (plan: any) => plan.name === 'annual' ? plan.price_yearly : plan.price_monthly;
const statusLabel = (status: string) => {
  const map: Record<string, string> = { active: '生效中', expired: '已过期', cancelled: '已取消', free: '未开通' };
  return map[status] || status;
};
const formatDate = (value?: string) => value ? new Date(value).toLocaleString('zh-CN') : '-';
const featureLabel = (key: string) => {
  const map: Record<string, string> = {
    hotspot_export_daily: '热点导出/日',
    prompt_usage_monthly: '提示词调用/月',
    draft_generation_daily: '草稿生成/日',
    account_limit: '公众号数量',
    support: '支持服务',
  };
  return map[key] || key;
};

const createOrder = async (planName: string) => {
  submittingPlan.value = planName;
  try {
    const res = await createMembershipOrder(planName);
    MessagePlugin.success(`订单已创建：${res.data.order_no}，请联系管理员微信完成开通`);
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '创建订单失败');
  } finally {
    submittingPlan.value = '';
  }
};

onMounted(async () => {
  await Promise.all([
    getMembershipPlans().then((res) => { plans.value = res.data; }).catch(() => {}),
    getCurrentMembership().then((res) => { current.value = res.data; }).catch(() => {}),
    getMembershipContact().then((res) => { contact.value = res.data; }).catch(() => {}),
  ]);
});
</script>
