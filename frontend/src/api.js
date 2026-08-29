// 与后端 Python 服务通信
export const api = async (path, opts) => (await fetch(path, opts)).json()
export const get = (p) => api(p)
export const post = (p, body) => api(p, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})
