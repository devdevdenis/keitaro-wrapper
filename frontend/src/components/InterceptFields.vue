<script setup>
/**
 * Настройки перехватывающего потока: страны и адрес редиректа (логика фильтров — всегда «ИЛИ»
 * для новых потоков, у существующих остаётся как в Keitaro).
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
    <div class="field">
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
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  padding: 16px 20px 18px;
}
</style>
