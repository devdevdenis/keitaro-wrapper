<script setup>
/**
 * Настройки перехватывающего потока: страны, логика фильтров (ИЛИ / И) и адрес редиректа.
 * Каждое изменение уходит в черновик потока; в Keitaro — по Push to KT.
 */
import { computed, ref, watch } from 'vue'
import SearchSelect from '@/components/SearchSelect.vue'

const props = defineProps({
  stream: { type: Object, required: true },
  countryOptions: { type: Array, default: () => [] },
  busy: { type: String, default: null },
})
const emit = defineEmits(['patch'])

const disabled = computed(() => Boolean(props.busy))
const fieldId = (name) => `stream-${props.stream.id}-${name}`

const countries = ref([...props.stream.countries])
const redirectUrl = ref(props.stream.redirect_url)
watch(
  () => props.stream,
  (stream) => {
    countries.value = [...stream.countries]
    redirectUrl.value = stream.redirect_url
  },
)

function saveCountries(codes) {
  countries.value = codes
  emit('patch', { countries: codes })
}

function saveRedirect() {
  if (redirectUrl.value !== props.stream.redirect_url) {
    emit('patch', { redirect_url: redirectUrl.value })
  }
}
</script>

<template>
  <div class="intercept-fields">
    <div class="field wide">
      <label class="field-label" :for="fieldId('countries')">Страны</label>
      <SearchSelect
        :id="fieldId('countries')"
        :model-value="countries"
        multiple
        :options="countryOptions"
        :disabled="disabled"
        placeholder="Выберите одну или несколько стран"
        @update:model-value="saveCountries"
      />
      <span class="field-hint">Трафик из этих стран поток перехватывает и уводит на редирект</span>
    </div>

    <div class="field">
      <label class="field-label" :for="fieldId('logic')">Логика фильтров</label>
      <select
        :id="fieldId('logic')"
        class="input"
        :value="stream.filter_or ? 'or' : 'and'"
        :disabled="disabled"
        @change="emit('patch', { filter_or: $event.target.value === 'or' })"
      >
        <option value="or">ИЛИ — достаточно одного условия</option>
        <option value="and">И — нужны все условия</option>
      </select>
    </div>

    <div class="field wide">
      <label class="field-label" :for="fieldId('redirect')">Редирект на</label>
      <input
        :id="fieldId('redirect')"
        v-model="redirectUrl"
        class="input mono"
        type="url"
        placeholder="https://www.google.com"
        :disabled="disabled"
        @change="saveRedirect"
        @keydown.enter="$event.target.blur()"
      />
    </div>
  </div>
</template>

<style scoped>
/* класс не .fields: стили родительской страницы попадают на корневой элемент компонента */
.intercept-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  padding: 16px 20px 18px;
}
.wide {
  grid-column: span 2;
}
@media (max-width: 860px) {
  .intercept-fields {
    grid-template-columns: 1fr;
  }
  .wide {
    grid-column: auto;
  }
}
</style>
