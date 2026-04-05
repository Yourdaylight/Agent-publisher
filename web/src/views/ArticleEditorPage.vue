<template>
  <t-loading :loading="loading" style="display: block">
    <t-card :bordered="true" style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap">
        <div>
          <div style="font-size: 22px; font-weight: 700; margin-bottom: 6px">文章在线编辑</div>
          <div style="font-size: 13px; color: var(--td-text-color-secondary)">
            把 AI 草稿升级为可发布内容：支持 TipTap 富文本编辑、Markdown 渲染预览、HTML 源码校正。
          </div>
        </div>
        <t-space>
          <t-button variant="outline" @click="goBack">返回文章列表</t-button>
          <t-button variant="outline" :loading="renderLoading" @click="renderMarkdownPreview">渲染 Markdown 预览</t-button>
          <t-button theme="primary" :loading="saving" @click="saveArticle">保存内容</t-button>
          <t-button v-if="form.status === 'published'" theme="warning" :loading="syncing" @click="saveAndSync">保存并同步</t-button>
        </t-space>
      </div>
    </t-card>

    <t-row :gutter="16">
      <t-col :span="6">
        <t-card title="文章信息" :bordered="true">
          <t-form layout="vertical">
            <t-form-item label="标题">
              <t-input v-model="form.title" placeholder="文章标题" />
            </t-form-item>
            <t-form-item label="摘要">
              <t-textarea v-model="form.digest" :autosize="{ minRows: 3, maxRows: 6 }" placeholder="公众号摘要" />
            </t-form-item>
            <t-form-item label="封面图 URL">
              <t-input v-model="form.cover_image_url" placeholder="封面图 URL" />
            </t-form-item>
            <div v-if="form.cover_image_url" style="margin-bottom: 16px">
              <img :src="form.cover_image_url" alt="cover" style="width: 100%; border-radius: 8px; border: 1px solid var(--td-border-level-1-color)" />
            </div>
            <t-descriptions :column="1" bordered size="small">
              <t-descriptions-item label="文章 ID">{{ form.id || '-' }}</t-descriptions-item>
              <t-descriptions-item label="状态">{{ form.status === 'published' ? '已发布' : '草稿' }}</t-descriptions-item>
              <t-descriptions-item label="编辑模式">{{ modeLabelMap[editMode] }}</t-descriptions-item>
            </t-descriptions>
          </t-form>
        </t-card>
      </t-col>

      <t-col :span="18">
        <t-card :bordered="true">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap">
              <t-radio-group v-model="activeTab" variant="default-filled" size="small">
                <t-radio-button value="rich">TipTap 富文本</t-radio-button>
                <t-radio-button value="markdown">Markdown</t-radio-button>
                <t-radio-button value="html">HTML 源码</t-radio-button>
                <t-radio-button value="preview">实时预览</t-radio-button>
              </t-radio-group>
              <div style="font-size: 12px; color: var(--td-text-color-secondary)">
                当前保存源：{{ modeLabelMap[editMode] }}
              </div>
            </div>
          </template>

          <div v-show="activeTab === 'rich'">
            <TiptapEditor v-model="richHtml" placeholder="在这里对文章进行富文本精修" />
          </div>

          <div v-show="activeTab === 'markdown'">
            <div style="margin-bottom: 8px; font-size: 12px; color: var(--td-text-color-secondary)">
              适合对 AI 原始 Markdown 做结构化修改。保存时会更新 <code>content</code>，渲染时自动生成新的 HTML。
            </div>
            <textarea v-model="form.content" class="editor-textarea" placeholder="Markdown 内容" @input="markMode('markdown')" />
          </div>

          <div v-show="activeTab === 'html'">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 12px; flex-wrap: wrap">
              <div style="font-size: 12px; color: var(--td-text-color-secondary)">
                适合对最终发布样式做微调。点击“应用到预览”会同步到 TipTap 与实时预览。
              </div>
              <t-button size="small" variant="outline" @click="applyHtmlSource">应用到预览</t-button>
            </div>
            <textarea v-model="htmlSource" class="editor-textarea" placeholder="HTML 内容" @input="markMode('html')" />
          </div>

          <div v-show="activeTab === 'preview'" class="preview-shell">
            <div v-if="previewHtml" v-html="previewHtml" />
            <t-empty v-else description="暂无预览内容" />
          </div>
        </t-card>
      </t-col>
    </t-row>
  </t-loading>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import TiptapEditor from '@/components/TiptapEditor.vue';
import { getArticle, syncArticle, updateArticle } from '@/api';

interface EditForm {
  id: number | null;
  title: string;
  digest: string;
  content: string;
  html_content: string;
  cover_image_url: string;
  status: string;
}

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const saving = ref(false);
const syncing = ref(false);
const renderLoading = ref(false);
const activeTab = ref<'rich' | 'markdown' | 'html' | 'preview'>('rich');
const editMode = ref<'rich' | 'markdown' | 'html'>('rich');
const richHtml = ref('');
const htmlSource = ref('');

const modeLabelMap: Record<'rich' | 'markdown' | 'html', string> = {
  rich: 'TipTap 富文本',
  markdown: 'Markdown',
  html: 'HTML 源码',
};

const form = ref<EditForm>({
  id: null,
  title: '',
  digest: '',
  content: '',
  html_content: '',
  cover_image_url: '',
  status: 'draft',
});

const articleId = computed(() => Number(route.params.id));
const previewHtml = computed(() => {
  if (editMode.value === 'markdown') {
    return form.value.html_content || '';
  }
  if (editMode.value === 'html') {
    return htmlSource.value || '';
  }
  return richHtml.value || form.value.html_content || '';
});

const markMode = (mode: 'rich' | 'markdown' | 'html') => {
  editMode.value = mode;
};

watch(richHtml, () => {
  if (activeTab.value === 'rich') {
    editMode.value = 'rich';
  }
});

const fetchArticle = async () => {
  if (!articleId.value || Number.isNaN(articleId.value)) {
    MessagePlugin.error('文章 ID 无效');
    router.replace('/articles');
    return;
  }
  loading.value = true;
  try {
    const res = await getArticle(articleId.value);
    const article = res.data;
    form.value = {
      id: article.id,
      title: article.title || '',
      digest: article.digest || '',
      content: article.content || '',
      html_content: article.html_content || '',
      cover_image_url: article.cover_image_url || '',
      status: article.status || 'draft',
    };
    richHtml.value = article.html_content || '<p></p>';
    htmlSource.value = article.html_content || '';
    editMode.value = article.html_content ? 'rich' : 'markdown';
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '加载文章失败');
    router.replace('/articles');
  } finally {
    loading.value = false;
  }
};

const buildPayload = () => {
  const payload: Record<string, any> = {
    title: form.value.title,
    digest: form.value.digest,
    cover_image_url: form.value.cover_image_url,
  };
  if (editMode.value === 'markdown') {
    payload.content = form.value.content;
  } else if (editMode.value === 'html') {
    payload.html_content = htmlSource.value;
  } else {
    payload.html_content = richHtml.value;
  }
  return payload;
};

const saveArticle = async () => {
  if (!form.value.id) return false;
  saving.value = true;
  try {
    const res = await updateArticle(form.value.id, buildPayload());
    const updated = res.data;
    form.value.html_content = updated.html_content || form.value.html_content;
    form.value.content = updated.content || form.value.content;
    form.value.status = updated.status || form.value.status;
    richHtml.value = updated.html_content || richHtml.value;
    htmlSource.value = updated.html_content || htmlSource.value;
    MessagePlugin.success('文章已保存');
    return true;
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '保存失败');
    return false;
  } finally {
    saving.value = false;
  }
};

const renderMarkdownPreview = async () => {
  if (!form.value.id || !form.value.content) {
    MessagePlugin.warning('请先输入 Markdown 内容');
    return;
  }
  renderLoading.value = true;
  try {
    const res = await updateArticle(form.value.id, { content: form.value.content });
    form.value.html_content = res.data.html_content || '';
    richHtml.value = form.value.html_content;
    htmlSource.value = form.value.html_content;
    editMode.value = 'markdown';
    activeTab.value = 'preview';
    MessagePlugin.success('Markdown 已渲染为预览 HTML');
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '渲染失败');
  } finally {
    renderLoading.value = false;
  }
};

const applyHtmlSource = () => {
  richHtml.value = htmlSource.value;
  editMode.value = 'html';
  activeTab.value = 'preview';
  MessagePlugin.success('HTML 已应用到实时预览');
};

const saveAndSync = async () => {
  if (!form.value.id) return;
  syncing.value = true;
  try {
    const saved = await saveArticle();
    if (!saved) return;
    await syncArticle(form.value.id);
    MessagePlugin.success('已保存并同步到微信草稿箱');
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '同步失败');
  } finally {
    syncing.value = false;
  }
};

const goBack = () => router.push('/articles');

onMounted(fetchArticle);
</script>

<style scoped>
.editor-textarea {
  width: 100%;
  min-height: 520px;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--td-border-level-2-color);
  background: var(--td-bg-color-container);
  color: var(--td-text-color-primary);
  line-height: 1.8;
  font-size: 14px;
  box-sizing: border-box;
  resize: vertical;
}

.preview-shell {
  min-height: 520px;
  padding: 16px;
  border: 1px solid var(--td-border-level-2-color);
  border-radius: 8px;
  background: var(--td-bg-color-container);
  line-height: 1.8;
}

.preview-shell :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}
</style>
