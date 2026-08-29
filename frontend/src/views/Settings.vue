<script setup>
import { ref, onMounted } from 'vue'
import { get, post } from '../api.js'

const s = ref({ workers: [], budget: {} })
const judge = ref('mock')
const defaultUsd = ref(5)
const overUsd = ref(2)
const enabled = ref({})
const declared = ref({})
const msg = ref('')
const saving = ref(false)

async function load() {
  s.value = await get('/api/status')
  judge.value = s.value.judge || 'mock'
  defaultUsd.value = s.value.budget?.default_usd ?? 5
  overUsd.value = s.value.budget?.approve_over_usd ?? 2
  declared.value = s.value.declared || {}
  const map = {}
  for (const [name, conf] of Object.entries(declared.value)) {
    map[name] = !!(conf && conf.enabled)
  }
  enabled.value = map
}
async function save() {
  saving.value = true; msg.value = ''
  const workers = {}
  for (const name of Object.keys(enabled.value)) {
    workers[name] = { enabled: !!enabled.value[name] }
  }
  try {
    await post('/api/settings', {
      judge: { provider: judge.value },
      budget: { default_usd: Number(defaultUsd.value), approve_over_usd: Number(overUsd.value) },
      workers,
    })
    await load()
    msg.value = '已保存。CLI 工人需本机命令在 PATH 里，否则派活时会回退 mock。'
  } catch (e) {
    msg.value = '保存失败：' + e.message
  } finally { saving.value = false }
}
onMounted(load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>设置</h1>
        <p class="sub">judge、预算阈值和是否启用真实 CLI。没配好的命令不会把核心弄崩。</p>
      </div>
    </div>
    <div class="section">
      <h2>Judge</h2>
      <select v-model="judge" style="max-width:240px">
        <option value="mock">mock（开箱演示）</option>
        <option value="api">api（需 .env 里 DEEPSEEK_API_KEY）</option>
      </select>
      <p class="muted">当前模型 {{ s.judge_model || '—' }} · {{ s.has_key ? '已配置 key' : '未配置 key，api 会回退 mock' }}</p>
    </div>
    <div class="section">
      <h2>预算</h2>
      <div class="fields" style="max-width:420px">
        <div><span class="lab">默认预算 USD</span><input type="number" v-model.number="defaultUsd" min="0" step="0.5"></div>
        <div><span class="lab">高成本确认阈值</span><input type="number" v-model.number="overUsd" min="0" step="0.1"></div>
      </div>
    </div>
    <div class="section">
      <h2>Workers</h2>
      <div class="stk" v-for="(conf, name) in declared" :key="name">
        <div>
          <b>{{ name }}</b>
          <div class="muted">{{ conf.type || 'cli' }} · {{ (conf.capability||[]).join(', ') }}</div>
        </div>
        <label class="muted">
          <input type="checkbox" v-model="enabled[name]"> 启用真实接入
        </label>
      </div>
      <p class="muted" style="margin-top:8px">当前注册：{{ (s.workers||[]).map(w => w.name + '/' + w.kind).join(' · ') }}</p>
    </div>
    <div class="row">
      <button class="btn pri" :disabled="saving" @click="save">保存设置</button>
      <span class="muted">{{ msg }}</span>
    </div>
  </div>
</template>
