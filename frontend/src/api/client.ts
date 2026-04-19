import axios from 'axios'
import { message } from 'ant-design-vue'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

const apiKey = import.meta.env.VITE_API_KEY
if (apiKey) {
  client.defaults.headers.common['X-API-Key'] = apiKey
}

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    message.error(msg)
    return Promise.reject(error)
  },
)

export default client
