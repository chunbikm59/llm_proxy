import { ref } from 'vue'
import { api, type ApiKey } from '@/api'
import { toast } from 'sonner'
import { useConfirmDialog } from './useConfirmDialog'

export function useKeys() {
  const keys = ref<ApiKey[]>([])
  const loading = ref(false)
  const { confirm } = useConfirmDialog()

  async function fetchKeys() {
    loading.value = true
    try {
      keys.value = await api.listKeys()
    } catch (e: unknown) {
      toast.error(`載入失敗：${(e as Error).message}`)
    } finally {
      loading.value = false
    }
  }

  async function revokeKey(k: ApiKey) {
    try {
      await api.revokeKey(k.id)
      k.is_active = 0
      toast.success(`已停用 Key「${k.name}」`)
    } catch (e: unknown) {
      toast.error(`停用失敗：${(e as Error).message}`)
    }
  }

  async function activateKey(k: ApiKey) {
    try {
      await api.activateKey(k.id)
      k.is_active = 1
      toast.success(`已啟用 Key「${k.name}」`)
    } catch (e: unknown) {
      toast.error(`啟用失敗：${(e as Error).message}`)
    }
  }

  async function deleteKey(k: ApiKey) {
    const ok = await confirm(
      `確定要永久刪除「${k.name}」？`,
      '此操作不可復原，Key 及所有用量記錄都將被刪除。'
    )
    if (!ok) return
    try {
      await api.deleteKeyPermanent(k.id)
      keys.value = keys.value.filter(x => x.id !== k.id)
      toast.success(`已刪除 Key「${k.name}」`)
    } catch (e: unknown) {
      toast.error(`刪除失敗：${(e as Error).message}`)
    }
  }

  return { keys, loading, fetchKeys, revokeKey, activateKey, deleteKey }
}
