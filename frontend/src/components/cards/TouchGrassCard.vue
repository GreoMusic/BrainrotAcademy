<script setup>
import { ref } from 'vue'
const props = defineProps({ card: Object })
const emit = defineEmits(['cleared'])

const busy = ref(false)
const verdict = ref(null)
const preview = ref(null)
const fileEl = ref(null)

async function onFile(e) {
  const file = e.target.files[0]
  if (!file) return
  preview.value = URL.createObjectURL(file)
  busy.value = true
  verdict.value = null
  try {
    const fd = new FormData()
    fd.append('photo', file)
    const res = await fetch('/api/friction/touch-grass', { method: 'POST', body: fd })
    verdict.value = await res.json()
    if (verdict.value.pass) setTimeout(() => emit('cleared'), 1500)
  } catch {
    verdict.value = { pass: false, reason: 'Could not reach the judge.' }
  } finally {
    busy.value = false
  }
}
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
        <p class="gate-title" style="text-align: center">Quick toll before you continue</p>
        <p class="gate-sub" style="text-align: center">
          Go outside and photograph something alive. The camera checks it is real.
        </p>

        <div class="cam-box" @click="fileEl.click()">
          <img v-if="preview" :src="preview" />
          <span v-else>📷 point at grass</span>
        </div>
        <input ref="fileEl" type="file" accept="image/*" capture="environment" hidden @change="onFile" />

        <div v-if="busy || verdict" class="status" :class="{ good: verdict && verdict.pass }">
          {{ busy ? 'Checking…' : verdict.reason }}
        </div>

        <button class="btn btn-gradient" style="margin-top: 12px" @click="fileEl.click()">
          {{ preview ? 'Retake photo' : 'Open camera' }}
        </button>
        <div class="link-row"><span @click="emit('cleared')">I am indoors — let me through</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.status { margin-top: 12px; padding: 11px; border-radius: 10px; background: #f7f7f7; font-size: 12.5px; color: #555; text-align: center; }
.status.good { background: rgba(0, 149, 246, 0.09); color: var(--blue); font-weight: 600; }
</style>
