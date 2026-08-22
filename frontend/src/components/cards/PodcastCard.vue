<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { api } from '../../api'

const props = defineProps({ card: Object, active: Boolean, sessionId: String })
const emit = defineEmits(['answered', 'listened'])

// Voices render in the background after a topic is generated, so a segment can
// arrive caption-only. Swap in the audio the moment it lands.
const liveSeg = ref(null)
const seg = computed(() => liveSeg.value || props.card.payload.segment || { turns: [] })
const turns = computed(() => seg.value.turns || [])
const awaitingVoices = computed(() => turns.value.length > 0 && !turns.value[0].audio)

const idx = ref(0)
const playing = ref(false)
const showQuiz = ref(false)
const picked = ref(null)
// Set once the segment has played out. The feed unlocks off this, so it also
// stops a late-arriving audio render from restarting a card already cleared.
const finished = ref(false)

const current = computed(() => turns.value[idx.value] || {})
const quiz = computed(() => seg.value.quiz_after)

let audio = null
let preload = null
let timer = null
let poll = null

async function watchForVoices() {
  if (poll || !awaitingVoices.value) return
  const slug = props.card.payload.topic
  if (!slug) return
  poll = setInterval(async () => {
    try {
      const { segment, audio_ready } = await api.segment(slug, seg.value.id)
      if (segment && segment.turns?.some((turn) => turn.audio)) {
        liveSeg.value = segment
        stopPolling()
        // Caption playback has not started yet, so voices begin once from the
        // first turn instead of restarting a line the listener already read.
        if (props.active && !finished.value) playTurn(0)
      } else if (audio_ready) {
        if (segment) liveSeg.value = segment
        stopPolling()
        // Rendering completed without usable audio. Run the caption fallback
        // once; it no longer races and restarts when voices arrive.
        if (props.active && !finished.value) playTurn(0)
      }
    } catch {
      stopPolling()
    }
  }, 4000)
}

function stopPolling() {
  if (poll) { clearInterval(poll); poll = null }
}

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
    audio.onerror = () => playCaptionFallback(n, turn)
    audio.play().catch(() => playCaptionFallback(n, turn))
    // Preload N+1 during N so the swap on `ended` is not audibly gappy.
    if (next && next.audio) preload = new Audio(next.audio)
  } else {
    timer = setTimeout(() => playTurn(n + 1), (turn.dur || 3) * 1000)
  }
  playing.value = true
}

function playCaptionFallback(n, turn) {
  // Missing/blocked clips still advance using the caption timing instead of
  // leaving the podcast stuck forever on a silent line.
  if (timer) return
  if (audio) {
    audio.onended = null
    audio.onerror = null
    audio.pause()
    audio = null
  }
  timer = setTimeout(() => playTurn(n + 1), (turn.dur || 3) * 1000)
  playing.value = true
}

function finishSegment() {
  playing.value = false
  finished.value = true
  if (quiz.value) showQuiz.value = true
  // The lock: the feed will not hand the user anything past this card until
  // they have actually listened all the way through.
  emit('listened')
}

function stopAudio() {
  if (audio) { audio.pause(); audio = null }
  if (timer) { clearTimeout(timer); timer = null }
  preload = null
}

function toggle() {
  if (showQuiz.value) return
  if (awaitingVoices.value) {
    watchForVoices()
    return
  }
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
    if (a) {
      if (awaitingVoices.value) watchForVoices()
      else playTurn(0)
    } else {
      stopAudio()
      stopPolling()
      playing.value = false
      idx.value = 0
      showQuiz.value = false
      picked.value = null
      finished.value = false
    }
  },
  { immediate: true, flush: 'post' },
)

onBeforeUnmount(() => {
  stopAudio()
  stopPolling()
})
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
        <div class="k">
          {{ card.payload.title }}
          <em v-if="awaitingVoices" class="rendering">· voices rendering</em>
        </div>

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
          <div class="q line" :key="idx">
            {{ awaitingVoices ? 'Preparing both voices…' : current.text }}
          </div>
        </transition>

        <div class="wave" :class="{ on: playing }">
          <i v-for="n in 20" :key="n" :style="{ animationDelay: n * 0.055 + 's' }" />
        </div>
      </div>

      <div class="controls">
        <button class="ctl" @click="step(-1)">◀◀</button>
        <button class="btn btn-primary play" :disabled="awaitingVoices" @click="toggle">
          {{ awaitingVoices ? 'Preparing voices…' : playing ? 'Pause' : 'Play' }}
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
.rendering { font-style: normal; color: var(--dim); text-transform: none; letter-spacing: 0; }

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
