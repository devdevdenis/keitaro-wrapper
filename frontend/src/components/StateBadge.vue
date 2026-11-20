<script setup>
import { computed } from 'vue'
import { STATES } from '@/utils/format'

const props = defineProps({ state: { type: String, default: null } })
const meta = computed(() => STATES[props.state] ?? { label: props.state ?? '—', tone: 'slate' })
</script>

<template>
  <span class="badge" :class="`tone-${meta.tone}`">{{ meta.label }}</span>
</template>
