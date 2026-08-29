<script setup>
import { ref, computed, onMounted } from 'vue'
import { get, post } from '../api.js'
const emit = defineEmits(['navigate'])

const jobs = ref([])
const approvals = ref([])
const cur = ref('')
const title = ref(''); const desc = ref('')

const stats = computed(() => ({
  running: jobs.value.filter(j => j.status === 'running' || j.status === 'awaiting_approval').length,
  approvals: approvals.value.length,
  done: jobs.value.filter(j => j.status === 'done').length,
  avg: (() => { const e = jobs.value.flatMap(j => j.evals || []); return e.length ? (e.reduce((a, b) => a + b.weighted, 0) / e.length).toFixed(2) : '—' })(),
}))

async function load() {
  jobs.value = await get('/api/jobs')
  approvals.value = await get('/api/approvals')
}
const job = computed(() => jobs.value.find(j => j.id === cur.value))
const dec = computed(() => { try { return JSON.parse(job.value?.decision_json || '{}') } catch { return {} } })
const feats = computed(() => { try { return JSON.parse(job.value?.features_json || '{}') } catch { return {} } })

async function submit() {
  if (!title.value.trim()) return
  const r = await post('/api/run', { title: title.value.trim(), description: desc.value.trim() })
  cur.value = r.job_id; title.value = ''; desc.value = ''
  await load()
}
function sealStatus(s) { return s === 'done' ? {t:'已盖章',c:'ok'} : s === 'awaiting_approval' ? {t:'待盖章',c:'warn'} : {t:'处理中',c:'muted'} }
onMounted(load)
</script>

<template>
  <div>
    <div class="strip">
      <div class="stat"><div class="k">进行中</div><div class="v">{{ stats.running }}</div></div>
      <div class="stat warn"><div class="k">待盖章</div><div class="v">{{ stats.approvals }}</div></div>
      <div class="stat ok"><div class="k">已完成</div><div class="v">{{ stats.done }}</div></div>
      <div class="stat"><div class="k">平均分</div><div class="v">{{ stats.avg }}</div></div>
      <div class="stat budget"><div class="k">订单预算</div><div class="bar"><i></i></div></div>
    </div>
    <div class="split">
      <div class="paper queue">
        <div class="q-h"><span>工单</span><span>点选查看</span></div>
        <button v-for="j in jobs" :key="j.id" class="ticket" :class="{on: cur===j.id}" @click="cur=j.id">
          <div class="t">{{ j.title }}</div>
          <div class="m">{{ j.id }} · {{ j.task_type }} · {{ j.status }}</div>
        </button>
        <p v-if="!jobs.length" style="color:var(--muted);padding:8px">还没有工单，先新建。</p>
      </div>
      <div>
        <article class="paper form-panel" v-if="job">
          <div class="meta"><span>{{ job.id }}</span><span>{{ job.task_type }}</span></div>
          <span class="seal" :class="sealStatus(job.status).c">{{ sealStatus(job.status).t }}</span>
          <h1>{{ job.title }}</h1>
          <div class="fields">
            <div><span class="lab">主 worker</span>{{ dec.worker || '-' }}</div>
            <div><span class="lab">拆分</span>{{ dec.split ? '是' : '否' }}</div>
            <div><span class="lab">优先级</span>{{ (dec.priority_order || []).join(' → ') }}</div>
            <div><span class="lab">预算</span>${{ dec.budget_usd || '-' }}</div>
          </div>
          <div class="reason">{{ dec.reason }}<div class="src">{{ dec.source }}</div></div>
          <div class="chips"><span v-for="(v,k) in feats" :key="k">{{ k }}:{{ Array.isArray(v)?v.join('|'):v }}</span></div>
          <div class="row">
            <button class="btn sm" @click="emit('navigate','jobs')">打开任务</button>
            <button class="btn sm" style="background:none;border:1px solid var(--line)" @click="emit('navigate','eval')">看评测</button>
          </div>
        </article>
        <div class="panel" style="background:#fff;margin-top:14px">
          <b>新建工单</b>
          <input v-model="title" placeholder="标题，如：批量抠图小程序" style="margin-top:8px">
          <textarea v-model="desc" rows="2" placeholder="需求（可选）"></textarea>
          <button class="btn stamp" @click="submit">抽取特征并决策</button>
        </div>
      </div>
    </div>
  </div>
</template>
