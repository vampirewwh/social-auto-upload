<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand">
        <el-icon :size="22" color="#409eff"><Promotion /></el-icon>
        <span class="brand-name">SAU 自媒体自动化</span>
        <el-tag size="small" effect="plain" type="success">v2</el-tag>
      </div>

      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        :ellipsis="false"
        class="nav"
        @select="onSelect"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>总览</span>
        </el-menu-item>
        <el-menu-item index="/publish">
          <el-icon><Upload /></el-icon>
          <span>发布中心</span>
        </el-menu-item>
        <el-menu-item index="/accounts">
          <el-icon><User /></el-icon>
          <span>账号管理</span>
        </el-menu-item>
        <el-menu-item index="/analytics">
          <el-icon><TrendCharts /></el-icon>
          <span>数据分析</span>
        </el-menu-item>
        <el-menu-item index="/materials">
          <el-icon><FolderOpened /></el-icon>
          <span>素材管理</span>
        </el-menu-item>
        <el-menu-item index="/about">
          <el-icon><InfoFilled /></el-icon>
          <span>关于</span>
        </el-menu-item>
      </el-menu>

      <div class="health" :title="healthText">
        <span class="dot" :class="online ? 'ok' : 'bad'"></span>
        <span class="health-text">{{ online ? '服务正常' : '服务离线' }}</span>
      </div>
    </el-header>

    <el-main class="main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </el-main>
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import sauApi from '@/api/sau'

const route = useRoute()
const router = useRouter()

const online = ref(false)
const healthText = ref('')

const activeMenu = computed(() => route.path)

function onSelect(index) {
  if (index !== route.path) router.push(index)
}

async function probe() {
  try {
    const data = await sauApi.getHealth()
    online.value = !!data.ok
    healthText.value = '后端工作目录：' + (data.root || '-')
  } catch (e) {
    online.value = false
    healthText.value = '无法连接后端：' + e.message
  }
}

onMounted(probe)
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 56px;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  position: sticky;
  top: 0;
  z-index: 100;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: #303133;
}
.nav {
  flex: 1;
  border-bottom: none;
  min-width: 0;
}
.nav :deep(.el-menu-item) {
  height: 56px;
  line-height: 56px;
}
.health {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  font-size: 12px;
  color: #909399;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c0c4cc;
}
.dot.ok {
  background: #67c23a;
  box-shadow: 0 0 0 3px rgba(103, 194, 58, 0.15);
}
.dot.bad {
  background: #f56c6c;
  box-shadow: 0 0 0 3px rgba(245, 108, 108, 0.15);
}
.main {
  padding: 16px 20px 32px;
  background: #f2f3f5;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
