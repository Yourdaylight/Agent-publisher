<template>
  <div>
    <t-card :bordered="true" style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: flex-end">
        <t-space>
          <t-input v-model="filters.keyword" placeholder="搜索提示词名称/内容" style="width: 260px" />
          <t-select v-model="filters.category" placeholder="分类" clearable style="width: 160px">
            <t-option v-for="category in categories" :key="category" :label="category" :value="category" />
          </t-select>
          <t-button theme="primary" @click="fetchPrompts">查询</t-button>
        </t-space>
        <t-button theme="primary" @click="openCreate">新增提示词</t-button>
      </div>
    </t-card>

    <t-table :data="prompts" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #category="{ row }">
        <t-tag variant="light">{{ row.category }}</t-tag>
      </template>
      <template #is_builtin="{ row }">
        <t-tag :theme="row.is_builtin ? 'primary' : 'default'" variant="light">{{ row.is_builtin ? '系统' : '自定义' }}</t-tag>
      </template>
      <template #content="{ row }">
        <div style="white-space: pre-wrap; color: var(--td-text-color-secondary)">{{ row.content.slice(0, 120) }}{{ row.content.length > 120 ? '...' : '' }}</div>
      </template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openEdit(row)">编辑</t-link>
          <t-link theme="danger" v-if="!row.is_builtin" @click="removePrompt(row)">删除</t-link>
        </t-space>
      </template>
    </t-table>

    <t-dialog v-model:visible="dialogVisible" :header="editingId ? '编辑提示词' : '新增提示词'" :footer="false" width="720px">
      <t-form layout="vertical">
        <t-form-item label="名称">
          <t-input v-model="form.name" />
        </t-form-item>
        <t-form-item label="分类">
          <t-select v-model="form.category">
            <t-option v-for="category in defaultCategories" :key="category" :label="category" :value="category" />
          </t-select>
        </t-form-item>
        <t-form-item label="描述">
          <t-input v-model="form.description" />
        </t-form-item>
        <t-form-item label="模板变量（逗号分隔）">
          <t-input v-model="form.variablesInput" placeholder="title,digest,content" />
        </t-form-item>
        <t-form-item label="提示词内容">
          <t-textarea v-model="form.content" :autosize="{ minRows: 8, maxRows: 18 }" />
        </t-form-item>
        <t-form-item>
          <t-space>
            <t-button theme="primary" :loading="saving" @click="savePrompt">保存</t-button>
            <t-button variant="outline" @click="dialogVisible = false">取消</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { MessagePlugin } from 'tdesign-vue-next';
import { createPromptTemplate, deletePromptTemplate, getPromptCategories, getPromptTemplates, updatePromptTemplate } from '@/api';

const loading = ref(false);
const saving = ref(false);
const prompts = ref<any[]>([]);
const categories = ref<string[]>([]);
const dialogVisible = ref(false);
const editingId = ref<number | null>(null);
const defaultCategories = ['rewrite', 'summary', 'expand', 'style', 'custom'];

const filters = reactive({
  keyword: '',
  category: undefined as string | undefined,
});

const form = reactive({
  name: '',
  category: 'rewrite',
  description: '',
  content: '',
  variablesInput: '',
});

const columns = [
  { colKey: 'name', title: '名称', width: 180 },
  { colKey: 'category', title: '分类', width: 100 },
  { colKey: 'description', title: '描述', width: 220 },
  { colKey: 'content', title: '内容' },
  { colKey: 'usage_count', title: '使用次数', width: 100 },
  { colKey: 'is_builtin', title: '类型', width: 100 },
  { colKey: 'op', title: '操作', width: 120 },
];

const fetchPrompts = async () => {
  loading.value = true;
  try {
    const res = await getPromptTemplates({ category: filters.category, keyword: filters.keyword || undefined });
    prompts.value = res.data;
  } catch {
    MessagePlugin.error('加载提示词失败');
  } finally {
    loading.value = false;
  }
};

const fetchCategories = async () => {
  try {
    const res = await getPromptCategories();
    categories.value = res.data.items || [];
  } catch {
    categories.value = defaultCategories;
  }
};

const resetForm = () => {
  editingId.value = null;
  form.name = '';
  form.category = 'rewrite';
  form.description = '';
  form.content = '';
  form.variablesInput = '';
};

const openCreate = () => {
  resetForm();
  dialogVisible.value = true;
};

const openEdit = (row: any) => {
  editingId.value = row.id;
  form.name = row.name;
  form.category = row.category;
  form.description = row.description || '';
  form.content = row.content || '';
  form.variablesInput = (row.variables || []).join(',');
  dialogVisible.value = true;
};

const savePrompt = async () => {
  if (!form.name.trim() || !form.content.trim()) {
    MessagePlugin.warning('请填写名称和内容');
    return;
  }
  saving.value = true;
  const payload = {
    name: form.name,
    category: form.category,
    description: form.description,
    content: form.content,
    variables: form.variablesInput.split(',').map((item) => item.trim()).filter(Boolean),
  };
  try {
    if (editingId.value) {
      await updatePromptTemplate(editingId.value, payload);
      MessagePlugin.success('提示词已更新');
    } else {
      await createPromptTemplate(payload);
      MessagePlugin.success('提示词已创建');
    }
    dialogVisible.value = false;
    fetchPrompts();
    fetchCategories();
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '保存失败');
  } finally {
    saving.value = false;
  }
};

const removePrompt = async (row: any) => {
  try {
    await deletePromptTemplate(row.id);
    MessagePlugin.success('提示词已删除');
    fetchPrompts();
    fetchCategories();
  } catch {
    MessagePlugin.error('删除失败');
  }
};

onMounted(async () => {
  await Promise.all([fetchPrompts(), fetchCategories()]);
});
</script>
