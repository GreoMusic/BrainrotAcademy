<script setup>
import { computed } from 'vue'
const props = defineProps({ progress: Object, budgetMax: { type: Number, default: 8 } })

// Only the reel gets the budget bar - a light content screen carries its own
// chrome, and a floating overlay on top of it just looks like a bug.
const onReel = computed(() => props.progress.stage === 'SCROLL')
const pct = computed(() =>
  Math.max(0, Math.min(100, (props.progress.scroll_budget / props.budgetMax) * 100)),
)
</script>

<template>
  <div v-if="onReel" class="budget">
    <div class="budget-row">
      <span>SCROLL BUDGET</span>
      <span>{{ progress.scroll_budget }} left</span>
    </div>
    <div class="budget-track">
      <div class="budget-fill" :style="{ width: pct + '%' }" />
    </div>
  </div>
</template>
