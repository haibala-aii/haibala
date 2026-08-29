<script setup>
import { ref } from 'vue'
import Dash from './views/Dash.vue'
import Jobs from './views/Jobs.vue'
import Eval from './views/Eval.vue'
import Audit from './views/Audit.vue'
import Approvals from './views/Approvals.vue'
import Settings from './views/Settings.vue'

const view = ref('dash')
const tabs = [
  { id: 'dash', label: '总览' },
  { id: 'jobs', label: '任务' },
  { id: 'eval', label: '评测' },
  { id: 'audit', label: '审计' },
  { id: 'approvals', label: '审批' },
  { id: 'settings', label: '设置' },
]
const views = { dash: Dash, jobs: Jobs, eval: Eval, audit: Audit, approvals: Approvals, settings: Settings }
</script>

<template>
  <div class="app">
    <header class="bar">
      <div class="brand"><b>haibala</b><span>签发台 · Vue</span></div>
      <div class="live"><span class="dot" aria-hidden="true"></span>核心在线 · 本地 · 数据不出机</div>
    </header>
    <nav class="tabs">
      <a v-for="t in tabs" :key="t.id" :class="{on: view===t.id}" @click="view=t.id">
        {{ t.label }}<span v-if="t.id==='approvals'" class="count" id="apc">{{ '' }}</span>
      </a>
    </nav>
    <component :is="views[view]" @navigate="view=$event" />
  </div>
</template>
