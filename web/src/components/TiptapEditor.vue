<template>
  <div class="tiptap-shell">
    <div class="tiptap-toolbar">
      <div class="toolbar-group">
        <span class="toolbar-label">格式</span>
        <button class="tb-btn" :class="{ active: isActive('bold') }" title="加粗 Ctrl+B" @click="toggleBold"><strong>B</strong></button>
        <button class="tb-btn" :class="{ active: isActive('italic') }" title="斜体 Ctrl+I" @click="toggleItalic"><em>I</em></button>
        <button class="tb-btn" :class="{ active: isActive('underline') }" title="下划线" @click="toggleUnderline"><u>U</u></button>
        <button class="tb-btn" :class="{ active: isActive('strike') }" title="删除线" @click="toggleStrike"><s>S</s></button>
      </div>
      <div class="toolbar-divider" />
      <div class="toolbar-group">
        <span class="toolbar-label">标题</span>
        <button class="tb-btn" :class="{ active: isActive('heading', { level: 1 }) }" title="大标题" @click="toggleH1">H1</button>
        <button class="tb-btn" :class="{ active: isActive('heading', { level: 2 }) }" title="中标题" @click="toggleH2">H2</button>
        <button class="tb-btn" :class="{ active: isActive('heading', { level: 3 }) }" title="小标题" @click="toggleH3">H3</button>
      </div>
      <div class="toolbar-divider" />
      <div class="toolbar-group">
        <span class="toolbar-label">对齐</span>
        <button class="tb-btn" title="左对齐" @click="setAlignLeft">≡</button>
        <button class="tb-btn" title="居中" @click="setAlignCenter">≡</button>
        <button class="tb-btn" title="右对齐" @click="setAlignRight">≡</button>
      </div>
      <div class="toolbar-divider" />
      <div class="toolbar-group">
        <span class="toolbar-label">插入</span>
        <button class="tb-btn" :class="{ active: isActive('bulletList') }" title="无序列表" @click="toggleBulletList">• 列表</button>
        <button class="tb-btn" :class="{ active: isActive('orderedList') }" title="有序列表" @click="toggleOrderedList">1. 列表</button>
        <button class="tb-btn" :class="{ active: isActive('blockquote') }" title="引用" @click="toggleBlockquote">❝ 引用</button>
        <button class="tb-btn" title="分割线" @click="insertDivider">—</button>
        <button class="tb-btn" title="链接" @click="setLink">🔗</button>
        <button class="tb-btn" title="图片" @click="setImage">🖼</button>
      </div>
      <div class="toolbar-divider" />
      <div class="toolbar-group">
        <span class="toolbar-label">公众号</span>
        <button class="tb-btn wx-special" title="插入关注引导" @click="insertFollowBlock">⭐ 关注</button>
        <button class="tb-btn wx-special" title="插入卡片引言" @click="insertCardQuote">📌 卡片</button>
        <button class="tb-btn wx-special" title="插入分割卡片" @click="insertSectionBreak">〓 章节</button>
      </div>
      <div class="toolbar-divider" />
      <div class="toolbar-group">
        <button class="tb-btn" title="撤销 Ctrl+Z" @click="undo">↩</button>
        <button class="tb-btn" title="重做 Ctrl+Y" @click="redo">↪</button>
      </div>
    </div>

    <div class="tiptap-editor">
      <EditorContent v-if="editor" :editor="editor" />
    </div>

    <div class="tiptap-footer">
      <span class="word-count">约 {{ wordCount }} 字</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue';
import { EditorContent, useEditor } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';

const props = defineProps<{
  modelValue: string;
  placeholder?: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const editor = useEditor({
  content: props.modelValue || '<p></p>',
  extensions: [
    StarterKit,
    Underline,
    Link.configure({ openOnClick: false, autolink: true, defaultProtocol: 'https' }),
    Image.configure({ allowBase64: true, inline: false }),
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
    Placeholder.configure({ placeholder: props.placeholder || '开始写作……' }),
  ],
  editorProps: { attributes: { class: 'tiptap-prosemirror' } },
  onUpdate: ({ editor: instance }) => {
    emit('update:modelValue', instance.getHTML());
  },
});

const wordCount = computed(() => {
  const text = editor.value?.getText() || '';
  return text.replace(/\s/g, '').length;
});

watch(
  () => props.modelValue,
  (value) => {
    const instance = editor.value;
    if (!instance) return;
    const normalized = value || '<p></p>';
    if (normalized !== instance.getHTML()) {
      instance.commands.setContent(normalized, { emitUpdate: false });
    }
  },
);

const isActive = (name: string, attrs?: Record<string, unknown>) => editor.value?.isActive(name, attrs) ?? false;
const focus = () => editor.value?.chain().focus();
const toggleBold = () => focus()?.toggleBold().run();
const toggleItalic = () => focus()?.toggleItalic().run();
const toggleUnderline = () => focus()?.toggleUnderline().run();
const toggleStrike = () => focus()?.toggleStrike().run();
const toggleH1 = () => focus()?.toggleHeading({ level: 1 }).run();
const toggleH2 = () => focus()?.toggleHeading({ level: 2 }).run();
const toggleH3 = () => focus()?.toggleHeading({ level: 3 }).run();
const toggleBulletList = () => focus()?.toggleBulletList().run();
const toggleOrderedList = () => focus()?.toggleOrderedList().run();
const toggleBlockquote = () => focus()?.toggleBlockquote().run();
const setAlignLeft = () => focus()?.setTextAlign('left').run();
const setAlignCenter = () => focus()?.setTextAlign('center').run();
const setAlignRight = () => focus()?.setTextAlign('right').run();
const insertDivider = () => focus()?.setHorizontalRule().run();
const undo = () => editor.value?.chain().focus().undo().run();
const redo = () => editor.value?.chain().focus().redo().run();

const setLink = () => {
  const instance = editor.value;
  if (!instance) return;
  const prev = instance.getAttributes('link').href as string | undefined;
  const url = window.prompt('链接地址', prev || 'https://');
  if (url === null) return;
  if (!url.trim()) { instance.chain().focus().extendMarkRange('link').unsetLink().run(); return; }
  instance.chain().focus().extendMarkRange('link').setLink({ href: url.trim() }).run();
};

const setImage = () => {
  const instance = editor.value;
  if (!instance) return;
  const url = window.prompt('图片地址', 'https://');
  if (!url?.trim()) return;
  instance.chain().focus().setImage({ src: url.trim() }).run();
};

// 公众号专用组件
const insertFollowBlock = () => {
  editor.value?.chain().focus().insertContent(
    `<blockquote><p>👆 点击上方蓝字 <strong>关注</strong> 我们，获取更多内容。</p></blockquote>`,
  ).run();
};

const insertCardQuote = () => {
  editor.value?.chain().focus().insertContent(
    `<blockquote><p>📌 <strong>本文亮点</strong>：在这里写一句精炼的摘要或观点。</p></blockquote>`,
  ).run();
};

const insertSectionBreak = () => {
  editor.value?.chain().focus().insertContent(
    `<hr/><p></p>`,
  ).run();
};

onBeforeUnmount(() => { editor.value?.destroy(); });
</script>

<style scoped>
.tiptap-shell {
  border: 1px solid var(--td-border-level-2-color);
  border-radius: 10px;
  background: #fff;
  display: flex;
  flex-direction: column;
}
.tiptap-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--td-border-level-1-color);
  background: #fafafa;
  border-radius: 10px 10px 0 0;
  flex-wrap: wrap;
}
.toolbar-group {
  display: flex;
  align-items: center;
  gap: 2px;
}
.toolbar-label {
  font-size: 10px;
  color: #aaa;
  margin-right: 2px;
  white-space: nowrap;
}
.toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--td-border-level-1-color);
  margin: 0 4px;
}
.tb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--td-text-color-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
  min-height: 28px;
}
.tb-btn:hover { background: #f0f0f0; color: var(--td-text-color-primary); }
.tb-btn.active { background: var(--td-brand-color-1); color: var(--td-brand-color); border-color: var(--td-brand-color-3); }
.tb-btn.wx-special { color: #07C160; }
.tb-btn.wx-special:hover { background: #f0fdf4; }
.tiptap-editor { flex: 1; min-height: 520px; }
.tiptap-editor :deep(.tiptap-prosemirror) {
  min-height: 520px;
  padding: 20px 24px;
  outline: none;
  line-height: 1.9;
  font-size: 15px;
  color: #1a1a1a;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', sans-serif;
}
.tiptap-editor :deep(.tiptap-prosemirror p) { margin: 0 0 12px; }
.tiptap-editor :deep(.tiptap-prosemirror h1) { font-size: 22px; font-weight: 700; margin: 24px 0 12px; line-height: 1.4; }
.tiptap-editor :deep(.tiptap-prosemirror h2) { font-size: 18px; font-weight: 700; margin: 20px 0 10px; line-height: 1.4; }
.tiptap-editor :deep(.tiptap-prosemirror h3) { font-size: 16px; font-weight: 700; margin: 16px 0 8px; line-height: 1.4; }
.tiptap-editor :deep(.tiptap-prosemirror p.is-editor-empty:first-child::before) {
  color: #bbb;
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}
.tiptap-editor :deep(.tiptap-prosemirror img) { max-width: 100%; border-radius: 8px; display: block; margin: 12px auto; }
.tiptap-editor :deep(.tiptap-prosemirror blockquote) {
  margin: 16px 0;
  padding: 12px 16px;
  border-left: 4px solid #07C160;
  background: #f7fdf9;
  border-radius: 0 8px 8px 0;
  color: #444;
  line-height: 1.8;
}
.tiptap-editor :deep(.tiptap-prosemirror pre) { background: #0f172a; color: #e2e8f0; padding: 14px; border-radius: 8px; overflow-x: auto; font-size: 13px; }
.tiptap-editor :deep(.tiptap-prosemirror hr) { border: none; border-top: 2px solid #f0f0f0; margin: 20px 0; }
.tiptap-editor :deep(.tiptap-prosemirror ul), .tiptap-editor :deep(.tiptap-prosemirror ol) { padding-left: 22px; margin: 10px 0; }
.tiptap-editor :deep(.tiptap-prosemirror li) { margin-bottom: 6px; line-height: 1.8; }
.tiptap-editor :deep(.tiptap-prosemirror strong) { font-weight: 700; color: #111; }
.tiptap-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--td-border-level-1-color);
  display: flex;
  justify-content: flex-end;
  background: #fafafa;
  border-radius: 0 0 10px 10px;
}
.word-count { font-size: 12px; color: #aaa; }
</style>
