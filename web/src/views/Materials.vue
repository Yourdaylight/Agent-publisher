<template>
  <div>
    <!-- Header: Title + Tabs + Upload buttons -->
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px; gap: 12px; flex-wrap: wrap; align-items: center">
      <h3 style="margin: 0">素材库</h3>
      <t-space>
        <t-button v-if="libraryMode === 'candidate'" theme="primary" @click="showUploadDialog = true">
          <template #icon><t-icon name="upload" /></template>
          手动上传
        </t-button>
        <t-button v-if="libraryMode === 'media'" theme="primary" @click="showMediaUploadDialog = true">
          <template #icon><t-icon name="upload" /></template>
          上传图片
        </t-button>
        <t-button v-if="libraryMode === 'media'" theme="default" @click="showMarkdownUploadDialog = true">
          <template #icon><t-icon name="upload" /></template>
          上传 Markdown
        </t-button>
      </t-space>
    </div>

    <!-- Three-tab navigation -->
    <t-tabs v-model="libraryMode" @change="onTabChange" style="margin-bottom: 16px">
      <t-tab-panel value="trending" label="🔥 热点素材" />
      <t-tab-panel value="candidate" label="📦 内容素材" />
      <t-tab-panel value="media" label="🖼 图片素材" />
    </t-tabs>

    <!-- Filter bar -->
    <t-card :bordered="true" style="margin-bottom: 16px">
      <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end">
        <!-- Trending filters -->
        <template v-if="libraryMode === 'trending'">
          <div style="min-width: 160px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">Agent</div>
            <t-select v-model="filters.agent_id" placeholder="全部 Agent" clearable @change="fetchData">
              <t-option v-for="a in agents" :key="a.id" :value="a.id" :label="a.name" />
            </t-select>
          </div>
          <div style="min-width: 140px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">平台</div>
            <t-select v-model="trendingPlatformFilter" placeholder="全部平台" clearable multiple @change="fetchData">
              <t-option v-for="p in availablePlatforms" :key="p" :value="p" :label="p" />
            </t-select>
          </div>
          <div style="min-width: 120px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">质量分</div>
            <t-select v-model="trendingQualityFilter" placeholder="全部" clearable @change="fetchData">
              <t-option value="0.5" label="≥ 0.5 (高热)" />
              <t-option value="0.3" label="≥ 0.3 (中热)" />
            </t-select>
          </div>
          <t-button
            theme="primary"
            :loading="collecting"
            @click="onCollect"
          >
            <template #icon><t-icon name="refresh" /></template>
            一键采集
          </t-button>
        </template>
        <!-- Candidate filters -->
        <template v-if="libraryMode === 'candidate'">
          <div style="min-width: 160px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">Agent</div>
            <t-select v-model="filters.agent_id" placeholder="全部 Agent" clearable @change="fetchData">
              <t-option v-for="a in agents" :key="a.id" :value="a.id" :label="a.name" />
            </t-select>
          </div>
          <div style="min-width: 140px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">来源类型</div>
            <t-select v-model="filters.source_type" placeholder="全部类型" clearable @change="fetchData">
              <t-option value="rss" label="RSS" />
              <t-option value="search" label="网络搜索" />
              <t-option value="skills_feed" label="Skills 供稿" />
              <t-option value="manual" label="手动上传" />
              <t-option value="trending" label="🔥 热点" />
            </t-select>
          </div>
          <div style="min-width: 120px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">状态</div>
            <t-select v-model="filters.status" placeholder="全部状态" clearable @change="fetchData">
              <t-option value="pending" label="待处理" />
              <t-option value="accepted" label="已采纳" />
              <t-option value="rejected" label="已拒绝" />
            </t-select>
          </div>
        </template>
        <!-- Media filters -->
        <template v-if="libraryMode === 'media'">
          <div style="min-width: 160px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">素材来源</div>
            <t-select v-model="filters.media_source_kind" placeholder="全部来源" clearable @change="fetchData">
              <t-option value="manual" label="手动上传" />
              <t-option value="article_body" label="正文图片" />
              <t-option value="article_cover" label="封面图片" />
            </t-select>
          </div>
          <div style="min-width: 180px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">公众号</div>
            <t-select v-model="filters.media_account_id" placeholder="全部公众号" clearable @change="fetchData">
              <t-option v-for="account in accounts" :key="account.id" :value="account.id" :label="account.name" />
            </t-select>
          </div>
          <div style="min-width: 160px">
            <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">上传状态</div>
            <t-select v-model="filters.media_upload_status" placeholder="全部状态" clearable @change="fetchData">
              <t-option value="pending" label="待上传" />
              <t-option value="processing" label="上传中" />
              <t-option value="success" label="已上传" />
              <t-option value="failed" label="上传失败" />
            </t-select>
          </div>
        </template>
        <div style="min-width: 200px">
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 4px">标签筛选</div>
          <t-input v-model="filters.tags" placeholder="输入标签，逗号分隔" clearable @change="fetchData" />
        </div>
        <t-button variant="outline" @click="resetFilters">重置</t-button>
      </div>
    </t-card>

    <!-- Empty state -->
    <t-card v-if="!loading && materials.length === 0" :bordered="true" style="text-align: center; padding: 60px 0">
      <t-icon name="folder-open" size="48px" style="color: var(--td-text-color-placeholder); margin-bottom: 16px" />
      <div style="font-size: 16px; color: var(--td-text-color-secondary); margin-bottom: 8px">
        {{ emptyTitle }}
      </div>
      <div style="font-size: 14px; color: var(--td-text-color-placeholder); margin-bottom: 24px">
        {{ emptyDesc }}
      </div>
      <t-space>
        <t-button v-if="libraryMode === 'trending'" theme="primary" :loading="collecting" @click="onCollect">一键采集热点</t-button>
        <t-button v-if="libraryMode === 'candidate'" theme="primary" @click="showUploadDialog = true">手动上传素材</t-button>
        <t-button v-if="libraryMode === 'media'" theme="primary" @click="showMediaUploadDialog = true">上传图片</t-button>
        <t-button variant="outline" @click="$router.push('/agents')">配置 Agent 采集</t-button>
      </t-space>
    </t-card>

    <!-- Trending card grid -->
    <template v-else-if="libraryMode === 'trending'">
      <div class="trending-grid" :style="{ opacity: loading ? 0.5 : 1 }">
        <div
          v-for="item in filteredTrendingMaterials"
          :key="item.id"
          class="trending-card"
          :style="{ borderLeftColor: qualityBorderColor(item.quality_score) }"
          @click="openDetail(item)"
        >
          <!-- Top row: platform tag + rank + quality bar -->
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px">
            <t-tag size="small" variant="light" theme="primary">
              {{ extractPlatform(item) || '未知来源' }}
            </t-tag>
            <span v-if="extractRank(item)" style="font-size: 12px; font-weight: 600; color: var(--td-error-color)">
              #{{ extractRank(item) }}
            </span>
            <div style="flex: 1" />
            <!-- Quality mini bar -->
            <div v-if="item.quality_score != null" style="display: flex; align-items: center; gap: 4px; min-width: 70px">
              <div style="flex:1; height: 6px; background: var(--td-bg-color-component); border-radius: 3px; overflow: hidden">
                <div :style="{ width: (item.quality_score * 100) + '%', height: '100%', background: qualityBarColor(item.quality_score), borderRadius: '3px', transition: 'width 0.3s' }" />
              </div>
              <span style="font-size: 11px; color: var(--td-text-color-secondary); min-width: 24px; text-align: right">
                {{ (item.quality_score * 100).toFixed(0) }}
              </span>
            </div>
          </div>

          <!-- Title -->
          <div style="font-weight: 600; font-size: 14px; line-height: 1.5; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical">
            {{ item.title || '(无标题)' }}
          </div>

          <!-- Source summary -->
          <div style="font-size: 12px; color: var(--td-text-color-secondary); margin-bottom: 8px; line-height: 1.4">
            <template v-if="extractCrossPlatformInfo(item)">
              热榜来源: {{ extractCrossPlatformInfo(item)!.sources }} | 跨{{ extractCrossPlatformInfo(item)!.count }}平台
            </template>
            <template v-else-if="item.summary">
              {{ item.summary.slice(0, 60) }}{{ item.summary.length > 60 ? '...' : '' }}
            </template>
          </div>

          <!-- Tags (show first 3) -->
          <div style="margin-bottom: 8px">
            <t-space size="4px" v-if="item.tags && item.tags.length">
              <t-tag
                v-for="tag in displayTags(item.tags)"
                :key="tag"
                size="small"
                variant="outline"
                :theme="tag.startsWith('platform:') ? 'primary' : 'default'"
              >
                {{ tag.startsWith('platform:') ? tag.replace('platform:', '') : tag }}
              </t-tag>
              <t-tag v-if="item.tags.length > 3" size="small" variant="light">+{{ item.tags.length - 3 }}</t-tag>
            </t-space>
          </div>

          <!-- Bottom: time + action -->
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--td-text-color-placeholder)">
            <span>{{ formatDate(item.created_at) }}</span>
            <t-link theme="primary" size="small" @click.stop="openDetail(item)">详情</t-link>
          </div>
        </div>
      </div>

      <!-- Trending pagination -->
      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <t-pagination
          :current="filters.page"
          :page-size="filters.page_size"
          :total="total"
          show-jumper
          :page-size-options="[12, 24, 48]"
          @current-change="(v: number) => { filters.page = v; fetchData(); }"
          @page-size-change="(v: number) => { filters.page_size = v; filters.page = 1; fetchData(); }"
        />
      </div>
    </template>

    <!-- Candidate / Media table -->
    <t-table
      v-else
      :data="materials"
      :columns="columns"
      row-key="id"
      :loading="loading"
      stripe
      :pagination="pagination"
      @page-change="onPageChange"
    >
      <template #source_type="{ row }">
        <t-tag :theme="sourceTypeTheme(row.source_type)" variant="light" size="small">
          {{ sourceTypeLabel(row.source_type) }}
        </t-tag>
      </template>
      <template #source_kind="{ row }">
        <t-tag :theme="mediaSourceKindTheme(row.source_kind)" variant="light" size="small">
          {{ mediaSourceKindLabel(row.source_kind) }}
        </t-tag>
      </template>
      <template #filename="{ row }">
        <div style="display: flex; align-items: center; gap: 8px">
          <img
            :src="row.url"
            :alt="row.filename"
            style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px"
          />
          <span>{{ row.filename }}</span>
        </div>
      </template>
      <template #tags="{ row }">
        <t-space size="4px" v-if="row.tags && row.tags.length">
          <t-tag v-for="tag in row.tags.slice(0, 3)" :key="tag" size="small" variant="outline">{{ tag }}</t-tag>
          <t-tag v-if="row.tags.length > 3" size="small" variant="light">+{{ row.tags.length - 3 }}</t-tag>
        </t-space>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #status="{ row }">
        <t-tag :theme="statusTheme(row.status)" variant="light" size="small">{{ statusLabel(row.status) }}</t-tag>
      </template>
      <template #quality_score="{ row }">
        <div v-if="row.quality_score != null" style="display: flex; align-items: center; gap: 6px">
          <div style="flex: 1; height: 6px; background: var(--td-bg-color-component); border-radius: 3px; overflow: hidden">
            <div :style="{ width: (row.quality_score * 100) + '%', height: '100%', background: qualityBarColor(row.quality_score), borderRadius: '3px' }" />
          </div>
          <span style="font-size: 12px; min-width: 24px; text-align: right">{{ (row.quality_score * 100).toFixed(0) }}</span>
        </div>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #latest_upload_status="{ row }">
        <t-tag
          v-if="row.latest_upload_status"
          :theme="uploadStatusTheme(row.latest_upload_status)"
          variant="light"
          size="small"
        >
          {{ uploadStatusLabel(row.latest_upload_status) }}
        </t-tag>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #wechat_mapping_summary="{ row }">
        <t-space size="4px" v-if="row.wechat_mappings && row.wechat_mappings.length">
          <t-tag
            v-for="mapping in row.wechat_mappings.slice(0, 2)"
            :key="mapping.id"
            size="small"
            variant="outline"
            :theme="uploadStatusTheme(mapping.upload_status)"
          >
            {{ accountNameById(mapping.account_id) }} · {{ uploadStatusLabel(mapping.upload_status) }}
          </t-tag>
          <t-tag v-if="row.wechat_mappings.length > 2" size="small" variant="light">
            +{{ row.wechat_mappings.length - 2 }}
          </t-tag>
        </t-space>
        <span v-else style="color: var(--td-text-color-placeholder)">-</span>
      </template>
      <template #created_at="{ row }">{{ formatDate(row.created_at) }}</template>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openDetail(row)">详情</t-link>
          <t-link v-if="libraryMode === 'candidate'" theme="primary" @click="openTagEditor(row)">标签</t-link>
          <t-link v-if="libraryMode === 'media'" theme="primary" :href="row.url" target="_blank">查看</t-link>
          <t-link v-if="libraryMode === 'media'" theme="danger" @click="confirmDeleteMedia(row)">删除</t-link>
        </t-space>
      </template>
    </t-table>

    <!-- Upload dialog (candidate) -->
    <t-dialog v-model:visible="showUploadDialog" header="手动上传素材" :footer="false" width="600px">
      <t-form :data="uploadForm" @submit="onUpload" layout="vertical">
        <t-form-item label="标题" name="title" :rules="[{ required: true, message: '请输入标题' }]">
          <t-input v-model="uploadForm.title" placeholder="输入素材标题" />
        </t-form-item>
        <t-form-item label="内容" name="content">
          <t-textarea v-model="uploadForm.content" placeholder="输入素材内容" :autosize="{ minRows: 4, maxRows: 10 }" />
        </t-form-item>
        <t-form-item label="原始链接" name="original_url">
          <t-input v-model="uploadForm.original_url" placeholder="https://..." />
        </t-form-item>
        <t-form-item label="标签" name="tags">
          <t-input v-model="uploadForm.tagsInput" placeholder="输入标签，逗号分隔" />
        </t-form-item>
        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit" :loading="uploading">上传</t-button>
            <t-button variant="outline" @click="showUploadDialog = false">取消</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Upload dialog (media) -->
    <t-dialog v-model:visible="showMediaUploadDialog" header="上传图片素材" :footer="false" width="600px">
      <t-form :data="mediaUploadForm" @submit="onMediaUpload" layout="vertical">
        <t-form-item label="选择图片" name="file" :rules="[{ required: true, message: '请选择图片文件' }]">
          <t-upload
            v-model="mediaUploadForm.fileList"
            theme="image"
            accept="image/*"
            :auto-upload="false"
            :max="1"
            :size-limit="{ size: 20, unit: 'MB' }"
            @fail="onMediaUploadFail"
          />
        </t-form-item>
        <t-form-item label="标签" name="tags">
          <t-input v-model="mediaUploadForm.tagsInput" placeholder="输入标签，逗号分隔" />
        </t-form-item>
        <t-form-item label="描述" name="description">
          <t-textarea v-model="mediaUploadForm.description" placeholder="输入图片描述" :autosize="{ minRows: 2, maxRows: 4 }" />
        </t-form-item>
        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit" :loading="mediaUploading">上传</t-button>
            <t-button variant="outline" @click="showMediaUploadDialog = false">取消</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Markdown upload dialog -->
    <t-dialog v-model:visible="showMarkdownUploadDialog" header="上传 Markdown" :footer="false" width="700px">
      <t-form layout="vertical">
        <t-form-item label="Markdown 内容">
          <t-textarea
            v-model="markdownUploadForm.content"
            placeholder="粘贴 Markdown 内容，或上传 .md 文件"
            :autosize="{ minRows: 8, maxRows: 16 }"
          />
        </t-form-item>
        <t-form-item label="上传 .md 文件">
          <t-upload
            ref="markdownFileRef"
            theme="file"
            accept=".md,.markdown"
            :size-limit="{ size: 5, unit: 'MB' }"
            @change="onMarkdownFileChange"
          />
        </t-form-item>
        <t-form-item label="图片标签">
          <t-input v-model="markdownUploadForm.tagsInput" placeholder="输入标签，逗号分隔（可选）" />
        </t-form-item>
        <t-form-item v-if="markdownUploadResult">
          <t-alert :theme="markdownUploadResult.images_count > 0 ? 'success' : 'warning'" :title="`处理完成：${markdownUploadResult.images_count} 个图片已上传，${markdownUploadResult.skipped_count} 个跳过`" />
          <div v-if="markdownUploadResult.images.length" style="margin-top: 12px; max-height: 200px; overflow-y: auto">
            <div v-for="img in markdownUploadResult.images" :key="img.media_id" style="font-size: 12px; padding: 4px 0; border-bottom: 1px solid var(--td-border-level-1-color)">
              <div style="color: var(--td-text-color-secondary)">{{ img.filename }}</div>
              <div style="color: var(--td-brand-color)">{{ img.original_url }} → {{ img.url }}</div>
            </div>
          </div>
        </t-form-item>
        <t-form-item>
          <t-space>
            <t-button theme="primary" type="submit" :loading="markdownUploading" @click="onMarkdownUpload">处理并上传图片</t-button>
            <t-button variant="outline" @click="showMarkdownUploadDialog = false; markdownUploadResult = null">取消</t-button>
            <t-button v-if="markdownUploadResult" variant="outline" theme="default" @click="copyProcessedMarkdown">复制处理后的 Markdown</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Detail drawer -->
    <t-drawer v-model:visible="showDetail" :header="detailTitle" size="600px">
      <template v-if="detailMaterial">
        <template v-if="detailMode === 'candidate'">
          <!-- Trending metadata card -->
          <t-card
            v-if="detailMaterial.source_type === 'trending' && detailMaterial.metadata"
            :bordered="true"
            style="margin-bottom: 16px; background: var(--td-bg-color-container-hover)"
          >
            <div style="font-weight: 600; margin-bottom: 12px; font-size: 14px">🔥 热点信息</div>
            <t-descriptions :column="2" bordered size="small">
              <t-descriptions-item label="平台">
                {{ extractPlatform(detailMaterial) || '-' }}
              </t-descriptions-item>
              <t-descriptions-item label="排名">
                <span v-if="extractRank(detailMaterial)" style="font-weight: 600; color: var(--td-error-color)">
                  #{{ extractRank(detailMaterial) }}
                </span>
                <span v-else>-</span>
              </t-descriptions-item>
              <t-descriptions-item label="热度值">
                {{ extractHotValue(detailMaterial) || '-' }}
              </t-descriptions-item>
              <t-descriptions-item label="跨平台次数">
                {{ extractCrossPlatformCount(detailMaterial) || '-' }}
              </t-descriptions-item>
              <t-descriptions-item label="出现平台" :span="2">
                {{ extractAllPlatforms(detailMaterial) || '-' }}
              </t-descriptions-item>
              <t-descriptions-item label="权重分" :span="2">
                {{ extractWeightScore(detailMaterial) || '-' }}
              </t-descriptions-item>
            </t-descriptions>
          </t-card>

          <t-descriptions :column="1" bordered>
            <t-descriptions-item label="ID">{{ detailMaterial.id }}</t-descriptions-item>
            <t-descriptions-item label="来源类型">
              <t-tag :theme="sourceTypeTheme(detailMaterial.source_type)" variant="light" size="small">
                {{ sourceTypeLabel(detailMaterial.source_type) }}
              </t-tag>
            </t-descriptions-item>
            <t-descriptions-item label="来源标识">{{ detailMaterial.source_identity || '-' }}</t-descriptions-item>
            <t-descriptions-item label="状态">
              <t-tag :theme="statusTheme(detailMaterial.status)" variant="light">{{ statusLabel(detailMaterial.status) }}</t-tag>
            </t-descriptions-item>
            <t-descriptions-item label="质量分">
              <div v-if="detailMaterial.quality_score != null" style="display: flex; align-items: center; gap: 8px; width: 160px">
                <div style="flex: 1; height: 6px; background: var(--td-bg-color-component); border-radius: 3px; overflow: hidden">
                  <div :style="{ width: (detailMaterial.quality_score * 100) + '%', height: '100%', background: qualityBarColor(detailMaterial.quality_score), borderRadius: '3px' }" />
                </div>
                <span style="font-size: 12px">{{ detailMaterial.quality_score.toFixed(2) }}</span>
              </div>
              <span v-else>-</span>
            </t-descriptions-item>
            <t-descriptions-item label="重复">{{ detailMaterial.is_duplicate ? '是' : '否' }}</t-descriptions-item>
            <t-descriptions-item label="原始链接">
              <a v-if="detailMaterial.original_url" :href="detailMaterial.original_url" target="_blank">{{ detailMaterial.original_url }}</a>
              <span v-else>-</span>
            </t-descriptions-item>
            <t-descriptions-item label="采集时间">{{ formatDate(detailMaterial.created_at) }}</t-descriptions-item>
          </t-descriptions>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">标签</div>
            <t-space size="4px" v-if="detailMaterial.tags && detailMaterial.tags.length">
              <t-tag v-for="tag in detailMaterial.tags" :key="tag" size="small" closable @close="removeDetailTag(tag)">{{ tag }}</t-tag>
            </t-space>
            <span v-else style="color: var(--td-text-color-placeholder)">无标签</span>
            <div style="margin-top: 8px; display: flex; gap: 8px">
              <t-input v-model="newTagInput" placeholder="添加标签" size="small" style="width: 150px" @enter="addDetailTag" />
              <t-button size="small" @click="addDetailTag">添加</t-button>
            </div>
          </div>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">摘要</div>
            <div style="color: var(--td-text-color-secondary); line-height: 1.6">{{ detailMaterial.summary || '无摘要' }}</div>
          </div>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">完整内容</div>
            <t-card :bordered="true" style="max-height: 300px; overflow-y: auto">
              <pre style="white-space: pre-wrap; font-size: 13px; margin: 0">{{ detailMaterial.raw_content || '无内容' }}</pre>
            </t-card>
          </div>
          <div v-if="detailMaterial.metadata" style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">元数据</div>
            <t-card :bordered="true">
              <pre style="white-space: pre-wrap; font-size: 12px; margin: 0">{{ JSON.stringify(detailMaterial.metadata, null, 2) }}</pre>
            </t-card>
          </div>
        </template>
        <template v-else>
          <t-descriptions :column="1" bordered>
            <t-descriptions-item label="ID">{{ detailMaterial.id }}</t-descriptions-item>
            <t-descriptions-item label="文件名">{{ detailMaterial.filename }}</t-descriptions-item>
            <t-descriptions-item label="素材来源">
              <t-tag :theme="mediaSourceKindTheme(detailMaterial.source_kind)" variant="light" size="small">
                {{ mediaSourceKindLabel(detailMaterial.source_kind) }}
              </t-tag>
            </t-descriptions-item>
            <t-descriptions-item label="文章 ID">{{ detailMaterial.article_id ?? '-' }}</t-descriptions-item>
            <t-descriptions-item label="Content-Type">{{ detailMaterial.content_type }}</t-descriptions-item>
            <t-descriptions-item label="文件大小">{{ formatFileSize(detailMaterial.file_size) }}</t-descriptions-item>
            <t-descriptions-item label="所有者">{{ detailMaterial.owner_email || '-' }}</t-descriptions-item>
            <t-descriptions-item label="原始来源">{{ detailMaterial.source_url || '-' }}</t-descriptions-item>
            <t-descriptions-item label="创建时间">{{ formatDate(detailMaterial.created_at) }}</t-descriptions-item>
          </t-descriptions>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">图片预览</div>
            <t-card :bordered="true" style="text-align: center">
              <img :src="detailMaterial.url" :alt="detailMaterial.filename" style="max-width: 100%; max-height: 360px" />
            </t-card>
          </div>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">公众号上传状态</div>
            <t-card :bordered="true">
              <t-space size="8px" direction="vertical" style="width: 100%">
                <div
                  v-for="mapping in detailMaterial.wechat_mappings || []"
                  :key="mapping.id"
                  style="display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap"
                >
                  <div>
                    <div style="font-weight: 500">{{ accountNameById(mapping.account_id) }}</div>
                    <div style="font-size: 12px; color: var(--td-text-color-secondary)">
                      公众号 ID: {{ mapping.account_id }}
                    </div>
                    <div v-if="mapping.error_message" style="font-size: 12px; color: var(--td-error-color)">
                      {{ mapping.error_message }}
                    </div>
                  </div>
                  <t-tag :theme="uploadStatusTheme(mapping.upload_status)" variant="light">
                    {{ uploadStatusLabel(mapping.upload_status) }}
                  </t-tag>
                </div>
                <span v-if="!detailMaterial.wechat_mappings || detailMaterial.wechat_mappings.length === 0" style="color: var(--td-text-color-placeholder)">
                  暂无公众号上传记录
                </span>
              </t-space>
            </t-card>
          </div>
          <div style="margin-top: 16px">
            <div style="font-weight: 600; margin-bottom: 8px">标签</div>
            <t-space size="4px" v-if="detailMaterial.tags && detailMaterial.tags.length">
              <t-tag v-for="tag in detailMaterial.tags" :key="tag" size="small" variant="outline">{{ tag }}</t-tag>
            </t-space>
            <span v-else style="color: var(--td-text-color-placeholder)">无标签</span>
          </div>
        </template>
      </template>
    </t-drawer>

    <!-- Delete confirm dialog -->
    <t-dialog v-model:visible="showDeleteConfirm" header="确认删除" :footer="false" width="400px">
      <div style="padding: 8px 0">
        <div style="margin-bottom: 16px">
          确定要删除素材 <strong>{{ deletingMedia?.filename || deletingMedia?.title }}</strong> 吗？此操作不可恢复。
        </div>
        <t-space>
          <t-button theme="danger" :loading="deleting" @click="onDeleteMedia">删除</t-button>
          <t-button variant="outline" @click="showDeleteConfirm = false">取消</t-button>
        </t-space>
      </div>
    </t-dialog>

    <!-- Tag editor dialog -->
    <t-dialog v-model:visible="showTagEditor" header="管理标签" :footer="false" width="500px">
      <template v-if="tagEditMaterial">
        <div style="margin-bottom: 12px">
          <div style="font-weight: 600; margin-bottom: 8px">当前标签</div>
          <t-space size="4px" v-if="tagEditMaterial.tags && tagEditMaterial.tags.length">
            <t-tag v-for="tag in tagEditMaterial.tags" :key="tag" closable @close="removeTag(tag)">{{ tag }}</t-tag>
          </t-space>
          <span v-else style="color: var(--td-text-color-placeholder)">无标签</span>
        </div>
        <div style="display: flex; gap: 8px">
          <t-input v-model="tagEditorInput" placeholder="输入新标签" @enter="addTag" />
          <t-button theme="primary" @click="addTag">添加</t-button>
        </div>
      </template>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import {
  getAccounts,
  getAgents,
  getMaterial,
  getMaterials,
  getMedia,
  getMediaDetail,
  updateMaterialTags,
  uploadMaterial,
  uploadMedia,
  uploadMarkdown,
  deleteMedia,
  collectForAgent,
} from '@/api';
import { MessagePlugin } from 'tdesign-vue-next';

const loading = ref(false);
const materials = ref<any[]>([]);
const agents = ref<any[]>([]);
const accounts = ref<any[]>([]);
const total = ref(0);
const libraryMode = ref<'trending' | 'candidate' | 'media'>('trending');
const detailMode = ref<'candidate' | 'media'>('candidate');

// Trending-specific filters
const trendingPlatformFilter = ref<string[]>([]);
const trendingQualityFilter = ref<string | undefined>(undefined);
const collecting = ref(false);

const filters = reactive({
  agent_id: undefined as number | undefined,
  source_type: undefined as string | undefined,
  media_source_kind: undefined as string | undefined,
  media_account_id: undefined as number | undefined,
  media_upload_status: undefined as string | undefined,
  status: undefined as string | undefined,
  tags: '',
  page: 1,
  page_size: 20,
});

const pagination = computed(() => ({
  current: filters.page,
  pageSize: filters.page_size,
  total: total.value,
  showJumper: true,
  showSizeChanger: true,
  pageSizeOptions: [10, 20, 50],
}));

// Empty state text
const emptyTitle = computed(() => {
  const map: Record<string, string> = {
    trending: '热点素材库为空',
    candidate: '内容素材库为空',
    media: '图片素材库为空',
  };
  return map[libraryMode.value];
});

const emptyDesc = computed(() => {
  const map: Record<string, string> = {
    trending: '可以选择 Agent 后点击「一键采集」获取热点素材',
    candidate: '可以通过 Agent 自动采集或手动上传来获取素材',
    media: '可以手动上传图片，或通过文章自动入库',
  };
  return map[libraryMode.value];
});

// Extract available platforms from trending materials' tags
const availablePlatforms = computed(() => {
  const platforms = new Set<string>();
  materials.value.forEach((item: any) => {
    if (item.tags) {
      item.tags.forEach((tag: string) => {
        if (tag.startsWith('platform:')) {
          platforms.add(tag.replace('platform:', ''));
        }
      });
    }
    // Also extract from metadata
    if (item.metadata?.platform) {
      platforms.add(item.metadata.platform);
    }
  });
  return Array.from(platforms).sort();
});

// Frontend filtering for trending materials (platform + quality)
const filteredTrendingMaterials = computed(() => {
  let items = materials.value;

  // Platform filter
  if (trendingPlatformFilter.value && trendingPlatformFilter.value.length > 0) {
    items = items.filter((item: any) => {
      const itemPlatforms = new Set<string>();
      if (item.tags) {
        item.tags.forEach((tag: string) => {
          if (tag.startsWith('platform:')) {
            itemPlatforms.add(tag.replace('platform:', ''));
          }
        });
      }
      if (item.metadata?.platform) {
        itemPlatforms.add(item.metadata.platform);
      }
      return trendingPlatformFilter.value.some((p: string) => itemPlatforms.has(p));
    });
  }

  // Quality filter
  if (trendingQualityFilter.value) {
    const threshold = parseFloat(trendingQualityFilter.value);
    items = items.filter((item: any) => item.quality_score != null && item.quality_score >= threshold);
  }

  return items;
});

const candidateColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'source_type', title: '来源', width: 100 },
  { colKey: 'title', title: '标题', ellipsis: true },
  { colKey: 'tags', title: '标签', width: 200 },
  { colKey: 'quality_score', title: '质量分', width: 120 },
  { colKey: 'status', title: '状态', width: 80 },
  { colKey: 'created_at', title: '采集时间', width: 160 },
  { colKey: 'op', title: '操作', width: 120 },
];

const mediaColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'source_kind', title: '来源', width: 120 },
  { colKey: 'filename', title: '文件', ellipsis: true },
  { colKey: 'article_id', title: '文章 ID', width: 90 },
  { colKey: 'latest_upload_status', title: '上传状态', width: 110 },
  { colKey: 'wechat_mapping_summary', title: '公众号状态', width: 260 },
  { colKey: 'tags', title: '标签', width: 180 },
  { colKey: 'created_at', title: '创建时间', width: 180 },
  { colKey: 'op', title: '操作', width: 120 },
];

const columns = computed(() => {
  return libraryMode.value === 'candidate' ? candidateColumns : mediaColumns;
});

const showUploadDialog = ref(false);
const uploading = ref(false);
const uploadForm = reactive({ title: '', content: '', original_url: '', tagsInput: '' });

const showMediaUploadDialog = ref(false);
const mediaUploading = ref(false);
const mediaUploadForm = reactive({ fileList: [] as any[], tagsInput: '', description: '' });

const showMarkdownUploadDialog = ref(false);
const markdownUploading = ref(false);
const markdownUploadForm = reactive({ content: '', tagsInput: '' });
const markdownUploadResult = ref<any>(null);
const markdownFileRef = ref();

const showDeleteConfirm = ref(false);
const deletingMedia = ref<any>(null);
const deleting = ref(false);

const showDetail = ref(false);
const detailMaterial = ref<any>(null);
const newTagInput = ref('');
const detailTitle = computed(() => {
  if (!detailMaterial.value) {
    return '素材详情';
  }
  return detailMode.value === 'candidate'
    ? detailMaterial.value.title || '素材详情'
    : detailMaterial.value.filename || '图片素材详情';
});

const showTagEditor = ref(false);
const tagEditMaterial = ref<any>(null);
const tagEditorInput = ref('');

// ── Label / Theme helpers ──

const sourceTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    rss: 'RSS',
    search: '搜索',
    skills_feed: 'Skills',
    manual: '手动',
    trending: '🔥 热点',
  };
  return map[type] || type;
};

const sourceTypeTheme = (type: string): string => {
  const map: Record<string, string> = {
    rss: 'primary',
    search: 'warning',
    skills_feed: 'success',
    manual: 'default',
    trending: 'danger',
  };
  return map[type] || 'default';
};

const mediaSourceKindLabel = (type: string) => {
  const map: Record<string, string> = { manual: '手动上传', article_body: '正文图片', article_cover: '封面图片' };
  return map[type] || type;
};

const mediaSourceKindTheme = (type: string): string => {
  const map: Record<string, string> = { manual: 'primary', article_body: 'success', article_cover: 'warning' };
  return map[type] || 'default';
};

const statusLabel = (status: string) => {
  const map: Record<string, string> = { pending: '待处理', accepted: '已采纳', rejected: '已拒绝' };
  return map[status] || status;
};

const statusTheme = (status: string): string => {
  const map: Record<string, string> = { pending: 'warning', accepted: 'success', rejected: 'danger' };
  return map[status] || 'default';
};

const uploadStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待上传',
    processing: '上传中',
    success: '已上传',
    failed: '上传失败',
  };
  return map[status] || status || '-';
};

const uploadStatusTheme = (status: string): string => {
  const map: Record<string, string> = {
    pending: 'warning',
    processing: 'primary',
    success: 'success',
    failed: 'danger',
  };
  return map[status] || 'default';
};

const accountNameById = (accountId?: number) => {
  if (!accountId) {
    return '未知公众号';
  }
  return accounts.value.find((item) => item.id === accountId)?.name || `公众号 ${accountId}`;
};

// ── Quality color helpers ──

const qualityBarColor = (score: number | null): string => {
  if (score == null) return 'var(--td-gray-color-5)';
  if (score >= 0.5) return 'var(--td-error-color)';
  if (score >= 0.35) return 'var(--td-warning-color)';
  return 'var(--td-gray-color-5)';
};

const qualityBorderColor = (score: number | null): string => {
  if (score == null) return 'var(--td-gray-color-5)';
  if (score >= 0.5) return 'var(--td-error-color)';
  if (score >= 0.35) return 'var(--td-warning-color)';
  return 'var(--td-gray-color-5)';
};

// ── Trending metadata extractors ──

const extractPlatform = (item: any): string => {
  // Try metadata first
  if (item.metadata?.platform) return item.metadata.platform;
  if (item.metadata?.source_name) return item.metadata.source_name;
  // Fallback: extract from tags
  if (item.tags) {
    const platformTag = item.tags.find((t: string) => t.startsWith('platform:'));
    if (platformTag) return platformTag.replace('platform:', '');
  }
  return '';
};

const extractRank = (item: any): number | null => {
  if (item.metadata?.rank != null) return item.metadata.rank;
  if (item.metadata?.position != null) return item.metadata.position;
  return null;
};

const extractHotValue = (item: any): string => {
  if (item.metadata?.hot_value != null) {
    const val = item.metadata.hot_value;
    if (typeof val === 'number') {
      return val >= 10000 ? (val / 10000).toFixed(1) + '万' : String(val);
    }
    return String(val);
  }
  if (item.metadata?.heat != null) return String(item.metadata.heat);
  return '';
};

const extractCrossPlatformCount = (item: any): number | null => {
  if (item.metadata?.cross_platform_count != null) return item.metadata.cross_platform_count;
  if (item.metadata?.platform_count != null) return item.metadata.platform_count;
  // Infer from platforms array
  if (item.metadata?.platforms && Array.isArray(item.metadata.platforms)) {
    return item.metadata.platforms.length;
  }
  return null;
};

const extractAllPlatforms = (item: any): string => {
  if (item.metadata?.platforms && Array.isArray(item.metadata.platforms)) {
    return item.metadata.platforms.join(', ');
  }
  // Fallback: collect all platform: tags
  if (item.tags) {
    const platforms = item.tags
      .filter((t: string) => t.startsWith('platform:'))
      .map((t: string) => t.replace('platform:', ''));
    if (platforms.length) return platforms.join(', ');
  }
  const p = extractPlatform(item);
  return p || '';
};

const extractWeightScore = (item: any): string => {
  if (item.metadata?.weight_score != null) return Number(item.metadata.weight_score).toFixed(2);
  if (item.metadata?.weight != null) return Number(item.metadata.weight).toFixed(2);
  return '';
};

const extractCrossPlatformInfo = (item: any): { sources: string; count: number } | null => {
  const count = extractCrossPlatformCount(item);
  if (count && count > 1) {
    return {
      sources: extractAllPlatforms(item),
      count,
    };
  }
  return null;
};

const displayTags = (tags: string[]): string[] => {
  return tags.slice(0, 3);
};

// ── Format helpers ──

const formatDate = (dateStr: string) => {
  if (!dateStr) {
    return '-';
  }
  return new Date(dateStr).toLocaleString('zh-CN');
};

const formatFileSize = (size: number) => {
  if (!size) {
    return '0 B';
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

// ── Data fetching ──

const fetchData = async () => {
  loading.value = true;
  try {
    if (libraryMode.value === 'trending') {
      const params: Record<string, any> = {
        page: filters.page,
        page_size: filters.page_size,
        source_type: 'trending',
      };
      if (filters.agent_id) {
        params.agent_id = filters.agent_id;
      }
      if (filters.tags) {
        params.tags = filters.tags;
      }
      const res = await getMaterials(params);
      materials.value = res.data.items;
      total.value = res.data.total;
    } else if (libraryMode.value === 'candidate') {
      const params: Record<string, any> = { page: filters.page, page_size: filters.page_size };
      if (filters.agent_id) {
        params.agent_id = filters.agent_id;
      }
      if (filters.source_type) {
        params.source_type = filters.source_type;
      }
      if (filters.status) {
        params.status = filters.status;
      }
      if (filters.tags) {
        params.tags = filters.tags;
      }
      const res = await getMaterials(params);
      materials.value = res.data.items;
      total.value = res.data.total;
    } else {
      const params: Record<string, any> = { page: filters.page, page_size: filters.page_size };
      if (filters.tags) {
        params.tag = filters.tags;
      }
      if (filters.media_source_kind) {
        params.source_kind = filters.media_source_kind;
      }
      if (filters.media_account_id) {
        params.account_id = filters.media_account_id;
      }
      if (filters.media_upload_status) {
        params.upload_status = filters.media_upload_status;
      }
      const res = await getMedia(params);
      materials.value = res.data.items;
      total.value = res.data.total;
    }
  } catch {
    const labels: Record<string, string> = {
      trending: '加载热点素材失败',
      candidate: '加载素材失败',
      media: '加载图片素材失败',
    };
    MessagePlugin.error(labels[libraryMode.value]);
  } finally {
    loading.value = false;
  }
};

const onTabChange = (val: string | number) => {
  libraryMode.value = val as 'trending' | 'candidate' | 'media';
  showUploadDialog.value = false;
  showMediaUploadDialog.value = false;
  showTagEditor.value = false;
  showDetail.value = false;
  resetFilters();
};

const resetFilters = () => {
  filters.agent_id = undefined;
  filters.source_type = undefined;
  filters.media_source_kind = undefined;
  filters.media_account_id = undefined;
  filters.media_upload_status = undefined;
  filters.status = undefined;
  filters.tags = '';
  filters.page = 1;
  trendingPlatformFilter.value = [];
  trendingQualityFilter.value = undefined;
  if (libraryMode.value === 'trending') {
    filters.page_size = 24;
  } else {
    filters.page_size = 20;
  }
  fetchData();
};

const onPageChange = (pageInfo: { current: number; pageSize: number }) => {
  filters.page = pageInfo.current;
  filters.page_size = pageInfo.pageSize;
  fetchData();
};

// ── Collect ──

const onCollect = async () => {
  if (!filters.agent_id) {
    MessagePlugin.warning('请先选择 Agent');
    return;
  }
  collecting.value = true;
  try {
    const res = await collectForAgent(filters.agent_id);
    const count = res.data?.total_collected ?? res.data?.count ?? 0;
    MessagePlugin.success(`采集完成，新增 ${count} 条素材`);
    fetchData();
  } catch {
    MessagePlugin.error('采集失败，请稍后重试');
  } finally {
    collecting.value = false;
  }
};

// ── Upload handlers ──

const onUpload = async () => {
  if (!uploadForm.title.trim()) {
    MessagePlugin.warning('请输入标题');
    return;
  }
  uploading.value = true;
  try {
    const tags = uploadForm.tagsInput
      ? uploadForm.tagsInput.split(',').map((t) => t.trim()).filter(Boolean)
      : [];
    await uploadMaterial({
      title: uploadForm.title,
      content: uploadForm.content,
      original_url: uploadForm.original_url,
      tags,
    });
    MessagePlugin.success('上传成功');
    showUploadDialog.value = false;
    uploadForm.title = '';
    uploadForm.content = '';
    uploadForm.original_url = '';
    uploadForm.tagsInput = '';
    fetchData();
  } catch {
    MessagePlugin.error('上传失败');
  } finally {
    uploading.value = false;
  }
};

const onMediaUpload = async () => {
  if (!mediaUploadForm.fileList.length) {
    MessagePlugin.warning('请选择图片文件');
    return;
  }
  const fileItem = mediaUploadForm.fileList[0];
  const file = fileItem.raw || fileItem;
  if (!file) {
    MessagePlugin.warning('请选择图片文件');
    return;
  }
  mediaUploading.value = true;
  try {
    const tags = mediaUploadForm.tagsInput
      ? mediaUploadForm.tagsInput.split(',').map((t: string) => t.trim()).filter(Boolean).join(',')
      : '';
    await uploadMedia(file, tags, mediaUploadForm.description);
    MessagePlugin.success('图片上传成功');
    showMediaUploadDialog.value = false;
    mediaUploadForm.fileList = [];
    mediaUploadForm.tagsInput = '';
    mediaUploadForm.description = '';
    fetchData();
  } catch {
    MessagePlugin.error('图片上传失败');
  } finally {
    mediaUploading.value = false;
  }
};

const onMediaUploadFail = ({ file }: any) => {
  MessagePlugin.warning(`文件 ${file.name} 超过 20MB 大小限制`);
};

const onMarkdownFileChange = (files: any[]) => {
  const file = files?.[0]?.raw || files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    markdownUploadForm.content = e.target?.result as string || '';
  };
  reader.readAsText(file);
};

const onMarkdownUpload = async () => {
  if (!markdownUploadForm.content.trim()) {
    MessagePlugin.warning('请输入 Markdown 内容');
    return;
  }
  markdownUploading.value = true;
  try {
    const tags = markdownUploadForm.tagsInput
      ? markdownUploadForm.tagsInput.split(',').map((t: string) => t.trim()).filter(Boolean)
      : [];
    const res = await uploadMarkdown(markdownUploadForm.content, tags);
    markdownUploadResult.value = res.data;
    MessagePlugin.success('Markdown 处理完成，图片已上传到素材库');
    fetchData();
  } catch {
    MessagePlugin.error('Markdown 处理失败');
  } finally {
    markdownUploading.value = false;
  }
};

const copyProcessedMarkdown = () => {
  if (!markdownUploadResult.value?.content) return;
  navigator.clipboard.writeText(markdownUploadResult.value.content).then(() => {
    MessagePlugin.success('已复制到剪贴板');
  }).catch(() => {
    MessagePlugin.error('复制失败');
  });
};

// ── Delete media ──

const confirmDeleteMedia = (row: any) => {
  deletingMedia.value = row;
  showDeleteConfirm.value = true;
};

const onDeleteMedia = async () => {
  if (!deletingMedia.value) return;
  deleting.value = true;
  try {
    await deleteMedia(deletingMedia.value.id);
    MessagePlugin.success('素材已删除');
    showDeleteConfirm.value = false;
    deletingMedia.value = null;
    fetchData();
  } catch {
    MessagePlugin.error('删除失败');
  } finally {
    deleting.value = false;
  }
};

// ── Detail drawer ──

const openDetail = async (row: any) => {
  if (libraryMode.value === 'media') {
    detailMode.value = 'media';
    try {
      const res = await getMediaDetail(row.id);
      detailMaterial.value = res.data;
      showDetail.value = true;
    } catch {
      detailMaterial.value = row;
      showDetail.value = true;
    }
    return;
  }

  try {
    const res = await getMaterial(row.id);
    detailMode.value = 'candidate';
    detailMaterial.value = res.data;
    showDetail.value = true;
  } catch {
    MessagePlugin.error('加载详情失败');
  }
};

// ── Tag management ──

const addDetailTag = async () => {
  const tag = newTagInput.value.trim();
  if (!tag || !detailMaterial.value || detailMode.value !== 'candidate') {
    return;
  }
  try {
    const res = await updateMaterialTags(detailMaterial.value.id, { add_tags: [tag] });
    detailMaterial.value = res.data;
    newTagInput.value = '';
    fetchData();
  } catch {
    MessagePlugin.error('添加标签失败');
  }
};

const removeDetailTag = async (tag: string) => {
  if (!detailMaterial.value || detailMode.value !== 'candidate') {
    return;
  }
  try {
    const res = await updateMaterialTags(detailMaterial.value.id, { remove_tags: [tag] });
    detailMaterial.value = res.data;
    fetchData();
  } catch {
    MessagePlugin.error('移除标签失败');
  }
};

const openTagEditor = (row: any) => {
  if (libraryMode.value !== 'candidate') {
    return;
  }
  tagEditMaterial.value = { ...row };
  tagEditorInput.value = '';
  showTagEditor.value = true;
};

const addTag = async () => {
  const tag = tagEditorInput.value.trim();
  if (!tag || !tagEditMaterial.value) {
    return;
  }
  try {
    const res = await updateMaterialTags(tagEditMaterial.value.id, { add_tags: [tag] });
    tagEditMaterial.value = res.data;
    tagEditorInput.value = '';
    fetchData();
  } catch {
    MessagePlugin.error('添加标签失败');
  }
};

const removeTag = async (tag: string) => {
  if (!tagEditMaterial.value) {
    return;
  }
  try {
    const res = await updateMaterialTags(tagEditMaterial.value.id, { remove_tags: [tag] });
    tagEditMaterial.value = res.data;
    fetchData();
  } catch {
    MessagePlugin.error('移除标签失败');
  }
};

// ── Init ──

onMounted(async () => {
  try {
    const [agentsResponse, accountsResponse] = await Promise.all([
      getAgents(),
      getAccounts(),
    ]);
    agents.value = agentsResponse.data;
    accounts.value = accountsResponse.data;
  } catch {
    try {
      const r = await getAgents();
      agents.value = r.data;
    } catch {}
  }
  filters.page_size = 24; // Default for trending grid
  fetchData();
});
</script>

<style scoped>
.trending-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  transition: opacity 0.2s;
}

.trending-card {
  background: var(--td-bg-color-container);
  border: 1px solid var(--td-border-level-1-color);
  border-left: 4px solid var(--td-gray-color-5);
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.15s;
}

.trending-card:hover {
  box-shadow: var(--td-shadow-2);
  transform: translateY(-2px);
}
</style>
