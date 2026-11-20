<script setup>
import { computed, ref } from 'vue'
import SearchSelect from '@/components/SearchSelect.vue'
import { STREAM_TYPES, flag } from '@/utils/format'

const props = defineProps({
  stream: { type: Object, required: true },
  offersById: { type: Object, default: () => ({}) },
  offerOptions: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['add-offer', 'remove-offer'])

const typeMeta = computed(
  () => STREAM_TYPES[props.stream.type] ?? { label: props.stream.type, tone: 'slate' },
)
const editableOffers = computed(() => props.stream.schema === 'landings')
const newOffer = ref(null)

const availableOptions = computed(() => {
  const used = new Set(props.stream.offers.map((o) => o.offer_id))
  return props.offerOptions.filter((o) => !used.has(o.value))
})

function payloadList(filter) {
  const value = filter.payload
  if (Array.isArray(value)) return value
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : [value]
    } catch {
      return [value]
    }
  }
  return value == null ? [] : [String(value)]
}

function add() {
  if (!newOffer.value) return
  emit('add-offer', newOffer.value)
  newOffer.value = null
}
</script>

<template>
  <article class="card stream" :class="`stream-${stream.type}`">
    <header class="stream-head">
      <span class="position mono">{{ stream.position ?? '—' }}</span>
      <div class="titles">
        <h3>{{ stream.name || `Поток #${stream.id}` }}</h3>
        <div class="row meta">
          <span class="badge" :class="`tone-${typeMeta.tone}`">{{ typeMeta.label }}</span>
          <span class="chip">schema: {{ stream.schema }}</span>
          <span class="chip">id: {{ stream.id }}</span>
          <span v-if="stream.state !== 'active'" class="badge tone-slate">{{ stream.state }}</span>
        </div>
      </div>
    </header>

    <div class="stream-body">
      <div v-if="stream.filters.length" class="block">
        <span class="block-label">Фильтры</span>
        <div class="row wrap">
          <span v-for="f in stream.filters" :key="f.id ?? f.name" class="filter">
            <span class="faint">{{ f.name }}</span>
            <span :class="f.mode === 'reject' ? 'neg' : 'pos'">
              {{ f.mode === 'reject' ? '≠' : '=' }}
            </span>
            <span v-for="v in payloadList(f)" :key="v">
              {{ f.name === 'country' ? flag(v) : '' }} {{ v }}
            </span>
          </span>
        </div>
      </div>

      <div v-if="stream.schema === 'redirect'" class="block">
        <span class="block-label">Редирект ({{ stream.action_type }})</span>
        <a
          v-if="typeof stream.action_payload === 'string'"
          :href="stream.action_payload"
          target="_blank"
          rel="noreferrer"
          class="mono"
        >
          {{ stream.action_payload }}
        </a>
      </div>

      <div v-if="editableOffers" class="block">
        <span class="block-label">Офферы</span>
        <ul class="offers">
          <li v-for="o in stream.offers" :key="o.offer_id">
            <span class="chip">#{{ o.offer_id }}</span>
            <span class="offer-name">
              {{ offersById[o.offer_id]?.name ?? 'Неизвестный оффер' }}
            </span>
            <span class="share-bar" :title="`${o.share}%`">
              <span :style="{ width: `${o.share}%` }" />
            </span>
            <span class="share mono">{{ o.share }}%</span>
            <button
              type="button"
              class="btn btn-ghost btn-sm btn-danger"
              :disabled="busy || stream.offers.length <= 1"
              :title="stream.offers.length <= 1 ? 'В потоке должен остаться хотя бы один оффер' : ''"
              @click="emit('remove-offer', o.offer_id)"
            >
              Удалить
            </button>
          </li>
          <li v-if="!stream.offers.length" class="faint">Офферов нет</li>
        </ul>

        <div class="add-offer">
          <SearchSelect
            v-model="newOffer"
            :options="availableOptions"
            placeholder="Добавить оффер…"
            :disabled="busy || !availableOptions.length"
          />
          <button type="button" class="btn" :disabled="busy || !newOffer" @click="add">
            <span v-if="busy" class="spinner" /> Добавить
          </button>
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.stream {
  border-left: 3px solid var(--border-strong);
}
.stream-forced {
  border-left-color: var(--amber);
}
.stream-regular {
  border-left-color: var(--teal);
}
.stream-head {
  display: flex;
  gap: 14px;
  padding: 16px 20px 0;
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
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
h3 {
  font-size: 15px;
}
.meta {
  flex-wrap: wrap;
  gap: 6px;
}
.stream-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px 20px 64px;
}
.block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.block-label {
  color: var(--text-3);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.wrap {
  flex-wrap: wrap;
}
.filter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
}
.pos {
  color: var(--green);
  font-weight: 700;
}
.neg {
  color: var(--red);
  font-weight: 700;
}
.offers {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.offers li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border);
}
.offers li:last-child {
  border-bottom: none;
}
.offer-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.share-bar {
  width: 90px;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--slate-soft);
}
.share-bar span {
  display: block;
  height: 100%;
  background: var(--teal);
}
.share {
  width: 40px;
  color: var(--text-2);
  text-align: right;
}
.add-offer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  max-width: 520px;
}

@media (max-width: 640px) {
  .stream-body {
    padding-left: 20px;
  }
  .share-bar {
    display: none;
  }
}
</style>
