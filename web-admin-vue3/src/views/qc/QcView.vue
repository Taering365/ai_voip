<template>
  <div class="split-grid">
    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">质检规则</h2>
          <p class="page-subtitle">维护关键词、意向、敏感词等质检规则。</p>
        </div>
        <div class="page-toolbar-right">
          <el-button type="primary" plain @click="loadQcData">刷新</el-button>
          <el-button type="primary" @click="openRuleDialog('create')">新增规则</el-button>
        </div>
      </div>

      <el-table :data="rules" border>
        <el-table-column prop="rule_code" label="编码" min-width="140" />
        <el-table-column prop="rule_name" label="名称" min-width="160" />
        <el-table-column prop="rule_type" label="类型" width="120" />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column label="规则配置" min-width="220">
          <template #default="{ row }">
            <pre class="json-block">{{ formatJson(row.rule_config) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click="openRuleDialog('edit', row)">编辑</el-button>
            <el-button link type="danger" @click="removeRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">质检结果</h2>
          <p class="page-subtitle">展示通话后的自动评分、语义标签、意向等级和摘要内容。</p>
        </div>
      </div>

      <el-table :data="results" border>
        <el-table-column prop="session_id" label="会话 ID" width="90" />
        <el-table-column prop="score" label="评分" width="90" />
        <el-table-column prop="intent_level" label="自动意向" width="110" />
        <el-table-column prop="manual_intent_level" label="人工意向" width="110" />
        <el-table-column prop="flow_label" label="流程标签" width="120" />
        <el-table-column label="风险标签" min-width="180">
          <template #default="{ row }">
            {{ (row.risk_tags || []).join('、') || '--' }}
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.summary_text || '--' }}
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="ruleDialogVisible" :title="ruleDialogMode === 'create' ? '新增规则' : '编辑规则'" width="720px">
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="规则编码">
          <el-input v-model="ruleForm.rule_code" :disabled="ruleDialogMode === 'edit'" />
        </el-form-item>
        <el-form-item label="规则名称">
          <el-input v-model="ruleForm.rule_name" />
        </el-form-item>
        <el-form-item label="规则类型">
          <el-input v-model="ruleForm.rule_type" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="ruleForm.is_enabled" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="ruleForm.priority" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="规则配置">
          <JsonEditor v-model="ruleForm.rule_config_text" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingRule" @click="submitRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import JsonEditor from '@/components/JsonEditor.vue'
import { createQcRuleApi, deleteQcRuleApi, fetchQcResultsApi, fetchQcRulesApi, updateQcRuleApi } from '@/api/modules'
import { formatJson, parseJsonText } from '@/utils/format'

const rules = ref([])
const results = ref([])
const ruleDialogVisible = ref(false)
const ruleDialogMode = ref('create')
const editingRuleId = ref(null)
const submittingRule = ref(false)
const ruleForm = reactive(createDefaultRuleForm())

/**
 * 创建质检规则表单默认值对象。
 *
 * @returns {object} 质检规则表单默认值。
 */
function createDefaultRuleForm() {
  return {
    rule_code: '',
    rule_name: '',
    rule_type: '',
    is_enabled: true,
    priority: 100,
    rule_config_text: '{}',
  }
}

/**
 * 加载质检规则与质检结果。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadQcData() {
  const [ruleItems, resultItems] = await Promise.all([fetchQcRulesApi(), fetchQcResultsApi()])
  rules.value = ruleItems
  results.value = resultItems
}

/**
 * 打开质检规则弹窗。
 *
 * @param {'create' | 'edit'} mode 当前弹窗模式。
 * @param {object | null} row 当前编辑的规则对象。
 * @returns {void}
 */
function openRuleDialog(mode, row = null) {
  ruleDialogMode.value = mode
  editingRuleId.value = row?.id || null
  Object.assign(ruleForm, createDefaultRuleForm())

  if (row) {
    Object.assign(ruleForm, {
      rule_code: row.rule_code,
      rule_name: row.rule_name,
      rule_type: row.rule_type,
      is_enabled: row.is_enabled,
      priority: row.priority,
      rule_config_text: formatJson(row.rule_config),
    })
  }

  ruleDialogVisible.value = true
}

/**
 * 保存质检规则。
 *
 * @returns {Promise<void>} 保存完成后的 Promise。
 */
async function submitRule() {
  submittingRule.value = true
  try {
    const payload = {
      rule_code: ruleForm.rule_code,
      rule_name: ruleForm.rule_name,
      rule_type: ruleForm.rule_type,
      is_enabled: ruleForm.is_enabled,
      priority: ruleForm.priority,
      rule_config: parseJsonText(ruleForm.rule_config_text, {}),
    }

    if (ruleDialogMode.value === 'create') {
      await createQcRuleApi(payload)
      ElMessage.success('规则已创建')
    } else {
      delete payload.rule_code
      await updateQcRuleApi(editingRuleId.value, payload)
      ElMessage.success('规则已更新')
    }

    ruleDialogVisible.value = false
    await loadQcData()
  } finally {
    submittingRule.value = false
  }
}

/**
 * 删除指定质检规则。
 *
 * @param {object} row 当前选中的规则对象。
 * @returns {Promise<void>} 删除完成后的 Promise。
 */
async function removeRule(row) {
  await ElMessageBox.confirm(`确定删除规则「${row.rule_name}」吗？`, '删除确认', { type: 'warning' })
  await deleteQcRuleApi(row.id)
  ElMessage.success('规则已删除')
  await loadQcData()
}

onMounted(loadQcData)
</script>
