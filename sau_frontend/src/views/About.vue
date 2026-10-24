<template>
  <div class="about-page">
    <!-- 顶部：品牌 + 关键信息 -->
    <el-card shadow="never" class="hero">
      <div class="hero-inner">
        <div class="hero-brand">
          <div class="logo">SAU</div>
          <div class="hero-text">
            <div class="hero-title">
              social-auto-upload
              <el-tag size="small" type="success" effect="plain" class="version">v2</el-tag>
            </div>
            <div class="hero-sub">多平台自媒体发布与数据分析控制台</div>
          </div>
        </div>
        <div class="hero-stats">
          <div class="hero-stat">
            <b>{{ store.platforms.length }}</b>
            <span>支持平台</span>
          </div>
          <div class="hero-stat">
            <b>{{ store.accounts.length }}</b>
            <span>已登录账号</span>
          </div>
          <div class="hero-stat">
            <b>{{ supportedActions }}</b>
            <span>可用动作</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16">
      <!-- 运行环境 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="card-header">
              <span class="panel-title">运行环境</span>
            </div>
          </template>
          <div class="info-list">
            <div class="info-row">
              <span class="info-label">后端入口</span>
              <span class="info-value mono">sau_server.py</span>
            </div>
            <div class="info-row">
              <span class="info-label">CLI 入口</span>
              <span class="info-value mono">sau_cli.py</span>
            </div>
            <div class="info-row">
              <span class="info-label">程序目录</span>
              <span class="info-value mono path" :title="health.root">
                {{ health.root || '-' }}
              </span>
            </div>
            <div class="info-row">
              <span class="info-label">数据目录</span>
              <span class="info-value mono path" :title="currentDataDir">
                {{ currentDataDir }}
              </span>
              <el-tag v-if="dataDir.is_custom" size="small" type="success" effect="plain">
                自定义
              </el-tag>
              <el-button size="small" text type="primary" @click="openDataDir">
                修改
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 工作原理 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="card-header">
              <span class="panel-title">工作原理</span>
            </div>
          </template>
          <div class="workflow">
            <div class="flow-step" v-for="(step, i) in workflow" :key="i">
              <span class="flow-no">{{ i + 1 }}</span>
              <div class="flow-body">
                <div class="flow-title">{{ step.title }}</div>
                <div class="flow-desc">{{ step.desc }}</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据目录说明 -->
    <el-card shadow="never" class="panel">
      <template #header>
        <div class="card-header">
          <span class="panel-title">数据目录</span>
          <el-button size="small" @click="openDataDir">修改目录</el-button>
        </div>
      </template>
      <el-alert type="info" :closable="false" show-icon class="dir-alert">
        <template #title>
          <span class="mono">{{ currentDataDir }}</span>
        </template>
        <div class="dir-desc">
          账号 cookie、数据库、素材和日志都存放在这里。修改后需要重启服务生效，已有数据不会自动迁移，请自行拷贝。
        </div>
      </el-alert>
      <div class="dir-items">
        <div class="dir-item" v-for="item in dataDirs" :key="item.name">
          <el-icon><FolderOpened /></el-icon>
          <span class="dir-name mono">{{ item.name }}/</span>
          <span class="dir-desc-text">{{ item.desc }}</span>
        </div>
      </div>
    </el-card>

    <!-- 平台与动作 -->
    <el-card shadow="never" class="panel">
      <template #header>
        <div class="card-header">
          <span class="panel-title">
            支持的平台
            <span class="sub">共 {{ store.platforms.length }} 个，每个平台可用的操作如下</span>
          </span>
          <el-input
            v-model="platformKeyword"
            placeholder="搜索平台"
            clearable
            size="small"
            class="search"
          />
        </div>
      </template>
      <div class="platform-grid">
        <div
          v-for="row in filteredPlatforms"
          :key="row.key"
          class="platform-card"
        >
          <div class="platform-head">
            <span class="platform-label">{{ row.label }}</span>
            <span class="platform-key mono">{{ row.key }}</span>
          </div>
          <div class="platform-actions">
            <el-tooltip
              v-for="a in row.actions"
              :key="a"
              :content="actionLabel(a) + ' · ' + (actionDesc[a] || '')"
              placement="top"
            >
              <span class="action-pill">
                {{ actionLabel(a) }}
                <em class="action-key">{{ a }}</em>
              </span>
            </el-tooltip>
          </div>
        </div>
      </div>
      <el-empty
        v-if="!filteredPlatforms.length"
        description="没有匹配的平台"
        :image-size="60"
      />
    </el-card>

    <!-- 命令行用法 -->
    <el-card shadow="never" class="panel">
      <template #header>
        <div class="card-header">
          <span class="panel-title">命令行用法</span>
          <el-button size="small" text type="primary" @click="copyCommands">
            复制示例
          </el-button>
        </div>
      </template>
      <pre class="cmd">{{ commandExamples }}</pre>
    </el-card>

    <el-dialog v-model="dataDirVisible" title="修改数据目录" width="520px">
      <el-form label-position="top">
        <el-form-item label="数据目录路径">
          <el-input v-model="dataDirInput" placeholder="例如 D:\sau-data" />
        </el-form-item>
      </el-form>
      <div class="dialog-hint">
        将存放 cookies/、db/、videos/、logs/。保存后需重启服务生效。
      </div>
      <template #footer>
        <el-button @click="dataDirVisible = false">取消</el-button>
        <el-button type="primary" :loading="dataDirSaving" @click="saveDataDir">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()
const health = ref({})
const dataDir = ref({})
const dataDirVisible = ref(false)
const dataDirInput = ref('')
const dataDirSaving = ref(false)
const platformKeyword = ref('')

const currentDataDir = computed(
  () => dataDir.value.data_dir || health.value.data_dir || '-'
)

const supportedActions = computed(() =>
  new Set(store.platforms.flatMap((p) => p.actions || [])).size
)

const filteredPlatforms = computed(() => {
  const kw = platformKeyword.value.trim().toLowerCase()
  if (!kw) return store.platforms
  return store.platforms.filter(
    (p) =>
      p.label.toLowerCase().includes(kw) || p.key.toLowerCase().includes(kw)
  )
})

const workflow = [
  { title: '读取 CLI 定义', desc: '后端解析 sau_cli 的 argparse，生成 /api/schema' },
  { title: '自动渲染表单', desc: '前端按字段类型生成控件，新增参数无需改界面' },
  { title: '子进程执行', desc: '表单拼回命令行，独立进程运行 python -m sau_cli' },
  { title: '实时日志', desc: '轮询子进程输出，可随时取消任务' }
]

// CLI 动作的中文名与说明，避免直接暴露英文命令
const ACTION_NAMES = {
  check: '校验登录',
  login: '登录账号',
  delete: '删除作品',
  verify: '查询作品',
  'upload-video': '发布视频',
  'upload-note': '发布图文',
  'upload-article': '发布文章',
  render: '渲染文章',
  setup: '安装依赖',
  themes: '列出主题'
}

const actionDesc = {
  check: '检测账号登录态是否有效',
  login: '扫码或浏览器登录，保存 cookie',
  delete: '删除已发布的作品',
  verify: '确认作品是否发布成功',
  'upload-video': '上传并发布一条视频',
  'upload-note': '上传图片并发布图文',
  'upload-article': '上传长文并发布',
  render: '把 Markdown 文章渲染成 HTML',
  setup: '安装文章渲染所需的 Node 依赖',
  themes: '查看可用的文章排版主题'
}

function actionLabel(action) {
  return ACTION_NAMES[action] || action
}

const dataDirs = [
  { name: 'cookies', desc: '账号登录态，每个平台每个账号一个 JSON' },
  { name: 'db', desc: 'SQLite 数据库，含账号快照、作品与登录校验状态' },
  { name: 'videos', desc: '待发布的视频与图片素材' },
  { name: 'logs', desc: '服务运行日志' }
]

const commandExamples = computed(() => {
  const dir = health.value.root || '<项目目录>'
  const exe = `${dir}\\.venv\\Scripts\\sau.exe`
  return `cd ${dir}

# 登录账号
${exe} douyin login --account creator

# 校验登录态
${exe} douyin check --account creator

# 发布视频
${exe} douyin upload-video --account creator --file videos\\demo.mp4 --title "标题" --desc "简介"`
})

async function loadDataDir() {
  try {
    dataDir.value = await sauApi.getDataDir()
  } catch {
    dataDir.value = {}
  }
}

function openDataDir() {
  dataDirInput.value = currentDataDir.value
  dataDirVisible.value = true
}

async function saveDataDir() {
  const path = dataDirInput.value.trim()
  if (!path) {
    ElMessage.warning('请填写目录路径')
    return
  }
  dataDirSaving.value = true
  try {
    const result = await sauApi.setDataDir(path)
    dataDirVisible.value = false
    ElMessage.success('已保存到 ' + result.data_dir + '，重启服务后生效')
    await loadDataDir()
  } catch (error) {
    // 错误提示由请求拦截器统一弹出
  } finally {
    dataDirSaving.value = false
  }
}

async function copyCommands() {
  try {
    await navigator.clipboard.writeText(commandExamples.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选中复制')
  }
}

onMounted(async () => {
  await Promise.all([store.loadSchema(), store.loadAccounts(), loadDataDir()])
  try {
    health.value = await sauApi.getHealth()
  } catch {
    health.value = {}
  }
})
</script>

<style scoped>
.about-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.mono {
  font-family: Consolas, Monaco, monospace;
}

/* 顶部品牌区 */
.hero-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}
.hero-brand {
  display: flex;
  align-items: center;
  gap: 16px;
}
.logo {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.hero-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}
.version {
  transform: scale(0.9);
}
.hero-sub {
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
}
.hero-stats {
  display: flex;
  gap: 32px;
}
.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.hero-stat b {
  font-size: 22px;
  font-weight: 700;
  color: #409eff;
}
.hero-stat span {
  font-size: 12px;
  color: #909399;
}

/* 面板 */
.panel {
  height: 100%;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.panel-title .sub {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

/* 运行环境 */
.info-list {
  display: flex;
  flex-direction: column;
}
.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid #f5f7fa;
  font-size: 13px;
}
.info-row:last-child {
  border-bottom: none;
}
.info-label {
  flex-shrink: 0;
  width: 72px;
  color: #909399;
}
.info-value {
  flex: 1;
  min-width: 0;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.info-value.path {
  font-size: 12px;
  color: #606266;
}

/* 工作原理 */
.workflow {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.flow-step {
  display: flex;
  gap: 12px;
}
.flow-no {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.flow-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.flow-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}

/* 数据目录 */
.dir-alert {
  margin-bottom: 12px;
}
.dir-desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
}
.dir-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 24px;
}
.dir-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
}
.dir-name {
  font-weight: 600;
  color: #303133;
  font-size: 12px;
}
.dir-desc-text {
  color: #909399;
}

/* 平台栅格 */
.search {
  width: 180px;
}
.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
.platform-card {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.platform-card:hover {
  border-color: #c6e2ff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.08);
}
.platform-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.platform-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.platform-key {
  font-size: 11px;
  color: #c0c4cc;
}
.platform-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.action-pill {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 2px 8px;
  border: 1px solid #d9ecff;
  border-radius: 11px;
  background: #f4f9ff;
  font-size: 12px;
  color: #409eff;
  cursor: help;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.action-pill:hover {
  background: #ecf5ff;
  border-color: #a0cfff;
}
.action-key {
  font-style: normal;
  font-size: 10px;
  color: #a8c6e8;
}

/* 命令行 */
.cmd {
  margin: 0;
  padding: 16px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.8;
  font-family: Consolas, Monaco, monospace;
  overflow-x: auto;
}
.dialog-hint {
  font-size: 12px;
  color: #909399;
}
</style>
