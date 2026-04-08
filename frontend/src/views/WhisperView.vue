<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { type WhisperCluster, type WhisperTranscriptionJob } from '@/api'
import { api } from '@/api'
import { useWhisperClusters } from '@/composables/useWhisperClusters'
import CreateWhisperClusterDialog from '@/components/whisper/CreateWhisperClusterDialog.vue'
import WhisperLogsDialog from '@/components/whisper/WhisperLogsDialog.vue'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableEmpty
} from '@/components/ui/table'
import { RefreshCw, Plus, ScrollText, Trash2, MicOff, Pencil } from 'lucide-vue-next'

const { clusters, loading, fetchClusters, deleteCluster, addCluster } = useWhisperClusters()

const createDialog = ref<InstanceType<typeof CreateWhisperClusterDialog> | null>(null)
const logsDialog = ref<InstanceType<typeof WhisperLogsDialog> | null>(null)

// 轉錄歷史
const jobs = ref<WhisperTranscriptionJob[]>([])
const jobsLoading = ref(false)

async function fetchJobs() {
  jobsLoading.value = true
  try {
    jobs.value = await api.listTranscriptionJobs(50, 0)
  } catch { /* silent */ } finally {
    jobsLoading.value = false
  }
}

onMounted(fetchJobs)

function onCreated(cluster: WhisperCluster) {
  addCluster(cluster)
}

function onUpdated(cluster: WhisperCluster) {
  const idx = clusters.value.findIndex(c => c.name === cluster.name)
  if (idx !== -1) clusters.value[idx] = cluster
}

type StatusVariant = 'success' | 'default' | 'secondary' | 'destructive' | 'outline' | 'info'

function statusVariant(status: WhisperCluster['status']): StatusVariant {
  switch (status) {
    case 'running': return 'success'
    case 'failed':  return 'destructive'
    default:        return 'secondary'
  }
}

function statusLabel(status: WhisperCluster['status']): string {
  switch (status) {
    case 'running': return '可用'
    case 'failed':  return '失敗'
    case 'stopped': return '閒置'
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').substring(0, 19)
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatAudioDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '—'
  const totalSec = Math.round(ms / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  if (m === 0) return `${s}s`
  return `${m}m ${s}s`
}

function jobStatusVariant(status: WhisperTranscriptionJob['status']): StatusVariant {
  switch (status) {
    case 'done':       return 'success'
    case 'processing': return 'info'
    case 'failed':     return 'destructive'
    default:           return 'secondary'
  }
}

function jobStatusLabel(status: WhisperTranscriptionJob['status']): string {
  switch (status) {
    case 'pending':    return '排隊中'
    case 'processing': return '處理中'
    case 'done':       return '完成'
    case 'failed':     return '失敗'
  }
}
</script>

<template>
  <div class="p-6 max-w-6xl space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold tracking-tight">Whisper.cpp Cluster 管理</h2>
        <p class="text-xs text-muted-foreground mt-0.5">管理本地 whisper-cli 設定與音訊轉錄任務</p>
      </div>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchClusters(); fetchJobs()">
          <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          刷新
        </Button>
        <Button size="sm" @click="createDialog?.open()">
          <Plus class="h-3.5 w-3.5" />
          新增 Cluster
        </Button>
      </div>
    </div>

    <!-- Clusters Table -->
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>名稱</TableHead>
          <TableHead>狀態</TableHead>
          <TableHead>進行中</TableHead>
          <TableHead>上限</TableHead>
          <TableHead>執行檔</TableHead>
          <TableHead>模型</TableHead>
          <TableHead class="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableEmpty v-if="clusters.length === 0" :colspan="7">
          <div class="flex flex-col items-center gap-2 py-4 text-muted-foreground">
            <MicOff class="h-8 w-8 opacity-25" />
            <p>尚無 Cluster，點擊「新增 Cluster」開始</p>
          </div>
        </TableEmpty>
        <TableRow v-for="c in clusters" :key="c.name">
          <TableCell class="font-medium">
            {{ c.name }}
            <Badge v-if="c.config.is_default" variant="outline" class="ml-1.5 text-xs">預設</Badge>
          </TableCell>
          <TableCell>
            <Badge :variant="statusVariant(c.status)">{{ statusLabel(c.status) }}</Badge>
          </TableCell>
          <TableCell class="font-mono text-sm">
            {{ c.active_count }} / {{ c.config.max_instances }}
          </TableCell>
          <TableCell class="font-mono text-sm text-muted-foreground">
            {{ c.config.max_instances }}
          </TableCell>
          <TableCell class="font-mono text-xs text-muted-foreground max-w-48 truncate" :title="c.config.executable_path">
            {{ c.config.executable_path.split(/[\\/]/).pop() }}
          </TableCell>
          <TableCell class="font-mono text-xs text-muted-foreground max-w-48 truncate" :title="c.config.model_path">
            {{ c.config.model_path.split(/[\\/]/).pop() }}
          </TableCell>
          <TableCell class="text-right">
            <div class="flex items-center justify-end gap-1">
              <Button
                variant="ghost"
                size="icon-sm"
                title="編輯設定"
                @click="createDialog?.openEdit(c)"
              >
                <Pencil class="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                title="查看日誌"
                @click="logsDialog?.open(c.name)"
              >
                <ScrollText class="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                title="刪除"
                class="text-destructive hover:text-destructive"
                @click="deleteCluster(c.name)"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </Button>
            </div>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <!-- 模型摘要卡 -->
    <div v-if="clusters.length > 0" class="space-y-2">
      <h3 class="text-xs font-medium text-muted-foreground uppercase tracking-widest">模型設定摘要</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        <Card v-for="c in clusters" :key="c.name" class="text-xs">
          <CardContent class="pt-4 pb-3 px-4 space-y-1.5">
            <div class="font-semibold text-sm mb-2 flex items-center gap-2">
              {{ c.name }}
              <Badge v-if="c.config.is_default" variant="outline" class="text-xs">預設</Badge>
            </div>
            <div class="text-muted-foreground break-all">{{ c.config.model_path }}</div>
            <div class="flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground mt-1">
              <span v-if="c.config.n_threads">threads {{ c.config.n_threads }}</span>
              <span v-if="c.config.n_processors">proc {{ c.config.n_processors }}</span>
              <span v-if="c.config.beam_size">beam {{ c.config.beam_size }}</span>
              <span v-if="c.config.audio_ctx">ctx {{ c.config.audio_ctx }}</span>
              <span>max {{ c.config.max_instances }} 並發</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>

    <!-- 轉錄歷史 -->
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-medium text-muted-foreground uppercase tracking-widest">轉錄歷史</h3>
        <Button variant="ghost" size="sm" :disabled="jobsLoading" @click="fetchJobs">
          <RefreshCw class="h-3 w-3" :class="jobsLoading ? 'animate-spin' : ''" />
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>時間</TableHead>
            <TableHead>檔名</TableHead>
            <TableHead>音訊長度</TableHead>
            <TableHead>處理時間</TableHead>
            <TableHead>狀態</TableHead>
            <TableHead>Cluster</TableHead>
            <TableHead>錯誤</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableEmpty v-if="jobs.length === 0" :colspan="7">
            <p class="text-center text-muted-foreground py-4">尚無轉錄記錄</p>
          </TableEmpty>
          <TableRow v-for="job in jobs" :key="job.id">
            <TableCell class="text-xs text-muted-foreground whitespace-nowrap">
              {{ formatTime(job.created_at) }}
            </TableCell>
            <TableCell class="text-xs max-w-32 truncate" :title="job.filename">
              {{ job.filename }}
            </TableCell>
            <TableCell class="text-xs font-mono">{{ formatAudioDuration(job.audio_duration_ms) }}</TableCell>
            <TableCell class="text-xs font-mono">{{ formatDuration(job.processing_time_ms) }}</TableCell>
            <TableCell>
              <Badge :variant="jobStatusVariant(job.status)" class="text-xs">
                {{ jobStatusLabel(job.status) }}
              </Badge>
            </TableCell>
            <TableCell class="text-xs text-muted-foreground">{{ job.cluster_name ?? '—' }}</TableCell>
            <TableCell class="text-xs text-destructive max-w-40 truncate" :title="job.error_message ?? ''">
              {{ job.error_message ?? '' }}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  </div>

  <CreateWhisperClusterDialog ref="createDialog" @created="onCreated" @updated="onUpdated" />
  <WhisperLogsDialog ref="logsDialog" />
</template>
