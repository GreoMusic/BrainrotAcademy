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
  const n = Math.min(Math.max(idx.value + delta, 0), turns.value.length - 1)
  playTurn(n)
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
  setTimeout(() => emit('answered', correct), 2200)
}

// Same contract as VideoCard: play only while on screen.
watch(() => props.active, (a) => {
  if (a) playTurn(0)
  else { stopAudio(); playing.value = false; idx.value = 0; showQuiz.value = false; picked.value = null }
})

onBeforeUnmount(stopAudio)
</script>

<template>
  <div class="card pod" :style="{ '--hue': (card.payload.index || 0) * 47 }">
    <div class="card-gradient pod-bg" />

    <!-- Story-style dots: honest about how much is left. -->
    <div class="dots">
      <span v-for="(t, i) in turns" :key="i" :class="{ on: i <= idx }" />
    </div>

    <div class="eyebrow">podcast · {{ card.payload.title }}</div>

    <div class="hosts">
      <div class="host" :class="{ live: playing && current.speaker === 'a' }">
        <div class="blob a">🎙️</div><span>ARI</span>
      </div>
      <div class="host" :class="{ live: playing && current.speaker === 'b' }">
        <div class="blob b">🤨</div><span>BEX</span>
      </div>
    </div>

    <!-- Captions are not optional: most people scroll muted. -->
    <transition name="fade" mode="out-in">
      <div class="caption" :key="idx">{{ current.text }}</div>
    </transition>

    <div class="wave" :class="{ on: playing }">
      <i v-for="n in 22" :key="n" :style="{ animationDelay: n * 0.055 + 's' }" />
    </div>

    <div v-if="!showQuiz" class="controls">
      <button class="ctl" @click="step(-1)">◀◀</button>
      <button class="ctl big-ctl" @click="toggle">{{ playing ? '❚❚' : '▶' }}</button>
      <button class="ctl" @click="step(1)">▶▶</button>
    </div>

    <!-- Scripted interjection: the reliable backbone of the interactivity. -->
    <transition name="fade">
      <div v-if="showQuiz" class="sheet">
        <div class="sheet-q">{{ quiz.q }}</div>
        <div class="stack">
          <button
            v-for="(o, i) in quiz.options" :key="i" class="btn"
            :class="picked === null ? '' : (i === quiz.correct ? 'correct' : (i === picked ? 'wrong' : ''))"
            :disabled="picked !== null" @click="answer(i)"
          >{{ o }}</button>
        </div>
        <div v-if="picked !== null" class="reaction">
          {{ picked === quiz.correct ? quiz.reaction_correct : quiz.reaction_wrong }}
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.pod { justify-content: flex-start; padding-top: 96px; }
.pod-bg {
  background: linear-gradient(165deg,
    hsl(calc(265 + var(--hue)) 70% 22%),
    hsl(calc(300 + var(--hue)) 60% 8%));
}
.dots { position: absolute; top: 68px; left: 20px; right: 20px; display: flex; gap: 4px; }
.dots span { flex: 1; height: 3px; border-radius: 2px; background: rgba(255,255,255,0.22); transition: background 0.3s; }
.dots span.on { background: #fff; }

.hosts { display: flex; gap: 30px; margin: 10px 0 26px; }
.host { display: grid; justify-items: center; gap: 6px; opacity: 0.4; transition: opacity 0.25s, transform 0.25s; }
.host.live { opacity: 1; transform: scale(1.07); }
.host span { font-size: 10px; font-weight: 800; letter-spacing: 0.14em; }
.blob {
  width: 62px; height: 62px; border-radius: 50%; display: grid; place-items: center;
  font-size: 28px; background: rgba(255,255,255,0.14); border: 2px solid rgba(255,255,255,0.2);
}
.host.live .blob { animation: pulse 1.1s ease-in-out infinite; border-color: var(--accent-2); }
@keyframes pulse { 50% { box-shadow: 0 0 0 11px rgba(0,229,192,0.12) } }

.caption { font-size: clamp(20px, 5.6vw, 27px); font-weight: 700; line-height: 1.32; min-height: 120px; }

.wave { display: flex; align-items: flex-end; gap: 3px; height: 34px; margin-top: 22px; opacity: 0.3; }
.wave.on { opacity: 1; }
.wave i { flex: 1; background: var(--accent-2); border-radius: 2px; height: 20%; }
.wave.on i { animation: bar 0.85s ease-in-out infinite; }
@keyframes bar { 50% { height: 100% } }

.controls { display: flex; gap: 14px; align-items: center; margin-top: 26px; }
.ctl {
  padding: 11px 15px; border-radius: 12px; background: rgba(255,255,255,0.12);
  font-weight: 800; font-size: 13px;
}
.big-ctl { font-size: 17px; padding: 11px 24px; }

.sheet {
  position: absolute; left: 0; right: 0; bottom: 0;
  padding: 26px 22px calc(30px + env(safe-area-inset-bottom));
  background: rgba(8,4,18,0.94); backdrop-filter: blur(16px);
  border-radius: 26px 26px 0 0; border-top: 1.5px solid rgba(255,255,255,0.14);
}
.sheet-q { font-size: 20px; font-weight: 800; margin-bottom: 16px; }
.reaction { margin-top: 15px; font-size: 15px; font-style: italic; color: var(--accent-2); }
</style>
