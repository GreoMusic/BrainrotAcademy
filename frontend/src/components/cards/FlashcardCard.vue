<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ card: Object, active: Boolean })
const flipped = ref(false)
// Re-arm when the card scrolls away so it is fresh if revisited.
watch(() => props.active, (a) => { if (!a) flipped.value = false })
</script>

<template>
  <div class="card lightscreen">
    <div class="content">
      <span class="pill grad">learning round</span>

      <div class="tabs">
        <div class="tab on">flashcard</div>
        <div class="tab">fun facts</div>
        <div class="tab">podcast</div>
      </div>

      <div class="learn-card" @click="flipped = !flipped">
        <div class="k">flashcard</div>
        <div class="q">{{ card.payload.front }}</div>
        <transition name="fade" mode="out-in">
          <div v-if="flipped" class="a" key="a">{{ card.payload.back }}</div>
          <div v-else class="a hook" key="h">{{ card.payload.hook || 'Tap to reveal.' }}</div>
        </transition>
      </div>

      <button class="btn btn-ghost" @click="flipped = !flipped">
        {{ flipped ? 'Hide answer' : 'Reveal answer' }}
      </button>
      <div class="link-row"><span>swipe up to continue</span></div>
    </div>
  </div>
</template>

<style scoped>
.hook { font-style: italic; color: var(--dim); }
</style>
