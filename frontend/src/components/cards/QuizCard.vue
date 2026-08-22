<script setup>
import { ref, computed } from 'vue'
const props = defineProps({ card: Object, active: Boolean })
const emit = defineEmits(['answered'])

const picked = ref(null)
const done = ref(false)
const correct = computed(() => picked.value === props.card.payload.correct)

function choose(i) {
  if (done.value) return
  picked.value = i
  done.value = true
  // Let the verdict land visually before the feed moves on.
  setTimeout(() => emit('answered', i === props.card.payload.correct), 1900)
}

function cls(i) {
  if (!done.value) return 'btn-outline'
  if (i === props.card.payload.correct) return 'opt-correct'
  return i === picked.value ? 'opt-wrong' : 'btn-outline muted'
}
</script>

<template>
  <div class="card lightscreen">
    <div class="content">
      <span class="pill blue">enrollment check</span>
      <p class="screen-title">{{ card.payload.q }}</p>
      <p class="screen-sub">Prove it to get back in the feed.</p>

      <div class="stack">
        <button
          v-for="(opt, i) in card.payload.options" :key="i"
          class="btn" :class="cls(i)" :disabled="done" @click="choose(i)"
        >{{ opt }}</button>
      </div>

      <div class="spacer" />

      <transition name="fade">
        <div v-if="done" class="explain" :class="{ good: correct }">
          <b>{{ correct ? 'Correct.' : 'Not quite.' }}</b>
          {{ card.payload.explain }}
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
.spacer { flex: 1; min-height: 12px; }
.opt-correct { background: rgba(0, 149, 246, 0.1); color: var(--blue); border: 1.5px solid var(--blue); }
.opt-wrong { background: #fff0f3; color: var(--g3); border: 1.5px solid var(--g3); }
.muted { opacity: 0.55; }
.explain {
  padding: 13px 14px; border-radius: 12px; background: #f7f7f7;
  font-size: 12.5px; line-height: 1.5; color: #555;
}
.explain.good { background: rgba(0, 149, 246, 0.08); }
.explain b { display: block; margin-bottom: 3px; color: var(--ink); }
</style>
