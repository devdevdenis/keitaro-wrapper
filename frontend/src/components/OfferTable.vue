<script setup>
/**
 * Офферы обычного потока: таблица «оффер — доля — действия» и поиск оффера для добавления.
 * Правки копятся в черновике потока; в Keitaro они уходят по Push to KT.
 */
import { computed, ref } from 'vue'
import SearchSelect from '@/components/SearchSelect.vue'

const props = defineProps({
  offers: { type: Array, required: true },
  offersById: { type: Object, default: () => ({}) },
  offerOptions: { type: Array, default: () => [] },
  busy: { type: String, default: null },
})
const emit = defineEmits(['add', 'remove', 'restore', 'forget', 'pin'])

const disabled = computed(() => Boolean(props.busy))

/** Удалённые офферы — внизу, под всеми активными. Порядок данных (и пересчёт долей) не меняется:
 * после Bring Back оффер возвращается на своё место. */
const rows = computed(() => [
  ...props.offers.filter((o) => !o.removed),
  ...props.offers.filter((o) => o.removed),
])

const newOffer = ref(null)
const availableOptions = computed(() => {
  const listed = new Set(props.offers.map((o) => o.offer_id))
  return props.offerOptions.filter((o) => !listed.has(o.value))
})

function offerName(offerId) {
  return props.offersById[offerId]?.name ?? 'Неизвестный оффер'
}

/** «было N %» — только у незакреплённых: закреплённая доля при пересчётах не меняется */
function shareChanged(offer) {
  return !offer.pinned && offer.published_share !== null && offer.published_share !== offer.share
}

function add() {
  if (!newOffer.value) return
  emit('add', newOffer.value)
  newOffer.value = null
}
</script>

<template>
  <div>
    <div class="table-wrap">
      <table class="table offers">
        <thead>
          <tr>
            <th>Оффер</th>
            <th class="share-col">Доля</th>
            <th class="actions-col"><span class="sr-only">Действия</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in rows" :key="o.offer_id" :class="{ removed: o.removed }">
            <td>
              <div class="offer">
                <!-- «убрать насовсем» — слева, подальше от Bring Back, чтобы не промахнуться -->
                <button
                  v-if="o.removed"
                  type="button"
                  class="btn btn-ghost btn-sm btn-danger forget"
                  title="Убрать из списка насовсем"
                  :aria-label="`Убрать оффер #${o.offer_id} из списка`"
                  :disabled="disabled"
                  @click="emit('forget', o.offer_id)"
                >
                  ×
                </button>
                <span class="chip">#{{ o.offer_id }}</span>
                <span class="offer-name" :title="offerName(o.offer_id)">
                  {{ offerName(o.offer_id) }}
                </span>
                <span v-if="o.status === 'removed'" class="badge plain tone-slate">Removed</span>
                <span v-else-if="o.status === 'new'" class="badge plain tone-teal">New</span>
              </div>
            </td>
            <td class="share-col">
              <div class="share-cell">
                <span class="share-bar" aria-hidden="true">
                  <span :style="{ width: `${o.share}%` }" />
                </span>
                <span class="share mono">{{ o.share }}%</span>
                <button
                  type="button"
                  class="pin"
                  :class="{ pinned: o.pinned }"
                  :aria-pressed="o.pinned"
                  :disabled="disabled || o.removed"
                  :title="o.pinned ? 'Снять закрепление' : 'Закрепить долю'"
                  :aria-label="`${o.pinned ? 'Снять закрепление' : 'Закрепить долю'} #${o.offer_id}`"
                  @click="emit('pin', o.offer_id, !o.pinned)"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M9 3h6l-1 6 3 3v2H7v-2l3-3-1-6z" />
                    <path d="M12 14v7" />
                  </svg>
                </button>
              </div>
              <span v-if="shareChanged(o)" class="was faint">было {{ o.published_share }}%</span>
            </td>
            <td class="actions-col">
              <button
                v-if="o.removed"
                type="button"
                class="btn btn-sm"
                :disabled="disabled"
                @click="emit('restore', o.offer_id)"
              >
                Bring Back
              </button>
              <button
                v-else
                type="button"
                class="btn btn-ghost btn-sm btn-danger"
                :disabled="disabled"
                @click="emit('remove', o.offer_id)"
              >
                Remove
              </button>
            </td>
          </tr>
          <tr v-if="!offers.length">
            <td colspan="3" class="faint">Офферов пока нет — найдите оффер ниже и нажмите Add</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="stream-body">
      <div class="add-offer">
        <SearchSelect
          v-model="newOffer"
          :options="availableOptions"
          placeholder="Найти оффер по ID или названию…"
          :disabled="disabled || !availableOptions.length"
        />
        <button type="button" class="btn" :disabled="disabled || !newOffer" @click="add">
          <span v-if="busy === 'add'" class="spinner" /> Add
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
.offers td {
  padding-top: 8px;
  padding-bottom: 8px;
}
.offers tr.removed td {
  color: var(--text-3);
}
.offers tr.removed .offer-name {
  text-decoration: line-through;
}
.offers tr.removed .chip {
  opacity: 0.6;
}
.offer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
  min-width: 0;
}
.offer-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.offers th,
.offers td {
  padding-right: 12px;
  padding-left: 12px;
}
.share-col {
  width: 150px;
}
/* по содержимому: Remove или Bring Back + × */
.actions-col {
  width: 1%;
  white-space: nowrap;
  text-align: right;
}
.forget {
  width: 26px;
  height: 26px;
  margin-left: -6px;
  padding: 0;
  font-size: 18px;
  line-height: 1;
}
.share-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.share-bar {
  width: 48px;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--slate-soft);
}
.share-bar span {
  display: block;
  height: 100%;
  background: var(--teal);
  transition: width 0.2s;
}
.removed .share-bar span {
  background: var(--border-strong);
}
.share {
  width: 40px;
  color: var(--text-2);
  text-align: right;
}
.was {
  display: block;
  padding-left: 56px;
  font-size: 12px;
}
.pin {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
}
.pin svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.pin:hover:not(:disabled) {
  background: var(--slate-soft);
  color: var(--text);
}
.pin.pinned {
  border-color: color-mix(in srgb, var(--accent) 30%, transparent);
  background: var(--accent-soft);
  color: var(--accent);
}
.pin.pinned svg {
  fill: currentColor;
}
.pin:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.stream-body {
  padding: 14px 20px 16px;
  border-top: 1px solid var(--border);
}
.add-offer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  max-width: 520px;
}

@media (max-width: 640px) {
  .offers th,
  .offers td {
    padding-right: 8px;
    padding-left: 8px;
  }
  .offers th:first-child,
  .offers td:first-child {
    padding-left: 14px;
  }
  .offers th:last-child,
  .offers td:last-child {
    padding-right: 14px;
  }
  /* название оффера переносится на вторую строку, а не растягивает таблицу */
  .offer {
    flex-wrap: wrap;
    gap: 4px 6px;
  }
  .offer-name {
    flex-basis: 100%;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .share-bar {
    display: none;
  }
  .share-col,
  .actions-col {
    width: auto;
  }
  .share {
    width: auto;
  }
  .was {
    padding-left: 0;
  }
  .stream-body {
    padding: 12px 14px 14px;
  }
  .add-offer {
    max-width: none;
  }
}
</style>
