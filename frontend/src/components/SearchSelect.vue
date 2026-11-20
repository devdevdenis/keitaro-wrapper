<script setup>
import { computed, nextTick, ref, watch } from 'vue'

/**
 * Выпадающий список с поиском.
 * options: [{ value, label, hint?, prefix? }]
 */
const model = defineModel({ type: [String, Number, null], default: null })
const props = defineProps({
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Выберите…' },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  id: { type: String, default: undefined },
})

const open = ref(false)
const query = ref('')
const highlighted = ref(0)
const searchInput = ref(null)
const root = ref(null)

const selected = computed(() => props.options.find((o) => o.value === model.value) ?? null)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.options
  return props.options.filter((o) =>
    `${o.label} ${o.hint ?? ''} ${o.value}`.toLowerCase().includes(q),
  )
})

watch(filtered, () => (highlighted.value = 0))

async function toggle() {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) {
    query.value = ''
    const idx = filtered.value.findIndex((o) => o.value === model.value)
    highlighted.value = Math.max(idx, 0)
    await nextTick()
    searchInput.value?.focus()
  }
}

function choose(option) {
  model.value = option.value
  open.value = false
}

function onKeydown(event) {
  if (event.key === 'ArrowDown') {
    highlighted.value = Math.min(highlighted.value + 1, filtered.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    highlighted.value = Math.max(highlighted.value - 1, 0)
  } else if (event.key === 'Enter') {
    const option = filtered.value[highlighted.value]
    if (option) choose(option)
  } else if (event.key === 'Escape') {
    open.value = false
    return
  } else {
    return
  }
  event.preventDefault()
}

function onFocusOut(event) {
  if (!root.value?.contains(event.relatedTarget)) open.value = false
}
</script>

<template>
  <div ref="root" class="select" :class="{ open, disabled }" @focusout="onFocusOut">
    <button
      :id="id"
      type="button"
      class="input trigger"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
    >
      <span v-if="selected" class="value">
        <span v-if="selected.prefix" class="prefix">{{ selected.prefix }}</span>
        {{ selected.label }}
        <span v-if="selected.hint" class="hint">{{ selected.hint }}</span>
      </span>
      <span v-else class="placeholder">{{ loading ? 'Загрузка…' : placeholder }}</span>
      <svg class="caret" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 8l4 4 4-4" /></svg>
    </button>

    <div v-if="open" class="dropdown">
      <input
        ref="searchInput"
        v-model="query"
        class="search"
        placeholder="Поиск…"
        @keydown="onKeydown"
      />
      <ul role="listbox">
        <li
          v-for="(option, i) in filtered"
          :key="option.value"
          role="option"
          tabindex="-1"
          :aria-selected="option.value === model"
          :class="{ highlighted: i === highlighted, chosen: option.value === model }"
          @mousedown.prevent="choose(option)"
          @mouseenter="highlighted = i"
        >
          <span v-if="option.prefix" class="prefix">{{ option.prefix }}</span>
          <span class="label">{{ option.label }}</span>
          <span v-if="option.hint" class="hint">{{ option.hint }}</span>
        </li>
        <li v-if="!filtered.length" class="empty">Ничего не найдено</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.select {
  position: relative;
}
.trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: left;
  cursor: pointer;
}
.trigger:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.value,
.placeholder {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.placeholder {
  color: var(--text-3);
}
.caret {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  fill: none;
  stroke: var(--text-3);
  stroke-width: 2;
  stroke-linecap: round;
  transition: transform 0.15s;
}
.open .caret {
  transform: rotate(180deg);
}
.prefix {
  margin-right: 2px;
}
.hint {
  margin-left: 6px;
  color: var(--text-3);
  font-family: var(--mono);
  font-size: 12px;
}

.dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 20;
  overflow: hidden;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  background: var(--surface);
  box-shadow: var(--shadow-lg);
}
.search {
  width: 100%;
  height: 38px;
  padding: 0 12px;
  border: none;
  border-bottom: 1px solid var(--border);
  background: transparent;
  color: var(--text);
  font: inherit;
  outline: none;
}
ul {
  max-height: 260px;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  list-style: none;
}
li {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
}
li .label {
  flex: 1;
}
li.highlighted {
  background: var(--surface-2);
}
li.chosen {
  color: var(--accent);
  font-weight: 600;
}
li.empty {
  color: var(--text-3);
  cursor: default;
}
</style>
