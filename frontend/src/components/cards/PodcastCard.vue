<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'

const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['answered'])

const seg = computed(() => props.card.payload.segment || { turns: [] })
const turns = computed(() => seg.value.turns || [])

const idx = ref(0)
const playing = ref(false)
const showQuiz = ref(false)
const picked = ref(null)

const current = computed(() => turns.value[idx.value] || {})
const quiz = computed(() => seg.value.quiz_after)

let audio = null
let preload = null
let timer = null

/** Play turn N. Falls back to a duration timer when audio has not been
 *  rendered yet, so the podcast is demoable before any TTS exists. */
function playTurn(n) {
  stopAudio()
  if (n >= turns.value.length) return finishSegment()
  idx.value = n

  const turn = turns.value[n]
  const next = turns.value[n + 1]

  if (turn.audio) {
    audio = new Audio(turn.audio)
    audio.onended = () => playTurn(n + 1)
    audio.play().catch(() => {})
    // Preload N+1 during N so the swap on `ended` is not audibly gappy.
    if (next && next.audio) preload = new Audio(next.audio)
  } else {
    timer = setTimeout(() => playTurn(n + 1), (turn.dur || 3) * 1000)
  }
  playing.value = true
}

function finishSegment() {
  playing.value = false
  if (quiz.value) showQuiz.value = true
}

function stopAudio() {
  if (audio) { audio.pause(); audio = null }
  if (timer) { clearTimeout(timer); timer = null }
  preload = null
}

function toggle() {
  if (showQuiz.value) return
  if (playing.value) {
    stopAudio()
    playing.value = false
  } else {
    playTurn(idx.value)
  }
}

function step(delta) {
  playTurn(Math.min(Math.max(idx.value + delta, 0), turns.value.length - 1))
}

function answer(i) {
  if (picked.value !== null) return
  picked.value = i
  const correct = i === quiz.value.correct
  const src = correct ? quiz.value.reaction_correct_audio : quiz.value.reaction_wrong_audio
  if (src) {
    audio = new Audio(src)
    audio.play().catch(() => {})
  }
  setTimeout(() => emit('answered', correct), 2400)
}

// Same contract as VideoCard: play only while on screen.
// `immediate` matters: a card can mount already active (the first card in the
// feed, or after a programmatic scroll), and a plain watcher never fires for
// the initial value, so it would sit there silently forever.
watch(
  () => props.active,
  (a) => {
    if (a) playTurn(0)
    else {
      stopAudio()
      playing.value = false
      idx.value = 0
      showQuiz.value = false
      picked.value = null
    }
  },
  { immediate: true, flush: 'post' },
)

onBeforeUnmount(stopAudio)
</script>

<template>
  <div class="card lightscreen">
    <div class="content">
      <span class="pill grad">learning round</span>

      <div class="tabs">
        <div class="tab">flashcard</div>
        <div class="tab">fun facts</div>
        <div class="tab on">podcast</div>
      </div>

      <!-- Turn-level progress: honest about how much is left. -->
      <div class="dashes">
        <div v-for="(t, i) in turns" :key="i" class="d" :class="{ on: i <= idx }" />
      </div>

      <div class="learn-card pod">
        <div class="k">{{ card.payload.title }}</div>

        <div class="hosts">
          <div class="host" :class="{ live: playing && current.speaker === 'a' }">
            <div class="ring"><div class="inner">🎙️</div></div>
            <span>ARI</span>
          </div>
          <div class="host" :class="{ live: playing && current.speaker === 'b' }">
            <div class="ring"><div class="inner">🤨</div></div>
            <span>BEX</span>
          </div>
        </div>

        <!-- Captions are not optional: most people watch muted. -->
        <transition name="fade">
          <div class="q line" :key="idx">{{ current.text }}</div>
        </transition>

        <div class="wave" :class="{ on: playing }">
          <i v-for="n in 20" :key="n" :style="{ animationDelay: n * 0.055 + 's' }" />
        </div>
      </div>

      <div class="controls">
        <button class="ctl" @click="step(-1)">◀◀</button>
        <button class="btn btn-primary play" @click="toggle">
          {{ playing ? 'Pause' : 'Play' }}
        </button>
        <button class="ctl" @click="step(1)">▶▶</button>
      </div>
    </div>

    <!-- Scripted interjection: the reliable backbone of the interactivity. -->
    <transition name="fade">
      <div v-if="showQuiz" class="sheet-overlay">
        <div class="sheet">
          <div class="sheet-handle" />
          <p class="gate-title" style="text-align: center">{{ quiz.q }}</p>
          <div class="stack" style="margin-top: 14px">
            <button
              v-for="(o, i) in quiz.options" :key="i" class="btn"
              :class="picked === null
                ? 'btn-outline'
                : (i === quiz.correct ? 'opt-correct' : (i === picked ? 'opt-wrong' : 'btn-outline muted'))"
              :disabled="picked !== null" @click="answer(i)"
            >{{ o }}</button>
          </div>
          <div v-if="picked !== null" class="reaction">
            {{ picked === quiz.correct ? quiz.reaction_correct : quiz.reaction_wrong }}
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.pod { justify-content: flex-start; }
.hosts { display: flex; gap: 22px; margin: 6px 0 16px; }
.host { display: grid; justify-items: center; gap: 5px; opacity: 0.42; transition: opacity 0.25s, transform 0.25s; }
.host.live { opacity: 1; transform: scale(1.06); }
.host span { font-size: 9px; font-weight: 800; letter-spacing: 0.12em; color: #666; }
.ring {
  width: 48px; height: 48px; border-radius: 50%; padding: 2.5px;
  background: #e6e6e6; display: flex; align-items: center; justify-content: center;
}
.host.live .ring { background: var(--ig-gradient); }
.ring .inner {
  width: 100%; height: 100%; border-radius: 50%; background: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 21px;
}

.line { flex: 1; display: flex; align-items: center; font-size: 15px; }

.wave { display: flex; align-items: flex-end; gap: 2.5px; height: 22px; margin-top: 10px; opacity: 0.28; }
.wave.on { opacity: 1; }
.wave i { flex: 1; background: var(--g3); border-radius: 2px; height: 22%; }
.wave.on i { animation: bar 0.85s ease-in-out infinite; }
@keyframes bar { 50% { height: 100% } }

.controls { display: flex; gap: 8px; align-items: center; }
.ctl {
  padding: 13px 14px; border-radius: 11px; background: #f2f2f2;
  font-weight: 700; font-size: 12px; color: #444; flex: none;
}
.play { flex: 1; }

.opt-correct { background: rgba(0, 149, 246, 0.1); color: var(--blue); border: 1.5px solid var(--blue); }
.opt-wrong { background: #fff0f3; color: var(--g3); border: 1.5px solid var(--g3); }
.muted { opacity: 0.55; }
.reaction { margin-top: 13px; font-size: 12.5px; font-style: italic; color: var(--dim); text-align: center; }
</style>
