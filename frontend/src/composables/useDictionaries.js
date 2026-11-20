import { computed, reactive, ref } from 'vue'
import { api } from '@/api'

// Кеш на уровне модуля: справочники грузятся один раз на сессию вкладки
const state = reactive({
  countries: [],
  domains: [],
  groups: [],
  trafficSources: [],
  offers: [],
})
const loading = ref(false)
const error = ref(null)
let pending = null

const LOADERS = {
  countries: api.countries,
  domains: api.domains,
  groups: api.groups,
  trafficSources: api.trafficSources,
  offers: api.offers,
}

const byId = (list, key = 'id') => Object.fromEntries(list.map((item) => [item[key], item]))

export function useDictionaries() {
  async function load({ force = false } = {}) {
    if (pending && !force) return pending
    loading.value = true
    error.value = null
    pending = Promise.all(
      Object.entries(LOADERS).map(async ([key, loader]) => {
        state[key] = await loader()
      }),
    )
      .catch((e) => {
        error.value = e
        pending = null
        throw e
      })
      .finally(() => {
        loading.value = false
      })
    return pending
  }

  return {
    dict: state,
    loading,
    error,
    load,
    countriesByCode: computed(() => byId(state.countries, 'code')),
    domainsById: computed(() => byId(state.domains)),
    groupsById: computed(() => byId(state.groups)),
    sourcesById: computed(() => byId(state.trafficSources)),
    offersById: computed(() => byId(state.offers)),
  }
}
