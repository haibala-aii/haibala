<script setup>
import { ref, onMounted, watch } from 'vue'
import { get, post } from '../api.js'
import { tick } from '../live.js'
const rows = ref([])
async function load() { rows.value = await get('/api/approvals') }
async function decide(id, d) { await post('/api/approve', { id, decision: d }); await load() }
onMounted(load)
watch(tick, load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>待确认</h1>
        <p class="sub">这里是超支或高成本的事后确认。活已经干完，盖的是花费记录，不是派活许可。</p>
      </div>
    </div>
    <div class="alert" v-for="a in rows" :key="a.id">
      <b>{{ a.action }}</b>
      <p class="muted">{{ a.reason }} · {{ a.worker }} · {{ a.job_id }}</p>
      <div class="row">
        <button class="btn pri sm" @click="decide(a.id,'approve')">确认记录</button>
        <button class="btn bad sm" @click="decide(a.id,'deny')">标为否认</button>
      </div>
    </div>
    <p v-if="!rows.length" class="muted">没有待确认项。</p>
  </div>
</template>
