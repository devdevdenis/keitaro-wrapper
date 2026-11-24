<script setup>
/**
 * Схема кампании: куда уходит трафик. Потоки идут в порядке, в котором их проверяет Keitaro —
 * сначала перехватывающие, потом обычные, потом резервные; внутри типа — по позиции.
 * Показывает то, что видно в карточках, то есть с учётом неопубликованных правок.
 */
import { computed } from 'vue'
import { flag } from '@/utils/format'

const props = defineProps({
  campaignName: { type: String, default: '' },
  streams: { type: Array, default: () => [] },
  offersById: { type: Object, default: () => ({}) },
  placeholder: { type: String, default: '' },
})
const emit = defineEmits(['select'])

const TYPE_ORDER = { forced: 0, regular: 1, default: 2 }
const KIND_LABEL = { intercept: 'перехватывающий', regular: 'обычный', other: 'другой' }
const MAX_OFFERS = 4

const ordered = computed(() =>
  [...props.streams].sort(
    (a, b) =>
      (TYPE_ORDER[a.type] ?? 3) - (TYPE_ORDER[b.type] ?? 3) ||
      a.position - b.position ||
      a.id - b.id,
  ),
)

const activeOffers = (stream) => stream.offers.filter((o) => !o.removed)
const host = (url) => url.replace(/^https?:\/\//, '').replace(/\/$/, '') || '—'
const offerName = (id) => props.offersById[id]?.name ?? `Оффер #${id}`
</script>

<template>
  <div class="flow">
    <div class="node source">
      <span class="kicker">Входящий трафик</span>
      <strong>{{ campaignName || 'Новая кампания' }}</strong>
    </div>

    <p v-if="!ordered.length" class="empty faint">{{ placeholder || 'Потоков нет' }}</p>

    <template v-for="(stream, i) in ordered" :key="stream.id">
      <div class="connector" :class="{ labeled: i > 0 }"><span v-if="i > 0">иначе</span></div>

      <button
        type="button"
        class="node stream"
        :class="[`kind-${stream.kind}`, { draft: stream.has_draft }]"
        :title="`Перейти к потоку «${stream.name}»`"
        @click="emit('select', stream.id)"
      >
        <span class="head">
          <span class="num mono">{{ i + 1 }}</span>
          <strong class="name">{{ stream.name || 'Без названия' }}</strong>
          <span class="kind faint">{{ KIND_LABEL[stream.kind] }}</span>
          <span v-if="stream.is_new" class="badge plain tone-amber">новый</span>
          <span v-else-if="stream.has_draft" class="badge plain tone-amber">черновик</span>
        </span>

        <template v-if="stream.kind === 'intercept'">
          <span class="line">
            <span class="faint">если</span>
            <template v-if="stream.countries.length">
              <span class="chip">country ∈ {{ stream.countries.join(', ') }}</span>
              <span class="flags">{{ stream.countries.map(flag).join(' ') }}</span>
            </template>
            <span v-else class="warn">страны не выбраны</span>
            <span class="chip logic" title="Логика фильтров потока">
              логика: {{ stream.filter_or ? 'ИЛИ' : 'И' }}
            </span>
          </span>
          <span class="line">
            <span class="arrow">→</span>
            <span class="mono">{{ host(stream.redirect_url) }}</span>
          </span>
        </template>

        <template v-else-if="stream.kind === 'regular'">
          <span v-for="o in activeOffers(stream).slice(0, MAX_OFFERS)" :key="o.offer_id" class="line">
            <span class="arrow">→</span>
            <span class="offer">{{ offerName(o.offer_id) }}</span>
            <span class="share mono">{{ o.share }}%</span>
          </span>
          <span v-if="activeOffers(stream).length > MAX_OFFERS" class="line faint">
            и ещё {{ activeOffers(stream).length - MAX_OFFERS }}
          </span>
          <span v-if="!activeOffers(stream).length" class="line warn">офферов нет</span>
        </template>

        <span v-else class="line faint">настройки — в Keitaro</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.flow {
  display: flex;
  flex-direction: column;
}
.node {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  text-align: left;
}
.source {
  background: var(--surface-2);
}
.source strong {
  overflow-wrap: anywhere;
}
.kicker {
  color: var(--text-3);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.stream {
  border-left: 3px solid var(--border-strong);
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
}
.stream:hover {
  background: var(--surface-2);
}
.kind-intercept {
  border-left-color: var(--amber);
}
.kind-regular {
  border-left-color: var(--teal);
}
.stream.draft {
  border-style: dashed;
  border-left-style: solid;
}
.head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.num {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 5px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text-2);
  font-size: 11px;
  font-weight: 700;
}
.name {
  overflow-wrap: anywhere;
}
.kind {
  font-size: 12px;
}
.line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 13px;
}
.arrow {
  color: var(--text-3);
  font-weight: 700;
}
.offer {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.share {
  color: var(--text-3);
  font-size: 12px;
}
.logic {
  margin-left: auto;
}
.warn {
  color: var(--amber);
}
.empty {
  margin: 12px 0 0;
  font-size: 13px;
}
.connector {
  position: relative;
  width: 2px;
  height: 16px;
  margin-left: 22px;
  background: var(--border-strong);
}
.connector.labeled {
  height: 26px;
}
.connector span {
  position: absolute;
  top: 50%;
  left: 10px;
  transform: translateY(-50%);
  color: var(--text-3);
  font-size: 12px;
  white-space: nowrap;
}
</style>
