<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/api'
import AlertBox from '@/components/AlertBox.vue'
import OfferStreamCard from '@/components/OfferStreamCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useAsync } from '@/composables/useAsync'
import { useDictionaries } from '@/composables/useDictionaries'
import { useToast } from '@/composables/useToast'
import { flag, formatDate } from '@/utils/format'

const props = defineProps({ id: { type: Number, required: true } })

const toast = useToast()
const { dict, load, domainsById, groupsById, sourcesById, offersById, countriesByCode } =
  useDictionaries()
load().catch(() => {})

// каждое открытие и «Обновить» подтягивают изменения, сделанные напрямую в Keitaro
const { data: campaign, error, loading, run } = useAsync(() => api.getCampaign(props.id))
const refresh = () => run().catch(() => {})
refresh()

/** { streamId, action } — что сейчас выполняется; остальные действия потока заблокированы */
const busy = ref(null)

const offerOptions = computed(() =>
  dict.offers.map((o) => ({ value: o.id, label: o.name, hint: `#${o.id}` })),
)

const domain = computed(() => domainsById.value[campaign.value?.domain_id])
const campaignUrl = computed(() =>
  domain.value && campaign.value ? `https://${domain.value.name}/${campaign.value.alias}` : null,
)
const draftCount = computed(
  () => campaign.value?.streams.filter((s) => s.editor?.has_draft).length ?? 0,
)

const ACTIONS = {
  add: (streamId, offerId) => api.addStreamOffer(streamId, offerId),
  remove: (streamId, offerId) => api.removeStreamOffer(streamId, offerId),
  restore: (streamId, offerId) => api.restoreStreamOffer(streamId, offerId),
  pin: (streamId, offerId, pinned) => api.pinStreamOffer(streamId, offerId, pinned),
  push: (streamId) => api.pushStream(streamId),
  cancel: (streamId) => api.cancelStreamDraft(streamId),
}

function replaceEditor(streamId, editor) {
  campaign.value = {
    ...campaign.value,
    streams: campaign.value.streams.map((s) => (s.id === streamId ? { ...s, editor } : s)),
  }
}

async function act(stream, action, ...args) {
  busy.value = { streamId: stream.id, action }
  try {
    replaceEditor(stream.id, await ACTIONS[action](stream.id, ...args))
    if (action === 'push') toast.success(`«${stream.name || stream.id}»: опубликовано в Keitaro`)
  } catch (e) {
    toast.error(e.message)
    // поток изменили в Keitaro — показываем актуальное состояние и блокировку публикации
    if (action === 'push' && e.status === 409) refresh()
  } finally {
    busy.value = null
  }
}
</script>

<template>
  <section>
    <div v-if="loading && !campaign" class="loading">
      <div class="skeleton" style="width: 40%; height: 28px" />
      <div class="skeleton" style="width: 25%" />
    </div>

    <template v-else-if="error">
      <PageHeader :title="`Кампания #${id}`" />
      <AlertBox :title="error.status === 404 ? 'Кампания не найдена' : 'Ошибка загрузки'">
        {{ error.message }}
      </AlertBox>
      <p><RouterLink :to="{ name: 'campaigns' }">← К списку кампаний</RouterLink></p>
    </template>

    <template v-else-if="campaign">
      <PageHeader :title="campaign.name">
        <template #eyebrow>
          <RouterLink :to="{ name: 'campaigns' }" class="back">← Кампании</RouterLink>
        </template>
        <template #subtitle>
          <span class="row wrap">
            <StateBadge :state="campaign.state" />
            <span class="chip">#{{ campaign.id }}</span>
            <span class="chip">alias: {{ campaign.alias }}</span>
            <a v-if="campaignUrl" :href="campaignUrl" target="_blank" rel="noreferrer" class="mono">
              {{ campaignUrl }}
            </a>
          </span>
        </template>
        <template #actions>
          <span v-if="draftCount" class="badge tone-amber">
            Не опубликовано потоков: {{ draftCount }}
          </span>
          <button class="btn btn-ghost btn-sm" :disabled="loading || !!busy" @click="refresh">
            <span v-if="loading" class="spinner" /> Обновить
          </button>
        </template>
      </PageHeader>

      <div class="layout">
        <div class="streams">
          <template v-for="stream in campaign.streams" :key="stream.id">
            <OfferStreamCard
              v-if="stream.editor"
              :stream="stream"
              :offers-by-id="offersById"
              :offer-options="offerOptions"
              :busy="busy?.streamId === stream.id ? busy.action : null"
              @add="(offerId) => act(stream, 'add', offerId)"
              @remove="(offerId) => act(stream, 'remove', offerId)"
              @restore="(offerId) => act(stream, 'restore', offerId)"
              @pin="(offerId, pinned) => act(stream, 'pin', offerId, pinned)"
              @push="act(stream, 'push')"
              @cancel="act(stream, 'cancel')"
            />
            <!-- потоки без офферов редактор не разбирает и не меняет -->
            <article v-else class="card plain-stream">
              <span class="position mono">{{ stream.position ?? '—' }}</span>
              <h3>{{ stream.name || `Поток #${stream.id}` }}</h3>
              <span class="faint">не редактируется</span>
            </article>
          </template>
          <p v-if="!campaign.streams.length" class="muted">У кампании нет потоков.</p>
        </div>

        <aside class="card info">
          <div class="card-header"><h2>Настройки</h2></div>
          <dl class="card-body">
            <dt>Гео</dt>
            <dd>
              <ul v-if="campaign.country_codes.length" class="geo-list">
                <li v-for="code in campaign.country_codes" :key="code">
                  {{ flag(code) }} {{ countriesByCode[code]?.name ?? code }}
                </li>
              </ul>
              <span v-else class="faint">— (кампания создана напрямую в Keitaro)</span>
            </dd>
            <dt>Домен</dt>
            <dd>{{ domain?.name ?? '—' }}</dd>
            <dt>Группа</dt>
            <dd>{{ groupsById[campaign.group_id]?.name ?? campaign.group_id ?? '—' }}</dd>
            <dt>Источник</dt>
            <dd>
              {{
                sourcesById[campaign.traffic_source_id]?.name ?? campaign.traffic_source_id ?? '—'
              }}
            </dd>
            <dt>Создана</dt>
            <dd>{{ formatDate(campaign.created_at) }}</dd>
          </dl>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.loading {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.back {
  color: var(--text-3);
  font-size: 13px;
}
.wrap {
  flex-wrap: wrap;
  gap: 8px;
}
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  align-items: start;
  gap: 20px;
}
.streams {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
h2,
h3 {
  font-size: 15px;
}
.plain-stream {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 20px;
  border-left: 3px solid var(--border-strong);
}
.plain-stream h3 {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
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
dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px 14px;
  margin: 0;
}
dt {
  color: var(--text-3);
}
dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.geo-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

@media (max-width: 1080px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
