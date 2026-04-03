import { ref, onMounted } from 'vue'
import { api, type WhisperCluster, type WhisperClusterConfig } from '@/api'
import { toast } from 'sonner'
import { useConfirmDialog } from './useConfirmDialog'

export function useWhisperClusters() {
  const clusters = ref<WhisperCluster[]>([])
  const loading = ref(false)
  const { confirm } = useConfirmDialog()

  async function fetchClusters() {
    loading.value = true
    try {
      clusters.value = await api.listWhisperClusters()
    } catch (e: unknown) {
      toast.error(`載入失敗：${(e as Error).message}`)
    } finally {
      loading.value = false
    }
  }

  async function deleteCluster(name: string) {
    const ok = await confirm(
      `確定要刪除 Cluster「${name}」？`,
      '此操作將永久移除該 Cluster 設定。'
    )
    if (!ok) return
    try {
      await api.deleteWhisperCluster(name)
      clusters.value = clusters.value.filter(c => c.name !== name)
      toast.success(`已刪除 Cluster「${name}」`)
    } catch (e: unknown) {
      toast.error(`刪除失敗：${(e as Error).message}`)
    }
  }

  function addCluster(cluster: WhisperCluster) {
    clusters.value.push(cluster)
  }

  async function updateCluster(name: string, config: Partial<WhisperClusterConfig>): Promise<WhisperCluster> {
    const updated = await api.updateWhisperCluster(name, config)
    const idx = clusters.value.findIndex(c => c.name === name)
    if (idx !== -1) clusters.value[idx] = updated
    toast.success(`已更新「${name}」設定`)
    return updated
  }

  onMounted(fetchClusters)

  return { clusters, loading, fetchClusters, deleteCluster, addCluster, updateCluster }
}
