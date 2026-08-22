<script setup>
import { ref, watch, computed, onBeforeUnmount } from 'vue'

const props = defineProps({ card: Object, active: Boolean })
const el = ref(null)
const liked = ref(false)

// Stable fake engagement per clip - a reel with no numbers reads as a mockup.
const HANDLES = [
  { avatar: '🥣', user: 'cerealtok' },
  { avatar: '🐶', user: 'theo.does.tricks' },
  { avatar: '🐸', user: 'wildliferizz' },
  { avatar: '🎧', user: 'quantum_chill' },
  { avatar: '🛹', user: 'concretegoblin' },
]

function hash(s) {
  let h = 0
  for (let i = 0; i < String(s).length; i++) h = (h * 31 + String(s).charCodeAt(i)) | 0
  return Math.abs(h)
}

const seed = computed(() => hash(props.card.id))
const handle = computed(() => HANDLES[seed.value % HANDLES.length])
const likes = computed(() => {
  const n = 200 + (seed.value % 4600)
  return n > 999 ? (n / 1000).toFixed(1) + 'M' : n + 'K'
})
const comments = computed(() => {
  const n = (seed.value % 380) + 4
  return n >= 100 ? n + 'K' : (n + (seed.value % 10) / 10).toFixed(1) + 'K'
})
const caption = computed(() => props.card.payload.caption || 'brainrot')

// Same play-only-while-visible contract as VideoCard. `immediate` + post
// flush so a card that mounts already active still plays - a plain watcher
// never fires for the initial value, which left the first clip in the feed
// frozen on frame one.
watch(
  () => props.active,
  (a) => {
    const v = el.value
    if (!v) return
    if (a) v.play().catch(() => {})
    else {
      v.pause()
      v.currentTime = 0
    }
  },
  { immediate: true, flush: 'post' },
)

onBeforeUnmount(() => {
  if (el.value) el.value.pause()
})
</script>

<template>
  <div class="card reel">
    <div class="reel-bg">
      <video
        v-if="card.payload.src"
        ref="el"
        :src="card.payload.src"
        muted
        loop
        playsinline
        preload="metadata"
      />
      <span v-else>🌀</span>
    </div>

    <div class="reel-scrim-top" />
    <div class="reel-scrim-bottom" />

    <!-- GIPHY's API terms require attribution on content served through it. -->
    <a
      v-if="card.payload.giphy_url" class="giphy-badge"
      :href="card.payload.giphy_url" target="_blank" rel="noopener"
      @click.stop
    >Powered by GIPHY</a>

    <div class="reel-actions">
      <div class="act" @click="liked = !liked">
        <span class="ic">{{ liked ? '❤️' : '♡' }}</span>
        <span class="n">{{ likes }}</span>
      </div>
      <div class="act"><span class="ic">💬</span><span class="n">{{ comments }}</span></div>
      <div class="act"><span class="ic">✈</span><span class="n">Share</span></div>
      <div class="act"><span class="ic">⋯</span></div>
    </div>

    <div class="reel-caption">
      <div class="user-row">
        <div class="avatar">{{ handle.avatar }}</div>
        <span class="uname">{{ handle.user }}</span>
        <span class="follow">Follow</span>
      </div>
      <div class="cap">{{ caption }}</div>
      <div class="music">♪ <span>original audio — {{ handle.user }}</span></div>
    </div>

    <div class="tap-hint"><span>swipe up to keep scrolling</span></div>
  </div>
</template>

<style scoped>
.giphy-badge {
  position: absolute; top: 16px; right: 14px; z-index: 8;
  padding: 5px 10px; border-radius: 999px;
  background: rgba(0, 0, 0, 0.45); backdrop-filter: blur(4px);
  color: #fff; font-size: 10px; font-weight: 800; letter-spacing: 0.02em;
  text-decoration: none;
}
</style>
