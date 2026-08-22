<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ card: Object, active: Boolean })
const flipped = ref(false)
// Re-arm when the card scrolls away so it is fresh if revisited.
watch(() => props.active, (a) => { if (!a) flipped.value = false })
</script>

<template>
  <div class="card" @click="flipped = !flipped">
    <div class="card-gradient" style="--g1:#2b1055; --g2:#0d0620" />
    <div class="eyebrow">flashcard</div>

    <div class="big">{{ card.payload.front }}</div>

    <transition name="fade">
      <div v-if="flipped" class="answer">{{ card.payload.back }}</div>
      <div v-else-if="card.payload.hook" class="hook">{{ card.payload.hook }}</div>
    </transition>

    <div class="tap">{{ flipped ? 'tap to hide' : 'tap to reveal' }}</div>
    <div class="hint">swipe up ↑</div>
  </div>
</template>

<style scoped>
.answer {
  margin-top: 22px; padding: 18px; border-radius: var(--card-r);
  background: rgba(255,255,255,0.12); border: 1.5px solid rgba(255,255,255,0.18);
  font-size: 19px; font-weight: 600;
}
.hook { margin-top: 22px; font-size: 15px; color: var(--dim); font-style: italic; }
.tap { margin-top: 20px; font-size: 12px; color: var(--dim); letter-spacing: 0.08em; text-transform: uppercase; }
</style>
