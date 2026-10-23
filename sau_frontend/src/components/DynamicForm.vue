<template>
  <el-form label-position="top" class="dynamic-form">
    <el-row :gutter="16">
      <el-col
        v-for="field in orderedFields"
        :key="field.dest"
        :xs="24"
        :sm="field.span === 24 || isLongText(field) ? 24 : 12"
      >
        <el-form-item :required="field.required" :error="errors[field.dest] || ''">
          <template #label>
            <span class="field-label">{{ labelOf(field) }}</span>
            <el-tag v-if="field.required" size="small" type="danger" effect="plain" class="ml-1">
              必填
            </el-tag>
            <el-tag v-else size="small" type="info" effect="plain" class="ml-1">选填</el-tag>
            <span class="field-flag">{{ field.flag }}</span>
          </template>

          <!-- 账号：可从已登录账号里选，也可手输新别名 -->
          <el-select
            v-if="field.dest === 'account'"
            :model-value="values[field.dest]"
            filterable
            allow-create
            default-first-option
            clearable
            style="width: 100%"
            placeholder="输入账号别名，或选择已登录账号"
            @update:model-value="(v) => setValue(field, v)"
          >
            <el-option
              v-for="a in accountOptions"
              :key="a.account"
              :label="a.account + '  (' + a.label + ')'"
              :value="a.account"
            />
          </el-select>

          <!-- 布尔（v-else-if：account 已用独立 v-if，这里必须接在同一链上，否则 account 字段会多渲染一个文本框） -->
          <el-switch
            v-else-if="field.kind === 'bool'"
            :model-value="Boolean(values[field.dest])"
            @update:model-value="(v) => setValue(field, v)"
          />

          <!-- 枚举 -->
          <el-select
            v-else-if="field.kind === 'select'"
            :model-value="values[field.dest]"
            clearable
            filterable
            style="width: 100%"
            :placeholder="field.required ? '请选择' : '默认'"
            @update:model-value="(v) => setValue(field, v)"
          >
            <el-option v-for="c in field.choices" :key="c" :label="String(c)" :value="c" />
          </el-select>

          <!-- 文件 / 目录 -->
          <el-select
            v-else-if="field.kind === 'file' || field.kind === 'dir'"
            :model-value="values[field.dest]"
            clearable
            filterable
            allow-create
            default-first-option
            style="width: 100%"
            :placeholder="field.kind === 'dir' ? '输入或选择目录路径' : '输入完整路径，或从素材中选择'"
            @update:model-value="(v) => setValue(field, v)"
          >
            <el-option
              v-for="m in optionsFor(field)"
              :key="m.name"
              :label="m.name + '  (' + m.size_text + ')'"
              :value="m.path"
            />
          </el-select>

          <!-- 时间 -->
          <el-date-picker
            v-else-if="field.kind === 'datetime'"
            :model-value="values[field.dest]"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm"
            placeholder="留空表示立即发布"
            style="width: 100%"
            @update:model-value="(v) => setValue(field, v)"
          />

          <!-- 数字 -->
          <el-input-number
            v-else-if="field.kind === 'number' && !field.nargs"
            :model-value="values[field.dest]"
            :min="0"
            controls-position="right"
            style="width: 100%"
            @update:model-value="(v) => setValue(field, v)"
          />

          <!-- 多值 -->
          <el-input
            v-else-if="field.kind === 'list' || field.nargs"
            :model-value="listValue(field)"
            placeholder="多个值用英文逗号分隔"
            @update:model-value="(v) => setListValue(field, v)"
          />

          <!-- 长文本 -->
          <el-input
            v-else-if="isLongText(field)"
            :model-value="values[field.dest]"
            type="textarea"
            :rows="4"
            placeholder="请输入"
            @update:model-value="(v) => setValue(field, v)"
          />

          <!-- 普通文本 -->
          <el-input
            v-else
            :model-value="values[field.dest]"
            :placeholder="placeholderOf(field)"
            clearable
            @update:model-value="(v) => setValue(field, v)"
          />

          <div v-if="helpOf(field)" class="field-help">{{ helpOf(field) }}</div>
        </el-form-item>
      </el-col>
    </el-row>
  </el-form>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  errors: { type: Object, default: () => ({}) },
  materials: { type: Array, default: () => [] },
  accounts: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:modelValue'])

const values = computed(() => props.modelValue || {})

const orderedFields = computed(() => props.fields || [])

const accountOptions = computed(() => props.accounts || [])

const LABELS = {
  account: '账号名称',
  file: '视频文件',
  video: '视频文件',
  images: '图片列表',
  image: '图片文件',
  title: '标题',
  short_title: '短标题',
  desc: '简介 / 描述',
  description: '描述',
  note: '正文内容',
  notef: '正文文件',
  content_file: '正文文件',
  tags: '话题标签',
  schedule: '定时发布时间',
  thumbnail: '封面图',
  thumbnail_landscape: '横版封面',
  thumbnail_portrait: '竖版封面',
  cover: '独立封面',
  cover_indices: '封面图片序号',
  product_link: '商品链接',
  product_title: '商品标题',
  declaration: '内容声明',
  collection: '合集名称',
  playlist: '播放列表',
  category: '内容分类',
  tid: '分区 ID',
  bgm: '背景音乐',
  debug: '调试模式',
  headless: '无头模式（不显示浏览器窗口）',
  prepare_only: '仅上传不发布',
  draft: '存为草稿',
  visibility: '可见性',
  originality: '原创 / 转载',
  source: '信息来源',
  source_url: '原文链接',
  author: '作者',
  public: '审核后校验公开',
  upload_timeout: '上传超时（秒）',
  timeout: '超时（秒）',
  content_id: '作品 ID',
  origin_id: '草稿 ID',
  page: '作品短码',
  page_id: '主页数字 ID',
  owner_id: '主页数字 ID',
  post_url: '原作品链接',
  expected_name: '期望账号名',
  expected_text: '核对用正文',
  deleted: '仅检查是否已删除',
  from_trash: '作品在垃圾箱',
  permanent: '永久删除',
  scheduled: '定时列表操作',
  show_options: '仅列出可选项',
  result: '结果文件',
  output: '输出文件',
  overwrite: '覆盖已有文件',
  video_mark: '视频声明',
  type: '作品类型',
  theme: '渲染主题',
  themes: '主题列表',
  verify: '校验登录态',
  proxy: '代理地址',
  location: '位置',
  at: '定时时间',
  force: '强制执行'
}

const HELP_ZH = {
  'Video file path': '视频文件的完整路径',
  'Video title': '视频标题',
  'Video title (4-40 chars)': '视频标题，4-40 个字符',
  'Video title (<=100 chars)': '视频标题，最多 100 个字符',
  'Video title (max 30 chars)': '视频标题，最多 30 个字符',
  'Title, 5-60 Chinese character units': '标题，5-60 个汉字宽度',
  'Video description': '视频简介',
  'Comma-separated tags': '英文逗号分隔的话题标签',
  'Comma-separated tags, such as tag1,tag2': '英文逗号分隔的话题标签，例：tag1,tag2',
  'Schedule time in %Y-%m-%d %H:%M': '定时发布时间，格式 YYYY-MM-DD HH:mm',
  'Enable debug mode': '打开调试日志',
  'Run in headless mode': '不显示浏览器窗口',
  'Save as draft instead of publishing': '只存草稿，不点击发布',
  'Video visibility': '视频可见范围',
  'Image file paths': '图片文件的完整路径，多张用逗号分隔',
  'Local account alias': '本地账号别名，用于区分多个账号',
  'Login timeout in seconds': '登录等待秒数',
  'Upload/processing timeout in seconds': '上传与处理的超时秒数',
  'Optional video description': '选填，视频简介',
  'Optional cover image path': '选填，封面图片路径',
  'Optional cover image path (<5MB)': '选填，封面图片路径（小于 5MB）',
  'Optional thumbnail image path': '选填，缩略图路径',
  'Optional thumbnail path': '选填，封面路径',
  'Optional 3:4 portrait thumbnail path': '选填，3:4 竖版封面路径',
  'Optional 4:3 landscape thumbnail path': '选填，4:3 横版封面路径',
  'Optional Bilibili cover image path': '选填，B 站封面图片路径',
  'Optional WeChat Channels short title': '选填，视频号短标题',
  'Optional collection name': '选填，合集名称',
  'Optional collection name to add the work into (must already exist)': '选填，要加入的合集名称（需已存在）',
  'Optional playlist name to add the video to (for series)': '选填，要加入的播放列表（系列）',
  'Optional product link': '选填，商品链接',
  'Optional product title': '选填，商品标题',
  'Optional note content': '选填，图文正文',
  'Optional post description': '选填，帖子描述',
  'Post title, merged into Facebook caption': '帖子标题，会并入 Facebook 文案',
  'Bilibili category id': 'B 站分区 ID',
  'BGM music name to search and select': '搜索并选择的背景音乐名称',
  'Upload and fill only; do not click publish': '只上传并填好表单，不点击发布',
  'Draft ID captured before confirming publication': '确认发布前记录的草稿 ID',
  'Published content_id returned by Dayu': '大鱼号返回的作品 content_id',
  'Saved Dayu result JSON to recover': '用于恢复的大鱼号结果 JSON',
  'Expected name displayed by Dayu': '大鱼号上显示的期望昵称',
  'Read note content from file (txt/md)': '从 txt/md 文件读取正文',
  'Exact Douyin self-declaration option text; omitted means do not set one': '抖音自主声明选项的精确文案，留空表示不设置'
}

const VIDEO_DESTS = new Set(['file', 'video'])
const IMAGE_DESTS = new Set([
  'thumbnail',
  'thumbnail_landscape',
  'thumbnail_portrait',
  'cover',
  'image',
  'images'
])

const VIDEO_EXT = /\.(mp4|mov|mkv|avi|flv|webm|m4v)$/i
const IMAGE_EXT = /\.(png|jpe?g|webp|bmp|gif)$/i

function kindOf(material) {
  if (material.kind === 'video' || material.kind === 'image') return material.kind
  if (IMAGE_EXT.test(material.name || '')) return 'image'
  if (VIDEO_EXT.test(material.name || '')) return 'video'
  return ''
}

function optionsFor(field) {
  const list = props.materials || []
  let filtered = list
  if (VIDEO_DESTS.has(field.dest)) {
    filtered = list.filter((m) => kindOf(m) !== 'image')
  } else if (IMAGE_DESTS.has(field.dest)) {
    filtered = list.filter((m) => kindOf(m) !== 'video')
  }
  if (!filtered.length) filtered = list
  return filtered.map((m) => ({
    name: m.name,
    path: m.path || m.name,
    size_text: m.size_text || ''
  }))
}

function labelOf(field) {
  if (LABELS[field.dest]) return LABELS[field.dest]
  const raw = (field.help || '').split(/[；;，,。]/)[0].trim()
  if (raw) return raw.slice(0, 16)
  return field.dest
}

function helpOf(field) {
  const h = field.help || ''
  if (!h) return ''
  // 账号类 help 形如 "Douyin user-defined account_name"，统一换成中文说明
  if (/user-defined account_name$/.test(h) || /^Meta account name$/.test(h)) {
    return '本地账号别名，需与 cookies 里的账号名一致'
  }
  return HELP_ZH[h] || h
}

function placeholderOf(field) {
  if (field.default !== null && field.default !== undefined && field.default !== '') {
    return '默认：' + String(field.default)
  }
  return '请输入'
}

function isLongText(field) {
  return ['desc', 'description', 'content', 'body', 'text', 'note'].includes(field.dest)
}

function setValue(field, value) {
  emit('update:modelValue', { ...values.value, [field.dest]: value })
}

function listValue(field) {
  const v = values.value[field.dest]
  if (Array.isArray(v)) return v.join(',')
  return v === undefined || v === null ? '' : String(v)
}

function setListValue(field, raw) {
  const items = String(raw)
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  setValue(field, items)
}
</script>

<style scoped>
.dynamic-form :deep(.el-form-item) {
  margin-bottom: 18px;
}
.field-label {
  font-weight: 600;
  color: #303133;
}
.field-flag {
  margin-left: 8px;
  font-family: Consolas, Monaco, monospace;
  font-size: 11px;
  font-weight: 400;
  color: #c0c4cc;
}
.field-help {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #909399;
  word-break: break-all;
}
.ml-1 {
  margin-left: 6px;
}
</style>
