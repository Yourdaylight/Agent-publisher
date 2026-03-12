<template>
  <div style="max-width: 900px; margin: 0 auto">
    <t-card :bordered="true" style="margin-bottom: 24px">
      <div style="text-align: center; padding: 16px 0">
        <h2 style="margin: 0 0 8px">快速配置指引</h2>
        <p style="color: var(--td-text-color-secondary); margin: 0">
          按照以下 6 步完成从微信公众号注册到生成第一篇文章的完整流程
        </p>
      </div>
    </t-card>

    <t-steps :current="currentStep" theme="dot" style="margin-bottom: 32px">
      <t-step-item title="注册公众号" />
      <t-step-item title="获取密钥" />
      <t-step-item title="IP 白名单" />
      <t-step-item title="添加公众号" />
      <t-step-item title="创建 Agent" />
      <t-step-item title="生成文章" />
    </t-steps>

    <!-- Step 1: 注册微信公众号 -->
    <t-card v-if="currentStep === 0" title="第 1 步：注册微信公众号" :bordered="true">
      <t-alert theme="info" style="margin-bottom: 16px">
        <template #message>
          如果你已经有公众号，可以直接跳过此步骤。
        </template>
      </t-alert>
      <div style="line-height: 2">
        <p><strong>1.</strong> 访问微信公众平台：<t-link theme="primary" href="https://mp.weixin.qq.com" target="_blank">mp.weixin.qq.com</t-link></p>
        <p><strong>2.</strong> 点击右上角「立即注册」，选择账号类型</p>
        <p><strong>订阅号 vs 服务号区别：</strong></p>
        <t-table :data="accountTypes" :columns="accountTypeCols" row-key="type" size="small" style="margin-bottom: 16px" />
        <p><strong>推荐：</strong>个人开发者选择<strong>订阅号</strong>，企业选择<strong>服务号</strong></p>
        <p><strong>3.</strong> 按照指引完成邮箱验证、信息登记、公众号信息填写</p>
        <div style="margin-top: 16px; border: 1px solid var(--td-border-level-2-color); border-radius: 8px; overflow: hidden">
          <img src="/guide-images/step1-register.png" alt="公众号注册页面" style="width: 100%; display: block" />
        </div>
        <p style="color: var(--td-text-color-placeholder); font-size: 12px; margin-top: 4px">
          ↑ 注册页面示例：依次填写邮箱、验证码和密码
        </p>
      </div>
      <template #footer>
        <div style="text-align: right">
          <t-button theme="primary" @click="currentStep = 1">下一步</t-button>
        </div>
      </template>
    </t-card>

    <!-- Step 2: 获取开发者密钥 -->
    <t-card v-if="currentStep === 1" title="第 2 步：获取开发者密钥" :bordered="true">
      <div style="line-height: 2">
        <p><strong>1.</strong> 登录 <t-link theme="primary" href="https://mp.weixin.qq.com" target="_blank">微信公众平台</t-link></p>
        <p><strong>2.</strong> 左侧菜单进入「设置与开发」->「基本配置」</p>
        <p><strong>3.</strong> 在「公众号开发信息」区域：</p>
        <ul>
          <li>复制 <strong>AppID（应用ID）</strong></li>
          <li>点击「重置」获取 <strong>AppSecret（应用密钥）</strong></li>
        </ul>
        <t-alert theme="warning" style="margin: 12px 0">
          <template #message>
            AppSecret 只在重置时显示一次，请立即保存！如果忘记需要再次重置。
          </template>
        </t-alert>
        <p><strong>4.</strong> 妥善保存 AppID 和 AppSecret，后续步骤需要使用</p>
        <div style="margin-top: 16px; border: 1px solid var(--td-border-level-2-color); border-radius: 8px; overflow: hidden">
          <img src="/guide-images/step2-developer-platform.png" alt="微信开发者平台" style="width: 100%; display: block" />
        </div>
        <p style="color: var(--td-text-color-placeholder); font-size: 12px; margin-top: 4px">
          ↑ 在微信开发者平台左侧菜单选择「公众号」，查看基础信息和开发密钥
        </p>
        <div style="margin-top: 12px; border: 1px solid var(--td-border-level-2-color); border-radius: 8px; overflow: hidden">
          <img src="/guide-images/step3-appid-secret.png" alt="获取AppID和AppSecret" style="width: 100%; display: block" />
        </div>
        <p style="color: var(--td-text-color-placeholder); font-size: 12px; margin-top: 4px">
          ↑ 红框标注的是你需要复制的 AppID、AppSecret 和 IP 白名单位置
        </p>
      </div>
      <template #footer>
        <div style="display: flex; justify-content: space-between">
          <t-button variant="outline" @click="currentStep = 0">上一步</t-button>
          <t-button theme="primary" @click="currentStep = 2">下一步</t-button>
        </div>
      </template>
    </t-card>

    <!-- Step 3: 配置 IP 白名单 -->
    <t-card v-if="currentStep === 2" title="第 3 步：配置 IP 白名单" :bordered="true">
      <div style="line-height: 2">
        <p>微信公众号 API 要求将服务器 IP 加入白名单才能调用。</p>
        <p><strong>1.</strong> 在「基本配置」页面找到「IP白名单」，点击「查看」或「修改」</p>
        <p><strong>2.</strong> 查询你的服务器公网 IP：</p>
        <t-card :bordered="true" style="background: var(--td-bg-color-container-hover); margin: 8px 0 16px">
          <code style="font-size: 14px">curl ifconfig.me</code>
        </t-card>
        <p><strong>3.</strong> 将获取到的 IP 地址添加到白名单中</p>
        <div style="margin-top: 12px; border: 1px solid var(--td-border-level-2-color); border-radius: 8px; overflow: hidden">
          <img src="/guide-images/step3-appid-secret.png" alt="IP白名单位置" style="width: 100%; display: block" />
        </div>
        <p style="color: var(--td-text-color-placeholder); font-size: 12px; margin-top: 4px">
          ↑ 「API IP白名单」在开发密钥区域下方，点击「编辑」添加服务器 IP
        </p>
        <t-alert theme="info" style="margin-top: 12px">
          <template #message>
            家用宽带的公网 IP 可能会变化，建议使用固定 IP 的云服务器部署。
          </template>
        </t-alert>
      </div>
      <template #footer>
        <div style="display: flex; justify-content: space-between">
          <t-button variant="outline" @click="currentStep = 1">上一步</t-button>
          <t-button theme="primary" @click="currentStep = 3">下一步</t-button>
        </div>
      </template>
    </t-card>

    <!-- Step 4: 添加公众号到本平台 -->
    <t-card v-if="currentStep === 3" title="第 4 步：添加公众号到本平台" :bordered="true">
      <t-alert v-if="createdAccount" theme="success" style="margin-bottom: 16px">
        <template #message>
          公众号「{{ createdAccount.name }}」已添加成功！ID: {{ createdAccount.id }}
        </template>
      </t-alert>
      <AccountForm v-if="!createdAccount" :hide-submit="false" @success="onAccountCreated" />
      <template #footer>
        <div style="display: flex; justify-content: space-between">
          <t-button variant="outline" @click="currentStep = 2">上一步</t-button>
          <t-button theme="primary" :disabled="!createdAccount" @click="currentStep = 4">下一步</t-button>
        </div>
      </template>
    </t-card>

    <!-- Step 5: 创建 Agent -->
    <t-card v-if="currentStep === 4" title="第 5 步：选择主题创建 Agent" :bordered="true">
      <t-alert v-if="createdAgent" theme="success" style="margin-bottom: 16px">
        <template #message>
          Agent「{{ createdAgent.name }}」已创建成功！ID: {{ createdAgent.id }}
        </template>
      </t-alert>
      <AgentForm
        v-if="!createdAgent"
        :hide-submit="false"
        :preset-account-id="createdAccount?.id"
        @success="onAgentCreated"
      />
      <template #footer>
        <div style="display: flex; justify-content: space-between">
          <t-button variant="outline" @click="currentStep = 3">上一步</t-button>
          <t-button theme="primary" :disabled="!createdAgent" @click="currentStep = 5">下一步</t-button>
        </div>
      </template>
    </t-card>

    <!-- Step 6: 生成第一篇文章 -->
    <t-card v-if="currentStep === 5" title="第 6 步：生成第一篇文章" :bordered="true">
      <div v-if="!generateTask">
        <p style="line-height: 2">
          一切准备就绪！点击下方按钮，Agent 将自动从 RSS 源抓取最新资讯，通过 AI 生成一篇公众号文章。
        </p>
        <div style="text-align: center; padding: 24px 0">
          <t-button theme="primary" size="large" :loading="generating" @click="onGenerate">
            生成文章
          </t-button>
        </div>
      </div>

      <div v-else>
        <t-alert :theme="taskAlertTheme" style="margin-bottom: 16px">
          <template #message>
            任务状态：{{ generateTask.status }}
            <span v-if="generateTask.status === 'running'">（自动刷新中...）</span>
          </template>
        </t-alert>

        <div v-if="generatedArticle" style="margin-top: 16px">
          <h3>{{ generatedArticle.title }}</h3>
          <p style="color: var(--td-text-color-secondary)">{{ generatedArticle.digest }}</p>
          <t-divider />
          <div v-html="generatedArticle.html_content" style="line-height: 1.8" />
        </div>
      </div>

      <template #footer>
        <div style="display: flex; justify-content: space-between">
          <t-button variant="outline" @click="currentStep = 4">上一步</t-button>
          <t-button theme="primary" @click="$router.push('/dashboard')">完成，进入仪表盘</t-button>
        </div>
      </template>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { generateForAgent, getTask, getArticles } from '@/api'
import AccountForm from '@/components/AccountForm.vue'
import AgentForm from '@/components/AgentForm.vue'

const currentStep = ref(0)
const createdAccount = ref<any>(null)
const createdAgent = ref<any>(null)
const generating = ref(false)
const generateTask = ref<any>(null)
const generatedArticle = ref<any>(null)

const accountTypes = [
  { type: '订阅号', frequency: '每天 1 次', auth: '个人/企业', api: '基础接口' },
  { type: '服务号', frequency: '每月 4 次', auth: '企业/组织', api: '高级接口（支付等）' },
]

const accountTypeCols = [
  { colKey: 'type', title: '类型', width: 100 },
  { colKey: 'frequency', title: '群发频率', width: 120 },
  { colKey: 'auth', title: '认证主体', width: 120 },
  { colKey: 'api', title: 'API 权限' },
]

const taskAlertTheme = computed(() => {
  if (!generateTask.value) return 'info'
  const s = generateTask.value.status
  if (s === 'done') return 'success'
  if (s === 'failed') return 'error'
  return 'info'
})

const onAccountCreated = (data: any) => {
  createdAccount.value = data
}

const onAgentCreated = (data: any) => {
  createdAgent.value = data
}

const onGenerate = async () => {
  if (!createdAgent.value) return
  generating.value = true
  try {
    const res = await generateForAgent(createdAgent.value.id)
    generateTask.value = { id: res.data.task_id, status: res.data.status }
    pollTask(res.data.task_id)
  } catch (e) {
    console.error(e)
    generating.value = false
  }
}

const pollTask = async (taskId: number) => {
  const poll = async () => {
    try {
      const res = await getTask(taskId)
      generateTask.value = res.data
      if (res.data.status === 'running' || res.data.status === 'pending') {
        setTimeout(poll, 3000)
      } else {
        generating.value = false
        if (res.data.status === 'done') {
          loadArticle()
        }
      }
    } catch {
      generating.value = false
    }
  }
  poll()
}

const loadArticle = async () => {
  try {
    const res = await getArticles({ agent_id: createdAgent.value.id })
    if (res.data.length > 0) {
      const { getArticle } = await import('@/api')
      const detail = await getArticle(res.data[0].id)
      generatedArticle.value = detail.data
    }
  } catch {}
}
</script>
