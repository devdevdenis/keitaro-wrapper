<script setup>
/**
 * Кампания: параметры сверху, потоки снизу. id = null — создание новой кампании.
 * Параметры сохраняются сразу в Keitaro; правки потоков копятся в черновиках и уходят по Push to KT.
 */
import { computed, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api } from '@/api'
import AlertBox from '@/components/AlertBox.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import InterceptFields from '@/components/InterceptFields.vue'
import OfferTable from '@/components/OfferTable.vue'
import PageHeader from '@/components/PageHeader.vue'
import RefreshIcon from '@/components/RefreshIcon.vue'
import SearchSelect from '@/components/SearchSelect.vue'
import StateBadge from '@/components/StateBadge.vue'
import StreamCard from '@/components/StreamCard.vue'
import StreamsOverview from '@/components/StreamsOverview.vue'
import { useAsync } from '@/composables/useAsync'
import { useDeleteCampaign } from '@/composables/useDeleteCampaign'
import { useDictionaries } from '@/composables/useDictionaries'
import { useToast } from '@/composables/useToast'
import { flag, formatDate } from '@/utils/format'

const props = defineProps({ id: { type: Number, default: null } })
const isNew = computed(() => props.id == null)

const router = useRouter()
const toast = useToast()
const { dict, load, loading: dictLoading, error: dictError, domainsById, offersById } =
  useDictionaries()
load().catch(() => {})

// каждое открытие и «Обновить» подтягивают изменения, сделанные напрямую в Keitaro
const { data: campaign, error, loading, run } = useAsync(() => api.getCampaign(props.id))
const refresh = () => run().catch(() => {})
if (!isNew.value) refresh()

const removal = useDeleteCampaign(() => router.push({ name: 'campaigns' }))

// --- параметры кампании -------------------------------------------------------

const FIELDS = ['name', 'domain_id', 'group_id', 'traffic_source_id']
const form = reactive({ name: '', domain_id: null, group_id: null, traffic_source_id: null })
const saving = ref(false)
const formError = ref(null)

function resetForm() {
  for (const key of FIELDS) form[key] = campaign.value?.[key] ?? (key === 'name' ? '' : null)
  formError.value = null
}
watch(campaign, (value, previous) => {
  // после «Обновить» не затираем то, что пользователь уже начал менять
  if (!previous || !formChanged(previous)) resetForm()
})

function formChanged(base = campaign.value) {
  return FIELDS.some((key) => (key === 'name' ? form.name.trim() : form[key]) !== base?.[key])
}
const dirty = computed(() => !isNew.value && campaign.value && formChanged())
const formValid = computed(() => form.name.trim() && FIELDS.every((key) => form[key]))

const toOptions = (list) => list.map((i) => ({ value: i.id, label: i.name, hint: `#${i.id}` }))
const domainOptions = computed(() => toOptions(dict.domains))
const groupOptions = computed(() => toOptions(dict.groups))
const sourceOptions = computed(() => toOptions(dict.trafficSources))

async function submit() {
  if (!formValid.value || saving.value) return
  saving.value = true
  formError.value = null
  const data = { ...form, name: form.name.trim() }
  try {
    if (isNew.value) {
      const created = await api.createCampaign(data)
      toast.success(`Кампания «${created.name}» создана`)
      router.replace({ name: 'campaign-edit', params: { id: created.id } })
    } else {
      const updated = await api.updateCampaign(props.id, data)
      campaign.value = { ...campaign.value, ...updated }
      resetForm()
      toast.success('Параметры кампании сохранены')
    }
  } catch (e) {
    formError.value = e
  } finally {
    saving.value = false
  }
}

const domain = computed(() => domainsById.value[campaign.value?.domain_id])
const campaignUrl = computed(() =>
  domain.value && campaign.value ? `https://${domain.value.name}/${campaign.value.alias}` : null,
)

// --- потоки -----------------------------------------------------------------

const countryOptions = computed(() =>
  dict.countries.map((c) => ({ value: c.code, label: c.name, hint: c.code, icon: flag(c.code) })),
)
const offerOptions = computed(() =>
  dict.offers.map((o) => ({ value: o.id, label: o.name, hint: `#${o.id}` })),
)

const streams = computed(() => campaign.value?.streams ?? [])
const draftCount = computed(() => streams.value.filter((s) => s.has_draft).length)

/** { streamId, action } — что сейчас выполняется; остальные действия потока заблокированы */
const busy = ref(null)
const adding = ref(null)

const ACTIONS = {
  patch: (id, patch) => api.updateStream(id, patch),
  add: (id, offerId) => api.addStreamOffer(id, offerId),
  remove: (id, offerId) => api.removeStreamOffer(id, offerId),
  restore: (id, offerId) => api.restoreStreamOffer(id, offerId),
  pin: (id, offerId, pinned) => api.pinStreamOffer(id, offerId, pinned),
  push: (id) => api.pushStream(id),
  cancel: (id) => api.cancelStreamDraft(id),
}

function setStreams(list) {
  campaign.value = { ...campaign.value, streams: list }
}

async function act(stream, action, ...args) {
  busy.value = { streamId: stream.id, action }
  try {
    const updated = await ACTIONS[action](stream.id, ...args)
    setStreams(streams.value.map((s) => (s.id === stream.id ? updated : s)))
    if (action === 'push') toast.success(`«${updated.name}»: опубликовано в Keitaro`)
  } catch (e) {
    toast.error(e.message)
    // поток изменили в Keitaro — показываем актуальное состояние и блокировку публикации
    if (action === 'push' && e.status === 409) refresh()
  } finally {
    busy.value = null
  }
}

async function addStream(kind) {
  adding.value = kind
  try {
    setStreams([...streams.value, await api.addStream(props.id, kind)])
  } catch (e) {
    toast.error(e.message)
  } finally {
    adding.value = null
  }
}

// удаление потока — с подтверждением; опубликованный удаляется и в Keitaro
const streamToDelete = ref(null)
const deletingStream = ref(false)
async function deleteStream() {
  const stream = streamToDelete.value
  deletingStream.value = true
  try {
    await api.deleteStream(stream.id)
    setStreams(streams.value.filter((s) => s.id !== stream.id))
    toast.success(`Поток «${stream.name}» удалён`)
    streamToDelete.value = null
  } catch (e) {
    toast.error(e.message)
  } finally {
    deletingStream.value = false
  }
}
/** Клик по потоку на схеме — прокрутка к его карточке с короткой подсветкой */
function showStream(id) {
  const card = document.getElementById(`stream-${id}`)
  if (!card) return
  card.scrollIntoView({ behavior: 'smooth', block: 'start' })
  card.classList.remove('flash')
  void card.offsetWidth // перезапуск анимации
  card.classList.add('flash')
}

const busyFor = (stream) => (busy.value?.streamId === stream.id ? busy.value.action : null)
</script>

<template>
  <section>
    <div v-if="!isNew && loading && !campaign" class="loading">
      <div class="skeleton" style="width: 40%; height: 28px" />
      <div class="skeleton" style="width: 25%" />
    </div>

    <template v-else-if="!isNew && error">
      <PageHeader :title="`Кампания #${id}`" />
      <AlertBox :title="error.status === 404 ? 'Кампания не найдена' : 'Ошибка загрузки'">
        {{ error.message }}
      </AlertBox>
      <p><RouterLink :to="{ name: 'campaigns' }">← К списку кампаний</RouterLink></p>
    </template>

    <template v-else>
      <PageHeader :title="isNew ? 'Новая кампания' : campaign.name">
        <template #eyebrow>
          <RouterLink :to="{ name: 'campaigns' }" class="back">← Кампании</RouterLink>
        </template>
        <template v-if="!isNew" #subtitle>
          <span class="row wrap">
            <StateBadge :state="campaign.state" />
            <span class="chip">#{{ campaign.id }}</span>
            <span class="chip">alias: {{ campaign.alias }}</span>
            <a v-if="campaignUrl" :href="campaignUrl" target="_blank" rel="noreferrer" class="mono">
              {{ campaignUrl }}
            </a>
            <span class="faint">создана {{ formatDate(campaign.created_at) }}</span>
          </span>
        </template>
        <template v-if="!isNew" #actions>
          <span v-if="draftCount" class="badge tone-amber">
            Не опубликовано потоков: {{ draftCount }}
          </span>
          <button class="btn btn-ghost btn-sm" :disabled="loading || !!busy" @click="refresh">
            <RefreshIcon :spinning="loading" /> Обновить
          </button>
          <button
            class="btn btn-ghost btn-sm btn-danger"
            :disabled="!!busy"
            @click="removal.ask(campaign)"
          >
            Удалить
          </button>
        </template>
      </PageHeader>

      <AlertBox v-if="dictError" title="Справочники Keitaro не загрузились" class="mb">
        {{ dictError.message }}
      </AlertBox>

      <div class="page-grid">
        <form class="card params" @submit.prevent="submit">
          <div class="card-header"><h2>Параметры</h2></div>
          <div class="card-body fields">
            <label class="field span-2" for="campaign-name">
              <span class="field-label">Название</span>
              <input
                id="campaign-name"
                v-model="form.name"
                class="input"
                placeholder="Например, Nutra DE — Facebook"
                autocomplete="off"
                maxlength="100"
              />
              <span class="field-hint">Так кампания называется в Keitaro</span>
            </label>

            <div class="field">
              <label class="field-label" for="campaign-domain">Домен</label>
              <SearchSelect
                id="campaign-domain"
                v-model="form.domain_id"
                :options="domainOptions"
                :loading="dictLoading"
                placeholder="Выберите домен"
              />
            </div>

            <div class="field">
              <label class="field-label" for="campaign-group">Группа</label>
              <SearchSelect
                id="campaign-group"
                v-model="form.group_id"
                :options="groupOptions"
                :loading="dictLoading"
                placeholder="Выберите группу"
              />
            </div>

            <div class="field">
              <label class="field-label" for="campaign-source">Источник трафика</label>
              <SearchSelect
                id="campaign-source"
                v-model="form.traffic_source_id"
                :options="sourceOptions"
                :loading="dictLoading"
                placeholder="Выберите источник"
              />
            </div>

            <AlertBox
              v-if="formError"
              :title="isNew ? 'Кампания не создана' : 'Не удалось сохранить'"
              class="span-2"
            >
              {{ formError.message }}
            </AlertBox>
          </div>

          <div v-if="isNew || dirty" class="card-footer">
            <button
              v-if="isNew"
              type="button"
              class="btn btn-ghost"
              @click="router.push({ name: 'campaigns' })"
            >
              Отмена
            </button>
            <button v-else type="button" class="btn btn-ghost" :disabled="saving" @click="resetForm">
              Сбросить
            </button>
            <button type="submit" class="btn btn-primary" :disabled="!formValid || saving">
              <span v-if="saving" class="spinner" />
              {{ isNew ? 'Создать кампанию' : 'Сохранить' }}
            </button>
          </div>
        </form>

        <div class="main-col">
          <div class="streams-head">
            <h2>Потоки</h2>
            <div v-if="!isNew" class="row">
              <button
                type="button"
                class="btn btn-sm"
                :disabled="!!adding"
                @click="addStream('intercept')"
              >
                <span v-if="adding === 'intercept'" class="spinner" /> + Перехватывающий
              </button>
              <button type="button" class="btn btn-sm" :disabled="!!adding" @click="addStream('regular')">
                <span v-if="adding === 'regular'" class="spinner" /> + Обычный
              </button>
            </div>
          </div>

          <div v-if="isNew" class="card placeholder">
            <p class="muted">Потоки станут доступны после создания кампании.</p>
          </div>

          <div v-else class="streams">
            <StreamCard
              v-for="stream in streams"
              :id="`stream-${stream.id}`"
              :key="stream.id"
              :stream="stream"
              :busy="busyFor(stream)"
              @patch="(patch) => act(stream, 'patch', patch)"
              @push="act(stream, 'push')"
              @cancel="act(stream, 'cancel')"
              @delete="streamToDelete = stream"
            >
              <InterceptFields
                v-if="stream.kind === 'intercept'"
                :stream="stream"
                :country-options="countryOptions"
                :busy="busyFor(stream)"
                @patch="(patch) => act(stream, 'patch', patch)"
              />
              <OfferTable
                v-else-if="stream.kind === 'regular'"
                :offers="stream.offers"
                :offers-by-id="offersById"
                :offer-options="offerOptions"
                :busy="busyFor(stream)"
                @add="(offerId) => act(stream, 'add', offerId)"
                @remove="(offerId) => act(stream, 'remove', offerId)"
                @restore="(offerId) => act(stream, 'restore', offerId)"
                @pin="(offerId, pinned) => act(stream, 'pin', offerId, pinned)"
              />
              <p v-else class="other muted">
                Этот поток редактор не разбирает — его настройки меняются в Keitaro.
              </p>
            </StreamCard>

            <div v-if="!streams.length" class="card placeholder">
              <p class="muted">У кампании нет потоков — добавьте перехватывающий или обычный поток.</p>
            </div>
          </div>
        </div>

        <aside class="overview-col">
          <section class="card overview">
            <div class="card-header"><h2>Схема</h2></div>
            <div class="card-body">
              <StreamsOverview
                :campaign-name="isNew ? form.name.trim() : campaign.name"
                :streams="streams"
                :offers-by-id="offersById"
                placeholder="Потоки появятся после создания кампании"
                @select="showStream"
              />
            </div>
          </section>
        </aside>
      </div>
    </template>

    <ConfirmDialog
      :open="!!streamToDelete"
      :title="`Удалить поток «${streamToDelete?.name ?? ''}»?`"
      confirm-label="Удалить"
      danger
      :busy="deletingStream"
      @confirm="deleteStream"
      @cancel="streamToDelete = null"
    >
      <template v-if="streamToDelete?.is_new">
        Поток ещё не опубликован — в Keitaro ничего не изменится.
      </template>
      <template v-else>
        Поток будет удалён в Keitaro, неопубликованные изменения потеряются. Восстановить его можно в
        Keitaro.
      </template>
    </ConfirmDialog>

    <ConfirmDialog
      :open="!!removal.target.value"
      :title="`Удалить кампанию «${removal.target.value?.name ?? ''}»?`"
      confirm-label="Удалить"
      danger
      :busy="removal.deleting.value"
      @confirm="removal.confirm"
      @cancel="removal.cancel"
    >
      Кампания будет перемещена в архив Keitaro и пропадёт из списка. Неопубликованные изменения
      потоков будут потеряны. Восстановить кампанию можно в Keitaro из архива.
    </ConfirmDialog>
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
.mb {
  margin-bottom: 16px;
}
h2 {
  font-size: 15px;
}
/*
 * Три колонки: параметры | потоки | схема. Уже 1500px схема уходит под параметры (иначе таблице
 * офферов в середине не хватает ширины), уже 1080px — всё в одну колонку.
 */
.page-grid {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(260px, 340px);
  grid-template-areas: 'params streams overview';
  align-items: start;
  gap: 20px;
}
.params {
  grid-area: params;
}
.main-col {
  grid-area: streams;
  min-width: 0;
}
/* колонка схемы тянется на всю высоту, чтобы схема «прилипала» при прокрутке потоков */
.overview-col {
  grid-area: overview;
  align-self: stretch;
}
.overview {
  position: sticky;
  top: 24px;
}
.fields {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}
.span-2 {
  grid-column: 1 / -1;
}
.card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: var(--surface-2);
  border-radius: 0 0 var(--radius) var(--radius);
}
.streams-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 30px;
  margin-bottom: 12px;
}
.streams-head h2 {
  font-size: 17px;
}
.streams :deep(.flash) {
  animation: flash 1.2s ease-out;
}
@keyframes flash {
  from {
    box-shadow: 0 0 0 3px var(--accent);
  }
}
.streams {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.placeholder {
  padding: 28px 20px;
  text-align: center;
}
.placeholder p,
.other {
  margin: 0;
}
.other {
  padding: 14px 20px 16px;
}

@media (max-width: 1499px) {
  .page-grid {
    grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
    grid-template-rows: auto 1fr;
    grid-template-areas:
      'params streams'
      'overview streams';
  }
}
@media (max-width: 1080px) {
  .page-grid {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: none;
    grid-template-areas: 'params' 'overview' 'streams';
  }
  .overview {
    position: static;
  }
}
</style>
