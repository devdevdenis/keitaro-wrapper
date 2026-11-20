<script setup>
/**
 * Модальное подтверждение действия (нативный <dialog>).
 * Открывается, когда open = true; закрытие — Esc, «Отмена» или клик по фону.
 */
import { ref, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, required: true },
  confirmLabel: { type: String, default: 'Подтвердить' },
  danger: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['confirm', 'cancel'])

const dialog = ref(null)

watch(
  () => props.open,
  (open) => {
    if (open && !dialog.value?.open) dialog.value?.showModal()
    if (!open && dialog.value?.open) dialog.value.close()
  },
  { flush: 'post' },
)

function cancel() {
  if (!props.busy) emit('cancel')
}

function onBackdrop(event) {
  if (event.target === dialog.value) cancel()
}
</script>

<template>
  <dialog
    ref="dialog"
    class="confirm"
    @cancel.prevent="cancel"
    @click="onBackdrop"
  >
    <div class="confirm-body">
      <h2>{{ title }}</h2>
      <div class="muted"><slot /></div>
    </div>
    <footer class="confirm-footer">
      <button type="button" class="btn btn-ghost" :disabled="busy" @click="cancel">Отмена</button>
      <button
        type="button"
        class="btn"
        :class="danger ? 'btn-danger-solid' : 'btn-primary'"
        :disabled="busy"
        @click="emit('confirm')"
      >
        <span v-if="busy" class="spinner" /> {{ confirmLabel }}
      </button>
    </footer>
  </dialog>
</template>

<style scoped>
.confirm {
  width: min(440px, calc(100vw - 32px));
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-lg);
}
.confirm::backdrop {
  background: rgb(0 0 0 / 45%);
}
.confirm-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px 20px 16px;
}
h2 {
  font-size: 16px;
}
.confirm-body p {
  margin: 0;
}
.confirm-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  background: var(--surface-2);
}
.btn-danger-solid {
  border-color: var(--red);
  background: var(--red);
  color: #fff;
}
.btn-danger-solid:hover {
  background: color-mix(in srgb, var(--red) 85%, #000);
}
</style>
