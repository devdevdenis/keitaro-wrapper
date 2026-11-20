<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<template>
  <header class="page-header">
    <div class="titles">
      <slot name="eyebrow" />
      <h1>{{ title }}</h1>
      <p v-if="subtitle || $slots.subtitle" class="muted">
        <slot name="subtitle">{{ subtitle }}</slot>
      </p>
    </div>
    <div v-if="$slots.actions" class="actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}
.titles {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
h1 {
  font-size: 24px;
  overflow-wrap: anywhere;
}
p {
  margin: 0;
}
.actions {
  display: flex;
  gap: 8px;
}
</style>
