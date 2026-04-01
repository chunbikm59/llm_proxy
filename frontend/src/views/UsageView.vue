<script setup lang="ts">
import { ref, computed, watch, onMounted, type Ref } from 'vue'
import { type ApiKey } from '@/api'
import { type Rates, getModelType, calcCost } from '@/utils/modelUtils'
import { fmtNum, fmtCost } from '@/utils/format'
import { useUsageData } from '@/composables/useUsageData'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import MultiSelect from '@/components/usage/MultiSelect.vue'
import UsageSummaryCards from '@/components/usage/UsageSummaryCards.vue'
import UsageChart from '@/components/usage/UsageChart.vue'
import RatesPanel from '@/components/usage/RatesPanel.vue'
import { Settings2, RefreshCw, Inbox } from 'lucide-vue-next'

interface Props {
  allKeys: Ref<ApiKey[]>
  rates: Rates
  resetRates: () => void
}

const props = defineProps<Props>()

const showRates = ref(false)
const groupBy = ref<'type' | 'key' | 'model'>('type')

const usageData = useUsageData(props.rates)
const { dates, filterKeys, filterType, filterModels, loading, fetchAll, availableModels, filtered, summary } = usageData

const keyOptions = computed(() => props.allKeys.value.map(k => ({ value: k.id, label: k.name })))
const modelOptions = computed(() => availableModels.value.map(m => ({ value: m, label: m })))

const filterTypeOptions = [
  { value: 'chat', label: 'Chat' },
  { value: 'embedding', label: 'Embedding' },
]

onMounted(async () => {
  await fetchAll()
})

watch([() => dates.start, () => dates.end], () => {
  fetchAll()
})
</script>

<template>
  <div class="p-6 space-y-5">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h2 class="text-xl font-semibold tracking-tight">用量分析</h2>
        <p class="text-sm text-muted-foreground mt-0.5">依日期、Key、模型分析 Token 用量與費用估算</p>
      </div>
      <div class="flex gap-2">
        <Button variant="outline" size="sm" @click="showRates = !showRates">
          <Settings2 class="h-4 w-4" />
          費率設定
        </Button>
        <Button variant="outline" size="sm" :disabled="loading" @click="fetchAll">
          <RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin' : ''" />
          重新整理
        </Button>
      </div>
    </div>

    <!-- 費率設定 -->
    <RatesPanel v-if="showRates" :rates="rates" @reset="resetRates" />

    <!-- 篩選列 -->
    <Card>
      <CardContent class="p-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">日期範圍</label>
            <div class="flex items-center gap-2">
              <input type="date" v-model="dates.start"
                class="flex h-9 flex-1 rounded-md border border-input bg-transparent px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
              <span class="text-muted-foreground text-xs shrink-0">～</span>
              <input type="date" v-model="dates.end"
                class="flex h-9 flex-1 rounded-md border border-input bg-transparent px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
            </div>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">API Key</label>
            <MultiSelect v-model="filterKeys" :options="keyOptions" placeholder="全部 Key" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">類型</label>
            <select v-model="filterType"
              class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
              <option value="">全部類型</option>
              <option v-for="o in filterTypeOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-medium text-muted-foreground">模型</label>
            <MultiSelect v-model="filterModels" :options="modelOptions" placeholder="全部模型" />
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- 統計卡片 -->
    <UsageSummaryCards :summary="summary" />

    <!-- ECharts 圖表 -->
    <UsageChart
      :filtered="filtered"
      :group-by="groupBy"
      :rates="rates"
      :dates="dates"
      @update:group-by="groupBy = $event"
    />

    <!-- 明細表格 -->
    <Card>
      <CardHeader class="pb-3">
        <CardTitle class="text-base">
          明細記錄
          <span class="ml-2 text-sm font-normal text-muted-foreground">（{{ filtered.length }} 筆）</span>
        </CardTitle>
      </CardHeader>
      <CardContent class="pt-0">
        <div v-if="!filtered.length" class="py-12 flex flex-col items-center gap-2 text-muted-foreground">
          <Inbox class="h-10 w-10 opacity-30" />
          <span class="text-sm">無符合條件的記錄</span>
        </div>

        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead>日期</TableHead>
              <TableHead>模型</TableHead>
              <TableHead>類型</TableHead>
              <TableHead>Key</TableHead>
              <TableHead class="text-right">Input</TableHead>
              <TableHead class="text-right">Output</TableHead>
              <TableHead class="text-right">Total</TableHead>
              <TableHead class="text-right">Requests</TableHead>
              <TableHead class="text-right">估算費用</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="(r, i) in filtered" :key="i">
              <TableCell class="font-mono text-xs">{{ r.date }}</TableCell>
              <TableCell class="text-xs text-muted-foreground">{{ r.model }}</TableCell>
              <TableCell>
                <Badge :variant="getModelType(r.model) === 'chat' ? 'info' : 'secondary'" class="text-xs">
                  {{ getModelType(r.model) === 'chat' ? 'Chat' : 'Embed' }}
                </Badge>
              </TableCell>
              <TableCell class="text-xs">{{ r.key_name }}</TableCell>
              <TableCell class="text-right font-mono text-xs">{{ fmtNum(r.input_tokens) }}</TableCell>
              <TableCell class="text-right font-mono text-xs">{{ fmtNum(r.output_tokens) }}</TableCell>
              <TableCell class="text-right font-mono text-xs">{{ fmtNum(r.total_tokens) }}</TableCell>
              <TableCell class="text-right font-mono text-xs">{{ r.requests || 1 }}</TableCell>
              <TableCell class="text-right font-mono text-xs text-amber-600">
                {{ fmtCost(calcCost(r, rates)) }}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </div>
</template>
