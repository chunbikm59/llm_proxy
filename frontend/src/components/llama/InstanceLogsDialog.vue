<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { api } from '@/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { RefreshCw } from 'lucide-vue-next'

const visible = ref(false)
const instanceName = ref('')
const logs = ref<string[]>([])
const loading = ref(false)
const lines = ref('200')  // 預設多一點行數方便看錯誤
const logsContainer = ref<HTMLElement | null>(null)

const linesOptions = [
  { value: '50', label: '最後 50 行' },
  { value: '100', label: '最後 100 行' },
  { value: '200', label: '最後 200 行' },
  { value: '500', label: '最後 500 行' },
]

async function fetchLogs() {
  loading.value = true
  try {
    logs.value = await api.getLlamaInstanceLogs(instanceName.value, Number(lines.value))
  } catch {
    logs.value = ['[錯誤] 無法取得日誌']
  } finally {
    loading.value = false
    await nextTick()
    if (logsContainer.value) {
      logsContainer.value.scrollTop = logsContainer.value.scrollHeight
    }
  }
}

function highlightErrorLines(line: string): string {
  // 關鍵字突出顯示
  if (line.includes('failed') || line.includes('error') || line.includes('Error') || line.includes('ERROR')) {
    return 'text-red-400 bg-red-950 bg-opacity-30'
  }
  if (line.includes('warning') || line.includes('Warning')) {
    return 'text-yellow-400'
  }
  return ''
}

async function open(name: string) {
  instanceName.value = name
  logs.value = []
  lines.value = '200'  // 預設顯示 200 行方便看錯誤
  visible.value = true
  await nextTick()  // 等 Dialog DOM 掛載後再 fetch
  await fetchLogs()
}

function close() {
  visible.value = false
}

defineExpose({ open })
</script>

<template>
  <Dialog :open="visible">
    <DialogContent max-width="max-w-3xl" @close="close">
      <DialogHeader>
        <DialogTitle>日誌：{{ instanceName }}</DialogTitle>
      </DialogHeader>

      <div class="flex items-center gap-2 mb-3">
        <Select v-model="lines" :options="linesOptions" class="w-36" @update:model-value="fetchLogs" />
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchLogs">
          <RefreshCw class="h-3.5 w-3.5 mr-1.5" :class="loading ? 'animate-spin' : ''" />
          刷新
        </Button>
      </div>

      <div ref="logsContainer" class="rounded-md border bg-zinc-950 overflow-auto" style="height: 400px">
        <pre class="p-3 text-xs font-mono text-zinc-200 leading-relaxed whitespace-pre-wrap break-all">
          <span v-if="loading" class="text-zinc-500">載入中…</span>
          <span v-else-if="logs.length === 0" class="text-zinc-500">（無日誌輸出）</span>
          <template v-else>
            <span v-for="(line, idx) in logs" :key="idx" :class="highlightErrorLines(line)">{{ line }}<br/></span>
          </template>
        </pre>
      </div>
    </DialogContent>
  </Dialog>
</template>
