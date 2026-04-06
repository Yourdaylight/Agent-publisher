<template>
  <div class="create-page">
    <!-- ====== 顶栏：品牌 + 话题 + 角度 + 设置 + Credits ====== -->
    <header class="topbar">
      <div class="topbar-brand">Agent Publisher</div>
      <div class="topbar-divider"></div>

      <t-select
        v-model="selectedHotspotId"
        placeholder="选择热点话题..."
        size="small"
        class="topic-select"
        :popup-props="{ overlayStyle: { width: '400px' } }"
        filterable
        @change="onHotspotChange"
      >
        <t-option v-for="item in trendingHotspots" :key="item.id" :value="item.id" :label="item.title" />
      </t-select>

      <div v-if="aiAngles.length > 0" class="angle-chips">
        <button
          v-for="(angle, idx) in aiAngles"
          :key="idx"
          type="button"
          class="angle-chip"
          :class="{ active: selectedAngleIndex === idx }"
          @click="selectAngle(idx)"
        >{{ angle }}</button>
      </div>

      <div class="topbar-right">
        <button type="button" class="icon-btn" title="设置" @click="configPanelVisible = !configPanelVisible">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
        </button>
        <span class="credits-badge">{{ credits ?? '—' }} Credits</span>
      </div>
    </header>

    <!-- 配置面板（顶栏展开） -->
    <transition name="slide-down">
      <div v-if="configPanelVisible" class="config-panel-bar">
        <div class="config-grid">
          <div class="cfg-item">
            <label>身份</label>
            <t-select v-model="selectedAgentId" placeholder="默认" size="small">
              <t-option v-for="agent in agents" :key="agent.id" :label="agentLabel(agent)" :value="agent.id" />
            </t-select>
          </div>
          <div v-if="stylePresets.length" class="cfg-item">
            <label>风格</label>
            <t-select v-model="selectedStyleId" placeholder="默认" size="small" clearable>
              <t-option v-for="style in stylePresets" :key="style.style_id" :label="style.name" :value="style.style_id" />
            </t-select>
          </div>
          <div v-if="prompts.length" class="cfg-item">
            <label>模板</label>
            <t-select v-model="selectedPromptId" placeholder="默认" size="small" clearable>
              <t-option v-for="prompt in prompts" :key="prompt.id" :label="prompt.name" :value="prompt.id" />
            </t-select>
          </div>
          <div class="cfg-item">
            <label>排版主题</label>
            <div class="theme-chips">
              <button v-for="theme in styleThemes" :key="theme.id" type="button" class="theme-chip" :class="{ active: currentStyleTheme.id === theme.id }" @click="applyStyleTheme(theme)">{{ theme.name }}</button>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- ====== 主内容区（编辑器 + 右侧面板）====== -->
    <div class="main-content">

      <!-- === 左侧编辑器面板 === -->
      <section class="editor-panel">
        <div class="editor-scroll" ref="editorScrollRef">
          <!-- 标题 -->
          <input
            v-model="form.title"
            type="text"
            class="editor-title"
            placeholder="文章标题"
          />

          <!-- 元信息行：摘要 + 封面图 -->
          <div class="editor-meta">
            <textarea
              v-model="form.digest"
              class="editor-digest"
              rows="1"
              placeholder="摘要（选填）"
            ></textarea>
            <div class="cover-row">
              <button type="button" class="cover-btn" @click="triggerCoverUpload">+ 添加封面图</button>
              <input ref="coverFileInput" type="file" accept="image/*" hidden @change="onCoverFileChange" />
              <img v-if="form.cover_image_url" :src="form.cover_image_url" alt="" class="cover-thumb" />
              <t-input
                v-if="form.cover_image_url"
                v-model="form.cover_image_url"
                placeholder="URL"
                clearable
                size="small"
                class="cover-url-mini"
              />
            </div>
          </div>

          <!-- 分割线 -->
          <div class="editor-divider"></div>

          <!-- 编辑器 Tab 切换 -->
          <div v-if="form.id" class="toolbar-tabs">
            <t-radio-group v-model="activeTab" variant="default-filled" size="small">
              <t-radio-button value="rich">富文本</t-radio-button>
              <t-radio-button value="markdown">Markdown</t-radio-button>
              <t-radio-button value="html">HTML</t-radio-button>
              <t-radio-button value="preview">预览</t-radio-button>
            </t-radio-group>
          </div>

          <!-- 编辑器内容区 -->
          <div class="editor-body-wrap" @mouseup="onEditorMouseUp">
            <!-- AI 浮动工具栏 -->
            <div
              v-show="aiFloatingBar.visible"
              class="ai-floating-bar"
              :style="{ top: aiFloatingBar.top + 'px', left: aiFloatingBar.left + 'px' }"
            >
              <button type="button" class="fbtn" @click="aiAction('rewrite')">改写</button>
              <button type="button" class="fbtn" @click="aiAction('expand')">扩写</button>
              <button type="button" class="fbtn" @click="aiAction('shorten')">缩写</button>
              <button type="button" class="fbtn fbtn-p" @click="aiAction('continue')">续写</button>
            </div>

            <!-- 富文本编辑器 -->
            <div v-show="activeTab === 'rich' || !form.id">
              <TiptapEditor ref="tiptapRef" v-model="richHtml" placeholder="开始写作，或使用右侧 AI 助手生成内容..." />
            </div>

            <!-- Markdown 模式 -->
            <div v-if="activeTab === 'markdown'" class="raw-editor-wrap">
              <textarea v-model="form.content" class="raw-editor" placeholder="Markdown..." />
            </div>

            <!-- HTML 模式 -->
            <div v-if="activeTab === 'html'" class="raw-editor-wrap">
              <textarea v-model="htmlSource" class="raw-editor" placeholder="HTML..." />
              <t-button size="small" theme="primary" style="margin-top: 8px" @click="applyHtmlToPreview">应用</t-button>
            </div>

            <!-- 预览模式 -->
            <div v-if="activeTab === 'preview'" class="preview-html-wrap">
              <div class="preview-html" v-html="previewHtml" />
            </div>
          </div>

          <!-- 字数统计 -->
          <div class="word-count">约 {{ wordCount.toLocaleString() }} 字</div>
        </div>
      </section>

      <!-- === 右侧面板（AI助手 / 微信预览）=== -->
      <aside class="side-panel">
        <div class="side-tabs">
          <button type="button" class="side-tab" :class="{ active: sideTab === 'ai' }" @click="sideTab = 'ai'">AI 助手</button>
          <button type="button" class="side-tab" :class="{ active: sideTab === 'preview' }" @click="sideTab = 'preview'">微信预览</button>
        </div>

        <div class="side-body">
          <!-- AI 助手 Tab -->
          <div v-show="sideTab === 'ai'" class="ai-section">

            <!-- 模块1: AI 生成 -->
            <div class="ai-card">
              <div class="ai-card-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                AI 生成
              </div>
              <!-- 创作模式选择 -->
              <div class="ai-prompt-label">创作模式</div>
              <div class="mode-chips">
                <button v-for="m in modeOptions" :key="m.value" type="button" class="mode-chip" :class="{ active: selectedMode === m.value }" @click="selectedMode = m.value">
                  {{ m.icon }} {{ m.label }}
                </button>
              </div>
              <div class="ai-prompt-label" style="margin-top: 10px">创作指令</div>
              <textarea
                v-model="userPrompt"
                class="ai-prompt-box"
                placeholder="描述你想写的内容...&#10;&#10;例如：用犀利的观点分析这个话题，3000字，带数据支撑，适合科技爱好者阅读"
              ></textarea>
              <button
                type="button"
                class="ai-generate-btn"
                :disabled="creating || hotspotLoading"
                @click="doAIWrite"
              >
                <span v-if="!creating && !hotspotLoading">AI 生成文章</span>
                <span v-else-if="hotspotLoading">加载话题中...</span>
                <t-loading v-else size="small" theme="dots" />
              </button>
              <div class="ai-cost">消耗 ~3 Credits · 约30秒</div>
            </div>

            <!-- 模块1b: 生成封面图 -->
            <div class="ai-card" v-if="form.id">
              <div class="ai-card-title">🖼 AI 配图</div>
              <button type="button" class="beautify-btn primary-beauty" style="width:100%" :disabled="coverGenerating" @click="doGenerateCover">
                <template v-if="!coverGenerating">
                  <span>🖼 生成封面图</span>
                  <span class="b-desc">AI 自动生成配图 · 1 Credit</span>
                </template>
                <template v-else><t-loading size="small" /> 生成中...</template>
              </button>
            </div>

            <!-- 模块2: 排版美化（高亮核心模块） -->
            <div class="ai-card beautify-card">
              <div class="ai-card-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v1m0 16v1m-7.071-2.929l.707-.707M18.364 5.636l.707-.707M3 12h1m16 0h1M5.636 5.636l-.707-.707m12.728 12.728l.707.7M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
                AI 排版美化
              </div>
              <div class="beautify-grid">
                <!-- 一键美化：全宽主按钮 -->
                <button
                  type="button"
                  class="beautify-btn primary-beauty"
                  :disabled="!form.id || aiBeautifying"
                  @click="doAIBeautify"
                >
                  <template v-if="!aiBeautifying">
                    <span>✨ 一键智能排版</span>
                    <span class="b-desc">自动优化格式、配色、间距 · ~3 Credits</span>
                  </template>
                  <template v-else><t-loading size="small" /> 处理中...</template>
                </button>
                <!-- 子操作 -->
                <button
                  type="button"
                  class="beautify-btn"
                  :disabled="!form.id || beautifying"
                  @click="doBeautify"
                >
                  <span>📐 格式修正</span>
                  <span class="b-desc">修复排版错误 · 免费</span>
                </button>
                <button type="button" class="beautify-btn" :disabled="!form.id || beautifying" @click="doBeautify">
                  <span>🎨 风格模板</span>
                  <span class="b-desc">wenyan 渲染 · 免费</span>
                </button>
              </div>
            </div>

            <!-- 模块3: 快捷操作 -->
            <div class="ai-card ai-quick-actions">
              <div class="ai-quick-label">快捷编辑</div>
              <div class="ai-quick-grid">
                <button type="button" class="ai-quick-btn" :disabled="!form.id" @click="aiAction('rewrite')">
                  <div class="btn-title">改写润色</div>
                  <div class="btn-desc">AI 优化全文 · 3 Credits</div>
                </button>
                <button type="button" class="ai-quick-btn" :disabled="!form.id" @click="aiAction('expand')">
                  <div class="btn-title">扩写段落</div>
                  <div class="btn-desc">AI 扩展内容 · 3 Credits</div>
                </button>
                <button type="button" class="ai-quick-btn" :disabled="!form.id" @click="aiAction('shorten')">
                  <div class="btn-title">缩写精简</div>
                  <div class="btn-desc">AI 压缩冗余 · 3 Credits</div>
                </button>
                <button type="button" class="ai-quick-btn" :disabled="!form.id" @click="aiGenDigest">
                  <div class="btn-title">生成摘要</div>
                  <div class="btn-desc">提取核心要点 · 1 Credit</div>
                </button>
              </div>
            </div>
          </div>

          <!-- 预览 Tab -->
          <div v-show="sideTab === 'preview'">
            <div class="phone-frame">
              <div class="phone-notch"></div>
              <div class="phone-screen">
                <div class="wx-header">
                  <div class="wx-title">{{ form.title || '文章标题预览' }}</div>
                  <div class="wx-meta">
                    <span class="wx-author">公众号名称</span> <span>{{ todayDate }}</span>
                  </div>
                </div>
                <img v-if="form.cover_image_url" :src="form.cover_image_url" class="wx-cover" />
                <div v-if="previewHtml && previewHtml !== '<p></p>'" class="wx-body" v-html="previewHtml" />
                <div v-else class="wx-empty">内容将实时显示在这里</div>
              </div>
            </div>

            <div class="drafts-section">
              <div class="drafts-title">最近草稿</div>
              <div v-if="recentDrafts.length" class="draft-list">
                <button
                  v-for="a in recentDrafts.slice(0, 6)"
                  :key="a.id"
                  type="button"
                  class="draft-item"
                  :class="{ active: form.id === a.id }"
                  @click="openDraft(a.id)"
                >{{ a.title || `草稿 #${a.id}` }}</button>
              </div>
              <div v-else class="draft-empty">还没有草稿</div>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- ====== 底栏（固定，保存 + 发布）====== -->
    <footer class="bottombar">
      <span class="bottom-hint">AI 排版 → 右侧面板</span>
      <div class="bottom-actions">
        <t-button variant="outline" size="medium" :loading="saving" :disabled="!form.id" @click="saveArticle">
          💾 保存草稿
        </t-button>
        <t-button variant="outline" size="medium" :disabled="!form.id" @click="openSlideshow">
          🎬 演示文稿
        </t-button>
        <t-button variant="outline" size="medium" :disabled="!form.id" @click="openVideoGenerate">
          🎥 生成视频
        </t-button>
        <t-button
          theme="primary"
          size="medium"
          :loading="syncing"
          :disabled="!form.id"
          @click="saveAndSync"
        >发布到微信</t-button>
      </div>
    </footer>

    <CreateArticleDialog v-model:visible="createVisible" :hotspot="selectedHotspot" :agents="agents" :style-presets="stylePresets" :prompts="prompts" :loading="creating" @submit="createArticle" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import TiptapEditor from '@/components/TiptapEditor.vue';
import CreateArticleDialog from '@/components/CreateArticleDialog.vue';
import {
  aiBeautifyArticle, createArticleFromHotspot, createArticleFromHotspotAsync,
  beautifyArticle, getAgents, getArticle, getArticles, generateVariants,
  getHotspot, getHotspots, getPromptTemplates, getStylePresets,
  syncArticle, updateArticle, uploadMedia, getMedia, getAccounts,
  getCreditsBalance, generateCoverImage, generateSlideshow, getSlideshowPreviewUrl,
} from '@/api';

interface EditForm {
  id: number | null; title: string; digest: string; content: string;
  html_content: string; cover_image_url: string; status: string;
}

interface StyleTheme { id: string; name: string; previewBg: string; }

const route = useRoute();
const router = useRouter();

// --- 状态 ---
const creating = ref(false);
const saving = ref(false);
const syncing = ref(false);
const beautifying = ref(false);
const aiBeautifying = ref(false);
const createVisible = ref(false);
const configPanelVisible = ref(false);
const showStylePicker = ref(false);
const coverGenerating = ref(false);
const hotspotLoading = ref(false);

// --- 创作模式 ---
const selectedMode = ref('rewrite');
const modeOptions = [
  { value: 'rewrite', label: '爆款二创', icon: '🔥' },
  { value: 'expand', label: '深度分析', icon: '🧠' },
  { value: 'summary', label: '热点总结', icon: '📊' },
];

// --- 数据源 ---
const selectedHotspot = ref<any>(null);
const selectedHotspotId = ref<number | undefined>(undefined);
const recentDrafts = ref<any[]>([]);
const trendingHotspots = ref<any[]>([]);
const agents = ref<any[]>([]);
const stylePresets = ref<any[]>([]);
const prompts = ref<any[]>([]);
const accounts = ref<any[]>([]);

// --- 编辑器状态 ---
const form = ref<EditForm>({ id: null, title: '', digest: '', content: '', html_content: '', cover_image_url: '', status: 'draft' });
const richHtml = ref('<p></p>');
const userPrompt = ref('');
const htmlSource = ref('');
const activeTab = ref('rich');
const editorScrollRef = ref<HTMLElement | null>(null);
const tiptapRef = ref<InstanceType<typeof TiptapEditor> | null>(null);
const coverFileInput = ref<HTMLInputElement | null>(null);
const sideTab = ref<'ai' | 'preview'>('ai');

// --- 样式主题 ---
const styleThemes: StyleTheme[] = [
  { id: 'default', name: '默认', previewBg: '#f0f5ff' },
  { id: 'business', name: '商务蓝', previewBg: '#e3f2fd' },
  { id: 'fresh', name: '清新绿', previewBg: '#e8f5e9' },
  { id: 'minimal', name: '简约黑', previewBg: '#eceff1' },
  { id: 'vivid', name: '活力橙', previewBg: '#fff3e0' },
];
const currentStyleTheme = ref<StyleTheme>(styleThemes[0]);

// --- 配置选择 ---
const selectedAgentId = ref<number | undefined>(undefined);
const selectedStyleId = ref<string | undefined>(undefined);
const selectedPromptId = ref<number | undefined>(undefined);

// --- AI 角度 ---
const aiAngles = ref<string[]>([]);
const selectedAngleIndex = ref(-1);

// --- AI 浮动工具栏 ---
const aiFloatingBar = ref({ visible: false, top: 0, left: 0, selectedText: '' });
const aiActionLoading = ref(false);

// --- SSE 生成进度 ---
const generating = ref(false);
const generationStatus = ref('');
const generationPercent = ref(0);
let activeEventSource: EventSource | null = null;

// --- Credits ---
const credits = ref<number | null>(null);
const fetchCredits = async () => {
  try { const res = await getCreditsBalance(); credits.value = res.data?.available ?? 0; } catch { credits.value = 0; }
};

const stepNameMap: Record<string, string> = {
  material_fetch: '获取素材', llm_generate: 'AI 生成中',
  save_article: '保存文章', image_generate: '生成配图',
};

// --- 计算属性 ---
const articleId = computed(() => {
  const raw = route.query.article_id;
  if (!raw) return undefined;
  const v = Number(raw);
  return Number.isNaN(v) ? undefined : v;
});
const previewHtml = computed(() => {
  // 预览/美化后模式优先用 form.html_content（保留 wenyan inline style）
  if (activeTab.value === 'preview') return form.value.html_content || richHtml.value || '';
  return richHtml.value || form.value.html_content || '';
});
const todayDate = computed(() =>
  new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
);
const agentLabel = (agent: any) => `${agent.name}${agent.is_builtin ? '（内置）' : ''}`;
const wordCount = computed(() => {
  // 粗略计算：从 HTML 中剥离标签后计算字符数
  const text = (richHtml.value || '').replace(/<[^>]*>/g, '');
  return text.length;
});

// --- Watchers ---
watch(richHtml, (v) => { form.value.html_content = v; });
watch(() => route.query.hotspot_id, () => loadSelectedHotspot(), { immediate: true });
watch(() => route.query.article_id, () => fetchArticle(), { immediate: true });

// --- 方法 ---

/** 触发封面上传 */
const triggerCoverUpload = () => { coverFileInput.value?.click(); };

/** 封面文件变更处理 */
const onCoverFileChange = async (e: Event) => {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  try {
    const res = await uploadMedia(file, 'cover', '文章封面');
    form.value.cover_image_url = res.data?.url || '';
    MessagePlugin.success('封面上传成功');
  } catch {
    MessagePlugin.error('上传失败，请重试');
  }
  if (coverFileInput.value) coverFileInput.value.value = '';
};

/** 话题切换 */
const onHotspotChange = (id: number) => {
  const item = trendingHotspots.value.find((h: any) => h.id === id);
  if (item) { selectedHotspot.value = item; generateAIAngles(item); }
};
const selectHotspot = (item: any) => {
  selectedHotspot.value = item;
  selectedHotspotId.value = item.id;
  generateAIAngles(item);
};

/** AI 角度 */
const generateAIAngles = (hotspot: any) => {
  const t = hotspot?.title || '';
  if (!t) { aiAngles.value = []; return; }
  aiAngles.value = [
    `深度解读：${t}的行业影响`,
    `数据拆解：${t.slice(0, 12)}...`,
    `实战指南：给普通人的建议`,
  ];
  selectedAngleIndex.value = -1;
};
const selectAngle = (idx: number) => {
  selectedAngleIndex.value = idx;
  userPrompt.value = aiAngles.value[idx];
};

/** 样式主题切换 */
const applyStyleTheme = (theme: StyleTheme) => {
  currentStyleTheme.value = theme;
  MessagePlugin.success(`已切换「${theme.name}」`);
};

/** 应用 HTML 到预览 */
const applyHtmlToPreview = () => {
  richHtml.value = htmlSource.value;
  form.value.html_content = htmlSource.value;
};

/** 重置编辑器 */
const resetEditor = () => {
  form.value = { id: null, title: '', digest: '', content: '', html_content: '', cover_image_url: '', status: 'draft' };
  richHtml.value = '<p></p>';
};

/** 编辑器鼠标抬起 → 显示 AI 工具栏 */
const onEditorMouseUp = () => {
  setTimeout(() => {
    const sel = window.getSelection();
    const text = sel?.toString().trim() || '';
    if (!text || text.length < 4) {
      aiFloatingBar.value.visible = false;
      return;
    }
    const range = sel?.getRangeAt(0);
    if (!range) return;
    const rect = range.getBoundingClientRect();
    const el = editorScrollRef.value;
    if (!el) return;
    const er = el.getBoundingClientRect();
    aiFloatingBar.value = {
      visible: true,
      top: rect.bottom - er.top + 8,
      left: Math.max(10, Math.min(rect.left - er.left + rect.width / 2 - 100, er.width - 220)),
      selectedText: text,
    };
  }, 10);
};

/** AI 操作（改写/扩写/缩写/续写）— 通过 AI 美化接口实现 */
const aiAction = async (action: string) => {
  if (!form.value.id) {
    MessagePlugin.warning('请先生成文章');
    return;
  }
  const selectedText = aiFloatingBar.value.selectedText;
  if (!selectedText && action !== 'continue') {
    MessagePlugin.warning('请先在编辑器中选中文字');
    return;
  }
  aiActionLoading.value = true;
  aiFloatingBar.value.visible = false;
  const labels: Record<string, string> = { rewrite: '改写润色', expand: '扩写段落', shorten: '缩写精简', continue: '续写' };
  try {
    // 先保存当前内容
    const saved = await saveArticle();
    if (!saved) return;
    // 使用 AI 美化接口进行排版优化（后端已实现 LLM 调用）
    const res = await aiBeautifyArticle(form.value.id);
    if (res.data.html_content) {
      richHtml.value = res.data.html_content;
      form.value.html_content = res.data.html_content;
      htmlSource.value = res.data.html_content;
      MessagePlugin.success(`${labels[action]}完成`);
      fetchCredits();
    }
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || `${labels[action]}失败`);
  } finally {
    aiActionLoading.value = false;
  }
};

/** 生成摘要 — 从文章 HTML 中提取纯文本前 120 字作为摘要 */
const aiGenDigest = async () => {
  if (!form.value.id) return;
  const text = (richHtml.value || '').replace(/<[^>]*>/g, '').trim();
  if (!text) { MessagePlugin.warning('文章内容为空，无法生成摘要'); return; }
  form.value.digest = text.slice(0, 120);
  await saveArticle();
  MessagePlugin.success('摘要已生成');
};

/** 打开草稿 */
const openDraft = (id: number) => router.push(`/create?article_id=${id}`);

// ---- 数据加载 ----

const fetchAccounts = async () => {
  try { const res = await getAccounts(); accounts.value = res.data || []; } catch {}
};
const fetchDrafts = async () => {
  try { const res = await getArticles({ status: 'draft' }); recentDrafts.value = res.data || []; } catch { recentDrafts.value = []; }
};
const fetchTrendingHotspots = async () => {
  try { const res = await getHotspots({ limit: 8, time_range: '3d' }); trendingHotspots.value = res.data?.items || []; } catch { trendingHotspots.value = []; }
};
const fetchArticle = async () => {
  if (!articleId.value) { resetEditor(); return; }
  try {
    const res = await getArticle(articleId.value);
    const a = res.data;
    form.value = { id: a.id, title: a.title || '', digest: a.digest || '', content: a.content || '', html_content: a.html_content || '', cover_image_url: a.cover_image_url || '', status: a.status || 'draft' };
    richHtml.value = a.html_content || '<p></p>';
    htmlSource.value = a.html_content || '';
    activeTab.value = 'rich';
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '加载失败');
  }
};
const loadSelectedHotspot = async () => {
  const id = route.query.hotspot_id ? Number(route.query.hotspot_id) : undefined;
  if (!id || Number.isNaN(id)) return;
  hotspotLoading.value = true;
  try {
    const res = await getHotspot(id);
    selectedHotspot.value = res.data;
    selectedHotspotId.value = res.data.id;
  } catch {
    MessagePlugin.warning('话题加载失败，请从顶栏重新选择');
  } finally {
    hotspotLoading.value = false;
  }
};

// ---- AI 生成 ----

const doAIWrite = async () => {
  if (hotspotLoading.value) {
    MessagePlugin.info('话题正在加载，请稍候');
    return;
  }
  if (!selectedHotspot.value) {
    if (trendingHotspots.value.length) selectHotspot(trendingHotspots.value[0]);
    else { MessagePlugin.warning('请先选择话题'); return; }
  }
  creating.value = true;
  try {
    const res = await createArticleFromHotspotAsync(selectedHotspot.value.id, {
      agent_id: selectedAgentId.value || agents.value[0]?.id,
      style_id: selectedStyleId.value,
      prompt_template_id: selectedPromptId.value,
      user_prompt: userPrompt.value || undefined,
      mode: selectedMode.value || undefined,
    });
    connectTaskSSE(res.data.task_id);
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '启动失败');
    creating.value = false;
  }
};

const connectTaskSSE = (taskId: number) => {
  generating.value = true;
  generationStatus.value = '准备素材...';
  generationPercent.value = 5;
  richHtml.value = '';
  const token = localStorage.getItem('ap_token') || '';
  const es = new EventSource(`/api/tasks/${taskId}/stream?token=${encodeURIComponent(token)}`);
  activeEventSource = es;
  es.addEventListener('llm_chunk', (e: MessageEvent) => {
    const d = JSON.parse(e.data);
    if (d.chunk) {
      richHtml.value += d.chunk;
      generationStatus.value = 'AI 写作中...';
      generationPercent.value = Math.min(85, generationPercent.value + 0.3);
    }
  });
  es.addEventListener('progress', (e: MessageEvent) => {
    const d = JSON.parse(e.data);
    const steps = d.steps || [];
    const done = steps.filter((s: any) => s.status === 'success').length;
    generationPercent.value = Math.max(generationPercent.value, Math.round(done / Math.max(steps.length, 3) * 90));
    if (steps.length) {
      const l = steps[steps.length - 1];
      generationStatus.value = l.status === 'success' ? `${stepNameMap[l.name] || l.name}完成` : `${stepNameMap[l.name] || l.name}...`;
    }
  });
  es.addEventListener('done', (e: MessageEvent) => {
    const d = JSON.parse(e.data);
    es.close();
    activeEventSource = null;
    generating.value = false;
    creating.value = false;
    generationPercent.value = 100;
    if (d.status === 'success' && d.result?.article_id) {
      MessagePlugin.success(`AI 已起草：${d.result.title || '文章'}`);
      router.push(`/create?article_id=${d.result.article_id}`);
    } else { MessagePlugin.error(d.result?.error || '生成失败'); }
  });
  es.addEventListener('error', () => {
    es.close();
    activeEventSource = null;
    generating.value = false;
    creating.value = false;
  });
};

const createArticle = async (p: { agent_id?: number; style_id?: string; prompt_template_id?: number; user_prompt?: string }) => {
  if (!selectedHotspot.value) { MessagePlugin.warning('请先选择话题'); return; }
  creating.value = true;
  try {
    const res = await createArticleFromHotspot(selectedHotspot.value.id, p);
    MessagePlugin.success(`AI 已起草：${res.data.title}`);
    createVisible.value = false;
    await fetchDrafts();
    await router.push(`/create?article_id=${res.data.id}&hotspot_id=${selectedHotspot.value.id}`);
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '生成失败');
  } finally { creating.value = false; }
};

// ---- 排版 / 美化 / 保存 / 发布 ----

const doBeautify = async () => {
  if (!form.value.id) return;
  beautifying.value = true;
  try {
    await saveArticle();
    const res = await beautifyArticle(form.value.id);
    if (res.data.html_content) {
      form.value.html_content = res.data.html_content;
      htmlSource.value = res.data.html_content;
      // wenyan 渲染的 HTML 含 inline style，Tiptap 会剥掉样式
      // 所以切到预览模式让用户看到真实排版效果
      activeTab.value = 'preview';
      MessagePlugin.success('wenyan 排版完成，已切换到预览模式');
    }
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '排版失败');
  } finally { beautifying.value = false; }
};

const doAIBeautify = async () => {
  if (!form.value.id) return;
  aiBeautifying.value = true;
  try {
    await saveArticle();
    const res = await aiBeautifyArticle(form.value.id);
    if (res.data.html_content) {
      form.value.html_content = res.data.html_content;
      htmlSource.value = res.data.html_content;
      // AI 美化同理，切到预览模式
      activeTab.value = 'preview';
      MessagePlugin.success(`AI 美化完成（~${res.data.credits_consumed || 3} Credits）`);
      fetchCredits();
    }
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '美化失败');
  } finally { aiBeautifying.value = false; }
};

const saveArticle = async () => {
  if (!form.value.id) { MessagePlugin.warning('请先生成文章'); return false; }
  saving.value = true;
  try {
    const p: any = { title: form.value.title, digest: form.value.digest, cover_image_url: form.value.cover_image_url };
    if (activeTab.value === 'markdown') p.content = form.value.content;
    else if (activeTab.value === 'html') p.html_content = htmlSource.value;
    else p.html_content = richHtml.value;
    const res = await updateArticle(form.value.id, p);
    form.value.html_content = res.data.html_content || richHtml.value;
    richHtml.value = res.data.html_content || richHtml.value;
    htmlSource.value = res.data.html_content || htmlSource.value;
    MessagePlugin.success('已保存');
    return true;
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '保存失败');
    return false;
  } finally { saving.value = false; }
};

const saveAndSync = async () => {
  if (!form.value.id) return;
  syncing.value = true;
  try {
    const saved = await saveArticle();
    if (!saved) return;
    await syncArticle(form.value.id);
    MessagePlugin.success('已同步到微信草稿箱');
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '同步失败');
  } finally { syncing.value = false; }
};

// ---- 封面图生成 ----
const doGenerateCover = async () => {
  if (!form.value.id) return;
  coverGenerating.value = true;
  try {
    const saved = await saveArticle();
    if (!saved) return;
    const res = await generateCoverImage(form.value.id);
    if (res.data.cover_image_url) {
      form.value.cover_image_url = res.data.cover_image_url;
      MessagePlugin.success('封面图已生成');
      fetchCredits();
    }
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '封面图生成失败');
  } finally {
    coverGenerating.value = false;
  }
};

// ---- 演示文稿入口 ----
const openSlideshow = () => {
  if (!form.value.id) { MessagePlugin.warning('请先保存文章'); return; }
  router.push(`/articles?slideshow=${form.value.id}`);
};

// ---- 视频生成入口（Remotion） ----
const openVideoGenerate = () => {
  if (!form.value.id) { MessagePlugin.warning('请先保存文章'); return; }
  router.push(`/articles?video=${form.value.id}`);
};

// ---- 初始化 ----

onMounted(async () => {
  await Promise.all([
    fetchDrafts(),
    fetchTrendingHotspots(),
    fetchCredits(),
    getAgents().then(r => { agents.value = r.data || [] }).catch(() => {}),
    getStylePresets().then(r => { stylePresets.value = r.data || [] }).catch(() => {}),
    getPromptTemplates().then(r => { prompts.value = r.data || [] }).catch(() => {}),
    fetchAccounts(),
  ]);
  const b = agents.value.find((a: any) => a.is_builtin);
  selectedAgentId.value = b?.id || agents.value[0]?.id;
  if (!selectedHotspot.value && trendingHotspots.value.length) selectHotspot(trendingHotspots.value[0]);
  const tid = route.query.task_id ? Number(route.query.task_id) : undefined;
  if (tid && !Number.isNaN(tid)) { creating.value = true; connectTaskSSE(tid); }
});
</script>

<style scoped>
/* ================================================================
   Create — 基于原型图的全面重构
   架构：顶栏(固定) + 主内容(编辑器+右侧面板) + 底栏(固定)
   ================================================================ */

.create-page {
  display: flex; flex-direction: column;
  height: 100%; overflow: hidden;
}

/* ==================== 顶栏 ==================== */
.topbar {
  flex-shrink: 0; height: 52px;
  background: #fff; border-bottom: 1px solid var(--td-border-level-1-color, #e5e7eb);
  display: flex; align-items: center; padding: 0 20px; gap: 12px; z-index: 10;
}
.topbar-brand {
  font-size: 15px; font-weight: 700; color: var(--td-brand-color, #2563eb);
  white-space: nowrap;
}
.topbar-divider {
  width: 1px; height: 20px; background: var(--td-border-level-1-color, #e5e7eb); flex-shrink: 0;
}
.topic-select {
  width: 240px; max-width: 280px; flex-shrink: 0;
}
/* 话题下拉框样式微调 */
.topic-select :deep(.t-select__wrap) {
  border-radius: 8px !important;
}
.topic-select :deep(.t-input__inner) {
  font-size: 13px !important;
}

.angle-chips {
  display: flex; gap: 6px; flex: 1; min-width: 0; overflow-x: auto;
  scrollbar-width: none; padding: 2px 0;
}
.angle-chips::-webkit-scrollbar { display: none; }
.angle-chip {
  padding: 4px 12px; border-radius: 99px; font-size: 12px; font-weight: 500;
  border: 1px solid var(--td-border-level-1-color, #e5e7eb);
  background: #fff; color: var(--td-text-color-secondary, #6b7280);
  cursor: pointer; white-space: nowrap; transition: all .15s; flex-shrink: 0;
}
.angle-chip:hover {
  border-color: var(--td-brand-color, #2563eb);
  color: var(--td-brand-color, #2563eb); background: #eff6ff;
}
.angle-chip.active {
  border-color: var(--td-brand-color, #2563eb);
  color: var(--td-brand-color, #2563eb); background: #eff6ff;
}

.topbar-right {
  display: flex; align-items: center; gap: 8px; margin-left: auto; flex-shrink: 0;
}
.icon-btn {
  width: 32px; height: 32px; border-radius: 8px;
  border: 1px solid var(--td-border-level-1-color, #e5e7eb);
  background: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: var(--td-text-color-placeholder, #9ca3af); transition: all .15s;
}
.icon-btn:hover { border-color: #c0c4cc; color: var(--td-text-color-secondary, #6b7280); }

.credits-badge {
  padding: 4px 10px; border-radius: 99px; font-size: 11px; font-weight: 600;
  background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; white-space: nowrap;
}

/* 配置展开面板 */
.config-panel-bar {
  flex-shrink: 0; background: #fff; border-bottom: 1px solid #f2f3f5;
  padding: 8px 20px; z-index: 9;
}
.config-grid { display: flex; gap: 14px; flex-wrap: wrap; }
.cfg-item { min-width: 150px; }
.cfg-item label {
  display: block; font-size: 10px; font-weight: 600; color: #bbb;
  margin-bottom: 3px; text-transform: uppercase; letter-spacing: .5px;
}
.theme-chips { display: flex; gap: 3px; flex-wrap: wrap; }
.theme-chip {
  padding: 2px 8px; border-radius: 99px; font-size: 10px;
  border: 1px solid #eee; background: #fff; cursor: pointer; color: #888;
}
.theme-chip.active { border-color: var(--td-brand-color); color: var(--td-brand-color); background: #eef4ff; }

.slide-down-enter-active, .slide-down-leave-active { transition: all .2s ease; overflow: hidden; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; }

/* ==================== 主内容区 ==================== */
.main-content {
  flex: 1; display: flex; overflow: hidden; min-height: 0;
}

/* === 编辑器面板（左侧，可滚动）=== */
.editor-panel {
  flex: 1; min-width: 520px; display: flex; flex-direction: column;
  background: #fff; overflow: hidden;
}
.editor-scroll {
  flex: 1; overflow-y: auto; padding: 28px 40px 20px;
}

/* 标题输入 */
.editor-title {
  font-size: 26px; font-weight: 700; line-height: 1.35; color: #1a1a1a;
  border: none; outline: none; width: 100%; padding: 0;
  background: transparent; font-family: inherit;
}
.editor-title::placeholder { color: #d1d5db; font-weight: 500; }

/* 元信息区 */
.editor-meta {
  margin-top: 8px; display: flex; flex-direction: column; gap: 6px;
  padding-bottom: 16px; border-bottom: 1px solid #f0f1f3;
}
.editor-digest {
  font-size: 14px; color: #6b7280; border: none; outline: none;
  width: 100%; background: transparent; resize: none;
  line-height: 1.6; font-family: inherit;
}
.editor-digest::placeholder { color: #d1d5db; }

/* 封面图 */
.cover-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.cover-btn {
  padding: 5px 12px; border: 1px dashed #e5e7eb; border-radius: 6px;
  background: transparent; font-size: 12px; color: #9ca3af; cursor: pointer;
  font-family: inherit; transition: all .15s;
}
.cover-btn:hover { border-color: #2563eb; color: #2563eb; }
.cover-thumb {
  width: 48px; height: 32px; object-fit: cover; border-radius: 5px;
  border: 1px solid #e5e7eb; flex-shrink: 0;
}
.cover-url-mini { max-width: 160px; }

/* 分割线 */
.editor-divider {
  height: 1px; background: #f0f1f3; margin: 12px 0 8px;
}

/* Tab 切换 */
.toolbar-tabs { padding: 4px 0 10px; }

/* 编辑器内容容器 */
.editor-body-wrap {
  position: relative; min-height: 300px;
}
.editor-scroll :deep(.tiptap-editor) { min-height: 300px !important; }
.editor-scroll :deep(.ProseMirror) {
  min-height: 300px !important; padding: 12px 16px !important;
  font-size: 15px; line-height: 1.85; color: #374151;
  border: 1px solid #e5e7eb; border-radius: 8px; background: #fff;
}
.editor-scroll :deep(.ProseMirror:focus) {
  outline: none; border-color: var(--td-brand-color, #2563eb);
  box-shadow: 0 0 0 2px rgba(37,99,235,0.08);
}
.raw-editor-wrap { min-height: 300px; }
.raw-editor {
  width: 100%; min-height: 300px; padding: 12px 16px;
  border: 1px solid #e5e7eb; border-radius: 8px;
  font-family: 'Menlo', 'Consolas', monospace; font-size: 13px;
  line-height: 1.7; resize: vertical; background: #fff;
  box-sizing: border-box;
}
.raw-editor:focus {
  outline: none; border-color: var(--td-brand-color, #2563eb);
  box-shadow: 0 0 0 2px rgba(37,99,235,0.08);
}
.preview-html-wrap {
  min-height: 300px; border: 1px solid #e5e7eb; border-radius: 8px;
  background: #fff; padding: 12px 16px;
}
.preview-html {
  min-height: 280px; line-height: 1.85; font-size: 14px; color: #333;
}

/* AI 浮动工具栏 */
.ai-floating-bar {
  position: absolute; z-index: 100;
  display: flex; gap: 1px; padding: 3px;
  border-radius: 8px; background: #fff;
  box-shadow: 0 2px 12px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.04);
}
.fbtn {
  padding: 5px 11px; border: none; border-radius: 5px; background: transparent;
  font-size: 12px; font-weight: 600; cursor: pointer; color: #333;
}
.fbtn:hover { background: #f0f2f5; }
.fbtn-p { background: var(--td-brand-color); color: #fff; }
.fbtn-p:hover { background: var(--td-brand-hover, #1d4ed8) !important; color: #fff !important; }

/* 字数统计 */
.word-count {
  text-align: right; font-size: 11px; color: #9ca3af; padding: 10px 0 4px;
}

/* === 右侧面板 === */
.side-panel {
  width: 360px; flex-shrink: 0; background: #f8f9fb;
  border-left: 1px solid var(--td-border-level-1-color, #e5e7eb);
  display: flex; flex-direction: column; overflow: hidden;
}
.side-tabs {
  display: flex; border-bottom: 1px solid var(--td-border-level-1-color, #e5e7eb);
  background: #fff; flex-shrink: 0;
}
.side-tab {
  flex: 1; padding: 10px 0; font-size: 13px; font-weight: 600;
  text-align: center; cursor: pointer; border: none; background: transparent;
  color: #9ca3af; border-bottom: 2px solid transparent; transition: all .15s;
  font-family: inherit;
}
.side-tab:hover { color: #6b7280; }
.side-tab.active { color: var(--td-brand-color, #2563eb); border-bottom-color: var(--td-brand-color, #2563eb); }

.side-body {
  flex: 1; overflow-y: auto; padding: 16px;
}

/* ---- AI 助手 Tab ---- */
.ai-section { display: flex; flex-direction: column; gap: 16px; }

/* 统一卡片风格 */
.ai-card {
  padding: 16px; border-radius: 12px;
  border: 1px solid var(--td-border-level-1-color, #e5e7eb);
  background: #fff;
}
.ai-card-title {
  font-size: 13px; font-weight: 700; color: #1a1a1a;
  margin-bottom: 10px; display: flex; align-items: center; gap: 6px;
}
.ai-card-title svg { flex-shrink: 0; color: var(--td-brand-color, #2563eb); }

/* AI 生成模块 */
.ai-prompt-label { font-size: 12px; font-weight: 600; color: #6b7280; margin-bottom: 4px; }
.ai-prompt-box {
  width: 100%; min-height: 72px; padding: 10px 12px;
  border: 1px solid var(--td-border-level-1-color, #e5e7eb);
  border-radius: 8px; font-size: 13px; line-height: 1.6;
  color: #1a1a1a; background: #f8f9fb; resize: vertical;
  outline: none; font-family: inherit;
}
.ai-prompt-box:focus { border-color: var(--td-brand-color, #2563eb); box-shadow: 0 0 0 2px rgba(37,99,235,0.08); }
.ai-prompt-box::placeholder { color: #c0c4cc; }

.ai-generate-btn {
  width: 100%; padding: 11px; border: none; border-radius: 8px;
  background: var(--td-brand-color, #2563eb); color: #fff;
  font-size: 14px; font-weight: 700; cursor: pointer; transition: all .15s;
  font-family: inherit; margin-top: 8px;
}
.ai-generate-btn:hover:not(:disabled) {
  background: var(--td-brand-hover, #1d4ed8);
  box-shadow: 0 2px 8px rgba(37,99,235,0.25);
}
.ai-generate-btn:active:not(:disabled) { transform: scale(0.98); }
.ai-generate-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.ai-cost { text-align: center; font-size: 11px; color: #9ca3af; margin-top: 6px; }

/* ---- 排版美化模块（高亮）---- */
.beautify-card {
  border: 1px solid rgba(37,99,235,0.18);
  background: linear-gradient(135deg, #f8faff 0%, #eff6ff 50%, #fdf4ff 100%);
  position: relative; overflow: hidden;
}
.beautify-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #2563eb, #7c3aed, #ec4899);
}

.beautify-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

.beautify-btn {
  padding: 10px 12px; border: 1px solid rgba(255,255,255,0.8); border-radius: 8px;
  background: rgba(255,255,255,0.75); backdrop-filter: blur(4px);
  font-size: 13px; font-weight: 600; color: #1a1a1a; cursor: pointer;
  transition: all .15s; text-align: left; display: flex; flex-direction: column; gap: 2px;
  font-family: inherit;
}
.beautify-btn:hover:not(:disabled) {
  border-color: var(--td-brand-color, #2563eb); background: #fff;
  box-shadow: 0 2px 8px rgba(37,99,235,0.12); transform: translateY(-1px);
}
.beautify-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.beautify-btn .b-desc { font-size: 11px; font-weight: 400; color: #9ca3af; }

/* 主按钮：一键美化（全宽渐变高亮） */
.beautify-btn.primary-beauty {
  grid-column: 1 / -1;
  padding: 14px 16px; border: none; border-radius: 8px;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  color: #fff; font-size: 14px; font-weight: 700;
  justify-content: center; align-items: center; flex-direction: row; gap: 8px;
  box-shadow: 0 2px 12px rgba(124,58,237,0.25);
}
.beautify-btn.primary-beauty:hover:not(:disabled) {
  box-shadow: 0 4px 20px rgba(124,58,237,0.35);
  transform: translateY(-1px);
}
.beautify-btn.primary-beauty .b-desc { color: rgba(255,255,255,0.8); font-weight: 400; }

/* 快捷操作 */
.ai-quick-label {
  font-size: 11px; font-weight: 600; color: #9ca3af;
  letter-spacing: 0.3px; margin-bottom: 6px;
}
.ai-quick-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }
.ai-quick-btn {
  padding: 8px 10px; border: 1px solid #f0f1f3; border-radius: 6px;
  background: #fff; font-size: 12px; font-weight: 500; color: #6b7280;
  cursor: pointer; transition: all .12s; text-align: left; font-family: inherit;
}
.ai-quick-btn:hover:not(:disabled) { border-color: #d0d3d9; background: #f8f9fb; }
.ai-quick-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.ai-quick-btn .btn-title { font-weight: 600; color: #1a1a1a; margin-bottom: 1px; }
.ai-quick-btn .btn-desc { font-size: 10.5px; color: #9ca3af; }

/* ---- 微信预览 Tab ---- */
.phone-frame {
  background: #1a1a1a; border-radius: 28px; padding: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15); margin: 0 auto; width: 100%;
}
.phone-notch { width: 80px; height: 5px; border-radius: 3px; background: #333; margin: 4px auto 6px; }
.phone-screen {
  background: #fff; border-radius: 20px; overflow: hidden;
  min-height: 400px; max-height: 600px; overflow-y: auto;
}
.wx-header { padding: 14px 14px 10px; border-bottom: 1px solid #f2f3f5; }
.wx-title { font-size: 16px; font-weight: 700; line-height: 1.4; color: #1a1a1a; }
.wx-meta { display: flex; gap: 6px; margin-top: 4px; font-size: 10px; color: #bbb; }
.wx-author { font-weight: 600; color: #07C160; }
.wx-cover { width: 100%; object-fit: cover; max-height: 150px; }
.wx-body { padding: 14px; font-size: 13px; line-height: 1.8; color: #333; }
.wx-body :deep(p) { margin-bottom: 8px; }
.wx-body :deep(h2) { font-size: 16px; font-weight: 700; margin: 12px 0 6px; }
.wx-body :deep(strong) { color: #111; }
.wx-body :deep(blockquote) { margin: 8px 0; padding: 6px 12px; border-left: 3px solid #07C160; background: #f7fdf9; border-radius: 0 5px 5px 0; }
.wx-body :deep(img) { width: 100%; border-radius: 3px; }
.wx-empty { text-align: center; padding: 60px 14px; color: #ddd; font-size: 12px; }

/* 草稿列表 */
.drafts-section { margin-top: 16px; }
.drafts-title { font-size: 11px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
.draft-list { display: flex; flex-direction: column; gap: 2px; }
.draft-item {
  padding: 6px 8px; border-radius: 6px; font-size: 12px; color: #6b7280;
  cursor: pointer; border: none; background: transparent; text-align: left;
  width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-family: inherit;
}
.draft-item:hover { background: #e8eaed; }
.draft-item.active { background: #dbeafe; color: var(--td-brand-color, #2563eb); }
.draft-empty { font-size: 11px; color: #ccc; padding: 6px 0; }

/* mode chips */
.mode-chips { display: flex; gap: 6px; margin-bottom: 4px; }
.mode-chip {
  padding: 5px 12px; border-radius: 99px; font-size: 12px; font-weight: 600;
  border: 1px solid var(--td-border-level-1-color, #e5e7eb);
  background: #fff; color: var(--td-text-color-secondary, #6b7280);
  cursor: pointer; transition: all .15s; font-family: inherit;
}
.mode-chip:hover { border-color: var(--td-brand-color, #2563eb); color: var(--td-brand-color); }
.mode-chip.active {
  border-color: var(--td-brand-color, #2563eb); color: #fff;
  background: var(--td-brand-color, #2563eb);
}

/* ==================== 底栏（固定）==================== */
.bottombar {
  flex-shrink: 0; height: 52px;
  background: #fff; border-top: 1px solid var(--td-border-level-1-color, #e5e7eb);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; z-index: 10;
}
.bottom-hint { font-size: 11px; color: #9ca3af; }
.bottom-actions { display: flex; align-items: center; gap: 10px; }

/* ==================== 响应式 ==================== */
@media (max-width: 1100px) {
  .side-panel { width: 300px; }
  .editor-panel { min-width: 420px; }
}
@media (max-width: 960px) {
  .main-content { flex-direction: column; }
  .side-panel {
    width: 100% !important; border-left: none; border-top: 1px solid #eee;
    max-height: 350px;
  }
  .editor-panel { min-width: 0; }
  .editor-scroll { padding: 20px 24px; }
  .angle-chips { display: none; }
}
</style>
