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

      <el-row :gutter="16" align="stretch" v-loading="store.accountsLoading">
        <el-col
          v-for="row in store.accounts"
          :key="row.platform + '/' + row.account"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
        >
          <el-card shadow="hover" class="account-card">
            <div class="account-top">
              <el-avatar
                :src="row.avatar || undefined"
                :size="42"
                class="account-avatar"
                :style="{ background: platformColor(row.platform) }"
              >
                {{ platformInitial(row.label) }}
              </el-avatar>
              <div class="account-id">
                <div class="platform-line">
                  <span class="platform-label">{{ row.label }}</span>
                  <span class="platform-key">{{ row.platform }}</span>
                </div>
                <div class="account-name" :title="row.nickname || row.account">
                  {{ row.nickname || row.account }}
                </div>
                <div v-if="row.nickname" class="account-alias">@{{ row.account }}</div>
                <div class="updated-at">更新于 {{ fmtTime(row.updated_at) }}</div>
              </div>
              <el-tooltip
                :content="statusHint(row)"
                placement="top"
                :disabled="!statusHint(row)"
              >
                <el-tag
                  size="small"
                  :type="statusType(row)"
                  effect="light"
                  class="status-dot"
                >
                  {{ statusText(row) }}
                </el-tag>
              </el-tooltip>
            </div>

            <div class="account-stats">
              <template v-if="row.follower_count != null">
                <div class="stat-item">
                  <span class="stat-num">{{ fmtCount(row.follower_count) }}</span>
                  <span class="stat-label">粉丝</span>
                </div>
                <div class="stat-item">
                  <span class="stat-num">{{ fmtCount(row.total_favorited) }}</span>
                  <span class="stat-label">获赞</span>
                </div>
                <div class="stat-item">
                  <span class="stat-num">{{ fmtCount(row.aweme_count) }}</span>
                  <span class="stat-label">作品</span>
                </div>
              </template>
              <div v-else class="stat-empty">暂无经营数据</div>
            </div>

            <div class="account-actions">
              <el-button
                size="small"
                type="primary"
                class="manual-btn"
                @click="openManual(row)"
              >
                手动发布
              </el-button>
              <div class="account-secondary">
                <el-button size="small" text type="primary" @click="viewData(row)">
                  查看数据
                </el-button>
                <el-button size="small" text type="primary" @click="checkAccount(row)">
                  校验
                </el-button>
                <el-button size="small" text type="primary" @click="relogin(row)">
                  重新登录
                </el-button>
                <el-button size="small" text type="danger" @click="remove(row)">删除</el-button>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="!store.accountsLoading && !store.accounts.length" description="还没有账号" />
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import LoginDialog from '@/components/LoginDialog.vue'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()
const router = useRouter()

const uploadVisible = ref(false)
const uploadPlatform = ref('douyin')
const uploadAccount = ref('')
const uploadFile = ref(null)
const uploading = ref(false)

const loginVisible = ref(false)
const loginPlatform = ref('douyin')

const recentLogs = ref([])
// platform/account -> 校验轮询定时器，组件卸载时统一清理
const checkTimers = new Map()

// 平台品牌色，用于卡片头像与视觉区分
const PLATFORM_COLORS = {
  douyin: '#17171a',
  kuaishou: '#ff4906',
  xiaohongshu: '#ff2442',
  bilibili: '#fb7299',
  tencent: '#07c160',
  alipay: '#1677ff',
  weibo: '#e6162d',
  hupu: '#d81e06',
  facebook: '#1877f2',
  'facebook-page': '#1877f2',
  instagram: '#e1306c',
  youtube: '#ff0000',
  baijiahao: '#5a6ff0',
  dayu: '#ff6a00',
  xueqiu: '#1f8fff',
  zhihu: '#0084ff',
  article: '#8a63d2'
}

function platformColor(platform) {
  return PLATFORM_COLORS[platform] || '#409eff'
}

function platformInitial(label) {
  return (label || '?').trim().charAt(0).toUpperCase()
}

function fmtCount(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return String(num)
}

// 卡片状态以真实校验结果为准；没校验过不冒充“正常”
function statusText(row) {
  if (row.login_valid === true) return '正常'
  if (row.login_valid === false) return '失效'
  return '未校验'
}

function statusType(row) {
  if (row.login_valid === true) return 'success'
  if (row.login_valid === false) return 'danger'
  return 'info'
}

function statusHint(row) {
  if (row.login_valid == null) return '尚未校验登录态，点「校验」确认'
  const when = row.login_checked_at ? fmtTime(row.login_checked_at) : ''
  const prefix = row.login_valid ? '最近校验有效' : '最近校验已失效'
  return when ? prefix + ' · ' + when : prefix
}

function stopCheck(key) {
  const timer = checkTimers.get(key)
  if (timer) clearInterval(timer)
  checkTimers.delete(key)
}

const platformOptions = computed(() => store.platforms)

function fmtTime(ts) {
  if (!ts) return '—'
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

function viewData(row) {
  router.push({
    path: '/analytics',
    query: { platform: row.platform, account: row.account }
  })
}

async function openManual(row) {
  try {
    await sauApi.openManual(row.platform, row.account)
    ElMessage.success('已打开官方后台，请在浏览器窗口中手动操作')
  } catch (e) {
    // 错误提示由请求拦截器统一弹出
  }
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
  // 同一行重复点“校验”时先停掉旧的轮询，避免多个定时器互相覆盖结果
  const key = row.platform + '/' + row.account
  const existing = checkTimers.get(key)
  if (existing) clearInterval(existing)
  let tries = 0
  const timer = setInterval(async () => {
    tries += 1
    try {
      const data = await sauApi.getTask(id)
      if (['success', 'failed', 'cancelled'].includes(data.status)) {
        stopCheck(key)
        const lines = data.logs || []
        const last = lines.filter((l) => l.trim()).slice(-3).join(' | ')
        pushLog(
          '校验 ' + row.label + ' / ' + row.account,
          data.status === 'success' && data.exit_code === 0,
          last || ('退出码 ' + data.exit_code)
        )
        // 刷新卡片，展示后端写回的真实登录态
        await store.loadAccounts()
      }
    } catch {
      stopCheck(key)
    }
    if (tries > 120) stopCheck(key)
  }, 1500)
  checkTimers.set(key, timer)
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
    // 错误提示由请求拦截器统一弹出
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
  await store.loadSchema()
  await store.loadAccounts()
})

onBeforeUnmount(() => {
  for (const timer of checkTimers.values()) clearInterval(timer)
  checkTimers.clear()
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

/* 账号卡片 */
.account-card {
  height: 100%;
  margin-bottom: 16px;
  border-radius: 8px;
  transition: transform 0.15s ease;
}
.account-card:hover {
  transform: translateY(-2px);
}
.account-card :deep(.el-card__body) {
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}
.account-top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.account-avatar {
  flex-shrink: 0;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
}
.account-id {
  flex: 1;
  min-width: 0;
}
.platform-line {
  display: flex;
  align-items: center;
  gap: 6px;
}
.platform-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}
.platform-key {
  font-size: 11px;
  color: #c0c4cc;
}
.account-name {
  margin-top: 3px;
  font-size: 16px;
  font-weight: 700;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.account-alias {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-dot {
  flex-shrink: 0;
}

.updated-at {
  margin-top: 2px;
  font-size: 11px;
  color: #c0c4cc;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.account-stats {
  margin-top: 12px;
  padding-top: 10px;
  padding-bottom: 12px;
  border-top: 1px solid #f0f2f5;
  display: flex;
}
.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.stat-item + .stat-item {
  border-left: 1px solid #f0f2f5;
}
.stat-num {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}
.stat-label {
  font-size: 11px;
  color: #909399;
}
.stat-empty {
  flex: 1;
  text-align: center;
  font-size: 12px;
  color: #c0c4cc;
  padding: 6px 0;
}

.account-actions {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid #f0f2f5;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.manual-btn {
  width: 100%;
}
.account-secondary {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.account-secondary :deep(.el-button + .el-button) {
  margin-left: 0;
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
