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

function barW(score) {
  return Math.max(4, Math.round((Number(score) / maxAvg.value) * 100)) + '%'
}
function sampleW(n) {
  return Math.max(8, Math.round((Number(n) / maxN.value) * 100)) + '%'
}
</script>

<template>
  <div>
    <div class="paper panel">
      <h2>Rubric · 编码/图像（带锚点）</h2>
      <div class="chips">
        <span>功能正确性 · 0.40</span>
        <span>代码质量 · 0.25</span>
        <span>可复用性 · 0.20</span>
        <span>成本/耗时 · 0.15</span>
      </div>
    </div>

    <div class="paper panel">
      <h2>跨任务榜单</h2>
      <p class="desc" style="margin-bottom:12px">横条是平均加权分（满分按 5 计）。右侧数字是峰值。</p>
      <div v-if="lb.length" class="chart">
        <div class="bar-row" v-for="x in lb" :key="x.worker">
          <span class="bar-lab">{{ x.worker }}</span>
          <div class="track" :title="'均分 ' + x.avg_score">
            <i :style="{ width: barW(x.avg_score) }"></i>
          </div>
          <span class="bar-num">{{ x.avg_score }} <em>峰值 {{ x.best_score }}</em></span>
        </div>
      </div>
      <p v-else class="desc">暂无数据。先跑几个任务。</p>
    </div>

    <div class="paper panel">
      <h2>Agent 画像</h2>
      <p class="desc" style="margin-bottom:12px">圆环是均分；底条是样本数（评过几次）。</p>
      <div v-if="lb.length" class="portraits">
        <div class="portrait" v-for="x in lb" :key="'p-'+x.worker">
          <svg viewBox="0 0 72 72" width="72" height="72" aria-hidden="true">
            <circle cx="36" cy="36" r="28" fill="none" stroke="#dce0e6" stroke-width="8"/>
            <circle cx="36" cy="36" r="28" fill="none" stroke="#c81e5c" stroke-width="8"
              stroke-linecap="round"
              :stroke-dasharray="2 * Math.PI * 28"
              :stroke-dashoffset="2 * Math.PI * 28 * (1 - Math.min(1, x.avg_score / 5))"
              transform="rotate(-90 36 36)"/>
            <text x="36" y="40" text-anchor="middle" font-size="14" font-weight="700" fill="#141820">{{ x.avg_score }}</text>
          </svg>
          <div>
            <b>{{ x.worker }}</b>
            <div class="sample-track"><i :style="{ width: sampleW(x.samples) }"></i></div>
            <div class="desc">{{ x.samples }} 次评测 · 最好 {{ x.best_score }}</div>
          </div>
        </div>
      </div>
      <p v-else class="desc">画像会随评测累积。</p>
    </div>

    <div class="paper panel">
      <h2>它学会了什么 · {{ lr.model || '—' }}{{ accPct != null ? ' · 准确率 ' + accPct + '%' : '' }} · 学习 {{ lr.history || 0 }} 次</h2>
      <div v-if="accPct != null" class="acc-track" :title="'训练集准确率'">
        <i :style="{ width: accPct + '%' }"></i>
      </div>
      <table v-if="lr.predicts && lr.predicts.length" style="margin-top:12px">
        <tr><th>任务类型</th><th>它认为该用</th></tr>
        <tr v-for="p in lr.predicts" :key="p.task_type"><td>{{ p.task_type }}</td><td><b>{{ p.best_worker }}</b></td></tr>
      </table>
      <p v-else class="desc">还在学习（冷启动）。多跑几个任务后，这里会给出「什么类型 → 用谁」。</p>
      <p class="desc" style="margin-top:8px">路由：有 sklearn 用逻辑回归，否则 softmax，再否则线性策略。</p>
    </div>
  </div>
</template>
