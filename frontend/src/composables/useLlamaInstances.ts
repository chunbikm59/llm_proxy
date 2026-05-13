import { ref, onMounted, onUnmounted } from 'vue'
import { api, type LlamaInstance, type LlamaInstanceConfig, type LlamaSlotInfo } from '@/api'
import { toast } from 'sonner'
import { useConfirmDialog } from './useConfirmDialog'

const UNSTABLE_STATUSES = new Set(['starting', 'restarting'])

export function useLlamaInstances() {
  const instances = ref<LlamaInstance[]>([])
  const slotMap = ref<Record<string, LlamaSlotInfo>>({})
  const loading = ref(false)
  const { confirm } = useConfirmDialog()
  let pollTimer: ReturnType<typeof setInterval> | null = null
  const failedInstances = new Set<string>()

  async function fetchInstances() {
    loading.value = true
    try {
      const [instList, slotsResp] = await Promise.all([
        api.listLlamaInstances(),
        api.getLlamaSlots(),
      ])
      // 同一個 tick 寫入，確保 instances 和 slotMap 永遠一致
      instances.value = instList
      _applySlots(slotsResp.instances)
    } catch (e: unknown) {
      toast.error(`載入失敗：${(e as Error).message}`)
    } finally {
      loading.value = false
    }
  }

  function _applySlots(incoming: LlamaSlotInfo[]) {
    const next: Record<string, LlamaSlotInfo> = {}
    for (const s of incoming) next[s.name] = s
    for (const name of Object.keys(next)) {
      if (!slotMap.value[name]) {
        slotMap.value[name] = next[name]
      } else {
        const cur = slotMap.value[name]
        const nxt = next[name]
        cur.host = nxt.host
        cur.port = nxt.port
        cur.status = nxt.status
        cur.in_flight = nxt.in_flight
        cur.error = nxt.error
        // slots 失敗（null）時保留上次的值，避免 processing 期間閃爍為「—」
        if (nxt.slots) {
          if (!cur.slots) cur.slots = nxt.slots
          else Object.assign(cur.slots, nxt.slots)
          cur.slot_details.splice(0, cur.slot_details.length, ...nxt.slot_details)
        }
      }
    }
    for (const name of Object.keys(slotMap.value)) {
      if (!next[name]) delete slotMap.value[name]
    }
  }

  // 靜默輪詢：instances + slots 同時取得，同一 tick 寫入
  async function _poll() {
    try {
      const [instList, slotsResp] = await Promise.all([
        api.listLlamaInstances(),
        api.getLlamaSlots(),
      ])

      // 檢測狀態變化：starting/restarting → failed
      for (const newInst of instList) {
        const oldInst = instances.value.find(i => i.name === newInst.name)
        if (oldInst && UNSTABLE_STATUSES.has(oldInst.status) && newInst.status === 'failed') {
          if (!failedInstances.has(newInst.name)) {
            failedInstances.add(newInst.name)
            toast.error(`實例「${newInst.name}」啟動失敗，請查看日誌了解詳情`)
          }
        }
      }
      // in-place 更新 instances
      for (const newInst of instList) {
        const idx = instances.value.findIndex(i => i.name === newInst.name)
        if (idx !== -1) Object.assign(instances.value[idx], newInst)
        else instances.value.push(newInst)
      }
      const updatedNames = new Set(instList.map(i => i.name))
      instances.value = instances.value.filter(i => updatedNames.has(i.name))

      _applySlots(slotsResp.instances)
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
    pollTimer = setInterval(_poll, 2000)
  })

  onUnmounted(() => {
    if (pollTimer) clearInterval(pollTimer)
  })

  return { instances, slotMap, loading, fetchInstances, stopInstance, restartInstance, deleteInstance, addInstance, updateInstance }
}
