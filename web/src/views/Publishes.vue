<template>
  <div>
    <!-- Stats cards -->
    <div style="display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap">
      <t-card :bordered="true" style="flex: 1; min-width: 150px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-brand-color)">{{ stats.total }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">总记录数</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-success-color)">{{ stats.success }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">成功</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-error-color)">{{ stats.failed }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">失败</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-brand-color)">{{ stats.publishes }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">发布次数</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-warning-color)">{{ stats.syncs }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">同步次数</div>
        </div>
      </t-card>
    </div>

    <!-- Filters -->
    <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap">
      <t-input
        v-model="filterArticleId"
        placeholder="文章 ID"
        clearable
        style="width: 140px"
        type="number"
        @change="fetchRecords"
      />
      <t-select v-model="filterAction" placeholder="操作类型" clearable style="width: 140px" @change="fetchRecords">
        <t-option label="发布" value="publish" />
        <t-option label="同步" value="sync" />
      </t-select>
      <t-select v-model="filterStatus" placeholder="状态" clearable style="width: 140px" @change="fetchRecords">
        <t-option label="成功" value="success" />
        <t-option label="失败" value="failed" />
      </t-select>
      <t-button theme="default" variant="outline" @click="onReset">重置</t-button>
    </div>

    <!-- Records table -->
    <t-table
      :data="records"
      :columns="columns"
      row-key="id"
      :loading="loading"
      stripe
      :pagination="pagination"
      @page-change="onPageChange"
    >
      <template #action="{ row }">
        <t-tag
          :theme="row.action === 'publish' ? 'primary' : 'warning'"
          variant="light"
        >
          {{ row.action === 'publish' ? '发布' : '同步' }}
        </t-tag>
      </template>
      <template #recordStatus="{ row }">
        <t-tag
          :theme="row.status === 'success' ? 'success' : 'danger'"
          variant="light"
        >
          {{ row.status === 'success' ? '成功' : '失败' }}
        </t-tag>
      </template>
      <template #op="{ row }">
        <t-space>
          <t-link v-if="row.error_message" theme="danger" @click="showError(row)">查看错误</t-link>
        </t-space>
      </template>
    </t-table>

    <!-- Error detail dialog -->
    <t-dialog
      v-model:visible="errorDialogVisible"
      header="错误详情"
      :footer="false"
      width="500px"
    >
      <pre style="white-space: pre-wrap; word-break: break-all; font-size: 13px; background: var(--td-bg-color-page); padding: 12px; border-radius: 6px">{{ errorContent }}</pre>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { getPublishRecords, getPublishStats } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const records = ref<any[]>([]);

const filterArticleId = ref<string>('');
const filterAction = ref<string | undefined>();
const filterStatus = ref<string | undefined>();

const stats = ref({
  total: 0,
  success: 0,
  failed: 0,
  publishes: 0,
  syncs: 0,
});

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
});

const errorDialogVisible = ref(false);
const errorContent = ref('');

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'article_id', title: '文章 ID', width: 80 },
  { colKey: 'action', title: '类型', width: 80 },
  { colKey: 'recordStatus', title: '状态', width: 80 },
  { colKey: 'operator', title: '操作人', width: 180, ellipsis: true },
  { colKey: 'wechat_media_id', title: 'Media ID', ellipsis: true },
  {
    colKey: 'created_at',
    title: '时间',
    width: 180,
    cell: (_h: any, { row }: any) => row.created_at ? new Date(row.created_at).toLocaleString() : '-',
  },
  { colKey: 'op', title: '操作', width: 100 },
];

const fetchRecords = async () => {
  loading.value = true;
  try {
    const params: any = {
      limit: pagination.value.pageSize,
      offset: (pagination.value.current - 1) * pagination.value.pageSize,
    };
    if (filterArticleId.value) {
      params.article_id = Number(filterArticleId.value);
    }
    if (filterAction.value) {
      params.action = filterAction.value;
    }
    if (filterStatus.value) {
      params.status = filterStatus.value;
    }
    const res = await getPublishRecords(params);
    records.value = res.data;
    // Update total count for pagination (approximation since API returns array)
    pagination.value.total = res.data.length < pagination.value.pageSize
      ? (pagination.value.current - 1) * pagination.value.pageSize + res.data.length
      : (pagination.value.current + 1) * pagination.value.pageSize;
  } catch {
    MessagePlugin.error('加载发布记录失败');
  } finally {
    loading.value = false;
  }
};

const fetchStats = async () => {
  try {
    const res = await getPublishStats();
    stats.value = res.data;
    pagination.value.total = res.data.total || 0;
  } catch {
    // ignore
  }
};

const onPageChange = (pageInfo: any) => {
  pagination.value.current = pageInfo.current;
  pagination.value.pageSize = pageInfo.pageSize;
  fetchRecords();
};

const onReset = () => {
  filterArticleId.value = '';
  filterAction.value = undefined;
  filterStatus.value = undefined;
  pagination.value.current = 1;
  fetchRecords();
  fetchStats();
};

const showError = (row: any) => {
  errorContent.value = row.error_message || 'No error message';
  errorDialogVisible.value = true;
};

onMounted(() => {
  fetchRecords();
  fetchStats();
});
</script>
