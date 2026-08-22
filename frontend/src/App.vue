<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from './api'
import FeedView from './views/FeedView.vue'
import TouchGrassCard from './components/cards/TouchGrassCard.vue'

const board = ref(null)
const openSubject = ref(null)
const session = ref(null)
const draft = ref('')
const error = ref('')
const starting = ref(false)
const justReset = ref(false)
const previewFriction = import.meta.env.DEV
  && new URLSearchParams(window.location.search).get('preview') === 'friction'
const previewFrictionDone = ref(false)
const previewFrictionCard = {
  id: 'preview:friction',
  type: 'touch_grass',
  payload: { topic: 'black-holes' },
}

function finishFrictionPreview() {
  previewFrictionDone.value = true
  setTimeout(() => { window.location.href = '/' }, 1400)
}

// Shown while Mistral builds the pack. These name what is actually happening
// rather than faking a percentage.
const STEPS = [
  'Reading up on it…',
  'Writing your flashcards…',
  'Scripting the podcast…',
  'Casting the hosts…',
]
const step = ref(0)
let stepTimer = null

const subject = computed(() =>
  board.value?.subjects.find((s) => s.slug === openSubject.value) || null,
)

async function loadBoard() {
  try {
    board.value = await api.catalogue()
  } catch {
    error.value = 'Backend unreachable. Is Flask running on :5001?'
  }
}

onMounted(loadBoard)
onBeforeUnmount(() => clearInterval(stepTimer))

async function start(payload) {
  if (starting.value) return
  starting.value = true
  error.value = ''
  step.value = 0
  stepTimer = setInterval(() => {
    step.value = Math.min(step.value + 1, STEPS.length - 1)
  }, 2800)

  // This tap is the user gesture that unlocks audio for the whole session.
  try {
    new Audio().play().catch(() => {})
  } catch {}

  try {
    const res = await api.start(payload)
    // Spending the last topic rolls the board into a new cycle.
    if (res.cycle?.reset) justReset.value = true
    session.value = res
  } catch (e) {
    error.value = String(e.message || e).replace(/^\{.*"error":\s*"/, '').replace(/".*\}$/, '')
    starting.value = false
    loadBoard()
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

        <div v-if="previewFriction && previewFrictionDone" class="card verdict-screen">
          <div class="verdict-ring"><div class="inner">✓</div></div>
          <div class="verdict-title">Reset complete</div>
          <div class="verdict-sub">Reflection reviewed. Returning to your subjects.</div>
        </div>
        <TouchGrassCard
          v-else-if="previewFriction"
          :card="previewFrictionCard"
          @cleared="finishFrictionPreview"
        />
        <FeedView v-else-if="session" :session="session" />

        <div v-else class="card reel">
          <div class="reel-bg" style="filter: blur(6px)">🌀</div>

          <div class="gate-full">
            <!-- Building -->
            <div v-if="starting" class="gate-card">
              <div class="wordmark">Brainrot Academy</div>
              <div class="gate-ring spin"><div class="inner">✍️</div></div>
              <p class="gate-title">Building your round.</p>
              <transition name="fade" mode="out-in">
                <p class="gate-sub" :key="step">{{ STEPS[step] }}</p>
              </transition>
              <div class="bar"><div class="bar-fill" /></div>
            </div>

            <!-- Level 2: topics inside a subject -->
            <div v-else-if="subject" class="gate-card">
              <button class="back" @click="openSubject = null">‹ subjects</button>
              <div class="subj-head">
                <span class="subj-emoji">{{ subject.emoji }}</span>
                <div>
                  <p class="gate-title" style="margin: 0">{{ subject.title }}</p>
                  <p class="tiny">{{ subject.used }} of {{ subject.total }} done</p>
                </div>
              </div>

              <div class="stack">
                <button
                  v-for="t in subject.topics" :key="t.slug"
                  class="btn topic-row"
                  :class="t.used ? 'spent' : 'btn-outline'"
                  :disabled="t.used"
                  @click="start({ slug: t.slug })"
                >
                  <span>{{ t.title }}</span>
                  <!-- Spent topics stay visible so the cycle's progress reads
                       as progress, rather than options quietly vanishing. -->
                  <span v-if="t.used" class="tick">✓</span>
                  <span v-else-if="t.cached" class="ready">instant</span>
                </button>
              </div>

              <p v-if="error" class="err">{{ error }}</p>
            </div>

            <!-- Level 1: subjects -->
            <div v-else class="gate-card">
              <div class="wordmark">Brainrot Academy</div>
              <p class="gate-title">Pick your subject.</p>
              <p class="gate-sub" v-if="board">
                Cycle {{ board.cycle }} · {{ board.remaining }} of {{ board.total }} left
              </p>

              <div v-if="justReset" class="reset-note">
                🎉 You cleared the whole board. Everything is unlocked again.
              </div>

              <div class="subjects" v-if="board">
                <button
                  v-for="s in board.subjects" :key="s.slug"
                  class="subj" :class="{ done: s.used === s.total }"
                  @click="openSubject = s.slug"
                >
                  <span class="subj-emoji">{{ s.emoji }}</span>
                  <b>{{ s.title }}</b>
                  <i>{{ s.used }}/{{ s.total }}</i>
                  <span class="meter"><i :style="{ width: (s.used / s.total) * 100 + '%' }" /></span>
                </button>
              </div>

              <details class="own">
                <summary>or learn something else</summary>
                <input
                  v-model="draft"
                  class="topic-in"
                  placeholder="why cats purr, WW2, the Krebs cycle…"
                  maxlength="120"
                  @keyup.enter="draft.trim() && start({ topic: draft.trim() })"
                />
                <button
                  class="btn btn-gradient" :disabled="!draft.trim()"
                  @click="start({ topic: draft.trim() })"
                >Start learning</button>
              </details>

              <p v-if="error" class="err">{{ error }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.subjects { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-bottom: 14px; }
.subj {
  position: relative;
  padding: 11px 9px 13px;
  border-radius: 13px;
  background: #fafafa;
  border: 1px solid var(--border);
  text-align: center;
  overflow: hidden;
}
.subj.done { opacity: 0.5; }
.subj-emoji { font-size: 21px; display: block; }
.subj b { display: block; font-size: 12px; margin-top: 3px; }
.subj i { display: block; font-style: normal; font-size: 10px; color: var(--dim); margin-top: 1px; }
.meter { position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: #eee; display: block; }
.meter i { display: block; height: 100%; background: var(--ig-gradient); transition: width 0.4s; }

.back {
  font-size: 11.5px; font-weight: 700; color: var(--blue);
  display: block; margin-bottom: 10px;
}
.subj-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; text-align: left; }
.subj-head .subj-emoji { font-size: 26px; }
.tiny { font-size: 11px; color: var(--dim); margin-top: 2px; }

.topic-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px; font-size: 13px; text-align: left; padding: 11px 13px;
}
.spent { background: #f4f4f4; color: #aaa; border: 1px solid var(--border-soft); }
.tick { color: var(--blue); font-weight: 800; }
.ready { font-size: 9.5px; font-weight: 700; color: var(--blue); text-transform: uppercase; letter-spacing: 0.05em; }

.reset-note {
  font-size: 11.5px; line-height: 1.45; padding: 9px 11px; margin-bottom: 12px;
  border-radius: 10px; background: rgba(0, 149, 246, 0.09); color: var(--blue);
}

.own { margin-top: 4px; }
.own summary {
  font-size: 11.5px; color: var(--dim); cursor: pointer;
  list-style: none; text-decoration: underline; margin-bottom: 10px;
}
.own summary::-webkit-details-marker { display: none; }
.topic-in {
  width: 100%; padding: 11px 13px; border-radius: 11px;
  border: 1px solid var(--border); background: #fafafa;
  font-size: 13px; margin-bottom: 8px; text-align: center;
}
.topic-in:focus { outline: none; border-color: var(--blue); background: #fff; }

.spin { animation: spin 2.4s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.spin .inner { animation: spin 2.4s linear infinite reverse; }

.bar { height: 3px; border-radius: 3px; background: #eee; overflow: hidden; margin-top: 18px; }
.bar-fill { height: 100%; width: 40%; background: var(--ig-gradient); animation: slide 1.5s ease-in-out infinite; }
@keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }

.err { margin-top: 12px; font-size: 11.5px; color: var(--g3); line-height: 1.45; }
</style>
