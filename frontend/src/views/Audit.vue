<script setup>
import { ref, onMounted, watch } from 'vue'
import { get } from '../api.js'
import { tick } from '../live.js'
const rows = ref([])
async function load() { rows.value = await get('/api/audit') }
onMounted(load)
watch(tick, load)
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>审计</h1>
        <p class="sub">谁在何时做了什么。只增不改，用来回放决策和派活。</p>
      </div>
    </div>
    <ul class="audit">
      <li v-for="(a,i) in rows" :key="a.id || i">
        <span class="ts">{{ a.ts }}</span><span class="tg">{{ a.action }}</span><span>{{ a.detail }}</span>
      </li>
      <li v-if="!rows.length"><span class="ts">—</span><span class="tg"></span><span>暂无记录</span></li>
    </ul>
  </div>
</template>
