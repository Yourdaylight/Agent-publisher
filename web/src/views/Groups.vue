<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
      <div>
        <h3 style="margin: 0 0 4px 0">权限组管理</h3>
        <p style="margin: 0; color: var(--td-text-color-secondary); font-size: 13px">
          同一权限组的成员可以查看彼此发布的文章
        </p>
      </div>
      <t-button theme="primary" @click="openCreateDialog">新建权限组</t-button>
    </div>

    <t-loading :loading="loading">
      <t-card
        v-for="group in groups"
        :key="group.id"
        style="margin-bottom: 16px"
        :bordered="true"
        hover-shadow
      >
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <div>
              <span style="font-weight: 600; font-size: 15px">{{ group.name }}</span>
              <t-tag v-if="group.description" size="small" style="margin-left: 8px" variant="light">
                {{ group.description }}
              </t-tag>
            </div>
            <div style="display: flex; gap: 8px">
              <t-button size="small" variant="outline" @click="openAddMember(group)">添加成员</t-button>
              <t-button size="small" theme="danger" variant="outline" @click="confirmDeleteGroup(group)">删除组</t-button>
            </div>
          </div>
        </template>

        <div v-if="group.members.length === 0" style="color: var(--td-text-color-placeholder); font-size: 13px">
          暂无成员
        </div>
        <div v-else style="display: flex; flex-wrap: wrap; gap: 8px">
          <t-tag
            v-for="member in group.members"
            :key="member.email"
            closable
            @close="confirmRemoveMember(group, member.email)"
          >
            {{ member.email }}
          </t-tag>
        </div>
      </t-card>

      <t-empty v-if="!loading && groups.length === 0" description="暂无权限组，点击右上角创建" />
    </t-loading>

    <!-- Create Group Dialog -->
    <t-dialog
      v-model:visible="createDialog"
      header="新建权限组"
      :confirm-btn="{ content: '创建', loading: saving }"
      @confirm="submitCreate"
      @close="resetCreateForm"
    >
      <t-form :data="createForm" label-align="right" :label-width="80">
        <t-form-item label="组名称" name="name">
          <t-input v-model="createForm.name" placeholder="请输入权限组名称" style="width: 300px" />
        </t-form-item>
        <t-form-item label="描述" name="description">
          <t-input v-model="createForm.description" placeholder="可选描述" style="width: 300px" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Add Member Dialog -->
    <t-dialog
      v-model:visible="addMemberDialog"
      header="添加成员"
      :confirm-btn="{ content: '添加', loading: saving }"
      @confirm="submitAddMember"
      @close="resetMemberForm"
    >
      <p style="color: var(--td-text-color-secondary); font-size: 13px; margin-bottom: 12px">
        向「{{ currentGroup?.name }}」添加成员（成员需在系统邮箱白名单中）
      </p>
      <t-form label-align="right" :label-width="80">
        <t-form-item label="邮箱">
          <t-input v-model="memberEmail" placeholder="user@example.com" style="width: 300px" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next';
import {
  getGroups,
  createGroup,
  deleteGroup,
  addGroupMember,
  removeGroupMember,
} from '@/api';

interface GroupMember {
  id: number;
  group_id: number;
  email: string;
  added_at: string;
}

interface Group {
  id: number;
  name: string;
  description: string;
  created_by: string;
  created_at: string;
  members: GroupMember[];
}

const loading = ref(false);
const saving = ref(false);
const groups = ref<Group[]>([]);

const createDialog = ref(false);
const addMemberDialog = ref(false);
const currentGroup = ref<Group | null>(null);
const memberEmail = ref('');

const createForm = reactive({ name: '', description: '' });

const fetchGroups = async () => {
  loading.value = true;
  try {
    const res = await getGroups();
    groups.value = res.data;
  } catch {
    MessagePlugin.error('加载权限组失败');
  } finally {
    loading.value = false;
  }
};

const openCreateDialog = () => {
  createDialog.value = true;
};

const resetCreateForm = () => {
  createForm.name = '';
  createForm.description = '';
};

const submitCreate = async () => {
  if (!createForm.name.trim()) {
    MessagePlugin.warning('请输入权限组名称');
    return;
  }
  saving.value = true;
  try {
    await createGroup({ name: createForm.name.trim(), description: createForm.description });
    MessagePlugin.success('权限组已创建');
    createDialog.value = false;
    resetCreateForm();
    fetchGroups();
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '创建失败';
    MessagePlugin.error(detail);
  } finally {
    saving.value = false;
  }
};

const confirmDeleteGroup = (group: Group) => {
  const confirmDia = DialogPlugin.confirm({
    header: '删除权限组',
    body: `确定删除权限组「${group.name}」？此操作将同时移除所有成员关系，不可恢复。`,
    theme: 'danger',
    confirmBtn: '删除',
    onConfirm: async () => {
      try {
        await deleteGroup(group.id);
        MessagePlugin.success('权限组已删除');
        fetchGroups();
      } catch {
        MessagePlugin.error('删除失败');
      }
      confirmDia.destroy();
    },
    onClose: () => confirmDia.destroy(),
  });
};

const openAddMember = (group: Group) => {
  currentGroup.value = group;
  memberEmail.value = '';
  addMemberDialog.value = true;
};

const resetMemberForm = () => {
  memberEmail.value = '';
  currentGroup.value = null;
};

const submitAddMember = async () => {
  if (!memberEmail.value.trim()) {
    MessagePlugin.warning('请输入邮箱地址');
    return;
  }
  if (!currentGroup.value) return;
  saving.value = true;
  try {
    await addGroupMember(currentGroup.value.id, { email: memberEmail.value.trim() });
    MessagePlugin.success('成员已添加');
    addMemberDialog.value = false;
    resetMemberForm();
    fetchGroups();
  } catch (err: any) {
    const detail = err?.response?.data?.detail || '添加失败';
    MessagePlugin.error(detail);
  } finally {
    saving.value = false;
  }
};

const confirmRemoveMember = (group: Group, email: string) => {
  const confirmDia = DialogPlugin.confirm({
    header: '移除成员',
    body: `确定将「${email}」从「${group.name}」中移除？`,
    theme: 'warning',
    confirmBtn: '移除',
    onConfirm: async () => {
      try {
        await removeGroupMember(group.id, email);
        MessagePlugin.success('成员已移除');
        fetchGroups();
      } catch {
        MessagePlugin.error('移除失败');
      }
      confirmDia.destroy();
    },
    onClose: () => confirmDia.destroy(),
  });
};

onMounted(fetchGroups);
</script>
