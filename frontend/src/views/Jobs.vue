<script setup>
import { ref, computed, inject, watch, onMounted } from 'vue'
import { get, post } from '../api.js'
import { tick } from '../live.js'
import { decisionOf, featuresOf, statusMeta } from '../util.js'

const shell = inject('shell')
const status = ref({ worker_options: [] })
const pick = ref('')
const mode = ref('dispatch')
const manual = ref('')
const busy = ref(false)
const err = ref('')

const jobs = computed(() => shell.jobs.value || [])
const job = computed(() => jobs.value.find(j => j.id === shell.focusJob.value) || jobs.value[0])
const dec = computed(() => decisionOf(job.value))
const feats = computed(() => featuresOf(job.value))
const ev = computed(() => [...(job.value?.evals || [])].sort((a, b) => b.weighted - a.weighted))
const top = computed(() => ev.value[0]?.weighted)
const subs = computed(() => job.value?.subtasks || [])
const arts = computed(() => job.value?.artifacts || [])

watch(job, (j) => { if (j) pick.value = decisionOf(j).worker || '' }, { immediate: true })

async function loadStatus() { status.value = await get('/api/status') }
async function act(action, extra = {}) {
  if (!job.value || busy.value) return
  busy.value = true; err.value = ''
  try {
    const r = await post('/api/confirm', {
      job_id: job.value.id, action, worker: pick.value || dec.value.worker,
      mode: mode.value, ...extra,
    })
    if (r.error) err.value = r.error
    await shell.load()
  } finally { busy.value = false }
}
async function fillManual() {
  if (!manual.value.trim()) return
  busy.value = true; err.value = ''
  try {
    const r = await post('/api/manual', { job_id: job.value.id, detail: manual.value.trim() })
    if (r.error) err.value = r.error
    manual.value = ''
    await shell.load()
  } finally { busy.value = false }
}
async function resume() {
  busy.value = true
  try { await post('/api/resume', { job_id: job.value.id }); await shell.load() }
  finally { busy.value = false }
}
onMounted(loadStatus)
watch(tick, () => shell.load())
</script>

<template>
  <div v-if="job">
    <div class="page-head">
      <div>
        <p class="muted" style="font-size:12px">{{ job.id }} · 阶段 {{ job.stage || '—' }}</p>
        <h1>{{ job.title }}</h1>
        <p class="sub">{{ job.description || '没有更详细的需求说明。' }}</p>
      </div>
      <span class="seal" :class="statusMeta(job.status).k">{{ statusMeta(job.status).t }}</span>
    </div>

    <div class="alert" v-if="job.sensitive">描述里含敏感动作。盖章即表示允许派活。</div>
    <div class="alert" v-if="job.status==='interrupted'">
      任务在 {{ job.stage || '某' }} 阶段中断，可从断点续跑。
      <div class="row"><button class="btn pri sm" @click="resume">从断点恢复</button></div>
    </div>
    <p class="muted" v-if="err">{{ err }}</p>

    <div class="section">
      <h2>决策</h2>
      <div class="fields">
        <div>
          <span class="lab">主 worker</span>
          <select v-if="job.status==='awaiting_decision'" v-model="pick" style="margin:0">
            <option v-for="w in status.worker_options" :key="w" :value="w">{{ w }}</option>
          </select>
          <span v-else>{{ dec.worker || '-' }}</span>
        </div>
        <div><span class="lab">拆分</span>{{ dec.split ? '是' : '否' }}</div>
        <div><span class="lab">优先级</span>{{ (dec.priority_order || []).join(' → ') || '-' }}</div>
        <div><span class="lab">预算</span>${{ job.budget_usd || dec.budget_usd || '-' }} · 已花 ${{ (job.spent_usd || 0).toFixed(2) }}</div>
      </div>
      <div class="bar-track" style="max-width:280px;margin-bottom:10px">
        <i :style="{width: Math.min(100, Math.round(((job.spent_usd||0)/Math.max(job.budget_usd||5,0.01))*100))+'%'}"></i>
      </div>
      <div class="reason">{{ dec.reason }}<div class="src">{{ dec.source }}</div></div>
      <div class="chips"><span v-for="(v,k) in feats" :key="k">{{ k }}:{{ Array.isArray(v)?v.join('|'):v }}</span></div>
    </div>

    <div class="section" v-if="job.status==='awaiting_decision'">
      <h2>盖章派活</h2>
      <p class="muted" style="margin-bottom:10px">默认只派你选中的人。同场比试会让所有能自动跑的工人一起交卷（手动工人会跳过）。</p>
      <div class="row">
        <label class="muted"><input type="radio" value="dispatch" v-model="mode"> 只派选中的人</label>
        <label class="muted"><input type="radio" value="benchmark" v-model="mode"> 同场比试</label>
      </div>
      <div class="row">
        <button class="btn stamp" :disabled="busy" @click="act(pick!==dec.worker?'modify':'accept')">盖章并派活</button>
        <button class="btn bad sm" :disabled="busy" @click="act('reject')">拒绝</button>
      </div>
    </div>

    <div class="section" v-if="job.status==='awaiting_manual'">
      <h2>手动任务卡</h2>
      <p class="muted">到 Cursor（或对应 GUI）做完后，把产物贴在下面。</p>
      <pre class="reason" style="white-space:pre-wrap">{{ (arts[0] && arts[0].detail) || job.description }}</pre>
      <textarea v-model="manual" rows="5" placeholder="粘贴代码、说明或产物路径"></textarea>
      <button class="btn pri" :disabled="busy" @click="fillManual">回填并继续评测</button>
    </div>

    <div class="section">
      <h2>子任务</h2>
      <div class="stk" v-for="s in subs" :key="s.id">
        <div><b>{{ s.title }}</b><div class="muted">{{ s.worker }}</div></div>
        <span class="badge" :class="s.status==='done'?'b-done':s.status==='awaiting_manual'?'b-wait':'b-run'">{{ s.status }}</span>
      </div>
      <p v-if="!subs.length" class="muted">盖章派活后才会生成真实子任务。</p>
    </div>

    <div class="section" v-if="ev.length">
      <h2>{{ job.dispatch_mode==='benchmark' ? '同场比试' : '评测' }}</h2>
      <table>
        <tr><th>worker</th><th>加权</th><th>花费</th><th>延迟</th><th>理由</th></tr>
        <tr v-for="e in ev" :key="e.id || e.worker">
          <td :style="{fontWeight:e.weighted===top?700:400,color:e.weighted===top?'var(--stamp)':'inherit'}">{{ e.worker }}</td>
          <td>
            <div class="track" style="width:100px;margin-right:8px"><i :style="{width: Math.round((e.weighted/5)*100)+'%'}"></i></div>
            {{ e.weighted }}
          </td>
          <td>${{ e.cost_usd ?? '—' }}</td>
          <td>{{ e.latency_ms ? Math.round(e.latency_ms)+'ms' : '—' }}</td>
          <td class="muted">{{ e.rationale }}</td>
        </tr>
      </table>
    </div>
  </div>
  <p v-else class="muted">从工单库点开一张工单，或先新建。</p>
</template>
