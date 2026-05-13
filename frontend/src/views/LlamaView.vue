<script setup lang="ts">
import { ref } from 'vue'
import { type LlamaInstance } from '@/api'
import { useLlamaInstances } from '@/composables/useLlamaInstances'
import CreateInstanceDialog from '@/components/llama/CreateInstanceDialog.vue'
import InstanceLogsDialog from '@/components/llama/InstanceLogsDialog.vue'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableEmpty
} from '@/components/ui/table'
import { AlertCircle, RefreshCw, Plus, Square, RotateCcw, ScrollText, Trash2, ServerOff, Pencil, ExternalLink } from 'lucide-vue-next'

const { instances, slotMap, loading, fetchInstances, stopInstance, restartInstance, deleteInstance, addInstance } =
  useLlamaInstances()

const createDialog = ref<InstanceType<typeof CreateInstanceDialog> | null>(null)
const logsDialog = ref<InstanceType<typeof InstanceLogsDialog> | null>(null)

// 展開的 slot 詳情：instance name
const expandedSlots = ref<Set<string>>(new Set())

function toggleSlots(name: string) {
  const s = new Set(expandedSlots.value)
  s.has(name) ? s.delete(name) : s.add(name)
  expandedSlots.value = s
}

function onCreated(instance: LlamaInstance) {
  addInstance(instance)
}

function onUpdated(instance: LlamaInstance) {
  const idx = instances.value.findIndex(i => i.name === instance.name)
  if (idx !== -1) instances.value[idx] = instance
}

type StatusVariant = 'success' | 'default' | 'secondary' | 'destructive' | 'outline' | 'info'

function statusVariant(status: LlamaInstance['status']): StatusVariant {
  switch (status) {
    case 'running':    return 'success'
    case 'starting':
    case 'restarting': return 'info'
    case 'failed':     return 'destructive'
    default:           return 'secondary'
  }
}

function statusLabel(status: LlamaInstance['status']): string {
  switch (status) {
    case 'running':    return '運行中'
    case 'starting':   return '啟動中'
    case 'restarting': return '重啟中'
    case 'failed':     return '失敗'
    case 'stopped':    return '已停止'
  }
}

function isUnstable(status: LlamaInstance['status']): boolean {
  return status === 'starting' || status === 'restarting'
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').substring(0, 19)
}
</script>

<template>
  <div class="p-6 max-w-6xl space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold tracking-tight">llama.cpp 實例管理</h2>
        <p class="text-xs text-muted-foreground mt-0.5">管理本地 llama.cpp server 執行程序</p>
      </div>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchInstances">
          <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          刷新
        </Button>
        <Button size="sm" @click="createDialog?.open()">
          <Plus class="h-3.5 w-3.5" />
          新增實例
        </Button>
      </div>
    </div>

    <!-- 失敗警告 -->
    <div v-if="instances.some(i => i.status === 'failed')" class="rounded-lg border border-red-200 bg-red-50 p-4 flex gap-3">
      <AlertCircle class="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
      <div class="text-sm text-red-800">
        <p class="font-semibold mb-1">實例啟動失敗</p>
        <p class="text-xs">點擊「查看日誌」按鈕了解失敗原因</p>
      </div>
    </div>

    <!-- Table -->
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>名稱</TableHead>
          <TableHead>狀態</TableHead>
          <TableHead>位址</TableHead>
          <TableHead>Web UI</TableHead>
          <TableHead>PID</TableHead>
          <TableHead>啟動時間</TableHead>
          <TableHead>重啟</TableHead>
          <TableHead class="text-center">推論</TableHead>
          <TableHead class="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableEmpty v-if="instances.length === 0" :colspan="9">
          <div class="flex flex-col items-center gap-2 py-4 text-muted-foreground">
            <ServerOff class="h-8 w-8 opacity-25" />
            <p>尚無實例，點擊「新增實例」開始</p>
          </div>
        </TableEmpty>
        <template v-for="inst in instances" :key="inst.name">
        <TableRow>
          <TableCell class="font-medium">{{ inst.name }}</TableCell>
          <TableCell>
            <div class="flex items-center gap-1.5">
              <RefreshCw
                v-if="isUnstable(inst.status)"
                class="h-3 w-3 animate-spin text-blue-500"
              />
              <Badge :variant="statusVariant(inst.status)">{{ statusLabel(inst.status) }}</Badge>
            </div>
          </TableCell>
          <TableCell class="font-mono text-xs text-muted-foreground">
            {{ inst.config.host }}:{{ inst.config.port }}
          </TableCell>
          <TableCell>
            <a
              v-if="!inst.config.no_webui && inst.status === 'running'"
              :href="`http://${inst.config.host}:${inst.config.port}`"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 text-xs text-blue-500 hover:underline"
            >
              <ExternalLink class="h-3 w-3" />
              開啟
            </a>
            <span v-else-if="!inst.config.no_webui" class="text-xs text-muted-foreground">未啟動</span>
            <span v-else class="text-xs text-muted-foreground">已停用</span>
          </TableCell>
          <TableCell class="font-mono text-xs">{{ inst.pid ?? '—' }}</TableCell>
          <TableCell class="text-xs text-muted-foreground">{{ formatTime(inst.started_at) }}</TableCell>
          <TableCell class="text-center">{{ inst.restart_count }}</TableCell>
          <TableCell class="text-center">
            <template v-if="inst.status === 'running' && slotMap[inst.config.port]?.slots">
              <button
                class="tabular-nums text-xs hover:opacity-70 transition-opacity cursor-pointer"
                :title="expandedSlots.has(inst.name) ? '收起 slot 詳情' : '展開 slot 詳情'"
                @click="toggleSlots(inst.name)"
              >
                <span class="text-emerald-500 font-medium">{{ slotMap[inst.config.port]!.slots!.processing }}</span>
                <span class="text-muted-foreground">/{{ slotMap[inst.config.port]!.slots!.total }}</span>
                <span v-if="slotMap[inst.config.port]!.slots!.queued > 0" class="ml-1 text-amber-500">
                  +{{ slotMap[inst.config.port]!.slots!.queued }}
                </span>
              </button>
            </template>
            <span v-else class="text-xs text-muted-foreground">—</span>
          </TableCell>
          <TableCell class="text-right">
            <div class="flex items-center justify-end gap-1">
              <!-- 停止（運行中才顯示） -->
              <Button
                v-if="inst.status === 'running' || inst.status === 'starting'"
                variant="ghost"
                size="icon-sm"
                title="停止"
                @click="stopInstance(inst.name)"
              >
                <Square class="h-3.5 w-3.5" />
              </Button>

              <!-- 重啟 -->
              <Button
                variant="ghost"
                size="icon-sm"
                title="重啟"
                :disabled="isUnstable(inst.status)"
                @click="restartInstance(inst.name)"
              >
                <RotateCcw class="h-3.5 w-3.5" />
              </Button>

              <!-- 編輯 -->
              <Button
                variant="ghost"
                size="icon-sm"
                title="編輯設定"
                @click="createDialog?.openEdit(inst)"
              >
                <Pencil class="h-3.5 w-3.5" />
              </Button>

              <!-- 日誌 -->
              <Button
                variant="ghost"
                size="icon-sm"
                title="查看日誌"
                @click="logsDialog?.open(inst.name)"
              >
                <ScrollText class="h-3.5 w-3.5" />
              </Button>

              <!-- 刪除 -->
              <Button
                variant="ghost"
                size="icon-sm"
                title="刪除"
                class="text-destructive hover:text-destructive"
                @click="deleteInstance(inst.name)"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </Button>
            </div>
          </TableCell>
        </TableRow>

        <!-- Slot 詳情展開列 -->
        <TableRow
          v-if="expandedSlots.has(inst.name) && slotMap[inst.config.port]?.slot_details?.length"
          class="bg-muted/30 hover:bg-muted/30"
        >
          <TableCell :colspan="9" class="py-2 px-4">
            <div class="space-y-1.5">
              <div
                v-for="(slot, idx) in slotMap[inst.config.port]!.slot_details"
                :key="idx"
                class="flex items-start gap-3 rounded-md border px-3 py-2 text-xs"
                :class="slot.is_processing ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-border bg-background'"
              >
                <!-- Slot ID + 狀態 -->
                <div class="flex items-center gap-1.5 shrink-0 w-20">
                  <span
                    class="inline-block h-2 w-2 rounded-full shrink-0"
                    :class="slot.is_processing ? 'bg-emerald-500' : 'bg-muted-foreground/30'"
                  />
                  <span class="font-mono font-medium">Slot {{ slot.id ?? idx }}</span>
                </div>

                <!-- 推論進度 -->
                <template v-if="slot.is_processing">
                  <!-- prompt processing 階段：n_decoded = 0 -->
                  <div v-if="!slot.n_decoded" class="flex items-center gap-1.5 shrink-0 text-amber-500">
                    <svg class="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
                    </svg>
                    <span class="text-xs">處理 prompt...</span>
                    <span v-if="slot.n_prompt_tokens" class="text-xs opacity-70">({{ slot.n_prompt_tokens }} tokens)</span>
                  </div>
                  <!-- 生成階段：n_decoded > 0 -->
                  <div v-else class="flex items-center gap-3 shrink-0">
                    <span class="text-muted-foreground">
                      已生成 <span class="tabular-nums font-medium text-foreground">{{ slot.n_decoded }}</span> tokens
                    </span>
                    <span v-if="slot.n_remain != null && slot.n_remain >= 0" class="text-muted-foreground">
                      剩餘 <span class="tabular-nums font-medium text-foreground">{{ slot.n_remain }}</span>
                    </span>
                    <span v-if="slot.n_prompt_tokens" class="text-muted-foreground">
                      prompt <span class="tabular-nums font-medium text-foreground">{{ slot.n_prompt_tokens }}</span> tokens
                    </span>
                  </div>
                </template>
                <div v-else class="text-muted-foreground/60 shrink-0">空閒</div>

                <!-- Prompt 預覽 -->
                <div v-if="slot.is_processing && slot.prompt" class="flex-1 min-w-0 font-mono text-muted-foreground truncate" :title="slot.prompt">
                  {{ slot.prompt }}
                </div>

                <!-- 採樣參數 -->
                <div v-if="slot.is_processing" class="flex items-center gap-2 shrink-0 text-muted-foreground/70">
                  <span v-if="slot.temperature != null">temp {{ slot.temperature }}</span>
                  <span v-if="slot.top_p != null">top_p {{ slot.top_p }}</span>
                </div>
              </div>
            </div>
          </TableCell>
        </TableRow>
        </template>
      </TableBody>
    </Table>

    <!-- 實例詳細資訊卡（點擊展開，可選） -->
    <div v-if="instances.length > 0" class="space-y-2">
      <h3 class="text-xs font-medium text-muted-foreground uppercase tracking-widest">模型設定摘要</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        <Card v-for="inst in instances" :key="inst.name" class="text-xs">
          <CardContent class="pt-4 pb-3 px-4 space-y-1.5">
            <div class="font-semibold text-sm mb-2">{{ inst.name }}</div>
            <div class="text-muted-foreground break-all">{{ inst.config.model_path }}</div>
            <div class="flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground mt-1">
              <span>ctx {{ inst.config.context_size }}</span>
              <span>GPU {{ inst.config.n_gpu_layers }}</span>
              <span>parallel {{ inst.config.parallel }}</span>
              <span v-if="inst.config.flash_attn">flash-attn</span>
              <span v-if="inst.config.cont_batching">cont-batch</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  </div>

  <CreateInstanceDialog ref="createDialog" @created="onCreated" @updated="onUpdated" />
  <InstanceLogsDialog ref="logsDialog" />
</template>
