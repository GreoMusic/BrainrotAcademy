<script setup>
import { ref } from 'vue'
const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['answered'])

const picked = ref(null)
const done = ref(false)

function choose(i) {
  if (done.value) return
  picked.value = i
  done.value = true
  // Let the result land visually before the feed moves on.
  setTimeout(() => emit('answered', i === props.card.payload.correct), 1400)
}

const cls = (i) => {
  if (!done.value) return ''
  if (i === props.card.payload.correct) return 'correct'
  return i === picked.value ? 'wrong' : ''
}
</script>

<template>
  <div class="card is-gate">
    <div class="card-gradient" style="--g1:#003b33; --g2:#06131a" />
    <div class="eyebrow">prove it to keep scrolling</div>

    <div class="big q">{{ card.payload.q }}</div>

    <div class="stack">
      <button
        v-for="(opt, i) in card.payload.options" :key="i"
        class="btn" :class="cls(i)" :disabled="done" @click="choose(i)"
      >{{ opt }}</button>
    </div>

    <transition name="fade">
      <div v-if="done" class="explain">
        <b>{{ picked === card.payload.correct ? 'Correct.' : 'Not quite.' }}</b>
        {{ card.payload.explain }}
      </div>
    </transition>
  </div>
</template>

<style scoped>
.q { margin-bottom: 26px; }
.explain {
  margin-top: 20px; padding: 15px; border-radius: 14px;
  background: rgba(0,0,0,0.35); font-size: 15px; line-height: 1.5;
}
.explain b { display: block; margin-bottom: 4px; }
</style>
