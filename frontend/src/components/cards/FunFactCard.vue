<script setup>
defineProps({ card: Object, active: Boolean })
</script>

<template>
  <div class="card">
    <div class="card-gradient" style="--g1:#06312b; --g2:#04120f" />
    <div class="eyebrow">did you know</div>
    <div class="emoji">{{ card.payload.emoji }}</div>
    <div class="big">{{ card.payload.text }}</div>
    <div class="hint">swipe up ↑</div>
  </div>
</template>

<style scoped>
.emoji { font-size: 62px; margin-bottom: 14px; }
</style>
