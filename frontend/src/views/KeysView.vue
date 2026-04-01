<script setup lang="ts">
import { ref } from 'vue'
import { toast } from 'sonner'
import { type ApiKey } from '@/api'
import { copyText } from '@/utils/clipboard'
import { fmtNum, fmtCost, fmtDate } from '@/utils/format'
import { useKeys } from '@/composables/useKeys'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableEmpty } from '@/components/ui/table'
import CreateKeyDialog from '@/components/keys/CreateKeyDialog.vue'
import EditKeyDialog from '@/components/keys/EditKeyDialog.vue'
import KeyUsageDialog from '@/components/keys/KeyUsageDialog.vue'
import { Plus, Copy, BarChart2, Pencil, Pause, Play, Trash2, Loader2, KeyRound } from 'lucide-vue-next'

interface Props {
  keysState: ReturnType<typeof useKeys>
}

const props = defineProps<Props>()
const { keys, loading, fetchKeys, revokeKey, activateKey, deleteKey } = props.keysState

const createDialog = ref<InstanceType<typeof CreateKeyDialog> | null>(null)
const editDialog = ref<InstanceType<typeof EditKeyDialog> | null>(null)
const usageDialog = ref<InstanceType<typeof KeyUsageDialog> | null>(null)

function onCreated(newKey: ApiKey) {
  toast.success(`Key「${newKey.name}」建立成功`)
  fetchKeys()
}

function onUpdated(updatedKey: ApiKey) {
  const idx = keys.value.findIndex(k => k.id === updatedKey.id)
  if (idx >= 0) keys.value[idx] = updatedKey
}

async function copy(key: string) {
  await copyText(key)
  toast.success('已複製到剪貼簿')
}
</script>

<template>
  <div class="p-6 space-y-5">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-semibold tracking-tight">API Key 管理</h2>
        <p class="text-sm text-muted-foreground mt-0.5">管理所有虛擬 API Key</p>
      </div>
      <Button @click="createDialog?.open()">
        <Plus class="h-4 w-4" />
        建立新 Key
      </Button>
    </div>

    <!-- Table Card -->
    <Card>
      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-16 gap-2 text-muted-foreground">
        <Loader2 class="h-5 w-5 animate-spin" />
        <span class="text-sm">載入中…</span>
      </div>

      <Table v-else>
        <TableHeader>
          <TableRow>
            <TableHead class="w-12">ID</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Key</TableHead>
            <TableHead>建立時間</TableHead>
            <TableHead>狀態</TableHead>
            <TableHead class="text-right">Requests</TableHead>
            <TableHead class="text-right">Tokens</TableHead>
            <TableHead class="text-right">Cost</TableHead>
            <TableHead class="text-center w-40">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableEmpty v-if="!keys.length" :colspan="10">
            <div class="flex flex-col items-center gap-2">
              <KeyRound class="h-10 w-10 opacity-20" />
              <span>尚無 API Key，點擊右上角建立第一個</span>
            </div>
          </TableEmpty>

          <TableRow v-for="k in keys" :key="k.id">
            <TableCell class="text-muted-foreground font-mono text-xs">#{{ k.id }}</TableCell>
            <TableCell class="font-medium">{{ k.name }}</TableCell>
            <TableCell class="text-muted-foreground text-xs">{{ k.description || '—' }}</TableCell>
            <TableCell>
              <div class="flex items-center gap-1.5">
                <code class="text-xs bg-muted px-2 py-0.5 rounded font-mono select-all">
                  {{ k.key.slice(0, 12) }}…
                </code>
                <Button variant="ghost" size="icon-sm" @click="copy(k.key)" title="複製">
                  <Copy class="h-3 w-3" />
                </Button>
              </div>
            </TableCell>
            <TableCell class="text-muted-foreground text-xs">{{ fmtDate(k.created_at) }}</TableCell>
            <TableCell>
              <Badge :variant="k.is_active ? 'success' : 'destructive'">
                {{ k.is_active ? 'Active' : 'Revoked' }}
              </Badge>
            </TableCell>
            <TableCell class="text-right font-mono text-xs">{{ fmtNum(k.total_requests) }}</TableCell>
            <TableCell class="text-right font-mono text-xs">{{ fmtNum(k.total_tokens) }}</TableCell>
            <TableCell class="text-right font-mono text-xs">{{ fmtCost(k.total_cost_usd) }}</TableCell>
            <TableCell>
              <div class="flex items-center justify-center gap-1">
                <Button variant="outline" size="icon-sm" title="查看用量" @click="usageDialog?.open(k)">
                  <BarChart2 class="h-3.5 w-3.5" />
                </Button>
                <Button variant="outline" size="icon-sm" title="編輯" @click="editDialog?.open(k)">
                  <Pencil class="h-3.5 w-3.5" />
                </Button>
                <Button
                  v-if="k.is_active"
                  variant="outline" size="icon-sm"
                  class="text-amber-600 hover:text-amber-700 hover:border-amber-300"
                  title="停用"
                  @click="revokeKey(k)"
                >
                  <Pause class="h-3.5 w-3.5" />
                </Button>
                <Button
                  v-else
                  variant="outline" size="icon-sm"
                  class="text-emerald-600 hover:text-emerald-700 hover:border-emerald-300"
                  title="啟用"
                  @click="activateKey(k)"
                >
                  <Play class="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="outline" size="icon-sm"
                  class="text-destructive hover:text-destructive hover:border-destructive/30"
                  title="永久刪除"
                  @click="deleteKey(k)"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </Card>
  </div>

  <!-- Dialogs -->
  <CreateKeyDialog ref="createDialog" @created="onCreated" />
  <EditKeyDialog ref="editDialog" @updated="onUpdated" />
  <KeyUsageDialog ref="usageDialog" />
</template>
