<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
      <h3 style="margin: 0">公众号列表</h3>
      <t-button theme="primary" @click="openDialog()">添加公众号</t-button>
    </div>

    <t-table :data="accounts" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #followers="{ row }">
        <t-loading v-if="statsLoading[row.id]" size="small" />
        <template v-else-if="statsData[row.id]">
          <t-tag
            v-if="statsData[row.id].total_followers !== undefined"
            theme="primary"
            variant="light"
            style="cursor: pointer"
            @click="openStatsDrawer(row)"
          >
            {{ statsData[row.id].total_followers }} 粉丝
          </t-tag>
          <t-tag v-if="statsData[row.id].warnings?.length" theme="warning" variant="light" style="margin-left: 4px">
            受限
          </t-tag>
        </template>
        <t-tag v-else theme="default" variant="light">--</t-tag>
      </template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openStatsDrawer(row)">
            <t-icon name="chart" style="margin-right: 2px" />数据
          </t-link>
          <t-link theme="primary" @click="openDialog(row)">编辑</t-link>
          <t-popconfirm content="确定删除该公众号？" @confirm="onDelete(row.id)">
            <t-link theme="danger">删除</t-link>
          </t-popconfirm>
        </t-space>
      </template>
    </t-table>

    <!-- Add / Edit dialog -->
    <t-dialog
      v-model:visible="dialogVisible"
      :header="editingAccount ? '编辑公众号' : '添加公众号'"
      :footer="false"
      width="560px"
    >
      <AccountForm
        :edit-id="editingAccount?.id"
        :initial-data="editingAccount"
        @success="onFormSuccess"
      />
    </t-dialog>

    <!-- Stats Drawer -->
    <t-drawer
      v-model:visible="drawerVisible"
      :header="`${drawerAccount?.name || ''} · 数据统计`"
      size="640px"
      :footer="false"
    >
      <div v-if="drawerAccount" style="padding: 0 8px">
        <!-- Date range picker -->
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px">
          <span style="white-space: nowrap; font-size: 14px; color: var(--td-text-color-secondary)">日期范围</span>
          <t-date-range-picker
            v-model="dateRange"
            :disabled-date="disabledDate"
            style="width: 280px"
            @change="onDateRangeChange"
          />
        </div>

        <!-- Follower overview -->
        <t-card title="粉丝概况" :bordered="true" style="margin-bottom: 16px" :loading="drawerLoading">
          <div v-if="drawerFollowers" style="display: flex; gap: 24px; flex-wrap: wrap">
            <div style="text-align: center; min-width: 100px">
              <div style="font-size: 28px; font-weight: 600; color: var(--td-brand-color)">
                {{ drawerFollowers.total_followers ?? '--' }}
              </div>
              <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">累计粉丝</div>
            </div>
            <div v-if="followerSummary.newUsers > 0 || followerSummary.cancelUsers > 0" style="display: flex; gap: 24px">
              <div style="text-align: center; min-width: 80px">
                <div style="font-size: 20px; font-weight: 600; color: var(--td-success-color)">
                  +{{ followerSummary.newUsers }}
                </div>
                <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">新增关注</div>
              </div>
              <div style="text-align: center; min-width: 80px">
                <div style="font-size: 20px; font-weight: 600; color: var(--td-error-color)">
                  -{{ followerSummary.cancelUsers }}
                </div>
                <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">取消关注</div>
              </div>
              <div style="text-align: center; min-width: 80px">
                <div style="font-size: 20px; font-weight: 600" :style="{ color: followerSummary.netUsers >= 0 ? 'var(--td-success-color)' : 'var(--td-error-color)' }">
                  {{ followerSummary.netUsers >= 0 ? '+' : '' }}{{ followerSummary.netUsers }}
                </div>
                <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">净增</div>
              </div>
            </div>
          </div>
          <div v-if="drawerFollowers?.warnings?.length" style="margin-top: 12px">
            <t-alert
              v-for="(w, i) in drawerFollowers.warnings"
              :key="i"
              theme="warning"
              :message="w"
              style="margin-bottom: 8px"
            />
          </div>
          <!-- Follower daily trend table -->
          <t-table
            v-if="drawerFollowers?.user_summary?.length"
            :data="drawerFollowers.user_summary"
            :columns="followerColumns"
            row-key="ref_date"
            size="small"
            stripe
            style="margin-top: 16px"
          />
        </t-card>

        <!-- Article stats -->
        <t-card title="图文统计" :bordered="true" :loading="drawerLoading">
          <div v-if="drawerArticleStats">
            <div v-if="drawerArticleStats.warnings?.length" style="margin-bottom: 12px">
              <t-alert
                v-for="(w, i) in drawerArticleStats.warnings"
                :key="i"
                theme="warning"
                :message="w"
                style="margin-bottom: 8px"
              />
            </div>
            <!-- Daily summary -->
            <t-table
              v-if="drawerArticleStats.article_summary?.length"
              :data="drawerArticleStats.article_summary"
              :columns="articleSummaryColumns"
              row-key="ref_date"
              size="small"
              stripe
              style="margin-bottom: 16px"
            >
              <template #title>每日汇总</template>
            </t-table>
            <!-- Per-article detail -->
            <div v-if="articleDetailRows.length" style="margin-top: 8px">
              <div style="font-size: 14px; font-weight: 500; margin-bottom: 8px">文章明细</div>
              <t-table
                :data="articleDetailRows"
                :columns="articleDetailColumns"
                row-key="_key"
                size="small"
                stripe
              />
            </div>
            <t-empty
              v-if="!drawerArticleStats.article_summary?.length && !articleDetailRows.length && !drawerArticleStats.warnings?.length"
              description="暂无图文统计数据"
            />
          </div>
        </t-card>
      </div>
    </t-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { getAccounts, deleteAccount, getAccountFollowers, getAccountArticleStats } from '@/api';
import AccountForm from '@/components/AccountForm.vue';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const accounts = ref<any[]>([]);
const dialogVisible = ref(false);
const editingAccount = ref<any>(null);

// Stats data loaded inline for each account row
const statsLoading = ref<Record<number, boolean>>({});
const statsData = ref<Record<number, any>>({});

// Drawer state
const drawerVisible = ref(false);
const drawerAccount = ref<any>(null);
const drawerLoading = ref(false);
const drawerFollowers = ref<any>(null);
const drawerArticleStats = ref<any>(null);

// Date range for drawer (default: last 7 days)
const getDefaultDateRange = (): [string, string] => {
  const end = new Date();
  end.setDate(end.getDate() - 1);
  const begin = new Date(end);
  begin.setDate(begin.getDate() - 6);
  return [begin.toISOString().slice(0, 10), end.toISOString().slice(0, 10)];
};
const dateRange = ref<[string, string]>(getDefaultDateRange());

const disabledDate = (d: Date) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d >= today;
};

// Table columns
const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'name', title: '名称', width: 160 },
  { colKey: 'appid', title: 'AppID', width: 200 },
  { colKey: 'followers', title: '粉丝数', width: 140 },
  { colKey: 'ip_whitelist', title: 'IP 白名单', ellipsis: true },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
  { colKey: 'op', title: '操作', width: 180 },
];

const followerColumns = [
  { colKey: 'ref_date', title: '日期', width: 120 },
  { colKey: 'new_user', title: '新增关注', width: 100 },
  { colKey: 'cancel_user', title: '取消关注', width: 100 },
  {
    colKey: 'net',
    title: '净增',
    width: 100,
    cell: (_h: any, { row }: any) => {
      const net = (row.new_user || 0) - (row.cancel_user || 0);
      return `${net >= 0 ? '+' : ''}${net}`;
    },
  },
];

const articleSummaryColumns = [
  { colKey: 'ref_date', title: '日期', width: 120 },
  { colKey: 'int_page_read_user', title: '阅读人数', width: 100 },
  { colKey: 'int_page_read_count', title: '阅读次数', width: 100 },
  { colKey: 'share_user', title: '分享人数', width: 100 },
  { colKey: 'share_count', title: '分享次数', width: 100 },
  { colKey: 'add_to_fav_count', title: '收藏次数', width: 100 },
];

const articleDetailColumns = [
  { colKey: 'ref_date', title: '日期', width: 100 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'int_page_read_user', title: '阅读人数', width: 100 },
  { colKey: 'int_page_read_count', title: '阅读次数', width: 100 },
  { colKey: 'share_user', title: '分享人数', width: 90 },
  { colKey: 'add_to_fav_user', title: '收藏人数', width: 90 },
];

// Computed: flatten article_total data for per-article table
const articleDetailRows = computed(() => {
  const total = drawerArticleStats.value?.article_total || [];
  const rows: any[] = [];
  for (const item of total) {
    const details = item.details || [];
    for (const detail of details) {
      rows.push({
        _key: `${item.ref_date}-${item.title}-${detail.stat_date}`,
        ref_date: detail.stat_date || item.ref_date,
        title: item.title || '--',
        int_page_read_user: detail.int_page_read_user || 0,
        int_page_read_count: detail.int_page_read_count || 0,
        share_user: detail.share_user || 0,
        add_to_fav_user: detail.add_to_fav_user || 0,
      });
    }
  }
  return rows;
});

// Computed: aggregate follower summary numbers
const followerSummary = computed(() => {
  const summary = drawerFollowers.value?.user_summary || [];
  let newUsers = 0;
  let cancelUsers = 0;
  for (const item of summary) {
    newUsers += item.new_user || 0;
    cancelUsers += item.cancel_user || 0;
  }
  return { newUsers, cancelUsers, netUsers: newUsers - cancelUsers };
});

// Fetch accounts list
const fetchData = async () => {
  loading.value = true;
  try {
    const res = await getAccounts();
    accounts.value = res.data;
    // Load follower stats for each account in parallel
    loadAllStats();
  } catch {
    // ignore
  } finally {
    loading.value = false;
  }
};

// Load follower count for all accounts in list
const loadAllStats = () => {
  for (const account of accounts.value) {
    loadAccountStats(account.id);
  }
};

const loadAccountStats = async (id: number) => {
  statsLoading.value[id] = true;
  try {
    const res = await getAccountFollowers(id);
    statsData.value[id] = res.data;
  } catch {
    statsData.value[id] = null;
  } finally {
    statsLoading.value[id] = false;
  }
};

// Drawer: open and load detailed stats
const openStatsDrawer = async (account: any) => {
  drawerAccount.value = account;
  drawerVisible.value = true;
  dateRange.value = getDefaultDateRange();
  await loadDrawerData();
};

const loadDrawerData = async () => {
  if (!drawerAccount.value) return;
  const id = drawerAccount.value.id;
  const params = { begin_date: dateRange.value[0], end_date: dateRange.value[1] };

  drawerLoading.value = true;
  drawerFollowers.value = null;
  drawerArticleStats.value = null;

  try {
    const [followersRes, articleRes] = await Promise.all([
      getAccountFollowers(id, params),
      getAccountArticleStats(id, params),
    ]);
    drawerFollowers.value = followersRes.data;
    drawerArticleStats.value = articleRes.data;
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '获取统计数据失败');
  } finally {
    drawerLoading.value = false;
  }
};

const onDateRangeChange = () => {
  loadDrawerData();
};

const openDialog = (account?: any) => {
  editingAccount.value = account || null;
  dialogVisible.value = true;
};

const onFormSuccess = () => {
  dialogVisible.value = false;
  MessagePlugin.success('操作成功');
  fetchData();
};

const onDelete = async (id: number) => {
  try {
    await deleteAccount(id);
    MessagePlugin.success('删除成功');
    fetchData();
  } catch {
    MessagePlugin.error('删除失败');
  }
};

onMounted(fetchData);
</script>
