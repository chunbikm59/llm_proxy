<script setup lang="ts">
import { ref } from 'vue'
import { api, type ApiKey, type UsageRow } from '@/api'
import { fmtNum } from '@/utils/format'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Loader2 } from 'lucide-vue-next'

const visible = ref(false)
const currentKey = ref<ApiKey | null>(null)
const data = ref<UsageRow[]>([])
const loading = ref(false)

async function open(k: ApiKey) {
  currentKey.value = k
  visible.value = true
  loading.value = true
  data.value = []
  try {
    data.value = await api.getKeyUsage(k.id)
  } finally {
    loading.value = false
  }
}

function close() {
  visible.value = false
}

defineExpose({ open })
</script>

<template>
  <Dialog :open="visible">
    <DialogContent max-width="max-w-3xl" class="p-0" @close="close">
      <div class="px-6 pt-6 pb-4 border-b">
        <DialogHeader>
          <DialogTitle>{{ currentKey?.name }} 用量記錄</DialogTitle>
          <p class="text-xs text-muted-foreground font-mono mt-1">{{ currentKey?.key }}</p>
        </DialogHeader>
      </div>

      <div class="max-h-[60vh] overflow-y-auto px-6 py-4">
        <div v-if="loading" class="flex items-center justify-center py-12 gap-2 text-muted-foreground">
          <Loader2 class="h-5 w-5 animate-spin" />
          <span class="text-sm">載入中…</span>
        </div>

        <div v-else-if="!data.length" class="py-12 text-center text-muted-foreground text-sm">
          尚無用量記錄
        </div>

        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead>日期</TableHead>
              <TableHead>模型</TableHead>
              <TableHead class="text-right">Input</TableHead>
              <TableHead class="text-right">Output</TableHead>
              <TableHead class="text-right">Total</TableHead>
              <TableHead class="text-right">Requests</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="(r, i) in data" :key="i">
              <TableCell class="font-mono text-xs">{{ r.date }}</TableCell>
              <TableCell class="text-xs text-muted-foreground">{{ r.model }}</TableCell>
              <TableCell class="text-right font-mono text-xs">{{ fmtNum(r.input_tokens) }}</TableCell>
              <TableCell class="text-right font-mono text-xs">{{ fmtNum(r.output_tokens) }}</TableCell>
              <TableCell class="text-right font-mono text-xs">{{ fmtNum(r.total_tokens) }}</TableCell>
              <TableCell class="text-right font-mono text-xs">{{ r.requests || 1 }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </DialogContent>
  </Dialog>
</template>
