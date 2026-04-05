<template>
  <div>
    <t-row :gutter="16">
      <t-col :span="4">
        <t-card title="选择素材" :bordered="true">
          <t-space direction="vertical" style="width: 100%">
            <t-select v-model="filters.agent_id" placeholder="按 Agent 筛选" clearable @change="fetchMaterials">
              <t-option v-for="agent in agents" :key="agent.id" :label="agent.name" :value="agent.id" />
            </t-select>
            <t-select v-model="filters.source_type" placeholder="来源类型" clearable @change="fetchMaterials">
              <t-option value="trending" label="热点" />
              <t-option value="manual" label="手动" />
              <t-option value="rss" label="RSS" />
            </t-select>
            <t-input v-model="filters.tags" placeholder="标签筛选" @change="fetchMaterials" />
          </t-space>
          <div style="margin-top: 16px; max-height: 560px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px">
            <t-card
              v-for="item in materials"
              :key="item.id"
              size="small"
              :bordered="true"
              :style="selectedMaterialIds.includes(item.id) ? 'border-color: var(--td-brand-color); box-shadow: 0 0 0 1px var(--td-brand-color)' : ''"
              @click="toggleMaterial(item.id)"
            >
              <div style="font-weight: 600; margin-bottom: 4px">{{ item.title }}</div>
              <div style="font-size: 12px; color: var(--td-text-color-secondary)">{{ item.summary || '暂无摘要' }}</div>
            </t-card>
          </div>
        </t-card>
      </t-col>
      <t-col :span="8">
        <t-card title="生成配置" :bordered="true">
          <t-form layout="vertical">
            <t-form-item label="目标 Agent">
              <t-select v-model="form.agent_id" placeholder="选择 Agent">
                <t-option v-for="agent in agents" :key="agent.id" :label="agent.name" :value="agent.id" />
              </t-select>
            </t-form-item>
            <t-form-item label="风格预设">
              <t-select v-model="form.style_id" placeholder="可选" clearable>
                <t-option v-for="style in stylePresets" :key="style.style_id" :label="style.name" :value="style.style_id" />
              </t-select>
            </t-form-item>
            <t-form-item label="提示词模板">
              <t-select v-model="form.prompt_id" placeholder="可选" clearable>
                <t-option v-for="prompt in prompts" :key="prompt.id" :label="prompt.name" :value="prompt.id" />
              </t-select>
            </t-form-item>
            <t-form-item label="已选素材">
              <t-tag v-for="id in selectedMaterialIds" :key="id" style="margin-right: 8px; margin-bottom: 8px">#{{ id }}</t-tag>
              <div v-if="!selectedMaterialIds.length" style="color: var(--td-text-color-placeholder)">请从左侧选择至少一条素材</div>
            </t-form-item>
            <t-form-item>
              <t-space>
                <t-button theme="primary" :loading="creating" @click="createDraft">生成文章草稿</t-button>
                <t-button variant="outline" @click="goHotspots">去热点发现</t-button>
              </t-space>
            </t-form-item>
          </t-form>
        </t-card>
      </t-col>
      <t-col :span="12">
        <t-card title="工作台说明" :bordered="true">
          <t-steps layout="vertical" :current="2">
            <t-step title="选素材" content="支持从热点、手动素材、RSS 素材中挑选。" />
            <t-step title="配风格" content="组合 Agent、风格预设与提示词模板。" />
            <t-step title="出草稿" content="生成后自动进入文章管理，可继续编辑与发布。" />
          </t-steps>
          <t-alert theme="success" style="margin-top: 16px" message="该工作台用于承接热点发现页的一键创作，也可单独从素材库批量创作。" />
        </t-card>
      </t-col>
    </t-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import { createFromMaterials, getAgents, getMaterials, getPromptTemplates, getStylePresets } from '@/api';

const route = useRoute();
const router = useRouter();
const agents = ref<any[]>([]);
const materials = ref<any[]>([]);
const prompts = ref<any[]>([]);
const stylePresets = ref<any[]>([]);
const selectedMaterialIds = ref<number[]>([]);
const creating = ref(false);

const filters = reactive({
  agent_id: undefined as number | undefined,
  source_type: undefined as string | undefined,
  tags: '',
});

const form = reactive({
  agent_id: undefined as number | undefined,
  style_id: undefined as string | undefined,
  prompt_id: undefined as number | undefined,
});

const fetchMaterials = async () => {
  try {
    const res = await getMaterials({
      agent_id: filters.agent_id,
      source_type: filters.source_type,
      tags: filters.tags || undefined,
      page: 1,
      page_size: 50,
    });
    materials.value = res.data.items || [];
  } catch {
    MessagePlugin.error('加载素材失败');
  }
};

const toggleMaterial = (id: number) => {
  if (selectedMaterialIds.value.includes(id)) {
    selectedMaterialIds.value = selectedMaterialIds.value.filter((item) => item !== id);
  } else {
    selectedMaterialIds.value = [...selectedMaterialIds.value, id];
  }
};

const createDraft = async () => {
  if (!selectedMaterialIds.value.length) {
    MessagePlugin.warning('请至少选择一条素材');
    return;
  }
  if (!form.agent_id) {
    MessagePlugin.warning('请选择目标 Agent');
    return;
  }
  creating.value = true;
  try {
    const res = await createFromMaterials({
      material_ids: selectedMaterialIds.value,
      agent_id: form.agent_id,
      style_id: form.style_id,
      prompt_id: form.prompt_id,
    });
    MessagePlugin.success(`草稿创建成功：${res.data.title}`);
    router.push('/articles');
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '创建草稿失败');
  } finally {
    creating.value = false;
  }
};

const goHotspots = () => router.push('/hotspots');

onMounted(async () => {
  await Promise.all([
    getAgents().then((res) => {
      agents.value = res.data;
      form.agent_id = res.data[0]?.id;
    }).catch(() => {}),
    getPromptTemplates().then((res) => { prompts.value = res.data; }).catch(() => {}),
    getStylePresets().then((res) => { stylePresets.value = res.data; }).catch(() => {}),
  ]);
  const materialId = route.query.materialId ? Number(route.query.materialId) : undefined;
  if (materialId && !Number.isNaN(materialId)) {
    selectedMaterialIds.value = [materialId];
  }
  fetchMaterials();
});
</script>
