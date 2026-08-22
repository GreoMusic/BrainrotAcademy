<script setup>
import ConversationChallenge from '../ConversationChallenge.vue'

defineProps({ card: Object })
const emit = defineEmits(['cleared'])
</script>

<template>
  <div class="card reel">
    <div class="reel-bg" style="filter: blur(6px)">🗣️</div>
    <div class="reel-scrim-top" />
    <div class="budget">
      <div class="budget-row"><span>SCROLL BUDGET</span><span>0 left</span></div>
      <div class="budget-track"><div class="budget-fill" style="width: 0%" /></div>
    </div>
    <div class="sheet-overlay">
      <div class="sheet">
        <div class="sheet-handle" />
        <p class="gate-title" style="text-align: center">Talk it through with someone</p>
        <p class="gate-sub" style="text-align: center">A real conversation, followed by private communication coaching.</p>
        <ConversationChallenge :topic="card.payload.topic" :allow-back="false" @complete="emit('cleared')" />
      </div>
    </div>
  </div>
</template>
