<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { api } from '../api'
import ProgressHud from '../components/ProgressHud.vue'
import FlashcardCard from '../components/cards/FlashcardCard.vue'
import FunFactCard from '../components/cards/FunFactCard.vue'
import VideoCard from '../components/cards/VideoCard.vue'
import QuizCard from '../components/cards/QuizCard.vue'
import MathGateCard from '../components/cards/MathGateCard.vue'
import PodcastCard from '../components/cards/PodcastCard.vue'
import TouchGrassCard from '../components/cards/TouchGrassCard.vue'
import TalkToHumanCard from '../components/cards/TalkToHumanCard.vue'
import CoachCard from '../components/cards/CoachCard.vue'

const props = defineProps({ session: Object })

const CARD_FOR = {
  flashcard: FlashcardCard,
  fun_fact: FunFactCard,
  video: VideoCard,
  quiz: QuizCard,
  coach: CoachCard,
  podcast: PodcastCard,
  math_gate: MathGateCard,
  touch_grass: TouchGrassCard,
  talk_to_human: TalkToHumanCard,
}

// Cards the user must resolve before the feed may grow past them.
// This is what makes a gate a gate: it blocks simply by being the last card,
// so there is no scroll-locking hack anywhere.
const BLOCKING = new Set(['quiz', 'coach', 'math_gate', 'touch_grass', 'talk_to_human'])

const cards = ref([])
const activeIndex = ref(0)
const progress = ref(props.session.progress)
const loading = ref(false)
const error = ref('')

const feedEl = ref(null)
let observer = null

const lastIsBlocking = computed(() => {
  const last = cards.value[cards.value.length - 1]
  return last ? BLOCKING.has(last.type) && !last.resolved : false
})

async function fetchMore(n = 2) {
  if (loading.value || lastIsBlocking.value) return
  loading.value = true
  try {
    const data = await api.next(props.session.session_id, n)
    for (const c of data.cards) {
      cards.value.push(c)
      // Never queue past a card that needs an answer: the server's choice of
      // next card depends on that answer being recorded first.
      if (BLOCKING.has(c.type)) break
    }
    progress.value = data.progress
    await nextTick()
    observeAll()
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    loading.value = false
  }
}

async function ensureBuffer() {
  let guard = 0
  while (!lastIsBlocking.value && cards.value.length - activeIndex.value < 3 && guard++ < 4) {
    await fetchMore(2)
  }
}

function observeAll() {
  if (!observer) return
  const els = feedEl.value ? feedEl.value.querySelectorAll('[data-card]') : []
  els.forEach((el) => observer.observe(el))
}

function scrollToNext() {
  nextTick(() => {
    const els = feedEl.value ? feedEl.value.querySelectorAll('[data-card]') : null
    const target = els ? els[activeIndex.value + 1] : null
    if (target) target.scrollIntoView({ behavior: 'smooth' })
  })
}

/** A quiz was answered: record it, then let the feed grow again. */
async function onAnswered(card, correct) {
  card.resolved = true
  try {
    const res = await api.answer(
      props.session.session_id,
      card.id,
      correct,
      card.payload ? card.payload.item_id : undefined,
    )
    progress.value = res.progress
  } catch (e) {
    error.value = String(e.message || e)
  }
  await ensureBuffer()
  scrollToNext()
}

/** A friction gate was cleared. */
async function onCleared(card) {
  card.resolved = true
  try {
    const res = await api.clearFriction(props.session.session_id)
    progress.value = res.progress
  } catch (e) {
    error.value = String(e.message || e)
  }
  await ensureBuffer()
  scrollToNext()
}

onMounted(async () => {
  observer = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting && e.intersectionRatio > 0.6) {
          activeIndex.value = Number(e.target.dataset.card)
          ensureBuffer()
        }
      }
    },
    { threshold: [0.6] },
  )
  await fetchMore(3)
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})
</script>

<template>
  <div class="shell">
    <ProgressHud :progress="progress" />

    <div class="feed" ref="feedEl">
      <div v-for="(card, i) in cards" :key="card.id + ':' + i" :data-card="i">
        <component
          :is="CARD_FOR[card.type]"
          :card="card"
          :active="i === activeIndex"
          :session-id="session.session_id"
          @answered="(correct) => onAnswered(card, correct)"
          @cleared="() => onCleared(card)"
        />
      </div>

      <div v-if="!cards.length" class="card">
        <div class="card-gradient" style="--g1: #1a1030; --g2: #07060d" />
        <div class="eyebrow">loading</div>
        <div class="big">Warming up your feed…</div>
      </div>
    </div>

    <div v-if="error" class="err" @click="error = ''">{{ error }}</div>
  </div>
</template>

<style scoped>
.err {
  position: absolute;
  bottom: 16px;
  left: 16px;
  right: 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 45, 129, 0.92);
  font-size: 13px;
  font-weight: 600;
  z-index: 50;
}
</style>
