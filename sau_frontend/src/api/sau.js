import { http } from '@/utils/request'

// 后端全部接口都挂在 /api 下
export const sauApi = {
  // ---- 元信息
  getSchema() {
    return http.get('/schema')
  },
  getHealth() {
    // 健康探测失败只更新顶部状态灯，不弹全局错误
    return http.get('/health', undefined, { silent: true })
  },
  getLoginPlatforms() {
    return http.get('/login/platforms')
  },

  // ---- 任务
  createTask(platform, action, values) {
    return http.post('/tasks', { platform, action, values })
  },
  listTasks(limit = 50) {
    return http.get('/tasks', { limit })
  },
  getTask(id, tail = 0) {
    return http.get('/tasks/' + id, tail ? { tail } : undefined)
  },
  cancelTask(id) {
    return http.post('/tasks/' + id + '/cancel')
  },
  clearTasks() {
    return http.delete('/tasks')
  },

  // ---- 账号
  listAccounts() {
    return http.get('/accounts')
  },
  deleteAccount(platform, account) {
    return http.delete('/accounts', { platform, account })
  },
  uploadAccount(platform, account, file) {
    const form = new FormData()
    form.append('platform', platform)
    form.append('account', account)
    form.append('file', file)
    return http.upload('/accounts/upload', form)
  },

  // ---- 素材
  listMaterials() {
    return http.get('/materials')
  },
  uploadMaterial(file, onProgress) {
    const form = new FormData()
    form.append('file', file)
    // 素材管理页会带文件名提示，这里不再让拦截器重复弹一次
    return http.upload('/materials/upload', form, onProgress, { silent: true })
  },
  deleteMaterial(name) {
    return http.delete('/materials', { name })
  },
  materialPreviewUrl(name) {
    const prefix = import.meta.env.VITE_API_BASE_URL || '/api'
    return prefix + '/materials/preview/' + encodeURIComponent(name)
  },

  // ---- 登录
  startLogin(platform, account, headless = true) {
    return http.post('/login/start', { platform, account, headless })
  },
  loginStreamUrl(sessionId) {
    const prefix = import.meta.env.VITE_API_BASE_URL || '/api'
    return prefix + '/login/' + sessionId + '/stream'
  },

  // ---- 数据分析
  getAnalyticsOverview(platform, account, config) {
    return http.get('/analytics/overview', { platform, account }, config)
  },
  getAnalyticsSummary() {
    return http.get('/analytics/summary')
  },
  getAnalyticsTrend(days = 30) {
    return http.get('/analytics/trend', { days })
  },
  listAnalyticsWorks(platform, account, page = 1, size = 20, keyword = '', config) {
    return http.get(
      '/analytics/works',
      { platform, account, page, size, keyword },
      config
    )
  },
  collectAnalytics(platform, account) {
    return http.post('/analytics/collect', { platform, account })
  },
  getAnalyticsSchedule() {
    return http.get('/analytics/schedule')
  },
  saveAnalyticsSchedule(payload) {
    return http.put('/analytics/schedule', payload)
  },

  // ---- 手动发布
  openManual(platform, account) {
    return http.post('/manual/open', { platform, account })
  },

  // ---- 设置
  getDataDir() {
    return http.get('/settings/data-dir')
  },
  setDataDir(dataDir) {
    return http.put('/settings/data-dir', { data_dir: dataDir })
  }
}

export default sauApi
