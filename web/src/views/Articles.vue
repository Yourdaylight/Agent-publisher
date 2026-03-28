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

    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
      <div>
        <h3 style="margin: 0 0 8px 0">文章管理</h3>
        <p style="margin: 0; color: var(--td-text-color-secondary); font-size: 13px">
          共 {{ articles.length }} 篇文章 · 已发布 {{ publishedCount }} 篇 · 草稿 {{ draftCount }} 篇
        </p>
      </div>
    </div>

    <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap">
      <t-select v-model="filterAgentId" placeholder="筛选 Agent" clearable style="width: 200px" @change="fetchData">
        <t-option v-for="a in agentOptions" :key="a.id" :label="a.name" :value="a.id" />
      </t-select>
      <t-select v-model="filterStatus" placeholder="筛选状态" clearable style="width: 160px" @change="fetchData">
        <t-option label="草稿" value="draft" />
        <t-option label="已发布" value="published" />
      </t-select>
      <!-- 权限组筛选：仅管理员可见 -->
      <t-select
        v-if="isAdmin"
        v-model="filterGroupId"
        placeholder="按权限组筛选"
        clearable
        style="width: 200px"
        @change="fetchData"
      >
        <t-option v-for="g in groupOptions" :key="g.id" :label="g.name" :value="g.id" />
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
        <div style="display: flex; gap: 4px; flex-wrap: wrap">
          <t-tooltip :content="`预览文章：${row.title}`">
            <t-button
              theme="primary"
              variant="text"
              size="small"
              @click="openPreview(row)"
            >
              👁
            </t-button>
          </t-tooltip>
          <t-tooltip content="编辑文章">
            <t-button
              theme="primary"
              variant="text"
              size="small"
              @click="openEditor(row)"
            >
              ✏️
            </t-button>
          </t-tooltip>

          <t-divider layout="vertical" style="margin: 0 4px" />

          <t-tooltip :content="row.status !== 'published' ? '发布到公众号' : '同步到草稿箱'">
            <t-button
              :theme="row.status !== 'published' ? 'primary' : 'default'"
              variant="text"
              size="small"
              @click="row.status !== 'published' ? onPublish(row) : onSync(row)"
            >
              {{ row.status !== 'published' ? '📤' : '🔄' }}
            </t-button>
          </t-tooltip>

          <t-tooltip content="查看发布记录">
            <t-button
              theme="default"
              variant="text"
              size="small"
              @click="openPublishRecords(row)"
            >
              📋
            </t-button>
          </t-tooltip>

          <template v-if="extensionActions.length > 0">
            <t-divider layout="vertical" style="margin: 0 4px" />
            <t-tooltip v-for="action in extensionActions" :key="action.key" :content="action.label">
              <t-button
                theme="primary"
                variant="text"
                size="small"
                @click="onExtensionAction(action, row)"
              >
                <t-icon :name="action.icon" />
              </t-button>
            </t-tooltip>
          </template>
          <!-- slideshow status tag — shows when a task exists for this article -->
          <t-tag
            v-if="row.slideshowTaskId"
            size="small"
            :theme="row.slideshowStatus === 'success' ? 'success' : row.slideshowStatus === 'failed' ? 'danger' : 'warning'"
            style="margin-left: 4px; cursor: pointer"
            @click="openSlideshowDrawerForArticle(row)"
          >
            {{ row.slideshowStatus === 'success' ? '🎬 已生成' : row.slideshowStatus === 'failed' ? '❌ 失败' : '⏳ 生成中' }}
          </t-tag>
        </div>
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

    <t-dialog
      v-model:visible="publishDialogVisible"
      :header="getPublishDialogTitle()"
      :confirm-btn="publishAction === 'publish' ? '确认发布' : '确认同步'"
      :confirm-loading="publishSubmitting"
      @confirm="executePublishAction"
      width="700px"
      @opened="publishTab = 'select'"
    >
      <t-tabs v-model:value="publishTab" default-value="select">
        <!-- Tab 1: 选择账号 -->
        <t-tab-panel value="select" label="选择目标">
          <div style="padding: 12px 0">
            <div style="margin-bottom: 12px; color: var(--td-text-color-secondary); font-size: 14px">
              请选择要{{ publishAction === 'publish' ? '发布到' : '同步到' }}的公众号，可多选。
              <span v-if="publishTargetIds.length > 0" style="color: var(--td-brand-color); margin-left: 8px">
                已选择 {{ publishTargetIds.length }} 个
              </span>
            </div>

            <t-checkbox-group v-model="publishTargetIds">
              <div style="display: flex; flex-direction: column; gap: 12px">
                <t-checkbox
                  v-for="account in accountOptions"
                  :key="account.id"
                  :value="account.id"
                  :label="`${account.name} (ID: ${account.id})`"
                />
              </div>
            </t-checkbox-group>

            <t-alert
              v-if="accountOptions.length === 0"
              theme="warning"
              style="margin-top: 16px"
            >
              当前没有可用公众号，请先创建账号。
            </t-alert>

            <t-alert
              v-else-if="publishTargetIds.length === 0"
              theme="info"
              style="margin-top: 16px"
            >
              ⚠️ 未选择任何账号。将使用该文章的默认绑定账号（如有）。
            </t-alert>

            <t-alert
              v-else
              theme="success"
              style="margin-top: 16px"
            >
              ✓ 已选择 {{ publishTargetIds.length }} 个账号进行{{ publishAction === 'publish' ? '发布' : '同步' }}
            </t-alert>
          </div>
        </t-tab-panel>

        <!-- Tab 2: 预览内容 -->
        <t-tab-panel value="preview" label="内容预览">
          <div style="padding: 12px 0">
            <div v-if="publishTargetArticle" class="article-preview-container">
              <div style="margin-bottom: 16px">
                <div style="font-size: 18px; font-weight: 600; margin-bottom: 8px">
                  {{ publishTargetArticle.title }}
                </div>
                <div style="color: var(--td-text-color-secondary); font-size: 13px; margin-bottom: 12px">
                  {{ publishTargetArticle.digest }}
                </div>
              </div>

              <div
                v-if="publishTargetArticle.html_content"
                class="article-html-preview"
                v-html="publishTargetArticle.html_content"
                style="
                  border-top: 1px solid var(--td-border-level-1);
                  padding-top: 16px;
                  max-height: 400px;
                  overflow-y: auto;
                  font-size: 14px;
                  line-height: 1.6;
                "
              />

              <div v-else style="color: var(--td-text-color-secondary); text-align: center; padding: 40px 0">
                暂无内容预览
              </div>
            </div>
          </div>
        </t-tab-panel>
      </t-tabs>
    </t-dialog>

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
            {{ row.action === 'publish' ? '📤 发布' : '🔄 同步' }}
          </t-tag>
        </template>
        <template #recordStatus="{ row }">
          <t-tag
            :theme="row.status === 'success' ? 'success' : 'danger'"
            variant="light"
          >
            {{ row.status === 'success' ? '✓ 成功' : '✗ 失败' }}
          </t-tag>
        </template>
        <template #op="{ row }">
          <t-space size="small">
            <t-button
              v-if="row.error_message"
              theme="danger"
              variant="text"
              size="small"
              @click="showErrorDetail(row)"
            >
              错误
            </t-button>
            <t-link v-else theme="primary" disabled>
              -
            </t-link>
          </t-space>
        </template>
      </t-table>
    </t-drawer>

    <!-- Error Detail Dialog -->
    <t-dialog
      v-model:visible="errorDetailVisible"
      header="发布错误详情"
      :footer="false"
      width="600px"
    >
      <div v-if="selectedErrorRecord">
        <t-alert theme="error" style="margin-bottom: 16px">
          <div>账号：{{ selectedErrorRecord.account_name || selectedErrorRecord.account_id }}</div>
          <div>操作：{{ selectedErrorRecord.action === 'publish' ? '发布' : '同步' }}</div>
          <div>时间：{{ new Date(selectedErrorRecord.created_at).toLocaleString() }}</div>
        </t-alert>
        <div style="margin-bottom: 12px; color: var(--td-text-color-secondary); font-size: 13px">
          错误信息：
        </div>
        <pre
          style="
            background: var(--td-bg-color-page);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 12px;
            line-height: 1.5;
            color: var(--td-text-color);
            white-space: pre-wrap;
            word-break: break-all;
          "
        >{{ selectedErrorRecord.error_message }}</pre>
      </div>
    </t-dialog>

    <!-- ===== Slideshow Generation Drawer ===== -->
    <t-drawer
      v-model:visible="slideshowDrawerVisible"
      :header="slideshowPhase === 'preview' ? `预览演示文稿 — ${slideshowArticle?.title || ''}` : `生成演示文稿 — ${slideshowArticle?.title || ''}`"
      size="80%"
      placement="right"
      :close-on-esc-keydown="slideshowPhase === 'setup'"
      :footer="false"
      @close="onSlideshowDrawerClose"
    >
      <div style="padding: 8px 0">
        <!-- Phase: Setup -->
        <div v-if="slideshowPhase === 'setup'">
          <t-card :bordered="true" style="margin-bottom: 20px">
            <div style="font-size: 13px; color: var(--td-text-color-secondary); margin-bottom: 4px">文章</div>
            <div style="font-weight: 600; font-size: 15px">{{ slideshowArticle?.title }}</div>
          </t-card>
          <div style="margin-bottom: 20px">
            <div style="font-weight: 500; margin-bottom: 8px">配置选项</div>
            <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--td-bg-color-page); border-radius: 6px">
              <t-switch v-model="slideshowWithTts" />
              <div>
                <div style="font-size: 14px">语音旁白（TTS）</div>
                <div style="font-size: 12px; color: var(--td-text-color-secondary)">使用 AI 语音为每张幻灯片生成中文旁白，生成时间约增加 1 分钟</div>
              </div>
            </div>
          </div>
          <t-alert theme="info" style="margin-bottom: 20px">
            <template #message>
              生成流程：AI 生成大纲（约30秒）→ {{ slideshowWithTts ? '合成语音（约1分钟）→ ' : '' }}构建幻灯片 → 录制视频（约3-5分钟）
            </template>
          </t-alert>
          <t-button theme="primary" size="large" block :loading="slideshowSubmitting" @click="startSlideshowGeneration">
            开始生成
          </t-button>
        </div>

        <!-- Phase: Progress -->
        <div v-else-if="slideshowPhase === 'progress'">
          <t-alert theme="info" style="margin-bottom: 20px">
            <template #message>正在生成演示文稿，请耐心等待…</template>
          </t-alert>
          <t-steps layout="vertical" :current="slideshowCurrentStep" style="margin-bottom: 24px">
            <t-step-item
              v-for="(step, idx) in slideshowStepDefs"
              :key="step.key"
              :title="step.label"
              :content="step.hint"
              :status="getSlideshowStepStatus(idx)"
            />
          </t-steps>
          <div v-if="slideshowPollError" style="margin-bottom: 16px">
            <t-alert theme="warning">
              <template #message>{{ slideshowPollError }}</template>
            </t-alert>
          </div>
          <t-button variant="outline" block @click="onSlideshowRunInBackground">后台运行（可在任务管理中查看）</t-button>
        </div>

        <!-- Phase: Completed -->
        <div v-else-if="slideshowPhase === 'completed'">
          <t-result theme="success" title="演示文稿已生成" style="margin-bottom: 24px">
            <template #description>
              <div>已生成 {{ slideshowSlideCount }} 张幻灯片{{ slideshowHasSubtitle ? '，含语音字幕' : '' }}</div>
            </template>
          </t-result>
          <div style="display: flex; gap: 12px; flex-direction: column">
            <t-button theme="primary" size="large" block @click="openSlideshowPreview">
              <t-icon name="browse" style="margin-right: 6px" />在线预览演示文稿
            </t-button>
            <t-button size="large" block @click="onDownloadVideo">
              <t-icon name="download" style="margin-right: 6px" />下载视频{{ slideshowVideoExt }}
            </t-button>
            <t-button v-if="slideshowHasSubtitle" variant="text" size="large" block @click="onDownloadSubtitle">
              <t-icon name="file" style="margin-right: 6px" />下载字幕（SRT）
            </t-button>
            <t-divider />
            <t-button variant="outline" @click="onRegenerateSlideshow">重新生成</t-button>
          </div>
        </div>

        <!-- Phase: Failed -->
        <div v-else-if="slideshowPhase === 'failed'">
          <t-result theme="error" title="生成失败" style="margin-bottom: 24px">
            <template #description>{{ slideshowErrorMsg || '生成过程中发生错误，请重试' }}</template>
          </t-result>
          <t-steps layout="vertical" :current="slideshowCurrentStep" style="margin-bottom: 24px">
            <t-step-item
              v-for="(step, idx) in slideshowStepDefs"
              :key="step.key"
              :title="step.label"
              :status="getSlideshowStepStatus(idx)"
            />
          </t-steps>
          <t-button theme="primary" block @click="slideshowPhase = 'setup'">重新生成</t-button>
        </div>

        <!-- Phase: Preview (iframe) -->
        <div v-else-if="slideshowPhase === 'preview'" style="height: calc(100vh - 120px); position: relative">
          <t-loading v-if="slideshowPreviewLoading" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center" />
          <div v-if="slideshowPreviewError" style="padding: 40px; text-align: center">
            <t-result theme="error" title="预览加载失败">
              <template #description>{{ slideshowPreviewError }}</template>
            </t-result>
            <t-button style="margin-top: 16px" @click="onDownloadVideo">下载视频查看</t-button>
          </div>
          <iframe
            v-else
            :src="slideshowPreviewUrl"
            style="width: 100%; height: 100%; border: none; border-radius: 8px; background: #000"
            @load="slideshowPreviewLoading = false"
            @error="onPreviewIframeError"
          />
          <div style="position: absolute; top: 8px; right: 8px; display: flex; gap: 8px">
            <t-button size="small" theme="default" @click="slideshowPhase = 'completed'">← 返回</t-button>
            <t-button size="small" @click="onDownloadVideo">下载视频</t-button>
          </div>
        </div>
      </div>
    </t-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';
import {
  getArticles,
  getArticle,
  updateArticle,
  syncArticle,
  getAgents,
  getAccounts,
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
  getExtensions,
  getGroups,
  generateSlideshow,
  getSlideshowStatus,
  getSlideshowPreviewUrl,
  downloadSlideshowVideo,
  downloadSlideshowSubtitle,
} from '@/api';
import http from '@/api';
import { MessagePlugin, NotifyPlugin } from 'tdesign-vue-next';
import { getUserInfo } from '@/api';

const loading = ref(false);
const articles = ref<any[]>([]);
const agentOptions = ref<any[]>([]);
const accountOptions = ref<any[]>([]);
const groupOptions = ref<any[]>([]);
const filterAgentId = ref<number | undefined>();
const filterStatus = ref<string | undefined>();
const filterGroupId = ref<number | undefined>();
const isAdmin = computed(() => getUserInfo()?.is_admin ?? false);
const previewDrawerVisible = ref(false);
const previewArticle = ref<any>(null);
const runningTasks = ref<any[]>([]);
const publishDialogVisible = ref(false);
const publishSubmitting = ref(false);
const publishAction = ref<'publish' | 'sync'>('publish');
const publishTargetArticle = ref<any>(null);
const publishTargetIds = ref<number[]>([]);
const publishFromEditor = ref(false);
const publishTab = ref<string>('select');  // 'select' | 'preview'
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
const errorDetailVisible = ref(false);
const selectedErrorRecord = ref<any>(null);
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

// Extension actions state
const extensionActions = ref<any[]>([]);

const publishRecordColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'account_name', title: '公众号', width: 180, cell: (_h: any, { row }: any) => row.account_name || (row.account_id ? `#${row.account_id}` : '-') },
  { colKey: 'action', title: '类型', width: 80 },
  { colKey: 'recordStatus', title: '状态', width: 80 },
  { colKey: 'operator', title: '操作人', width: 140 },
  { colKey: 'created_at', title: '时间', width: 160, cell: (_h: any, { row }: any) => row.created_at ? new Date(row.created_at).toLocaleString() : '-' },
  { colKey: 'op', title: '操作', width: 80 },
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

const publishedCount = computed(() => articles.value.filter(a => a.status === 'published').length);
const draftCount = computed(() => articles.value.filter(a => a.status === 'draft').length);

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'agent_id', title: 'Agent ID', width: 90 },
  { colKey: 'status', title: '状态', width: 80 },
  { colKey: 'variant_count', title: '变体', width: 70 },
  { colKey: 'publish_count', title: '发布次数', width: 90 },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
  { colKey: 'op', title: '操作', width: 160 },
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
  const preset = stylePresets.value.find((s) => s.style_id === styleId);
  return preset ? preset.name : styleId;
};

interface AccountScopedResult {
  account_id: number;
  account_name: string;
  status: string;
  wechat_media_id: string;
  stage: string;
  error: string;
}

interface PublishResponsePayload {
  ok: boolean;
  article_id: number;
  overall_status: string;
  results: AccountScopedResult[];
}

const getDefaultAccountIdsForArticle = (row: any): number[] => {
  const relationIds = Array.isArray(row.publish_relations)
    ? row.publish_relations
      .map((item: any) => item.account_id)
      .filter((accountId: number | null | undefined) => Number.isInteger(accountId))
    : [];
  if (relationIds.length > 0) {
    return relationIds;
  }
  const agent = agentOptions.value.find((item) => item.id === row.agent_id);
  return agent?.account_id ? [agent.account_id] : [];
};

const getPublishDialogTitle = (): string => {
  if (!publishTargetArticle.value) {
    return '选择目标公众号';
  }
  const actionText = publishAction.value === 'publish' ? '发布' : '同步';
  return `${actionText}文章 - ${publishTargetArticle.value.title || `#${publishTargetArticle.value.id}`}`;
};

const buildPublishResultMessage = (payload: PublishResponsePayload): string => {
  if (!payload.results || payload.results.length === 0) {
    return payload.overall_status || '已处理';
  }

  const successCount = payload.results.filter((item) => item.status === 'success').length;
  const failedItems = payload.results.filter((item) => item.status !== 'success');

  if (failedItems.length === 0) {
    return `成功处理 ${successCount} 个公众号`;
  }

  const failureSummary = failedItems
    .map((item) => `${item.account_name || `#${item.account_id}`}: ${item.error || item.status}`)
    .join('；');

  return `成功 ${successCount} 个，失败 ${failedItems.length} 个：${failureSummary}`;
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
    if (filterGroupId.value) {
      params.group_id = filterGroupId.value;
    }
    const res = await getArticles(params);
    articles.value = res.data;
  } catch {
    // ignore
  } finally {
    loading.value = false;
  }
};

const fetchAccounts = async () => {
  try {
    const res = await getAccounts();
    accountOptions.value = res.data || [];
  } catch {
    accountOptions.value = [];
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

const onSave = async (): Promise<boolean> => {
  if (!editForm.value.id) {
    return false;
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
    return true;
  } catch (err: any) {
    MessagePlugin.error(err?.response?.data?.detail || '保存失败');
    return false;
  } finally {
    saving.value = false;
  }
};

const openPublishDialog = (row: any, action: 'publish' | 'sync', fromEditor = false) => {
  publishAction.value = action;
  publishTargetArticle.value = row;
  publishFromEditor.value = fromEditor;
  publishTargetIds.value = getDefaultAccountIdsForArticle(row);
  publishDialogVisible.value = true;
};

const executePublishAction = async () => {
  if (!publishTargetArticle.value?.id) {
    MessagePlugin.error('请先选择要发布的文章');
    return;
  }

  if (publishTargetIds.value.length === 0) {
    MessagePlugin.error('请至少选择一个目标公众号');
    return;
  }

  publishSubmitting.value = true;
  if (publishFromEditor.value) {
    syncing.value = true;
  }

  try {
    if (publishFromEditor.value) {
      const saveSucceeded = await onSave();
      if (!saveSucceeded) {
        MessagePlugin.error('保存文章失败，请重试');
        return;
      }
    }

    const articleId = publishTargetArticle.value.id;
    const actionText = publishAction.value === 'publish' ? '发布' : '同步';

    // Log for debugging
    console.log(`[${actionText}] Article ID: ${articleId}, Target Accounts:`, publishTargetIds.value);

    const requestData = {
      target_account_ids: publishTargetIds.value.length > 0 ? publishTargetIds.value : undefined,
    };

    const request = publishAction.value === 'publish'
      ? publishArticle(articleId, requestData)
      : syncArticle(articleId, requestData);

    const res = await request;
    console.log(`[${actionText}] Response:`, res.data);

    const payload = res.data as PublishResponsePayload;
    const message = buildPublishResultMessage(payload);

    if (payload.ok) {
      MessagePlugin.success(`${actionText}完成：${message}`);
    } else {
      MessagePlugin.warning(`${actionText}完成：${message}`);
    }

    publishDialogVisible.value = false;
    await Promise.all([fetchData(), fetchAccounts()]);

    if (publishTargetArticle.value) {
      await openPublishRecords(publishTargetArticle.value);
    }
  } catch (err: any) {
    console.error(`[${publishAction.value}] Error:`, err);
    const errorMsg = err?.response?.data?.detail
      || err?.response?.data?.message
      || err?.message
      || `${publishAction.value === 'publish' ? '发布' : '同步'}失败，请检查日志`;
    MessagePlugin.error(errorMsg);
  } finally {
    publishSubmitting.value = false;
    if (publishFromEditor.value) {
      syncing.value = false;
    }
  }
};

const onSyncFromEditor = async () => {
  if (!editForm.value.id) {
    return;
  }
  openPublishDialog({
    id: editForm.value.id,
    title: editForm.value.title,
    agent_id: articles.value.find((item) => item.id === editForm.value.id)?.agent_id,
    publish_relations: articles.value.find((item) => item.id === editForm.value.id)?.publish_relations || [],
  }, 'sync', true);
};

const onSync = async (row: any) => {
  openPublishDialog(row, 'sync');
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
  openPublishDialog(row, 'publish');
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

const showErrorDetail = (record: any) => {
  selectedErrorRecord.value = record;
  errorDetailVisible.value = true;
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

// --- Extension action handler ---
// ============================================================
// Slideshow Generation State & Logic
// ============================================================

// Step definitions (shown in the progress stepper)
const slideshowStepDefs = [
  { key: 'llm_outline',   label: 'AI 生成内容大纲',  hint: '约 20-40 秒' },
  { key: 'tts_generate',  label: '合成语音旁白',       hint: '约 30-60 秒（跳过时自动跳过）' },
  { key: 'build_html',    label: '构建演示文稿',       hint: '约 5 秒' },
  { key: 'video_export',  label: '录制视频',           hint: '约 2-5 分钟' },
] as const;

const TERMINAL_STATES = ['success', 'failed', 'cancelled', 'expired'] as const;
const MAX_POLL_RETRIES = 120;
const POLL_INTERVAL_MS = 3000;
const VIDEO_EXPORT_POLL_MS = 8000; // back off during slow step

// Per-article slideshow task state
type SlideshowState = {
  taskId: number | null;
  status: string;
  phase: 'setup' | 'progress' | 'completed' | 'failed' | 'preview';
};
const slideshowStateMap = ref(new Map<number, SlideshowState>());

// Active drawer state
const slideshowDrawerVisible = ref(false);
const slideshowArticle = ref<any>(null);
const slideshowPhase = ref<'setup' | 'progress' | 'completed' | 'failed' | 'preview'>('setup');
const slideshowWithTts = ref(true);
const slideshowSubmitting = ref(false);
const slideshowTaskId = ref<number | null>(null);
const slideshowSteps = ref<any[]>([]);
const slideshowPollError = ref('');
const slideshowErrorMsg = ref('');
const slideshowCurrentStep = ref(0);
const slideshowHasSubtitle = ref(false);
const slideshowHasVideo = ref(false);
const slideshowVideoExt = ref('.webm');
const slideshowSlideCount = ref(0);
// Preview
const slideshowPreviewUrl = ref('');
const slideshowPreviewLoading = ref(false);
const slideshowPreviewError = ref('');

// Polling cleanup
let slideshowPollTimer: ReturnType<typeof setTimeout> | null = null;
let slideshowPollRetries = 0;
let slideshowActivePollTaskId: number | null = null;

function clearSlideshowPoll() {
  if (slideshowPollTimer) {
    clearTimeout(slideshowPollTimer);
    slideshowPollTimer = null;
  }
  slideshowActivePollTaskId = null;
}

function getSlideshowStepStatus(idx: number): 'default' | 'process' | 'finish' | 'error' {
  const steps = slideshowSteps.value;
  // Find the step by key
  const stepKey = slideshowStepDefs[idx]?.key;
  const matchedStep = steps.find((s: any) => s.name === stepKey);
  if (!matchedStep) {
    // Not started yet
    if (idx < slideshowCurrentStep.value) return 'finish';
    if (idx === slideshowCurrentStep.value) return 'process';
    return 'default';
  }
  if (matchedStep.status === 'success') return 'finish';
  if (matchedStep.status === 'running') return 'process';
  if (matchedStep.status === 'failed' || matchedStep.status === 'error') return 'error';
  return 'default';
}

function computeCurrentStep(steps: any[]): number {
  let current = 0;
  for (let i = 0; i < slideshowStepDefs.length; i++) {
    const matched = steps.find((s: any) => s.name === slideshowStepDefs[i].key);
    if (matched && (matched.status === 'success' || matched.status === 'running')) {
      current = i;
    }
  }
  return current;
}

async function scheduleSlideshowPoll(taskId: number) {
  if (slideshowActivePollTaskId !== taskId) return; // stale poll
  if (slideshowPollRetries >= MAX_POLL_RETRIES) {
    slideshowPollError.value = '生成超时，请前往任务中心查看状态';
    return;
  }

  try {
    const { data } = await getSlideshowStatus(taskId);
    if (slideshowActivePollTaskId !== taskId) return; // navigated away

    slideshowSteps.value = data.steps || [];
    slideshowCurrentStep.value = computeCurrentStep(slideshowSteps.value);

    if (data.status === 'success') {
      slideshowPhase.value = 'completed';
      slideshowHasSubtitle.value = data.has_subtitle;
      slideshowHasVideo.value = data.has_video;
      // detect .webm vs .mp4 from steps result (heuristic — backend always returns actual ext)
      slideshowVideoExt.value = '.webm';

      // Count slides from steps output
      const outlineStep = (data.steps || []).find((s: any) => s.name === 'llm_outline');
      slideshowSlideCount.value = outlineStep?.output?.slide_count || 0;

      // Update per-article map
      if (slideshowArticle.value?.id) {
        const state = slideshowStateMap.value.get(slideshowArticle.value.id);
        if (state) { state.status = 'success'; state.phase = 'completed'; }
        // Update articles list tag
        const art = articles.value.find(a => a.id === slideshowArticle.value.id);
        if (art) { art.slideshowTaskId = taskId; art.slideshowStatus = 'success'; }
      }
      clearSlideshowPoll();
      return;
    }

    if (data.status === 'failed') {
      slideshowPhase.value = 'failed';
      slideshowErrorMsg.value = data.error || '生成失败，请重试';
      if (slideshowArticle.value?.id) {
        const art = articles.value.find(a => a.id === slideshowArticle.value.id);
        if (art) { art.slideshowStatus = 'failed'; }
      }
      clearSlideshowPoll();
      return;
    }

    // Still running — schedule next poll with backoff for video_export step
    slideshowPollRetries++;
    const isVideoStep = (data.steps || []).some(
      (s: any) => s.name === 'video_export' && s.status === 'running'
    );
    const delay = isVideoStep ? VIDEO_EXPORT_POLL_MS : POLL_INTERVAL_MS;
    slideshowPollTimer = setTimeout(() => scheduleSlideshowPoll(taskId), delay);

  } catch (err: any) {
    if (slideshowActivePollTaskId !== taskId) return;
    if (err?.response?.status === 404) {
      slideshowPhase.value = 'failed';
      slideshowErrorMsg.value = '任务已过期，请重新生成';
      clearSlideshowPoll();
      return;
    }
    // Network error — retry with doubled delay
    slideshowPollRetries++;
    slideshowPollTimer = setTimeout(() => scheduleSlideshowPoll(taskId), POLL_INTERVAL_MS * 2);
  }
}

function openSlideshowDrawerForArticle(article: any) {
  slideshowArticle.value = article;
  slideshowDrawerVisible.value = true;

  // If there's an existing task, restore its phase
  const existing = slideshowStateMap.value.get(article.id);
  if (existing?.taskId) {
    slideshowTaskId.value = existing.taskId;
    slideshowPhase.value = existing.phase;
    // If still in progress, resume polling
    if (existing.phase === 'progress') {
      slideshowActivePollTaskId = existing.taskId;
      slideshowPollRetries = 0;
      scheduleSlideshowPoll(existing.taskId);
    }
  } else if (article.slideshowTaskId && article.slideshowStatus === 'success') {
    slideshowTaskId.value = article.slideshowTaskId;
    slideshowPhase.value = 'completed';
  } else {
    slideshowPhase.value = 'setup';
    slideshowTaskId.value = null;
    slideshowPollError.value = '';
    slideshowErrorMsg.value = '';
    slideshowSteps.value = [];
  }
}

async function startSlideshowGeneration() {
  if (slideshowSubmitting.value || !slideshowArticle.value) return;
  slideshowSubmitting.value = true;
  slideshowPollError.value = '';
  slideshowPollRetries = 0;

  try {
    const { data } = await generateSlideshow(slideshowArticle.value.id, slideshowWithTts.value);
    const taskId = data.task_id;
    slideshowTaskId.value = taskId;
    slideshowPhase.value = 'progress';

    // Update article row tag
    const art = articles.value.find(a => a.id === slideshowArticle.value.id);
    if (art) { art.slideshowTaskId = taskId; art.slideshowStatus = 'running'; }

    // Store state
    slideshowStateMap.value.set(slideshowArticle.value.id, {
      taskId,
      status: 'running',
      phase: 'progress',
    });

    // Start polling
    slideshowActivePollTaskId = taskId;
    slideshowPollTimer = setTimeout(() => scheduleSlideshowPoll(taskId), POLL_INTERVAL_MS);

  } catch (err: any) {
    slideshowPhase.value = 'failed';
    slideshowErrorMsg.value = err?.response?.data?.detail || '启动生成失败';
  } finally {
    slideshowSubmitting.value = false;
  }
}

function onSlideshowRunInBackground() {
  slideshowDrawerVisible.value = false;
  NotifyPlugin.info({
    title: '演示文稿生成中',
    content: '完成后点击文章行的标签查看结果',
    duration: 5000,
  });
}

function onSlideshowDrawerClose() {
  // Don't stop polling if still in progress — run in background
  if (slideshowPhase.value === 'progress') {
    // Keep polling, drawer just closes
  } else {
    clearSlideshowPoll();
  }
  // Clean up preview URL
  slideshowPreviewUrl.value = '';
  slideshowPreviewError.value = '';
}

function openSlideshowPreview() {
  if (!slideshowTaskId.value) return;
  slideshowPreviewUrl.value = getSlideshowPreviewUrl(slideshowTaskId.value);
  slideshowPreviewLoading.value = true;
  slideshowPreviewError.value = '';
  slideshowPhase.value = 'preview';
}

function onPreviewIframeError() {
  slideshowPreviewLoading.value = false;
  slideshowPreviewError.value = '演示文稿预览加载失败，Reveal.js 资源可能无法访问，请直接下载查看';
}

function onDownloadVideo() {
  if (!slideshowTaskId.value) return;
  // Detect WeChat WebView
  if (/MicroMessenger/i.test(navigator.userAgent)) {
    MessagePlugin.warning('微信内无法直接下载，请复制链接到外部浏览器');
    return;
  }
  downloadSlideshowVideo(slideshowTaskId.value);
}

function onDownloadSubtitle() {
  if (!slideshowTaskId.value) return;
  downloadSlideshowSubtitle(slideshowTaskId.value);
}

function onRegenerateSlideshow() {
  clearSlideshowPoll();
  slideshowPhase.value = 'setup';
  slideshowTaskId.value = null;
  slideshowSteps.value = [];
  slideshowPollError.value = '';
  slideshowErrorMsg.value = '';
}

const onExtensionAction = async (action: any, article: any) => {
  if (action.key === 'slideshow_generate') {
    openSlideshowDrawerForArticle(article);
  } else {
    // Generic extension action
    try {
      const { data } = await http.post(action.endpoint, { article_id: article.id });
      MessagePlugin.success(`${action.label} 任务已创建`);
      console.log('Extension action result:', data);
    } catch (err: any) {
      MessagePlugin.error(err?.response?.data?.detail || `${action.label} 失败`);
    }
  }
};

onMounted(async () => {
  try {
    const [agentsRes, accountsRes] = await Promise.all([
      getAgents(),
      getAccounts(),
    ]);
    agentOptions.value = agentsRes.data;
    accountOptions.value = accountsRes.data || [];
  } catch {
    // ignore
  }
  // Load groups for admin filter
  if (isAdmin.value) {
    try {
      const groupsRes = await getGroups();
      groupOptions.value = groupsRes.data || [];
    } catch {
      // ignore
    }
  }
  // Load extension actions (graceful: empty array if none installed)
  try {
    const { data } = await getExtensions();
    extensionActions.value = (data.extensions || []).flatMap((e: any) => e.article_actions || []);
  } catch {
    // no extensions available
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
  clearSlideshowPoll();
});

// Route leave guard — warn if slideshow is generating
onBeforeRouteLeave((_to, _from, next) => {
  if (slideshowPhase.value === 'progress' && slideshowActivePollTaskId) {
    // Allow navigation — poll continues in background until component unmounts
    next();
  } else {
    next();
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
