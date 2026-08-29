<script setup>
import { ref, onMounted } from 'vue'
import { get, post } from '../api.js'
const rows = ref([])
async function load() { rows.value = await get('/api/approvals') }
async function decide(id, d) { await post('/api/approve', { id, decision: d }); await load() }
onMounted(load)
</script>

<template>
  <div class="paper panel">
    <h2>待你盖章</h2>
    <div class="alert" v-for="a in rows" :key="a.id">
      <b>{{ a.action }}</b>
      <p class="desc">{{ a.reason }} · {{ a.worker }} · {{ a.job_id }}</p>
      <div class="row">
        <button class="btn sm" @click="decide(a.id,'approve')">批准</button>
        <button class="btn sm bad" @click="decide(a.id,'deny')">拒绝</button>
      </div>
    </div>
    <p v-if="!rows.length" style="color:var(--muted)">没有待盖章项。</p>
  </div>
</template>
