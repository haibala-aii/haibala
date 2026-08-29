<script setup>
import { ref, computed, onMounted } from 'vue'
import { get, post } from '../api.js'
const jobs = ref([])
const cur = ref('')
const job = computed(() => jobs.value.find(j => j.id === cur.value))
const dec = computed(() => { try { return JSON.parse(job.value?.decision_json || '{}') } catch { return {} } })
const ev = computed(() => [...(job.value?.evals || [])].sort((a, b) => b.weighted - a.weighted))
const top = computed(() => ev.value[0]?.weighted)
async function load() {
  jobs.value = await get('/api/jobs')
  if (!cur.value && jobs.value.length) cur.value = jobs.value[0].id
}
async function resume() {
  await post('/api/resume', { job_id: cur.value })
  await load()
}
onMounted(load)
</script>

<template>
  <div class="paper panel">
    <div class="meta"><span>{{ job?.id }}</span><span>阶段:{{ job?.stage || '—' }}</span></div>
    <h1 style="margin-top:2px">{{ job?.title }}</h1>

    <div class="alert" v-if="job?.status==='interrupted'">
      <b>任务已中断（{{ job.stage || '某' }} 阶段）</b>
      <p class="desc">可从断点续跑，不重做已完成阶段。</p>
      <div class="row"><button class="btn stamp sm" @click="resume">从断点恢复</button></div>
    </div>

    <h2>决策</h2>
    <div class="fields">
      <div><span class="lab">worker</span>{{ dec.worker || '-' }}</div>
      <div><span class="lab">拆分</span>{{ dec.split ? '是' : '否' }}</div>
      <div><span class="lab">优先级</span>{{ (dec.priority_order || []).join(' → ') }}</div>
      <div><span class="lab">预算</span>${{ dec.budget_usd || '-' }}</div>
    </div>
    <div class="reason">{{ dec.reason }}<div class="src">{{ dec.source }}</div></div>

    <h2>子任务</h2>
    <div class="stk" v-for="i in Math.min(dec.n_workers || 1, 4)" :key="i">
      <div><b>子任务 {{ i }}</b></div><span class="badge b-done">done</span>
    </div>

    <h2>同场比试 · 各 agent 得分</h2>
    <table>
      <tr><th>worker</th><th>加权</th><th>花费</th><th>理由</th></tr>
      <tr v-for="e in ev" :key="e.worker">
        <td :style="{fontWeight:e.weighted===top?700:400, color:e.weighted===top?'var(--stamp)':'inherit'}">{{ e.worker }}</td>
        <td>
          <div class="track" style="width:120px;display:inline-block;vertical-align:middle;margin-right:8px">
            <i :style="{ width: Math.round((e.weighted / 5) * 100) + '%' }"></i>
          </div>
          {{ e.weighted }}
        </td>
        <td>${{ e.cost_usd || '-' }}</td>
        <td style="color:var(--muted)">{{ (e.rationale || '').slice(0,40) }}</td>
      </tr>
    </table>
  </div>
</template>
