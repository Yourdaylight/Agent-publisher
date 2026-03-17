<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px; gap: 12px; flex-wrap: wrap; align-items: center">
      <h3 style="margin: 0">素材库</h3>
      <t-space>
        <t-button :theme="libraryMode === 'candidate' ? 'primary' : 'default'" @click="switchLibraryMode('candidate')">
          内容素材
        </t-button>
        <t-button :theme="libraryMode === 'media' ? 'primary' : 'default'" @click="switchLibraryMode('media')">
          图片素材
        </t-button>
        <t-button v-if="libraryMode === 'candidate'" theme="primary" @click="showUploadDialog = true">
          <template #icon><t-icon name="upload" /></template>
          手动上传
        </t-button>
        <t-button v-if="libraryMode === 'media'" theme="primary" @click="showMediaUploadDialog = true">
          <template #icon><t-icon name="upload" /></template>
          上传图片
        </t-button>
      </t-space>
    </div>

    <t-card :bordered="true" style="margin-bottom: 16px">
      <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end">
        <template v-if="libraryMode === 'candidate'">
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
        </template>
        <template v-else>
          <div style="min-width: 160px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">素材来源</div>
            <t-select v-model="filters.media_source_kind" placeholder="全部来源" clearable @change="fetchData">
              <t-option value="manual" label="手动上传" />
              <t-option value="article_body" label="正文图片" />
              <t-option value="article_cover" label="封面图片" />
            </t-select>
          </div>
          <div style="min-width: 180px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">公众号</div>
            <t-select v-model="filters.media_account_id" placeholder="全部公众号" clearable @change="fetchData">
              <t-option v-for="account in accounts" :key="account.id" :value="account.id" :label="account.name" />
            </t-select>
          </div>
          <div style="min-width: 160px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">上传状态</div>
            <t-select v-model="filters.media_upload_status" placeholder="全部状态" clearable @change="fetchData">
              <t-option value="pending" label="待上传" />
              <t-option value="processing" label="上传中" />
              <t-option value="success" label="已上传" />
              <t-option value="failed" label="上传失败" />
            </t-select>
          </div>
        </template>
        <div style="min-width: 200px">
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">标签筛选</div>
          <t-input v-model="filters.tags" placeholder="输入标签，逗号分隔" clearable @change="fetchData" />
        </div>
        <t-button variant="outline" @click="resetFilters">重置</t-button>
      </div>
    </t-card>

    <t-card v-if="!loading && materials.length === 0" :bordered="true" style="text-align: center; padding: 60px 0">
      <t-icon name="folder-open" size="48px" style="color: var(--td-text-color-placeholder); margin-bottom: 16px" />
      <div style="font-size: 16px; color: var(--td-text-color-secondary); margin-bottom: 8px">
        {{ libraryMode === 'candidate' ? '内容素材库为空' : '图片素材库为空' }}
      </div>
      <div style="font-size: 14px; color: var(--td-text-color-placeholder); margin-bottom: 24px">
        {{ libraryMode === 'candidate' ? '可以通过 Agent 自动采集或手动上传来获取素材' : '可以手动上传图片，或通过文章自动入库' }}
      </div>
      <t-space>
        <t-button v-if="libraryMode === 'candidate'" theme="primary" @click="showUploadDialog = true">手动上传素材</t-button>
        <t-button v-if="libraryMode === 'media'" theme="primary" @click="showMediaUploadDialog = true">上传图片</t-button>
        <t-button variant="outline" @click="$router.push('/agents')">配置 Agent 采集</t-button>
      </t-space>
    </t-card>

    <t-table
      v-else
      :data="materials"
      :columns="columns"
      row-key="id"
      :loading="loading"
      stripe
      :pagination="pagination"
      @page-change="onPageChange"
    >
      <template #source_type="{ row }">
        <t-tag :theme="sourceTypeTheme(row.source_type)" variant="light" size="small">
          {{ sourceTypeLabel(row.source_type) }}
        </t-tag>
      </template>
      <template #source_kind="{ row }">
        <t-tag :theme="mediaSourceKindTheme(row.source_kind)" variant="light" size="small">
          {{ mediaSourceKindLabel(row.source_kind) }}
        </t-tag>
      </template>
      <template #filename="{ row }">
        <div style="display: flex; align-items: center; gap: 8px">
          <img
            :src="row.url"
            :alt="row.filename"
            style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px"
          />
          <span>{{ row.filename }}</span>
        </div>
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
      <template #latest_upload_status="{ row }">
        <t-tag
          v-if="row.latest_upload_status"
          :theme="uploadStatusTheme(row.latest_upload_status)"
          variant="light"
          size="small"
        >
          {{ uploadStatusLabel(row.latest_upload_status) }}
        </t-tag>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #wechat_mapping_summary="{ row }">
        <t-space size="4px" v-if="row.wechat_mappings && row.wechat_mappings.length">
          <t-tag
            v-for="mapping in row.wechat_mappings.slice(0, 2)"
            :key="mapping.id"
            size="small"
            variant="outline"
            :theme="uploadStatusTheme(mapping.upload_status)"
          >
            {{ accountNameById(mapping.account_id) }} · {{ uploadStatusLabel(mapping.upload_status) }}
          </t-tag>
          <t-tag v-if="row.wechat_mappings.length > 2" size="small" variant="light">
            +{{ row.wechat_mappings.length - 2 }}
          </t-tag>
        </t-space>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #created_at="{ row }">{{ formatDate(row.created_at) }}</template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openDetail(row)">详情</t-link>
          <t-link v-if="libraryMode === 'candidate'" theme="primary" @click="openTagEditor(row)">标签</t-link>
          <t-link v-if="libraryMode === 'media'" theme="primary" :href="row.url" target="_blank">查看</t-link>
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

    <t-dialog v-model:visible="showMediaUploadDialog" header="上传图片素材" :footer="false" width="600px">
      <t-form :data="mediaUploadForm" @submit="onMediaUpload" layout="vertical">
        <t-form-item label="选择图片" name="file" :rules="[{ required: true, message: '请选择图片文件' }]">
          <t-upload
            v-model="mediaUploadForm.fileList"
            theme="image"
            accept="image/*"
            :auto-upload="false"
            :max="1"
            :size-limit="{ size: 20, unit: 'MB' }"
            @fail="onMediaUploadFail"
          />
        </t-form-item>
        <t-form-item label="标签" name="tags">
          <t-input v-model="mediaUploadForm.tagsInput" placeholder="输入标签，逗号分隔" />
        </t-form-item>
        <t-form-item label="描述" name="description">
          <t-textarea v-model="mediaUploadForm.description" placeholder="输入图片描述" :autosize="{ minRows: 2, maxRows: 4 }" />
        </t-form-item>
        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit" :loading="mediaUploading">上传</t-button>
            <t-button variant="outline" @click="showMediaUploadDialog = false">取消</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-dialog>

    <t-drawer v-model:visible="showDetail" :header="detailTitle" size="600px">
      <template v-if="detailMaterial">
        <template v-if="detailMode === 'candidate'">
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
        <template v-else>
          <t-descriptions :column="1" bordered>
            <t-descriptions-item label="ID">{{ detailMaterial.id }}</t-descriptions-item>
            <t-descriptions-item label="文件名">{{ detailMaterial.filename }}</t-descriptions-item>
            <t-descriptions-item label="素材来源">
              <t-tag :theme="mediaSourceKindTheme(detailMaterial.source_kind)" variant="light" size="small">
                {{ mediaSourceKindLabel(detailMaterial.source_kind) }}
              </t-tag>
            </t-descriptions-item>
            <t-descriptions-item label="文章 ID">{{ detailMaterial.article_id ?? '-' }}</t-descriptions-item>
            <t-descriptions-item label="Content-Type">{{ detailMaterial.content_type }}</t-descriptions-item>
            <t-descriptions-item label="文件大小">{{ formatFileSize(detailMaterial.file_size) }}</t-descriptions-item>
            <t-descriptions-item label="所有者">{{ detailMaterial.owner_email || '-' }}</t-descriptions-item>
            <t-descriptions-item label="原始来源">{{ detailMaterial.source_url || '-' }}</t-descriptions-item>
            <t-descriptions-item label="创建时间">{{ formatDate(detailMaterial.created_at) }}</t-descriptions-item>
          </t-descriptions>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">图片预览</div>
            <t-card :bordered="true" style="text-align: center">
              <img :src="detailMaterial.url" :alt="detailMaterial.filename" style="max-width: 100%; max-height: 360px" />
            </t-card>
          </div>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">公众号上传状态</div>
            <t-card :bordered="true">
              <t-space size="8px" direction="vertical" style="width: 100%">
                <div
                  v-for="mapping in detailMaterial.wechat_mappings || []"
                  :key="mapping.id"
                  style="display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap"
                >
                  <div>
                    <div style="font-weight: 500">{{ accountNameById(mapping.account_id) }}</div>
                    <div style="font-size: 12px; color: var(--td-text-color-secondary)">
                      公众号 ID: {{ mapping.account_id }}
                    </div>
                    <div v-if="mapping.error_message" style="font-size: 12px; color: var(--td-error-color)">
                      {{ mapping.error_message }}
                    </div>
                  </div>
                  <t-tag :theme="uploadStatusTheme(mapping.upload_status)" variant="light">
                    {{ uploadStatusLabel(mapping.upload_status) }}
                  </t-tag>
                </div>
                <span v-if="!detailMaterial.wechat_mappings || detailMaterial.wechat_mappings.length === 0" style="color: var(--td-text-color-placeholder)">
                  暂无公众号上传记录
                </span>
              </t-space>
            </t-card>
          </div>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">标签</div>
            <t-space size="4px" v-if="detailMaterial.tags && detailMaterial.tags.length">
              <t-tag v-for="tag in detailMaterial.tags" :key="tag" size="small" variant="outline">{{ tag }}</t-tag>
            </t-space>
            <span v-else style="color: var(--td-text-color-placeholder)">无标签</span>
          </div>
        </template>
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
import { computed, onMounted, reactive, ref } from 'vue';
import { getAccounts, getAgents, getMaterial, getMaterials, getMedia, getMediaDetail, updateMaterialTags, uploadMaterial, uploadMedia, deleteMedia } from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const materials = ref<any[]>([]);
const agents = ref<any[]>([]);
const accounts = ref<any[]>([]);
const total = ref(0);
const libraryMode = ref<'candidate' | 'media'>('candidate');
const detailMode = ref<'candidate' | 'media'>('candidate');

const filters = reactive({
  agent_id: undefined as number | undefined,
  source_type: undefined as string | undefined,
  media_source_kind: undefined as string | undefined,
  media_account_id: undefined as number | undefined,
  media_upload_status: undefined as string | undefined,
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

const candidateColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'source_type', title: '来源', width: 100 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'tags', title: '标签', width: 200 },
  { colKey: 'quality_score', title: '质量分', width: 80 },
  { colKey: 'status', title: '状态', width: 80 },
  { colKey: 'created_at', title: '采集时间', width: 160 },
  { colKey: 'op', title: '操作', width: 120 },
];

const mediaColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'source_kind', title: '来源', width: 120 },
  { colKey: 'filename', title: '文件', ellipsis: true },
  { colKey: 'article_id', title: '文章 ID', width: 90 },
  { colKey: 'latest_upload_status', title: '上传状态', width: 110 },
  { colKey: 'wechat_mapping_summary', title: '公众号状态', width: 260 },
  { colKey: 'tags', title: '标签', width: 180 },
  { colKey: 'created_at', title: '创建时间', width: 180 },
  { colKey: 'op', title: '操作', width: 120 },
];

const columns = computed(() => {
  return libraryMode.value === 'candidate' ? candidateColumns : mediaColumns;
});

const showUploadDialog = ref(false);
const uploading = ref(false);
const uploadForm = reactive({ title: '', content: '', original_url: '', tagsInput: '' });

const showMediaUploadDialog = ref(false);
const mediaUploading = ref(false);
const mediaUploadForm = reactive({ fileList: [] as any[], tagsInput: '', description: '' });

const showDetail = ref(false);
const detailMaterial = ref<any>(null);
const newTagInput = ref('');
const detailTitle = computed(() => {
  if (!detailMaterial.value) {
    return '素材详情';
  }
  return detailMode.value === 'candidate'
    ? detailMaterial.value.title || '素材详情'
    : detailMaterial.value.filename || '图片素材详情';
});

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

const mediaSourceKindLabel = (type: string) => {
  const map: Record<string, string> = { manual: '手动上传', article_body: '正文图片', article_cover: '封面图片' };
  return map[type] || type;
};

const mediaSourceKindTheme = (type: string): string => {
  const map: Record<string, string> = { manual: 'primary', article_body: 'success', article_cover: 'warning' };
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

const uploadStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待上传',
    processing: '上传中',
    success: '已上传',
    failed: '上传失败',
  };
  return map[status] || status || '-';
};

const uploadStatusTheme = (status: string): string => {
  const map: Record<string, string> = {
    pending: 'warning',
    processing: 'primary',
    success: 'success',
    failed: 'danger',
  };
  return map[status] || 'default';
};

const accountNameById = (accountId?: number) => {
  if (!accountId) {
    return '未知公众号';
  }
  return accounts.value.find((item) => item.id === accountId)?.name || `公众号 ${accountId}`;
};

const formatDate = (dateStr: string) => {
  if (!dateStr) {
    return '-';
  }
  return new Date(dateStr).toLocaleString('zh-CN');
};

const formatFileSize = (size: number) => {
  if (!size) {
    return '0 B';
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const fetchData = async () => {
  loading.value = true;
  try {
    if (libraryMode.value === 'candidate') {
      const params: Record<string, any> = { page: filters.page, page_size: filters.page_size };
      if (filters.agent_id) {
        params.agent_id = filters.agent_id;
      }
      if (filters.source_type) {
        params.source_type = filters.source_type;
      }
      if (filters.status) {
        params.status = filters.status;
      }
      if (filters.tags) {
        params.tags = filters.tags;
      }
      const res = await getMaterials(params);
      materials.value = res.data.items;
      total.value = res.data.total;
    } else {
      const params: Record<string, any> = { page: filters.page, page_size: filters.page_size };
      if (filters.tags) {
        params.tag = filters.tags;
      }
      if (filters.media_source_kind) {
        params.source_kind = filters.media_source_kind;
      }
      if (filters.media_account_id) {
        params.account_id = filters.media_account_id;
      }
      if (filters.media_upload_status) {
        params.upload_status = filters.media_upload_status;
      }
      const res = await getMedia(params);
      materials.value = res.data.items;
      total.value = res.data.total;
    }
  } catch {
    MessagePlugin.error(libraryMode.value === 'candidate' ? '加载素材失败' : '加载图片素材失败');
  } finally {
    loading.value = false;
  }
};

const switchLibraryMode = (mode: 'candidate' | 'media') => {
  if (libraryMode.value === mode) {
    return;
  }
  libraryMode.value = mode;
  showUploadDialog.value = false;
  showMediaUploadDialog.value = false;
  showTagEditor.value = false;
  showDetail.value = false;
  resetFilters();
};

const resetFilters = () => {
  filters.agent_id = undefined;
  filters.source_type = undefined;
  filters.media_source_kind = undefined;
  filters.media_account_id = undefined;
  filters.media_upload_status = undefined;
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
  if (!uploadForm.title.trim()) {
    MessagePlugin.warning('请输入标题');
    return;
  }
  uploading.value = true;
  try {
    const tags = uploadForm.tagsInput
      ? uploadForm.tagsInput.split(',').map((t) => t.trim()).filter(Boolean)
      : [];
    await uploadMaterial({
      title: uploadForm.title,
      content: uploadForm.content,
      original_url: uploadForm.original_url,
      tags,
    });
    MessagePlugin.success('上传成功');
    showUploadDialog.value = false;
    uploadForm.title = '';
    uploadForm.content = '';
    uploadForm.original_url = '';
    uploadForm.tagsInput = '';
    fetchData();
  } catch {
    MessagePlugin.error('上传失败');
  } finally {
    uploading.value = false;
  }
};

const onMediaUpload = async () => {
  if (!mediaUploadForm.fileList.length) {
    MessagePlugin.warning('请选择图片文件');
    return;
  }
  const fileItem = mediaUploadForm.fileList[0];
  const file = fileItem.raw || fileItem;
  if (!file) {
    MessagePlugin.warning('请选择图片文件');
    return;
  }
  mediaUploading.value = true;
  try {
    const tags = mediaUploadForm.tagsInput
      ? mediaUploadForm.tagsInput.split(',').map((t: string) => t.trim()).filter(Boolean).join(',')
      : '';
    await uploadMedia(file, tags, mediaUploadForm.description);
    MessagePlugin.success('图片上传成功');
    showMediaUploadDialog.value = false;
    mediaUploadForm.fileList = [];
    mediaUploadForm.tagsInput = '';
    mediaUploadForm.description = '';
    fetchData();
  } catch {
    MessagePlugin.error('图片上传失败');
  } finally {
    mediaUploading.value = false;
  }
};

const onMediaUploadFail = ({ file }: any) => {
  MessagePlugin.warning(`文件 ${file.name} 超过 20MB 大小限制`);
};

const openDetail = async (row: any) => {
  if (libraryMode.value === 'media') {
    detailMode.value = 'media';
    try {
      const res = await getMediaDetail(row.id);
      detailMaterial.value = res.data;
      showDetail.value = true;
    } catch {
      detailMaterial.value = row;
      showDetail.value = true;
    }
    return;
  }

  try {
    const res = await getMaterial(row.id);
    detailMode.value = 'candidate';
    detailMaterial.value = res.data;
    showDetail.value = true;
  } catch {
    MessagePlugin.error('加载详情失败');
  }
};

const addDetailTag = async () => {
  const tag = newTagInput.value.trim();
  if (!tag || !detailMaterial.value || detailMode.value !== 'candidate') {
    return;
  }
  try {
    const res = await updateMaterialTags(detailMaterial.value.id, { add_tags: [tag] });
    detailMaterial.value = res.data;
    newTagInput.value = '';
    fetchData();
  } catch {
    MessagePlugin.error('添加标签失败');
  }
};

const removeDetailTag = async (tag: string) => {
  if (!detailMaterial.value || detailMode.value !== 'candidate') {
    return;
  }
  try {
    const res = await updateMaterialTags(detailMaterial.value.id, { remove_tags: [tag] });
    detailMaterial.value = res.data;
    fetchData();
  } catch {
    MessagePlugin.error('移除标签失败');
  }
};

const openTagEditor = (row: any) => {
  if (libraryMode.value !== 'candidate') {
    return;
  }
  tagEditMaterial.value = { ...row };
  tagEditorInput.value = '';
  showTagEditor.value = true;
};

const addTag = async () => {
  const tag = tagEditorInput.value.trim();
  if (!tag || !tagEditMaterial.value) {
    return;
  }
  try {
    const res = await updateMaterialTags(tagEditMaterial.value.id, { add_tags: [tag] });
    tagEditMaterial.value = res.data;
    tagEditorInput.value = '';
    fetchData();
  } catch {
    MessagePlugin.error('添加标签失败');
  }
};

const removeTag = async (tag: string) => {
  if (!tagEditMaterial.value) {
    return;
  }
  try {
    const res = await updateMaterialTags(tagEditMaterial.value.id, { remove_tags: [tag] });
    tagEditMaterial.value = res.data;
    fetchData();
  } catch {
    MessagePlugin.error('移除标签失败');
  }
};

onMounted(async () => {
  try {
    const [agentsResponse, accountsResponse] = await Promise.all([
      getAgents(),
      getAccounts(),
    ]);
    agents.value = agentsResponse.data;
    accounts.value = accountsResponse.data;
  } catch {
    try {
      const r = await getAgents();
      agents.value = r.data;
    } catch {}
  }
  fetchData();
});
</script>
