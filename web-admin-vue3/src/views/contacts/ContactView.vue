<template>
  <div class="split-grid">
    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">名单批次</h2>
          <p class="page-subtitle">批次仅保留名称和备注，用于承接联系人导入。</p>
        </div>
        <div class="page-toolbar-right">
          <el-button type="primary" plain @click="loadBatches">刷新</el-button>
          <el-button type="primary" @click="openBatchDialog">新增批次</el-button>
        </div>
      </div>

      <el-table :data="batches" border highlight-current-row @current-change="handleBatchChange">
        <el-table-column prop="batch_name" label="批次名称" min-width="180" />
        <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
        <el-table-column prop="source_type" label="导入类型" width="110" />
        <el-table-column prop="import_total" label="总数" width="80" />
        <el-table-column prop="success_total" label="成功" width="80" />
        <el-table-column prop="failed_total" label="失败" width="80" />
        <el-table-column prop="import_status" label="状态" width="100" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="danger" @click.stop="removeBatch(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="page-card table-section">
      <div class="page-toolbar">
        <div>
          <h2 class="page-title">联系人</h2>
          <p class="page-subtitle">
            {{ activeBatch ? `当前批次：${activeBatch.batch_name}，默认导入文件并归属到该批次。` : '默认采用批量导入，可选单个录入姓名和手机号。' }}
          </p>
        </div>
        <div class="page-toolbar-right">
          <el-button type="primary" plain @click="loadContacts">刷新</el-button>
          <el-button type="primary" @click="openContactDialog">新增联系人</el-button>
        </div>
      </div>

      <el-table :data="contacts" border>
        <el-table-column prop="customer_name" label="客户姓名" min-width="160" />
        <el-table-column prop="mobile" label="手机号" min-width="160" />
        <el-table-column prop="contact_status" label="状态" width="110" />
        <el-table-column prop="last_intent_code" label="最近意向" width="120" />
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeContact(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="batchDialogVisible" title="新增名单批次" width="560px">
      <el-form :model="batchForm" label-width="90px">
        <el-form-item label="批次名称">
          <el-input v-model="batchForm.batch_name" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="batchForm.remark" type="textarea" :rows="4" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingBatch" @click="submitBatch">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="contactDialogVisible" title="新增联系人" width="760px">
      <el-form :model="contactForm" label-width="100px">
        <el-form-item label="导入方式">
          <el-radio-group v-model="contactForm.mode">
            <el-radio-button label="file">批次导入</el-radio-button>
            <el-radio-button label="single">单个导入</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="所属批次">
          <el-select v-model="contactForm.batch_id" placeholder="请选择批次" clearable>
            <el-option v-for="batch in batches" :key="batch.id" :label="batch.batch_name" :value="batch.id" />
          </el-select>
        </el-form-item>

        <template v-if="contactForm.mode === 'file'">
          <el-form-item label="导入文件">
            <el-upload
              class="contact-upload"
              drag
              :auto-upload="false"
              :show-file-list="false"
              accept=".txt,.csv,.xlsx,.xls"
              :on-change="handleImportFileChange"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">拖拽文件到这里，或 <em>点击选择文件</em></div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 `txt / csv / xlsx / xls`，默认从模板表头读取“客户姓名、手机号”。
                </div>
              </template>
            </el-upload>
            <div v-if="contactForm.fileName" class="upload-file-name">已选择：{{ contactForm.fileName }}</div>
          </el-form-item>
          <el-form-item label="模板下载">
            <div class="template-actions">
              <el-button @click="downloadTxtTemplate">TXT 模板</el-button>
              <el-button @click="downloadCsvTemplate">CSV 模板</el-button>
              <el-button @click="downloadXlsxTemplate">Excel 模板</el-button>
            </div>
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="客户姓名">
            <el-input v-model="contactForm.customer_name" maxlength="255" />
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="contactForm.mobile" maxlength="32" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="contactDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submittingContact" @click="submitContact">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'

import {
  createBatchApi,
  createContactRecordApi,
  deleteBatchApi,
  deleteContactRecordApi,
  fetchBatchesApi,
  fetchContactRecordsApi,
  importContactRecordsApi,
} from '@/api/modules'

const batches = ref([])
const contacts = ref([])
const activeBatch = ref(null)
const batchDialogVisible = ref(false)
const contactDialogVisible = ref(false)
const submittingBatch = ref(false)
const submittingContact = ref(false)
const batchForm = reactive(createDefaultBatchForm())
const contactForm = reactive(createDefaultContactForm())

/**
 * 创建名单批次表单默认值对象。
 *
 * @returns {{batch_name: string, remark: string}} 批次表单默认值。
 */
function createDefaultBatchForm() {
  return {
    batch_name: '',
    remark: '',
  }
}

/**
 * 创建联系人表单默认值对象。
 *
 * @returns {{mode: string, batch_id: number | null, customer_name: string, mobile: string, file: File | null, fileName: string}} 联系人表单默认值。
 */
function createDefaultContactForm() {
  return {
    mode: 'file',
    batch_id: null,
    customer_name: '',
    mobile: '',
    file: null,
    fileName: '',
  }
}

/**
 * 加载全部名单批次。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadBatches() {
  batches.value = await fetchBatchesApi()
  if (activeBatch.value) {
    activeBatch.value = batches.value.find((item) => item.id === activeBatch.value.id) || null
  }
}

/**
 * 加载联系人列表。
 *
 * @returns {Promise<void>} 数据加载完成后的 Promise。
 */
async function loadContacts() {
  contacts.value = await fetchContactRecordsApi(activeBatch.value?.id || null)
}

/**
 * 处理批次切换行为并刷新联系人。
 *
 * @param {object | null} currentRow 当前选中的批次对象。
 * @returns {Promise<void>} 联系人刷新完成后的 Promise。
 */
async function handleBatchChange(currentRow) {
  activeBatch.value = currentRow
  await loadContacts()
}

/**
 * 打开新增批次弹窗。
 *
 * @returns {void} 无返回值。
 */
function openBatchDialog() {
  Object.assign(batchForm, createDefaultBatchForm())
  batchDialogVisible.value = true
}

/**
 * 打开新增联系人弹窗并默认指向当前批次。
 *
 * @returns {void} 无返回值。
 */
function openContactDialog() {
  Object.assign(contactForm, createDefaultContactForm(), {
    batch_id: activeBatch.value?.id || null,
  })
  contactDialogVisible.value = true
}

/**
 * 保存名单批次。
 *
 * @returns {Promise<void>} 保存完成后的 Promise。
 */
async function submitBatch() {
  const batchName = batchForm.batch_name.trim()
  if (!batchName) {
    ElMessage.warning('请输入批次名称')
    return
  }
  submittingBatch.value = true
  try {
    await createBatchApi({
      batch_name: batchName,
      remark: batchForm.remark.trim() || null,
    })
    ElMessage.success('批次已创建')
    batchDialogVisible.value = false
    await loadBatches()
  } finally {
    submittingBatch.value = false
  }
}

/**
 * 删除指定名单批次。
 *
 * @param {object} row 当前选中的批次对象。
 * @returns {Promise<void>} 删除完成后的 Promise。
 */
async function removeBatch(row) {
  await ElMessageBox.confirm(`确定删除批次「${row.batch_name}」吗？`, '删除确认', { type: 'warning' })
  await deleteBatchApi(row.id)
  ElMessage.success('批次已删除')
  if (activeBatch.value?.id === row.id) {
    activeBatch.value = null
  }
  await loadBatches()
  await loadContacts()
}

/**
 * 处理导入文件变更并缓存用户选择的原始文件。
 *
 * @param {object} uploadFile Element Plus 上传组件回传的文件对象。
 * @returns {void} 无返回值。
 */
function handleImportFileChange(uploadFile) {
  contactForm.file = uploadFile.raw || null
  contactForm.fileName = uploadFile.name || ''
}

/**
 * 统一提交联系人创建动作，并按当前模式分发到单个创建或批量导入。
 *
 * @returns {Promise<void>} 提交完成后的 Promise。
 */
async function submitContact() {
  if (!contactForm.batch_id) {
    ElMessage.warning('请选择所属批次')
    return
  }
  submittingContact.value = true
  try {
    if (contactForm.mode === 'single') {
      await submitSingleContact()
      ElMessage.success('联系人已创建')
    } else {
      const importSummary = await submitContactImport()
      if (!importSummary) {
        return
      }
      ElMessage.success(`联系人已导入，共 ${importSummary.success_total} 条`)
    }
    contactDialogVisible.value = false
    await loadBatches()
    await loadContacts()
  } catch (error) {
    if (!error?.response) {
      ElMessage.error(error?.message || '联系人保存失败')
    }
  } finally {
    submittingContact.value = false
  }
}

/**
 * 提交单个联系人创建请求。
 *
 * @returns {Promise<void>} 保存完成后的 Promise。
 */
async function submitSingleContact() {
  const mobile = contactForm.mobile.trim()
  if (!mobile) {
    ElMessage.warning('请输入手机号')
    return
  }
  await createContactRecordApi({
    batch_id: contactForm.batch_id,
    customer_name: contactForm.customer_name.trim() || null,
    mobile,
  })
}

/**
 * 解析所选文件并提交批量导入请求。
 *
 * @returns {Promise<object>} 导入结果摘要对象。
 */
async function submitContactImport() {
  if (!contactForm.file) {
    ElMessage.warning('请先选择导入文件')
    return null
  }
  const parsedRecords = await parseUploadedContactFile(contactForm.file)
  if (!parsedRecords.length) {
    ElMessage.warning('导入文件中没有可用联系人')
    return null
  }
  return importContactRecordsApi({
    batch_id: contactForm.batch_id,
    source_type: resolveImportSourceType(contactForm.file.name),
    original_filename: contactForm.file.name,
    records: parsedRecords,
  })
}

/**
 * 根据文件扩展名解析联系人文件内容。
 *
 * @param {File} file 用户上传的原始文件对象。
 * @returns {Promise<Array<{customer_name: string | null, mobile: string}>>} 标准化后的联系人数组。
 */
async function parseUploadedContactFile(file) {
  const extension = resolveFileExtension(file.name)
  if (extension === 'txt') {
    const text = await file.text()
    return parseTxtContacts(text)
  }
  if (extension === 'csv' || extension === 'xlsx' || extension === 'xls') {
    const buffer = await file.arrayBuffer()
    const workbook = XLSX.read(buffer, { type: 'array' })
    const firstSheetName = workbook.SheetNames[0]
    const firstSheet = workbook.Sheets[firstSheetName]
    return parseWorksheetRows(XLSX.utils.sheet_to_json(firstSheet, { header: 1, defval: '' }))
  }
  throw new Error('仅支持 txt、csv、xlsx、xls 文件')
}

/**
 * 解析 TXT 文本内容为联系人数组。
 *
 * @param {string} text TXT 文件的完整文本内容。
 * @returns {Array<{customer_name: string | null, mobile: string}>} 标准化后的联系人数组。
 */
function parseTxtContacts(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.split(/[,\t，]/).map((item) => item.trim()).filter(Boolean))
    .filter((parts) => !(parts[0] === '客户姓名' && parts[1] === '手机号'))
    .map((parts) => normalizeImportedContactLine({ customer_name: parts[0] || '', mobile: parts[1] || parts[0] || '' }))
    .filter(Boolean)
}

/**
 * 解析表格类文件的二维数组内容。
 *
 * @param {Array<Array<string>>} rows 由 xlsx 库解析出的二维表格数组。
 * @returns {Array<{customer_name: string | null, mobile: string}>} 标准化后的联系人数组。
 */
function parseWorksheetRows(rows) {
  const normalizedRows = rows
    .map((row) => (Array.isArray(row) ? row.map((cell) => String(cell ?? '').trim()) : []))
    .filter((row) => row.some(Boolean))
  if (!normalizedRows.length) {
    return []
  }
  const headerRow = normalizedRows[0]
  const mobileIndex = findHeaderIndex(headerRow, ['手机号', '手机', 'mobile', 'phone'])
  const customerNameIndex = findHeaderIndex(headerRow, ['客户姓名', '姓名', 'customer_name', 'name'])
  const dataRows = mobileIndex >= 0 ? normalizedRows.slice(1) : normalizedRows
  return dataRows
    .map((row) =>
      normalizeImportedContactLine({
        customer_name: customerNameIndex >= 0 ? row[customerNameIndex] : row[0],
        mobile: mobileIndex >= 0 ? row[mobileIndex] : row[1] || row[0],
      }),
    )
    .filter(Boolean)
}

/**
 * 把单行导入记录清洗为接口可接收的标准对象。
 *
 * @param {{customer_name: string | null | undefined, mobile: string | null | undefined}} row 单行联系人原始数据。
 * @returns {{customer_name: string | null, mobile: string} | null} 可用联系人对象，手机号为空时返回 null。
 */
function normalizeImportedContactLine(row) {
  const mobile = String(row.mobile || '').trim()
  if (!mobile || ['手机号', 'mobile', 'phone'].includes(mobile.toLowerCase())) {
    return null
  }
  const customerName = String(row.customer_name || '').trim()
  return {
    customer_name: customerName || null,
    mobile,
  }
}

/**
 * 在表头数组中查找匹配的列序号。
 *
 * @param {string[]} headers 当前文件第一行的表头数组。
 * @param {string[]} candidates 允许匹配的表头别名数组。
 * @returns {number} 命中的索引位置，未命中时返回 -1。
 */
function findHeaderIndex(headers, candidates) {
  const normalizedCandidates = candidates.map((item) => item.toLowerCase())
  return headers.findIndex((header) => normalizedCandidates.includes(String(header).trim().toLowerCase()))
}

/**
 * 下载 TXT 导入模板。
 *
 * @returns {void} 无返回值。
 */
function downloadTxtTemplate() {
  triggerTextDownload('联系人导入模板.txt', '客户姓名,手机号\n张三,13800138000\n李四,13900139000\n')
}

/**
 * 下载 CSV 导入模板。
 *
 * @returns {void} 无返回值。
 */
function downloadCsvTemplate() {
  triggerTextDownload('联系人导入模板.csv', '\uFEFF客户姓名,手机号\n张三,13800138000\n李四,13900139000\n')
}

/**
 * 下载 Excel 导入模板。
 *
 * @returns {void} 无返回值。
 */
function downloadXlsxTemplate() {
  const worksheet = XLSX.utils.json_to_sheet([
    { 客户姓名: '张三', 手机号: '13800138000' },
    { 客户姓名: '李四', 手机号: '13900139000' },
  ])
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, '联系人模板')
  XLSX.writeFile(workbook, '联系人导入模板.xlsx')
}

/**
 * 生成文本模板下载动作。
 *
 * @param {string} filename 下载文件名。
 * @param {string} content 下载文件内容。
 * @returns {void} 无返回值。
 */
function triggerTextDownload(filename, content) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

/**
 * 根据文件名解析导入来源类型。
 *
 * @param {string} filename 用户上传的文件名。
 * @returns {string} 后端批次统计使用的来源类型。
 */
function resolveImportSourceType(filename) {
  const extension = resolveFileExtension(filename)
  if (extension === 'txt' || extension === 'csv') {
    return 'csv'
  }
  if (extension === 'xlsx' || extension === 'xls') {
    return 'xlsx'
  }
  return extension || 'csv'
}

/**
 * 提取文件扩展名并统一为小写。
 *
 * @param {string} filename 用户上传的文件名。
 * @returns {string} 小写扩展名，未命中时返回空字符串。
 */
function resolveFileExtension(filename) {
  const parts = String(filename || '').split('.')
  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}

/**
 * 删除指定联系人。
 *
 * @param {object} row 当前选中的联系人对象。
 * @returns {Promise<void>} 删除完成后的 Promise。
 */
async function removeContact(row) {
  await ElMessageBox.confirm(`确定删除联系人「${row.customer_name || row.mobile}」吗？`, '删除确认', { type: 'warning' })
  await deleteContactRecordApi(row.id)
  ElMessage.success('联系人已删除')
  await loadBatches()
  await loadContacts()
}

/**
 * 初始化名单页数据。
 *
 * @returns {Promise<void>} 初始化完成后的 Promise。
 */
async function initializePage() {
  await loadBatches()
  await loadContacts()
}

onMounted(initializePage)
</script>

<style scoped>
.template-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.upload-file-name {
  margin-top: 10px;
  color: #606266;
  font-size: 13px;
}

.contact-upload {
  width: 100%;
}
</style>
