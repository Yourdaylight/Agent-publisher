<template>
  <div class="home-page">
    <!-- Row 1: 个人概览卡片 -->
    <div class="stat-row">
      <div class="stat-card" @click="router.push('/accounts')">
        <div class="stat-icon">📡</div>
        <div class="stat-value">{{ stats.accounts }}</div>
        <div class="stat-label">绑定公众号</div>
      </div>
      <div class="stat-card" @click="router.push('/articles')">
        <div class="stat-icon">📝</div>
        <div class="stat-value">{{ stats.articles }}</div>
        <div class="stat-label">文章总数</div>
      </div>
      <div class="stat-card" @click="router.push('/agents')">
        <div class="stat-icon">🤖</div>
        <div class="stat-value">{{ stats.agents }}</div>
        <div class="stat-label">写作身份</div>
      </div>
      <div class="stat-card" @click="router.push('/membership')">
        <div class="stat-icon">💎</div>
        <div class="stat-value">{{ creditsAvailable ?? '—' }}</div>
        <div class="stat-label">Credits 余额</div>
      </div>
    </div>

    <!-- Row 2: 快捷操作 -->
    <div class="quick-actions">
      <button class="action-card primary" @click="router.push('/create')">
        <div class="action-icon">✨</div>
        <div class="action-title">开始创作</div>
        <div class="action-desc">从热点一键生成文章</div>
      </button>
      <button class="action-card" @click="router.push('/trending')">
        <div class="action-icon">🔥</div>
        <div class="action-title">发现热点</div>
        <div class="action-desc">跨平台热榜聚合</div>
      </button>
      <button class="action-card" @click="router.push('/articles')">
        <div class="action-icon">📋</div>
        <div class="action-title">管理文章</div>
        <div class="action-desc">编辑、发布、生成视频</div>
      </button>
      <button class="action-card" @click="router.push('/guide')">
        <div class="action-icon">🚀</div>
        <div class="action-title">快速配置</div>
        <div class="action-desc">6 步完成初始化</div>
      </button>
    </div>

    <!-- Row 3: Skill 下载 Banner -->
    <div class="skill-banner">
      <div class="skill-left">
        <div class="skill-title">🤖 连接 AI Agent</div>
        <div class="skill-desc">复制安装命令，让 AI Agent 一键接入本系统，自动管理公众号和生成文章</div>
      </div>
      <div class="skill-actions">
        <t-button theme="primary" @click="onCopyInstallCommand">
          <template #icon><t-icon name="file-copy" /></template>
          复制安装命令
        </t-button>
        <t-button variant="outline" @click="onDownloadSkill">
          <template #icon><t-icon name="download" /></template>
          下载 Skill
        </t-button>
      </div>
    </div>
    <div v-if="showCommand" class="command-preview">{{ installCommand }}</div>

    <div class="two-col">
      <!-- Left: 热点快报 -->
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">🔥 热点快报</div>
          <t-link theme="primary" @click="router.push('/trending')">查看更多 →</t-link>
        </div>
        <div v-if="hotspots.length" class="hotspot-list">
          <div v-for="(item, idx) in hotspots" :key="item.id" class="hotspot-item" @click="goCreate(item)">
            <span class="hotspot-rank">#{{ idx + 1 }}</span>
            <div class="hotspot-info">
              <div class="hotspot-title">{{ item.title }}</div>
              <div class="hotspot-meta">
                <t-tag size="small" variant="light">{{ getPlatform(item) }}</t-tag>
                <span>{{ formatTime(item.created_at) }}</span>
              </div>
            </div>
            <t-button size="small" theme="primary" variant="text" @click.stop="goCreate(item)">创作</t-button>
          </div>
        </div>
        <div v-else class="empty-hint">暂无热点数据，请先配置数据源</div>
      </div>

      <!-- Right: 最近草稿 -->
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">📝 最近草稿</div>
          <t-link theme="primary" @click="router.push('/articles')">查看全部 →</t-link>
        </div>
        <div v-if="drafts.length" class="draft-list">
          <div v-for="a in drafts" :key="a.id" class="draft-item" @click="router.push(`/create?article_id=${a.id}`)">
            <div class="draft-title">{{ a.title || `草稿 #${a.id}` }}</div>
            <div class="draft-meta">{{ formatTime(a.created_at) }}</div>
          </div>
        </div>
        <div v-else class="empty-hint">还没有草稿，开始创作吧</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { getStats, getArticles, getHotspots, getCreditsBalance, getUserInfo } from '@/api';

const router = useRouter();
const stats = ref({ accounts: 0, agents: 0, articles: 0, tasks: 0 });
const creditsAvailable = ref<number | null>(null);
const hotspots = ref<any[]>([]);
const drafts = ref<any[]>([]);
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
    MessagePlugin.success('安装命令已复制');
    showCommand.value = true;
  } catch {
    MessagePlugin.error('复制失败');
    showCommand.value = true;
  }
};

const onDownloadSkill = () => {
  window.open(`${window.location.origin}/api/skill-package/download`, '_blank');
};

const getPlatform = (item: any) => {
  if (item.metadata?.platform) return item.metadata.platform;
  if (item.source_identity) return item.source_identity.split('/')[0];
  return '热点';
};

const formatTime = (dt: string) => {
  if (!dt) return '';
  const d = new Date(dt);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
};

const goCreate = (item: any) => {
  router.push(`/create?hotspot_id=${item.id}`);
};

onMounted(async () => {
  await Promise.all([
    getStats().then(r => { stats.value = r.data; }).catch(() => {}),
    getCreditsBalance().then(r => { creditsAvailable.value = r.data?.available ?? 0; }).catch(() => {}),
    getHotspots({ limit: 8, time_range: '3d' }).then(r => { hotspots.value = r.data?.items || []; }).catch(() => {}),
    getArticles({ status: 'draft' }).then(r => { drafts.value = (r.data || []).slice(0, 8); }).catch(() => {}),
  ]);
});
</script>

<style scoped>
.home-page { max-width: 1100px; margin: 0 auto; }

.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
.stat-card {
  padding: 20px; border-radius: 14px; background: #fff;
  border: 1px solid var(--td-component-stroke); cursor: pointer;
  text-align: center; transition: all .2s;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,.06); }
.stat-icon { font-size: 28px; margin-bottom: 6px; }
.stat-value { font-size: 28px; font-weight: 800; color: var(--td-brand-color); }
.stat-label { font-size: 13px; color: var(--td-text-color-secondary); margin-top: 4px; }

.quick-actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.action-card {
  padding: 18px 16px; border-radius: 14px; background: #fff;
  border: 1px solid var(--td-component-stroke); cursor: pointer;
  text-align: left; transition: all .2s; font-family: inherit;
}
.action-card:hover { border-color: var(--td-brand-color); transform: translateY(-1px); }
.action-card.primary {
  background: linear-gradient(135deg, var(--td-brand-color) 0%, #7c3aed 100%);
  color: #fff; border: none;
}
.action-card.primary .action-desc { color: rgba(255,255,255,.7); }
.action-icon { font-size: 24px; margin-bottom: 8px; }
.action-title { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
.action-desc { font-size: 12px; color: var(--td-text-color-secondary); }

.skill-banner {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 24px; border-radius: 14px; margin-bottom: 12px;
  background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%);
  border: 1px solid #91caff; flex-wrap: wrap; gap: 12px;
}
.skill-title { font-weight: 700; font-size: 15px; margin-bottom: 4px; }
.skill-desc { font-size: 13px; color: var(--td-text-color-secondary); }
.skill-actions { display: flex; gap: 8px; flex-shrink: 0; }
.command-preview {
  background: rgba(0,0,0,.04); border-radius: 8px; padding: 12px;
  font-family: monospace; font-size: 12px; line-height: 1.6;
  word-break: break-all; margin-bottom: 20px;
}

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 8px; }
.section-card {
  padding: 20px; border-radius: 14px; background: #fff;
  border: 1px solid var(--td-component-stroke);
}
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.section-title { font-size: 16px; font-weight: 700; }

.hotspot-list { display: flex; flex-direction: column; gap: 8px; }
.hotspot-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 10px; cursor: pointer;
  border: 1px solid transparent; transition: all .15s;
}
.hotspot-item:hover { border-color: var(--td-component-stroke); background: #fafbfc; }
.hotspot-rank { font-size: 13px; font-weight: 700; color: var(--td-text-color-placeholder); min-width: 28px; }
.hotspot-info { flex: 1; min-width: 0; }
.hotspot-title { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hotspot-meta { display: flex; gap: 8px; align-items: center; margin-top: 4px; font-size: 12px; color: var(--td-text-color-secondary); }

.draft-list { display: flex; flex-direction: column; gap: 6px; }
.draft-item {
  padding: 10px 12px; border-radius: 10px; cursor: pointer;
  border: 1px solid transparent; transition: all .15s;
}
.draft-item:hover { border-color: var(--td-component-stroke); background: #fafbfc; }
.draft-title { font-size: 14px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.draft-meta { font-size: 12px; color: var(--td-text-color-placeholder); margin-top: 4px; }

.empty-hint { text-align: center; padding: 32px 0; color: var(--td-text-color-placeholder); font-size: 13px; }

@media (max-width: 900px) {
  .stat-row, .quick-actions { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
}
</style>
