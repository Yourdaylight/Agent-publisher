<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
      <div>
        <h3 style="margin: 0 0 4px 0">邀请码管理</h3>
        <p style="margin: 0; color: var(--td-text-color-secondary); font-size: 13px">
          通过邀请码让自媒体推广用户快速体验系统
        </p>
      </div>
      <t-button theme="primary" @click="createDialog = true">生成邀请码</t-button>
    </div>

    <!-- Stats -->
    <div style="display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap">
      <t-card :bordered="true" style="flex: 1; min-width: 120px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-brand-color)">{{ stats.total_codes }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">总邀请码</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 120px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-success-color)">{{ stats.active_codes }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">活跃</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 120px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-warning-color)">{{ stats.total_redemptions }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">总激活次数</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 120px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-brand-color)">{{ stats.unique_users }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">邀请用户</div>
        </div>
      </t-card>
    </div>

    <!-- Table -->
    <t-table :data="codes" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #status="{ row }">
        <t-tag :theme="row.is_active ? 'success' : 'default'" variant="light">
          {{ row.is_active ? '启用' : '停用' }}
        </t-tag>
      </template>
      <template #usage="{ row }">
        {{ row.used_count }}{{ row.max_uses > 0 ? ` / ${row.max_uses}` : ' / ∞' }}
      </template>
      <template #op="{ row }">
        <t-space size="small">
          <t-link theme="primary" @click="toggleActive(row)">
            {{ row.is_active ? '停用' : '启用' }}
          </t-link>
          <t-popconfirm content="确认删除此邀请码？" @confirm="onDelete(row.id)">
            <t-link theme="danger">删除</t-link>
          </t-popconfirm>
        </t-space>
      </template>
    </t-table>

    <!-- Create Dialog -->
    <t-dialog
      v-model:visible="createDialog"
      header="生成邀请码"
      :confirm-btn="{ content: '生成', loading: creating }"
      @confirm="onCreate"
    >
      <t-form :data="createForm" label-align="right" :label-width="100">
        <t-form-item label="渠道">
          <t-select v-model="createForm.channel" style="width: 200px">
            <t-option value="douyin" label="抖音" />
            <t-option value="xiaohongshu" label="小红书" />
            <t-option value="wechat" label="微信" />
            <t-option value="open" label="通用公开" />
          </t-select>
        </t-form-item>
        <t-form-item label="生成数量">
          <t-input-number v-model="createForm.count" :min="1" :max="100" style="width: 200px" />
        </t-form-item>
        <t-form-item label="奖励积分">
          <t-input-number v-model="createForm.bonus_credits" :min="0" :max="1000" style="width: 200px" />
        </t-form-item>
        <t-form-item label="使用上限">
          <t-input-number v-model="createForm.max_uses" :min="0" style="width: 200px" />
          <div style="font-size: 12px; color: var(--td-text-color-placeholder); margin-top: 4px">0 = 无限制</div>
        </t-form-item>
        <t-form-item label="备注">
          <t-input v-model="createForm.note" placeholder="如：抖音4月推广活动" style="width: 300px" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { MessagePlugin } from 'tdesign-vue-next';
import {
  getInviteCodes,
  createInviteCodes,
  updateInviteCode,
  deleteInviteCode,
  getInviteCodeStats,
} from '@/api';

const loading = ref(false);
const creating = ref(false);
const createDialog = ref(false);
const codes = ref<any[]>([]);
const stats = ref({ total_codes: 0, active_codes: 0, total_redemptions: 0, unique_users: 0 });

const createForm = reactive({
  channel: 'open',
  count: 5,
  bonus_credits: 100,
  max_uses: 0,
  note: '',
});

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'code', title: '邀请码', width: 200 },
  { colKey: 'channel', title: '渠道', width: 100 },
  { colKey: 'usage', title: '使用量', width: 100 },
  { colKey: 'bonus_credits', title: '奖励积分', width: 100 },
  { colKey: 'status', title: '状态', width: 80 },
  { colKey: 'note', title: '备注', ellipsis: true },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => row.created_at ? new Date(row.created_at).toLocaleString() : '-' },
  { colKey: 'op', title: '操作', width: 120 },
];

const fetchData = async () => {
  loading.value = true;
  try {
    const [codesRes, statsRes] = await Promise.all([getInviteCodes(), getInviteCodeStats()]);
    codes.value = codesRes.data;
    stats.value = statsRes.data;
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '加载邀请码失败');
  } finally {
    loading.value = false;
  }
};

const onCreate = async () => {
  creating.value = true;
  try {
    const res = await createInviteCodes(createForm);
    MessagePlugin.success(`已生成 ${res.data.count} 个邀请码`);
    createDialog.value = false;
    fetchData();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '生成失败');
  } finally {
    creating.value = false;
  }
};

const toggleActive = async (row: any) => {
  try {
    await updateInviteCode(row.id, { is_active: !row.is_active });
    MessagePlugin.success(row.is_active ? '已停用' : '已启用');
    fetchData();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '操作失败');
  }
};

const onDelete = async (id: number) => {
  try {
    await deleteInviteCode(id);
    MessagePlugin.success('已删除');
    fetchData();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '删除失败');
  }
};

onMounted(fetchData);
</script>
