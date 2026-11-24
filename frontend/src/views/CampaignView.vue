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
import { useHealth } from '@/composables/useHealth'
import { useToast } from '@/composables/useToast'
import { flag, formatDateShort } from '@/utils/format'

const props = defineProps({ id: { type: Number, default: null } })
const isNew = computed(() => props.id == null)

const router = useRouter()
const toast = useToast()
const { dict, load, loading: dictLoading, error: dictError, offersById } = useDictionaries()
const { health } = useHealth()
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
// только при создании (по ТЗ): гео и оффер — из них сразу строятся два потока
const streamsForm = reactive({ country_codes: [], offer_id: null })
const formValid = computed(
  () =>
    form.name.trim() &&
    FIELDS.every((key) => form[key]) &&
    (!isNew.value || (streamsForm.country_codes.length && streamsForm.offer_id)),
)

const toOptions = (list) => list.map((i) => ({ value: i.id, label: i.name, hint: `#${i.id}` }))
const domainOptions = computed(() => toOptions(dict.domains))
const groupOptions = computed(() => toOptions(dict.groups))
const sourceOptions = computed(() => toOptions(dict.trafficSources))

async function submit() {
  if (!formValid.value || saving.value) return
  saving.value = true
  formError.value = null
  const base = { ...form, name: form.name.trim() }
  const data = isNew.value ? { ...base, ...streamsForm } : base
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

/** Кампания в админке Keitaro: <KEITARO_URL>/admin/#!/campaign/<id>/main */
const keitaroUrl = computed(() => {
  const base = health.value?.keitaro_url
  return base && campaign.value
    ? `${base.replace(/\/+$/, '')}/admin/#!/campaign/${campaign.value.id}/main`
    : null
})

// --- потоки -----------------------------------------------------------------

const countryOptions = computed(() =>
  dict.countries.map((c) => ({ value: c.code, label: c.name, hint: c.code, icon: flag(c.code) })),
)
const offerOptions = computed(() =>
  dict.offers.map((o) => ({ value: o.id, label: o.name, hint: `#${o.id}` })),
)

/** Схема новой кампании: какие два потока будут созданы из формы */
const previewStreams = computed(() => [
  {
    id: -1,
    name: 'Flow 1',
    kind: 'intercept',
    type: 'forced',
    position: 1,
    countries: streamsForm.country_codes,
    redirect_url: health.value?.google_redirect_url ?? 'https://www.google.com',
    offers: [],
  },
  {
    id: -2,
    name: 'Flow 2',
    kind: 'regular',
    type: 'regular',
    position: 2,
    countries: [],
    redirect_url: '',
    offers: streamsForm.offer_id
      ? [{ offer_id: streamsForm.offer_id, share: 100, removed: false }]
      : [],
  },
])

const streams = computed(() => campaign.value?.streams ?? [])
/** В списке сначала потоки с офферами — их и правят; перехватывающие и прочие — внизу */
const listedStreams = computed(() => [
  ...streams.value.filter((s) => s.kind === 'regular'),
  ...streams.value.filter((s) => s.kind !== 'regular'),
])

/** { streamId, action } — что сейчас выполняется; остальные действия потока заблокированы */
const busy = ref(null)

const ACTIONS = {
  patch: (id, patch) => api.updateStream(id, patch),
  add: (id, offerId) => api.addStreamOffer(id, offerId),
  remove: (id, offerId) => api.removeStreamOffer(id, offerId),
  restore: (id, offerId) => api.restoreStreamOffer(id, offerId),
  forget: (id, offerId) => api.forgetStreamOffer(id, offerId),
  pin: (id, offerId, pinned) => api.pinStreamOffer(id, offerId, pinned),
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
  } catch (e) {
    toast.error(e.message)
  } finally {
    busy.value = null
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

// --- Push to KT: все черновики кампании одной пачкой ----------------------------

const drafts = computed(() => streams.value.filter((s) => s.has_draft))
/** потоки, из-за которых публикация недоступна: проблема в черновике или правки в Keitaro */
const blockers = computed(() => drafts.value.filter((s) => !s.can_push))
const pushing = ref(false)

async function pushAll() {
  pushing.value = true
  try {
    const result = await api.pushCampaign(props.id)
    setStreams(result.streams)
    if (result.failed_stream_id) {
      const failed = result.streams.find((s) => s.id === result.failed_stream_id)
      toast.error(
        `Опубликовано потоков: ${result.published}. «${failed?.name}» — Keitaro ответил: ` +
          `${result.error}. Он и следующие остались черновиками.`,
      )
    } else {
      toast.success(`Опубликовано в Keitaro потоков: ${result.published}`)
    }
  } catch (e) {
    toast.error(e.message)
    // поток изменили в Keitaro — показываем актуальное состояние и что мешает публикации
    if (e.status === 409) refresh()
  } finally {
    pushing.value = false
  }
}

const busyFor = (stream) =>
  pushing.value ? 'push' : busy.value?.streamId === stream.id ? busy.value.action : null
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
        <template v-if="!isNew" #title-extra>
          <span class="created faint" title="Создана">{{ formatDateShort(campaign.created_at) }}</span>
        </template>
        <template v-if="!isNew" #subtitle>
          <span class="row wrap">
            <StateBadge :state="campaign.state" />
            <span class="chip">#{{ campaign.id }}</span>
            <span class="chip">alias: {{ campaign.alias }}</span>
            <a
              v-if="keitaroUrl"
              :href="keitaroUrl"
              target="_blank"
              rel="noreferrer"
              class="kt-link"
              title="Открыть кампанию в Keitaro"
              aria-label="Открыть кампанию в Keitaro"
            >
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M11 4h5v5M16 4l-7 7M14 11.5V15a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h3.5" />
              </svg>
            </a>
          </span>
        </template>
        <template v-if="!isNew" #actions>
          <button class="btn btn-soft btn-sm" :disabled="loading || !!busy" @click="refresh">
            <RefreshIcon :spinning="loading" /> Обновить
          </button>
          <button
            class="btn btn-soft-danger btn-sm"
            :disabled="!!busy"
            @click="removal.ask(campaign)"
          >
            <svg class="icon" viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10M9 9v4M11 9v4" />
            </svg>
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

            <template v-if="isNew">
              <div class="divider" />

              <div class="field">
                <label class="field-label" for="campaign-geo">Гео</label>
                <SearchSelect
                  id="campaign-geo"
                  v-model="streamsForm.country_codes"
                  multiple
                  :options="countryOptions"
                  :loading="dictLoading"
                  placeholder="Выберите одну или несколько стран"
                />
                <span class="field-hint">Flow 1: трафик из этих стран уйдёт на Google</span>
              </div>

              <div class="field">
                <label class="field-label" for="campaign-offer">Оффер</label>
                <SearchSelect
                  id="campaign-offer"
                  v-model="streamsForm.offer_id"
                  :options="offerOptions"
                  :loading="dictLoading"
                  placeholder="Найдите оффер по ID или названию"
                />
                <span class="field-hint">Flow 2: весь остальной трафик уйдёт на этот оффер</span>
              </div>
            </template>

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

        <section class="card main-col streams-card" :class="{ 'has-changes': drafts.length }">
          <div class="card-header streams-header">
            <h2>Потоки</h2>
            <span v-if="!isNew && streams.length" class="faint">{{ streams.length }}</span>

            <!-- изменения показываются на уровне всего раздела и публикуются одной пачкой -->
            <div v-if="drafts.length" class="publish">
              <span v-if="blockers.length" class="publish-status blocked">
                Исправьте
                <button
                  v-for="s in blockers"
                  :key="s.id"
                  type="button"
                  class="link-btn"
                  @click="showStream(s.id)"
                >
                  «{{ s.name || 'Без названия' }}»
                </button>
              </span>
              <span v-else class="publish-status">
                <span class="dot" aria-hidden="true" />
                Не опубликовано: {{ drafts.length }}
              </span>
              <button
                type="button"
                class="btn btn-primary btn-sm"
                :disabled="pushing || !!busy || blockers.length > 0"
                @click="pushAll"
              >
                <span v-if="pushing" class="spinner" /> Push to KT
              </button>
            </div>
          </div>

          <div class="card-body streams-body">
            <p v-if="isNew" class="placeholder muted">
              Вместе с кампанией в Keitaro будут созданы два потока: Flow 1 — перехватывающий
              (выбранные страны → Google) и Flow 2 — обычный (весь остальной трафик → оффер). После
              создания их можно менять здесь.
            </p>

            <div v-else class="streams">
                <StreamCard
                  v-for="stream in listedStreams"
                  :id="`stream-${stream.id}`"
                  :key="stream.id"
                  :stream="stream"
                  :busy="busyFor(stream)"
                  @patch="(patch) => act(stream, 'patch', patch)"
                  @cancel="act(stream, 'cancel')"
                  @delete="streamToDelete = stream"
                >
                  <!-- содержимое — только у потоков с офферами; остальные показываются заголовком -->
                  <OfferTable
                    v-if="stream.kind === 'regular'"
                    :offers="stream.offers"
                    :offers-by-id="offersById"
                    :offer-options="offerOptions"
                    :busy="busyFor(stream)"
                    @add="(offerId) => act(stream, 'add', offerId)"
                    @remove="(offerId) => act(stream, 'remove', offerId)"
                    @restore="(offerId) => act(stream, 'restore', offerId)"
                    @forget="(offerId) => act(stream, 'forget', offerId)"
                    @pin="(offerId, pinned) => act(stream, 'pin', offerId, pinned)"
                  />
                </StreamCard>

              <p v-if="!streams.length" class="placeholder muted">У кампании пока нет потоков.</p>
            </div>
          </div>
        </section>

        <aside class="overview-col">
          <section class="card overview">
            <div class="card-header"><h2>Схема</h2></div>
            <div class="card-body">
              <StreamsOverview
                :campaign-name="isNew ? form.name.trim() : campaign.name"
                :streams="isNew ? previewStreams : streams"
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
.created {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.kt-link {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--accent);
}
.kt-link:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.kt-link svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.mb {
  margin-bottom: 16px;
}
h2 {
  font-size: 15px;
}
/*
 * Три колонки: параметры | потоки | схема. Уже 1600px схема уходит под параметры (иначе таблице
 * офферов в середине не хватает ширины), уже 1080px — всё в одну колонку.
 */
.page-grid {
  display: grid;
  /* потокам — больше места, чем схеме, но не всё: карточкам хватает ~550–900px */
  grid-template-columns: minmax(300px, 380px) minmax(540px, 1.4fr) minmax(300px, 1fr);
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
.divider {
  height: 1px;
  background: var(--border);
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
.streams {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.streams-card .card-header {
  justify-content: flex-start;
}
.streams-body {
  padding: 14px;
  border-radius: 0 0 var(--radius) var(--radius);
  background: var(--surface-2);
}
.streams :deep(.flash) {
  animation: flash 1.2s ease-out;
}
@keyframes flash {
  from {
    box-shadow: 0 0 0 3px var(--accent);
  }
}
.placeholder {
  margin: 0;
  padding: 18px 8px;
  text-align: center;
}
/* неопубликованные изменения — рамкой всего раздела, а не каждой карточкой */
.streams-card {
  transition: border-color 0.15s, box-shadow 0.15s;
}
.streams-card.has-changes {
  border-color: var(--amber);
  box-shadow:
    0 0 0 1px var(--amber),
    var(--shadow);
}
.streams-header {
  flex-wrap: wrap;
  gap: 8px 12px;
}
.publish {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px 12px;
  margin-left: auto;
}
.publish-status {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 6px;
  color: var(--amber);
  font-size: 13px;
  font-weight: 600;
}
.publish-status.blocked {
  color: var(--red);
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}
.link-btn {
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}
@media (max-width: 1599px) {
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
    grid-template-areas: 'params' 'streams';
  }
  /* в одну колонку схема не помещается рядом с потоками и только удлиняет страницу */
  .overview-col {
    display: none;
  }
}
</style>
