<script setup>
/**
 * Карточка потока в редакторе: название, тип, статус черновика, удаление, Push to KT / Cancel.
 * Содержимое (поля перехватывающего потока или таблица офферов) — в слоте.
 */
import { computed, ref, watch } from 'vue'
import AlertBox from '@/components/AlertBox.vue'
import { STREAM_TYPES } from '@/utils/format'

const props = defineProps({
  stream: { type: Object, required: true },
  busy: { type: String, default: null }, // действие, которое сейчас выполняется
})
const emit = defineEmits(['patch', 'cancel', 'delete'])

const KINDS = [
  { value: 'intercept', label: 'Перехватывающий' },
  { value: 'regular', label: 'Обычный' },
]

const disabled = computed(() => Boolean(props.busy))
const editable = computed(() => props.stream.kind !== 'other')
const typeMeta = computed(
  () => STREAM_TYPES[props.stream.type] ?? { label: props.stream.type ?? '—', tone: 'slate' },
)

// название правится на месте и уходит в черновик по Enter / потере фокуса
const name = ref(props.stream.name)
watch(
  () => props.stream.name,
  (value) => (name.value = value),
)
function saveName() {
  if (name.value !== props.stream.name) emit('patch', { name: name.value })
}
</script>

<template>
  <article
    class="card stream"
    :class="[`kind-${stream.kind}`, { dirty: stream.has_draft, conflict: stream.conflict }]"
    :aria-label="stream.name || 'Поток'"
  >
    <header class="stream-head">
      <span class="position mono">{{ stream.position || '—' }}</span>
      <div class="titles">
        <input
          v-if="editable"
          v-model="name"
          class="name-input"
          maxlength="100"
          placeholder="Название потока"
          aria-label="Название потока"
          :disabled="disabled"
          @change="saveName"
          @keydown.enter="$event.target.blur()"
        />
        <h3 v-else>{{ stream.name || 'Без названия' }}</h3>
        <div class="row meta">
          <!-- тип выбирается только у неопубликованного потока -->
          <div v-if="stream.is_new" class="kind-switch" role="radiogroup" aria-label="Тип потока">
            <button
              v-for="option in KINDS"
              :key="option.value"
              type="button"
              role="radio"
              class="kind-option"
              :class="[`kind-option-${option.value}`, { active: stream.kind === option.value }]"
              :aria-checked="stream.kind === option.value"
              :disabled="disabled"
              @click="stream.kind !== option.value && emit('patch', { kind: option.value })"
            >
              {{ option.label }}
            </button>
          </div>
          <span v-else class="badge" :class="`tone-${typeMeta.tone}`">{{ typeMeta.label }}</span>
          <span v-if="stream.keitaro_id" class="chip">id: {{ stream.keitaro_id }}</span>
        </div>
      </div>
      <span v-if="stream.is_new" class="badge tone-amber">Новый · не опубликован</span>
      <span v-else-if="stream.has_draft" class="badge tone-amber">Не опубликовано</span>
      <button
        type="button"
        class="btn btn-ghost btn-sm btn-danger icon-btn"
        title="Удалить поток"
        :aria-label="`Удалить поток ${stream.name}`"
        :disabled="disabled"
        @click="emit('delete')"
      >
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10M9 9v4M11 9v4" />
        </svg>
      </button>
    </header>

    <div class="stream-content">
      <slot />
    </div>

    <div v-if="stream.problem" class="stream-problem">
      <AlertBox :tone="stream.conflict ? 'red' : 'amber'">{{ stream.problem }}</AlertBox>
    </div>

    <!-- публикуются все потоки сразу (панель внизу карточки «Потоки»); здесь — откат одного -->
    <footer v-if="stream.has_draft && !stream.is_new" class="stream-footer">
      <span class="faint">Есть неопубликованные изменения</span>
      <button type="button" class="btn btn-ghost btn-sm" :disabled="disabled" @click="emit('cancel')">
        <span v-if="busy === 'cancel'" class="spinner" /> Cancel
      </button>
    </footer>
  </article>
</template>

<style scoped>
/* без overflow: hidden — иначе выпадающие списки внутри карточки обрезаются её краем */
.stream {
  border-left: 3px solid var(--border-strong);
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}
.kind-intercept {
  border-left-color: var(--amber);
}
.kind-regular {
  border-left-color: var(--teal);
}
.stream.dirty {
  border-color: var(--amber);
  box-shadow:
    0 0 0 1px var(--amber),
    var(--shadow);
}
.stream.conflict {
  border-color: var(--red);
  box-shadow:
    0 0 0 1px var(--red),
    var(--shadow);
}
.stream-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 8px 12px;
  padding: 14px 16px 14px 20px;
}
.position {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text-2);
  font-weight: 700;
}
.titles {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
h3 {
  font-size: 15px;
  line-height: 30px;
}
.name-input {
  width: 100%;
  max-width: 420px;
  height: 30px;
  margin-left: -8px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 15px;
  font-weight: 650;
  outline: none;
}
.name-input:hover {
  border-color: var(--border);
}
.name-input:focus {
  border-color: var(--accent);
  background: var(--surface);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.meta {
  flex-wrap: wrap;
  gap: 6px;
}
.kind-switch {
  display: inline-flex;
  padding: 2px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-2);
}
.kind-option {
  height: 22px;
  padding: 0 10px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--text-2);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.kind-option:hover:not(:disabled):not(.active) {
  color: var(--text);
}
.kind-option-intercept.active {
  background: var(--amber-soft);
  color: var(--amber);
}
.kind-option-regular.active {
  background: var(--teal-soft);
  color: var(--teal);
}
.kind-option:disabled {
  cursor: not-allowed;
}
.stream-head > .badge {
  flex-shrink: 0;
  margin-top: 4px;
}
.icon-btn {
  width: 30px;
  padding: 0;
}
.icon-btn svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.stream-content {
  border-top: 1px solid var(--border);
}
.stream-problem {
  padding: 0 20px 16px;
}
.stream-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px 8px 20px;
  font-size: 13px;
  border-top: 1px solid var(--border);
  border-radius: 0 0 var(--radius) var(--radius);
  background: var(--amber-soft);
}
.conflict .stream-footer {
  background: var(--red-soft);
}

@media (max-width: 640px) {
  .stream-head {
    padding: 12px 12px 12px 14px;
  }
  /* бейдж статуса уходит под название, корзина остаётся справа */
  .stream-head > .badge {
    order: 3;
    margin-top: 0;
    margin-left: 42px;
  }
  .stream-problem {
    padding: 0 14px 14px;
  }
  .stream-footer {
    padding: 10px 14px;
  }
}
</style>
