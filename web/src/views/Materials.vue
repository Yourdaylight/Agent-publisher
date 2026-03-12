<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
      <h3 style="margin: 0">素材库</h3>
      <t-button theme="primary" @click="showUploadDialog = true">
        <template #icon><t-icon name="upload" /></template>
        手动上传
      </t-button>
    </div>

    <t-card :bordered="true" style="margin-bottom: 16px">
      <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end">
        <div style="min-width: 160px">
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">Agent</div>
          <t-select v-model="filters.agent_id" placeholder="全部 Agent" clearable @change="fetchData">
            <t-option v-for="a in agents" :key="a.id" :value="a.id" :label="a.name" />
          </t-select>
        </div>
        <div style="min-width: 140px">
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">来源类型</div>
          <t-select v-model="filters.source_type" placeholder="全部类型" clearable @change="fetchData">
            <t-option value="rss" label="RSS" />
            <t-option value="search" label="网络搜索" />
            <t-option value="skills_feed" label="Skills 供稿" />
            <t-option value="manual" label="手动上传" />
          </t-select>
        </div>
        <div style="min-width: 120px">
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">状态</div>
          <t-select v-model="filters.status" placeholder="全部状态" clearable @change="fetchData">
            <t-option value="pending" label="待处理" />
            <t-option value="accepted" label="已采纳" />
            <t-option value="rejected" label="已拒绝" />
          </t-select>
        </div>
        <div style="min-width: 200px">
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">标签筛选</div>
          <t-input v-model="filters.tags" placeholder="输入标签，逗号分隔" clearable @change="fetchData" />
        </div>
        <t-button variant="outline" @click="resetFilters">重置</t-button>
      </div>
    </t-card>

    <t-card v-if="!loading && materials.length === 0" :bordered="true" style="text-align: center; padding: 60px 0">
      <t-icon name="folder-open" size="48px" style="color: var(--td-text-color-placeholder); margin-bottom: 16px" />
      <div style="font-size: 16px; color: var(--td-text-color-secondary); margin-bottom: 8px">素材库为空</div>
      <div style="font-size: 14px; color: var(--td-text-color-placeholder); margin-bottom: 24px">
        可以通过 Agent 自动采集或手动上传来获取素材
      </div>
      <t-space>
        <t-button theme="primary" @click="showUploadDialog = true">手动上传素材</t-button>
        <t-button variant="outline" @click="$router.push('/agents')">配置 Agent 采集</t-button>
      </t-space>
    </t-card>

    <t-table v-else :data="materials" :columns="columns" row-key="id" :loading="loading" stripe
      :pagination="pagination" @page-change="onPageChange">
      <template #source_type="{ row }">
        <t-tag :theme="sourceTypeTheme(row.source_type)" variant="light" size="small">
          {{ sourceTypeLabel(row.source_type) }}
        </t-tag>
      </template>
      <template #tags="{ row }">
        <t-space size="4px" v-if="row.tags && row.tags.length">
          <t-tag v-for="tag in row.tags.slice(0, 3)" :key="tag" size="small" variant="outline">{{ tag }}</t-tag>
          <t-tag v-if="row.tags.length > 3" size="small" variant="light">+{{ row.tags.length - 3 }}</t-tag>
        </t-space>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #status="{ row }">
        <t-tag :theme="statusTheme(row.status)" variant="light" size="small">{{ statusLabel(row.status) }}</t-tag>
      </template>
      <template #quality_score="{ row }">
        <span v-if="row.quality_score != null">{{ row.quality_score.toFixed(2) }}</span>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #created_at="{ row }">{{ formatDate(row.created_at) }}</template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openDetail(row)">详情</t-link>
          <t-link theme="primary" @click="openTagEditor(row)">标签</t-link>
        </t-space>
      </template>
    </t-table>

    <t-dialog v-model:visible="showUploadDialog" header="手动上传素材" :footer="false" width="600px">
      <t-form :data="uploadForm" @submit="onUpload" layout="vertical">
        <t-form-item label="标题" name="title" :rules="[{ required: true, message: '请输入标题' }]">
          <t-input v-model="uploadForm.title" placeholder="输入素材标题" />
        </t-form-item>
        <t-form-item label="内容" name="content">
          <t-textarea v-model="uploadForm.content" placeholder="输入素材内容" :autosize="{ minRows: 4, maxRows: 10 }" />
        </t-form-item>
        <t-form-item label="原始链接" name="original_url">
          <t-input v-model="uploadForm.original_url" placeholder="https://..." />
        </t-form-item>
        <t-form-item label="标签" name="tags">
          <t-input v-model="uploadForm.tagsInput" placeholder="输入标签，逗号分隔" />
        </t-form-item>
        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit" :loading="uploading">上传</t-button>
            <t-button variant="outline" @click="showUploadDialog = false">取消</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-dialog>

    <t-drawer v-model:visible="showDetail" :header="detailMaterial?.title || '素材详情'" size="600px">
      <template v-if="detailMaterial">
        <t-descriptions :column="1" bordered>
          <t-descriptions-item label="ID">{{ detailMaterial.id }}</t-descriptions-item>
          <t-descriptions-item label="来源类型">
            <t-tag :theme="sourceTypeTheme(detailMaterial.source_type)" variant="light" size="small">
              {{ sourceTypeLabel(detailMaterial.source_type) }}
            </t-tag>
          </t-descriptions-item>
          <t-descriptions-item label="来源标识">{{ detailMaterial.source_identity || '-' }}</t-descriptions-item>
          <t-descriptions-item label="状态">
            <t-tag :theme="statusTheme(detailMaterial.status)" variant="light">{{ statusLabel(detailMaterial.status) }}</t-tag>
          </t-descriptions-item>
          <t-descriptions-item label="质量分">{{ detailMaterial.quality_score ?? '-' }}</t-descriptions-item>
          <t-descriptions-item label="重复">{{ detailMaterial.is_duplicate ? '是' : '否' }}</t-descriptions-item>
          <t-descriptions-item label="原始链接">
            <a v-if="detailMaterial.original_url" :href="detailMaterial.original_url" target="_blank">{{ detailMaterial.original_url }}</a>
            <span v-else>-</span>
          </t-descriptions-item>
          <t-descriptions-item label="采集时间">{{ formatDate(detailMaterial.created_at) }}</t-descriptions-item>
        </t-descriptions>
        <div style="margin-top: 16px">
          <div style="font-weight: 600; margin-bottom: 8px">标签</div>
          <t-space size="4px" v-if="detailMaterial.tags && detailMaterial.tags.length">
            <t-tag v-for="tag in detailMaterial.tags" :key="tag" size="small" closable @close="removeDetailTag(tag)">{{ tag }}</t-tag>
          </t-space>
          <span v-else style="color: var(--td-text-color-placeholder)">无标签</span>
          <div style="margin-top: 8px; display: flex; gap: 8px">
            <t-input v-model="newTagInput" placeholder="添加标签" size="small" style="width: 150px" @enter="addDetailTag" />
            <t-button size="small" @click="addDetailTag">添加</t-button>
          </div>
        </div>
        <div style="margin-top: 16px">
          <div style="font-weight: 600; margin-bottom: 8px">摘要</div>
          <div style="color: var(--td-text-color-secondary); line-height: 1.6">{{ detailMaterial.summary || '无摘要' }}</div>
        </div>
        <div style="margin-top: 16px">
          <div style="font-weight: 600; margin-bottom: 8px">完整内容</div>
          <t-card :bordered="true" style="max-height: 300px; overflow-y: auto">
            <pre style="white-space: pre-wrap; font-size: 13px; margin: 0">{{ detailMaterial.raw_content || '无内容' }}</pre>
          </t-card>
        </div>
        <div v-if="detailMaterial.metadata" style="margin-top: 16px">
          <div style="font-weight: 600; margin-bottom: 8px">元数据</div>
          <t-card :bordered="true">
            <pre style="white-space: pre-wrap; font-size: 12px; margin: 0">{{ JSON.stringify(detailMaterial.metadata, null, 2) }}</pre>
          </t-card>
        </div>
      </template>
    </t-drawer>

    <t-dialog v-model:visible="showTagEditor" header="管理标签" :footer="false" width="500px">
      <template v-if="tagEditMaterial">
        <div style="margin-bottom: 12px">
          <div style="font-weight: 600; margin-bottom: 8px">当前标签</div>
          <t-space size="4px" v-if="tagEditMaterial.tags && tagEditMaterial.tags.length">
            <t-tag v-for="tag in tagEditMaterial.tags" :key="tag" closable @close="removeTag(tag)">{{ tag }}</t-tag>
          </t-space>
          <span v-else style="color: var(--td-text-color-placeholder)">无标签</span>
        </div>
        <div style="display: flex; gap: 8px">
          <t-input v-model="tagEditorInput" placeholder="输入新标签" @enter="addTag" />
          <t-button theme="primary" @click="addTag">添加</t-button>
        </div>
      </template>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue';
import { getMaterials, getMaterial, uploadMaterial, updateMaterialTags, getAgents } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const materials = ref<any[]>([]);
const agents = ref<any[]>([]);
const total = ref(0);

const filters = reactive({
  agent_id: undefined as number | undefined,
  source_type: undefined as string | undefined,
  status: undefined as string | undefined,
  tags: '',
  page: 1,
  page_size: 20,
});

const pagination = computed(() => ({
  current: filters.page,
  pageSize: filters.page_size,
  total: total.value,
  showJumper: true,
  showSizeChanger: true,
  pageSizeOptions: [10, 20, 50],
}));

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'source_type', title: '来源', width: 100 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'tags', title: '标签', width: 200 },
  { colKey: 'quality_score', title: '质量分', width: 80 },
  { colKey: 'status', title: '状态', width: 80 },
  { colKey: 'created_at', title: '采集时间', width: 160 },
  { colKey: 'op', title: '操作', width: 120 },
];

const showUploadDialog = ref(false);
const uploading = ref(false);
const uploadForm = reactive({ title: '', content: '', original_url: '', tagsInput: '' });

const showDetail = ref(false);
const detailMaterial = ref<any>(null);
const newTagInput = ref('');

const showTagEditor = ref(false);
const tagEditMaterial = ref<any>(null);
const tagEditorInput = ref('');

const sourceTypeLabel = (type: string) => {
  const map: Record<string, string> = { rss: 'RSS', search: '搜索', skills_feed: 'Skills', manual: '手动' };
  return map[type] || type;
};
const sourceTypeTheme = (type: string): string => {
  const map: Record<string, string> = { rss: 'primary', search: 'warning', skills_feed: 'success', manual: 'default' };
  return map[type] || 'default';
};
const statusLabel = (status: string) => {
  const map: Record<string, string> = { pending: '待处理', accepted: '已采纳', rejected: '已拒绝' };
  return map[status] || status;
};
const statusTheme = (status: string): string => {
  const map: Record<string, string> = { pending: 'warning', accepted: 'success', rejected: 'danger' };
  return map[status] || 'default';
};
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString('zh-CN');
};

const fetchData = async () => {
  loading.value = true;
  try {
    const params: Record<string, any> = { page: filters.page, page_size: filters.page_size };
    if (filters.agent_id) params.agent_id = filters.agent_id;
    if (filters.source_type) params.source_type = filters.source_type;
    if (filters.status) params.status = filters.status;
    if (filters.tags) params.tags = filters.tags;
    const res = await getMaterials(params);
    materials.value = res.data.items;
    total.value = res.data.total;
  } catch { MessagePlugin.error('加载素材失败'); }
  finally { loading.value = false; }
};

const resetFilters = () => {
  filters.agent_id = undefined;
  filters.source_type = undefined;
  filters.status = undefined;
  filters.tags = '';
  filters.page = 1;
  fetchData();
};

const onPageChange = (pageInfo: { current: number; pageSize: number }) => {
  filters.page = pageInfo.current;
  filters.page_size = pageInfo.pageSize;
  fetchData();
};

const onUpload = async () => {
  if (!uploadForm.title.trim()) { MessagePlugin.warning('请输入标题'); return; }
  uploading.value = true;
  try {
    const tags = uploadForm.tagsInput ? uploadForm.tagsInput.split(',').map(t => t.trim()).filter(Boolean) : [];
    await uploadMaterial({ title: uploadForm.title, content: uploadForm.content, original_url: uploadForm.original_url, tags });
    MessagePlugin.success('上传成功');
    showUploadDialog.value = false;
    uploadForm.title = ''; uploadForm.content = ''; uploadForm.original_url = ''; uploadForm.tagsInput = '';
    fetchData();
  } catch { MessagePlugin.error('上传失败'); }
  finally { uploading.value = false; }
};

const openDetail = async (row: any) => {
  try {
    const res = await getMaterial(row.id);
    detailMaterial.value = res.data;
    showDetail.value = true;
  } catch { MessagePlugin.error('加载详情失败'); }
};

const addDetailTag = async () => {
  const tag = newTagInput.value.trim();
  if (!tag || !detailMaterial.value) return;
  try {
    const res = await updateMaterialTags(detailMaterial.value.id, { add_tags: [tag] });
    detailMaterial.value = res.data;
    newTagInput.value = '';
    fetchData();
  } catch { MessagePlugin.error('添加标签失败'); }
};

const removeDetailTag = async (tag: string) => {
  if (!detailMaterial.value) return;
  try {
    const res = await updateMaterialTags(detailMaterial.value.id, { remove_tags: [tag] });
    detailMaterial.value = res.data;
    fetchData();
  } catch { MessagePlugin.error('移除标签失败'); }
};

const openTagEditor = (row: any) => {
  tagEditMaterial.value = { ...row };
  tagEditorInput.value = '';
  showTagEditor.value = true;
};

const addTag = async () => {
  const tag = tagEditorInput.value.trim();
  if (!tag || !tagEditMaterial.value) return;
  try {
    const res = await updateMaterialTags(tagEditMaterial.value.id, { add_tags: [tag] });
    tagEditMaterial.value = res.data;
    tagEditorInput.value = '';
    fetchData();
  } catch { MessagePlugin.error('添加标签失败'); }
};

const removeTag = async (tag: string) => {
  if (!tagEditMaterial.value) return;
  try {
    const res = await updateMaterialTags(tagEditMaterial.value.id, { remove_tags: [tag] });
    tagEditMaterial.value = res.data;
    fetchData();
  } catch { MessagePlugin.error('移除标签失败'); }
};

onMounted(async () => {
  try { const r = await getAgents(); agents.value = r.data; } catch {}
  fetchData();
});
</script>
