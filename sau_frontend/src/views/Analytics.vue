<template>
  <div class="analytics">
    <el-card shadow="never">
      <div class="toolbar">
        <div>
          <div class="title">账号数据分析</div>
          <div class="sub">{{ subText }}</div>
        </div>
        <div class="actions" v-if="supported">
          <el-select
            v-model="account"
            placeholder="选择账号"
            style="width: 180px"
            @change="onAccountChange"
          >
            <el-option
              v-for="item in currentAccounts"
              :key="item.account"
              :label="item.account"
              :value="item.account"
            />
          </el-select>
          <el-button
            type="primary"
            :loading="collecting"
            :disabled="!account"
            @click="collect"
          >
            {{ collecting ? '采集中…' : '立即采集' }}
          </el-button>
          <el-button @click="openSchedule">自动采集设置</el-button>
        </div>
      </div>

      <el-alert
        v-if="!supported"
        type="info"
        :closable="false"
        show-icon
        :title="'「' + platformLabel + '」暂不支持数据分析'"
        description="目前仅支持抖音，其余平台的数据采集正在开发中。"
      />
      <template v-else>
        <el-alert
          v-if="!currentAccounts.length"
          type="warning"
          :closable="false"
          show-icon
          title="该平台还没有账号，请先到账号管理里登录并保存 cookie"
        />
        <div v-else-if="overview && overview.latest" class="account-line">
        <span class="nickname">{{ overview.latest.nickname || account }}</span>
        <el-tag v-if="overview.latest.douyin_id" size="small" effect="plain">
          {{ platform === 'tencent' ? '视频号ID' : '抖音号' }} {{ overview.latest.douyin_id }}
        </el-tag>
        <el-tag
          v-if="overview.latest.enterprise_verify"
          size="small"
          type="success"
          effect="plain"
        >
          {{ overview.latest.enterprise_verify }}
        </el-tag>
        <span class="muted">最近采集：{{ formatStamp(overview.latest.captured_at) }}</span>
      </div>
      <div v-else-if="account && !loading" class="account-line">
        <span class="muted">这个账号还没有采集过数据，点“立即采集”开始。</span>
      </div>
      </template>
    </el-card>

    <el-row v-if="cards.length" :gutter="16">
      <el-col :xs="12" :sm="6" v-for="card in cards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
          <div class="stat-sub">
            <span v-if="card.delta" :class="card.delta.startsWith('+') ? 'up' : 'down'">
              {{ card.delta }}
            </span>
            <span>{{ card.sub }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" v-if="supported">
      <template #header>
        <div class="card-header">
          <span>作品明细 <span class="sub">共 {{ worksTotal }} 条</span></span>
          <div class="header-actions">
            <el-input
              v-model="keyword"
              placeholder="搜索作品描述"
              clearable
              size="small"
              style="width: 220px"
              @keyup.enter="search"
              @clear="search"
            />
            <el-button size="small" @click="search">搜索</el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="works"
        size="small"
        empty-text="还没有作品数据，先点“立即采集”"
      >
        <el-table-column label="封面" width="88">
          <template #default="{ row }">
            <el-image v-if="row.cover" :src="row.cover" fit="cover" class="cover">
              <template #error>
                <div class="cover cover-empty">失效</div>
              </template>
            </el-image>
            <div v-else class="cover cover-empty">无</div>
          </template>
        </el-table-column>
        <el-table-column label="作品" min-width="260">
          <template #default="{ row }">
            <div class="work-desc">{{ row.desc || '无作品描述' }}</div>
            <div class="work-meta">
              <el-tag v-if="row.is_private" size="small" type="info" effect="plain">
                私密
              </el-tag>
              <el-tag v-if="row.in_reviewing" size="small" type="warning" effect="plain">
                审核中
              </el-tag>
              <span>{{ formatTime(row.create_time) }}</span>
              <span v-if="row.duration">{{ formatDuration(row.duration) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="播放" width="84" align="right">
          <template #default="{ row }">{{ formatCount(row.play_count) }}</template>
        </el-table-column>
        <el-table-column label="点赞" width="84" align="right">
          <template #default="{ row }">{{ formatCount(row.digg_count) }}</template>
        </el-table-column>
        <el-table-column label="评论" width="84" align="right">
          <template #default="{ row }">{{ formatCount(row.comment_count) }}</template>
        </el-table-column>
        <el-table-column label="分享" width="84" align="right">
          <template #default="{ row }">{{ formatCount(row.share_count) }}</template>
        </el-table-column>
        <el-table-column label="收藏" width="84" align="right">
          <template #default="{ row }">{{ formatCount(row.collect_count) }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="worksTotal > 0"
        class="pager"
        background
        layout="total, sizes, prev, pager, next"
        :total="worksTotal"
        :page-sizes="[10, 20, 50, 100]"
        v-model:current-page="page"
        v-model:page-size="size"
        @current-change="loadWorks"
        @size-change="onSizeChange"
      />
    </el-card>

    <el-card v-if="collectLogs.length" shadow="never">
      <template #header>
        <div class="card-header">
          <span>采集日志</span>
          <span class="sub">{{ collectStatus }}</span>
        </div>
      </template>
      <pre class="logs">{{ collectLogs.join('\n') }}</pre>
    </el-card>

    <el-dialog v-model="scheduleVisible" title="每日自动采集" width="480px">
      <el-form label-width="90px">
        <el-form-item label="启用">
          <el-switch v-model="schedule.enabled" />
        </el-form-item>
        <el-form-item label="采集时间">
          <el-time-picker
            v-model="schedule.time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="08:30"
            :disabled="!schedule.enabled"
          />
        </el-form-item>
        <el-form-item label="采集账号">
          <el-select
            v-model="scheduleAccounts"
            multiple
            placeholder="不选则采集全部抖音账号"
            style="width: 100%"
            :disabled="!schedule.enabled"
          >
            <el-option
              v-for="item in douyinAccounts"
              :key="item.account"
              :label="item.account"
              :value="item.account"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="schedule.last_run_date" label="上次运行">
          <span class="muted">{{ schedule.last_run_date }}</span>
        </el-form-item>
      </el-form>
      <div class="hint">自动采集在 Web 服务进程内运行，需要保持服务启动。</div>
      <template #footer>
        <el-button @click="scheduleVisible = false">取消</el-button>
        <el-button type="primary" :loading="scheduleSaving" @click="saveSchedule">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()
const route = useRoute()
const router = useRouter()

const platform = ref('douyin')
const account = ref('')
const overview = ref(null)
const works = ref([])
const worksTotal = ref(0)
const page = ref(1)
const size = ref(20)
const keyword = ref('')
const loading = ref(false)

const collecting = ref(false)
const collectLogs = ref([])
const collectStatus = ref('')
let pollTimer = null

const scheduleVisible = ref(false)
const scheduleSaving = ref(false)
const schedule = ref({ enabled: false, time: '08:30', last_run_date: '' })
const scheduleAccounts = ref([])

// 目前抖音和视频号有采集器，其余平台显示“暂不支持”占位
const supportedPlatforms = ['douyin', 'tencent']
const supported = computed(() => supportedPlatforms.includes(platform.value))

const currentAccounts = computed(() =>
  store.accounts.filter((item) => item.platform === platform.value)
)

const douyinAccounts = computed(() =>
  store.accounts.filter((item) => item.platform === 'douyin')
)

const platformLabel = computed(() => store.platformLabel(platform.value))

const subText = computed(() =>
  supported.value
    ? `从${platformLabel.value}创作者中心采集，数据保存在本地 db/analytics.db`
    : '账号经营数据看板'
)

const cards = computed(() => {
  const info = overview.value
  if (!info || !info.latest) return []
  const latest = info.latest
  const previous = info.previous
  const delta = (key) => {
    if (!previous || latest[key] == null || previous[key] == null) return ''
    const diff = Number(latest[key]) - Number(previous[key])
    if (!diff) return ''
    return diff > 0 ? '+' + diff : String(diff)
  }
  return [
    {
      label: '粉丝',
      value: formatCount(latest.follower_count),
      delta: delta('follower_count'),
      sub: previous ? '较上次采集' : '首次采集',
      color: '#409eff'
    },
    {
      label: '累计获赞',
      value: formatCount(latest.total_favorited),
      delta: delta('total_favorited'),
      sub: '来自创作者中心',
      color: '#f56c6c'
    },
    {
      label: '关注',
      value: formatCount(latest.following_count),
      delta: delta('following_count'),
      sub: '关注数',
      color: '#e6a23c'
    },
    {
      label: '已采集作品',
      value: formatCount(info.works_total),
      delta: '',
      sub: '本地作品库',
      color: '#67c23a'
    }
  ]
})

function formatCount(value) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return String(num)
}

function formatTime(seconds) {
  const num = Number(seconds)
  if (!num) return '-'
  const date = new Date(num * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return (
    date.getFullYear() +
    '-' +
    pad(date.getMonth() + 1) +
    '-' +
    pad(date.getDate()) +
    ' ' +
    pad(date.getHours()) +
    ':' +
    pad(date.getMinutes())
  )
}

function formatStamp(value) {
  return formatTime(value)
}

function formatDuration(ms) {
  const total = Math.round(Number(ms) / 1000)
  if (!Number.isFinite(total) || total <= 0) return ''
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return minutes + ':' + String(seconds).padStart(2, '0')
}

// 快速切换账号时旧请求可能后返回，用 AbortController 让过期请求作废
let requestController = null

function abortPending() {
  if (requestController) {
    requestController.abort()
    requestController = null
  }
}

function isAborted(error) {
  return error && (error.code === 'ERR_CANCELED' || error.name === 'CanceledError')
}

async function loadOverview() {
  if (!account.value) return
  const target = account.value
  const targetPlatform = platform.value
  try {
    const data = await sauApi.getAnalyticsOverview(targetPlatform, target, {
      signal: requestController?.signal
    })
    if (target === account.value && targetPlatform === platform.value) overview.value = data
  } catch (error) {
    if (!isAborted(error)) throw error
  }
}

async function loadWorks() {
  if (!account.value) return
  const target = account.value
  const targetPlatform = platform.value
  loading.value = true
  try {
    const data = await sauApi.listAnalyticsWorks(
      targetPlatform,
      target,
      page.value,
      size.value,
      keyword.value.trim(),
      { signal: requestController?.signal }
    )
    if (target === account.value && targetPlatform === platform.value) {
      works.value = data.items || []
      worksTotal.value = data.total || 0
    }
  } catch (error) {
    if (!isAborted(error)) throw error
  } finally {
    if (target === account.value && targetPlatform === platform.value) loading.value = false
  }
}

async function reload() {
  page.value = 1
  abortPending()
  requestController = new AbortController()
  await Promise.all([loadOverview(), loadWorks()])
}

function search() {
  page.value = 1
  loadWorks()
}

function onSizeChange() {
  page.value = 1
  loadWorks()
}

async function collect() {
  if (!account.value) {
    ElMessage.warning('请先选择账号')
    return
  }
  collecting.value = true
  collectLogs.value = []
  collectStatus.value = '采集中'
  try {
    const task = await sauApi.collectAnalytics(platform.value, account.value)
    pollTask(task.id)
  } catch (error) {
    collecting.value = false
    collectStatus.value = 'failed'
  }
}

function pollTask(taskId) {
  clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const task = await sauApi.getTask(taskId, 100)
      collectLogs.value = task.logs || []
      collectStatus.value = task.status
      if (['success', 'failed', 'cancelled'].includes(task.status)) {
        clearInterval(pollTimer)
        pollTimer = null
        collecting.value = false
        if (task.status === 'success') {
          ElMessage.success('采集完成')
          await reload()
        } else {
          ElMessage.error(task.error || '采集失败')
        }
      }
    } catch (error) {
      clearInterval(pollTimer)
      pollTimer = null
      collecting.value = false
    }
  }, 1500)
}

async function loadSchedule() {
  const data = await sauApi.getAnalyticsSchedule()
  schedule.value = {
    enabled: !!data.enabled,
    time: data.time || '08:30',
    last_run_date: data.last_run_date || ''
  }
  scheduleAccounts.value = (data.accounts || [])
    .filter((item) => item.platform === 'douyin' && item.account)
    .map((item) => item.account)
}

function openSchedule() {
  loadSchedule()
  scheduleVisible.value = true
}

async function saveSchedule() {
  scheduleSaving.value = true
  try {
    const data = await sauApi.saveAnalyticsSchedule({
      enabled: schedule.value.enabled,
      time: schedule.value.time || '08:30',
      accounts: scheduleAccounts.value.map((name) => ({
        platform: 'douyin',
        account: name
      }))
    })
    schedule.value = {
      enabled: !!data.enabled,
      time: data.time,
      last_run_date: new Date().toISOString().slice(0, 10)
    }
    scheduleVisible.value = false
    ElMessage.success('已保存')
  } finally {
    scheduleSaving.value = false
  }
}

function onAccountChange() {
  router.replace({ query: { platform: platform.value, account: account.value } })
  reload()
}

// 从 URL 同步平台与账号，返回是否有变化
function applyRouteQuery() {
  const p = (route.query.platform && String(route.query.platform)) || 'douyin'
  const a = (route.query.account && String(route.query.account)) || ''
  const changed = p !== platform.value || a !== account.value
  platform.value = p
  account.value = a || (currentAccounts.value[0] && currentAccounts.value[0].account) || ''
  return changed
}

// 同一路由组件在 query 变化时不会重新挂载，需手动响应
watch(
  () => route.query,
  () => {
    if (applyRouteQuery() && supported.value && account.value) reload()
  }
)

onMounted(async () => {
  await Promise.all([store.loadSchema(), store.loadAccounts()])
  if (applyRouteQuery() && supported.value && account.value) {
    await reload()
  }
  await loadSchedule()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  abortPending()
})
</script>

<style scoped>
.analytics {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.title {
  font-size: 18px;
  font-weight: 600;
}
.sub {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}
.actions {
  display: flex;
  gap: 8px;
}
.account-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.nickname {
  font-size: 15px;
  font-weight: 600;
}
.muted {
  font-size: 12px;
  color: #909399;
}
.stat-card {
  margin-bottom: 16px;
}
.stat-label {
  font-size: 13px;
  color: #909399;
}
.stat-value {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #c0c4cc;
}
.stat-sub .up {
  margin-right: 4px;
  color: #67c23a;
}
.stat-sub .down {
  margin-right: 4px;
  color: #f56c6c;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.cover {
  width: 56px;
  height: 56px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
}
.cover-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #c0c4cc;
}
.work-desc {
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}
.work-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}
.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
.logs {
  max-height: 240px;
  margin: 0;
  overflow: auto;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #606266;
  white-space: pre-wrap;
}
.hint {
  font-size: 12px;
  color: #909399;
}
</style>
