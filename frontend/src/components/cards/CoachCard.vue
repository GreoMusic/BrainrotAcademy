<script setup>
import { reactive, ref, nextTick, onBeforeUnmount } from 'vue'
import ConversationChallenge from '../ConversationChallenge.vue'

const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['answered', 'recovered'])

const messages = ref([
  { role: 'assistant', content: props.card.payload.opener || 'Explain it to me in your own words.' },
])
const busy = ref(false)
const streamingReply = ref(false)
const recording = ref(false)
const connecting = ref(false)
const finalizing = ref(false)
const liveTranscript = ref('')
const liveStatus = ref('')
const verdict = ref(null)
const scroller = ref(null)
const confetti = ref([])
const recoveryMode = ref(null)
const recoveryBusy = ref(false)
const recoveryVerdict = ref(null)
const recoveryPreview = ref(null)
const recoveryFile = ref(null)

let socket = null
let mediaStream = null
let audioContext = null
let sourceNode = null
let processorNode = null
let silentGain = null
let silenceTimer = null
let finishTimer = null
let heardSpeech = false
let lastSpeechAt = 0
let ended = false
let normalSocketClose = false
let playbackContext = null
let playbackGain = null
let nextPlaybackAt = 0
const playbackSources = new Set()
const voiceUrls = new Set()
let replayAudio = null

const SILENCE_MS = 3000

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

async function ensurePlaybackContext() {
  if (!playbackContext || playbackContext.state === 'closed') {
    playbackContext = new AudioContext()
    playbackGain = playbackContext.createGain()
    playbackGain.gain.value = 1.6
    playbackGain.connect(playbackContext.destination)
    nextPlaybackAt = playbackContext.currentTime
  }
  if (playbackContext.state === 'suspended') await playbackContext.resume()
  if (playbackContext.state !== 'running') throw new Error('Audio playback is suspended')
  return playbackContext
}

async function queuePcm(encoded, sampleRate) {
  const context = await ensurePlaybackContext()

  const raw = atob(encoded)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  const samples = new Float32Array(bytes.buffer)
  const buffer = context.createBuffer(1, samples.length, sampleRate)
  buffer.copyToChannel(samples)

  const source = context.createBufferSource()
  source.buffer = buffer
  source.connect(playbackGain)
  const startsAt = Math.max(nextPlaybackAt, context.currentTime + 0.06)
  source.start(startsAt)
  nextPlaybackAt = startsAt + buffer.duration
  playbackSources.add(source)
  source.onended = () => playbackSources.delete(source)
}

function stopPlayback() {
  playbackSources.forEach((source) => {
    try { source.stop() } catch {}
  })
  playbackSources.clear()
  if (playbackContext) playbackContext.close().catch(() => {})
  playbackContext = null
  playbackGain = null
  nextPlaybackAt = 0
}

function wavUrl(chunks, sampleRate) {
  const pcmBytes = chunks.reduce((total, chunk) => total + chunk.length, 0)
  const wav = new ArrayBuffer(44 + pcmBytes)
  const view = new DataView(wav)
  const ascii = (offset, value) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i))
  }
  ascii(0, 'RIFF')
  view.setUint32(4, 36 + pcmBytes, true)
  ascii(8, 'WAVE')
  ascii(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 3, true) // IEEE float PCM
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 4, true)
  view.setUint16(32, 4, true)
  view.setUint16(34, 32, true)
  ascii(36, 'data')
  view.setUint32(40, pcmBytes, true)
  const output = new Uint8Array(wav, 44)
  let offset = 0
  for (const chunk of chunks) {
    output.set(chunk, offset)
    offset += chunk.length
  }
  const url = URL.createObjectURL(new Blob([wav], { type: 'audio/wav' }))
  voiceUrls.add(url)
  return url
}

function coachVoiceUrl(encodedChunks, sampleRate) {
  return wavUrl(encodedChunks.map((encoded) => {
    const raw = atob(encoded)
    const bytes = new Uint8Array(raw.length)
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
    return bytes
  }), sampleRate)
}

function primeVoicePlayback() {
  if (replayAudio) replayAudio.pause()
  // Keep an HTML audio element alive from the trusted microphone click. Some
  // embedded browsers reject a later AudioContext.resume(), but allow this
  // already-authorized element to swap from silence to the Voxtral reply.
  const silence = new Uint8Array(2400 * 4)
  replayAudio = new Audio(wavUrl([silence], 24000))
  replayAudio.loop = true
  replayAudio.volume = 0
  replayAudio.play().catch(() => {})
}

async function playVoiceUrl(url) {
  if (!replayAudio) replayAudio = new Audio()
  replayAudio.pause()
  replayAudio.loop = false
  replayAudio.src = url
  replayAudio.volume = 1
  await replayAudio.play()
}

function replayVoice(message) {
  if (!message.voiceUrl) return
  playVoiceUrl(message.voiceUrl).catch(() => {
    liveStatus.value = 'Tap the speaker again to play voice'
  })
}

async function askCoach(text) {
  if (!text || busy.value) return
  const history = messages.value.slice()
  messages.value.push({ role: 'user', content: text })
  busy.value = true
  let reply = null
  scrollDown()
  try {
    const res = await fetch('/api/coach/turn/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        topic: props.card.payload.topic,
        history,
      }),
    })
    if (!res.ok || !res.body) throw new Error('Coach stream unavailable')

    // Keep the local reference reactive too. Mutating the raw object that was
    // pushed into a ref array only repainted when another ref changed.
    reply = reactive({ role: 'assistant', content: '', streaming: true })
    messages.value.push(reply)
    streamingReply.value = true
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let pending = ''
    let sampleRate = 24000
    let result = null
    let voiceError = ''
    const encodedAudio = []

    while (true) {
      const { value, done } = await reader.read()
      pending += decoder.decode(value || new Uint8Array(), { stream: !done })
      const lines = pending.split('\n')
      pending = lines.pop() || ''
      for (const line of lines) {
        if (!line.trim()) continue
        const event = JSON.parse(line)
        if (event.type === 'start') sampleRate = event.sample_rate || sampleRate
        if (event.type === 'text_delta') {
          reply.content += event.text
          scrollDown()
        }
        if (event.type === 'audio') {
          encodedAudio.push(event.audio)
          if (!voiceError) {
            try {
              await queuePcm(event.audio, sampleRate)
            } catch (error) {
              voiceError = String(error?.message || error)
              stopPlayback()
            }
          }
        }
        if (event.type === 'audio_error') voiceError = event.error || 'Voxtral audio failed'
        if (event.type === 'result') result = event
      }
      if (done) break
    }

    reply.streaming = false
    if (encodedAudio.length) reply.voiceUrl = coachVoiceUrl(encodedAudio, sampleRate)
    streamingReply.value = false
    if (voiceError && reply.voiceUrl) {
      try {
        await playVoiceUrl(reply.voiceUrl)
        voiceError = ''
      } catch {
        // The visible replay button remains the final browser-permission escape hatch.
      }
    }
    if (voiceError) {
      liveStatus.value = 'Voice unavailable for this reply'
      setTimeout(() => {
        if (liveStatus.value === 'Voice unavailable for this reply') liveStatus.value = ''
      }, 3000)
    }
    const remainingMs = playbackContext
      ? Math.max(0, (nextPlaybackAt - playbackContext.currentTime) * 1000)
      : 0
    if (result?.done) {
      verdict.value = !!result.understood
      if (verdict.value) {
        // Let the confetti actually land before the feed pulls them away.
        burstConfetti()
        finishTimer = setTimeout(() => emit('answered', true), remainingMs + 1200)
      }
    }
    if (remainingMs) await new Promise((resolve) => setTimeout(resolve, remainingMs))
  } catch (error) {
    streamingReply.value = false
    if (reply) reply.streaming = false
    if (!reply?.content) messages.value.push({ role: 'assistant', content: 'Could not reach the coach.' })
    stopPlayback()
  } finally {
    busy.value = false
  }
}

function pcm16(float32) {
  const out = new Int16Array(float32.length)
  for (let i = 0; i < float32.length; i++) {
    const sample = Math.max(-1, Math.min(1, float32[i]))
    out[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
  }
  return out.buffer
}

function releaseAudio() {
  if (silenceTimer) clearInterval(silenceTimer)
  silenceTimer = null
  if (processorNode) processorNode.disconnect()
  if (sourceNode) sourceNode.disconnect()
  if (silentGain) silentGain.disconnect()
  if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop())
  if (audioContext) audioContext.close().catch(() => {})
  processorNode = null
  sourceNode = null
  silentGain = null
  mediaStream = null
  audioContext = null
}

function stopLiveMic() {
  if (!recording.value) return
  recording.value = false
  finalizing.value = true
  liveStatus.value = 'finishing transcript…'
  releaseAudio()
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'stop' }))
  }
}

async function startLiveMic() {
  try {
    connecting.value = true
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    })
    audioContext = new AudioContext({ sampleRate: 16000 })
    await audioContext.audioWorklet.addModule('/pcm-capture-worklet.js')
    sourceNode = audioContext.createMediaStreamSource(mediaStream)
    processorNode = new AudioWorkletNode(audioContext, 'pcm-capture')
    silentGain = audioContext.createGain()
    silentGain.gain.value = 0

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${location.host}/api/coach/realtime`)
    socket.binaryType = 'arraybuffer'
    normalSocketClose = false
    liveTranscript.value = ''
    heardSpeech = false
    lastSpeechAt = 0
    liveStatus.value = 'connecting to Voxtral…'

    socket.onopen = () => {
      connecting.value = false
      socket.send(JSON.stringify({ type: 'start', sample_rate: audioContext.sampleRate }))
      processorNode.port.onmessage = (event) => {
        if (socket.readyState === WebSocket.OPEN && recording.value) {
          socket.send(pcm16(event.data))
        }
      }
      sourceNode.connect(processorNode)
      processorNode.connect(silentGain)
      silentGain.connect(audioContext.destination)
      recording.value = true
      liveStatus.value = 'Start speaking'
      silenceTimer = setInterval(() => {
        if (recording.value && heardSpeech && Date.now() - lastSpeechAt >= SILENCE_MS) {
          stopLiveMic()
        }
      }, 250)
    }

    socket.onmessage = async (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'ready' && !heardSpeech) liveStatus.value = 'Start speaking'
      if (data.type === 'delta') {
        heardSpeech = true
        lastSpeechAt = Date.now()
        liveStatus.value = 'Listening…'
        liveTranscript.value += data.text
        scrollDown()
      }
      if (data.type === 'done') {
        releaseAudio()
        connecting.value = false
        recording.value = false
        finalizing.value = false
        liveStatus.value = ''
        const text = (data.text || liveTranscript.value).trim()
        liveTranscript.value = ''
        normalSocketClose = true
        socket.close()
        if (text) await askCoach(text)
      }
      if (data.type === 'error') {
        releaseAudio()
        connecting.value = false
        recording.value = false
        finalizing.value = false
        liveStatus.value = ''
        messages.value.push({ role: 'assistant', content: `Live transcription failed: ${data.error}` })
        normalSocketClose = true
        socket.close()
        scrollDown()
      }
    }

    socket.onerror = () => {
      if (normalSocketClose) return
      releaseAudio()
      connecting.value = false
      recording.value = false
      finalizing.value = false
      liveStatus.value = ''
      messages.value.push({ role: 'assistant', content: 'Live transcription is unavailable. Please try the microphone again.' })
      scrollDown()
    }
  } catch {
    connecting.value = false
    messages.value.push({ role: 'assistant', content: 'Microphone access is blocked. Allow it, then try again.' })
    releaseAudio()
  }
}

function toggleMic() {
  if (recording.value) stopLiveMic()
  else if (!connecting.value && !finalizing.value && !busy.value) {
    // Create/resume the output context while this trusted click still carries
    // browser user activation. Creating it later, when Voxtral's first chunk
    // arrives, can leave the context suspended and the reply silent.
    ensurePlaybackContext().catch(() => {})
    primeVoicePlayback()
    startLiveMic()
  }
}

function endCoaching() {
  if (ended) return
  ended = true
  stopPlayback()
  releaseAudio()
  normalSocketClose = true
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close()
  emit('answered', false)
}

function completeRecovery() {
  emit('recovered')
}

async function verifyRecoveryPhoto(event) {
  const file = event.target.files[0]
  if (!file) return
  if (recoveryPreview.value) URL.revokeObjectURL(recoveryPreview.value)
  recoveryPreview.value = URL.createObjectURL(file)
  recoveryBusy.value = true
  recoveryVerdict.value = null
  try {
    const form = new FormData()
    form.append('photo', file)
    const response = await fetch('/api/friction/touch-grass', { method: 'POST', body: form })
    recoveryVerdict.value = await response.json()
    if (!response.ok) throw new Error(recoveryVerdict.value.error || 'Could not verify the photo')
    if (recoveryVerdict.value.pass) finishTimer = setTimeout(completeRecovery, 1200)
  } catch (error) {
    recoveryVerdict.value = { pass: false, reason: error.message || 'Could not verify the photo.' }
  } finally {
    recoveryBusy.value = false
  }
}

onBeforeUnmount(() => {
  if (finishTimer) clearTimeout(finishTimer)
  stopPlayback()
  releaseAudio()
  normalSocketClose = true
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close()
  if (replayAudio) replayAudio.pause()
  voiceUrls.forEach((url) => URL.revokeObjectURL(url))
  voiceUrls.clear()
  if (recoveryPreview.value) URL.revokeObjectURL(recoveryPreview.value)
})
</script>

<template>
  <!-- Passing the coach is the moment worth celebrating, so it takes over the
       whole screen the way the design's verdict view does. -->
  <div v-if="verdict !== null" class="card verdict-screen" :class="{ 'recovery-screen': !verdict }">
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
    <template v-if="verdict">
      <div class="verdict-ring"><div class="inner">✓</div></div>
      <div class="verdict-title">You're verified</div>
      <div class="verdict-sub">Real understanding, not a bluff. Back to the feed.</div>
    </template>

    <div v-else class="recovery-panel">
      <template v-if="!recoveryMode">
        <div class="verdict-ring"><div class="inner">↺</div></div>
        <div class="verdict-title">Earn your break another way</div>
        <div class="verdict-sub">Choose one real-world reset to unlock the scroll.</div>
        <div class="recovery-options">
          <button class="recovery-option" @click="recoveryMode = 'talk'">
            <span>💬</span><strong>Talk to someone</strong><small>Have a short, everyday conversation</small>
          </button>
          <button class="recovery-option" @click="recoveryMode = 'nature'">
            <span>🌿</span><strong>Touch grass</strong><small>Photograph something alive outside</small>
          </button>
        </div>
      </template>

      <template v-else-if="recoveryMode === 'talk'">
        <div class="recovery-heading">Talk to someone</div>
        <p class="recovery-copy">Complete a short conversation to unlock your break.</p>
        <ConversationChallenge @complete="completeRecovery" @back="recoveryMode = null" />
      </template>

      <template v-else>
        <div class="recovery-heading">Touch grass</div>
        <p class="recovery-copy">Go outside and photograph a plant, the sky, or another piece of nature.</p>
        <div class="cam-box recovery-camera" @click="recoveryFile.click()">
          <img v-if="recoveryPreview" :src="recoveryPreview" />
          <span v-else>📷 point at nature</span>
        </div>
        <input ref="recoveryFile" type="file" accept="image/*" capture="environment" hidden @change="verifyRecoveryPhoto" />
        <div v-if="recoveryBusy || recoveryVerdict" class="recovery-status" :class="{ good: recoveryVerdict?.pass }">
          {{ recoveryBusy ? 'Checking…' : recoveryVerdict.reason }}
        </div>
        <button class="btn btn-gradient" @click="recoveryFile.click()">
          {{ recoveryPreview ? 'Retake photo' : 'Open camera' }}
        </button>
        <button class="recovery-back" @click="recoveryMode = null">Choose another reset</button>
      </template>
    </div>
  </div>

  <div v-else class="card lightscreen">
    <div class="appbar">
      <div class="who">
        <div class="pfp" aria-hidden="true">
          <svg viewBox="0 0 32 32">
            <circle cx="16" cy="12" r="5" />
            <path d="M7.5 27c.7-5.1 3.6-8 8.5-8s7.8 2.9 8.5 8" />
          </svg>
        </div>
        <div>
          <div class="name">coach</div>
          <div class="status">active now</div>
        </div>
      </div>
      <button class="end-button" @click="endCoaching">End coaching</button>
    </div>

    <div class="content">
      <div class="chat-area" ref="scroller">
        <div
          v-for="(m, i) in messages" :key="i" class="bubble"
          :class="[m.role === 'user' ? 'me' : 'them', { streaming: m.streaming }]"
        >
          {{ m.content }}
          <button
            v-if="m.role === 'assistant' && m.voiceUrl"
            class="replay-voice"
            aria-label="Replay coach voice"
            @click="replayVoice(m)"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 10v4h4l5 4V6l-5 4H4Z" />
              <path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11" />
            </svg>
          </button>
        </div>
        <div v-if="recording || finalizing" class="bubble me live-transcript">
          {{ liveTranscript || '…' }}
          <span class="live-dot" />
        </div>
        <div v-if="liveStatus" class="live-status">{{ liveStatus }}</div>
        <div v-if="busy && !streamingReply" class="bubble them typing">· · ·</div>
      </div>

      <div class="composer">
        <button
          class="voice-button"
          :class="{ recording }"
          :disabled="busy || connecting || finalizing"
          :aria-label="recording ? 'Stop and send' : 'Start speaking'"
          @click="toggleMic"
        >
          <span aria-hidden="true">
            <span v-if="connecting || finalizing" class="spinner" />
            <svg v-else-if="recording" viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="2" /></svg>
            <svg v-else viewBox="0 0 24 24">
              <rect x="9" y="3" width="6" height="12" rx="3" />
              <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6" />
            </svg>
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.who { display: flex; align-items: center; gap: 10px; }
.pfp {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #8b4c38; background: linear-gradient(145deg, #ffe0c7, #f5b997);
  box-shadow: inset 0 0 0 1px rgba(139, 76, 56, 0.08);
}
.pfp svg { width: 23px; height: 23px; fill: currentColor; }
.name { font-size: 13px; font-weight: 700; }
.status { font-size: 10.5px; color: var(--dim); }
.end-button {
  margin: 0; padding: 7px 11px; border-radius: 999px; border: 1px solid var(--border);
  background: #fff; color: var(--g3); font-size: 10.5px; font-weight: 700;
}
.end-button:active { transform: scale(0.97); }
.typing { opacity: 0.65; letter-spacing: 3px; }
.bubble.streaming::after {
  content: ''; display: inline-block; width: 2px; height: 1em; margin-left: 3px;
  vertical-align: -2px; border-radius: 2px; background: currentColor;
  animation: cursorBlink 0.8s steps(1) infinite;
}
.replay-voice {
  width: 25px; height: 25px; margin: 7px 0 -3px; padding: 0;
  display: grid; place-items: center; border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 50%; background: rgba(255, 255, 255, 0.78); color: #555;
}
.replay-voice svg { width: 14px; height: 14px; fill: currentColor; }
.replay-voice svg path:last-child { fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; }
@keyframes cursorBlink { 50% { opacity: 0; } }
.live-transcript { position: relative; min-width: 74px; font-style: italic; }
.live-dot {
  display: inline-block; width: 6px; height: 6px; margin-left: 5px;
  border-radius: 50%; background: #fff; animation: livePulse 0.9s infinite;
}
.live-status { align-self: flex-end; margin: -4px 5px 2px; font-size: 10px; color: var(--dim); }
@keyframes livePulse { 50% { opacity: 0.25; transform: scale(0.8); } }

.composer { display: flex; justify-content: center; }
.voice-button {
  width: 48px; height: 48px; flex: none; display: grid; place-items: center;
  padding: 0; border-radius: 50%; border: 0; color: #fff;
  background: var(--brand-gradient); transition: 160ms ease;
  box-shadow: 0 6px 18px rgba(193, 53, 132, 0.25);
}
.voice-button:not(:disabled):active { transform: scale(0.985); }
.voice-button.recording { box-shadow: 0 0 0 6px rgba(244, 62, 117, 0.12), 0 6px 18px rgba(193, 53, 132, 0.25); }
.voice-button:disabled { opacity: 0.65; }
.voice-button svg { width: 20px; height: 20px; fill: currentColor; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; }
.voice-button svg rect:first-child:not(:only-child) { stroke: none; }
.voice-button svg path { fill: none; }
.spinner {
  width: 17px; height: 17px; border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

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
.recovery-screen { justify-content: center; overflow-y: auto; background: #fffaf4; color: var(--ink); }
.recovery-screen .verdict-sub { color: var(--dim); }
.recovery-panel { width: 100%; max-width: 286px; display: flex; flex-direction: column; align-items: center; }
.recovery-options { width: 100%; display: grid; gap: 10px; margin-top: 20px; }
.recovery-option {
  width: 100%; padding: 13px; display: grid; grid-template-columns: 36px 1fr;
  align-items: center; column-gap: 10px; border: 1px solid var(--border);
  border-radius: 14px; background: #fff; text-align: left;
}
.recovery-option > span { grid-row: 1 / 3; font-size: 22px; text-align: center; }
.recovery-option strong { font-size: 12.5px; }
.recovery-option small { margin-top: 2px; color: var(--dim); font-size: 10px; }
.recovery-heading { width: 100%; font-size: 18px; font-weight: 800; text-align: center; }
.recovery-copy { margin: 6px 0 10px; color: var(--dim); font-size: 11px; line-height: 1.45; text-align: center; }
.recovery-camera { width: 100%; margin: 8px 0 12px; }
.recovery-status { width: 100%; margin-bottom: 10px; padding: 10px; border-radius: 10px; background: #f5f5f5; color: #555; font-size: 11px; text-align: center; }
.recovery-status.good { background: rgba(255, 130, 5, 0.1); color: #c43d08; font-weight: 700; }
.recovery-back { margin-top: 10px; padding: 4px; color: var(--dim); font-size: 10.5px; text-decoration: underline; }
</style>
