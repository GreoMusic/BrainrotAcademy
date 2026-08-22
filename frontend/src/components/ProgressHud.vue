<script setup>
defineProps({ progress: Object })

const STAGE_LABEL = {
  LEARN: 'learning',
  CHECK: 'prove it',
  SCROLL: 'brainrot unlocked',
  FRICTION: 'touch grass',
}
</script>

<template>
  <div class="hud">
    <div class="left">
      <span class="stage" :class="progress.stage">{{ STAGE_LABEL[progress.stage] }}</span>
    </div>

    <div class="right">
      <!-- Scroll budget is the whole economy of the app, so it gets the loudest slot. -->
      <span v-if="progress.stage === 'SCROLL'" class="budget">
        {{ progress.scroll_budget }} left
      </span>
      <span class="mastery">
        <svg viewBox="0 0 36 36" class="ring">
          <circle cx="18" cy="18" r="15" class="track" />
          <circle
            cx="18" cy="18" r="15" class="fill"
            :stroke-dasharray="`${(progress.mastery_pct / 100) * 94.2} 94.2`"
          />
        </svg>
        <b>{{ progress.mastered }}/{{ progress.total }}</b>
      </span>
    </div>
  </div>
</template>

<style scoped>
.hud {
  position: absolute;
  top: 0; left: 0; right: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  padding-top: max(14px, env(safe-area-inset-top));
  background: linear-gradient(180deg, rgba(0,0,0,0.6), transparent);
  pointer-events: none;
}
.stage {
  font-size: 11px; font-weight: 800; letter-spacing: 0.13em; text-transform: uppercase;
  padding: 6px 11px; border-radius: 999px;
  background: rgba(255,255,255,0.14); backdrop-filter: blur(10px);
}
.stage.SCROLL { background: rgba(255,45,129,0.9); }
.stage.FRICTION { background: rgba(255,210,63,0.92); color: #201a00; }
.stage.CHECK { background: rgba(0,229,192,0.85); color: #00201c; }
.right { display: flex; align-items: center; gap: 10px; }
.budget {
  font-size: 12px; font-weight: 800; padding: 6px 10px; border-radius: 999px;
  background: rgba(0,0,0,0.45); backdrop-filter: blur(10px);
}
.mastery { position: relative; display: grid; place-items: center; width: 38px; height: 38px; }
.ring { position: absolute; inset: 0; transform: rotate(-90deg); }
.track { fill: none; stroke: rgba(255,255,255,0.16); stroke-width: 3; }
.fill {
  fill: none; stroke: var(--accent-2); stroke-width: 3; stroke-linecap: round;
  transition: stroke-dasharray 0.5s ease;
}
.mastery b { font-size: 10px; font-weight: 800; }
</style>
