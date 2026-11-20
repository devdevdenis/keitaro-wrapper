<script setup>
defineProps({
  tone: { type: String, default: 'red' },
  title: { type: String, default: '' },
})
</script>

<template>
  <div class="alert" :class="`alert-${tone}`" role="alert">
    <strong v-if="title">{{ title }}</strong>
    <div><slot /></div>
  </div>
</template>

<style scoped>
.alert {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 16px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
}
.alert-red {
  border-color: color-mix(in srgb, var(--red) 25%, transparent);
  background: var(--red-soft);
  color: var(--red);
}
.alert-amber {
  border-color: color-mix(in srgb, var(--amber) 25%, transparent);
  background: var(--amber-soft);
  color: var(--amber);
}
.alert-slate {
  border-color: var(--border);
  background: var(--surface-2);
  color: var(--text-2);
}
</style>
