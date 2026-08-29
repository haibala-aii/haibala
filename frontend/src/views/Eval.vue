<script setup>
import { ref, computed, onMounted } from 'vue'
import { get } from '../api.js'

const lb = ref([])
const lr = ref({})
const maxAvg = computed(() => Math.max(5, ...lb.value.map(x => Number(x.avg_score) || 0)))
const maxN = computed(() => Math.max(1, ...lb.value.map(x => Number(x.samples) || 0)))
const accPct = computed(() => lr.value.accuracy == null ? null : Math.round(lr.value.accuracy * 100))

onMounted(async () => {
  lb.value = await get('/api/leaderboard')
  lr.value = await get('/api/learning')
})
function barW(score) { return Math.max(4, Math.round((Number(score) / maxAvg.value) * 100)) + '%' }
function sampleW(n) { return Math.max(8, Math.round((Number(n) / maxN.value) * 100)) + '%' }
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>评测</h1>
        <p class="sub">跨任务榜单和画像。分数来自盖章派活之后的产物，不是拍脑袋。</p>
      </div>
    </div>
    <div class="section">
      <h2>Rubric · 编码/图像（带锚点）</h2>
      <div class="chips">
        <span>功能正确性 · 0.40</span>
        <span>代码质量 · 0.25</span>
        <span>可复用性 · 0.20</span>
        <span>成本/耗时 · 0.15</span>
      </div>
    </div>
    <div class="section">
      <h2>跨任务榜单</h2>
      <p class="muted" style="margin-bottom:12px">横条是平均加权分（满分 5）。</p>
      <div v-if="lb.length">
        <div v-for="x in lb" :key="x.worker" style="display:grid;grid-template-columns:88px 1fr auto;gap:10px;align-items:center;margin-bottom:10px">
          <span>{{ x.worker }}</span>
          <div class="bar-track"><i :style="{ width: barW(x.avg_score) }"></i></div>
          <span>{{ x.avg_score }} <span class="muted">峰值 {{ x.best_score }}</span></span>
        </div>
      </div>
      <p v-else class="muted">暂无数据。先盖章跑几个任务。</p>
    </div>
    <div class="section">
      <h2>Agent 画像</h2>
      <div v-if="lb.length" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px">
        <div v-for="x in lb" :key="'p-'+x.worker" class="stk">
          <svg viewBox="0 0 72 72" width="72" height="72" aria-hidden="true">
            <circle cx="36" cy="36" r="28" fill="none" stroke="#ececef" stroke-width="8"/>
            <circle cx="36" cy="36" r="28" fill="none" stroke="#c81e5c" stroke-width="8"
              stroke-linecap="round"
              :stroke-dasharray="2 * Math.PI * 28"
              :stroke-dashoffset="2 * Math.PI * 28 * (1 - Math.min(1, x.avg_score / 5))"
              transform="rotate(-90 36 36)"/>
            <text x="36" y="40" text-anchor="middle" font-size="14" font-weight="700" fill="#111">{{ x.avg_score }}</text>
          </svg>
          <div>
            <b>{{ x.worker }}</b>
            <div class="bar-track" style="margin-top:6px"><i :style="{ width: sampleW(x.samples) }"></i></div>
            <div class="muted">{{ x.samples }} 次评测 · 最好 {{ x.best_score }}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="section">
      <h2>它学会了什么 · {{ lr.model || '—' }}{{ accPct != null ? ' · 准确率 ' + accPct + '%' : '' }}</h2>
      <div v-if="accPct != null" class="bar-track" style="margin-bottom:12px"><i :style="{ width: accPct + '%' }"></i></div>
      <table v-if="lr.predicts && lr.predicts.length">
        <tr><th>任务类型</th><th>它认为该用</th></tr>
        <tr v-for="p in lr.predicts" :key="p.task_type"><td>{{ p.task_type }}</td><td><b>{{ p.best_worker }}</b></td></tr>
      </table>
      <p v-else class="muted">还在冷启动。多跑几个任务后会出现「什么类型 → 用谁」。</p>
    </div>
  </div>
</template>
