import axios from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'

const request = axios.create({
  baseURL,
  timeout: 60000
})

request.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && typeof payload === 'object' && 'code' in payload) {
      if (payload.code === 200) {
        return payload.data
      }
      if (!response.config?.silent) {
        ElMessage.error(payload.msg || '请求失败')
      }
      return Promise.reject(new Error(payload.msg || '请求失败'))
    }
    return payload
  },
  (error) => {
    if (error.code === 'ERR_CANCELED' || error.name === 'CanceledError') {
      return Promise.reject(error)
    }
    const payload = error.response && error.response.data
    const msg =
      (payload && (payload.msg || payload.message)) || error.message || '网络请求失败'
    // 视图里已经自行提示的请求可传 { silent: true }，避免一次失败弹两条
    if (!error.config?.silent) {
      ElMessage.error(msg)
    }
    return Promise.reject(new Error(msg))
  }
)

export const http = {
  get(url, params, config) {
    return request.get(url, { params, ...config })
  },
  post(url, data, config) {
    return request.post(url, data, config)
  },
  put(url, data, config) {
    return request.put(url, data, config)
  },
  delete(url, params) {
    return request.delete(url, { params })
  },
  upload(url, formData, onUploadProgress, config) {
    return request.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
      ...config
    })
  }
}

export { baseURL }
export default request
