import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 注入token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.params = { ...config.params, token };
  }
  return config;
});

// 响应拦截器 - 统一错误处理
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('authToken');
      localStorage.removeItem('currentUser');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default client;
export { API_BASE };
