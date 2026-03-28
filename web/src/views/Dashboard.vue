<template>
  <div>
    <!-- Agent Connect Banner -->
    <t-card :bordered="true" style="margin-bottom: 24px; background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%); border-color: #91caff">
      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px">
        <div>
          <div style="font-weight: 600; font-size: 15px; margin-bottom: 4px">🤖 连接 AI Agent</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary)">复制安装命令，让 AI Agent 一键接入本系统，自动管理公众号和生成文章</div>
        </div>
        <div style="display: flex; gap: 8px; flex-shrink: 0">
          <t-button theme="primary" @click="onCopyInstallCommand">
            <template #icon><t-icon name="file-copy" /></template>
            一键复制安装命令
          </t-button>
          <t-tooltip content="下载 Skill 包到本地">
            <t-button variant="outline" @click="onDownloadSkill">
              <template #icon><t-icon name="download" /></template>
            </t-button>
          </t-tooltip>
        </div>
      </div>
      <!-- Collapsible command preview -->
      <div v-if="showCommand" style="margin-top: 12px; background: rgba(0,0,0,0.04); border-radius: 6px; padding: 12px; font-family: monospace; font-size: 12px; line-height: 1.6; word-break: break-all; color: #333">
        {{ installCommand }}
      </div>
      <t-link style="margin-top: 8px; display: inline-block; font-size: 12px" @click="showCommand = !showCommand">
        {{ showCommand ? '收起命令' : '查看命令内容' }}
      </t-link>
    </t-card>
    <div style="display: flex; gap: 16px; margin-bottom: 24px">
      <t-card v-for="card in statCards" :key="card.label" style="flex: 1" :bordered="true">
        <div style="text-align: center">
          <div style="font-size: 32px; font-weight: 700; color: var(--td-brand-color)">{{ card.value }}</div>
          <div style="color: var(--td-text-color-secondary); margin-top: 4px">{{ card.label }}</div>
        </div>
      </t-card>
    </div>

    <!-- Source mode stats -->
    <t-card title="来源模式效果对比" :bordered="true" style="margin-bottom: 24px">
      <template v-if="sourceStats.length">
        <t-table :data="sourceStats" :columns="sourceStatCols" row-key="source_type" size="small" stripe>
          <template #source_type="{ row }">
            <t-tag :theme="sourceTheme(row.source_type)" variant="light" size="small">
              {{ sourceLabel(row.source_type) }}
            </t-tag>
          </template>
          <template #acceptance_rate="{ row }">
            <t-progress :percentage="Math.round(row.acceptance_rate * 100)" size="small" theme="plump"
              :color="row.acceptance_rate > 0.5 ? '#52c41a' : row.acceptance_rate > 0.2 ? '#faad14' : '#ff4d4f'" />
          </template>
          <template #duplicate_rate="{ row }">
            <span :style="{ color: row.duplicate_rate > 0.3 ? 'var(--td-error-color)' : 'inherit' }">
              {{ (row.duplicate_rate * 100).toFixed(1) }}%
            </span>
          </template>
        </t-table>
      </template>
      <div v-else style="text-align: center; padding: 24px; color: var(--td-text-color-placeholder)">
        暂无素材统计数据
      </div>
    </t-card>

    <!-- Tag distribution -->
    <t-card title="标签分布统计 (Top 15)" :bordered="true" style="margin-bottom: 24px">
      <template v-if="tagStats.length">
        <t-table :data="tagStats.slice(0, 15)" :columns="tagStatCols" row-key="tag" size="small" stripe>
          <template #tag="{ row }">
            <t-tag size="small" variant="outline">{{ row.tag }}</t-tag>
          </template>
          <template #acceptance_rate="{ row }">
            <t-progress :percentage="Math.round(row.acceptance_rate * 100)" size="small" theme="plump"
              :color="row.acceptance_rate > 0.5 ? '#52c41a' : row.acceptance_rate > 0.2 ? '#faad14' : '#ff4d4f'" />
          </template>
        </t-table>
      </template>
      <div v-else style="text-align: center; padding: 24px; color: var(--td-text-color-placeholder)">
        暂无标签统计数据
      </div>
    </t-card>

    <!-- Recent articles -->
    <t-card title="最近文章" :bordered="true" style="margin-bottom: 24px">
      <template v-if="articles.length">
        <t-table :data="articles" :columns="articleCols" row-key="id" size="small" />
      </template>
      <t-result v-else status="404" title="暂无文章" description="还没有生成任何文章">
        <template #extra>
          <t-button theme="primary" @click="$router.push('/guide')">开始配置</t-button>
        </template>
      </t-result>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { getStats, getArticles, getSourceModeStats, getTagStats, getUserInfo } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

// Agent connect
const showCommand = ref(false);
const userInfo = getUserInfo();
const userEmail = computed(() => userInfo?.email && userInfo.email !== '__admin__' ? userInfo.email : '');
const installCommand = computed(() => {
  const origin = window.location.origin;
  const emailPart = userEmail.value ? ` auth --email ${userEmail.value}` : ' auth --email YOUR_EMAIL';
  return `curl -o /tmp/ap-skill.zip ${origin}/api/skill-package/download && unzip -o /tmp/ap-skill.zip -d ~/.ap-skill && uv run ~/.ap-skill/scripts/agent_publisher.py --url ${origin}${emailPart}`;
});

const onCopyInstallCommand = async () => {
  try {
    await navigator.clipboard.writeText(installCommand.value);
    MessagePlugin.success('安装命令已复制到剪贴板');
    showCommand.value = true;
  } catch {
    MessagePlugin.error('复制失败，请手动复制');
    showCommand.value = true;
  }
};

const onDownloadSkill = () => {
  window.open(`${window.location.origin}/api/skill-package/download`, '_blank');
};

const stats = ref({ agents: 0, articles: 0, tasks: 0, accounts: 0 });
const articles = ref<any[]>([]);
const sourceStats = ref<any[]>([]);
const tagStats = ref<any[]>([]);

const statCards = ref([
  { label: '公众号', value: 0 },
  { label: 'Agent', value: 0 },
  { label: '文章', value: 0 },
  { label: '任务', value: 0 },
]);

const sourceLabel = (type: string) => {
  const map: Record<string, string> = { rss: 'RSS', search: '搜索', skills_feed: 'Skills', manual: '手动' };
  return map[type] || type;
};

const sourceTheme = (type: string): string => {
  const map: Record<string, string> = { rss: 'primary', search: 'warning', skills_feed: 'success', manual: 'default' };
  return map[type] || 'default';
};

const sourceStatCols = [
  { colKey: 'source_type', title: '来源类型', width: 100 },
  { colKey: 'total', title: '总量', width: 80 },
  { colKey: 'accepted', title: '已采纳', width: 80 },
  { colKey: 'pending', title: '待处理', width: 80 },
  { colKey: 'duplicate_count', title: '重复', width: 70 },
  { colKey: 'acceptance_rate', title: '采纳率', width: 150 },
  { colKey: 'duplicate_rate', title: '重复率', width: 80 },
];

const tagStatCols = [
  { colKey: 'tag', title: '标签', width: 150 },
  { colKey: 'total', title: '素材数', width: 80 },
  { colKey: 'accepted', title: '已采纳', width: 80 },
  { colKey: 'acceptance_rate', title: '采纳率', width: 200 },
];

const articleCols = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
];

onMounted(async () => {
  try {
    const res = await getStats();
    stats.value = res.data;
    statCards.value = [
      { label: '公众号', value: res.data.accounts },
      { label: 'Agent', value: res.data.agents },
      { label: '文章', value: res.data.articles },
      { label: '任务', value: res.data.tasks },
    ];
  } catch {}

  try {
    const res = await getArticles();
    articles.value = res.data.slice(0, 10);
  } catch {}

  try {
    const res = await getSourceModeStats();
    sourceStats.value = res.data;
  } catch {}

  try {
    const res = await getTagStats();
    tagStats.value = res.data;
  } catch {}
});
</script>
