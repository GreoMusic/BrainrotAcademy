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
const confetti = ref([])

let recorder = null
let chunks = []
let audioEl = null

const CONFETTI_COLORS = ['#fb923c', '#a855f7', '#22c55e', '#3b82f6', '#ec4899', '#facc15']

function burstConfetti() {
  confetti.value = Array.from({ length: 28 }, (_, i) => ({
    id: i,
    left: Math.random() * 100,
    delay: Math.random() * 0.3,
    duration: 1.6 + Math.random() * 0.9,
    color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
    drift: Math.round((Math.random() - 0.5) * 60),
    rotate: Math.round(Math.random() * 360),
  }))
}

function scrollDown() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}

function handle(data) {
  if (data.error) {
    messages.value.push({ role: 'assistant', content: 'Coach is offline: ' + data.error })
    scrollDown()
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
    const passed = !!data.understood
    verdict.value = passed
    // Let the confetti actually land before the feed pulls them away.
    if (passed) burstConfetti()
    setTimeout(() => emit('answered', passed), 2800)
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
    messages.value.push({ role: 'assistant', content: 'Microphone blocked — type instead.' })
  }
}

onBeforeUnmount(() => {
  if (audioEl) audioEl.pause()
  if (recorder && recorder.state !== 'inactive') recorder.stop()
})
</script>

<template>
  <!-- Passing the coach is the moment worth celebrating, so it takes over the
       whole screen the way the design's verdict view does. -->
  <div v-if="verdict !== null" class="card verdict-screen">
    <div v-if="verdict" class="confetti-layer">
      <span
        v-for="p in confetti" :key="p.id" class="confetti-piece"
        :style="{
          left: p.left + '%',
          animationDelay: p.delay + 's',
          animationDuration: p.duration + 's',
          backgroundColor: p.color,
          '--drift': p.drift + 'px',
          '--rotate': p.rotate + 'deg',
        }"
      />
    </div>
    <div class="verdict-ring">
      <div class="inner">{{ verdict ? '✓' : '↺' }}</div>
    </div>
    <div class="verdict-title">{{ verdict ? "You're verified" : 'Not yet' }}</div>
    <div class="verdict-sub">
      {{ verdict
        ? 'Real understanding, not a bluff. Back to the feed.'
        : 'Close, but the idea is not there yet. One more learning round.' }}
    </div>
  </div>

  <div v-else class="card lightscreen">
    <div class="appbar">
      <div class="who">
        <div class="pfp">🤖</div>
        <div>
          <div class="name">coach</div>
          <div class="status">active now</div>
        </div>
      </div>
      <span class="pill blue" style="margin: 0">enrollment check</span>
    </div>

    <div class="content">
      <div class="chat-area" ref="scroller">
        <div v-for="(m, i) in messages" :key="i" class="bubble" :class="m.role === 'user' ? 'me' : 'them'">
          {{ m.content }}
        </div>
        <div v-if="busy" class="bubble them typing">· · ·</div>
      </div>

      <div class="composer">
        <input
          v-model="draft" class="in" placeholder="say it in your own words…"
          :disabled="busy" @keyup.enter="sendText"
        />
        <button class="round" :class="{ rec: recording }" :disabled="busy" @click="toggleMic">
          {{ recording ? '■' : '🎤' }}
        </button>
        <button class="round send" :disabled="busy || !draft.trim()" @click="sendText">↑</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.who { display: flex; align-items: center; gap: 10px; }
.pfp {
  width: 32px; height: 32px; border-radius: 50%; background: #eee;
  display: flex; align-items: center; justify-content: center; font-size: 15px;
}
.name { font-size: 13px; font-weight: 700; }
.status { font-size: 10.5px; color: var(--dim); }
.typing { opacity: 0.65; letter-spacing: 3px; }

.composer { display: flex; gap: 7px; align-items: center; }
.in {
  flex: 1; padding: 11px 14px; border-radius: 999px;
  background: #fff; border: 1px solid var(--border); font-size: 13px;
}
.in:focus { outline: none; border-color: var(--blue); }
.round {
  width: 40px; height: 40px; border-radius: 50%; flex: none; font-size: 15px; font-weight: 700;
  background: #f2f2f2; border: 1px solid var(--border);
}
.round.send { background: var(--blue); color: #fff; border-color: transparent; }
.round.rec { background: var(--ig-gradient); color: #fff; border-color: transparent; }
.round:disabled { opacity: 0.45; }

.confetti-layer { position: absolute; inset: 0; overflow: hidden; pointer-events: none; z-index: 5; }
.confetti-piece {
  position: absolute;
  top: -12px;
  width: 8px;
  height: 14px;
  border-radius: 2px;
  opacity: 0.95;
  animation-name: confetti-fall;
  animation-timing-function: cubic-bezier(0.35, 0, 0.65, 1);
  animation-fill-mode: forwards;
}
@keyframes confetti-fall {
  0% { transform: translate(0, 0) rotate(0deg); opacity: 1; }
  100% { transform: translate(var(--drift), 460px) rotate(var(--rotate)); opacity: 0; }
}
</style>
