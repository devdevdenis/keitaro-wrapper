import { ref } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'

/**
 * Удаление кампании с подтверждением: ask(campaign) открывает диалог, confirm() удаляет.
 * В Keitaro кампания уходит в архив.
 */
export function useDeleteCampaign(onDeleted) {
  const toast = useToast()
  const target = ref(null)
  const deleting = ref(false)

  function ask(campaign) {
    target.value = campaign
  }

  function cancel() {
    if (!deleting.value) target.value = null
  }

  async function confirm() {
    const campaign = target.value
    if (!campaign) return
    deleting.value = true
    try {
      await api.deleteCampaign(campaign.id)
      toast.success(`Кампания «${campaign.name}» удалена`)
      target.value = null
      await onDeleted?.(campaign)
    } catch (e) {
      toast.error(e.message)
    } finally {
      deleting.value = false
    }
  }

  return { target, deleting, ask, cancel, confirm }
}
