<script setup>
import { computed } from 'vue'

/** Пагинация таблицы: «1–25 из 230», номера страниц и выбор количества строк. */
const page = defineModel('page', { type: Number, required: true })
const perPage = defineModel('perPage', { type: Number, required: true })
const props = defineProps({
  total: { type: Number, required: true },
  sizes: { type: Array, default: () => [10, 25, 50, 100] },
})

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / perPage.value)))
const from = computed(() => (props.total ? (page.value - 1) * perPage.value + 1 : 0))
const to = computed(() => Math.min(page.value * perPage.value, props.total))

/** 1 … 4 5 [6] 7 8 … 20 */
const pages = computed(() => {
  const last = pageCount.value
  const current = page.value
  const wanted = new Set([1, last, current - 2, current - 1, current, current + 1, current + 2])
  const list = [...wanted].filter((n) => n >= 1 && n <= last).sort((a, b) => a - b)
  const result = []
  list.forEach((n, i) => {
    if (i && n - list[i - 1] > 1) result.push(null) // разрыв
    result.push(n)
  })
  return result
})

function go(n) {
  page.value = Math.min(Math.max(n, 1), pageCount.value)
}
</script>

<template>
  <nav class="pagination" aria-label="Страницы">
    <span class="range muted">
      <template v-if="total">{{ from }}–{{ to }} из {{ total }}</template>
      <template v-else>0 из 0</template>
    </span>

    <label class="size">
      <span class="faint">Строк на странице</span>
      <select v-model.number="perPage" class="input size-select">
        <option v-for="size in sizes" :key="size" :value="size">{{ size }}</option>
      </select>
    </label>

    <div class="pages">
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        :disabled="page <= 1"
        aria-label="Предыдущая страница"
        @click="go(page - 1)"
      >
        ‹
      </button>
      <template v-for="(n, i) in pages" :key="n ?? `gap-${i}`">
        <span v-if="n === null" class="gap faint">…</span>
        <button
          v-else
          type="button"
          class="btn btn-ghost btn-sm page"
          :class="{ current: n === page }"
          :aria-current="n === page ? 'page' : undefined"
          @click="go(n)"
        >
          {{ n }}
        </button>
      </template>
      <button
        type="button"
        class="btn btn-ghost btn-sm"
        :disabled="page >= pageCount"
        aria-label="Следующая страница"
        @click="go(page + 1)"
      >
        ›
      </button>
    </div>
  </nav>
</template>

<style scoped>
.pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 20px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}
.range {
  font-variant-numeric: tabular-nums;
}
.size {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.size-select {
  width: auto;
  height: 30px;
  padding: 0 8px;
}
.pages {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
}
.page {
  min-width: 30px;
  font-variant-numeric: tabular-nums;
}
.page.current {
  background: var(--accent-soft);
  color: var(--accent);
}
.gap {
  padding: 0 4px;
}
</style>
