<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 16px">
      <h3 style="margin: 0">公众号列表</h3>
      <t-button theme="primary" @click="openDialog()">添加公众号</t-button>
    </div>

    <t-table :data="accounts" :columns="columns" row-key="id" :loading="loading" stripe>
      <template #op="{ row }">
        <t-space>
          <t-link theme="primary" @click="openDialog(row)">编辑</t-link>
          <t-popconfirm content="确定删除该公众号？" @confirm="onDelete(row.id)">
            <t-link theme="danger">删除</t-link>
          </t-popconfirm>
        </t-space>
      </template>
    </t-table>

    <t-dialog
      v-model:visible="dialogVisible"
      :header="editingAccount ? '编辑公众号' : '添加公众号'"
      :footer="false"
      width="560px"
    >
      <AccountForm
        :edit-id="editingAccount?.id"
        :initial-data="editingAccount"
        @success="onFormSuccess"
      />
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAccounts, deleteAccount } from '@/api'
import AccountForm from '@/components/AccountForm.vue'
import { MessagePlugin } from 'tdesign-vue-next'

const loading = ref(false)
const accounts = ref<any[]>([])
const dialogVisible = ref(false)
const editingAccount = ref<any>(null)

const columns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'name', title: '名称' },
  { colKey: 'appid', title: 'AppID' },
  { colKey: 'ip_whitelist', title: 'IP 白名单', ellipsis: true },
  { colKey: 'created_at', title: '创建时间', width: 180, cell: (_h: any, { row }: any) => new Date(row.created_at).toLocaleString() },
  { colKey: 'op', title: '操作', width: 140 },
]

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getAccounts()
    accounts.value = res.data
  } catch {} finally {
    loading.value = false
  }
}

const openDialog = (account?: any) => {
  editingAccount.value = account || null
  dialogVisible.value = true
}

const onFormSuccess = () => {
  dialogVisible.value = false
  MessagePlugin.success('操作成功')
  fetchData()
}

const onDelete = async (id: number) => {
  try {
    await deleteAccount(id)
    MessagePlugin.success('删除成功')
    fetchData()
  } catch {
    MessagePlugin.error('删除失败')
  }
}

onMounted(fetchData)
</script>
