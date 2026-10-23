<template>
  <div class="publish-page">
    <el-row :gutter="16">
      <el-col :xs="24" :md="6">
        <el-card shadow="never" class="platform-card">
          <template #header>
            <div class="card-header">
              <span>选择平台</span>
              <el-input
                v-model="filter"
                size="small"
                placeholder="搜索"
                clearable
                style="width: 110px"
              />
            </div>
          </template>

          <el-scrollbar height="calc(100vh - 260px)">
            <div
              v-for="p in filteredPlatforms"
              :key="p.key"
              class="platform-item"
              :class="{ active: platform === p.key }"
              @click="selectPlatform(p.key)"
            >
              <div class="platform-name">{{ p.label }}</div>
              <div class="platform-key">{{ p.key }} · {{ p.actions.length }} 个动作</div>
            </div>
            <el-empty
              v-if="filteredPlatforms.length === 0"
              description="没有匹配的平台"
              :image-size="60"
            />
          </el-scrollbar>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="18">
        <el-card shadow="never" v-loading="store.schemaLoading">
          <template #header>
            <div class="card-header">
              <div>
                <span class="title">{{
                  currentPlatform ? currentPlatform.label : '请选择平台'
                }}</span>
                <span v-if="currentPlatform" class="sub">{{
                  currentPlatform.help || currentPlatform.key
                }}</span>
              </div>
              <div class="header-actions">
                <el-button size="small" @click="refreshSchema" :loading="store.schemaLoading">
                  刷新参数
                </el-button>
                <el-button size="small" type="primary" plain @click="openLogin" :disabled="!platform">
                  去登录
                </el-button>
              </div>
            </div>
          </template>

          <template v-if="currentPlatform">
            <el-radio-group v-model="action" class="action-group" @change="selectAction">
              <el-radio-button v-for="a in currentPlatform.actions" :key="a" :value="a">
                {{ actionLabel(a) }}
              </el-radio-button>
            </el-radio-group>

            <el-alert
              v-if="actionHint"
              :title="actionHint"
              type="info"
              :closable="false"
              show-icon
              class="action-hint"
            />

            <el-divider />

            <DynamicForm
              v-if="fields.length"
              :fields="fields"
              :model-value="values"
              :errors="errors"
              :materials="materialsForForm"
              :accounts="accountsForForm"
              @update:model-value="onValuesChange"
            />
            <el-empty v-else description="该动作没有可填写的参数" :image-size="60" />

            <div class="submit-bar">
              <el-button @click="resetValues">重置</el-button>
              <el-button type="primary" :loading="submitting" @click="submit">
                执行 {{ currentPlatform.label }} / {{ actionLabel(action) }}
              </el-button>
            </div>

            <div v-if="lastArgv.length" class="cmd-preview">
              <span class="cmd-label">等价命令</span>
              <code>{{ lastArgv.join(' ') }}</code>
            </div>
          </template>
          <el-empty v-else description="从左侧选择一个平台开始" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="task-card">
      <template #header>
        <div class="card-header">
          <span>任务记录</span>
          <div class="header-actions">
            <el-button size="small" @click="store.loadTasks()" :loading="store.tasksLoading">
              刷新
            </el-button>
            <el-button size="small" type="danger" plain @click="clearTasks">清空已结束</el-button>
          </div>
        </div>
      </template>

      <el-table :data="store.tasks" size="small" empty-text="还没有任务" @row-click="openTask">
        <el-table-column prop="platform" label="平台" width="110">
          <template #default="{ row }">{{ store.platformLabel(row.platform) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="150" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="dark">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">{{ duration(row) }}</template>
        </el-table-column>
        <el-table-column label="最后输出" min-width="260">
          <template #default="{ row }">
            <span class="last-line">{{ row.last_line || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click.stop="openTask(row)">日志</el-button>
            <el-button
              size="small"
              text
              type="danger"
              :disabled="row.status !== 'running'"
              @click.stop="cancelTask(row)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawer" :title="drawerTitle" size="60%" @closed="stopPolling">
      <div v-if="currentTask" class="drawer-body">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(currentTask.status)" size="small" effect="dark">
              {{ statusText(currentTask.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="退出码">{{ currentTask.exit_code ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ duration(currentTask) }}</el-descriptions-item>
        </el-descriptions>

        <div class="cmd-preview">
          <span class="cmd-label">命令</span>
          <code>{{ (currentTask.argv || []).join(' ') }}</code>
        </div>

        <el-input
          type="textarea"
          :rows="22"
          readonly
          class="log-box"
          :model-value="(currentTask.logs || []).join('\n')"
        />
      </div>
    </el-drawer>

    <LoginDialog v-model="loginVisible" :default-platform="platform" @success="onLoginSuccess" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DynamicForm from '@/components/DynamicForm.vue'
import LoginDialog from '@/components/LoginDialog.vue'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()

const filter = ref('')
const platform = ref('')
const action = ref('')
const values = ref({})
const errors = ref({})
const submitting = ref(false)
const lastArgv = ref([])

const drawer = ref(false)
const currentTask = ref(null)
let timer = null

const loginVisible = ref(false)

const filteredPlatforms = computed(() => {
  const kw = filter.value.trim().toLowerCase()
  if (!kw) return store.platforms
  return store.platforms.filter(
    (p) => p.key.toLowerCase().includes(kw) || p.label.toLowerCase().includes(kw)
  )
})

const currentPlatform = computed(() => store.platformMap[platform.value] || null)

const currentActionSchema = computed(() => {
  if (!platform.value || !action.value) return null
  return store.actionSchema(platform.value, action.value)
})

const fields = computed(() => (currentActionSchema.value ? currentActionSchema.value.fields : []))

const actionHint = computed(() => {
  const p = currentPlatform.value
  if (!p) return ''
  return p.help || ''
})

const materialsForForm = computed(() =>
  store.materials.map((m) => ({
    name: m.name,
    path: m.path || m.name,
    size_text: m.size_text,
    kind: m.kind
  }))
)

const accountsForForm = computed(() =>
  platform.value ? store.accountsFor(platform.value) : []
)

const ACTION_LABELS = {
  login: '登录',
  check: '校验账号',
  verify: '校验作品',
  delete: '删除作品',
  'upload-video': '发布视频',
  'upload-note': '发布图文',
  'upload-article': '发布文章',
  themes: '主题列表',
  setup: '初始化',
  render: '渲染',
  download: '下载'
}

function actionLabel(a) {
  return ACTION_LABELS[a] || a
}

function statusText(s) {
  return (
    {
      pending: '排队中',
      running: '执行中',
      success: '成功',
      failed: '失败',
      cancelled: '已取消'
    }[s] || s
  )
}

function statusType(s) {
  if (s === 'success') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  return 'info'
}

function duration(row) {
  if (!row) return '-'
  if (!row.started_at) return '-'
  const end = row.finished_at || Date.now() / 1000
  const secs = Math.max(0, Math.round(end - row.started_at))
  if (secs < 60) return secs + 's'
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return m + 'm' + s + 's'
}

function selectPlatform(key) {
  platform.value = key
  const p = store.platformMap[key]
  if (p && p.actions.length) {
    selectAction(p.actions.includes('upload-video') ? 'upload-video' : p.actions[0])
  } else {
    action.value = ''
    values.value = {}
  }
}

function selectAction(name) {
  action.value = name
  errors.value = {}
  const schema = store.actionSchema(platform.value, name)
  const next = {}
  if (schema && schema.fields) {
    for (const f of schema.fields) {
      if (f.kind === 'bool') {
        next[f.dest] = Boolean(f.default)
      } else if (f.default !== null && f.default !== undefined) {
        next[f.dest] = f.default
      }
    }
  }
  const candidates = store.accountsFor(platform.value)
  if (candidates.length && !next.account) {
    next.account = candidates[0].account
  }
  values.value = next
  lastArgv.value = []
}

function onValuesChange(next) {
  values.value = next
  errors.value = {}
}

function resetValues() {
  selectAction(action.value)
}

async function refreshSchema() {
  await store.loadSchema(true)
  ElMessage.success('参数结构已刷新')
}

function openLogin() {
  if (!platform.value) {
    ElMessage.warning('请先选择平台')
    return
  }
  loginVisible.value = true
}

async function onLoginSuccess() {
  await store.loadAccounts()
  selectAction(action.value)
}

async function submit() {
  if (!platform.value || !action.value) return
  errors.value = {}
  submitting.value = true
  try {
    const payload = cleanValues(values.value)
    const task = await sauApi.createTask(platform.value, action.value, payload)
    lastArgv.value = task.argv || []
    ElMessage.success('任务已提交：' + task.id)
    await store.loadTasks()
    watchTask(task.id)
  } catch (e) {
    if (e.message) ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

function cleanValues(raw) {
  const out = {}
  for (const [k, v] of Object.entries(raw || {})) {
    if (v === null || v === undefined || v === '') continue
    if (Array.isArray(v) && v.length === 0) continue
    out[k] = v
  }
  return out
}

async function clearTasks() {
  try {
    await ElMessageBox.confirm('清空所有已结束的任务记录？', '确认', { type: 'warning' })
  } catch {
    return
  }
  await sauApi.clearTasks()
  await store.loadTasks()
}

async function cancelTask(row) {
  try {
    await sauApi.cancelTask(row.id)
    ElMessage.info('已请求取消')
    await store.loadTasks()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function openTask(row) {
  currentTask.value = row
  drawer.value = true
  sauApi.getTask(row.id).then((data) => {
    currentTask.value = data
  })
  startPolling(row.id)
}

function watchTask(id) {
  const row = store.tasks.find((t) => t.id === id)
  if (row) openTask(row)
}

function startPolling(id) {
  stopPolling()
  timer = setInterval(async () => {
    try {
      const data = await sauApi.getTask(id)
      currentTask.value = data
      if (['success', 'failed', 'cancelled'].includes(data.status)) {
        stopPolling()
        await store.loadTasks()
      }
    } catch {
      stopPolling()
    }
  }, 1500)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

const drawerTitle = computed(() => {
  if (!currentTask.value) return '任务日志'
  return (
    store.platformLabel(currentTask.value.platform) +
    ' / ' +
    currentTask.value.action +
    ' · ' +
    currentTask.value.id
  )
})

onMounted(async () => {
  await store.loadSchema()
  await Promise.all([store.loadAccounts(), store.loadMaterials(), store.loadTasks()])
  if (store.platforms.length) {
    selectPlatform(store.platforms[0].key)
  }
})

onBeforeUnmount(stopPolling)

watch(
  () => store.accounts,
  () => {
    if (platform.value && action.value && !values.value.account) {
      const list = store.accountsFor(platform.value)
      if (list.length) values.value.account = list[0].account
    }
  },
  { deep: true }
)
</script>

<style scoped>
.publish-page {
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
.platform-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.platform-item:hover {
  background: #f5f7fa;
}
.platform-item.active {
  background: #ecf5ff;
  border-color: #409eff;
}
.platform-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.platform-key {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}
.action-group {
  margin-bottom: 12px;
}
.action-hint {
  margin-bottom: 8px;
}
.submit-bar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
.cmd-preview {
  margin-top: 12px;
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 12px;
  color: #606266;
  word-break: break-all;
}
.cmd-label {
  display: inline-block;
  margin-right: 8px;
  color: #909399;
}
.task-card {
  margin-top: 4px;
}
.last-line {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #606266;
}
.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.log-box :deep(textarea) {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  background: #1e1e1e;
  color: #d4d4d4;
}
</style>
