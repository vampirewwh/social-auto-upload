<template>
  <div class="dashboard">
    <el-row :gutter="16">
      <el-col :xs="12" :sm="6" v-for="card in cards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
          <div class="stat-sub">{{ card.sub }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>平台支持</span>
              <span class="sub">共 {{ store.platforms.length }} 个平台</span>
            </div>
          </template>
          <el-table :data="store.platforms" size="small" max-height="320">
            <el-table-column prop="label" label="中文名" width="110" />
            <el-table-column prop="key" label="命令" width="120" />
            <el-table-column label="可用动作">
              <template #default="{ row }">
                <el-tag
                  v-for="a in row.actions"
                  :key="a"
                  size="small"
                  effect="plain"
                  class="action-tag"
                >
                  {{ a }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>最近任务</span>
              <el-button size="small" text type="primary" @click="$router.push('/publish')">
                去发布
              </el-button>
            </div>
          </template>
          <el-table :data="store.tasks.slice(0, 8)" size="small" empty-text="还没有任务">
            <el-table-column label="平台" width="100">
              <template #default="{ row }">{{ store.platformLabel(row.platform) }}</template>
            </el-table-column>
            <el-table-column prop="action" label="动作" width="130" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="tagType(row.status)" effect="dark">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="最后输出" min-width="200">
              <template #default="{ row }">
                <span class="mono">{{ row.last_line || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>快速开始</span>
        </div>
      </template>
      <el-steps :active="4" align-center>
        <el-step title="登录账号" description="扫码或浏览器登录，登录态存到 cookies/" />
        <el-step title="上传素材" description="视频 / 封面放入 videos/" />
        <el-step title="选择平台" description="发布中心里挑平台与动作" />
        <el-step title="执行并查看日志" description="任务以子进程运行，实时输出" />
      </el-steps>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()

const cards = computed(() => {
  const running = store.tasks.filter((t) => t.status === 'running').length
  const success = store.tasks.filter((t) => t.status === 'success').length
  const failed = store.tasks.filter((t) => t.status === 'failed').length
  return [
    {
      label: '已登录账号',
      value: store.accounts.length,
      color: '#409eff',
      sub: store.accounts.length ? 'cookies/ 已就绪' : '还没有登录任何平台'
    },
    {
      label: '可用素材',
      value: store.materials.length,
      color: '#67c23a',
      sub: 'videos/ 目录'
    },
    {
      label: '执行中任务',
      value: running,
      color: '#e6a23c',
      sub: '子进程运行中'
    },
    {
      label: '成功 / 失败',
      value: success + ' / ' + failed,
      color: failed ? '#f56c6c' : '#67c23a',
      sub: '本进程内的任务统计'
    }
  ]
})

function tagType(s) {
  if (s === 'success') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'warning'
  return 'info'
}

onMounted(async () => {
  await store.loadSchema()
  await Promise.all([store.loadAccounts(), store.loadMaterials(), store.loadTasks()])
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
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-header .sub {
  font-size: 12px;
  color: #909399;
}
.action-tag {
  margin: 0 4px 4px 0;
}
.mono {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #606266;
}
</style>
