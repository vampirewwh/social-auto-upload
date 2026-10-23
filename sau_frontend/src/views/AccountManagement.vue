<template>
  <div class="account-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span class="title">账号管理</span>
            <span class="sub">共 {{ store.accounts.length }} 个账号，来自 cookies/ 目录</span>
          </div>
          <div class="header-actions">
            <el-button size="small" @click="store.loadAccounts()" :loading="store.accountsLoading">
              刷新
            </el-button>
            <el-button size="small" type="primary" @click="openLogin">扫码 / 浏览器登录</el-button>
            <el-button size="small" @click="uploadVisible = true">导入 Cookie</el-button>
          </div>
        </div>
      </template>

      <el-table :data="store.accounts" v-loading="store.accountsLoading" empty-text="还没有账号">
        <el-table-column label="平台" width="150">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.label }}</el-tag>
            <span class="key">{{ row.platform }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="account" label="账号名" width="160" />
        <el-table-column prop="file" label="Cookie 文件" min-width="200" />
        <el-table-column label="Cookie 数" width="110">
          <template #default="{ row }">
            <span :class="{ bad: row.cookie_count <= 0 }">
              {{ row.cookie_count > 0 ? row.cookie_count : '无效' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ (row.size / 1024).toFixed(1) }} KB</template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" align="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="checkAccount(row)">
              校验
            </el-button>
            <el-button size="small" text type="primary" @click="relogin(row)">重新登录</el-button>
            <el-button size="small" text type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="result-card" v-if="recentLogs.length">
      <template #header>
        <div class="card-header">
          <span>最近操作</span>
          <el-button size="small" text @click="recentLogs = []">清空</el-button>
        </div>
      </template>
      <div v-for="(item, i) in recentLogs" :key="i" class="log-item">
        <el-tag size="small" :type="item.ok ? 'success' : 'danger'" effect="dark">
          {{ item.ok ? '成功' : '失败' }}
        </el-tag>
        <span class="log-title">{{ item.title }}</span>
        <span class="log-text">{{ item.text }}</span>
      </div>
    </el-card>

    <el-dialog v-model="uploadVisible" title="导入 Cookie 文件" width="480px">
      <el-form label-position="top">
        <el-form-item label="平台" required>
          <el-select v-model="uploadPlatform" filterable style="width: 100%">
            <el-option
              v-for="p in platformOptions"
              :key="p.key"
              :label="p.label"
              :value="p.key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="账号名" required>
          <el-input v-model="uploadAccount" placeholder="例如 creator" />
        </el-form-item>
        <el-form-item label="Cookie JSON 文件" required>
          <input type="file" accept=".json" @change="onFileChange" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="doUpload">导入</el-button>
      </template>
    </el-dialog>

    <LoginDialog v-model="loginVisible" :default-platform="loginPlatform" @success="onLoginSuccess" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import LoginDialog from '@/components/LoginDialog.vue'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()

const uploadVisible = ref(false)
const uploadPlatform = ref('douyin')
const uploadAccount = ref('')
const uploadFile = ref(null)
const uploading = ref(false)

const loginVisible = ref(false)
const loginPlatform = ref('douyin')

const recentLogs = ref([])

const platformOptions = computed(() => store.platforms)

function fmtTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return (
    d.getFullYear() +
    '-' +
    pad(d.getMonth() + 1) +
    '-' +
    pad(d.getDate()) +
    ' ' +
    pad(d.getHours()) +
    ':' +
    pad(d.getMinutes())
  )
}

function pushLog(title, ok, text) {
  recentLogs.value.unshift({ title, ok, text })
  if (recentLogs.value.length > 20) recentLogs.value.pop()
}

function openLogin() {
  loginPlatform.value = uploadPlatform.value || 'douyin'
  loginVisible.value = true
}

function relogin(row) {
  loginPlatform.value = row.platform
  loginVisible.value = true
}

async function onLoginSuccess() {
  await store.loadAccounts()
}

async function checkAccount(row) {
  try {
    const task = await sauApi.createTask(row.platform, 'check', { account: row.account })
    pushLog('校验 ' + row.label + ' / ' + row.account, true, '已提交任务 ' + task.id)
    pollCheck(task.id, row)
  } catch (e) {
    pushLog('校验 ' + row.label + ' / ' + row.account, false, e.message)
  }
}

async function pollCheck(id, row) {
  let tries = 0
  const timer = setInterval(async () => {
    tries += 1
    try {
      const data = await sauApi.getTask(id)
      if (['success', 'failed', 'cancelled'].includes(data.status)) {
        clearInterval(timer)
        const lines = data.logs || []
        const last = lines.filter((l) => l.trim()).slice(-3).join(' | ')
        pushLog(
          '校验 ' + row.label + ' / ' + row.account,
          data.status === 'success' && data.exit_code === 0,
          last || ('退出码 ' + data.exit_code)
        )
      }
    } catch {
      clearInterval(timer)
    }
    if (tries > 120) clearInterval(timer)
  }, 1500)
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      '删除账号 ' + row.label + ' / ' + row.account + ' 的登录态？',
      '确认删除',
      { type: 'warning' }
    )
  } catch {
    return
  }
  await sauApi.deleteAccount(row.platform, row.account)
  ElMessage.success('已删除')
  await store.loadAccounts()
}

function onFileChange(ev) {
  const file = ev.target.files && ev.target.files[0]
  uploadFile.value = file || null
}

async function doUpload() {
  if (!uploadPlatform.value || !uploadAccount.value || !uploadFile.value) {
    ElMessage.warning('请填写平台、账号名并选择文件')
    return
  }
  uploading.value = true
  try {
    const info = await sauApi.uploadAccount(
      uploadPlatform.value,
      uploadAccount.value,
      uploadFile.value
    )
    ElMessage.success('导入成功：' + info.file)
    uploadVisible.value = false
    uploadFile.value = null
    uploadAccount.value = ''
    await store.loadAccounts()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
  await store.loadSchema()
  await store.loadAccounts()
})
</script>

<style scoped>
.account-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.card-header .title {
  font-weight: 600;
  font-size: 15px;
}
.card-header .sub {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.key {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}
.bad {
  color: #f56c6c;
  font-weight: 600;
}
.log-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px dashed #ebeef5;
  font-size: 13px;
}
.log-title {
  font-weight: 600;
  color: #303133;
}
.log-text {
  color: #606266;
  word-break: break-all;
}
</style>
