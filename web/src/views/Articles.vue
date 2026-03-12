<template>
  <div>
    <!-- Running tasks section -->
    <div v-if="runningTasks.length > 0" style="margin-bottom: 20px">
      <h3 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px">
        <t-loading size="small" />
        生成中的任务（{{ runningTasks.length }}）
      </h3>
      <div style="display: flex; gap: 12px; flex-wrap: wrap">
        <t-card v-for="task in runningTasks" :key="task.id" style="width: 320px" :bordered="true" hover-shadow>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>任务 #{{ task.id }}</span>
              <t-tag theme="warning" variant="light">
                {{ task.status === 'pending' ? '等待中' : '生成中' }}
              </t-tag>
            </div>
          </template>
          <div style="font-size: 13px; color: var(--td-text-color-secondary)">
            <p>Agent ID: {{ task.agent_id }}</p>
            <p v-if="task.steps && task.steps.length > 0">
              当前步骤: {{ stepNameMap[task.steps[task.steps.length - 1].name] || task.steps[task.steps.length - 1].name }}
            </p>
            <p v-else>准备中...</p>
            <t-progress
              :percentage="getTaskProgress(task)"
              :status="task.status === 'running' ? 'active' : 'warning'"
              style="margin-top: 8px"
            />
          </div>
        </t-card>
      </div>
    </div>

    <div style="display: flex; gap: 12px; margin-bottom: 16px">
      <t-select v-model="filterAgentId" placeholder="筛选 Agent" clearable style="width: 200px" @change="fetchData">
        <t-option v-for="a in agentOptions" :key="a.id" :label="a.name" :value="a.id" />
      </t-select>
      <t-select v-model="filterStatus" placeholder="筛选状态" clearable style="width: 160px" @change="fetchData">
        <t-option label="草稿" value="draft" />
        <t-option label="已发布" value="published" />
      </t-select>
    </div>

    <t-table :data="articles" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #status="{ row }">
        <t-tag :theme="row.status === 'published' ? 'success' : 'default'" variant="light">
          {{ row.status === 'published' ? '已发布' : '草稿' }}
        </t-tag>
      </template>
      <template #publish_count="{ row }">
        <t-link v-if="row.publish_count > 0" theme="primary" @click="openPublishRecords(row)">
          {{ row.publish_count }}
        </t-link>
        <span v-else style="color: var(--td-text-color-placeholder)">0</span>
      </template>
      <template #title="{ row }">
        <div style="display: flex; align-items: center; gap: 6px">
          <span>{{ row.title }}</span>
          <t-tag v-if="row.variant_style" size="small" theme="primary" variant="light">
            🏷 {{ getStyleName(row.variant_style) }}
          </t-tag>
        </div>
      </template>
      <template #variant_count="{ row }">
        <t-link v-if="row.variant_count > 0" theme="primary" @click="openVariants(row)">
          {{ row.variant_count }}
        </t-link>
        <span v-else style="color: var(--td-text-color-placeholder)">0</span>
      </template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openPreview(row)">预览</t-link>
          <t-link theme="primary" @click="openEditor(row)">编辑</t-link>
          <t-link theme="primary" @click="openVariantDialog(row)">生成变体</t-link>
          <t-link v-if="row.status !== 'published'" theme="primary" @click="onPublish(row)">发布</t-link>
          <t-link v-if="row.status === 'published'" theme="primary" @click="onSync(row)">
            同步草稿
          </t-link>
          <t-link theme="primary" @click="openPublishRecords(row)">发布记录</t-link>
        </t-space>
      </template>
    </t-table>

    <!-- Variant Generation Dialog -->
    <t-dialog
      v-model:visible="variantDialogVisible"
      header="生成文章变体"
      :width="720"
      :footer="false"
    >
      <div v-if="variantSourceArticle">
        <t-card :bordered="true" style="margin-bottom: 16px">
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 4px">源文章</div>
          <div style="font-weight: bold; font-size: 15px">{{ variantSourceArticle.title }}</div>
          <div v-if="variantSourceArticle.digest" style="color: var(--td-text-color-secondary); margin-top: 4px; font-size: 13px">
            {{ variantSourceArticle.digest }}
          </div>
        </t-card>

        <div style="margin-bottom: 16px">
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 8px; display: flex; align-items: center; gap: 8px">
            <span>选择风格预设</span>
            <t-link theme="primary" size="small" @click="styleManagerVisible = true">管理风格预设</t-link>
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 8px">
            <div
              v-for="style in stylePresets"
              :key="style.style_id"
              :class="['style-card', { 'style-card-selected': selectedStyles.includes(style.style_id) }]"
              @click="toggleStyle(style.style_id)"
            >
              <div style="display: flex; justify-content: space-between; align-items: center">
                <t-checkbox :checked="selectedStyles.includes(style.style_id)" @click.stop>
                  <span style="font-weight: bold">{{ style.name }}</span>
                </t-checkbox>
                <t-link size="small" theme="primary" @click.stop="toggleStylePrompt(style.style_id)">
                  {{ expandedStyles.includes(style.style_id) ? '收起' : '编辑Prompt' }}
                </t-link>
              </div>
              <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">
                {{ style.description }}
              </div>
              <div v-if="expandedStyles.includes(style.style_id)" style="margin-top: 8px">
                <t-textarea
                  v-model="style.prompt"
                  :autosize="{ minRows: 3, maxRows: 8 }"
                  placeholder="改写提示词模板"
                  style="font-size: 12px"
                />
                <t-button
                  size="small"
                  theme="primary"
                  variant="outline"
                  style="margin-top: 4px"
                  :loading="style._saving"
                  @click.stop="saveStylePrompt(style)"
                >
                  保存 Prompt
                </t-button>
              </div>
            </div>
          </div>
        </div>

        <div style="margin-bottom: 16px">
          <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 8px">选择目标 Agent（公众号）</div>
          <t-checkbox-group v-model="selectedAgents">
            <t-checkbox v-for="a in agentOptions" :key="a.id" :value="a.id">
              {{ a.name }}（ID: {{ a.id }}）
            </t-checkbox>
          </t-checkbox-group>
        </div>

        <t-alert
          v-if="selectedAgents.length > selectedStyles.length && selectedStyles.length > 0"
          theme="info"
          style="margin-bottom: 16px"
        >
          将循环使用所选风格分配给目标公众号
        </t-alert>

        <!-- Variant task progress -->
        <div v-if="variantTaskId" style="margin-bottom: 16px">
          <t-card :bordered="true">
            <div style="font-weight: bold; margin-bottom: 8px">生成进度</div>
            <t-progress
              :percentage="variantProgress"
              :status="variantTaskStatus === 'completed' ? 'success' : variantTaskStatus === 'failed' ? 'error' : 'active'"
            />
            <div style="margin-top: 8px; font-size: 13px; color: var(--td-text-color-secondary)">
              成功: {{ variantSucceeded }} / 失败: {{ variantFailed }} / 总计: {{ variantTotal }}
            </div>
            <div v-if="variantTaskStatus === 'completed' || variantTaskStatus === 'partial_completed'" style="margin-top: 8px">
              <t-link theme="primary" @click="onVariantsDone">查看生成的变体文章 →</t-link>
            </div>
          </t-card>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px">
          <t-button variant="outline" @click="variantDialogVisible = false">关闭</t-button>
          <t-button
            theme="primary"
            :loading="variantGenerating"
            :disabled="selectedStyles.length === 0 || selectedAgents.length === 0"
            @click="onGenerateVariants"
          >
            开始生成（{{ selectedAgents.length }} 篇）
          </t-button>
        </div>
      </div>
    </t-dialog>

    <!-- Style Manager Dialog -->
    <t-dialog
      v-model:visible="styleManagerVisible"
      header="管理风格预设"
      :width="600"
      :footer="false"
    >
      <div style="margin-bottom: 12px">
        <t-button size="small" theme="primary" @click="showCreateStyle = !showCreateStyle">
          {{ showCreateStyle ? '取消' : '+ 新增自定义风格' }}
        </t-button>
      </div>
      <div v-if="showCreateStyle" style="margin-bottom: 16px; padding: 12px; border: 1px solid var(--td-border-level-2-color); border-radius: 6px">
        <t-input v-model="newStyle.style_id" placeholder="风格ID (英文)" style="margin-bottom: 8px" />
        <t-input v-model="newStyle.name" placeholder="名称 (中文)" style="margin-bottom: 8px" />
        <t-input v-model="newStyle.description" placeholder="描述" style="margin-bottom: 8px" />
        <t-textarea v-model="newStyle.prompt" placeholder="提示词模板" :autosize="{ minRows: 3, maxRows: 6 }" style="margin-bottom: 8px" />
        <t-button size="small" theme="primary" :loading="creatingStyle" @click="onCreateStyle">创建</t-button>
      </div>
      <div v-for="style in stylePresets" :key="style.style_id" style="margin-bottom: 12px; padding: 12px; border: 1px solid var(--td-border-level-2-color); border-radius: 6px">
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div>
            <span style="font-weight: bold">{{ style.name }}</span>
            <t-tag v-if="style.is_builtin" size="small" variant="light" style="margin-left: 6px">内置</t-tag>
            <span style="color: var(--td-text-color-secondary); font-size: 12px; margin-left: 8px">{{ style.style_id }}</span>
          </div>
          <t-popconfirm
            v-if="!style.is_builtin"
            content="确认删除此风格预设？"
            @confirm="onDeleteStyle(style.style_id)"
          >
            <t-link theme="danger" size="small">删除</t-link>
          </t-popconfirm>
        </div>
        <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-top: 4px">
          {{ style.description }}
        </div>
      </div>
    </t-dialog>

    <!-- Variants Drawer -->
    <t-drawer
      v-model:visible="variantsDrawerVisible"
      :header="`变体文章 - ${variantsSourceTitle}`"
      size="640px"
    >
      <t-table
        :data="variantsData"
        :columns="variantColumns"
        row-key="id"
        :loading="variantsLoading"
        stripe
        size="small"
      >
        <template #variantStyle="{ row }">
          <t-tag v-if="row.variant_style" theme="primary" variant="light" size="small">
            {{ getStyleName(row.variant_style) }}
          </t-tag>
        </template>
        <template #variantStatus="{ row }">
          <t-tag :theme="row.status === 'published' ? 'success' : 'default'" variant="light" size="small">
            {{ row.status === 'published' ? '已发布' : '草稿' }}
          </t-tag>
        </template>
      </t-table>
    </t-drawer>

    <!-- Preview drawer -->
    <t-drawer v-model:visible="previewDrawerVisible" header="文章预览" size="640px">
      <div v-if="previewArticle">
        <h2>{{ previewArticle.title }}</h2>
        <p style="color: var(--td-text-color-secondary)">{{ previewArticle.digest }}</p>
        <img
          v-if="previewArticle.cover_image_url"
          :src="previewArticle.cover_image_url"
          style="max-width: 100%; border-radius: 8px; margin: 12px 0"
        />

        <!-- Source material tracing -->
        <t-card v-if="previewArticle.source_news && previewArticle.source_news.length" :bordered="true" style="margin: 16px 0">
          <template #header>
            <div style="display: flex; align-items: center; gap: 6px">
              <t-icon name="link" />
              <span style="font-weight: 600">素材来源（{{ previewArticle.source_news.length }}）</span>
            </div>
          </template>
          <div v-for="(src, idx) in previewArticle.source_news" :key="idx" style="margin-bottom: 8px; padding: 8px; background: var(--td-bg-color-page); border-radius: 4px">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <a v-if="src.link" :href="src.link" target="_blank" style="font-weight: 500">{{ src.title }}</a>
              <span v-else style="font-weight: 500">{{ src.title }}</span>
              <t-space size="4px">
                <t-tag v-if="src.source" size="small" variant="light">{{ src.source }}</t-tag>
                <t-tag v-if="src.material_id" size="small" theme="primary" variant="outline">素材 #{{ src.material_id }}</t-tag>
              </t-space>
            </div>
          </div>
        </t-card>

        <t-divider />
        <div v-html="previewArticle.html_content" style="line-height: 1.8" />
      </div>
    </t-drawer>

    <!-- Edit drawer -->
    <t-drawer
      v-model:visible="editDrawerVisible"
      :header="`编辑文章 #${editForm.id || ''}`"
      size="900px"
      :footer="false"
      @close="onEditDrawerClose"
    >
      <div v-if="editForm.id" style="padding: 0 8px">
        <!-- Metadata section -->
        <t-card :bordered="true" style="margin-bottom: 16px">
          <div style="display: flex; gap: 16px; margin-bottom: 16px">
            <div style="flex: 1">
              <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 4px">标题</div>
              <t-input v-model="editForm.title" placeholder="文章标题" />
            </div>
            <div style="width: 140px">
              <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 4px">状态</div>
              <t-tag
                :theme="editForm.status === 'published' ? 'success' : 'default'"
                variant="light"
                style="line-height: 30px"
              >
                {{ editForm.status === 'published' ? '已发布' : '草稿' }}
              </t-tag>
            </div>
          </div>
          <div style="margin-bottom: 16px">
            <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 4px">摘要</div>
            <t-textarea
              v-model="editForm.digest"
              placeholder="文章摘要（可选）"
              :autosize="{ minRows: 2, maxRows: 4 }"
            />
          </div>
          <div>
            <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 4px">封面图 URL</div>
            <div style="display: flex; gap: 8px; align-items: flex-start">
              <t-input v-model="editForm.cover_image_url" placeholder="封面图 URL 或 /api/media/{id}/download" style="flex: 1" />
              <img
                v-if="editForm.cover_image_url"
                :src="editForm.cover_image_url"
                style="width: 60px; height: 60px; border-radius: 6px; object-fit: cover; flex-shrink: 0; border: 1px solid var(--td-border-level-2-color)"
              />
            </div>
          </div>
        </t-card>

        <!-- Content editor -->
        <t-card :bordered="true" style="margin-bottom: 16px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <t-radio-group v-model="editTab" variant="default-filled" size="small">
                <t-radio-button value="markdown">Markdown</t-radio-button>
                <t-radio-button value="html">HTML 预览 / 编辑</t-radio-button>
              </t-radio-group>
              <t-space size="small">
                <t-button
                  v-if="editTab === 'markdown'"
                  size="small"
                  variant="outline"
                  :loading="renderLoading"
                  @click="onRenderPreview"
                >
                  渲染预览
                </t-button>
              </t-space>
            </div>
          </template>

          <!-- Markdown editor tab -->
          <div v-show="editTab === 'markdown'">
            <div style="display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap">
              <t-button size="small" variant="outline" @click="insertMarkdown('**', '**')">
                <strong>B</strong>
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('*', '*')">
                <em>I</em>
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('## ', '')">
                H2
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('### ', '')">
                H3
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('- ', '')">
                列表
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('> ', '')">
                引用
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('`', '`')">
                代码
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('![alt](', ')')">
                图片
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('[', '](url)')">
                链接
              </t-button>
              <t-button size="small" variant="outline" @click="insertMarkdown('---\n', '')">
                分割线
              </t-button>
            </div>
            <textarea
              ref="markdownTextarea"
              v-model="editForm.content"
              class="markdown-editor"
              placeholder="在此输入 Markdown 内容..."
              spellcheck="false"
            />
            <div style="font-size: 12px; color: var(--td-text-color-placeholder); margin-top: 4px">
              支持标准 Markdown 语法。点击「渲染预览」可通过 wenyan 生成排版后的 HTML。
            </div>
          </div>

          <!-- HTML preview / edit tab -->
          <div v-show="editTab === 'html'">
            <div style="display: flex; gap: 8px; margin-bottom: 8px">
              <t-radio-group v-model="htmlMode" variant="default-filled" size="small">
                <t-radio-button value="preview">预览</t-radio-button>
                <t-radio-button value="source">HTML 源码</t-radio-button>
              </t-radio-group>
            </div>
            <div v-if="htmlMode === 'preview'" class="html-preview" v-html="editForm.html_content" />
            <textarea
              v-else
              v-model="editForm.html_content"
              class="html-source-editor"
              placeholder="HTML 内容（由 wenyan 渲染生成或手动编辑）"
              spellcheck="false"
            />
          </div>
        </t-card>

        <!-- Action buttons -->
        <div style="display: flex; gap: 12px; justify-content: flex-end; padding-bottom: 24px">
          <t-button variant="outline" @click="editDrawerVisible = false">取消</t-button>
          <t-button theme="primary" :loading="saving" @click="onSave">
            保存
          </t-button>
          <t-button
            v-if="editForm.status === 'published'"
            theme="warning"
            :loading="syncing"
            @click="onSyncFromEditor"
          >
            保存并同步到微信
          </t-button>
        </div>
      </div>
    </t-drawer>

    <!-- Publish Records drawer -->
    <t-drawer
      v-model:visible="publishRecordsDrawerVisible"
      :header="`发布记录 - ${publishRecordsTitle}`"
      size="640px"
    >
      <t-table
        :data="publishRecordsData"
        :columns="publishRecordColumns"
        row-key="id"
        :loading="publishRecordsLoading"
        stripe
        size="small"
      >
        <template #action="{ row }">
          <t-tag
            :theme="row.action === 'publish' ? 'primary' : 'warning'"
            variant="light"
          >
            {{ row.action === 'publish' ? '发布' : '同步' }}
          </t-tag>
        </template>
        <template #recordStatus="{ row }">
          <t-tag
            :theme="row.status === 'success' ? 'success' : 'danger'"
            variant="light"
          >
            {{ row.status === 'success' ? '成功' : '失败' }}
          </t-tag>
        </template>
      </t-table>
    </t-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';
import {
  getArticles,
  getArticle,
  updateArticle,
  syncArticle,
  getAgents,
  publishArticle,
  getRunningTasks,
  getPendingTasks,
  getArticlePublishRecords,
  getStylePresets,
  updateStylePreset,
  createStylePreset,
  deleteStylePreset,
  generateVariants,
  getArticleVariants,
  getTask,
} from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const articles = ref<any[]>([]);
const agentOptions = ref<any[]>([]);
const filterAgentId = ref<number | undefined>();
const filterStatus = ref<string | undefined>();
const previewDrawerVisible = ref(false);
const previewArticle = ref<any>(null);
const runningTasks = ref<any[]>([]);
let pollTimer: ReturnType<typeof setInterval> | null = null;

// Edit drawer state
const editDrawerVisible = ref(false);
const editTab = ref<'markdown' | 'html'>('markdown');
const htmlMode = ref<'preview' | 'source'>('preview');
const saving = ref(false);
const syncing = ref(false);
const renderLoading = ref(false);
const markdownTextarea = ref<HTMLTextAreaElement | null>(null);

// Publish records drawer state
const publishRecordsDrawerVisible = ref(false);
const publishRecordsLoading = ref(false);
const publishRecordsData = ref<any[]>([]);
const publishRecordsTitle = ref('');

// Variant generation state
const variantDialogVisible = ref(false);
const variantSourceArticle = ref<any>(null);
const stylePresets = ref<any[]>([]);
const selectedStyles = ref<string[]>([]);
const selectedAgents = ref<number[]>([]);
const expandedStyles = ref<string[]>([]);
const variantGenerating = ref(false);
const variantTaskId = ref<number | null>(null);
const variantTaskStatus = ref('');
const variantProgress = ref(0);
const variantSucceeded = ref(0);
const variantFailed = ref(0);
const variantTotal = ref(0);
let variantPollTimer: ReturnType<typeof setInterval> | null = null;

// Style manager state
const styleManagerVisible = ref(false);
const showCreateStyle = ref(false);
const creatingStyle = ref(false);
const newStyle = ref({ style_id: '', name: '', description: '', prompt: '' });

// Variants drawer state
const variantsDrawerVisible = ref(false);
const variantsLoading = ref(false);
const variantsData = ref<any[]>([]);
const variantsSourceTitle = ref('');

const publishRecordColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'action', title: '类型', width: 80 },
  { colKey: 'recordStatus', title: '状态', width: 80 },
  { colKey: 'operator', title: '操作人', width: 160 },
  { colKey: 'wechat_media_id', title: 'Media ID', ellipsis: true },
  { colKey: 'created_at', title: '时间', width: 180, cell: (_h: any, { row }: any) => row.created_at ? new Date(row.created_at).toLocaleString() : '-' },
];

interface EditForm {
  id: number | null;
  title: string;
  digest: string;
  content: string;
  html_content: string;
  cover_image_url: string;
  status: string;
}

const editForm = ref<EditForm>({
  id: null,
  title: '',
  digest: '',
  content: '',
  html_content: '',
  cover_image_url: '',
  status: 'draft',
});

const stepNameMap: Record<string, string> = {
  rss_fetch: 'RSS 抓取',
  llm_generate: 'AI 生成文章',
  image_generate: '生成封面图',
  save_article: '保存文章',
};

const getTaskProgress = (task: any): number => {
  const steps = task.steps || [];
  const totalSteps = 4;
  return Math.round((steps.length / totalSteps) * 100);
};

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'agent_id', title: 'Agent ID', width: 90 },
  { colKey: 'status', title: '状态', width: 80 },
  { colKey: 'variant_count', title: '变体', width: 70 },
  { colKey: 'publish_count', title: '发布次数', width: 90 },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
  { colKey: 'op', title: '操作', width: 400 },
];

const variantColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'variantStyle', title: '风格', width: 100 },
  { colKey: 'agent_name', title: 'Agent', width: 120 },
  { colKey: 'variantStatus', title: '状态', width: 80 },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => row.created_at ? new Date(row.created_at).toLocaleString() : '-' },
];

const getStyleName = (styleId: string): string => {
  const preset = stylePresets.value.find(s => s.style_id === styleId);
  return preset ? preset.name : styleId;
};

const fetchData = async () => {
  loading.value = true;
  try {
    const params: any = {};
    if (filterAgentId.value) {
      params.agent_id = filterAgentId.value;
    }
    if (filterStatus.value) {
      params.status = filterStatus.value;
    }
    const res = await getArticles(params);
    articles.value = res.data;
  } catch {
    // ignore
  } finally {
    loading.value = false;
  }
};

const openPreview = async (row: any) => {
  try {
    const res = await getArticle(row.id);
    previewArticle.value = res.data;
    previewDrawerVisible.value = true;
  } catch {
    // ignore
  }
};

const openEditor = async (row: any) => {
  try {
    const res = await getArticle(row.id);
    const article = res.data;
    editForm.value = {
      id: article.id,
      title: article.title || '',
      digest: article.digest || '',
      content: article.content || '',
      html_content: article.html_content || '',
      cover_image_url: article.cover_image_url || '',
      status: article.status || 'draft',
    };
    editTab.value = 'markdown';
    htmlMode.value = 'preview';
    editDrawerVisible.value = true;
  } catch {
    MessagePlugin.error('加载文章失败');
  }
};

const onEditDrawerClose = () => {
  editForm.value = {
    id: null,
    title: '',
    digest: '',
    content: '',
    html_content: '',
    cover_image_url: '',
    status: 'draft',
  };
};

const onSave = async () => {
  if (!editForm.value.id) {
    return;
  }
  saving.value = true;
  try {
    const data: any = {};
    if (editForm.value.title) {
      data.title = editForm.value.title;
    }
    if (editForm.value.digest !== undefined) {
      data.digest = editForm.value.digest;
    }
    if (editForm.value.content !== undefined) {
      data.content = editForm.value.content;
    }
    if (editForm.value.html_content !== undefined) {
      data.html_content = editForm.value.html_content;
    }
    if (editForm.value.cover_image_url !== undefined) {
      data.cover_image_url = editForm.value.cover_image_url;
    }

    const res = await updateArticle(editForm.value.id, data);
    // Update local form with server response (html_content may be re-rendered)
    const updated = res.data;
    editForm.value.html_content = updated.html_content || editForm.value.html_content;
    editForm.value.status = updated.status || editForm.value.status;
    MessagePlugin.success('保存成功');
    fetchData();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '保存失败');
  } finally {
    saving.value = false;
  }
};

const onSyncFromEditor = async () => {
  if (!editForm.value.id) {
    return;
  }
  syncing.value = true;
  try {
    // Save first, then sync
    await onSave();
    const res = await syncArticle(editForm.value.id);
    const syncStatus = res.data?.sync_status;
    if (syncStatus === 'synced') {
      MessagePlugin.success('已同步到微信草稿箱');
    } else if (syncStatus === 'skipped') {
      MessagePlugin.warning('跳过同步（文章未发布或无 media_id）');
    } else {
      MessagePlugin.info(`同步状态: ${syncStatus}`);
    }
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '同步失败');
  } finally {
    syncing.value = false;
  }
};

const onSync = async (row: any) => {
  try {
    const res = await syncArticle(row.id);
    const syncStatus = res.data?.sync_status;
    if (syncStatus === 'synced') {
      MessagePlugin.success('已同步到微信草稿箱');
    } else if (syncStatus === 'skipped') {
      MessagePlugin.warning('跳过同步（文章未发布或无 media_id）');
    } else {
      MessagePlugin.info(`同步状态: ${syncStatus}`);
    }
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '同步失败');
  }
};

const onRenderPreview = async () => {
  if (!editForm.value.id || !editForm.value.content) {
    MessagePlugin.warning('请先输入 Markdown 内容');
    return;
  }
  renderLoading.value = true;
  try {
    // Save the content (backend will auto-render via wenyan)
    const res = await updateArticle(editForm.value.id, {
      content: editForm.value.content,
    });
    const updated = res.data;
    editForm.value.html_content = updated.html_content || '';
    editTab.value = 'html';
    htmlMode.value = 'preview';
    MessagePlugin.success('Markdown 已渲染');
    fetchData();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '渲染失败');
  } finally {
    renderLoading.value = false;
  }
};

const insertMarkdown = (before: string, after: string) => {
  const textarea = markdownTextarea.value;
  if (!textarea) {
    return;
  }
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const text = editForm.value.content;
  const selected = text.slice(start, end);
  const replacement = `${before}${selected || '文本'}${after}`;
  editForm.value.content = text.slice(0, start) + replacement + text.slice(end);
  nextTick(() => {
    const cursorPos = start + before.length + (selected || '文本').length;
    textarea.setSelectionRange(cursorPos, cursorPos);
    textarea.focus();
  });
};

const onPublish = async (row: any) => {
  try {
    await publishArticle(row.id);
    MessagePlugin.success('发布成功');
    fetchData();
  } catch {
    MessagePlugin.error('发布失败');
  }
};

const openPublishRecords = async (row: any) => {
  publishRecordsTitle.value = row.title || `文章 #${row.id}`;
  publishRecordsDrawerVisible.value = true;
  publishRecordsLoading.value = true;
  try {
    const res = await getArticlePublishRecords(row.id);
    publishRecordsData.value = res.data;
  } catch {
    MessagePlugin.error('加载发布记录失败');
    publishRecordsData.value = [];
  } finally {
    publishRecordsLoading.value = false;
  }
};

// --- Variant generation functions ---

const fetchStylePresets = async () => {
  try {
    const res = await getStylePresets();
    stylePresets.value = (res.data || []).map((s: any) => ({ ...s, _saving: false }));
  } catch {
    // ignore
  }
};

const openVariantDialog = async (row: any) => {
  variantSourceArticle.value = row;
  selectedStyles.value = [];
  selectedAgents.value = [];
  expandedStyles.value = [];
  variantTaskId.value = null;
  variantTaskStatus.value = '';
  variantProgress.value = 0;
  variantSucceeded.value = 0;
  variantFailed.value = 0;
  variantTotal.value = 0;
  await fetchStylePresets();
  variantDialogVisible.value = true;
};

const toggleStyle = (styleId: string) => {
  const idx = selectedStyles.value.indexOf(styleId);
  if (idx === -1) {
    selectedStyles.value.push(styleId);
  } else {
    selectedStyles.value.splice(idx, 1);
  }
};

const toggleStylePrompt = (styleId: string) => {
  const idx = expandedStyles.value.indexOf(styleId);
  if (idx === -1) {
    expandedStyles.value.push(styleId);
  } else {
    expandedStyles.value.splice(idx, 1);
  }
};

const saveStylePrompt = async (style: any) => {
  style._saving = true;
  try {
    await updateStylePreset(style.style_id, { prompt: style.prompt });
    MessagePlugin.success(`风格「${style.name}」的 Prompt 已保存`);
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '保存失败');
  } finally {
    style._saving = false;
  }
};

const onGenerateVariants = async () => {
  if (!variantSourceArticle.value) return;
  variantGenerating.value = true;
  try {
    const res = await generateVariants(variantSourceArticle.value.id, {
      agent_ids: selectedAgents.value,
      style_ids: selectedStyles.value,
    });
    variantTaskId.value = res.data.batch_task_id;
    variantTotal.value = res.data.total;
    MessagePlugin.success('变体生成任务已提交');
    pollVariantTask();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '提交失败');
  } finally {
    variantGenerating.value = false;
  }
};

const pollVariantTask = () => {
  if (variantPollTimer) {
    clearInterval(variantPollTimer);
  }
  variantPollTimer = setInterval(async () => {
    if (!variantTaskId.value) return;
    try {
      const res = await getTask(variantTaskId.value);
      const task = res.data;
      variantTaskStatus.value = task.status;
      const result = task.result || {};
      variantSucceeded.value = result.succeeded || 0;
      variantFailed.value = result.failed || 0;
      const total = result.total || variantTotal.value;
      const completed = result.completed || 0;
      variantProgress.value = total > 0 ? Math.round((completed / total) * 100) : 0;

      if (['completed', 'partial_completed', 'failed'].includes(task.status)) {
        if (variantPollTimer) {
          clearInterval(variantPollTimer);
          variantPollTimer = null;
        }
        fetchData();
      }
    } catch {
      // ignore
    }
  }, 3000);
};

const onVariantsDone = () => {
  variantDialogVisible.value = false;
  if (variantSourceArticle.value) {
    openVariants(variantSourceArticle.value);
  }
};

const openVariants = async (row: any) => {
  variantsSourceTitle.value = row.title || `文章 #${row.id}`;
  variantsDrawerVisible.value = true;
  variantsLoading.value = true;
  try {
    const res = await getArticleVariants(row.id);
    variantsData.value = res.data;
  } catch {
    MessagePlugin.error('加载变体列表失败');
    variantsData.value = [];
  } finally {
    variantsLoading.value = false;
  }
};

// --- Style manager functions ---

const onCreateStyle = async () => {
  if (!newStyle.value.style_id || !newStyle.value.name) {
    MessagePlugin.warning('风格 ID 和名称不能为空');
    return;
  }
  creatingStyle.value = true;
  try {
    await createStylePreset(newStyle.value);
    MessagePlugin.success('自定义风格已创建');
    newStyle.value = { style_id: '', name: '', description: '', prompt: '' };
    showCreateStyle.value = false;
    await fetchStylePresets();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '创建失败');
  } finally {
    creatingStyle.value = false;
  }
};

const onDeleteStyle = async (styleId: string) => {
  try {
    await deleteStylePreset(styleId);
    MessagePlugin.success('风格已删除');
    await fetchStylePresets();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '删除失败');
  }
};

const fetchRunningTasks = async () => {
  try {
    const [runningRes, pendingRes] = await Promise.all([
      getRunningTasks(),
      getPendingTasks(),
    ]);
    const allActive = [...(pendingRes.data || []), ...(runningRes.data || [])];
    const hadTasks = runningTasks.value.length > 0;
    runningTasks.value = allActive;

    if (hadTasks && allActive.length === 0) {
      fetchData();
    }

    if (allActive.length > 0 && !pollTimer) {
      pollTimer = setInterval(fetchRunningTasks, 5000);
    } else if (allActive.length === 0 && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  } catch {
    // ignore
  }
};

onMounted(async () => {
  try {
    const res = await getAgents();
    agentOptions.value = res.data;
  } catch {
    // ignore
  }
  fetchData();
  fetchRunningTasks();
  fetchStylePresets();
});

onBeforeUnmount(() => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (variantPollTimer) {
    clearInterval(variantPollTimer);
    variantPollTimer = null;
  }
});
</script>

<style scoped>
.markdown-editor {
  width: 100%;
  min-height: 400px;
  max-height: 600px;
  padding: 12px;
  font-family: 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', monospace;
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid var(--td-border-level-2-color);
  border-radius: 6px;
  resize: vertical;
  background: var(--td-bg-color-container);
  color: var(--td-text-color-primary);
  outline: none;
  tab-size: 2;
  box-sizing: border-box;
}

.markdown-editor:focus {
  border-color: var(--td-brand-color);
  box-shadow: 0 0 0 2px rgba(0, 82, 217, 0.1);
}

.html-preview {
  min-height: 400px;
  max-height: 600px;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid var(--td-border-level-2-color);
  border-radius: 6px;
  line-height: 1.8;
  background: var(--td-bg-color-container);
}

.html-source-editor {
  width: 100%;
  min-height: 400px;
  max-height: 600px;
  padding: 12px;
  font-family: 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  border: 1px solid var(--td-border-level-2-color);
  border-radius: 6px;
  resize: vertical;
  background: var(--td-bg-color-container);
  color: var(--td-text-color-primary);
  outline: none;
  box-sizing: border-box;
}

.html-source-editor:focus {
  border-color: var(--td-brand-color);
  box-shadow: 0 0 0 2px rgba(0, 82, 217, 0.1);
}

.style-card {
  width: calc(50% - 4px);
  padding: 10px 12px;
  border: 1px solid var(--td-border-level-2-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  box-sizing: border-box;
}

.style-card:hover {
  border-color: var(--td-brand-color-light);
  background: var(--td-bg-color-container-hover);
}

.style-card-selected {
  border-color: var(--td-brand-color);
  background: var(--td-brand-color-light-hover);
}
</style>
