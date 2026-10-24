<template>
  <div class="account-panel">
    <el-alert
      v-if="!supported"
      type="info"
      :closable="false"
      show-icon
      :title="'「' + platformLabel + '」暂不支持数据分析'"
      description="目前支持抖音与视频号，其余平台的数据同步正在开发中。"
    />

    <template v-else>
      <div class="panel-head">
        <div v-if="overview && overview.latest" class="account-line">
          <span class="nickname">{{ overview.latest.nickname || account }}</span>
          <el-tag v-if="overview.latest.douyin_id" size="small" effect="plain">
            {{ platform === 'tencent' ? '视频号ID' : '抖音号' }}
            {{ overview.latest.douyin_id }}
          </el-tag>
          <el-tag
            v-if="overview.latest.enterprise_verify"
            size="small"
            type="success"
            effect="plain"
          >
            {{ overview.latest.enterprise_verify }}
          </el-tag>
          <span class="muted">最近同步：{{ formatTime(overview.latest.captured_at) }}</span>
        </div>
        <div v-else-if="!loading" class="account-line">
          <span class="muted">还没有同步过数据，点「立即同步」开始。</span>
        </div>

        <div class="actions">
          <el-button type="primary" :loading="collecting" @click="sync">
            {{ collecting ? '同步中…' : '立即同步' }}
          </el-button>
        </div>
      </div>

      <el-row v-if="cards.length" :gutter="16" class="stat-row">
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

      <div class="works-head">
        <span class="works-title">作品明细 <span class="muted">共 {{ worksTotal }} 条</span></span>
        <div class="header-actions">
          <el-input
            v-model="keyword"
            placeholder="搜索作品描述"
            clearable
            size="small"
            style="width: 200px"
            @keyup.enter="search"
            @clear="search"
          />
          <el-button size="small" @click="search">搜索</el-button>
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="works"
        size="small"
        empty-text="还没有作品数据，先点「立即同步」"
      >
        <el-table-column label="封面" width="76">
          <template #default="{ row }">
            <el-image v-if="row.cover" :src="row.cover" fit="cover" class="cover">
              <template #error>
                <div class="cover cover-empty">失效</div>
              </template>
            </el-image>
            <div v-else class="cover cover-empty">无</div>
          </template>
        </el-table-column>
        <el-table-column label="作品" min-width="240">
          <template #default="{ row }">
            <div class="work-desc">{{ row.desc || '无作品描述' }}</div>
            <div class="work-meta">
              <el-tag v-if="row.is_private" size="small" type="info" effect="plain">私密</el-tag>
              <el-tag v-if="row.in_reviewing" size="small" type="warning" effect="plain">
                审核中
              </el-tag>
              <span>{{ formatTime(row.create_time) }}</span>
              <span v-if="row.duration">{{ formatDuration(row.duration) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="播放" width="78" align="right">
          <template #default="{ row }">{{ formatCount(row.play_count) }}</template>
        </el-table-column>
        <el-table-column label="点赞" width="78" align="right">
          <template #default="{ row }">{{ formatCount(row.digg_count) }}</template>
        </el-table-column>
        <el-table-column label="评论" width="78" align="right">
          <template #default="{ row }">{{ formatCount(row.comment_count) }}</template>
        </el-table-column>
        <el-table-column label="分享" width="78" align="right">
          <template #default="{ row }">{{ formatCount(row.share_count) }}</template>
        </el-table-column>
        <el-table-column label="收藏" width="78" align="right">
          <template #default="{ row }">{{ formatCount(row.collect_count) }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="worksTotal > 0"
        class="pager"
        background
        small
        layout="total, prev, pager, next"
        :total="worksTotal"
        :page-size="size"
        v-model:current-page="page"
        @current-change="loadWorks"
      />

      <el-collapse v-if="collectLogs.length" class="logs-box">
        <el-collapse-item title="同步日志" name="logs">
          <pre class="logs">{{ collectLogs.join('\n') }}</pre>
        </el-collapse-item>
      </el-collapse>
    </template>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const props = defineProps({
  platform: { type: String, required: true },
  account: { type: String, required: true },
  // 账号卡片里的基础信息，用于平台不支持时也能提示
  accountMeta: { type: Object, default: null }
})

const store = useSauStore()

const overview = ref(null)
const works = ref([])
const worksTotal = ref(0)
const page = ref(1)
const size = ref(10)
const keyword = ref('')
const loading = ref(false)

const collecting = ref(false)
const collectLogs = ref([])
let timer = null

const supportedPlatforms = ['douyin', 'tencent']
const supported = computed(() => supportedPlatforms.includes(props.platform))
const platformLabel = computed(() => store.platformLabel(props.platform))

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
      sub: previous ? '较上次同步' : '首次同步',
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
      label: '已同步作品',
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

function formatDuration(ms) {
  const total = Math.round(Number(ms) / 1000)
  if (!Number.isFinite(total) || total <= 0) return ''
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return minutes + ':' + String(seconds).padStart(2, '0')
}

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
  if (!supported.value) return
  try {
    const data = await sauApi.getAnalyticsOverview(props.platform, props.account, {
      signal: requestController?.signal
    })
    overview.value = data
  } catch (error) {
    if (!isAborted(error)) throw error
  }
}

async function loadWorks() {
  if (!supported.value) return
  loading.value = true
  try {
    const data = await sauApi.listAnalyticsWorks(
      props.platform,
      props.account,
      page.value,
      size.value,
      keyword.value.trim(),
      { signal: requestController?.signal }
    )
    works.value = data.items || []
    worksTotal.value = data.total || 0
  } catch (error) {
    if (!isAborted(error)) throw error
  } finally {
    loading.value = false
  }
}

async function reload() {
  page.value = 1
  overview.value = null
  works.value = []
  worksTotal.value = 0
  abortPending()
  requestController = new AbortController()
  await Promise.all([loadOverview(), loadWorks()])
}

function search() {
  page.value = 1
  loadWorks()
}

async function sync() {
  collecting.value = true
  collectLogs.value = []
  try {
    const task = await sauApi.collectAnalytics(props.platform, props.account)
    pollTask(task.id)
  } catch (error) {
    collecting.value = false
  }
}

function pollTask(taskId) {
  clearInterval(timer)
  timer = setInterval(async () => {
    try {
      const task = await sauApi.getTask(taskId, 100)
      collectLogs.value = task.logs || []
      if (['success', 'failed', 'cancelled'].includes(task.status)) {
        clearInterval(timer)
        timer = null
        collecting.value = false
        if (task.status === 'success') {
          ElMessage.success('同步完成')
          await reload()
        } else {
          ElMessage.error(task.error || '同步失败')
        }
      }
    } catch (error) {
      clearInterval(timer)
      timer = null
      collecting.value = false
    }
  }, 1500)
}

watch(
  () => [props.platform, props.account],
  () => {
    if (props.platform && props.account) reload()
  },
  { immediate: true }
)

onUnmounted(() => {
  if (timer) clearInterval(timer)
  abortPending()
})

defineExpose({ reload })
</script>

<style scoped>
.account-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.account-line {
  display: flex;
  align-items: center;
  gap: 8px;
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
.actions {
  display: flex;
  gap: 8px;
}
.stat-row {
  margin-top: 2px;
}
.stat-card {
  margin-bottom: 8px;
}
.stat-label {
  font-size: 12px;
  color: #909399;
}
.stat-value {
  margin-top: 4px;
  font-size: 24px;
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
.works-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 4px;
}
.works-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.cover {
  width: 48px;
  height: 48px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
}
.cover-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
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
  margin-top: 8px;
  justify-content: flex-end;
}
.logs-box {
  border-top: none;
}
.logs {
  max-height: 200px;
  margin: 0;
  overflow: auto;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #606266;
  white-space: pre-wrap;
}
</style>
