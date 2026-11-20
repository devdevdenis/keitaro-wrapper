<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/api'
import AlertBox from '@/components/AlertBox.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBadge from '@/components/StateBadge.vue'
import StreamCard from '@/components/StreamCard.vue'
import { useAsync } from '@/composables/useAsync'
import { useDictionaries } from '@/composables/useDictionaries'
import { useToast } from '@/composables/useToast'
import { flag, formatDate } from '@/utils/format'

const props = defineProps({ id: { type: Number, required: true } })

const toast = useToast()
const { dict, load, domainsById, groupsById, sourcesById, offersById, countriesByCode } =
  useDictionaries()
load().catch(() => {})

const { data: campaign, error, loading, run } = useAsync(() => api.getCampaign(props.id))
run().catch(() => {})

const busyStream = ref(null)

const offerOptions = computed(() =>
  dict.offers.map((o) => ({ value: o.id, label: o.name, hint: `#${o.id}` })),
)

const domain = computed(() => domainsById.value[campaign.value?.domain_id])
const campaignUrl = computed(() =>
  domain.value && campaign.value ? `https://${domain.value.name}/${campaign.value.alias}` : null,
)

function replaceStream(updated) {
  campaign.value = {
    ...campaign.value,
    streams: campaign.value.streams.map((s) => (s.id === updated.id ? updated : s)),
  }
}

async function mutateOffers(streamId, action, offerId) {
  busyStream.value = streamId
  try {
    const updated =
      action === 'add'
        ? await api.addStreamOffer(streamId, offerId)
        : await api.removeStreamOffer(streamId, offerId)
    replaceStream(updated)
    toast.success(action === 'add' ? `Оффер #${offerId} добавлен` : `Оффер #${offerId} удалён`)
  } catch (e) {
    toast.error(e.message)
  } finally {
    busyStream.value = null
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
          <button class="btn btn-ghost btn-sm" :disabled="loading" @click="run().catch(() => {})">
            <span v-if="loading" class="spinner" /> Обновить
          </button>
        </template>
      </PageHeader>

      <div class="layout">
        <div class="streams">
          <AlertBox tone="slate" title="Редактор — шаблон">
            Сейчас умеет добавлять и удалять офферы в потоках со схемой «landings»; доли
            распределяются поровну. Конкретные правила будут добавлены позже.
          </AlertBox>

          <StreamCard
            v-for="stream in campaign.streams"
            :key="stream.id"
            :stream="stream"
            :offers-by-id="offersById"
            :offer-options="offerOptions"
            :busy="busyStream === stream.id"
            @add-offer="(offerId) => mutateOffers(stream.id, 'add', offerId)"
            @remove-offer="(offerId) => mutateOffers(stream.id, 'remove', offerId)"
          />
          <p v-if="!campaign.streams.length" class="muted">У кампании нет потоков.</p>
        </div>

        <aside class="card info">
          <div class="card-header"><h2>Настройки</h2></div>
          <dl class="card-body">
            <dt>Гео</dt>
            <dd>
              <template v-if="campaign.country_code">
                {{ flag(campaign.country_code) }}
                {{ countriesByCode[campaign.country_code]?.name ?? campaign.country_code }}
              </template>
              <span v-else class="faint">— (создана не через обёртку)</span>
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
h2 {
  font-size: 15px;
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

@media (max-width: 1080px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
