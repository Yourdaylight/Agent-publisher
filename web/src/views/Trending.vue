<template>
  <div class="trending-page">
    <aside class="trending-sidebar">
      <div class="sidebar-panel page-meta-panel">
        <div class="page-kicker">发现热点</div>
        <div class="page-title">实时追踪全网热点，AI 一键创作</div>
      </div>

      <!-- 我的偏好 -->
      <div class="sidebar-panel preference-panel">
        <div class="panel-head">
          <div class="panel-label" style="margin-bottom:0">我的偏好</div>
          <t-link v-if="hasPreference" theme="danger" @click="clearPreference">清除</t-link>
        </div>
        <div class="pref-section">
          <div class="pref-hint">关注话题</div>
          <div class="pref-tags">
            <t-tag
              v-for="kw in preference.interest_keywords"
              :key="kw"
              size="small"
              theme="primary"
              variant="light"
              closable
              @close="removeInterestKeyword(kw)"
            >{{ kw }}</t-tag>
            <t-input
              v-model="newKeyword"
              size="small"
              placeholder="+ 添加"
              style="width: 80px"
              @enter="addInterestKeyword"
            />
          </div>
        </div>
        <div class="pref-section">
          <div class="pref-hint">常看平台</div>
          <div class="chip-row">
            <button
              v-for="platform in platformOptions"
              :key="'pref-' + platform.value"
              type="button"
              class="pref-chip"
              :class="{ active: preference.preferred_platforms.includes(platform.value) }"
              @click="togglePreferredPlatform(platform.value)"
            >{{ platform.label }}</button>
          </div>
        </div>
        <t-button size="small" theme="primary" block @click="applyPreferenceToFilters" :disabled="!hasPreference">应用偏好筛选</t-button>
      </div>

      <div class="sidebar-panel filter-panel">
        <div class="panel-label">搜索</div>
        <t-input v-model="filters.keyword" placeholder="搜索热点标题/摘要" clearable />
        <t-input v-model="filters.tag" placeholder="标签，如 AI" clearable style="margin-top: 10px" />

        <div class="section-block">
          <div class="panel-label">热度</div>
          <div class="chip-column compact">
            <button
              v-for="option in heatOptions"
              :key="option.value"
              type="button"
              class="filter-chip"
              :class="{ active: heatRange === option.value }"
              @click="heatRange = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <div class="section-block">
          <div class="panel-label">时间</div>
          <div class="chip-column compact">
            <button
              v-for="option in timeOptions"
              :key="option.value"
              type="button"
              class="filter-chip"
              :class="{ active: timeRange === option.value }"
              @click="timeRange = option.value; applyFilters()"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <div class="sidebar-actions">
          <t-button theme="primary" block @click="applyFilters">查询</t-button>
          <t-button variant="outline" block @click="resetFilters">重置</t-button>
        </div>
      </div>

      <div class="sidebar-panel cluster-panel">
        <div class="panel-head">
          <div class="panel-label">跨平台共振榜</div>
        </div>
        <div v-if="topClusters.length" class="cluster-list-mini">
          <button v-for="item in topClusters" :key="item.id" type="button" class="cluster-item-mini" @click="openQuickCreate(item)">
            <div class="cluster-title-mini">{{ item.title }}</div>
            <div class="cluster-meta-mini">
              <span>{{ getHotspotPlatform(item) }}</span>
              <span>跨 {{ item.metadata?.cross_platform_count || 1 }}</span>
              <span>{{ item.quality_score != null ? `${(item.quality_score * 100).toFixed(0)}` : '-' }}</span>
            </div>
          </button>
        </div>
        <div v-else class="empty-mini">暂无可展示的共振热点</div>
      </div>
    </aside>

    <main class="trending-main">
      <div class="stats-bar">
        <div class="stats-left">
          <span class="stats-pill">{{ pagination.total }} 条结果</span>
          <span class="stats-pill">跨平台 {{ crossPlatformCount }}</span>
          <span class="stats-pill">覆盖 {{ platformOptions.length }} 平台</span>
          <span class="stats-pill">更新 {{ latestUpdatedAt }}</span>
        </div>
        <div class="stats-right">
          <t-button size="small" variant="outline" :loading="exporting" @click="downloadExport">导出 CSV</t-button>
          <t-button v-if="isAdmin" size="small" theme="primary" :loading="refreshing" @click="refreshTrending">刷新热榜</t-button>
        </div>
      </div>

      <div class="main-shell">
        <div class="main-header">
          <div>
            <div class="main-title">热点榜单</div>
            <div class="main-subtitle">数据来源：TrendRadar 跨平台聚合引擎</div>
          </div>
        </div>

        <t-tabs :value="activePlatformTab" @change="handlePlatformTabChange" style="margin-bottom: 16px">
          <t-tab-panel value="all" :label="`全部 (${pagination.total})`" />
          <t-tab-panel
            v-for="platform in platformOptions"
            :key="platform.value"
            :value="platform.value"
            :label="`${platform.label} (${platform.count})`"
          />
        </t-tabs>

        <div v-if="hotspots.length" class="hotspot-grid" :style="{ opacity: loading ? 0.55 : 1 }">
          <article
            v-for="(item, index) in hotspots"
            :key="item.id"
            class="hotspot-card"
            :style="{ borderTopColor: qualityBarColor(item.quality_score) }"
          >
            <div class="hotspot-card-top">
              <div class="hotspot-meta-left">
                <t-tag size="small" theme="primary" variant="light">{{ getHotspotPlatform(item) }}</t-tag>
                <span class="rank-badge">#{{ pagination.offset + index + 1 }}</span>
                <span v-if="item.metadata?.cross_platform_count" class="cross-badge">跨 {{ item.metadata.cross_platform_count }}</span>
              </div>
              <span class="heat-badge" :style="{ color: qualityBarColor(item.quality_score) }">{{ heatLabel(item.quality_score) }}</span>
            </div>

            <div class="hotspot-title">{{ item.title || '无标题' }}</div>
            <div class="hotspot-summary">{{ item.summary || '暂无摘要' }}</div>

            <div class="hotspot-bar-row">
              <div class="hotspot-bar-track">
                <div class="hotspot-bar-fill" :style="{ width: `${Math.max((item.quality_score || 0) * 100, 4)}%`, background: qualityBarColor(item.quality_score) }" />
              </div>
              <span class="hotspot-score">{{ item.quality_score != null ? `${(item.quality_score * 100).toFixed(0)}` : '-' }}</span>
            </div>

            <div class="hotspot-extra">
              <span>{{ formatDateTime(item.created_at) }}</span>
              <span>{{ formatShortTime(item.created_at) }}</span>
            </div>

            <div class="hotspot-actions">
              <t-button size="small" theme="primary" @click.stop="openQuickCreate(item)">📝 一键创作</t-button>
              <t-button size="small" variant="outline" @click.stop="collectMaterial(item)">📋 收藏素材</t-button>
              <t-link theme="primary" @click="openTrend(item)">趋势</t-link>
              <a v-if="item.original_url" :href="item.original_url" target="_blank" rel="noreferrer" class="origin-link">原文 ↗</a>
            </div>
          </article>
        </div>

        <t-result v-else-if="!loading" status="404" title="没有找到符合条件的热点" description="换个平台、热度区间或时间范围试试。" />

        <div class="pagination-wrap">
          <t-pagination
            :current="pagination.page"
            :page-size="pagination.pageSize"
            :total="pagination.total"
            show-jumper
            :page-size-options="[12, 24, 48]"
            @current-change="onPageChange"
            @page-size-change="onPageSizeChange"
          />
        </div>
      </div>
    </main>

    <TrendDialog v-model:visible="trendVisible" :points="currentTrend" />

    <CreateArticleDialog
      v-model:visible="createVisible"
      :hotspot="selectedHotspotForCreate"
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
import { createArticleFromHotspot, createArticleFromHotspotAsync, exportHotspots, getAgents, getHotspotPlatforms, getHotspotTrend, getHotspots, getPromptTemplates, getStylePresets, getUserInfo, refreshAllTrending } from '@/api';
import CreateArticleDialog from '@/components/CreateArticleDialog.vue';
import TrendDialog from '@/components/TrendDialog.vue';
import { formatDateTime, formatShortTime } from '@/utils/format';
import { getHotspotPlatform, heatLabel, qualityBarColor } from '@/utils/hotspot';

const PREF_STORAGE_KEY = 'ap_user_preferences';

interface UserPreference {
  interest_keywords: string[];
  preferred_platforms: string[];
  blocked_keywords: string[];
}

const router = useRouter();
const loading = ref(false);
const refreshing = ref(false);
const exporting = ref(false);
const creating = ref(false);
const hotspots = ref<any[]>([]);
const agents = ref<any[]>([]);
const stylePresets = ref<any[]>([]);
const prompts = ref<any[]>([]);
const trendVisible = ref(false);
const createVisible = ref(false);
const currentTrend = ref<any[]>([]);
const selectedHotspotForCreate = ref<any>(null);
const activePlatformTab = ref('all');
const selectedPlatforms = ref<string[]>([]);
const heatRange = ref('all');
const timeRange = ref('3d');
const platformOptions = ref<Array<{ value: string; label: string; count: number }>>([]);
const newKeyword = ref('');

// User preference (localStorage + backend sync)
const preference = reactive<UserPreference>({
  interest_keywords: [],
  preferred_platforms: [],
  blocked_keywords: [],
});

const hasPreference = computed(() => preference.interest_keywords.length > 0 || preference.preferred_platforms.length > 0);

const filters = reactive({
  keyword: '',
  tag: '',
});

const pagination = reactive({
  page: 1,
  pageSize: 12,
  total: 0,
  offset: 0,
});

const isAdmin = computed(() => getUserInfo()?.is_admin ?? false);
const hasAgents = computed(() => agents.value.length > 0);
const crossPlatformCount = computed(() => hotspots.value.filter((item) => (item.metadata?.cross_platform_count || 1) > 1).length);
const latestUpdatedAt = computed(() => hotspots.value[0]?.created_at ? formatShortTime(hotspots.value[0].created_at) : '-');
const topClusters = computed(() => [...hotspots.value]
  .sort((a, b) => ((b.metadata?.cross_platform_count || 1) - (a.metadata?.cross_platform_count || 1)) || ((b.quality_score || 0) - (a.quality_score || 0)))
  .slice(0, 6));

const heatOptions = [
  { value: 'all', label: '全部热度' },
  { value: 'super', label: '超热 ≥80' },
  { value: 'high', label: '高热 ≥60' },
  { value: 'normal', label: '普通 <60' },
];

const timeOptions = [
  { value: 'today', label: '今天' },
  { value: '3d', label: '近3天' },
  { value: '7d', label: '近7天' },
];

const go = (path: string) => router.push(path);

// ── Preference helpers ──
const loadPreferenceFromStorage = () => {
  try {
    const raw = localStorage.getItem(PREF_STORAGE_KEY);
    if (raw) {
      const saved = JSON.parse(raw);
      preference.interest_keywords = saved.interest_keywords || [];
      preference.preferred_platforms = saved.preferred_platforms || [];
      preference.blocked_keywords = saved.blocked_keywords || [];
    }
  } catch { /* ignore */ }
};

const savePreferenceToStorage = () => {
  localStorage.setItem(PREF_STORAGE_KEY, JSON.stringify({
    interest_keywords: preference.interest_keywords,
    preferred_platforms: preference.preferred_platforms,
    blocked_keywords: preference.blocked_keywords,
  }));
};

const syncPreferenceToBackend = async () => {
  try {
    const { saveUserPreferences } = await import('@/api');
    await saveUserPreferences({
      interest_keywords: preference.interest_keywords,
      preferred_platforms: preference.preferred_platforms,
      blocked_keywords: preference.blocked_keywords,
    });
  } catch { /* silent */ }
};

const loadPreferenceFromBackend = async () => {
  try {
    const { getUserPreferences } = await import('@/api');
    const res = await getUserPreferences();
    if (res.data) {
      const d = res.data;
      if (d.interest_keywords?.length || d.preferred_platforms?.length) {
        preference.interest_keywords = d.interest_keywords || [];
        preference.preferred_platforms = d.preferred_platforms || [];
        preference.blocked_keywords = d.blocked_keywords || [];
        savePreferenceToStorage();
      }
    }
  } catch { /* silent */ }
};

const addInterestKeyword = () => {
  const kw = newKeyword.value.trim();
  if (kw && !preference.interest_keywords.includes(kw)) {
    preference.interest_keywords.push(kw);
    savePreferenceToStorage();
    syncPreferenceToBackend();
  }
  newKeyword.value = '';
};

const removeInterestKeyword = (kw: string) => {
  preference.interest_keywords = preference.interest_keywords.filter((k) => k !== kw);
  savePreferenceToStorage();
  syncPreferenceToBackend();
};

const togglePreferredPlatform = (platform: string) => {
  if (preference.preferred_platforms.includes(platform)) {
    preference.preferred_platforms = preference.preferred_platforms.filter((p) => p !== platform);
  } else {
    preference.preferred_platforms.push(platform);
  }
  savePreferenceToStorage();
  syncPreferenceToBackend();
};

const applyPreferenceToFilters = () => {
  if (preference.interest_keywords.length) {
    filters.keyword = preference.interest_keywords.join(' ');
  }
  if (preference.preferred_platforms.length === 1) {
    activePlatformTab.value = preference.preferred_platforms[0];
  }
  applyFilters();
};

const clearPreference = () => {
  preference.interest_keywords = [];
  preference.preferred_platforms = [];
  preference.blocked_keywords = [];
  savePreferenceToStorage();
  syncPreferenceToBackend();
};

const goToCreate = async (item: any) => {
  selectedHotspotForCreate.value = item;
  // 直接生成，不弹窗。有 Agent 用第一个，没有也能生成。
  creating.value = true;
  try {
    const res = await createArticleFromHotspot(item.id, {
      agent_id: agents.value[0]?.id,
    });
    MessagePlugin.success(`AI 已起草：${res.data.title}`);
    router.push(`/create?article_id=${res.data.id}&hotspot_id=${item.id}`);
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '生成失败');
  } finally {
    creating.value = false;
  }
};

const openQuickCreate = (item: any) => {
  selectedHotspotForCreate.value = item;
  createVisible.value = true;
};

const collectMaterial = async (item: any) => {
  try {
    const { uploadMaterial } = await import('@/api');
    await uploadMaterial({ title: item.title, content: item.summary || '', original_url: item.original_url || '', tags: item.tags || [] });
    MessagePlugin.success('已收藏到素材库');
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '收藏失败');
  }
};

const createArticle = async (payload: { agent_id?: number; style_id?: string; prompt_template_id?: number; user_prompt?: string; mode?: string }) => {
  if (!selectedHotspotForCreate.value) return;
  creating.value = true;
  try {
    const res = await createArticleFromHotspotAsync(selectedHotspotForCreate.value.id, {
      agent_id: payload.agent_id,
      style_id: payload.style_id,
      prompt_template_id: payload.prompt_template_id,
      user_prompt: payload.user_prompt,
      mode: payload.mode,
    });
    createVisible.value = false;
    // Redirect to create page with task_id for SSE streaming
    router.push(`/create?task_id=${res.data.task_id}&hotspot_id=${selectedHotspotForCreate.value.id}`);
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '生成失败');
  } finally {
    creating.value = false;
  }
};


const currentHeatRange = () => {
  if (heatRange.value === 'super') return { heat_min: 0.8 };
  if (heatRange.value === 'high') return { heat_min: 0.6 };
  if (heatRange.value === 'normal') return { heat_max: 0.59 };
  return {};
};

const fetchPlatformOptions = async () => {
  try {
    const res = await getHotspotPlatforms();
    platformOptions.value = res.data || [];
  } catch {
    platformOptions.value = [];
  }
};

const fetchHotspots = async () => {
  loading.value = true;
  pagination.offset = (pagination.page - 1) * pagination.pageSize;
  try {
    const heatParams = currentHeatRange();
    const res = await getHotspots({
      keyword: filters.keyword || undefined,
      tag: filters.tag || undefined,
      platform: activePlatformTab.value !== 'all' ? activePlatformTab.value : undefined,
      time_range: timeRange.value,
      limit: pagination.pageSize,
      offset: pagination.offset,
      ...heatParams,
    });
    let items = res.data?.items || [];

    // Preference boost: items matching interest keywords float to top
    if (preference.interest_keywords.length && !filters.keyword) {
      const kwList = preference.interest_keywords.map((k) => k.toLowerCase());
      const matchScore = (item: any) => {
        const text = ((item.title || '') + ' ' + (item.summary || '')).toLowerCase();
        return kwList.reduce((score, kw) => score + (text.includes(kw) ? 1 : 0), 0);
      };
      items = [...items].sort((a, b) => matchScore(b) - matchScore(a));
    }

    hotspots.value = items;
    pagination.total = res.data?.total || 0;
  } catch {
    hotspots.value = [];
    pagination.total = 0;
    MessagePlugin.error('加载热榜失败');
  } finally {
    loading.value = false;
  }
};

const applyFilters = async () => {
  pagination.page = 1;
  await fetchHotspots();
};

const resetFilters = async () => {
  filters.keyword = '';
  filters.tag = '';
  selectedPlatforms.value = [];
  activePlatformTab.value = 'all';
  heatRange.value = 'all';
  timeRange.value = 'today';
  pagination.page = 1;
  await fetchHotspots();
};

const togglePlatformFilter = (platform: string) => {
  if (selectedPlatforms.value.includes(platform)) {
    selectedPlatforms.value = selectedPlatforms.value.filter((item) => item !== platform);
  } else {
    selectedPlatforms.value = [...selectedPlatforms.value, platform];
  }
};

const handlePlatformTabChange = async (value: string) => {
  activePlatformTab.value = value;
  pagination.page = 1;
  await fetchHotspots();
};

const onPageChange = async (page: number) => {
  pagination.page = page;
  await fetchHotspots();
};

const onPageSizeChange = async (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.page = 1;
  await fetchHotspots();
};

const refreshTrending = async () => {
  refreshing.value = true;
  try {
    const res = await refreshAllTrending();
    const data = res.data || {};
    MessagePlugin.success(`更新完成：覆盖 ${data.platforms_collected?.length || 0} 个源，新增 ${data.new_items || 0} 条热点`);
    await Promise.all([fetchPlatformOptions(), fetchHotspots()]);
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '更新失败');
  } finally {
    refreshing.value = false;
  }
};

const downloadExport = async () => {
  exporting.value = true;
  try {
    const res = await exportHotspots({
      keyword: filters.keyword || undefined,
      platform: selectedPlatforms.value.length ? selectedPlatforms.value[0] : undefined,
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
    currentTrend.value = [];
    MessagePlugin.error('加载趋势失败');
  }
};

onMounted(async () => {
  // Load preference from localStorage first (instant)
  loadPreferenceFromStorage();

  // Auto-apply preference as default tab
  if (preference.preferred_platforms.length === 1) {
    activePlatformTab.value = preference.preferred_platforms[0];
  }

  await Promise.all([
    fetchPlatformOptions(),
    fetchHotspots(),
    getAgents().then((res) => { agents.value = res.data || []; }).catch(() => {}),
    getStylePresets().then((res) => { stylePresets.value = res.data || []; }).catch(() => {}),
    getPromptTemplates().then((res) => { prompts.value = res.data || []; }).catch(() => {}),
  ]);

  // Sync preference from backend (async, backend wins if different)
  loadPreferenceFromBackend();
});
</script>

<style scoped>
.trending-page {
  max-width: 100%;
  margin: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}
.sidebar-panel,
.main-shell {
  border-radius: 18px;
  border: 1px solid var(--td-component-stroke);
  background: linear-gradient(180deg, #fff 0%, #fbfcff 100%);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
}
.trending-sidebar {
  position: sticky;
  top: 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: calc(100vh - 48px);
  overflow: auto;
  padding-right: 2px;
}
.page-meta-panel,
.filter-panel,
.cluster-panel {
  padding: 16px;
}
.page-kicker {
  font-size: 12px;
  font-weight: 700;
  color: var(--td-brand-color);
  margin-bottom: 8px;
}
.page-title {
  font-size: 20px;
  font-weight: 800;
  color: var(--td-text-color-primary);
  line-height: 1.5;
}
.page-desc,
.panel-subtext,
.empty-mini {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.75;
  color: var(--td-text-color-secondary);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.panel-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--td-text-color-primary);
  margin-bottom: 8px;
}
.section-block {
  margin-top: 16px;
}
.chip-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chip-column.compact {
  gap: 6px;
}
.filter-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--td-component-stroke);
  background: #fff;
  color: var(--td-text-color-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all .2s ease;
}
.filter-chip:hover,
.filter-chip.active {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
  background: var(--td-brand-color-1);
}
.chip-count {
  font-size: 12px;
  color: var(--td-text-color-placeholder);
}
.sidebar-actions {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}
.cluster-list-mini {
  display: grid;
  gap: 8px;
}
.cluster-item-mini {
  padding: 12px;
  text-align: left;
  border-radius: 14px;
  border: 1px solid var(--td-component-stroke);
  background: #fff;
  cursor: pointer;
}
.cluster-title-mini {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.6;
  color: var(--td-text-color-primary);
}
.cluster-meta-mini {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.stats-bar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
  padding: 0 4px;
}
.stats-left {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.stats-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--td-bg-color-container-hover);
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.main-shell {
  padding: 16px;
}
.main-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 16px;
}
.main-title {
  font-size: 20px;
  font-weight: 800;
  color: var(--td-text-color-primary);
}
.main-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--td-text-color-secondary);
}
.hotspot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.hotspot-card {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--td-component-stroke);
  border-top-width: 4px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.hotspot-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.1);
}
.hotspot-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.hotspot-meta-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.rank-badge {
  font-size: 12px;
  font-weight: 700;
  color: var(--td-text-color-placeholder);
}
.cross-badge {
  font-size: 12px;
  font-weight: 700;
  color: #d05f1a;
  background: #fff1e8;
  padding: 4px 8px;
  border-radius: 999px;
}
.heat-badge {
  font-size: 12px;
  font-weight: 800;
}
.hotspot-title {
  font-size: 16px;
  font-weight: 800;
  line-height: 1.65;
  color: var(--td-text-color-primary);
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.hotspot-summary {
  min-height: 44px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--td-text-color-secondary);
  margin-bottom: 14px;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.hotspot-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.hotspot-bar-track {
  flex: 1;
  height: 8px;
  background: var(--td-bg-color-component);
  border-radius: 999px;
  overflow: hidden;
}
.hotspot-bar-fill {
  height: 100%;
  border-radius: 999px;
}
.hotspot-score {
  min-width: 28px;
  text-align: right;
  font-size: 12px;
  font-weight: 700;
  color: var(--td-text-color-primary);
}
.hotspot-extra {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--td-text-color-placeholder);
  margin-bottom: 14px;
}
.hotspot-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.origin-link {
  font-size: 12px;
  color: var(--td-text-color-secondary);
  text-decoration: none;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--td-component-stroke);
}
/* ── Preference panel ── */
.preference-panel {
  padding: 14px 16px;
}
.pref-section {
  margin-bottom: 12px;
}
.pref-hint {
  font-size: 11px;
  color: var(--td-text-color-secondary);
  margin-bottom: 6px;
}
.pref-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pref-chip {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--td-component-stroke);
  background: #fff;
  color: var(--td-text-color-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all .15s ease;
}
.pref-chip:hover,
.pref-chip.active {
  border-color: var(--td-brand-color);
  color: var(--td-brand-color);
  background: var(--td-brand-color-1);
}
@media (max-width: 1100px) {
  .trending-page {
    grid-template-columns: 1fr;
  }
  .trending-sidebar {
    position: static;
    max-height: none;
    overflow: visible;
  }
}
@media (max-width: 768px) {
  .stats-bar,
  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }
  .hotspot-grid {
    grid-template-columns: 1fr;
  }
}
</style>
