<script setup>
import { ref, onMounted } from 'vue'
import { api } from './api'
import FeedView from './views/FeedView.vue'

const topics = ref([])
const session = ref(null)
const error = ref('')
const starting = ref(false)

onMounted(async () => {
  try {
    const data = await api.topics()
    topics.value = data.topics
    if (!data.topics.length) {
      error.value = 'No topic packs found. Run: python -m tools.generate_content --stub'
    }
  } catch (e) {
    error.value = 'Backend unreachable. Is Flask running on :5001?'
  }
})

async function pick(topic) {
  starting.value = true
  // This tap is the user gesture that unlocks audio playback for the whole
  // session. Browsers block unmuted autoplay without one, so spend it here.
  try {
    const a = new Audio()
    a.play().catch(() => {})
  } catch {}

  try {
    session.value = await api.start(topic.slug)
  } catch (e) {
    error.value = String(e.message || e)
    starting.value = false
  }
}
</script>

<template>
  <FeedView v-if="session" :session="session" />

  <div v-else class="shell picker">
    <div class="hero">
      <div class="logo">🧠💀</div>
      <h1>Brainrot<br />Academy</h1>
      <p class="tag">Learn something. Then you may scroll.</p>
    </div>

    <div class="stack">
      <button
        v-for="t in topics" :key="t.slug"
        class="btn topic" :disabled="starting" @click="pick(t)"
      >
        <span class="emoji">{{ t.emoji }}</span>
        <span>
          <b>{{ t.title }}</b>
          <i>{{ t.blurb }}</i>
        </span>
      </button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<style scoped>
.picker {
  display: flex; flex-direction: column; justify-content: center;
  padding: 30px 24px; gap: 34px;
  background: radial-gradient(120% 80% at 50% 0%, #2b1055, #07060d 70%);
}
.hero { text-align: center; }
.logo { font-size: 58px; }
h1 { font-size: 42px; font-weight: 900; line-height: 1.02; letter-spacing: -0.03em; margin-top: 10px; }
.tag { color: var(--dim); margin-top: 14px; font-size: 15px; }
.topic { display: flex; align-items: center; gap: 15px; }
.topic .emoji { font-size: 30px; }
.topic b { display: block; font-size: 17px; }
.topic i { display: block; font-style: normal; font-size: 13px; color: var(--dim); font-weight: 500; margin-top: 2px; }
.error {
  padding: 14px; border-radius: 12px; background: rgba(255,45,129,0.2);
  border: 1px solid var(--hot); font-size: 14px; text-align: center;
}
</style>
