<script setup>
/** Иконка «обновить»; во время загрузки крутится. */
defineProps({ spinning: { type: Boolean, default: false } })
</script>

<template>
  <svg class="refresh-icon" :class="{ spinning }" viewBox="0 0 20 20" aria-hidden="true">
    <path d="M16 10a6 6 0 1 1-1.76-4.24" />
    <path d="M16 3.5v3.25h-3.25" />
  </svg>
</template>

<style scoped>
.refresh-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.spinning {
  animation: spin 0.8s linear infinite;
}
</style>
