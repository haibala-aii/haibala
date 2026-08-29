<script setup>
import { ref, onMounted } from 'vue'
import { get } from '../api.js'
const rows = ref([])
onMounted(async () => { rows.value = await get('/api/audit') })
</script>

<template>
  <div class="paper panel">
    <h2>全链路审计</h2>
    <ul class="audit">
      <li v-for="(a,i) in rows" :key="i">
        <span class="ts">{{ a.ts }}</span><span class="tg">{{ a.action }}</span><span>{{ a.detail }}</span>
      </li>
      <li v-if="!rows.length"><span class="ts">—</span><span class="tg"></span><span>暂无</span></li>
    </ul>
  </div>
</template>
