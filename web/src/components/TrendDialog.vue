<template>
  <t-dialog :visible="visible" header="热点趋势" :footer="false" width="560px" @update:visible="emit('update:visible', $event)">
    <div v-if="points.length">
      <t-steps layout="vertical" :current="points.length - 1">
        <t-step v-for="point in points" :key="point.label" :title="point.label" :content="`热度分：${point.score}`" />
      </t-steps>
    </div>
    <t-result v-else status="404" title="暂无趋势数据" description="当前热点还没有可展示的趋势点。" />
  </t-dialog>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean;
  points: Array<{ label: string; score: number }>;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();
</script>
