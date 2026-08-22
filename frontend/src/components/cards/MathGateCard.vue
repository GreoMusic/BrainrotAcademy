<script setup>
import { ref, computed } from 'vue'
const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['cleared'])

const val = ref('')
const shake = ref(false)
const ok = computed(() => Number(val.value) === props.card.payload.answer)

function submit() {
  if (ok.value) {
    setTimeout(() => emit('cleared'), 650)
  } else {
    shake.value = true
    setTimeout(() => { shake.value = false; val.value = '' }, 450)
  }
}
</script>

<template>
  <div class="card is-gate" :class="{ shake }">
    <div class="card-gradient" style="--g1:#3d2f00; --g2:#170f00" />
    <div class="eyebrow">the feed is locked</div>
    <div class="big">Solve it to keep scrolling.</div>

    <div class="eq">{{ card.payload.question }}</div>

    <input
      v-model="val" type="number" inputmode="numeric"
      placeholder="?" class="in" :class="{ good: ok }"
      @keyup.enter="submit"
    />
    <button class="btn primary" :disabled="!val" @click="submit">
      {{ ok ? 'Unlock ✓' : 'Check' }}
    </button>

    <div class="note">You have watched enough for now.</div>
  </div>
</template>

<style scoped>
.eq { font-size: 52px; font-weight: 800; letter-spacing: 0.03em; margin: 26px 0 18px; }
.in {
  width: 100%; padding: 16px; border-radius: 16px; margin-bottom: 12px;
  background: rgba(0,0,0,0.35); border: 1.5px solid rgba(255,255,255,0.2);
  color: var(--fg); font-size: 26px; font-weight: 800; text-align: center;
}
.in.good { border-color: var(--accent-2); }
.in::-webkit-outer-spin-button, .in::-webkit-inner-spin-button { -webkit-appearance: none; }
.note { margin-top: 18px; font-size: 13px; color: var(--dim); text-align: center; }
.shake { animation: sh 0.4s; }
@keyframes sh { 25% { transform: translateX(-9px) } 75% { transform: translateX(9px) } }
</style>
