// 实时订阅后端的 /api/events(SSE)。任何事件到来 -> tick+1，视图 watch 它自动刷新。
import { ref } from 'vue'
export const tick = ref(0)
let started = false
export function startLive() {
  if (started) return
  started = true
  const es = new EventSource('/api/events')
  es.onmessage = (e) => { try { const d = JSON.parse(e.data); if (d.type) tick.value++ } catch {} }
}
