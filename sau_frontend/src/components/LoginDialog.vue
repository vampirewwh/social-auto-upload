<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="520px"
    :close-on-click-modal="false"
    @closed="cleanup"
  >
    <el-form label-position="top">
      <el-form-item label="平台">
        <el-select v-model="platform" style="width: 100%" @change="reset">
          <el-option
            v-for="p in platformOptions"
            :key="p.platform"
            :label="p.label"
            :value="p.platform"
          >
            <span>{{ p.label }}</span>
            <span class="opt-tag">{{ p.mode === 'qrcode' ? '二维码' : '浏览器' }}</span>
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="账号名称（自定义标识）" required>
        <el-input v-model="account" placeholder="例如 creator" @input="reset" />
      </el-form-item>
      <el-form-item label="显示浏览器窗口">
        <el-switch v-model="headless" :active-value="false" :inactive-value="true" />
        <span class="hint">{{ modeHint }}</span>
      </el-form-item>
    </el-form>

    <div v-if="status" class="status-box">
      <el-tag :type="statusType" effect="dark">{{ statusText }}</el-tag>
      <span class="status-msg">{{ message }}</span>
    </div>

    <div v-if="qrcode" class="qrcode-box">
      <img :src="qrcode" alt="登录二维码" />
      <p class="qrcode-tip">请用对应 App 扫码，登录成功后窗口会自动关闭</p>
    </div>

    <div v-else-if="status === 'waiting'" class="waiting-box">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>请在弹出的浏览器窗口中完成登录...</span>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" :loading="starting" :disabled="!platform || !account" @click="start">
        开始登录
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import sauApi from '@/api/sau'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  defaultPlatform: { type: String, default: 'douyin' }
})
const emit = defineEmits(['update:modelValue', 'success'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const platformOptions = ref([])
const platform = ref(props.defaultPlatform)
const account = ref('')
const headless = ref(true)
const starting = ref(false)
const status = ref('')
const message = ref('')
const qrcode = ref('')
let source = null

const dialogTitle = computed(() => '扫码 / 浏览器登录')

const currentOption = computed(() =>
  platformOptions.value.find((p) => p.platform === platform.value)
)

const modeHint = computed(() => {
  const qr = currentOption.value ? currentOption.value.mode === 'qrcode' : false
  if (qr) {
    return headless.value
      ? '该平台支持二维码登录，无需显示浏览器'
      : '会弹出浏览器窗口，二维码同时显示在下方面板'
  }
  return headless.value
    ? '该平台只能浏览器登录，关闭窗口后可能看不到扫码页'
    : '会弹出浏览器窗口，请在其中手动完成登录'
})

const statusText = computed(() => {
  const map = {
    starting: '启动中',
    waiting: '等待操作',
    success: '登录成功',
    failed: '登录失败',
    timeout: '已超时'
  }
  return map[status.value] || '待开始'
})


const statusType = computed(() => {
  if (status.value === 'success') return 'success'
  if (status.value === 'failed' || status.value === 'timeout') return 'danger'
  if (status.value === 'waiting') return 'warning'
  return 'info'
})

async function loadPlatforms() {
  try {
    const data = await sauApi.getLoginPlatforms()
    platformOptions.value = [...(data.qrcode || []), ...(data.browser || [])]
  } catch (e) {
    platformOptions.value = []
  }
}

function reset() {
  cleanup()
  status.value = ''
  message.value = ''
  qrcode.value = ''
}

function cleanup() {
  if (source) {
    source.close()
    source = null
  }
}

async function start() {
  if (!platform.value || !account.value) return
  reset()
  starting.value = true
  try {
    const session = await sauApi.startLogin(platform.value, account.value, headless.value)
    status.value = 'starting'
    message.value = '已创建登录会话 ' + session.id

    source = new EventSource(sauApi.loginStreamUrl(session.id))
    source.addEventListener('status', (ev) => {
      const data = JSON.parse(ev.data)
      status.value = data.status || 'starting'
      message.value = data.message || ''
    })
    source.addEventListener('qrcode', (ev) => {
      const data = JSON.parse(ev.data)
      if (data.image_data_url) {
        qrcode.value = data.image_data_url
      } else if (data.image_path) {
        message.value = '二维码已保存到 ' + data.image_path
      }
    })
    source.addEventListener('result', (ev) => {
      const data = JSON.parse(ev.data)
      status.value = data.success ? 'success' : 'failed'
      message.value = data.message || (data.success ? '登录成功' : '登录失败')
      cleanup()
      if (data.success) {
        ElMessage.success('账号 ' + account.value + ' 登录成功')
        emit('success', { platform: platform.value, account: account.value })
      } else {
        ElMessage.error(message.value)
      }
    })
    source.onerror = () => {
      if (status.value === 'success' || status.value === 'failed') return
      message.value = '连接中断，请查看后端日志'
    }
  } catch (e) {
    status.value = 'failed'
    message.value = e.message || String(e)
  } finally {
    starting.value = false
  }
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      if (platformOptions.value.length === 0) loadPlatforms()
      if (props.defaultPlatform) platform.value = props.defaultPlatform
      // 每次打开都清掉上一次的二维码和结果，避免误以为已经登录
      reset()
    } else {
      cleanup()
    }
  }
)

onBeforeUnmount(cleanup)
</script>

<style scoped>
.hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}
.opt-tag {
  float: right;
  margin-left: 12px;
  font-size: 11px;
  color: #c0c4cc;
}
.status-box {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
}
.status-msg {
  font-size: 13px;
  color: #606266;
  word-break: break-all;
}
.qrcode-box {
  margin-top: 16px;
  text-align: center;
}
.qrcode-box img {
  width: 220px;
  height: 220px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
}
.qrcode-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}
.waiting-box {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  color: #e6a23c;
  font-size: 13px;
}
</style>
