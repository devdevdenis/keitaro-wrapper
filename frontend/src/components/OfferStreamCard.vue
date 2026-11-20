<script setup>
/**
 * Поток с офферами в редакторе: таблица «оффер — доля — действия».
 * Все правки копятся в черновике на бэкенде; в Keitaro они уходят по Push to KT.
 */
import { computed, ref } from 'vue'
import AlertBox from '@/components/AlertBox.vue'
import SearchSelect from '@/components/SearchSelect.vue'
import { STREAM_TYPES } from '@/utils/format'

const props = defineProps({
  stream: { type: Object, required: true }, // { id, name, type, position, state, editor }
  offersById: { type: Object, default: () => ({}) },
  offerOptions: { type: Array, default: () => [] },
  busy: { type: String, default: null }, // действие, которое сейчас выполняется
})
const emit = defineEmits(['add', 'remove', 'restore', 'pin', 'push', 'cancel'])

const editor = computed(() => props.stream.editor)
const typeMeta = computed(
  () => STREAM_TYPES[props.stream.type] ?? { label: props.stream.type, tone: 'slate' },
)
const disabled = computed(() => Boolean(props.busy))

const newOffer = ref(null)
const availableOptions = computed(() => {
  const listed = new Set(editor.value.offers.map((o) => o.offer_id))
  return props.offerOptions.filter((o) => !listed.has(o.value))
})

function offerName(offerId) {
  return props.offersById[offerId]?.name ?? 'Неизвестный оффер'
}

function shareChanged(offer) {
  return offer.published_share !== null && offer.published_share !== offer.share
}

function add() {
  if (!newOffer.value) return
  emit('add', newOffer.value)
  newOffer.value = null
}
</script>

<template>
  <article
    class="card stream"
    :class="{ dirty: editor.has_draft, conflict: editor.conflict }"
    :aria-label="stream.name || `Поток #${stream.id}`"
  >
    <header class="stream-head">
      <span class="position mono">{{ stream.position ?? '—' }}</span>
      <div class="titles">
        <h3>{{ stream.name || `Поток #${stream.id}` }}</h3>
        <div class="row meta">
          <span class="badge" :class="`tone-${typeMeta.tone}`">{{ typeMeta.label }}</span>
          <span class="chip">id: {{ stream.id }}</span>
          <span v-if="stream.state && stream.state !== 'active'" class="badge tone-slate">
            {{ stream.state }}
          </span>
        </div>
      </div>
      <span v-if="editor.has_draft" class="badge tone-amber draft-badge">Не опубликовано</span>
    </header>

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
          <tr v-for="o in editor.offers" :key="o.offer_id" :class="{ removed: o.removed }">
            <td>
              <div class="offer">
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
          <tr v-if="!editor.offers.length">
            <td colspan="3" class="faint">Офферов нет</td>
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

      <AlertBox v-if="editor.problem" :tone="editor.conflict ? 'red' : 'amber'">
        {{ editor.problem }}
      </AlertBox>
    </div>

    <footer v-if="editor.has_draft" class="stream-footer">
      <div class="footer-actions">
        <button type="button" class="btn btn-ghost" :disabled="disabled" @click="emit('cancel')">
          <span v-if="busy === 'cancel'" class="spinner" /> Cancel
        </button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="disabled || !editor.can_push"
          @click="emit('push')"
        >
          <span v-if="busy === 'push'" class="spinner" /> Push to KT
        </button>
      </div>
    </footer>
  </article>
</template>

<style scoped>
.stream {
  overflow: hidden;
  border-left: 3px solid var(--teal);
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
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
  align-items: flex-start;
  gap: 14px;
  padding: 16px 20px;
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
}
.meta {
  flex-wrap: wrap;
  gap: 6px;
}
.draft-badge {
  flex-shrink: 0;
}

.table-wrap {
  overflow-x: auto;
  border-top: 1px solid var(--border);
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
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.offer-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.share-col {
  width: 210px;
}
.actions-col {
  width: 120px;
  text-align: right;
}
.share-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.share-bar {
  width: 80px;
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
  padding-left: 88px;
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
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 20px 18px;
  border-top: 1px solid var(--border);
}
.add-offer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  max-width: 520px;
}
.stream-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  background: var(--amber-soft);
  font-size: 13px;
}
.footer-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.conflict .stream-footer {
  background: var(--red-soft);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

@media (max-width: 640px) {
  .share-bar {
    display: none;
  }
  .share-col {
    width: auto;
  }
  .was {
    padding-left: 0;
  }
}
</style>
