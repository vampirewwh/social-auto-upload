<template>
  <div class="material-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span class="title">素材管理</span>
            <span class="sub">共 {{ store.materials.length }} 个文件，来自 videos/ 目录</span>
          </div>
          <div class="header-actions">
            <el-button size="small" @click="store.loadMaterials()" :loading="store.materialsLoading">
              刷新
            </el-button>
            <el-button size="small" type="primary" :loading="uploading" @click="pickFile">
              上传素材
            </el-button>
            <input
              ref="fileInput"
              type="file"
              multiple
              style="display: none"
              @change="onFilesSelected"
            />
          </div>
        </div>
      </template>

      <div v-loading="store.materialsLoading">
        <el-row :gutter="16" v-if="store.materials.length">
          <el-col
            v-for="item in store.materials"
            :key="item.name"
            :xs="12"
            :sm="8"
            :md="6"
            :lg="4"
          >
            <el-card shadow="hover" class="material-card">
              <div class="thumb" @click="preview(item)">
                <img v-if="item.kind === 'image'" :src="sauApi.materialPreviewUrl(item.name)" :alt="item.name" />
                <div v-else class="video-thumb">
                  <el-icon :size="34"><VideoCamera /></el-icon>
                  <span>视频</span>
                </div>
              </div>
              <div class="meta">
                <div class="name" :title="item.name">{{ item.name }}</div>
                <div class="size">{{ item.size_text }}</div>
              </div>
              <div class="ops">
                <el-button size="small" text type="primary" @click="copyName(item)">复制名</el-button>
                <el-button size="small" text type="danger" @click="remove(item)">删除</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-else description="还没有素材，点右上角上传" />
      </div>
    </el-card>

    <el-dialog v-model="previewVisible" :title="previewItem ? previewItem.name : ''" width="720px">
      <div v-if="previewItem" class="preview-box">
        <img
          v-if="previewItem.kind === 'image'"
          :src="sauApi.materialPreviewUrl(previewItem.name)"
          :alt="previewItem.name"
        />
        <video
          v-else
          :src="sauApi.materialPreviewUrl(previewItem.name)"
          controls
          style="width: 100%"
        />
      </div>
    </el-dialog>

    <el-progress
      v-if="uploading"
      :percentage="progress"
      :stroke-width="14"
      text-inside
      class="progress-bar"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoCamera } from '@element-plus/icons-vue'
import sauApi from '@/api/sau'
import { useSauStore } from '@/stores/sau'

const store = useSauStore()

const fileInput = ref(null)
const uploading = ref(false)
const progress = ref(0)
const previewVisible = ref(false)
const previewItem = ref(null)

function pickFile() {
  if (fileInput.value) fileInput.value.click()
}

async function onFilesSelected(ev) {
  const files = Array.from(ev.target.files || [])
  if (!files.length) return
  uploading.value = true
  progress.value = 0
  let done = 0
  for (const file of files) {
    try {
      await sauApi.uploadMaterial(file, (e) => {
        if (e.total) {
          const base = (done / files.length) * 100
          progress.value = Math.round(base + (e.loaded / e.total) * (100 / files.length))
        }
      })
      done += 1
    } catch (err) {
      ElMessage.error(file.name + ' 上传失败：' + err.message)
    }
  }
  uploading.value = false
  progress.value = 0
  ev.target.value = ''
  await store.loadMaterials()
  if (done) ElMessage.success('已上传 ' + done + ' 个文件')
}

function preview(item) {
  previewItem.value = item
  previewVisible.value = true
}

async function copyName(item) {
  try {
    await navigator.clipboard.writeText(item.name)
    ElMessage.success('已复制文件名')
  } catch {
    ElMessage.warning('浏览器不允许访问剪贴板，请手动复制')
  }
}

async function remove(item) {
  try {
    await ElMessageBox.confirm('删除文件 ' + item.name + '？', '确认', { type: 'warning' })
  } catch {
    return
  }
  await sauApi.deleteMaterial(item.name)
  ElMessage.success('已删除')
  await store.loadMaterials()
}

onMounted(store.loadMaterials)
</script>

<style scoped>
.material-page {
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
.material-card {
  margin-bottom: 16px;
}
.thumb {
  height: 110px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
}
.thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.video-thumb {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: #909399;
  font-size: 12px;
}
.meta {
  margin-top: 8px;
}
.meta .name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta .size {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}
.ops {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}
.preview-box {
  text-align: center;
}
.preview-box img {
  max-width: 100%;
  max-height: 70vh;
}
.progress-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
}
</style>
