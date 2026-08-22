<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from './api'
import FeedView from './views/FeedView.vue'
import TouchGrassCard from './components/cards/TouchGrassCard.vue'
import SubjectIcon from './components/SubjectIcon.vue'

const board = ref(null)
const openSubject = ref(null)
const session = ref(null)
const draft = ref('')
const error = ref('')
const starting = ref(false)
const justReset = ref(false)
const enteredAcademy = ref(false)
const previewFriction = import.meta.env.DEV
  && new URLSearchParams(window.location.search).get('preview') === 'friction'
const previewFrictionDone = ref(false)
const previewFrictionCard = {
  id: 'preview:friction',
  type: 'touch_grass',
  payload: { topic: 'black-holes' },
}

// A 10ms silent WAV. iOS Safari only unlocks audio for a page once a media
// element actually plays inside a real user gesture - `new Audio().play()`
// with no src never produces sound, so WebKit never counts it and every
// later programmatic Audio() (every podcast turn, every coach reply) plays
// silently for the rest of the session. This one genuinely plays.
const SILENT_WAV =
  'data:audio/wav;base64,UklGRsQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YaAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'

function finishFrictionPreview() {
  previewFrictionDone.value = true
  setTimeout(() => { window.location.href = '/' }, 1400)
}
const resetting = ref(false)

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

async function resetTopics() {
  if (resetting.value || !window.confirm('Unlock every learned topic and start a new cycle?')) return
  resetting.value = true
  error.value = ''
  try {
    board.value = await api.resetCatalogue()
    justReset.value = true
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    resetting.value = false
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
    new Audio(SILENT_WAV).play().catch(() => {})
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

        <div
          v-else
          class="card reel"
          :class="{ 'landing-reel': !enteredAcademy && !starting && !subject }"
        >
          <div v-if="enteredAcademy || starting || subject" class="reel-bg" style="filter: blur(6px)">🌀</div>

          <div class="gate-full">
            <!-- Landing: a Vue/CSS adaptation of the supplied lamp concept. -->
            <div v-if="!enteredAcademy && !starting && !subject" class="landing-shell">
              <div class="mistral-lamp" aria-hidden="true">
                <div class="lamp-beam" />
                <div class="lamp-haze" />
                <div class="lamp-glow" />
              </div>

              <div class="landing-copy">
                <div class="landing-wordmark">Brainrot Academy</div>
                <h1>What if learning<br /><span>can be dynamic?</span></h1>
                <p>Learn it. Explain it. Earn the scroll.</p>
                <button class="landing-cta" @click="enteredAcademy = true">
                  Start learning <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>

            <!-- Building -->
            <div v-else-if="starting" class="gate-card">
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
                <SubjectIcon :slug="subject.slug" class="subject-mark large" />
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

              <button
                v-if="subject.used" class="reset-link subject-reset" :disabled="resetting"
                @click="resetTopics"
              >{{ resetting ? 'Resetting…' : 'Reset learned topics' }}</button>

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
                Everything is unlocked again. Pick any topic.
              </div>

              <div class="subjects" v-if="board">
                <button
                  v-for="s in board.subjects" :key="s.slug"
                  class="subj" :class="{ done: s.used === s.total }"
                  @click="openSubject = s.slug"
                >
                  <SubjectIcon :slug="s.slug" class="subject-mark" />
                  <b>{{ s.title }}</b>
                  <i>{{ s.used }}/{{ s.total }}</i>
                  <span class="meter"><i :style="{ width: (s.used / s.total) * 100 + '%' }" /></span>
                </button>
              </div>

              <button
                v-if="board?.used" class="reset-link" :disabled="resetting"
                @click="resetTopics"
              >{{ resetting ? 'Resetting…' : 'Reset learned topics' }}</button>

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
.landing-reel { background: #fff; }
.landing-reel .gate-full { padding: 0; }
.landing-shell {
  position: relative; width: 100%; height: 100%; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  background:
    radial-gradient(circle at 50% 0%, rgba(255, 216, 0, 0.13), transparent 34%),
    #fff;
}
.mistral-lamp {
  position: absolute; top: 0; left: 0; width: 100%; height: 390px;
  overflow: hidden; pointer-events: none;
}
.lamp-beam {
  position: absolute; top: -18px; left: 50%; width: 310px; height: 282px;
  transform: translateX(-50%) scaleX(0.56); transform-origin: center top;
  opacity: 0;
  background:
    radial-gradient(ellipse 74% 88% at 50% 0%, rgba(255, 175, 0, 0.31) 0%, rgba(255, 130, 5, 0.15) 43%, rgba(250, 80, 15, 0.04) 66%, transparent 82%);
  filter: blur(11px);
  animation:
    beam-open 1.45s 100ms cubic-bezier(0.22, 1, 0.36, 1) forwards,
    beam-breathe 5.8s 1.55s ease-in-out infinite;
}
.lamp-haze {
  position: absolute; top: -62px; left: 50%; width: 292px; height: 224px;
  transform: translateX(-50%); border-radius: 50%;
  background: rgba(255, 130, 5, 0.16); filter: blur(44px);
  animation: haze-in 1.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.lamp-glow {
  position: absolute; top: -28px; left: 50%; width: 184px; height: 94px;
  transform: translateX(-50%); border-radius: 50%;
  background: rgba(255, 175, 0, 0.48); filter: blur(22px);
  animation: glow-in 1.35s 160ms cubic-bezier(0.22, 1, 0.36, 1) both;
}
.landing-copy {
  position: relative; z-index: 2; width: 100%; margin-top: 46px; padding: 0 24px;
  display: flex; flex-direction: column; align-items: center; text-align: center;
  animation: copy-rise 800ms 260ms ease-out both;
}
.landing-wordmark {
  margin-bottom: 17px; color: #c43d08; font-size: 10px; font-weight: 850;
  letter-spacing: 0.16em; text-transform: uppercase;
}
.landing-copy h1 {
  color: #191919; font-size: 31px; line-height: 1.05; letter-spacing: -0.045em;
  font-weight: 780;
}
.landing-copy h1 span {
  color: #d75a24;
}
.landing-copy p { margin-top: 15px; color: #777; font-size: 12px; letter-spacing: -0.01em; }
.landing-cta {
  min-width: 174px; margin-top: 27px; padding: 12px 18px;
  display: flex; align-items: center; justify-content: center; gap: 11px;
  border-radius: 999px; color: #fff; background: #e9480b;
  font-size: 12px; font-weight: 750; box-shadow: 0 9px 24px rgba(233, 72, 11, 0.2);
  transition: transform 160ms ease, box-shadow 160ms ease;
}
.landing-cta:active { transform: translateY(1px) scale(0.99); box-shadow: 0 5px 14px rgba(233, 72, 11, 0.18); }
.landing-cta span { font-size: 15px; line-height: 1; }
@keyframes beam-open {
  from { opacity: 0; transform: translateX(-50%) scaleX(0.56); }
  to { opacity: 0.86; transform: translateX(-50%) scaleX(1); }
}
@keyframes beam-breathe { 0%, 100% { opacity: 0.68; } 50% { opacity: 0.88; } }
@keyframes haze-in { from { opacity: 0; transform: translateX(-50%) scale(0.6); } to { opacity: 1; transform: translateX(-50%) scale(1); } }
@keyframes glow-in { from { opacity: 0; transform: translateX(-50%) scaleX(0.45); } to { opacity: 1; transform: translateX(-50%) scaleX(1); } }
@keyframes copy-rise { from { opacity: 0; transform: translateY(28px); } to { opacity: 1; transform: translateY(0); } }

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
.subject-mark { margin: 0 auto 2px; }
.subj b { display: block; font-size: 12px; margin-top: 3px; }
.subj i { display: block; font-style: normal; font-size: 10px; color: var(--dim); margin-top: 1px; }
.meter { position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: #eee; display: block; }
.meter i { display: block; height: 100%; background: var(--brand-gradient); transition: width 0.4s; }

.back {
  font-size: 11.5px; font-weight: 700; color: var(--blue);
  display: block; margin-bottom: 10px;
}
.subj-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; text-align: left; }
.subj-head .subject-mark { margin: 0; flex: none; }
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

.reset-link {
  display: block; margin: -3px auto 12px; color: var(--dim);
  font-size: 10.5px; text-decoration: underline;
}
.reset-link:disabled { opacity: 0.55; }
.subject-reset { margin-top: 12px; margin-bottom: 0; }

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
.bar-fill { height: 100%; width: 40%; background: var(--brand-gradient); animation: slide 1.5s ease-in-out infinite; }
@keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }

.err { margin-top: 12px; font-size: 11.5px; color: var(--g3); line-height: 1.45; }
</style>
