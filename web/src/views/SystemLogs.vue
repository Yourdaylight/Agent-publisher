<template>
  <div>
    <!-- Stats cards -->
    <div style="display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap">
      <t-card :bordered="true" style="flex: 1; min-width: 150px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-brand-color)">{{ stats.total }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">总日志数</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-brand-color)">{{ stats.today }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">今日操作</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px">
        <div style="text-align: center">
          <div style="font-size: 28px; font-weight: 600; color: var(--td-error-color)">{{ stats.failed }}</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px">失败记录</div>
        </div>
      </t-card>
      <t-card v-for="(count, act) in (stats.by_action as Record<string, number>)" :key="act" :bordered="true" style="flex: 1; min-width: 120px">
        <div style="text-align: center">
          <div style="font-size: 22px; font-weight: 600; color: var(--td-warning-color)">{{ count }}</div>
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">{{ actionLabel(act) }}</div>
        </div>
      </t-card>
    </div>

    <!-- Filters -->
    <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center">
      <t-select v-model="filterAction" placeholder="操作类型" clearable style="width: 140px" @change="fetchData">
        <t-option v-for="a in actionOptions" :key="a.value" :label="a.label" :value="a.value" />
      </t-select>
      <t-select v-model="filterTargetType" placeholder="目标类型" clearable style="width: 140px" @change="fetchData">
        <t-option v-for="t in targetTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
      </t-select>
      <t-select v-model="filterStatus" placeholder="状态" clearable style="width: 120px" @change="fetchData">
        <t-option label="成功" value="success" />
        <t-option label="失败" value="failed" />
      </t-select>
      <t-input
        v-model="filterKeyword"
        placeholder="搜索描述/错误信息"
        clearable
        style="width: 200px"
        @change="fetchData"
      />
      <t-button theme="default" variant="outline" @click="onReset">重置</t-button>
      <div style="flex: 1" />
      <t-popconfirm content="确认清理？将删除超过指定天数的日志" @confirm="onCleanup">
        <t-button theme="danger" variant="outline" size="small">清理旧日志</t-button>
      </t-popconfirm>
    </div>

    <!-- Table -->
    <t-table
      :data="logs"
      :columns="columns"
      row-key="id"
      :loading="loading"
      stripe
      :pagination="pagination"
      @page-change="onPageChange"
    >
      <template #logAction="{ row }">
        <t-tag :theme="actionTheme(row.action)" variant="light" size="small">
          {{ actionLabel(row.action) }}
        </t-tag>
      </template>
      <template #logTarget="{ row }">
        <span v-if="row.target_type">
          <t-tag theme="default" variant="light" size="small">{{ targetTypeLabel(row.target_type) }}</t-tag>
          <span style="margin-left: 4px; font-size: 12px; color: var(--td-text-color-secondary)">#{{ row.target_id }}</span>
        </span>
        <span v-else style="color: var(--td-text-color-placeholder)">—</span>
      </template>
      <template #logStatus="{ row }">
        <t-tag :theme="row.status === 'success' ? 'success' : 'danger'" variant="light" size="small">
          {{ row.status === 'success' ? '成功' : '失败' }}
        </t-tag>
      </template>
      <template #logOperator="{ row }">
        <span style="font-size: 12px">
          {{ row.operator || '系统' }}
          <t-tag v-if="row.is_admin" size="small" theme="primary" variant="light" style="margin-left: 4px">管理员</t-tag>
        </span>
      </template>
      <template #logTime="{ row }">
        <span style="font-size: 12px">{{ formatTime(row.timestamp) }}</span>
      </template>
      <template #op="{ row }">
        <t-link v-if="row.error_message || row.extra" theme="primary" @click="showDetail(row)">详情</t-link>
      </template>
    </t-table>

    <!-- Detail dialog -->
    <t-dialog
      v-model:visible="detailVisible"
      header="日志详情"
      :footer="false"
      width="560px"
    >
      <t-descriptions v-if="detailLog" :column="1" bordered>
        <t-descriptions-item label="时间">{{ formatTime(detailLog.timestamp) }}</t-descriptions-item>
        <t-descriptions-item label="操作">{{ actionLabel(detailLog.action) }}</t-descriptions-item>
        <t-descriptions-item label="目标">{{ detailLog.target_type ? `${targetTypeLabel(detailLog.target_type)} #${detailLog.target_id}` : '—' }}</t-descriptions-item>
        <t-descriptions-item label="描述">{{ detailLog.description || '—' }}</t-descriptions-item>
        <t-descriptions-item label="操作人">{{ detailLog.operator || '系统' }}</t-descriptions-item>
        <t-descriptions-item label="状态">
          <t-tag :theme="detailLog.status === 'success' ? 'success' : 'danger'" variant="light">
            {{ detailLog.status === 'success' ? '成功' : '失败' }}
          </t-tag>
        </t-descriptions-item>
        <t-descriptions-item label="IP">{{ detailLog.client_ip || '—' }}</t-descriptions-item>
        <t-descriptions-item label="请求路径">{{ detailLog.request_path || '—' }}</t-descriptions-item>
      </t-descriptions>
      <div v-if="detailLog?.error_message" style="margin-top: 16px">
        <div style="font-weight: 600; margin-bottom: 8px; color: var(--td-error-color)">错误信息</div>
        <pre style="white-space: pre-wrap; word-break: break-all; font-size: 12px; background: var(--td-bg-color-page); padding: 12px; border-radius: 6px; max-height: 200px; overflow-y: auto">{{ detailLog.error_message }}</pre>
      </div>
      <div v-if="detailLog?.extra" style="margin-top: 16px">
        <div style="font-weight: 600; margin-bottom: 8px">附加信息</div>
        <pre style="white-space: pre-wrap; word-break: break-all; font-size: 12px; background: var(--td-bg-color-page); padding: 12px; border-radius: 6px; max-height: 200px; overflow-y: auto">{{ formatExtra(detailLog.extra) }}</pre>
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { getSystemLogs, getSystemLogStats, cleanupSystemLogs } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const logs = ref<any[]>([]);

const filterAction = ref<string | undefined>();
const filterTargetType = ref<string | undefined>();
const filterStatus = ref<string | undefined>();
const filterKeyword = ref('');

const stats = ref<any>({ total: 0, today: 0, failed: 0, by_action: {} });
const pagination = ref({ current: 1, pageSize: 30, total: 0 });

const detailVisible = ref(false);
const detailLog = ref<any>(null);

const actionOptions = [
  { label: '登录', value: 'login' },
  { label: '发布', value: 'publish' },
  { label: '同步', value: 'sync' },
  { label: '创建', value: 'create' },
  { label: '更新', value: 'update' },
  { label: '删除', value: 'delete' },
  { label: '生成', value: 'generate' },
  { label: '扫码授权', value: 'auth_scan' },
  { label: '错误', value: 'error' },
  { label: '系统', value: 'system' },
];

const targetTypeOptions = [
  { label: '公众号', value: 'account' },
  { label: 'Agent', value: 'agent' },
  { label: '文章', value: 'article' },
  { label: '数据源', value: 'source' },
  { label: '任务', value: 'task' },
  { label: '配置', value: 'settings' },
  { label: '素材', value: 'material' },
  { label: '素材', value: 'media' },
  { label: '发布记录', value: 'publish_record' },
];

const actionLabelMap: Record<string, string> = {
  login: '登录', publish: '发布', sync: '同步', create: '创建',
  update: '更新', delete: '删除', generate: '生成', auth_scan: '扫码授权',
  error: '错误', system: '系统', refresh: '刷新', collect: '采集',
};
const actionLabel = (a: string) => actionLabelMap[a] || a;

const actionThemeMap: Record<string, string> = {
  login: 'primary', publish: 'success', sync: 'warning', create: 'primary',
  update: 'default', delete: 'danger', generate: 'primary', auth_scan: 'primary',
  error: 'danger', system: 'default', refresh: 'warning', collect: 'default',
};
const actionTheme = (a: string) => actionThemeMap[a] || 'default';

const targetTypeLabelMap: Record<string, string> = {
  account: '公众号', agent: 'Agent', article: '文章', source: '数据源',
  task: '任务', settings: '配置', material: '素材', media: '素材',
  publish_record: '发布记录', platform: '平台',
};
const targetTypeLabel = (t: string) => targetTypeLabelMap[t] || t;

const formatTime = (ts: string) => ts ? new Date(ts).toLocaleString() : '—';
const formatExtra = (extra: string) => {
  if (!extra) return '';
  try { return JSON.stringify(JSON.parse(extra), null, 2); } catch { return extra; }
};

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'logAction', title: '操作', width: 100 },
  { colKey: 'logTarget', title: '目标', width: 160 },
  { colKey: 'description', title: '描述', ellipsis: true },
  { colKey: 'logOperator', title: '操作人', width: 160 },
  { colKey: 'logStatus', title: '状态', width: 70 },
  { colKey: 'logTime', title: '时间', width: 170 },
  { colKey: 'op', title: '', width: 60 },
];

const fetchData = async () => {
  loading.value = true;
  try {
    const params: any = {
      limit: pagination.value.pageSize,
      offset: (pagination.value.current - 1) * pagination.value.pageSize,
    };
    if (filterAction.value) params.action = filterAction.value;
    if (filterTargetType.value) params.target_type = filterTargetType.value;
    if (filterStatus.value) params.status = filterStatus.value;
    if (filterKeyword.value) params.keyword = filterKeyword.value;
    const res = await getSystemLogs(params);
    logs.value = res.data;
    pagination.value.total = res.data.length < pagination.value.pageSize
      ? (pagination.value.current - 1) * pagination.value.pageSize + res.data.length
      : (pagination.value.current + 1) * pagination.value.pageSize;
  } catch {
    MessagePlugin.error('加载日志失败');
  } finally {
    loading.value = false;
  }
};

const fetchStats = async () => {
  try {
    const res = await getSystemLogStats();
    stats.value = res.data;
  } catch { /* ignore */ }
};

const onPageChange = (pageInfo: any) => {
  pagination.value.current = pageInfo.current;
  pagination.value.pageSize = pageInfo.pageSize;
  fetchData();
};

const onReset = () => {
  filterAction.value = undefined;
  filterTargetType.value = undefined;
  filterStatus.value = undefined;
  filterKeyword.value = '';
  pagination.value.current = 1;
  fetchData();
};

const showDetail = (row: any) => {
  detailLog.value = row;
  detailVisible.value = true;
};

const onCleanup = async () => {
  try {
    const res = await cleanupSystemLogs(90);
    MessagePlugin.success(res.data.message || '清理完成');
    fetchStats();
    fetchData();
  } catch {
    MessagePlugin.error('清理失败');
  }
};

onMounted(() => {
  fetchData();
  fetchStats();
});
</script>
