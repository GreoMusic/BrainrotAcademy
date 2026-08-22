<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

const props = defineProps({
  topic: { type: String, default: 'what you just learned' },
  allowBack: { type: Boolean, default: true },
})
const emit = defineEmits(['complete', 'back'])

const recording = ref(false)
const busy = ref(false)
const result = ref(null)
const elapsed = ref(0)
let recorder = null
let chunks = []
let clock = null
let discard = false

const prompts = [
  'Ask: “How has your day been so far?” Share one detail from your day too.',
  'Talk about today’s weather and whether it changed either person’s plans.',
  'Ask what hobby they have been enjoying lately and how they got into it.',
  'Ask what they are looking forward to this week, then share your answer.',
  'Ask about a favorite place nearby and what makes it worth visiting.',
]
const promptIndex = ref(Math.floor(Math.random() * prompts.length))
const prompt = computed(() => prompts[promptIndex.value])

function anotherPrompt() {
  promptIndex.value = (promptIndex.value + 1) % prompts.length
}

const speakerNames = computed(() => {
  const names = {}
  for (const segment of result.value?.segments || []) {
    if (!names[segment.speaker]) names[segment.speaker] = `Speaker ${Object.keys(names).length + 1}`
  }
  return names
})

function stopClock() {
  if (clock) clearInterval(clock)
  clock = null
}

async function toggle() {
  if (recording.value) {
    recording.value = false
    stopClock()
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    return
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    })
    const preferred = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : undefined
    recorder = new MediaRecorder(stream, preferred ? { mimeType: preferred } : undefined)
    chunks = []
    discard = false
    elapsed.value = 0
    result.value = null
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunks.push(event.data)
    }
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop())
      if (!discard) send(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }))
    }
    recorder.start(500)
    recording.value = true
    clock = setInterval(() => { elapsed.value += 1 }, 1000)
  } catch {
    result.value = { pass: false, reason: 'Microphone access is blocked. Allow it and try again.' }
  }
}

async function send(blob) {
  busy.value = true
  try {
    const form = new FormData()
    form.append('audio', blob, 'conversation.webm')
    form.append('prompt', prompt.value)
    const response = await fetch('/api/friction/talk', { method: 'POST', body: form })
    result.value = await response.json()
    if (!response.ok) throw new Error(result.value.error || 'Reflection failed')
  } catch (error) {
    result.value = { pass: false, reason: error.message || 'Could not create the reflection.' }
  } finally {
    busy.value = false
  }
}

onBeforeUnmount(() => {
  discard = true
  stopClock()
  if (recorder && recorder.state !== 'inactive') recorder.stop()
})
</script>

<template>
  <div class="conversation-challenge">
    <div v-if="!result" class="challenge-intro">
      <div class="prompt-head">
        <div class="challenge-label">small-talk prompt</div>
        <button class="shuffle" @click="anotherPrompt">New prompt</button>
      </div>
      <p class="challenge-prompt">{{ prompt }}</p>
      <p class="privacy">Keep the phone nearby so both voices are captured. The transcript is used for this reflection only.</p>

      <button class="conversation-mic" :class="{ recording }" :disabled="busy" @click="toggle">
        <svg v-if="!recording" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="9" y="3" width="6" height="12" rx="3" />
          <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6" />
        </svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2" /></svg>
      </button>
      <div class="record-label">
        {{ recording ? `${elapsed}s · tap to finish` : busy ? 'Voxtral is transcribing…' : 'tap when both people are ready' }}
      </div>
      <button v-if="allowBack && !recording && !busy" class="back-link" @click="emit('back')">Choose another reset</button>
      <button v-else-if="!recording && !busy" class="back-link" @click="emit('complete')">Finish for now</button>
    </div>

    <div v-else class="reflection">
      <div class="challenge-label">reflection coach</div>
      <p class="reflection-title">{{ result.reason }}</p>

      <div v-if="result.segments?.length" class="transcript">
        <div class="section-label">Transcript</div>
        <div v-for="(segment, index) in result.segments" :key="index" class="speaker-line">
          <strong>{{ speakerNames[segment.speaker] }}</strong>
          <p>{{ segment.text }}</p>
        </div>
      </div>
      <div v-else-if="result.transcript" class="transcript">
        <div class="section-label">Transcript</div>
        <p>“{{ result.transcript }}”</p>
      </div>

      <template v-if="result.reflection">
        <div class="reflection-box positive">
          <div class="section-label">What worked</div>
          <ul><li v-for="item in result.reflection.strengths" :key="item">{{ item }}</li></ul>
        </div>
        <div class="reflection-box">
          <div class="section-label">Practice next</div>
          <p>{{ result.reflection.next_step }}</p>
        </div>
        <div v-if="result.reflection.follow_up" class="follow-up">
          Try asking: “{{ result.reflection.follow_up }}”
        </div>
      </template>

      <button v-if="result.pass" class="btn btn-gradient" @click="emit('complete')">Finish and continue</button>
      <template v-else>
        <button class="btn btn-outline" @click="result = null">Try conversation again</button>
        <button class="back-link" @click="emit('complete')">Finish for now</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.conversation-challenge { margin-top: 12px; }
.challenge-label, .section-label { font-size: 9px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; color: var(--dim); }
.prompt-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.shuffle { padding: 3px; background: none; color: var(--blue); font-size: 10px; font-weight: 700; }
.challenge-prompt { margin: 8px 0; font-size: 15px; line-height: 1.4; font-weight: 650; color: #292929; }
.privacy { margin: 0; font-size: 10.5px; line-height: 1.4; color: var(--dim); }
.conversation-mic {
  width: 58px; height: 58px; margin: 17px auto 8px; padding: 0; display: grid; place-items: center;
  border: 0; border-radius: 50%; color: #fff; background: var(--ig-gradient);
  box-shadow: 0 7px 20px rgba(193, 53, 132, 0.23);
}
.conversation-mic.recording { animation: pulse 1.1s infinite; }
.conversation-mic:disabled { opacity: 0.65; }
.conversation-mic svg { width: 22px; height: 22px; fill: currentColor; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; }
.conversation-mic svg path { fill: none; }
.record-label { min-height: 17px; text-align: center; font-size: 10.5px; color: var(--dim); }
.back-link { display: block; margin: 10px auto 0; padding: 3px; color: var(--dim); background: none; text-decoration: underline; font-size: 10.5px; }
.reflection-title { margin: 7px 0 11px; font-size: 14px; line-height: 1.35; font-weight: 650; }
.transcript, .reflection-box { margin: 8px 0; padding: 10px; border-radius: 11px; background: #f6f6f6; }
.transcript p, .reflection-box p { margin: 5px 0 0; font-size: 11px; line-height: 1.4; color: #555; }
.speaker-line { margin-top: 9px; }
.speaker-line strong { font-size: 9.5px; color: var(--blue); }
.speaker-line p { margin-top: 2px; }
.reflection-box.positive { background: rgba(0, 149, 246, 0.08); }
.reflection-box ul { margin: 6px 0 0; padding-left: 17px; font-size: 11px; line-height: 1.5; color: #444; }
.follow-up { margin: 10px 1px 13px; font-size: 11px; line-height: 1.4; font-style: italic; color: var(--dim); }
@keyframes pulse { 50% { box-shadow: 0 0 0 12px rgba(214, 41, 118, 0.12), 0 7px 20px rgba(193, 53, 132, 0.23); } }
</style>
