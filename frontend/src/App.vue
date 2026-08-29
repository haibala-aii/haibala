<script setup>
import { ref, computed, onMounted, watch, provide } from 'vue'
import { startLive, tick } from './live.js'
import { get, post } from './api.js'
import Dash from './views/Dash.vue'
import Chat from './views/Chat.vue'
import Jobs from './views/Jobs.vue'
import Eval from './views/Eval.vue'
import Audit from './views/Audit.vue'
import Approvals from './views/Approvals.vue'
import Settings from './views/Settings.vue'

const view = ref('dash')
const collapsed = ref(false)
const findOpen = ref(false)
const q = ref('')
const compose = ref(false)
const focusJob = ref('')
const jobs = ref([])
const approvals = ref([])
const title = ref('')
const desc = ref('')
const budget = ref(5)
const busy = ref(false)

const nav = [
  { id: 'dash', label: '工单库', icon: 'M4 5h16v14H4zM8 9h8M8 13h5' },
  { id: 'chat', label: '对话', icon: 'M4 5h16v11H8l-4 4z' },
  { id: 'eval', label: '评测', icon: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 8v5l3 3' },
  { id: 'audit', label: '审计', icon: 'M6 3h12v18H6zM9 8h6M9 12h6' },
  { id: 'approvals', label: '待确认', icon: 'M12 3l8 4v6c0 5-4 7-8 8-4-1-8-3-8-8V7z' },
  { id: 'settings', label: '设置', icon: 'M12 8a4 4 0 100 8 4 4 0 000-8zM4 12h2M18 12h2' },
]
const views = { dash: Dash, chat: Chat, jobs: Jobs, eval: Eval, audit: Audit, approvals: Approvals, settings: Settings }

const recent = computed(() => jobs.value.slice(0, 6))
const filteredNav = computed(() => {
  const s = q.value.trim()
  if (!s) return nav
  return nav.filter(n => n.label.includes(s))
})

async function load() {
  try {
    jobs.value = await get('/api/jobs')
    approvals.value = await get('/api/approvals')
  } catch { /* 后端未起时保持空 */ }
}

function openCompose() { compose.value = true }
function openJob(id) {
  focusJob.value = id
  view.value = 'jobs'
}
async function createJob() {
  if (!title.value.trim() || busy.value) return
  busy.value = true
  try {
    const r = await post('/api/run', {
      title: title.value.trim(),
      description: desc.value.trim(),
      budget_usd: Number(budget.value) || undefined,
    })
    compose.value = false
    title.value = ''; desc.value = ''
    await load()
    if (r.job_id) openJob(r.job_id)
  } finally { busy.value = false }
}

provide('shell', { view, focusJob, openCompose, openJob, jobs, load })

onMounted(() => {
  startLive()
  load()
  window.__haibala = { newJob: openCompose, go: (v) => { view.value = v } }
})
watch(tick, load)
</script>

<template>
  <div class="app">
    <aside class="side" :class="{collapsed}">
      <div class="brand">
        <img class="logo" src="/logo.png" alt="haibala" width="32" height="32">
        <span class="bt" v-if="!collapsed">haibala</span>
        <div class="tools">
          <button class="ico-btn" title="搜索" @click="findOpen=!findOpen; collapsed=false" aria-label="搜索">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3-3"/></svg>
          </button>
          <button class="ico-btn" :title="collapsed?'展开':'收起'" @click="collapsed=!collapsed" aria-label="收起侧栏">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h10M4 18h16"/></svg>
          </button>
        </div>
      </div>
      <div class="side-pad">
        <button class="btn pri block" @click="openCompose"><span>+ 新建工单</span></button>
        <input v-if="findOpen && !collapsed" class="search" v-model="q" placeholder="搜索导航" style="margin-bottom:8px;width:100%">
      </div>
      <nav class="nav">
        <div class="gt" v-if="!collapsed">工作台</div>
        <button v-for="it in filteredNav" :key="it.id" class="ni" :class="{on: view===it.id}" @click="view=it.id">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path :d="it.icon"/></svg>
          <span class="lbl">{{ it.label }}</span>
          <span v-if="it.id==='approvals' && approvals.length" class="count">{{ approvals.length }}</span>
        </button>
        <div class="gt" v-if="!collapsed">最近</div>
        <div class="recent" v-if="!collapsed">
          <button v-for="j in recent" :key="j.id" class="rj" :class="{on: focusJob===j.id && view==='jobs'}" @click="openJob(j.id)">
            <i class="dot"></i><span>{{ j.title }}</span>
          </button>
          <p v-if="!recent.length" class="muted" style="padding:8px;font-size:12px">还没有工单</p>
        </div>
      </nav>
      <div class="foot">
        <div class="ava">本</div>
        <span>本地 · 数据不出机</span>
        <i class="live-dot" title="核心在线"></i>
      </div>
    </aside>
    <section class="stage">
      <div class="canvas">
        <component :is="views[view]" />
      </div>
    </section>
  </div>

  <div class="modal" v-if="compose" @click.self="compose=false">
    <div class="sheet">
      <h2>新建工单</h2>
      <p class="muted" style="margin-bottom:14px">只出决策，不会马上派活。你盖章之后才动手。</p>
      <input type="text" v-model="title" placeholder="标题，例如：批量抠图小程序">
      <textarea v-model="desc" rows="4" placeholder="需求说明（可选）"></textarea>
      <label class="muted" style="display:block;margin:4px 0 6px;font-size:12px">预算（美元）</label>
      <input type="number" v-model.number="budget" min="0" step="0.5">
      <div class="row">
        <button class="btn pri" :disabled="busy" @click="createJob">抽取特征并出决策</button>
        <button class="btn ghost" @click="compose=false">取消</button>
      </div>
    </div>
  </div>
</template>
