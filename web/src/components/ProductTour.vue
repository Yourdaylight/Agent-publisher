<template>
  <Teleport to="body">
    <div v-if="active" class="tour-overlay" @click.self="onOverlayClick">
      <!-- 高亮框 -->
      <div v-if="highlightStyle" class="tour-highlight" :style="highlightStyle" />

      <!-- Tooltip -->
      <div v-if="currentStepDef && !currentStepDef.modal" class="tour-tooltip" :style="tooltipStyle">
        <div class="tour-tooltip-step">{{ currentStep + 1 }} / {{ tourSteps.length }}</div>
        <div class="tour-tooltip-title">{{ currentStepDef.title }}</div>
        <div class="tour-tooltip-desc">{{ currentStepDef.description }}</div>
        <div class="tour-tooltip-actions">
          <button class="tour-btn tour-btn-ghost" @click="skip">跳过</button>
          <div class="tour-tooltip-spacer" />
          <button v-if="currentStep > 0" class="tour-btn tour-btn-ghost" @click="prev">上一步</button>
          <button class="tour-btn tour-btn-primary" @click="next">
            {{ currentStep === tourSteps.length - 1 ? '完成' : '下一步' }}
          </button>
        </div>
      </div>

      <!-- Modal (欢迎 / 完成) -->
      <div v-if="currentStepDef?.modal" class="tour-modal">
        <div class="tour-modal-icon">{{ currentStepDef.icon }}</div>
        <div class="tour-modal-title">{{ currentStepDef.title }}</div>
        <div class="tour-modal-desc">{{ currentStepDef.description }}</div>
        <div class="tour-modal-actions">
          <button v-if="currentStepDef.skipLabel" class="tour-btn tour-btn-ghost" @click="skip">
            {{ currentStepDef.skipLabel }}
          </button>
          <button class="tour-btn tour-btn-primary" @click="next">
            {{ currentStepDef.nextLabel || '下一步' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const props = defineProps<{ modelValue: boolean }>();
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

const router = useRouter();
const route = useRoute();

const active = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const currentStep = ref(0);
const highlightRect = ref<DOMRect | null>(null);

interface TourStep {
  title: string;
  description: string;
  selector?: string;         // data-tour-id selector
  route?: string;            // auto-navigate before highlight
  modal?: boolean;           // show as centered modal
  icon?: string;
  nextLabel?: string;
  skipLabel?: string;
  placement?: 'right' | 'bottom';  // tooltip placement relative to target
}

const tourSteps: TourStep[] = [
  {
    title: '欢迎使用 Agent Publisher!',
    description: '30 秒了解核心功能，从发现热点到发布文章的完整流程。',
    modal: true,
    icon: '🚀',
    nextLabel: '开始引导',
    skipLabel: '稍后再看',
  },
  {
    title: '发现热点',
    description: '从这里浏览各平台的实时热榜，找到你感兴趣的话题。点击热点卡片可以一键创作文章。',
    selector: 'nav-trending',
    route: '/trending',
    placement: 'right',
  },
  {
    title: 'AI 创作',
    description: '在创作控制台，选择热点话题或直接输入主题，AI 帮你写文章。支持多种风格和模板。',
    selector: 'nav-create',
    placement: 'right',
  },
  {
    title: '内容管理',
    description: '所有文章在这里管理，可以预览、编辑或一键发布到微信公众号。',
    selector: 'nav-articles',
    placement: 'right',
  },
  {
    title: '素材库',
    description: '热点和 RSS 抓取的素材自动入库，你也可以手动上传。选中多个素材即可合并创作。',
    selector: 'nav-materials',
    placement: 'right',
  },
  {
    title: '你已经准备好了!',
    description: '随时点击左上角 💡 按钮重新查看引导。现在去发现热点，创作第一篇文章吧！',
    modal: true,
    icon: '🎉',
    nextLabel: '开始使用',
  },
];

const currentStepDef = computed(() => tourSteps[currentStep.value] || null);

// ── Highlight positioning ──

const PAD = 6; // padding around highlighted element

const highlightStyle = computed(() => {
  if (!highlightRect.value) return null;
  const r = highlightRect.value;
  return {
    top: `${r.top - PAD}px`,
    left: `${r.left - PAD}px`,
    width: `${r.width + PAD * 2}px`,
    height: `${r.height + PAD * 2}px`,
  };
});

const tooltipStyle = computed(() => {
  if (!highlightRect.value) return {};
  const r = highlightRect.value;
  const placement = currentStepDef.value?.placement || 'right';

  if (placement === 'right') {
    return {
      top: `${r.top - PAD}px`,
      left: `${r.right + PAD + 12}px`,
    };
  }
  // bottom
  return {
    top: `${r.bottom + PAD + 12}px`,
    left: `${r.left}px`,
  };
});

// ── Step navigation ──

const positionHighlight = async () => {
  await nextTick();
  const step = tourSteps[currentStep.value];
  if (!step || step.modal || !step.selector) {
    highlightRect.value = null;
    return;
  }

  // Wait a tick for DOM to settle after route change
  await new Promise((r) => setTimeout(r, 100));

  const el = document.querySelector(`[data-tour-id="${step.selector}"]`);
  if (el) {
    highlightRect.value = el.getBoundingClientRect();
  } else {
    highlightRect.value = null;
  }
};

const navigateIfNeeded = async () => {
  const step = tourSteps[currentStep.value];
  if (step?.route && route.path !== step.route) {
    await router.push(step.route);
    // Wait for route transition
    await new Promise((r) => setTimeout(r, 200));
  }
};

const goToStep = async (stepIdx: number) => {
  currentStep.value = stepIdx;
  await navigateIfNeeded();
  await positionHighlight();
};

const next = async () => {
  if (currentStep.value >= tourSteps.length - 1) {
    finish();
    return;
  }
  await goToStep(currentStep.value + 1);
};

const prev = async () => {
  if (currentStep.value > 0) {
    await goToStep(currentStep.value - 1);
  }
};

const skip = () => finish();

const finish = () => {
  active.value = false;
  currentStep.value = 0;
  highlightRect.value = null;
  localStorage.setItem('ap_tour_completed', '1');
};

const onOverlayClick = () => {
  // Don't close on overlay click — user must use buttons
};

// ── Watch active state ──

watch(active, async (val) => {
  if (val) {
    currentStep.value = 0;
    await positionHighlight();
  }
});

// ── Handle resize ──

const onResize = () => {
  if (active.value) positionHighlight();
};

onMounted(() => window.addEventListener('resize', onResize));
onUnmounted(() => window.removeEventListener('resize', onResize));
</script>

<style scoped>
.tour-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: rgba(0, 0, 0, 0.55);
  transition: background 0.3s;
}

.tour-highlight {
  position: fixed;
  border-radius: 10px;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.55);
  background: transparent;
  z-index: 10001;
  transition: all 0.3s ease;
  pointer-events: none;
}

.tour-tooltip {
  position: fixed;
  z-index: 10002;
  background: #fff;
  border-radius: 14px;
  padding: 20px;
  width: 320px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.18);
  animation: tour-fade-in 0.25s ease;
}

.tour-tooltip-step {
  font-size: 11px;
  font-weight: 700;
  color: var(--td-brand-color, #0052d9);
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}

.tour-tooltip-title {
  font-size: 16px;
  font-weight: 800;
  color: #1a1a2e;
  margin-bottom: 8px;
  line-height: 1.4;
}

.tour-tooltip-desc {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.7;
  margin-bottom: 16px;
}

.tour-tooltip-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tour-tooltip-spacer { flex: 1; }

/* ── Modal ── */

.tour-modal {
  position: fixed;
  z-index: 10002;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: #fff;
  border-radius: 20px;
  padding: 40px 36px 32px;
  width: 400px;
  max-width: 90vw;
  text-align: center;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.2);
  animation: tour-fade-in 0.3s ease;
}

.tour-modal-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.tour-modal-title {
  font-size: 22px;
  font-weight: 800;
  color: #1a1a2e;
  margin-bottom: 12px;
}

.tour-modal-desc {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.7;
  margin-bottom: 28px;
}

.tour-modal-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* ── Buttons ── */

.tour-btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
}

.tour-btn-primary {
  background: var(--td-brand-color, #0052d9);
  color: #fff;
}
.tour-btn-primary:hover {
  filter: brightness(1.1);
}

.tour-btn-ghost {
  background: transparent;
  color: #6b7280;
}
.tour-btn-ghost:hover {
  background: #f3f4f6;
  color: #374151;
}

@keyframes tour-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Modal needs its own transform animation since it already uses translate */
.tour-modal {
  animation: tour-modal-in 0.3s ease;
}
@keyframes tour-modal-in {
  from { opacity: 0; transform: translate(-50%, -48%); }
  to { opacity: 1; transform: translate(-50%, -50%); }
}
</style>
