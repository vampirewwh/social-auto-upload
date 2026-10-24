<template>
  <div class="analytics">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span class="title">账号数据分析</span>
            <span class="sub">共 {{ store.accounts.length }} 个账号</span>
          </div>
          <el-button size="small" @click="openSchedule">自动同步设置</el-button>
        </div>
      </template>

      <el-tabs
        v-if="store.accounts.length"
        v-model="activeTab"
        type="border-card"
        class="account-tabs"
      >
        <el-tab-pane
          v-for="row in store.accounts"
          :key="row.platform + '/' + row.account"
          :name="row.platform + '/' + row.account"
        >
          <template #label>
            <span class="tab-label">
              <el-avatar
                :src="row.avatar || undefined"
                :size="20"
                :style="{ background: platformColor(row.platform) }"
              >
                {{ (row.label || '?').charAt(0) }}
              </el-avatar>
              <span class="tab-name">{{ row.nickname || row.account }}</span>
              <el-tag size="small" :type="statusType(row)" effect="light" class="tab-status">
                {{ statusText(row) }}
              </el-tag>
            </span>
          </template>
          <AccountDataPanel
            v-if="activeTab === row.platform + '/' + row.account"
            :platform="row.platform"
            :account="row.account"
            :account-meta="row"
          />
        </el-tab-pane>
      </el-tabs>
      <el-empty v-else description="还没有账号，先去账号管理登录" :image-size="80" />
    </el-card>

    <el-dialog v-model="scheduleVisible" title="每日自动同步" width="480px">
      <el-form label-width="90px">
        <el-form-item label="启用">
          <el-switch v-model="schedule.enabled" />
        </el-form-item>
        <el-form-item label="同步时间">
          <el-time-picker
            v-model="schedule.time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="08:30"
            :disabled="!schedule.enabled"
          />
        </el-form-item>
        <el-form-item label="同步账号">
          <el-select
            v-model="scheduleAccounts"
            multiple
            placeholder="不选则同步全部抖音账号"
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
      <div class="hint">自动同步在 Web 服务进程内运行，需要保持服务启动。</div>
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AccountDataPanel from '@/components/AccountDataPanel.vue'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()
const route = useRoute()
const router = useRouter()

const activeTab = ref('')

const scheduleVisible = ref(false)
const scheduleSaving = ref(false)
const schedule = ref({ enabled: false, time: '08:30', last_run_date: '' })
const scheduleAccounts = ref([])

const douyinAccounts = computed(() =>
  store.accounts.filter((item) => item.platform === 'douyin')
)

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

function keyOf(row) {
  return row.platform + '/' + row.account
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

// 从 URL 选中账号（账号管理页跳转时带 platform/account）
function applyRouteSelection() {
  const platform = route.query.platform && String(route.query.platform)
  const account = route.query.account && String(route.query.account)
  if (platform && account) {
    const key = platform + '/' + account
    if (store.accounts.some((row) => keyOf(row) === key)) {
      activeTab.value = key
      return
    }
  }
  if (!activeTab.value && store.accounts.length) {
    activeTab.value = keyOf(store.accounts[0])
  }
}

watch(
  () => [route.query.platform, route.query.account],
  () => applyRouteSelection()
)

onMounted(async () => {
  await Promise.all([store.loadSchema(), store.loadAccounts()])
  applyRouteSelection()
  await loadSchedule()
})

watch(activeTab, (name) => {
  if (!name) return
  const [platform, ...rest] = name.split('/')
  const account = rest.join('/')
  if (route.query.platform === platform && route.query.account === account) return
  router.replace({ query: { platform, account } })
})
</script>

<style scoped>
.analytics {
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
.title {
  font-weight: 600;
  font-size: 15px;
}
.sub {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}
.muted {
  font-size: 12px;
  color: #909399;
}
.hint {
  font-size: 12px;
  color: #909399;
}
/* 账号 tab */
.account-tabs {
  box-shadow: none;
}
.account-tabs :deep(.el-tabs__header) {
  background: #fafbfc;
  margin-bottom: 16px;
}
.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.tab-name {
  font-size: 13px;
  font-weight: 500;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tab-status {
  transform: scale(0.9);
}
</style>
