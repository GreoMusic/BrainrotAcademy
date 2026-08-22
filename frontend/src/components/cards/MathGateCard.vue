<script setup>
import { ref, computed } from 'vue'
const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['cleared'])

const val = ref('')
const shake = ref(false)
const ok = computed(() => Number(val.value) === props.card.payload.answer)

function submit() {
  if (ok.value) return setTimeout(() => emit('cleared'), 550)
  shake.value = true
  setTimeout(() => { shake.value = false; val.value = '' }, 450)
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
      </div>
    </div>
  </div>
</template>

<style scoped>
.shake { animation: sh 0.4s; }
@keyframes sh { 25% { transform: translateX(-8px) } 75% { transform: translateX(8px) } }
</style>
