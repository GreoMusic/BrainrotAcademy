<script setup>
import { ref, computed } from 'vue'
const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['cleared'])

const val = ref('')
const shake = ref(false)
const ok = computed(() => Number(val.value) === props.card.payload.answer)

// A correct number alone proves nothing - typing it in doesn't prove anyone
// did the arithmetic. Getting it right just unlocks the camera step, which
// is the part that actually costs something.
const showCamera = ref(false)
const busy = ref(false)
const verdict = ref(null)
const preview = ref(null)
const fileEl = ref(null)

function submit() {
  if (ok.value) return (showCamera.value = true)
  shake.value = true
  setTimeout(() => { shake.value = false; val.value = '' }, 450)
}

async function onFile(e) {
  const file = e.target.files[0]
  if (!file) return
  preview.value = URL.createObjectURL(file)
  busy.value = true
  verdict.value = null
  try {
    const fd = new FormData()
    fd.append('photo', file)
    fd.append('question', props.card.payload.question)
    const res = await fetch('/api/friction/math-photo', { method: 'POST', body: fd })
    verdict.value = await res.json()
    if (verdict.value.pass) setTimeout(() => emit('cleared'), 1200)
  } catch {
    verdict.value = { pass: false, reason: 'Could not reach the judge.' }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="card reel">
    <!-- The feed is still there behind the toll, just out of reach. -->
    <div class="reel-bg" style="filter: blur(6px)">🎧</div>
    <div class="reel-scrim-top" />

    <div class="budget">
      <div class="budget-row"><span>SCROLL BUDGET</span><span>0 left</span></div>
      <div class="budget-track"><div class="budget-fill" style="width: 0%" /></div>
    </div>

    <div class="sheet-overlay">
      <div class="sheet" :class="{ shake }">
        <div class="sheet-handle" />

        <template v-if="!showCamera">
          <p class="gate-title" style="text-align: center">Quick toll before you continue</p>
          <div class="eq-box">{{ card.payload.question }} = ?</div>
          <input
            v-model="val" class="num-input" type="number" inputmode="numeric"
            placeholder="?" @keyup.enter="submit"
          />
          <button class="btn btn-gradient" style="margin-top: 16px" :disabled="!val" @click="submit">
            {{ ok ? 'Verified ✓ continue' : 'Submit' }}
          </button>
          <div class="link-row"><span>you have watched enough for now</span></div>
        </template>

        <template v-else>
          <p class="gate-title" style="text-align: center">Prove you did the math</p>
          <p class="gate-sub" style="text-align: center">
            Snap a photo of {{ card.payload.question }} worked out on paper.
          </p>

          <div class="cam-box" @click="fileEl.click()">
            <img v-if="preview" :src="preview" />
            <span v-else>📷 point at your work</span>
          </div>
          <input ref="fileEl" type="file" accept="image/*" capture="environment" hidden @change="onFile" />

          <div v-if="busy || verdict" class="status" :class="{ good: verdict && verdict.pass }">
            {{ busy ? 'Checking…' : verdict.reason }}
          </div>

          <button class="btn btn-gradient" style="margin-top: 12px" @click="fileEl.click()">
            {{ preview ? 'Retake photo' : 'Open camera' }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shake { animation: sh 0.4s; }
@keyframes sh { 25% { transform: translateX(-8px) } 75% { transform: translateX(8px) } }
.status { margin-top: 12px; padding: 11px; border-radius: 10px; background: #f7f7f7; font-size: 12.5px; color: #555; text-align: center; }
.status.good { background: rgba(0, 149, 246, 0.09); color: var(--blue); font-weight: 600; }
</style>
