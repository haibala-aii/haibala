<script setup>
import { ref, computed, inject, watch } from 'vue'
import { statusMeta, budgetPct, decisionOf } from '../util.js'

const shell = inject('shell')
const tab = ref('all')
const q = ref('')
const sort = ref('new')

const jobs = computed(() => shell.jobs.value || [])
const counts = computed(() => ({
  all: jobs.value.length,
  wait: jobs.value.filter(j => j.status === 'awaiting_decision' || j.status === 'awaiting_manual').length,
  run: jobs.value.filter(j => j.status === 'running').length,
  done: jobs.value.filter(j => j.status === 'done').length,
}))
const list = computed(() => {
  let rows = jobs.value
  if (tab.value === 'wait') rows = rows.filter(j => ['awaiting_decision','awaiting_manual','awaiting_approval'].includes(j.status))
  if (tab.value === 'run') rows = rows.filter(j => j.status === 'running' || j.status === 'interrupted')
  if (tab.value === 'done') rows = rows.filter(j => j.status === 'done' || j.status === 'rejected')
  const s = q.value.trim()
  if (s) rows = rows.filter(j => (j.title || '').includes(s) || (j.id || '').includes(s))
  rows = [...rows]
  if (sort.value === 'new') rows.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  return rows
})

watch(() => shell.view.value, v => { if (v === 'dash') shell.load() })
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>工单库</h1>
        <p class="sub">整理接单、看决策、盖章后再派活。同一份考卷也可以拉去同场比试。</p>
      </div>
      <svg class="stamp-art" viewBox="0 0 120 88" aria-hidden="true">
        <rect x="8" y="18" width="70" height="52" rx="8" fill="#f4f4f6" stroke="#e5e5e8"/>
        <rect x="16" y="28" width="40" height="6" rx="3" fill="#d4d4d8"/>
        <rect x="16" y="40" width="28" height="6" rx="3" fill="#e4e4e7"/>
        <circle cx="92" cy="44" r="22" fill="none" stroke="#c81e5c" stroke-width="3"/>
        <text x="92" y="49" text-anchor="middle" font-size="11" font-weight="700" fill="#c81e5c">章</text>
      </svg>
    </div>
    <div class="actions">
      <button class="btn pri" @click="shell.openCompose()">+ 新建工单</button>
    </div>
    <div style="display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap">
      <div class="tabs" style="flex:1;margin-bottom:0">
        <button :class="{on: tab==='all'}" @click="tab='all'">全部 {{ counts.all }}</button>
        <button :class="{on: tab==='wait'}" @click="tab='wait'">待处理 {{ counts.wait }}</button>
        <button :class="{on: tab==='run'}" @click="tab='run'">进行中 {{ counts.run }}</button>
        <button :class="{on: tab==='done'}" @click="tab='done'">已完成 {{ counts.done }}</button>
      </div>
      <div class="utils" style="margin:0">
        <input class="search" v-model="q" placeholder="搜索工单">
        <select v-model="sort" style="width:auto;margin:0;border-radius:999px">
          <option value="new">最近创建</option>
        </select>
      </div>
    </div>
    <div class="cards" style="margin-top:18px">
      <button class="pcard" v-for="j in list" :key="j.id" @click="shell.openJob(j.id)">
        <div class="thumb">
          <span class="seal" :class="statusMeta(j.status).k">{{ statusMeta(j.status).t }}</span>
        </div>
        <div class="meta">
          <div class="t">{{ j.title }}</div>
          <div class="m">{{ j.task_type || '—' }} · {{ decisionOf(j).worker || '未派' }} · 花费 ${{ (j.spent_usd || 0).toFixed(2) }} / ${{ (j.budget_usd || 5) }}</div>
          <div class="bar-track" style="margin-top:8px"><i :style="{width: budgetPct(j)+'%'}"></i></div>
        </div>
      </button>
    </div>
    <p v-if="!list.length" class="muted" style="padding:32px 0">这一栏还是空的。点「新建工单」出一份决策。</p>
  </div>
</template>
