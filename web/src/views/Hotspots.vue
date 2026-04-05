<template>
  <div>
    <t-card :bordered="true" style="margin-bottom: 16px">
      <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end">
        <t-input v-model="filters.keyword" placeholder="搜索热点标题/摘要" style="width: 260px" />
        <t-select v-model="filters.platform" placeholder="筛选平台" clearable style="width: 180px">
          <t-option v-for="platform in platforms" :key="platform" :label="platform" :value="platform" />
        </t-select>
        <t-input v-model="filters.tag" placeholder="标签筛选，如 AI" style="width: 180px" />
        <t-button theme="primary" @click="fetchHotspots">查询</t-button>
        <t-button variant="outline" @click="resetFilters">重置</t-button>
        <t-button variant="outline" :loading="exporting" @click="downloadExport">导出 CSV</t-button>
      </div>
    </t-card>

    <div style="display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap">
      <t-card v-for="card in summaryCards" :key="card.label" style="min-width: 180px; flex: 1" :bordered="true">
        <div style="font-size: 12px; color: var(--td-text-color-secondary)">{{ card.label }}</div>
        <div style="font-size: 28px; font-weight: 700; color: var(--td-brand-color); margin-top: 8px">{{ card.value }}</div>
      </t-card>
    </div>

    <t-table :data="hotspots" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #title="{ row }">
        <div>
          <div style="font-weight: 600">{{ row.title }}</div>
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">{{ row.summary || '暂无摘要' }}</div>
        </div>
      </template>
      <template #platform="{ row }">
        <t-tag theme="primary" variant="light">{{ getHotspotPlatform(row) }}</t-tag>
      </template>
      <template #tags="{ row }">
        <t-space size="4px">
          <t-tag v-for="tag in (row.tags || []).slice(0, 3)" :key="tag" size="small" variant="outline">{{ normalizeTag(tag) }}</t-tag>
        </t-space>
      </template>
      <template #quality_score="{ row }">
        <span>{{ row.quality_score != null ? (row.quality_score * 100).toFixed(0) : '-' }}</span>
      </template>
      <template #created_at="{ row }">{{ formatDateTime(row.created_at) }}</template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openTrend(row)">趋势</t-link>
          <t-link theme="primary" @click="openCreateDialog(row)">一键创作</t-link>
          <a v-if="row.original_url" :href="row.original_url" target="_blank" style="font-size: 12px">原文</a>
        </t-space>
      </template>
    </t-table>

    <TrendDialog v-model:visible="trendVisible" :points="currentTrend" />

    <CreateArticleDialog
      v-model:visible="createVisible"
      :hotspot="selectedHotspot"
      :agents="agents"
      :style-presets="stylePresets"
      :prompts="prompts"
      :loading="creating"
      @submit="createArticle"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { createArticleFromHotspot, exportHotspots, getAgents, getHotspotTrend, getHotspots, getPromptTemplates, getStylePresets } from '@/api';
import CreateArticleDialog from '@/components/CreateArticleDialog.vue';
import TrendDialog from '@/components/TrendDialog.vue';
import { formatDateTime } from '@/utils/format';
import { getHotspotPlatform, normalizeTag } from '@/utils/hotspot';

const router = useRouter();
const loading = ref(false);
const exporting = ref(false);
const creating = ref(false);
const hotspots = ref<any[]>([]);
const hotspotTotal = ref(0);
const agents = ref<any[]>([]);
const stylePresets = ref<any[]>([]);
const prompts = ref<any[]>([]);
const trendVisible = ref(false);
const currentTrend = ref<any[]>([]);
const createVisible = ref(false);
const selectedHotspot = ref<any>(null);

const filters = reactive({
  keyword: '',
  platform: undefined as string | undefined,
  tag: '',
});

const columns = [
  { colKey: 'title', title: '热点标题' },
  { colKey: 'platform', title: '平台', width: 120 },
  { colKey: 'tags', title: '标签', width: 220 },
  { colKey: 'quality_score', title: '热度分', width: 100 },
  { colKey: 'created_at', title: '时间', width: 180 },
  { colKey: 'op', title: '操作', width: 180 },
];

const platforms = computed(() => {
  const values = new Set<string>();
  hotspots.value.forEach((item) => {
    const platform = getHotspotPlatform(item);
    if (platform && platform !== '未知') values.add(platform);
  });
  return Array.from(values);
});

const summaryCards = computed(() => {
  const total = hotspotTotal.value;
  const avgScore = hotspots.value.length ? (hotspots.value.reduce((sum, item) => sum + (item.quality_score || 0), 0) / hotspots.value.length) : 0;
  const platformCount = new Set(hotspots.value.map((item) => getHotspotPlatform(item))).size;
  return [
    { label: '热点总数', value: total },
    { label: '覆盖平台', value: platformCount },
    { label: '平均热度', value: `${(avgScore * 100).toFixed(0)}` },
  ];
});

const fetchHotspots = async () => {
  loading.value = true;
  try {
    const res = await getHotspots({
      keyword: filters.keyword || undefined,
      platform: filters.platform,
      tag: filters.tag || undefined,
      limit: 200,
      offset: 0,
    });
    hotspots.value = res.data?.items || [];
    hotspotTotal.value = res.data?.total || 0;
  } catch {
    hotspots.value = [];
    hotspotTotal.value = 0;
    MessagePlugin.error('加载热点失败');
  } finally {
    loading.value = false;
  }
};

const resetFilters = () => {
  filters.keyword = '';
  filters.platform = undefined;
  filters.tag = '';
  fetchHotspots();
};

const downloadExport = async () => {
  exporting.value = true;
  try {
    const res = await exportHotspots({
      keyword: filters.keyword || undefined,
      platform: filters.platform,
      tag: filters.tag || undefined,
      limit: 500,
    });
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'hotspots.csv';
    link.click();
    window.URL.revokeObjectURL(url);
  } catch {
    MessagePlugin.error('导出失败');
  } finally {
    exporting.value = false;
  }
};

const openTrend = async (row: any) => {
  try {
    const res = await getHotspotTrend(row.id);
    currentTrend.value = res.data.points || [];
    trendVisible.value = true;
  } catch {
    MessagePlugin.error('加载趋势失败');
  }
};

const openCreateDialog = (row: any) => {
  selectedHotspot.value = row;
  createVisible.value = true;
};

const createArticle = async (payload: { agent_id?: number; style_id?: string; prompt_template_id?: number }) => {
  if (!selectedHotspot.value || !payload.agent_id) {
    MessagePlugin.warning('请选择 Agent');
    return;
  }
  creating.value = true;
  try {
    const res = await createArticleFromHotspot(selectedHotspot.value.id, {
      agent_id: payload.agent_id,
      style_id: payload.style_id,
      prompt_template_id: payload.prompt_template_id,
    });
    MessagePlugin.success(`已生成文章草稿：${res.data.title}`);
    createVisible.value = false;
    router.push('/articles');
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '生成失败');
  } finally {
    creating.value = false;
  }
};

onMounted(async () => {
  await Promise.all([
    fetchHotspots(),
    getAgents().then((res) => { agents.value = res.data || []; }).catch(() => {}),
    getStylePresets().then((res) => { stylePresets.value = res.data || []; }).catch(() => {}),
    getPromptTemplates().then((res) => { prompts.value = res.data || []; }).catch(() => {}),
  ]);
});
</script>
