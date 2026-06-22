const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const TOKEN = import.meta.env.VITE_API_TOKEN ?? ''

function headers() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${TOKEN}`,
  }
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`, { headers: headers() })
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

export const fetchWeeks = () => get('/weeks')
export const fetchSpend = () => get('/usage/current-month')
export const fetchChatHistory = (postId) => get(`/chat/${postId}/history`)
export const sendChatMessage = (postId, message) => post(`/chat/${postId}`, { message })
