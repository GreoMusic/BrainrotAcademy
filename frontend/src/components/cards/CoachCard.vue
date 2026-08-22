<script setup>
import { ref, nextTick, onBeforeUnmount } from 'vue'

const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['answered'])

const messages = ref([
  { role: 'assistant', content: props.card.payload.opener || 'Explain it to me in your own words.' },
])
const draft = ref('')
const busy = ref(false)
const recording = ref(false)
const verdict = ref(null)
const scroller = ref(null)

let recorder = null
let chunks = []
let audioEl = null

function scrollDown() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}

function handle(data) {
  if (data.error) {
    messages.value.push({ role: 'assistant', content: 'Coach is offline: ' + data.error })
    return
  }
  if (data.transcript) messages.value.push({ role: 'user', content: data.transcript })
  messages.value.push({ role: 'assistant', content: data.reply })
  scrollDown()

  if (data.audio) {
    audioEl = new Audio(data.audio)
    audioEl.play().catch(() => {})
  }

  if (data.done) {
    verdict.value = data.understood
    setTimeout(() => emit('answered', !!data.understood), 2600)
  }
}

async function sendText() {
  const text = draft.value.trim()
  if (!text || busy.value) return
  messages.value.push({ role: 'user', content: text })
  draft.value = ''
  busy.value = true
  scrollDown()
  try {
    const res = await fetch('/api/coach/turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        topic: props.card.payload.topic,
        history: messages.value.slice(0, -1),
        audio_reply: true,
      }),
    })
    handle(await res.json())
  } catch {
    messages.value.push({ role: 'assistant', content: 'Could not reach the coach.' })
  } finally {
    busy.value = false
  }
}

async function toggleMic() {
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
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      busy.value = true
      try {
        const fd = new FormData()
        fd.append('audio', new Blob(chunks, { type: 'audio/webm' }), 'turn.webm')
        fd.append('topic', props.card.payload.topic)
        fd.append('history', JSON.stringify(messages.value))
        const res = await fetch('/api/coach/turn', { method: 'POST', body: fd })
        handle(await res.json())
      } catch {
        messages.value.push({ role: 'assistant', content: 'Could not reach the coach.' })
      } finally {
        busy.value = false
      }
    }
    recorder.start()
    recording.value = true
  } catch {
    messages.value.push({ role: 'assistant', content: 'Microphone blocked - type instead.' })
  }
}

onBeforeUnmount(() => {
  if (audioEl) audioEl.pause()
  if (recorder && recorder.state !== 'inactive') recorder.stop()
})
</script>

<template>
  <div class="card is-gate coach">
    <div class="card-gradient" style="--g1: #1d0b3d; --g2: #07040f" />
    <div class="eyebrow">talk it through to keep scrolling</div>

    <div class="thread" ref="scroller">
      <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
        <span>{{ m.content }}</span>
      </div>
      <div v-if="busy" class="msg assistant typing"><span>· · ·</span></div>
    </div>

    <transition name="fade">
      <div v-if="verdict !== null" class="verdict" :class="{ good: verdict }">
        {{ verdict ? 'You have got it. Scroll on.' : 'Not quite yet — back to the cards.' }}
      </div>
    </transition>

    <div v-if="verdict === null" class="composer">
      <input
        v-model="draft" class="in" placeholder="say it in your own words…"
        :disabled="busy" @keyup.enter="sendText"
      />
      <button class="mic" :class="{ rec: recording }" :disabled="busy" @click="toggleMic">
        {{ recording ? '■' : '🎤' }}
      </button>
      <button class="send" :disabled="busy || !draft.trim()" @click="sendText">↑</button>
    </div>
  </div>
</template>

<style scoped>
.coach { justify-content: flex-start; padding-top: 92px; }
.thread {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 8px 0 14px;
  scrollbar-width: none;
}
.thread::-webkit-scrollbar { display: none; }
.msg { display: flex; }
.msg span {
  max-width: 84%;
  padding: 12px 15px;
  border-radius: 18px;
  font-size: 16px;
  line-height: 1.4;
}
.msg.assistant { justify-content: flex-start; }
.msg.assistant span {
  background: rgba(255, 255, 255, 0.13);
  border-bottom-left-radius: 5px;
}
.msg.user { justify-content: flex-end; }
.msg.user span {
  background: var(--accent);
  border-bottom-right-radius: 5px;
}
.typing span { opacity: 0.6; letter-spacing: 3px; }

.composer { display: flex; gap: 8px; align-items: center; }
.in {
  flex: 1;
  padding: 14px 16px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.4);
  border: 1.5px solid rgba(255, 255, 255, 0.18);
  color: var(--fg);
  font-size: 15px;
}
.mic, .send {
  width: 46px; height: 46px; border-radius: 50%; flex: none;
  background: rgba(255, 255, 255, 0.13);
  border: 1.5px solid rgba(255, 255, 255, 0.18);
  font-size: 17px; font-weight: 800;
}
.mic.rec { background: var(--hot); border-color: transparent; animation: p 1.1s infinite; }
@keyframes p { 50% { box-shadow: 0 0 0 14px rgba(255, 45, 129, 0.15) } }
.send:disabled, .mic:disabled { opacity: 0.4; }

.verdict {
  padding: 15px; border-radius: 14px; font-weight: 700;
  background: rgba(255, 45, 129, 0.22); border: 1.5px solid var(--hot);
}
.verdict.good { background: rgba(0, 229, 192, 0.2); border-color: var(--accent-2); }
</style>
