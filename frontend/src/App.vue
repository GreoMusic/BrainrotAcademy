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
  } catch {
    error.value = 'Backend unreachable. Is Flask running on :5001?'
  }
})

async function pick(topic) {
  starting.value = true
  // This tap is the user gesture that unlocks audio playback for the whole
  // session. Browsers block unmuted autoplay without one, so spend it here.
  try {
    new Audio().play().catch(() => {})
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
  <div class="stage">
    <div class="phone">
      <div class="screen">
        <div class="notch" />

        <FeedView v-if="session" :session="session" />

        <!-- Enrollment gate, styled as the design's full-screen takeover. -->
        <div v-else class="card reel">
          <div class="reel-bg" style="filter: blur(6px)">🌀</div>

          <div class="gate-full">
            <div class="gate-card">
              <div class="wordmark">Brainrot Academy</div>
              <div class="gate-ring"><div class="inner">🎓</div></div>
              <p class="gate-title">Enrollment check.</p>
              <p class="gate-sub">
                The feed is locked. Pick a subject and prove you learned something
                to get in.
              </p>

              <div class="stack">
                <button
                  v-for="t in topics" :key="t.slug"
                  class="btn btn-gradient topic" :disabled="starting" @click="pick(t)"
                >
                  <span class="emoji">{{ t.emoji }}</span>
                  <span>{{ t.title }}</span>
                </button>
              </div>

              <p v-if="error" class="err">{{ error }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.topic { display: flex; align-items: center; justify-content: center; gap: 8px; }
.topic .emoji { font-size: 16px; }
.err { margin-top: 14px; font-size: 11.5px; color: var(--g3); line-height: 1.45; }
</style>
