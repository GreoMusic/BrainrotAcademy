<script setup>
defineProps({ card: Object, active: Boolean })
</script>

<template>
  <div class="card lightscreen">
    <div class="content">
      <span class="pill grad">did you know</span>

      <div class="tabs">
        <div class="tab">flashcard</div>
        <div class="tab on">fun facts</div>
        <div class="tab">podcast</div>
      </div>

      <div class="learn-card fact">
        <div class="emoji">{{ card.payload.emoji }}</div>
        <div class="q">{{ card.payload.text }}</div>
      </div>

      <div class="link-row"><span>swipe up to continue</span></div>
    </div>
  </div>
</template>

<style scoped>
.fact { text-align: center; }
.emoji { font-size: 52px; margin-bottom: 14px; }
.fact .q { font-size: 16px; }
</style>
