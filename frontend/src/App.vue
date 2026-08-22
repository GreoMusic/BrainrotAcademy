<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { api } from './api'
import FeedView from './views/FeedView.vue'

const suggestions = ref([])
const session = ref(null)
const draft = ref('')
const error = ref('')
const starting = ref(false)

// Shown while Mistral builds the pack. These name what is actually happening
// rather than faking a percentage.
const STEPS = [
  'Reading up on it…',
  'Writing your flashcards…',
  'Setting the quiz…',
  'Scripting the podcast…',
  'Casting the hosts…',
]
const step = ref(0)
let stepTimer = null

onMounted(async () => {
  try {
    suggestions.value = (await api.topics()).topics
  } catch {
    error.value = 'Backend unreachable. Is Flask running on :5001?'
  }
})

onBeforeUnmount(() => clearInterval(stepTimer))

async function start(topicText) {
  const topic = (topicText || draft.value).trim()
  if (!topic || starting.value) return

  starting.value = true
  error.value = ''
  step.value = 0
  // A cached topic returns in well under a second, so only start the ticker
  // once it is clear this is a cold build.
  stepTimer = setInterval(() => {
    step.value = Math.min(step.value + 1, STEPS.length - 1)
  }, 2600)

  // This tap is the user gesture that unlocks audio for the whole session.
  try {
    new Audio().play().catch(() => {})
  } catch {}

  try {
    session.value = await api.start(topic)
  } catch (e) {
    error.value = String(e.message || e).replace(/^\{.*"error":\s*"/, '').replace(/".*\}$/, '')
    starting.value = false
  } finally {
    clearInterval(stepTimer)
  }
}
</script>

<template>
  <div class="stage">
    <div class="phone">
      <div class="screen">
        <div class="notch" />

        <FeedView v-if="session" :session="session" />

        <div v-else class="card reel">
          <div class="reel-bg" style="filter: blur(6px)">🌀</div>

          <div class="gate-full">
            <!-- Building state -->
            <div v-if="starting" class="gate-card">
              <div class="wordmark">Brainrot Academy</div>
              <div class="gate-ring spin"><div class="inner">✍️</div></div>
              <p class="gate-title">Building your round.</p>
              <transition name="fade" mode="out-in">
                <p class="gate-sub" :key="step">{{ STEPS[step] }}</p>
              </transition>
              <div class="bar"><div class="bar-fill" /></div>
            </div>

            <!-- Picker -->
            <div v-else class="gate-card">
              <div class="wordmark">Brainrot Academy</div>
              <div class="gate-ring"><div class="inner">🎓</div></div>
              <p class="gate-title">What do you want to learn?</p>
              <p class="gate-sub">Anything. We will build the round for it.</p>

              <div class="entry">
                <input
                  v-model="draft"
                  class="topic-in"
                  placeholder="the Krebs cycle, WW2, why cats purr…"
                  maxlength="120"
                  @keyup.enter="start()"
                />
                <button class="btn btn-gradient go" :disabled="!draft.trim()" @click="start()">
                  Start learning
                </button>
              </div>

              <div class="chips">
                <button
                  v-for="t in suggestions" :key="t.slug"
                  class="chip" :class="{ cached: t.cached }" @click="start(t.title)"
                >
                  <span>{{ t.emoji }}</span> {{ t.title }}
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
.entry { margin-bottom: 14px; }
.topic-in {
  width: 100%;
  padding: 12px 14px;
  border-radius: 11px;
  border: 1px solid var(--border);
  background: #fafafa;
  font-size: 13.5px;
  margin-bottom: 8px;
  text-align: center;
}
.topic-in:focus { outline: none; border-color: var(--blue); background: #fff; }
.go { font-size: 13.5px; }

.chips { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
.chip {
  font-size: 11px;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f2f2f2;
  color: #555;
  display: inline-flex;
  gap: 4px;
  align-items: center;
}
/* Already generated - instant to open. */
.chip.cached { background: rgba(0, 149, 246, 0.1); color: var(--blue); }

.spin { animation: spin 2.4s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.spin .inner { animation: spin 2.4s linear infinite reverse; }

.bar { height: 3px; border-radius: 3px; background: #eee; overflow: hidden; margin-top: 18px; }
.bar-fill {
  height: 100%;
  width: 40%;
  background: var(--ig-gradient);
  animation: slide 1.5s ease-in-out infinite;
}
@keyframes slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}

.err { margin-top: 14px; font-size: 11.5px; color: var(--g3); line-height: 1.45; }
</style>
