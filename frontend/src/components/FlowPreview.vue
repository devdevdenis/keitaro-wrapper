<script setup>
/** Наглядная схема потоков будущей кампании. */
import { flag } from '@/utils/format'

defineProps({
  name: { type: String, default: '' },
  countries: { type: Array, default: () => [] }, // [{ code, name }]
  offer: { type: Object, default: null }, // { id, name }
  googleUrl: { type: String, default: 'https://www.google.com' },
})
</script>

<template>
  <div class="flow">
    <div class="node source">
      <span class="node-kicker">Входящий трафик</span>
      <strong class="mono">{{ name || 'test_volper_…' }}</strong>
    </div>

    <div class="connector" />

    <div class="node stream forced">
      <div class="row">
        <span class="badge tone-amber">Поток 1 · перехват</span>
      </div>
      <div class="rule">
        <span class="faint">если</span>
        <span class="chip">
          country {{ countries.length > 1 ? '∈' : '=' }}
          {{ countries.length ? countries.map((c) => c.code).join(', ') : '??' }}
        </span>
        <span v-for="c in countries" :key="c.code">{{ flag(c.code) }} {{ c.name ?? c.code }}</span>
      </div>
      <div class="target">
        <span class="arrow">→</span>
        <span class="mono">{{ googleUrl.replace(/^https?:\/\//, '') }}</span>
      </div>
    </div>

    <div class="connector labeled"><span>иначе</span></div>

    <div class="node stream regular">
      <div class="row">
        <span class="badge tone-teal">Поток 2 · обычный</span>
      </div>
      <div class="target">
        <span class="arrow">→</span>
        <span v-if="offer">
          Оффер <span class="chip">#{{ offer.id }}</span> {{ offer.name }}
        </span>
        <span v-else class="faint">оффер не выбран</span>
        <span class="share">100%</span>
      </div>
    </div>
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
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
}
.source {
  background: var(--surface-2);
}
.source strong {
  overflow-wrap: anywhere;
}
.node-kicker {
  color: var(--text-3);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.forced {
  border-left: 3px solid var(--amber);
}
.regular {
  border-left: 3px solid var(--teal);
}
.rule,
.target {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.arrow {
  color: var(--text-3);
  font-weight: 700;
}
.share {
  margin-left: auto;
  color: var(--text-3);
  font-family: var(--mono);
  font-size: 12px;
}
.connector {
  position: relative;
  width: 2px;
  height: 22px;
  margin-left: 24px;
  background: var(--border-strong);
}
.connector.labeled {
  height: 30px;
}
.connector.labeled span {
  position: absolute;
  top: 50%;
  left: 10px;
  transform: translateY(-50%);
  color: var(--text-3);
  font-size: 12px;
  white-space: nowrap;
}
</style>
