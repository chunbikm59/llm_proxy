import { ref, onMounted, onUnmounted } from 'vue'
import { api, type LlamaInstance, type LlamaInstanceConfig } from '@/api'
import { toast } from 'sonner'
import { useConfirmDialog } from './useConfirmDialog'

const UNSTABLE_STATUSES = new Set(['starting', 'restarting'])

export function useLlamaInstances() {
  const instances = ref<LlamaInstance[]>([])
  const loading = ref(false)
  const { confirm } = useConfirmDialog()
  let pollTimer: ReturnType<typeof setInterval> | null = null
  const failedInstances = new Set<string>()  // 追蹤剛失敗的實例

  async function fetchInstances() {
    loading.value = true
    try {
      instances.value = await api.listLlamaInstances()
    } catch (e: unknown) {
      toast.error(`載入失敗：${(e as Error).message}`)
    } finally {
      loading.value = false
    }
  }

  function _hasUnstable() {
    return instances.value.some(i => UNSTABLE_STATUSES.has(i.status))
  }

  // 靜默輪詢（不設 loading）— 只更新狀態，並檢測失敗
  async function _poll() {
    if (!_hasUnstable()) return
    try {
      const updated = await api.listLlamaInstances()

      // 檢測狀態變化：started/restarting → failed
      for (const newInst of updated) {
        const oldInst = instances.value.find(i => i.name === newInst.name)
        if (oldInst && UNSTABLE_STATUSES.has(oldInst.status) && newInst.status === 'failed') {
          // 實例剛失敗，顯示錯誤提示
          if (!failedInstances.has(newInst.name)) {
            failedInstances.add(newInst.name)
            toast.error(`實例「${newInst.name}」啟動失敗，請查看日誌了解詳情`)
          }
        }
      }

      instances.value = updated
    } catch {
      // 靜默失敗
    }
  }

  async function stopInstance(name: string) {
    try {
      const updated = await api.stopLlamaInstance(name)
      _updateOne(updated)
      toast.success(`已停止實例「${name}」`)
    } catch (e: unknown) {
      toast.error(`停止失敗：${(e as Error).message}`)
    }
  }

  async function restartInstance(name: string) {
    try {
      const updated = await api.restartLlamaInstance(name)
      _updateOne(updated)
      toast.success(`已重啟實例「${name}」`)
    } catch (e: unknown) {
      toast.error(`重啟失敗：${(e as Error).message}`)
    }
  }

  async function deleteInstance(name: string) {
    const ok = await confirm(
      `確定要刪除實例「${name}」？`,
      '此操作將停止並永久移除該實例設定。'
    )
    if (!ok) return
    try {
      await api.deleteLlamaInstance(name)
      instances.value = instances.value.filter(i => i.name !== name)
      toast.success(`已刪除實例「${name}」`)
    } catch (e: unknown) {
      toast.error(`刪除失敗：${(e as Error).message}`)
    }
  }

  function addInstance(instance: LlamaInstance) {
    instances.value.push(instance)
  }

  async function updateInstance(name: string, config: Partial<LlamaInstanceConfig>, restart: boolean): Promise<LlamaInstance> {
    const updated = await api.updateLlamaInstance(name, config, restart)
    _updateOne(updated)
    toast.success(restart ? `已更新並重啟「${name}」` : `已更新「${name}」設定`)
    return updated
  }

  function _updateOne(updated: LlamaInstance) {
    const idx = instances.value.findIndex(i => i.name === updated.name)
    if (idx !== -1) instances.value[idx] = updated
  }

  onMounted(async () => {
    await fetchInstances()
    // 加快輪詢速度（2 秒），讓失敗狀態更快顯示
    pollTimer = setInterval(_poll, 2000)
  })

  onUnmounted(() => {
    if (pollTimer) clearInterval(pollTimer)
  })

  return { instances, loading, fetchInstances, stopInstance, restartInstance, deleteInstance, addInstance, updateInstance }
}
