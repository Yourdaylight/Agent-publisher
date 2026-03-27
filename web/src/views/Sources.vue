<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <div>
        <h3 style="margin: 0 0 8px 0">数据源管理</h3>
        <p style="margin: 0; color: var(--td-text-color-secondary); font-size: 13px">
          管理热榜平台、RSS 订阅源以及 Agent 数据源绑定关系。
        </p>
      </div>
    </div>

    <!-- Stats Cards -->
    <div style="display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap">
      <t-card :bordered="true" style="flex: 1; min-width: 150px; padding: 16px">
        <div style="text-align: center">
          <div style="font-size: 24px; font-weight: 600; color: var(--td-brand-color)">{{ allSources.length }}</div>
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">总数据源</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px; padding: 16px">
        <div style="text-align: center">
          <div style="font-size: 24px; font-weight: 600; color: var(--td-success-color)">{{ enabledCount }}</div>
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">启用中</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px; padding: 16px">
        <div style="text-align: center">
          <div style="font-size: 24px; font-weight: 600; color: var(--td-warning-color)">{{ rssCount }}</div>
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">RSS 源</div>
        </div>
      </t-card>
      <t-card :bordered="true" style="flex: 1; min-width: 150px; padding: 16px">
        <div style="text-align: center">
          <div style="font-size: 24px; font-weight: 600; color: var(--td-error-color)">{{ trendingCount }}</div>
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">热榜平台</div>
        </div>
      </t-card>
    </div>

    <!-- Three-tab navigation -->
    <t-tabs v-model="activeTab" @change="onTabChange" style="margin-bottom: 16px">
      <t-tab-panel value="trending" label="🔥 热榜平台" />
      <t-tab-panel value="rss" label="📡 RSS 订阅" />
      <t-tab-panel value="binding" label="🔗 Agent 绑定" />
    </t-tabs>

    <!-- ========== Tab 1: 热榜平台 ========== -->
    <div v-if="activeTab === 'trending'">
      <t-loading :loading="loading">
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px">
          <t-card
            v-for="item in trendingSources"
            :key="item.id"
            :bordered="true"
            :style="{
              borderLeft: item.is_enabled ? '4px solid var(--td-brand-color)' : '4px solid var(--td-component-stroke)',
              transition: 'all 0.2s ease',
            }"
            hover-shadow
          >
            <div style="display: flex; justify-content: space-between; align-items: center">
              <div>
                <div style="font-size: 15px; font-weight: 500">{{ item.display_name || item.source_key }}</div>
                <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">
                  <t-tag size="small" variant="light" theme="warning">热榜</t-tag>
                  <span style="margin-left: 8px">{{ item.source_key }}</span>
                </div>
              </div>
              <t-switch
                :value="item.is_enabled"
                @change="(val: boolean) => onToggleSource(item, val)"
                :loading="togglingIds.has(item.id)"
              />
            </div>
          </t-card>
        </div>
        <t-empty v-if="!loading && trendingSources.length === 0" description="暂无热榜平台数据" style="margin-top: 40px" />
      </t-loading>
    </div>

    <!-- ========== Tab 2: RSS 订阅 ========== -->
    <div v-if="activeTab === 'rss'">
      <div style="display: flex; justify-content: flex-end; margin-bottom: 12px">
        <t-button theme="primary" @click="openRssDialog()">
          <template #icon><t-icon name="add" /></template>
          添加 RSS
        </t-button>
      </div>
      <t-table :data="rssSources" :columns="rssColumns" row-key="id" :loading="loading" stripe>
        <template #display_name="{ row }">
          <span style="font-weight: 500">{{ row.display_name || row.source_key }}</span>
        </template>
        <template #source_key="{ row }">
          <t-link :href="row.source_key" target="_blank" theme="primary" style="font-size: 12px; word-break: break-all">
            {{ row.source_key }}
          </t-link>
        </template>
        <template #is_enabled="{ row }">
          <t-switch
            :value="row.is_enabled"
            @change="(val: boolean) => onToggleSource(row, val)"
            :loading="togglingIds.has(row.id)"
            size="small"
          />
        </template>
        <template #collect_cron="{ row }">
          <span v-if="row.collect_cron" style="font-family: monospace; font-size: 12px">{{ row.collect_cron }}</span>
          <span v-else style="color: var(--td-text-color-placeholder)">-</span>
        </template>
        <template #created_at="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
        <template #op="{ row }">
          <t-space>
            <t-link theme="primary" @click="openRssDialog(row)">编辑</t-link>
            <t-popconfirm content="确定删除此 RSS 源？" @confirm="onDeleteSource(row.id)">
              <t-link theme="danger">删除</t-link>
            </t-popconfirm>
          </t-space>
        </template>
      </t-table>
      <t-empty v-if="!loading && rssSources.length === 0" description="暂无 RSS 订阅源" style="margin-top: 40px" />
    </div>

    <!-- ========== Tab 3: Agent 绑定 ========== -->
    <div v-if="activeTab === 'binding'">
      <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 16px">
        <div style="min-width: 240px">
          <t-select
            v-model="selectedAgentId"
            placeholder="请选择 Agent"
            clearable
            @change="onAgentChange"
          >
            <t-option v-for="a in agents" :key="a.id" :value="a.id" :label="a.name" />
          </t-select>
        </div>
        <t-button
          v-if="selectedAgentId"
          theme="primary"
          @click="showBindDialog = true"
        >
          <template #icon><t-icon name="add" /></template>
          添加绑定
        </t-button>
      </div>

      <t-table
        v-if="selectedAgentId"
        :data="agentBindings"
        :columns="bindingColumns"
        row-key="id"
        :loading="bindingLoading"
        stripe
      >
        <template #source_type="{ row }">
          <t-tag
            :theme="row.source?.source_type === 'rss' ? 'primary' : row.source?.source_type === 'trending' ? 'warning' : 'default'"
            variant="light"
            size="small"
          >
            {{ sourceTypeLabel(row.source?.source_type) }}
          </t-tag>
        </template>
        <template #is_enabled="{ row }">
          <t-tag :theme="row.source?.is_enabled ? 'success' : 'default'" variant="light" size="small">
            {{ row.source?.is_enabled ? '启用' : '停用' }}
          </t-tag>
        </template>
        <template #op="{ row }">
          <t-popconfirm content="确定解除绑定？" @confirm="onUnbind(row)">
            <t-link theme="danger">解绑</t-link>
          </t-popconfirm>
        </template>
      </t-table>
      <t-empty v-if="selectedAgentId && !bindingLoading && agentBindings.length === 0" description="该 Agent 暂无绑定的数据源" style="margin-top: 40px" />
      <t-empty v-if="!selectedAgentId" description="请先选择一个 Agent" style="margin-top: 40px" />
    </div>

    <!-- ========== RSS 编辑弹窗 ========== -->
    <t-dialog
      v-model:visible="rssDialogVisible"
      :header="editingRss ? '编辑 RSS 源' : '添加 RSS 源'"
      width="560px"
      :confirm-btn="{ content: '保存', loading: rssSubmitting }"
      @confirm="onRssSubmit"
    >
      <t-form :data="rssForm" layout="vertical" style="margin-top: 16px">
        <t-form-item label="名称" name="display_name">
          <t-input v-model="rssForm.display_name" placeholder="例如：36氪 RSS" />
        </t-form-item>
        <t-form-item label="RSS URL" name="source_key" required-mark>
          <div style="display: flex; gap: 8px; width: 100%">
            <t-input v-model="rssForm.source_key" placeholder="https://example.com/feed.xml" style="flex: 1" />
            <t-button theme="default" :loading="rssTestLoading" @click="onTestRss">测试</t-button>
          </div>
        </t-form-item>
        <div v-if="rssTestResult" style="margin: -8px 0 12px; padding: 8px 12px; background: var(--td-bg-color-container-hover); border-radius: 6px; font-size: 13px">
          <div v-if="rssTestResult.success" style="color: var(--td-success-color)">
            <t-icon name="check-circle" style="margin-right: 4px" />
            测试成功！获取到 {{ rssTestResult.count }} 条内容
          </div>
          <div v-else style="color: var(--td-error-color)">
            <t-icon name="close-circle" style="margin-right: 4px" />
            测试失败：{{ rssTestResult.message }}
          </div>
          <div v-if="rssTestResult.titles && rssTestResult.titles.length > 0" style="margin-top: 6px; color: var(--td-text-color-secondary)">
            <div v-for="(title, i) in rssTestResult.titles.slice(0, 3)" :key="i" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
              {{ i + 1 }}. {{ title }}
            </div>
          </div>
        </div>
        <t-form-item label="采集频率 (Cron)" name="collect_cron">
          <t-input v-model="rssForm.collect_cron" placeholder="例如：0 */6 * * *（每6小时）" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- ========== Agent 绑定弹窗 ========== -->
    <t-dialog
      v-model:visible="showBindDialog"
      header="添加数据源绑定"
      width="560px"
      :confirm-btn="{ content: '绑定', loading: bindSubmitting }"
      @confirm="onBindSubmit"
    >
      <div style="margin-top: 16px">
        <p style="margin: 0 0 12px; color: var(--td-text-color-secondary); font-size: 13px">
          选择要绑定到当前 Agent 的数据源（已绑定的数据源不会显示）：
        </p>
        <t-checkbox-group v-model="selectedBindSourceIds" style="display: flex; flex-direction: column; gap: 8px">
          <t-checkbox
            v-for="s in unboundSources"
            :key="s.id"
            :value="s.id"
          >
            <span style="font-weight: 500">{{ s.display_name || s.source_key }}</span>
            <t-tag
              :theme="s.source_type === 'rss' ? 'primary' : s.source_type === 'trending' ? 'warning' : 'default'"
              variant="light"
              size="small"
              style="margin-left: 8px"
            >
              {{ sourceTypeLabel(s.source_type) }}
            </t-tag>
          </t-checkbox>
        </t-checkbox-group>
        <t-empty v-if="unboundSources.length === 0" description="所有数据源已绑定" style="margin-top: 16px" />
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import {
  getSources,
  createSource,
  updateSource,
  deleteSource,
  toggleSource,
  testRssUrl,
  getAgents,
  getAgentBindings,
  bindAgentSource,
  unbindAgentSource,
} from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

// ── State ──
const loading = ref(false);
const allSources = ref<any[]>([]);
const activeTab = ref('trending');
const togglingIds = ref<Set<number>>(new Set());

// Stats
const enabledCount = computed(() => allSources.value.filter(s => s.is_enabled).length);
const rssCount = computed(() => allSources.value.filter(s => s.source_type === 'rss').length);
const trendingCount = computed(() => allSources.value.filter(s => s.source_type === 'trending').length);

// Trending
const trendingSources = computed(() => allSources.value.filter(s => s.source_type === 'trending'));

// RSS
const rssSources = computed(() => allSources.value.filter(s => s.source_type === 'rss'));
const rssDialogVisible = ref(false);
const editingRss = ref<any>(null);
const rssSubmitting = ref(false);
const rssTestLoading = ref(false);
const rssTestResult = ref<any>(null);
const rssForm = ref({
  display_name: '',
  source_key: '',
  collect_cron: '',
});

const rssColumns = [
  { colKey: 'display_name', title: '名称', width: 160 },
  { colKey: 'source_key', title: 'URL', ellipsis: true },
  { colKey: 'is_enabled', title: '状态', width: 80 },
  { colKey: 'collect_cron', title: '采集频率', width: 140 },
  { colKey: 'created_at', title: '创建时间', width: 160 },
  { colKey: 'op', title: '操作', width: 120 },
];

// Agent 绑定
const agents = ref<any[]>([]);
const selectedAgentId = ref<number | null>(null);
const agentBindings = ref<any[]>([]);
const bindingLoading = ref(false);
const showBindDialog = ref(false);
const bindSubmitting = ref(false);
const selectedBindSourceIds = ref<number[]>([]);

const bindingColumns = [
  { colKey: 'source.display_name', title: '数据源名称', cell: (_h: any, { row }: any) => row.source?.display_name || row.source?.source_key || '-' },
  { colKey: 'source_type', title: '类型', width: 100 },
  { colKey: 'is_enabled', title: '状态', width: 80 },
  { colKey: 'filter_keywords', title: '过滤关键词', cell: (_h: any, { row }: any) => row.filter_keywords || '-' },
  { colKey: 'op', title: '操作', width: 80 },
];

const unboundSources = computed(() => {
  const boundIds = new Set(agentBindings.value.map((b: any) => b.source_id || b.source?.id));
  return allSources.value.filter(s => !boundIds.has(s.id));
});

// ── Helpers ──
const sourceTypeLabel = (type: string) => {
  const map: Record<string, string> = { rss: 'RSS', trending: '热榜', search: '搜索' };
  return map[type] || type || '-';
};

const formatTime = (str: string) => {
  if (!str) return '-';
  try {
    return new Date(str).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return str;
  }
};

// ── Data Fetching ──
const fetchSources = async () => {
  loading.value = true;
  try {
    const res = await getSources();
    allSources.value = res.data;
  } catch {
    MessagePlugin.error('加载数据源列表失败');
  } finally {
    loading.value = false;
  }
};

const fetchAgents = async () => {
  try {
    const res = await getAgents();
    agents.value = res.data;
  } catch {}
};

const fetchBindings = async () => {
  if (!selectedAgentId.value) {
    agentBindings.value = [];
    return;
  }
  bindingLoading.value = true;
  try {
    const res = await getAgentBindings(selectedAgentId.value);
    agentBindings.value = res.data;
  } catch {
    MessagePlugin.error('加载绑定列表失败');
  } finally {
    bindingLoading.value = false;
  }
};

// ── Event Handlers ──
const onTabChange = () => {
  // Refresh data when switching tabs
};

const onToggleSource = async (item: any, val: boolean) => {
  togglingIds.value.add(item.id);
  try {
    await toggleSource(item.id, val);
    item.is_enabled = val;
    MessagePlugin.success(val ? '已启用' : '已停用');
  } catch {
    MessagePlugin.error('操作失败');
  } finally {
    togglingIds.value.delete(item.id);
  }
};

// RSS CRUD
const openRssDialog = (rss?: any) => {
  editingRss.value = rss || null;
  rssTestResult.value = null;
  if (rss) {
    rssForm.value = {
      display_name: rss.display_name || '',
      source_key: rss.source_key || '',
      collect_cron: rss.collect_cron || '',
    };
  } else {
    rssForm.value = { display_name: '', source_key: '', collect_cron: '' };
  }
  rssDialogVisible.value = true;
};

const onTestRss = async () => {
  if (!rssForm.value.source_key) {
    MessagePlugin.warning('请先输入 RSS URL');
    return;
  }
  rssTestLoading.value = true;
  rssTestResult.value = null;
  try {
    const res = await testRssUrl(rssForm.value.source_key);
    rssTestResult.value = {
      success: true,
      count: res.data?.count ?? res.data?.items?.length ?? 0,
      titles: res.data?.titles || res.data?.items?.map((i: any) => i.title) || [],
    };
  } catch (err: any) {
    rssTestResult.value = {
      success: false,
      message: err?.response?.data?.detail || err?.message || '测试失败',
    };
  } finally {
    rssTestLoading.value = false;
  }
};

const onRssSubmit = async () => {
  if (!rssForm.value.source_key) {
    MessagePlugin.warning('RSS URL 不能为空');
    return;
  }
  rssSubmitting.value = true;
  try {
    const payload = {
      source_type: 'rss',
      source_key: rssForm.value.source_key,
      display_name: rssForm.value.display_name || undefined,
      collect_cron: rssForm.value.collect_cron || undefined,
      is_enabled: true,
    };
    if (editingRss.value) {
      await updateSource(editingRss.value.id, payload);
      MessagePlugin.success('更新成功');
    } else {
      await createSource(payload);
      MessagePlugin.success('创建成功');
    }
    rssDialogVisible.value = false;
    fetchSources();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '操作失败');
  } finally {
    rssSubmitting.value = false;
  }
};

const onDeleteSource = async (id: number) => {
  try {
    await deleteSource(id);
    MessagePlugin.success('删除成功');
    fetchSources();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '删除失败');
  }
};

// Agent 绑定
const onAgentChange = () => {
  fetchBindings();
};

const onUnbind = async (row: any) => {
  if (!selectedAgentId.value) return;
  const sourceId = row.source_id || row.source?.id;
  try {
    await unbindAgentSource(selectedAgentId.value, sourceId);
    MessagePlugin.success('解绑成功');
    fetchBindings();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '解绑失败');
  }
};

const onBindSubmit = async () => {
  if (!selectedAgentId.value || selectedBindSourceIds.value.length === 0) {
    MessagePlugin.warning('请至少选择一个数据源');
    return;
  }
  bindSubmitting.value = true;
  try {
    for (const sourceId of selectedBindSourceIds.value) {
      await bindAgentSource(selectedAgentId.value, { source_id: sourceId });
    }
    MessagePlugin.success(`成功绑定 ${selectedBindSourceIds.value.length} 个数据源`);
    showBindDialog.value = false;
    selectedBindSourceIds.value = [];
    fetchBindings();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '绑定失败');
  } finally {
    bindSubmitting.value = false;
  }
};

// ── Init ──
onMounted(() => {
  fetchSources();
  fetchAgents();
});
</script>
