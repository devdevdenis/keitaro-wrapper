<script setup>
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/api'
import AlertBox from '@/components/AlertBox.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useAsync } from '@/composables/useAsync'
import { useDictionaries } from '@/composables/useDictionaries'
import { flag, formatDate } from '@/utils/format'

const { load: loadDictionaries, groupsById, sourcesById } = useDictionaries()
loadDictionaries().catch(() => {})

const search = ref('')
const { data, error, loading, run } = useAsync(() => api.listCampaigns(), { initial: [] })
run().catch(() => {})

const campaigns = computed(() => {
  const q = search.value.trim().toLowerCase()
  const list = data.value ?? []
  return q ? list.filter((c) => `${c.id} ${c.name} ${c.alias}`.toLowerCase().includes(q)) : list
})
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
        <button class="btn btn-ghost btn-sm" :disabled="loading" @click="run().catch(() => {})">
          <span v-if="loading" class="spinner" /> Обновить
        </button>
      </div>

      <div v-if="error" class="state">
        <AlertBox title="Не удалось загрузить кампании">{{ error.message }}</AlertBox>
      </div>

      <table v-else-if="loading && !campaigns.length" class="table">
        <tbody>
          <tr v-for="i in 4" :key="i">
            <td colspan="6"><div class="skeleton" :style="{ width: `${40 + i * 12}%` }" /></td>
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
              <th>Гео</th>
              <th>Группа / источник</th>
              <th>Статус</th>
              <th>Создана</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in campaigns" :key="c.id">
              <td class="mono faint">#{{ c.id }}</td>
              <td>
                <RouterLink
                  :to="{ name: 'campaign-edit', params: { id: c.id } }"
                  class="campaign-name"
                >
                  {{ c.name }}
                </RouterLink>
                <div class="row sub">
                  <span class="chip">{{ c.alias }}</span>
                  <span v-if="!c.tracked" class="faint" title="Создана не через обёртку">
                    внешняя
                  </span>
                </div>
              </td>
              <td>
                <span v-if="c.country_codes.length" :title="c.country_codes.join(', ')">
                  <span v-for="code in c.country_codes" :key="code" class="geo">
                    {{ flag(code) }} {{ code }}
                  </span>
                </span>
                <span v-else class="faint">—</span>
              </td>
              <td class="muted">
                {{ groupsById[c.group_id]?.name ?? '—' }}
                <span class="faint"> · </span>
                {{ sourcesById[c.traffic_source_id]?.name ?? '—' }}
              </td>
              <td><StateBadge :state="c.state" /></td>
              <td class="muted nowrap">{{ formatDate(c.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
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
.table-wrap {
  overflow-x: auto;
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
</style>
