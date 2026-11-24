<script setup>
/**
 * Карточка потока в редакторе: название, тип, удаление; при конфликте с Keitaro — сброс правок.
 * Содержимое (таблица офферов) есть только у обычного потока.
 * Неопубликованные изменения показывает раздел «Потоки» целиком, а не каждая карточка.
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

const disabled = computed(() => Boolean(props.busy))
// правится только поток с офферами; перехватывающие и прочие можно лишь удалить
const editable = computed(() => props.stream.kind === 'regular')
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
  <article class="card stream" :aria-label="stream.name || 'Поток'">
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
          <span class="badge" :class="`tone-${typeMeta.tone}`">{{ typeMeta.label }}</span>
          <span v-if="stream.keitaro_id" class="chip">id: {{ stream.keitaro_id }}</span>
        </div>
      </div>
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

    <!-- у перехватывающих и прочих потоков — только заголовок, без лишних данных -->
    <div v-if="stream.kind === 'regular'" class="stream-content">
      <slot />
    </div>

    <div v-if="stream.problem" class="stream-problem">
      <AlertBox :tone="stream.conflict ? 'red' : 'amber'">
        {{ stream.problem }}
        <!-- откат правок оставлен только для выхода из конфликта с Keitaro -->
        <button
          v-if="stream.conflict"
          type="button"
          class="btn btn-sm reset"
          :disabled="disabled"
          @click="emit('cancel')"
        >
          <span v-if="busy === 'cancel'" class="spinner" /> Взять версию из Keitaro
        </button>
      </AlertBox>
    </div>

  </article>
</template>

<style scoped>
/* без overflow: hidden — иначе выпадающие списки внутри карточки обрезаются её краем */
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
  align-self: center;
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
.reset {
  display: flex;
  margin-top: 8px;
}
.stream-content {
  border-top: 1px solid var(--border);
}
.stream-problem {
  padding: 0 20px 16px;
}
@media (max-width: 640px) {
  .stream-head {
    padding: 12px 12px 12px 14px;
  }
  .stream-problem {
    padding: 0 14px 14px;
  }
}
</style>
