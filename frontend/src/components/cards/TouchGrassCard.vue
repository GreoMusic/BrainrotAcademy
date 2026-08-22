<script setup>
import { ref } from 'vue'
const props = defineProps({ card: Object, sessionId: String })
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
    if (verdict.value.pass) setTimeout(() => emit('cleared'), 1600)
  } catch (err) {
    verdict.value = { pass: false, reason: 'Could not reach the judge. Skip for now?' }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="card is-gate">
    <div class="card-gradient" style="--g1:#0c3b12; --g2:#04140a" />
    <div class="eyebrow">friction</div>
    <div class="big">Go outside. Photograph something alive.</div>

    <div class="frame" @click="fileEl.click()">
      <img v-if="preview" :src="preview" />
      <div v-else class="ph">📷<span>tap to open camera</span></div>
    </div>
    <input ref="fileEl" type="file" accept="image/*" capture="environment" hidden @change="onFile" />

    <div v-if="busy" class="status">Checking…</div>
    <div v-else-if="verdict" class="status" :class="{ good: verdict.pass }">
      {{ verdict.reason }}
    </div>

    <button class="skip" @click="emit('cleared')">I am indoors, let me through</button>
  </div>
</template>

<style scoped>
.frame {
  margin: 24px 0 16px; aspect-ratio: 4/3; border-radius: var(--card-r); overflow: hidden;
  background: rgba(0,0,0,0.35); border: 2px dashed rgba(255,255,255,0.24);
  display: grid; place-items: center;
}
.frame img { width: 100%; height: 100%; object-fit: cover; }
.ph { display: grid; justify-items: center; gap: 8px; font-size: 44px; }
.ph span { font-size: 13px; color: var(--dim); }
.status { padding: 13px; border-radius: 12px; background: rgba(0,0,0,0.4); font-size: 15px; }
.status.good { background: rgba(0,229,192,0.22); }
.skip { margin-top: 20px; font-size: 13px; color: var(--dim); text-decoration: underline; }
</style>
