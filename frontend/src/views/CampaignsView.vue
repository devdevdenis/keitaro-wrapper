<script setup>
import { computed, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import AlertBox from '@/components/AlertBox.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import PageHeader from '@/components/PageHeader.vue'
import RefreshIcon from '@/components/RefreshIcon.vue'
import StateBadge from '@/components/StateBadge.vue'
import TablePagination from '@/components/TablePagination.vue'
import { useAsync } from '@/composables/useAsync'
import { useDeleteCampaign } from '@/composables/useDeleteCampaign'
import { useDictionaries } from '@/composables/useDictionaries'
import { flag, formatDate } from '@/utils/format'

const PAGE_SIZES = [10, 25, 50, 100]
const PER_PAGE_KEY = 'campaigns.perPage'

const route = useRoute()
const router = useRouter()
const { load: loadDictionaries, groupsById, sourcesById } = useDictionaries()
loadDictionaries().catch(() => {})

const { data, error, loading, run } = useAsync(() => api.listCampaigns(), { initial: [] })
const reload = () => run().catch(() => {})
reload()

const removal = useDeleteCampaign(reload)

// --- поиск и страницы хранятся в адресе: «назад» из кампании вернёт на ту же страницу ---

function storedPerPage() {
  try {
    const value = Number(localStorage.getItem(PER_PAGE_KEY))
    return PAGE_SIZES.includes(value) ? value : 25
  } catch {
    return 25
  }
}

function setQuery(patch) {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (query[key] === '' || query[key] == null) delete query[key]
  router.replace({ query })
}

const search = computed({
  get: () => route.query.q ?? '',
  set: (q) => setQuery({ q: q || null, page: null }),
})
const perPage = computed({
  get: () => {
    const value = Number(route.query.per_page)
    return PAGE_SIZES.includes(value) ? value : storedPerPage()
  },
  set: (value) => {
    try {
      localStorage.setItem(PER_PAGE_KEY, String(value))
    } catch {
      // без localStorage просто не запоминаем
    }
    setQuery({ per_page: value, page: null })
  },
})
const page = computed({
  get: () => Math.max(1, Number(route.query.page) || 1),
  set: (value) => setQuery({ page: value > 1 ? value : null }),
})

const campaigns = computed(() => {
  const q = search.value.trim().toLowerCase()
  const list = data.value ?? []
  return q ? list.filter((c) => `${c.id} ${c.name} ${c.alias}`.toLowerCase().includes(q)) : list
})
const pageCount = computed(() => Math.max(1, Math.ceil(campaigns.value.length / perPage.value)))
const pageRows = computed(() =>
  campaigns.value.slice((page.value - 1) * perPage.value, page.value * perPage.value),
)

// после удаления или поиска страница могла опустеть — переходим на последнюю
watch(pageCount, (count) => {
  if (!loading.value && page.value > count) page.value = count
})

const editRoute = (campaign) => ({ name: 'campaign-edit', params: { id: campaign.id } })

/** Клик по любому месту строки открывает кампанию; Cmd/Ctrl-клик и колёсико — в новой вкладке. */
function openCampaign(campaign, event) {
  if (event.target.closest('a, button')) return // ссылка и кнопки строки обрабатывают клик сами
  if (window.getSelection()?.toString()) return // текст выделяли, а не кликали
  const target = editRoute(campaign)
  if (event.metaKey || event.ctrlKey || event.button === 1) {
    window.open(router.resolve(target).href, '_blank', 'noopener')
  } else {
    router.push(target)
  }
}
</script>

<template>
  <section>
    <PageHeader title="Кампании" subtitle="Кампании в трекере Keitaro">
      <template #actions>
        <RouterLink :to="{ name: 'campaign-create' }" class="btn btn-primary">
          + Новая кампания
        </RouterLink>
      </template>
    </PageHeader>

    <div class="card">
      <div class="toolbar">
        <input v-model="search" class="input search" placeholder="Поиск по ID, названию, alias…" />
        <div class="spacer" />
        <button class="btn btn-soft btn-sm" :disabled="loading" @click="reload">
          <RefreshIcon :spinning="loading" /> Обновить
        </button>
      </div>

      <div v-if="error" class="state">
        <AlertBox title="Не удалось загрузить кампании">{{ error.message }}</AlertBox>
      </div>

      <table v-else-if="loading && !campaigns.length" class="table">
        <tbody>
          <tr v-for="i in 4" :key="i">
            <td colspan="7"><div class="skeleton" :style="{ width: `${40 + i * 12}%` }" /></td>
          </tr>
        </tbody>
      </table>

      <div v-else-if="!campaigns.length" class="state empty">
        <p class="muted">
          {{ search ? 'Ничего не найдено.' : 'Кампаний пока нет.' }}
        </p>
        <RouterLink v-if="!search" :to="{ name: 'campaign-create' }" class="btn">
          Создать первую кампанию
        </RouterLink>
      </div>

      <div v-else class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Название</th>
              <th class="hide-sm">Гео</th>
              <th class="hide-sm">Группа / источник</th>
              <th>Статус</th>
              <th class="hide-sm">Создана</th>
              <th class="actions-col"><span class="sr-only">Действия</span></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in pageRows"
              :key="c.id"
              class="clickable"
              @click="openCampaign(c, $event)"
              @auxclick.middle="openCampaign(c, $event)"
            >
              <td class="mono faint">#{{ c.id }}</td>
              <td>
                <RouterLink :to="editRoute(c)" class="campaign-name">
                  {{ c.name }}
                </RouterLink>
                <div class="row sub">
                  <span class="chip">{{ c.alias }}</span>
                  <span v-if="!c.tracked" class="faint" title="Кампания создана напрямую в Keitaro">
                    внешняя
                  </span>
                </div>
              </td>
              <td class="hide-sm">
                <span v-if="c.country_codes.length" :title="c.country_codes.join(', ')">
                  <span v-for="code in c.country_codes" :key="code" class="geo">
                    {{ flag(code) }} {{ code }}
                  </span>
                </span>
                <span v-else class="faint">—</span>
              </td>
              <td class="muted hide-sm">
                {{ groupsById[c.group_id]?.name ?? '—' }}
                <span class="faint"> · </span>
                {{ sourcesById[c.traffic_source_id]?.name ?? '—' }}
              </td>
              <td><StateBadge :state="c.state" /></td>
              <td class="muted nowrap hide-sm">{{ formatDate(c.created_at) }}</td>
              <td class="actions-col">
                <button
                  type="button"
                  class="btn btn-ghost btn-sm btn-danger icon-btn"
                  :aria-label="`Удалить кампанию ${c.name}`"
                  title="Удалить"
                  @click="removal.ask(c)"
                >
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <path d="M4 6h12M8 6V4h4v2M6 6l1 10h6l1-10M9 9v4M11 9v4" />
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <TablePagination
          v-model:page="page"
          v-model:per-page="perPage"
          :total="campaigns.length"
          :sizes="PAGE_SIZES"
        />
      </div>
    </div>

    <ConfirmDialog
      :open="!!removal.target.value"
      :title="`Удалить кампанию «${removal.target.value?.name ?? ''}»?`"
      confirm-label="Удалить"
      danger
      :busy="removal.deleting.value"
      @confirm="removal.confirm"
      @cancel="removal.cancel"
    >
      Кампания будет перемещена в архив Keitaro и пропадёт из списка. Восстановить её можно в
      Keitaro из архива.
    </ConfirmDialog>
  </section>
</template>

<style scoped>
.clickable {
  cursor: pointer;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.search {
  max-width: 320px;
}
.state {
  padding: 20px;
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 20px;
}
.empty p {
  margin: 0;
}
.campaign-name {
  color: var(--text);
  font-weight: 600;
}
.sub {
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
}
.geo {
  display: inline-block;
  margin-right: 8px;
  white-space: nowrap;
}
.nowrap {
  white-space: nowrap;
}
.actions-col {
  width: 48px;
  text-align: right;
}
.icon-btn {
  width: 30px;
  padding: 0;
}
.icon-btn svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}

@media (max-width: 640px) {
  .hide-sm {
    display: none;
  }
  .toolbar {
    flex-wrap: nowrap;
    gap: 8px;
  }
  .toolbar .search {
    flex: 1;
    min-width: 0;
    max-width: none;
  }
  .toolbar .spacer {
    display: none;
  }
  .table th,
  .table td {
    padding-right: 8px;
    padding-left: 8px;
  }
  .table th:first-child,
  .table td:first-child {
    padding-left: 14px;
  }
  .table th:last-child,
  .table td:last-child {
    padding-right: 10px;
  }
  .actions-col {
    width: auto;
  }
}
</style>
