<script setup>
import { ref } from 'vue'
import { post } from '../api.js'
const sessionId = ref('s-' + Math.random().toString(36).slice(2))
const messages = ref([{ role: 'agent', text: '直接说你想做什么。我会先出决策，你说「开始」才盖章派活。' }])
const input = ref('')
const busy = ref(false)
async function send() {
  const t = input.value.trim(); if (!t) return
  messages.value.push({ role: 'user', text: t }); input.value = ''; busy.value = true
  try {
    const r = await post('/api/chat', { session_id: sessionId.value, text: t })
    messages.value.push({ role: 'agent', text: r.reply || '(无回复)' })
  } catch (e) {
    messages.value.push({ role: 'agent', text: '出错：' + e.message })
  } finally { busy.value = false }
}
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <h1>对话</h1>
        <p class="sub">用自然语言拆任务。队长只给草案，不会擅自派活。</p>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;min-height:calc(100vh - 220px)">
      <div style="flex:1;overflow:auto;padding:4px 0">
        <div v-for="(m,i) in messages" :key="i" style="display:flex;margin:8px 0" :style="{justifyContent:m.role==='user'?'flex-end':'flex-start'}">
          <div v-if="m.role==='agent'" class="reason" style="max-width:82%">{{ m.text }}</div>
          <div v-if="m.role==='user'" style="max-width:82%;background:#111;color:#fff;border-radius:12px;padding:10px 12px;white-space:pre-wrap">{{ m.text }}</div>
        </div>
      </div>
      <div class="row">
        <input type="text" v-model="input" placeholder="例如：做个批量抠图小程序" @keyup.enter="send" style="margin:0;flex:1">
        <button class="btn pri" :disabled="busy" @click="send">发送</button>
      </div>
    </div>
  </div>
</template>
