<template>
  <div class="page-card table-section">
    <div class="page-toolbar">
      <div>
        <h2 class="page-title">用户管理</h2>
        <p class="page-subtitle">管理员可新增用户、修改用户角色，并分配可用线路。</p>
      </div>
      <div class="page-toolbar-right">
        <el-button type="primary" plain @click="loadUserData">刷新</el-button>
        <el-button type="primary" @click="openUserDialog('create')">新增用户</el-button>
      </div>
    </div>

    <el-table :data="users" border>
      <el-table-column prop="username" label="用户名" min-width="140" />
      <el-table-column prop="display_name" label="显示名称" min-width="160" />
      <el-table-column prop="mobile" label="手机号" min-width="140" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column label="角色" min-width="180">
        <template #default="{ row }">
          {{ (row.role_codes || []).join(' / ') }}
        </template>
      </el-table-column>
      <el-table-column label="已分配线路" min-width="220">
        <template #default="{ row }">
          {{ (assignedTrunksMap[row.id] || []).map((item) => item.trunk_name).join('、') || '--' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button link type="primary" @click="openUserDialog('edit', row)">编辑</el-button>
          <el-button link type="success" @click="openAssignDialog(row)">分配线路</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="userDialogVisible" :title="userDialogMode === 'create' ? '新增用户' : '编辑用户'" width="720px">
      <el-form :model="userForm" label-width="110px">
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" :disabled="userDialogMode === 'edit'" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="userForm.display_name" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="userForm.mobile" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="userForm.status">
            <el-option label="active" value="active" />
            <el-option label="disabled" value="disabled" />
            <el-option label="locked" value="locked" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role_codes" multiple>
            <el-option label="普通用户" value="agent_user" />
            <el-option label="企业管理员" value="enterprise_admin" />
            <el-option label="运营管理员" value="ops_admin" />
            <el-option label="质检员" value="qc_admin" />
            <el-option label="查看员" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item :label="userDialogMode === 'create' ? '登录密码' : '新密码'">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingUser" @click="submitUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="assignDialogVisible" title="分配线路" width="700px">
      <el-form label-width="110px">
        <el-form-item label="目标用户">
          <el-input :model-value="assigningUser?.display_name || assigningUser?.username || ''" disabled />
        </el-form-item>
        <el-form-item label="可用线路">
          <el-select v-model="selectedTrunkIds" multiple style="width: 100%">
            <el-option v-for="trunk in allTrunks" :key="trunk.id" :label="trunk.trunk_name" :value="trunk.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingAssign" @click="submitAssignments">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  createUserApi,
  fetchTrunksApi,
  fetchUsersApi,
  fetchUserTrunksApi,
  replaceUserTrunksApi,
  updateUserApi,
} from '@/api/modules'

const users = ref([])
const allTrunks = ref([])
const assignedTrunksMap = ref({})
const userDialogVisible = ref(false)
const userDialogMode = ref('create')
const editingUserId = ref(null)
const submittingUser = ref(false)
const assignDialogVisible = ref(false)
const assigningUser = ref(null)
const selectedTrunkIds = ref([])
const submittingAssign = ref(false)
const userForm = reactive(createDefaultUserForm())

/**
 * 创建用户表单默认值对象。
 *
 * @returns {object} 用户表单默认值。
 */
function createDefaultUserForm() {
  return {
    username: '',
    display_name: '',
    mobile: '',
    email: '',
    status: 'active',
    role_codes: ['agent_user'],
    password: '',
  }
}

/**
 * 加载用户与线路分配数据。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadUserData() {
  users.value = await fetchUsersApi()
  allTrunks.value = await fetchTrunksApi()
  const assignmentEntries = await Promise.all(
    users.value.map(async (userItem) => [userItem.id, await fetchUserTrunksApi(userItem.id)]),
  )
  assignedTrunksMap.value = Object.fromEntries(assignmentEntries)
}

/**
 * 打开新增或编辑用户弹窗。
 *
 * @param {'create' | 'edit'} mode 当前弹窗模式。
 * @param {object | null} row 当前编辑的用户对象。
 * @returns {void}
 */
function openUserDialog(mode, row = null) {
  userDialogMode.value = mode
  editingUserId.value = row?.id || null
  Object.assign(userForm, createDefaultUserForm())
  if (row) {
    Object.assign(userForm, {
      username: row.username,
      display_name: row.display_name,
      mobile: row.mobile || '',
      email: row.email || '',
      status: row.status,
      role_codes: [...(row.role_codes || [])],
      password: '',
    })
  }
  userDialogVisible.value = true
}

/**
 * 提交用户新增或编辑操作。
 *
 * @returns {Promise<void>} 保存完成后的 Promise。
 */
async function submitUser() {
  submittingUser.value = true
  try {
    if (userDialogMode.value === 'create') {
      await createUserApi({
        username: userForm.username,
        password: userForm.password,
        display_name: userForm.display_name,
        mobile: userForm.mobile || null,
        email: userForm.email || null,
        status: userForm.status,
        role_codes: userForm.role_codes,
      })
      ElMessage.success('用户已创建')
    } else {
      await updateUserApi(editingUserId.value, {
        display_name: userForm.display_name,
        mobile: userForm.mobile || null,
        email: userForm.email || null,
        status: userForm.status,
        role_codes: userForm.role_codes,
        password: userForm.password || null,
      })
      ElMessage.success('用户已更新')
    }

    userDialogVisible.value = false
    await loadUserData()
  } finally {
    submittingUser.value = false
  }
}

/**
 * 打开线路分配弹窗。
 *
 * @param {object} row 当前选中的用户对象。
 * @returns {void}
 */
function openAssignDialog(row) {
  assigningUser.value = row
  selectedTrunkIds.value = (assignedTrunksMap.value[row.id] || []).map((item) => item.id)
  assignDialogVisible.value = true
}

/**
 * 提交用户线路分配关系。
 *
 * @returns {Promise<void>} 保存完成后的 Promise。
 */
async function submitAssignments() {
  if (!assigningUser.value) {
    return
  }
  submittingAssign.value = true
  try {
    await replaceUserTrunksApi(assigningUser.value.id, selectedTrunkIds.value)
    ElMessage.success('线路分配已更新')
    assignDialogVisible.value = false
    await loadUserData()
  } finally {
    submittingAssign.value = false
  }
}

onMounted(loadUserData)
</script>
