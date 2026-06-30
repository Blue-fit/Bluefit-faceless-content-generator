// API base from Vercel env. The auth token is NOT baked into the bundle anymore —
// it is obtained by logging in (POST /auth/login) and kept in localStorage.
const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'bf_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY) || ''
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)
export const isAuthed = () => !!getToken()

function headers() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${getToken()}`,
  }
}

function handleUnauthorized() {
  clearToken()
  if (window.location.pathname !== '/login') window.location.href = '/login'
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: headers() })
  if (res.status === 401) { handleUnauthorized(); throw new Error('Unauthorized') }
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  })
  if (res.status === 401) { handleUnauthorized(); throw new Error('Unauthorized') }
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

export async function login(username, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) throw new Error('Invalid username or password')
  const data = await res.json()
  setToken(data.token)
  return data
}

export const fetchWeeks = () => get('/weeks')
export const fetchSpend = () => get('/usage/current-month')
export const fetchChatHistory = (postId) => get(`/chat/${postId}/history`)
export const sendChatMessage = (postId, message) => post(`/chat/${postId}`, { message })
export const fetchExplain = (postId) => get(`/posts/${postId}/explain`)