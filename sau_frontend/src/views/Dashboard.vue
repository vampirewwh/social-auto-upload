<template>
  <div class="dashboard">
    <!-- 空状态：还没有任何账号 -->
    <el-card v-if="!store.accounts.length && loaded" shadow="never" class="panel">
      <el-empty description="还没有添加任何账号" :image-size="90">
        <div class="onboard">
          <div class="onboard-step" v-for="(step, i) in onboardingSteps" :key="i">
            <span class="step-no">{{ i + 1 }}</span>
            <div class="step-body">
              <div class="step-title">{{ step.title }}</div>
              <div class="step-desc">{{ step.desc }}</div>
            </div>
            <el-button size="small" type="primary" plain @click="$router.push(step.to)">
              {{ step.action }}
            </el-button>
          </div>
        </div>
      </el-empty>
    </el-card>

    <template v-else>
      <!-- 顶部五张指标卡 -->
      <el-row :gutter="16">
        <el-col :xs="12" :sm="8" :lg="4" v-for="card in cards" :key="card.key">
          <el-card
            shadow="never"
            class="stat-card"
            :class="{ clickable: card.to }"
            @click="card.to && $router.push(card.to)"
          >
            <div class="stat-label">
              {{ card.label }}
              <el-tooltip :content="card.hint" placement="top">
                <el-icon class="hint-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
            <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
            <div class="stat-sub">{{ card.sub }}</div>
          </el-card>
        </el-col>
      </el-row>

      <div class="updated-at">
        数据更新于 {{ relativeTime(summary && summary.generated_at) }}
      </div>

      <!-- 平台对比 + 待处理 -->
      <el-row :gutter="16">
        <el-col :xs="24" :lg="16">
          <el-card shadow="never" class="panel">
            <template #header>
              <div class="card-header">
                <span>平台表现</span>
                <el-button size="small" text type="primary" @click="$router.push('/analytics')">
                  详细分析
                </el-button>
              </div>
            </template>
            <el-table :data="platformRows" size="small" empty-text="还没有平台数据">
              <el-table-column label="平台" width="110">
                <template #default="{ row }">
                  <span class="platform-name">{{ row.label }}</span>
                  <span class="account-count">{{ row.accounts }}</span>
                </template>
              </el-table-column>
              <el-table-column label="粉丝" width="90" align="right">
                <template #default="{ row }">
                  <span :class="{ muted: !row.hasData }">{{ row.hasData ? fmtCount(row.fans) : '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="播放" width="90" align="right">
                <template #default="{ row }">
                  <span :class="{ muted: !row.hasData }">{{ row.hasData ? fmtCount(row.plays) : '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="互动" width="90" align="right">
                <template #default="{ row }">
                  <span :class="{ muted: !row.hasData }">{{ row.hasData ? fmtCount(row.interactions) : '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="播放对比" min-width="150">
                <template #default="{ row }">
                  <div class="bar-wrap">
                    <div
                      class="bar"
                      :style="{ width: barWidth(row), background: platformColor(row.platform) }"
                    />
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="同步" width="90" align="right">
                <template #default="{ row }">
                  <span class="muted">{{ row.syncText }}</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>

        <el-col :xs="24" :lg="8">
          <el-card shadow="never" class="panel">
            <template #header>
              <div class="card-header">
                <span>需要处理</span>
                <span v-if="alerts.length" class="sub">{{ alerts.length }} 项</span>
              </div>
            </template>

            <div v-if="!alerts.length" class="all-ok">
              <el-icon color="#67c23a"><CircleCheckFilled /></el-icon>
              <span>全部正常 · 最近同步 {{ relativeTime(latestSync) }}</span>
            </div>

            <div v-else class="alert-list">
              <div v-for="(item, i) in alerts" :key="i" class="alert-row">
                <div class="alert-main">
                  <div class="alert-title">
                    <el-icon :color="levelColor(item.level)"><WarningFilled /></el-icon>
                    <span>{{ item.label }} · {{ item.text }}</span>
                  </div>
                  <div class="alert-time">
                    最后成功：{{ item.lastSuccess || '从未' }}
                  </div>
                </div>
                <el-button size="small" type="primary" plain @click="fixAlert(item)">
                  {{ item.action }}
                </el-button>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 发布节奏 -->
      <el-card shadow="never" class="panel">
        <template #header>
          <div class="card-header">
            <span>发布节奏 <span class="sub">近 30 天</span></span>
            <span class="sub" v-if="summary">
              已发布 {{ summary.publish.last_30d }} 条 · 近 7 天 {{ summary.publish.last_7d }} 条
            </span>
          </div>
        </template>

        <div v-if="!rhythmRows.length" class="all-ok">
          <span class="muted">近 30 天没有发布记录</span>
        </div>
        <div v-else class="rhythm-list">
          <div v-for="row in rhythmRows" :key="row.platform" class="rhythm-row">
            <div class="rhythm-head">
              <span class="platform-name">{{ row.label }}</span>
              <span class="muted">
                {{ row.total }} 条
                <span v-if="row.streak" class="streak">· 连续 {{ row.streak }} 天</span>
                <span v-else-if="row.daysSinceLast != null" class="warn">
                  · {{ row.daysSinceLast }} 天未更新
                </span>
              </span>
            </div>
            <div class="rhythm-bars">
              <div
                v-for="cell in row.cells"
                :key="cell.day"
                class="rhythm-cell"
                :class="{ filled: cell.count > 0 }"
                :style="cell.count ? { background: platformColor(row.platform), opacity: 0.35 + Math.min(cell.count, 3) * 0.2 } : {}"
                :title="cell.day + ' · ' + cell.count + ' 条'"
              />
            </div>
          </div>
        </div>

        <div class="trend-hint">
          <el-icon><TrendCharts /></el-icon>
          <span v-if="summary && summary.trend_days_available < 7">
            粉丝趋势：数据积累中（已有 {{ summary.trend_days_available }} 天，满 7 天后显示曲线）
          </span>
          <span v-else>粉丝趋势已就绪</span>
        </div>
      </el-card>

      <!-- 最近任务 -->
      <el-card shadow="never" class="panel">
        <template #header>
          <div class="card-header">
            <span>最近任务</span>
            <el-button size="small" text type="primary" @click="$router.push('/publish')">
              去发布
            </el-button>
          </div>
        </template>
        <div v-if="!store.tasks.length" class="all-ok">
          <span class="muted">还没有任务</span>
        </div>
        <div v-else class="task-list">
          <div v-for="task in store.tasks.slice(0, 5)" :key="task.id" class="task-row">
            <div class="task-head">
              <span class="task-title">
                {{ store.platformLabel(task.platform) }} · {{ task.action }}
              </span>
              <el-tag size="small" :type="tagType(task.status)" effect="light">
                {{ statusLabel(task.status) }}
              </el-tag>
            </div>
            <div class="task-line mono">{{ task.last_line || '-' }}</div>
          </div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()
const router = useRouter()

const summary = ref(null)
const loaded = ref(false)

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

const onboardingSteps = [
  { title: '添加账号', desc: '扫码或导入 Cookie 登录第一个平台', action: '去登录', to: '/accounts' },
  { title: '同步数据', desc: '获取粉丝、播放与作品明细', action: '去同步', to: '/analytics' },
  { title: '发布内容', desc: '自动发布或打开官方后台手动发布', action: '去发布', to: '/publish' }
]

const platformRows = computed(() => {
  if (!summary.value) return []
  return summary.value.platforms.map((p) => {
    const hasData = p.last_sync != null
    const stale = p.stale_hours
    return {
      ...p,
      hasData,
      syncText: !hasData
        ? '从未'
        : stale != null && stale >= 24
          ? Math.floor(stale / 24) + '天前'
          : stale != null && stale >= 1
            ? Math.floor(stale) + 'h前'
            : '刚刚'
    }
  })
})

const maxPlays = computed(() =>
  Math.max(1, ...platformRows.value.map((r) => r.plays || 0))
)

function barWidth(row) {
  if (!row.hasData || !row.plays) return '0%'
  return Math.max(3, (row.plays / maxPlays.value) * 100) + '%'
}

const cards = computed(() => {
  const s = summary.value
  if (!s) return []
  const { coverage, totals, publish } = s
  const healthyAccounts = store.accounts.filter((a) => a.login_valid === true).length
  const expiredAccounts = store.accounts.filter((a) => a.login_valid === false).length
  const unchecked = store.accounts.filter((a) => a.login_valid == null).length
  const coverageText = `覆盖 ${coverage.synced}/${coverage.total} 账号`

  return [
    {
      key: 'health',
      label: '账号健康',
      value: `${healthyAccounts} / ${store.accounts.length}`,
      sub: expiredAccounts
        ? `${expiredAccounts} 个失效`
        : unchecked
          ? `${unchecked} 个未校验`
          : '全部正常',
      color: expiredAccounts ? '#f56c6c' : '#67c23a',
      hint: '登录态有效的账号数 / 总账号数',
      to: '/accounts'
    },
    {
      key: 'fans',
      label: '总粉丝',
      value: fmtCount(totals.fans),
      sub: coverageText,
      color: '#409eff',
      hint: '所有已同步账号的粉丝数之和；未同步的账号不计入',
      to: '/analytics'
    },
    {
      key: 'plays',
      label: '总播放',
      value: fmtCount(totals.plays),
      sub: coverageText,
      color: '#e6a23c',
      hint: '已同步作品播放量之和',
      to: '/analytics'
    },
    {
      key: 'interact',
      label: '总互动',
      value: fmtCount(totals.interactions),
      sub: '赞 · 评 · 转 · 藏',
      color: '#f56c6c',
      hint: '点赞 + 评论 + 转发 + 收藏',
      to: '/analytics'
    },
    {
      key: 'publish',
      label: '近 30 天发布',
      value: publish.last_30d,
      sub: `近 7 天 ${publish.last_7d} 条`,
      color: '#67c23a',
      hint: '已同步作品按发布时间统计',
      to: '/analytics'
    },
    {
      key: 'alerts',
      label: '需要处理',
      value: alerts.value.length,
      sub: alerts.value.length ? '点击查看' : '无需处理',
      color: alerts.value.length ? '#e6a23c' : '#909399',
      hint: '登录失效、数据过期或从未同步的账号'
    }
  ]
})

const alerts = computed(() => {
  if (!summary.value) return []
  return summary.value.alerts.map((item) => ({
    ...item,
    lastSuccess: item.last_success ? relativeTime(item.last_success) : ''
  }))
})

const latestSync = computed(() => {
  if (!summary.value) return null
  const times = summary.value.platforms
    .map((p) => p.last_sync)
    .filter(Boolean)
  return times.length ? Math.max(...times) : null
})

const rhythmRows = computed(() => {
  const s = summary.value
  if (!s) return []
  const days = []
  const today = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    days.push(d.toISOString().slice(0, 10))
  }

  return s.platforms
    .filter((p) => s.rhythm[p.platform])
    .map((p) => {
      const byDay = s.rhythm[p.platform] || {}
      const cells = days.map((day) => ({ day, count: byDay[day] || 0 }))
      const total = cells.reduce((sum, c) => sum + c.count, 0)

      let streak = 0
      for (let i = cells.length - 1; i >= 0; i--) {
        if (cells[i].count > 0) streak += 1
        else break
      }
      let daysSinceLast = null
      for (let i = cells.length - 1; i >= 0; i--) {
        if (cells[i].count > 0) {
          daysSinceLast = cells.length - 1 - i
          break
        }
      }
      return { platform: p.platform, label: p.label, cells, total, streak, daysSinceLast }
    })
})

function fmtCount(value) {
  if (value == null) return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toLocaleString('zh-CN')
}

function relativeTime(ts) {
  if (!ts) return '未知'
  const diff = (Date.now() / 1000) - Number(ts)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前'
  return Math.floor(diff / 86400) + ' 天前'
}

function levelColor(level) {
  return { error: '#f56c6c', warning: '#e6a23c', info: '#909399' }[level] || '#909399'
}

function fixAlert(item) {
  if (item.action === '重新登录') {
    router.push({ path: '/accounts' })
  } else {
    router.push({ path: '/analytics', query: { platform: item.platform, account: item.account } })
  }
}

function tagType(s) {
  if (s === 'success') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  return 'info'
}

function statusLabel(s) {
  return {
    success: '成功',
    failed: '失败',
    running: '执行中',
    pending: '等待中',
    cancelled: '已取消'
  }[s] || s
}

onMounted(async () => {
  await Promise.all([store.loadAccounts(), store.loadTasks()])
  try {
    summary.value = await sauApi.getAnalyticsSummary()
  } catch (error) {
    summary.value = null
  } finally {
    loaded.value = true
  }
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.stat-card {
  margin-bottom: 16px;
}
.stat-card.clickable {
  cursor: pointer;
  transition: transform 0.15s ease;
}
.stat-card.clickable:hover {
  transform: translateY(-2px);
}
.stat-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}
.hint-icon {
  font-size: 12px;
  color: #c0c4cc;
  cursor: help;
}
.stat-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-sub {
  margin-top: 4px;
  font-size: 11px;
  color: #c0c4cc;
}
.updated-at {
  margin-top: -8px;
  text-align: right;
  font-size: 11px;
  color: #c0c4cc;
}
.panel {
  height: 100%;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.card-header .sub {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}
.platform-name {
  font-size: 13px;
  color: #303133;
}
.account-count {
  margin-left: 6px;
  padding: 0 5px;
  border-radius: 8px;
  background: #f0f2f5;
  font-size: 11px;
  color: #909399;
}
.muted {
  color: #c0c4cc;
  font-size: 12px;
}
.bar-wrap {
  height: 8px;
  border-radius: 4px;
  background: #f5f7fa;
  overflow: hidden;
}
.bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

/* 待处理 */
.all-ok {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
  font-size: 13px;
  color: #606266;
}
.alert-list {
  display: flex;
  flex-direction: column;
}
.alert-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #f5f7fa;
}
.alert-row:last-child {
  border-bottom: none;
}
.alert-main {
  flex: 1;
  min-width: 0;
}
.alert-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #303133;
}
.alert-time {
  margin-top: 2px;
  margin-left: 20px;
  font-size: 11px;
  color: #c0c4cc;
}

/* 发布节奏 */
.rhythm-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.rhythm-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.streak {
  color: #67c23a;
}
.warn {
  color: #e6a23c;
}
.rhythm-bars {
  display: flex;
  gap: 3px;
}
.rhythm-cell {
  flex: 1;
  height: 18px;
  border-radius: 3px;
  background: #f5f7fa;
}
.rhythm-cell.filled {
  background: #409eff;
}
.trend-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f5f7fa;
  font-size: 12px;
  color: #909399;
}

/* 任务 */
.task-list {
  display: flex;
  flex-direction: column;
}
.task-row {
  padding: 10px 0;
  border-bottom: 1px solid #f5f7fa;
}
.task-row:last-child {
  border-bottom: none;
}
.task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.task-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.task-line {
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 空状态引导 */
.onboard {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 520px;
  margin: 0 auto;
  text-align: left;
}
.onboard-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}
.step-no {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.step-body {
  flex: 1;
}
.step-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.step-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}
.mono {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #909399;
}
</style>
