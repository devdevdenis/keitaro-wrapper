<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import AlertBox from '@/components/AlertBox.vue'
import FlowPreview from '@/components/FlowPreview.vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchSelect from '@/components/SearchSelect.vue'
import { useDictionaries } from '@/composables/useDictionaries'
import { useHealth } from '@/composables/useHealth'
import { useToast } from '@/composables/useToast'
import { flag } from '@/utils/format'

const router = useRouter()
const toast = useToast()
const { health } = useHealth()
const {
  dict,
  load,
  loading: dictLoading,
  error: dictError,
  countriesByCode,
  offersById,
} = useDictionaries()
load().catch(() => {})

const prefix = computed(() => health.value?.campaign_name_prefix ?? 'test_volper_')

const form = reactive({
  name: '',
  country_codes: [],
  offer_id: null,
  domain_id: null,
  group_id: null,
  traffic_source_id: null,
})
const submitting = ref(false)
const submitError = ref(null)

/** Пользователь вводит только суффикс; если вставил с префиксом — не дублируем */
const suffix = computed(() => {
  const value = form.name.trim()
  return value.startsWith(prefix.value) ? value.slice(prefix.value.length) : value
})
const fullName = computed(() => (suffix.value ? `${prefix.value}${suffix.value}` : ''))

const countryOptions = computed(() =>
  dict.countries.map((c) => ({ value: c.code, label: c.name, hint: c.code, prefix: flag(c.code) })),
)
const offerOptions = computed(() =>
  dict.offers.map((o) => ({
    value: o.id,
    label: o.name,
    hint: `#${o.id}${o.country?.length ? ' · ' + o.country.join(', ') : ''}`,
  })),
)
const toOptions = (list) => list.map((i) => ({ value: i.id, label: i.name, hint: `#${i.id}` }))
const domainOptions = computed(() => toOptions(dict.domains))
const groupOptions = computed(() => toOptions(dict.groups))
const sourceOptions = computed(() => toOptions(dict.trafficSources))

const canSubmit = computed(
  () =>
    suffix.value &&
    form.country_codes.length &&
    form.offer_id &&
    form.domain_id &&
    form.group_id &&
    form.traffic_source_id &&
    !submitting.value,
)

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  submitError.value = null
  try {
    const result = await api.createCampaign({ ...form, name: suffix.value })
    toast.success(`Кампания ${result.record.name} создана`)
    router.push({ name: 'campaign-edit', params: { id: result.record.keitaro_id } })
  } catch (e) {
    submitError.value = e
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section>
    <PageHeader
      title="Новая кампания"
      subtitle="Кампания создаётся в Keitaro сразу с двумя потоками"
    />

    <AlertBox v-if="dictError" title="Справочники Keitaro не загрузились" class="mb">
      {{ dictError.message }}
    </AlertBox>

    <div class="grid">
      <form class="card" @submit.prevent="submit">
        <div class="card-header"><h2>Параметры</h2></div>
        <div class="card-body fields">
          <label class="field span-2" for="name">
            <span class="field-label">Название</span>
            <div class="input name-input">
              <span class="name-prefix mono">{{ prefix }}</span>
              <input
                id="name"
                v-model="form.name"
                placeholder="campaign1"
                autocomplete="off"
                maxlength="100"
              />
            </div>
            <span class="field-hint">
              Префикс добавляется автоматически. Итог:
              <code>{{ fullName || `${prefix}…` }}</code>
            </span>
          </label>

          <div class="field">
            <label class="field-label" for="country">Гео (страны)</label>
            <SearchSelect
              id="country"
              v-model="form.country_codes"
              multiple
              :options="countryOptions"
              :loading="dictLoading"
              placeholder="Выберите одну или несколько стран"
            />
            <span class="field-hint">Трафик из выбранных стран уйдёт на Google</span>
          </div>

          <div class="field">
            <label class="field-label" for="offer">Оффер</label>
            <SearchSelect
              id="offer"
              v-model="form.offer_id"
              :options="offerOptions"
              :loading="dictLoading"
              placeholder="Выберите оффер"
            />
            <span class="field-hint">Весь остальной трафик</span>
          </div>

          <div class="divider span-2" />

          <div class="field">
            <label class="field-label" for="domain">Домен</label>
            <SearchSelect
              id="domain"
              v-model="form.domain_id"
              :options="domainOptions"
              :loading="dictLoading"
              placeholder="Выберите домен"
            />
          </div>

          <div class="field">
            <label class="field-label" for="group">Группа</label>
            <SearchSelect
              id="group"
              v-model="form.group_id"
              :options="groupOptions"
              :loading="dictLoading"
              placeholder="Выберите группу"
            />
          </div>

          <div class="field">
            <label class="field-label" for="source">Источник трафика</label>
            <SearchSelect
              id="source"
              v-model="form.traffic_source_id"
              :options="sourceOptions"
              :loading="dictLoading"
              placeholder="Выберите источник"
            />
          </div>

          <AlertBox v-if="submitError" title="Кампания не создана" class="span-2">
            {{ submitError.message }}
          </AlertBox>
        </div>

        <div class="card-footer">
          <button type="button" class="btn btn-ghost" @click="router.back()">Отмена</button>
          <button type="submit" class="btn btn-primary" :disabled="!canSubmit">
            <span v-if="submitting" class="spinner" />
            Создать кампанию
          </button>
        </div>
      </form>

      <aside class="card preview">
        <div class="card-header"><h2>Схема</h2></div>
        <div class="card-body">
          <FlowPreview
            :name="fullName"
            :countries="form.country_codes.map((code) => countriesByCode[code] ?? { code })"
            :offer="offersById[form.offer_id] ?? null"
            :google-url="health?.google_redirect_url"
          />
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.mb {
  margin-bottom: 16px;
}
.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(280px, 1fr);
  align-items: start;
  gap: 20px;
}
h2 {
  font-size: 15px;
}
.fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 16px;
}
.span-2 {
  grid-column: span 2;
}
.divider {
  height: 1px;
  background: var(--border);
}
.name-input {
  display: flex;
  align-items: center;
  padding: 0;
  overflow: hidden;
}
.name-prefix {
  display: flex;
  align-items: center;
  align-self: stretch;
  padding: 0 10px;
  border-right: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-2);
}
.name-input input {
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 0 10px;
  border: none;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-family: var(--mono);
  outline: none;
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
.preview {
  position: sticky;
  top: 24px;
}

@media (max-width: 1080px) {
  .grid {
    grid-template-columns: 1fr;
  }
  .preview {
    position: static;
  }
}
@media (max-width: 640px) {
  .fields {
    grid-template-columns: 1fr;
  }
  .span-2 {
    grid-column: auto;
  }
}
</style>
