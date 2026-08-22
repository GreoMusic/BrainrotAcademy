<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ConversationChallenge from '../ConversationChallenge.vue'
const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['cleared'])

const mode = ref('choose')
const busy = ref(false)
const verdict = ref(null)
const preview = ref(null)
const fileEl = ref(null)
const videoEl = ref(null)
const cameraOpen = ref(false)
const cameraError = ref('')

let cameraStream = null
let clearTimer = null

function setPreview(file) {
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = URL.createObjectURL(file)
}

async function submitPhoto(file) {
  if (!file || busy.value) return
  setPreview(file)
  busy.value = true
  verdict.value = null
  cameraError.value = ''
  try {
    const fd = new FormData()
    fd.append('photo', file)
    const res = await fetch('/api/friction/touch-grass', { method: 'POST', body: fd })
    verdict.value = await res.json()
    if (verdict.value.pass) {
      if (clearTimer) clearTimeout(clearTimer)
      clearTimer = setTimeout(() => emit('cleared'), 1500)
    }
  } catch {
    verdict.value = { pass: false, reason: 'Could not reach the judge.' }
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
  verdict.value = null
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
  await submitPhoto(new File([blob], 'touch-grass.jpg', { type: 'image/jpeg' }))
}

watch(() => props.active, (active) => {
  if (!active) stopCamera()
})

watch(mode, (nextMode) => {
  if (nextMode !== 'nature') stopCamera()
})

onBeforeUnmount(() => {
  stopCamera()
  if (preview.value) URL.revokeObjectURL(preview.value)
  if (clearTimer) clearTimeout(clearTimer)
})
</script>

<template>
  <div class="card reel">
    <div class="reel-bg" style="filter: blur(6px)">🌱</div>
    <div class="reel-scrim-top" />

    <div class="budget">
      <div class="budget-row"><span>SCROLL BUDGET</span><span>0 left</span></div>
      <div class="budget-track"><div class="budget-fill" style="width: 0%" /></div>
    </div>

    <div class="sheet-overlay">
      <div class="sheet">
        <div class="sheet-handle" />
        <template v-if="mode === 'choose'">
          <p class="gate-title" style="text-align: center">Choose a real-world reset</p>
          <p class="gate-sub" style="text-align: center">Step away from the feed for a moment that actually counts.</p>
          <div class="reset-options">
            <button class="reset-option" @click="mode = 'nature'">
              <span class="reset-icon">🌿</span>
              <span><strong>Touch grass</strong><small>Photograph something alive outside</small></span>
              <b>›</b>
            </button>
            <button class="reset-option" @click="mode = 'talk'">
              <span class="reset-icon">💬</span>
              <span><strong>Talk to someone</strong><small>Get a prompt, transcript, and reflection</small></span>
              <b>›</b>
            </button>
          </div>
        </template>

        <template v-else-if="mode === 'nature'">
          <p class="gate-title" style="text-align: center">Find something alive</p>
          <p class="gate-sub" style="text-align: center">Go outside and photograph a plant, the sky, or another piece of nature.</p>
          <div class="cam-box nature-photo">
            <video v-if="cameraOpen" ref="videoEl" autoplay muted playsinline />
            <img v-else-if="preview" :src="preview" alt="Your nature photo" />
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
          <div v-if="busy || verdict" class="status" :class="{ good: verdict && verdict.pass }">
            {{ busy ? 'Checking…' : verdict.reason }}
          </div>

          <div class="link-row"><span @click="mode = 'choose'">Choose another reset</span></div>
        </template>

        <template v-else>
          <p class="gate-title" style="text-align: center">Have a short conversation</p>
          <p class="gate-sub" style="text-align: center">You will get a transcript and a private reflection on how you communicated.</p>
          <ConversationChallenge :topic="card.payload.topic" @complete="emit('cleared')" @back="mode = 'choose'" />
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.status { margin-top: 12px; padding: 11px; border-radius: 10px; background: #f7f7f7; font-size: 12.5px; color: #555; text-align: center; }
.status.good { background: rgba(0, 149, 246, 0.09); color: var(--blue); font-weight: 600; }
.nature-photo { aspect-ratio: 16 / 9; margin-bottom: 10px; font-size: 13px; font-weight: 700; }
.nature-photo video { width: 100%; height: 100%; object-fit: cover; }
.photo-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.camera-cancel { display: block; margin: 8px auto 0; color: var(--dim); font-size: 11px; text-decoration: underline; }
.camera-error { margin-top: 9px; color: var(--g3); font-size: 11.5px; text-align: center; }
.reset-options { display: grid; gap: 9px; margin-top: 18px; }
.reset-option {
  width: 100%; min-height: 68px; padding: 11px 12px; display: grid;
  grid-template-columns: 38px 1fr auto; gap: 10px; align-items: center;
  border: 1px solid var(--border); border-radius: 14px; background: #fff; text-align: left;
}
.reset-option:active { transform: scale(0.99); background: #fafafa; }
.reset-icon { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 11px; background: #f4f4f4; font-size: 19px; }
.reset-option strong, .reset-option small { display: block; }
.reset-option strong { font-size: 13px; color: #292929; }
.reset-option small { margin-top: 3px; font-size: 10px; line-height: 1.3; color: var(--dim); }
.reset-option b { font-size: 20px; font-weight: 400; color: #aaa; }
</style>
