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
  if (recording.value) {
    recording.value = false
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    return
  }
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

async function send(blob) {
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('audio', blob, 'talk.webm')
    fd.append('topic', props.card.payload.topic)
    const res = await fetch('/api/friction/talk', { method: 'POST', body: fd })
    result.value = await res.json()
    if (result.value.pass) setTimeout(() => emit('cleared'), 1900)
  } catch {
    result.value = { pass: false, reason: 'Could not reach the transcriber.' }
  } finally {
    busy.value = false
  }
}

onBeforeUnmount(() => {
  if (recorder && recorder.state !== 'inactive') recorder.stop()
})
</script>

<template>
  <div class="card reel">
    <div class="reel-bg" style="filter: blur(6px)">🗣️</div>
    <div class="reel-scrim-top" />

    <div class="budget">
      <div class="budget-row"><span>SCROLL BUDGET</span><span>0 left</span></div>
      <div class="budget-track"><div class="budget-fill" style="width: 0%" /></div>
    </div>

    <div class="sheet-overlay">
      <div class="sheet">
        <div class="sheet-handle" />
        <p class="gate-title" style="text-align: center">Go say it to a real person</p>
        <p class="gate-sub" style="text-align: center">
          Explain {{ card.payload.topic.replace('-', ' ') }} out loud to someone. Record it here.
        </p>

        <button class="mic" :class="{ rec: recording }" :disabled="busy" @click="toggle">
          {{ recording ? '■' : '🎤' }}
        </button>
        <div class="label">
          {{ recording ? 'recording — tap to stop' : busy ? 'transcribing…' : 'tap to record' }}
        </div>

        <div v-if="result" class="status" :class="{ good: result.pass }">
          <div>{{ result.reason }}</div>
          <div v-if="result.transcript" class="tx">“{{ result.transcript }}”</div>
        </div>

        <div class="link-row"><span @click="emit('cleared')">Skip this one</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mic {
  width: 74px; height: 74px; border-radius: 50%; margin: 16px auto 10px; display: block;
  font-size: 28px; background: #f2f2f2; border: 1px solid var(--border);
}
.mic.rec { background: var(--ig-gradient); border-color: transparent; color: #fff; animation: p 1.1s infinite; }
@keyframes p { 50% { box-shadow: 0 0 0 14px rgba(214, 41, 118, 0.12) } }
.label { text-align: center; font-size: 11.5px; color: var(--dim); }
.status { margin-top: 14px; padding: 11px; border-radius: 10px; background: #f7f7f7; font-size: 12.5px; color: #555; }
.status.good { background: rgba(0, 149, 246, 0.09); color: var(--blue); }
.tx { margin-top: 6px; font-style: italic; color: var(--dim); font-size: 11.5px; }
</style>
