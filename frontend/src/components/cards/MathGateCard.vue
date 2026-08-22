<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { api } from '../../api'

const props = defineProps({ card: Object, active: Boolean, sessionId: String })
const emit = defineEmits(['cleared'])

const answer = ref('')
const busy = ref(false)
const busyLabel = ref('')
const result = ref(null)
const preview = ref(null)
const fileEl = ref(null)
const videoEl = ref(null)
const cameraOpen = ref(false)
const cameraError = ref('')
const shake = ref(false)

let cameraStream = null
let clearTimer = null

function showResult(nextResult) {
  result.value = nextResult
  if (nextResult.pass) {
    if (clearTimer) clearTimeout(clearTimer)
    clearTimer = setTimeout(() => emit('cleared'), 900)
  } else {
    shake.value = true
    setTimeout(() => { shake.value = false }, 450)
  }
}

function showError(error) {
  result.value = {
    pass: false,
    reason: String(error.message || error),
  }
}

async function submitAnswer() {
  if (!answer.value.trim() || busy.value) return
  busy.value = true
  busyLabel.value = 'Checking your answer…'
  result.value = null
  try {
    showResult(await api.gradeMathAnswer(props.sessionId, props.card.id, answer.value.trim()))
  } catch (error) {
    showError(error)
  } finally {
    busy.value = false
  }
}
function setPreview(file) {
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = URL.createObjectURL(file)
}

async function submitPhoto(file) {
  if (!file || busy.value) return
  setPreview(file)
  result.value = null
  busy.value = true
  busyLabel.value = 'Reading your handwriting with Mistral OCR…'
  try {
    showResult(await api.gradeMathPhoto(props.sessionId, props.card.id, file))
  } catch (error) {
    showError(error)
  } finally {
    busy.value = false
  }
}

async function onFile(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (file) await submitPhoto(file)
}

function stopCamera() {
  if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop())
  cameraStream = null
  cameraOpen.value = false
  if (videoEl.value) videoEl.value.srcObject = null
}

async function openCamera() {
  if (busy.value) return
  cameraError.value = ''
  result.value = null
  stopCamera()
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    })
    cameraOpen.value = true
    await nextTick()
    videoEl.value.srcObject = cameraStream
    await videoEl.value.play()
  } catch {
    stopCamera()
    cameraError.value = 'Camera unavailable or blocked. You can upload a photo instead.'
  }
}

async function capturePhoto() {
  const video = videoEl.value
  if (!video || !video.videoWidth || busy.value) return

  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
  stopCamera()
  if (!blob) {
    cameraError.value = 'Could not capture that frame. Please try again.'
    return
  }
  await submitPhoto(new File([blob], 'math-work.jpg', { type: 'image/jpeg' }))
}

watch(() => props.active, (active) => {
  if (!active) stopCamera()
})

onBeforeUnmount(() => {
  stopCamera()
  if (preview.value) URL.revokeObjectURL(preview.value)
  if (clearTimer) clearTimeout(clearTimer)
})
</script>

<template>
  <div class="card reel">
    <div class="reel-bg" style="filter: blur(6px)">✏️</div>
    <div class="reel-scrim-top" />

    <div class="budget">
      <div class="budget-row"><span>SCROLL BUDGET</span><span>0 left</span></div>
      <div class="budget-track"><div class="budget-fill" style="width: 0%" /></div>
    </div>

    <div class="sheet-overlay">
      <div class="sheet math-sheet" :class="{ shake }">
        <div class="sheet-handle" />
        <p class="gate-title" style="text-align: center">Quick toll before you continue</p>
        <div class="eq-box">{{ card.payload.question }} = ?</div>

        <div class="answer-row">
          <input
            v-model="answer" class="num-input answer-input" type="number"
            inputmode="decimal" placeholder="Answer" :disabled="busy"
            @keyup.enter="submitAnswer"
          />
          <button
            class="btn btn-primary answer-button"
            :disabled="busy || !answer.trim()" @click="submitAnswer"
          >
            Check
          </button>
        </div>

        <div class="or"><span>or show your work</span></div>

        <div class="cam-box work-photo">
          <video v-if="cameraOpen" ref="videoEl" autoplay muted playsinline />
          <img v-else-if="preview" :src="preview" alt="Your handwritten math work" />
          <span v-else>Upload a photo or use your camera</span>
        </div>
        <input ref="fileEl" type="file" accept="image/*" hidden @change="onFile" />

        <div class="photo-actions">
          <button class="btn btn-outline" :disabled="busy" @click="fileEl.click()">
            Upload photo
          </button>
          <button
            class="btn btn-gradient" :disabled="busy"
            @click="cameraOpen ? capturePhoto() : openCamera()"
          >
            {{ cameraOpen ? 'Take photo' : 'Use camera' }}
          </button>
        </div>
        <button v-if="cameraOpen" class="camera-cancel" @click="stopCamera">Cancel camera</button>

        <div v-if="cameraError" class="camera-error">{{ cameraError }}</div>
        <div v-if="busy || result" class="status" :class="{ good: result && result.pass }">
          {{ busy ? busyLabel : result.reason }}
        </div>
        <div class="link-row"><span>Box or circle handwritten answers for best results</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shake { animation: sh 0.4s; }
@keyframes sh { 25% { transform: translateX(-8px) } 75% { transform: translateX(8px) } }
.math-sheet { max-height: 92%; overflow-y: auto; }
.answer-row { display: flex; justify-content: center; gap: 8px; }
.answer-input { width: 128px; margin: 0; }
.answer-button { width: auto; flex: 0 0 86px; }
.or { display: flex; align-items: center; gap: 10px; margin: 14px 0 10px; color: var(--dim); font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; }
.or::before, .or::after { content: ''; height: 1px; background: var(--border); flex: 1; }
.work-photo { aspect-ratio: 16 / 7; margin: 0 0 10px; font-size: 13px; font-weight: 700; }
.work-photo video { width: 100%; height: 100%; object-fit: cover; }
.photo-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.camera-cancel { display: block; margin: 8px auto 0; color: var(--dim); font-size: 11px; text-decoration: underline; }
.camera-error { margin-top: 9px; color: var(--g3); font-size: 11.5px; text-align: center; }
.status {
  margin-top: 10px; padding: 11px; border-radius: 10px;
  background: #f7f7f7; color: #555; font-size: 12.5px; text-align: center;
}
.status.good { background: rgba(0, 149, 246, 0.09); color: var(--blue); font-weight: 600; }
</style>
