import { http } from '@/utils/request'

// 后端全部接口都挂在 /api 下
export const sauApi = {
  // ---- 元信息
  getSchema() {
    return http.get('/schema')
  },
  getHealth() {
    return http.get('/health')
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
    return http.upload('/materials/upload', form, onProgress)
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
  getAnalyticsOverview(platform, account) {
    return http.get('/analytics/overview', { platform, account })
  },
  listAnalyticsWorks(platform, account, page = 1, size = 20, keyword = '') {
    return http.get('/analytics/works', { platform, account, page, size, keyword })
  },
  collectAnalytics(platform, account) {
    return http.post('/analytics/collect', { platform, account })
  },
  getAnalyticsSchedule() {
    return http.get('/analytics/schedule')
  },
  saveAnalyticsSchedule(payload) {
    return http.put('/analytics/schedule', payload)
  }
}

export default sauApi
