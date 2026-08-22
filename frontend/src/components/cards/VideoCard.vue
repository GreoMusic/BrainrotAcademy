<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
const props = defineProps({ card: Object, active: Boolean })
const el = ref(null)

// The behaviour contract every media card shares: play only while on screen.
// `immediate` + post flush so a card that mounts already active still plays:
// a plain watcher never fires for the initial value, which left the very first
// video in the feed frozen on frame one.
watch(() => props.active, (a) => {
  const v = el.value
  if (!v) return
  if (a) v.play().catch(() => {})
  else { v.pause(); v.currentTime = 0 }
}, { immediate: true, flush: 'post' })
onBeforeUnmount(() => el.value && el.value.pause())
</script>

<template>
  <div class="card vid">
    <div class="card-gradient" style="--g1:#1b0620; --g2:#000" />
    <video
      v-if="card.payload.src"
      ref="el" :src="card.payload.src"
      muted loop playsinline preload="metadata"
    />
    <div v-else class="placeholder">
      <div class="emoji">📱</div>
      <div class="body">Drop .mp4 files into <code>backend/static/clips/</code></div>
    </div>
    <div class="caption">{{ card.payload.caption || 'brainrot' }}</div>
  </div>
</template>

<style scoped>
.vid { padding: 0; justify-content: flex-end; }
video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.placeholder { position: absolute; inset: 0; display: grid; place-content: center; gap: 14px; text-align: center; padding: 30px; }
.emoji { font-size: 64px; }
code { background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 6px; font-size: 14px; }
.caption {
  position: relative; padding: 22px; padding-bottom: 108px; font-weight: 700;
  text-shadow: 0 2px 12px rgba(0,0,0,0.8);
}
</style>
