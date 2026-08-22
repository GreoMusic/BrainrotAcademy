<script setup>
import { ref, onBeforeUnmount } from 'vue'
const props = defineProps({ card: Object })
const emit = defineEmits(['cleared'])

const recording = ref(false)
const busy = ref(false)
const result = ref(null)
let recorder = null
let chunks = []

async function toggle() {
  if (recording.value) return stop()
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    recorder = new MediaRecorder(stream)
    chunks = []
    recorder.ondataavailable = (e) => chunks.push(e.data)
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      send(new Blob(chunks, { type: 'audio/webm' }))
    }
    recorder.start()
    recording.value = true
  } catch {
    result.value = { pass: false, reason: 'Microphone blocked.' }
  }
}

function stop() {
  recording.value = false
  if (recorder && recorder.state !== 'inactive') recorder.stop()
}

async function send(blob) {
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('audio', blob, 'talk.webm')
    fd.append('topic', props.card.payload.topic)
    const res = await fetch('/api/friction/talk', { method: 'POST', body: fd })
    result.value = await res.json()
    if (result.value.pass) setTimeout(() => emit('cleared'), 2000)
  } catch {
    result.value = { pass: false, reason: 'Could not reach the transcriber.' }
  } finally {
    busy.value = false
  }
}

onBeforeUnmount(stop)
</script>

<template>
  <div class="card is-gate">
    <div class="card-gradient" style="--g1:#3a0d2c; --g2:#15040f" />
    <div class="eyebrow">friction</div>
    <div class="big">Find a human. Explain {{ card.payload.topic.replace('-', ' ') }} out loud.</div>
    <p class="sub">Record it. We only check that a real conversation happened.</p>

    <button class="mic" :class="{ rec: recording }" @click="toggle">
      {{ recording ? '■' : '🎤' }}
    </button>
    <div class="label">{{ recording ? 'recording — tap to stop' : busy ? 'transcribing…' : 'tap to record' }}</div>

    <div v-if="result" class="status" :class="{ good: result.pass }">
      <div>{{ result.reason }}</div>
      <div v-if="result.transcript" class="tx">“{{ result.transcript }}”</div>
    </div>

    <button class="skip" @click="emit('cleared')">Skip this one</button>
  </div>
</template>

<style scoped>
.sub { color: var(--dim); margin-top: 12px; font-size: 15px; }
.mic {
  width: 96px; height: 96px; border-radius: 50%; margin: 30px auto 12px; font-size: 36px;
  background: rgba(255,255,255,0.13); border: 2px solid rgba(255,255,255,0.22); display: block;
}
.mic.rec { background: var(--hot); border-color: transparent; animation: p 1.1s infinite; }
@keyframes p { 50% { box-shadow: 0 0 0 18px rgba(255,45,129,0.16) } }
.label { text-align: center; font-size: 13px; color: var(--dim); }
.status { margin-top: 20px; padding: 14px; border-radius: 12px; background: rgba(0,0,0,0.4); font-size: 15px; }
.status.good { background: rgba(0,229,192,0.22); }
.tx { margin-top: 8px; font-style: italic; color: var(--dim); font-size: 14px; }
.skip { margin-top: 18px; font-size: 13px; color: var(--dim); text-decoration: underline; }
</style>
