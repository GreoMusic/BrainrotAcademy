<script setup>
defineProps({ slug: { type: String, required: true } })
</script>

<template>
  <span class="subject-icon" aria-hidden="true">
    <svg v-if="slug === 'english'" viewBox="0 0 24 24">
      <path d="M4 5.5c2.8-.7 5.5-.1 8 1.8v11c-2.5-1.9-5.2-2.5-8-1.8zM20 5.5c-2.8-.7-5.5-.1-8 1.8v11c2.5-1.9 5.2-2.5 8-1.8z" />
    </svg>
    <svg v-else-if="slug === 'science'" viewBox="0 0 24 24">
      <path d="M9 3h6M10 3v6l-5 8.5A2.3 2.3 0 0 0 7 21h10a2.3 2.3 0 0 0 2-3.5L14 9V3M7.8 16h8.4" />
    </svg>
    <svg v-else-if="slug === 'math'" viewBox="0 0 24 24">
      <path d="M4 13h3l2.2 6L14 5h6M15.5 15.5h4M17.5 13.5v4" />
    </svg>
    <svg v-else-if="slug === 'engineering'" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" />
    </svg>
    <svg v-else-if="slug === 'coding'" viewBox="0 0 24 24">
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <path d="m8 10-2 2 2 2M11 15h5" />
    </svg>
    <svg v-else viewBox="0 0 24 24">
      <path d="M5 8h14M6.5 8v9M10.2 8v9M13.8 8v9M17.5 8v9M4 19h16M12 3l8 3H4z" />
    </svg>
  </span>
</template>

<style scoped>
.subject-icon {
  width: 35px; height: 35px; display: grid; place-items: center;
  border-radius: 11px; color: #cf5521; background: #fff4ec;
  box-shadow: inset 0 0 0 1px rgba(207, 85, 33, 0.08);
}
.subject-icon svg {
  width: 20px; height: 20px; fill: none; stroke: currentColor;
  stroke-width: 1.65; stroke-linecap: round; stroke-linejoin: round;
}
</style>
