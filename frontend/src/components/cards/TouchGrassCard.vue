<script setup>
import { ref } from 'vue'
import ConversationChallenge from '../ConversationChallenge.vue'
const props = defineProps({ card: Object })
const emit = defineEmits(['cleared'])

const mode = ref('choose')
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
          <div class="cam-box" @click="fileEl.click()">
            <img v-if="preview" :src="preview" />
            <span v-else>📷 point at nature</span>
          </div>
          <input ref="fileEl" type="file" accept="image/*" capture="environment" hidden @change="onFile" />

          <div v-if="busy || verdict" class="status" :class="{ good: verdict && verdict.pass }">
            {{ busy ? 'Checking…' : verdict.reason }}
          </div>

          <button class="btn btn-gradient" style="margin-top: 12px" @click="fileEl.click()">
            {{ preview ? 'Retake photo' : 'Open camera' }}
          </button>
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
