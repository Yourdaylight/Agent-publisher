<template>
  <div>
    <div style="display: flex; gap: 16px; margin-bottom: 24px">
      <t-card v-for="card in statCards" :key="card.label" style="flex: 1" :bordered="true">
        <div style="text-align: center">
          <div style="font-size: 32px; font-weight: 700; color: var(--td-brand-color)">{{ card.value }}</div>
          <div style="color: var(--td-text-color-secondary); margin-top: 4px">{{ card.label }}</div>
        </div>
      </t-card>
    </div>

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
import { ref, onMounted, h } from 'vue'
import { getStats, getArticles } from '@/api'

const stats = ref({ agents: 0, articles: 0, tasks: 0, accounts: 0 })
const articles = ref<any[]>([])

const statCards = ref([
  { label: '公众号', value: 0 },
  { label: 'Agent', value: 0 },
  { label: '文章', value: 0 },
  { label: '任务', value: 0 },
])

const articleCols = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
]

onMounted(async () => {
  try {
    const res = await getStats()
    stats.value = res.data
    statCards.value = [
      { label: '公众号', value: res.data.accounts },
      { label: 'Agent', value: res.data.agents },
      { label: '文章', value: res.data.articles },
      { label: '任务', value: res.data.tasks },
    ]
  } catch {}

  try {
    const res = await getArticles()
    articles.value = res.data.slice(0, 10)
  } catch {}
})
</script>
