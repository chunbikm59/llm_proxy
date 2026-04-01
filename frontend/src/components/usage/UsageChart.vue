<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import type { UsageRow } from '@/api'
import type { Rates } from '@/utils/modelUtils'
import { getModelType, calcCost } from '@/utils/modelUtils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

type GroupBy = 'type' | 'key' | 'model'

interface Props {
  filtered: UsageRow[]
  groupBy: GroupBy
  rates: Rates
  dates: { start: string; end: string }
}

const props = defineProps<Props>()
const emit = defineEmits<{ 'update:groupBy': [v: GroupBy] }>()

const CHART_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#f97316', '#84cc16', '#ec4899', '#6366f1',
]

const chartOption = computed(() => {
  const start = new Date(props.dates.start)
  const end = new Date(props.dates.end)
  const dates: string[] = []
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    dates.push(d.toISOString().slice(0, 10))
  }

  function getGroup(r: UsageRow) {
    if (props.groupBy === 'type') return getModelType(r.model) === 'embedding' ? 'Embedding' : 'Chat'
    if (props.groupBy === 'key') return r.key_name || `Key ${r.key_id}`
    return r.model || 'unknown'
  }

  const groups = [...new Set(props.filtered.map(r => getGroup(r)))].sort()
  const data: Record<string, Record<string, number>> = {}
  for (const g of groups) data[g] = {}
  for (const r of props.filtered) {
    const g = getGroup(r)
    const cost = calcCost(r, props.rates)
    data[g][r.date] = (data[g][r.date] || 0) + cost
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(params: { axisValue: string; marker: string; seriesName: string; value: number }[]) {
        const date = params[0].axisValue
        let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`
        let total = 0
        for (const p of params) {
          if (p.value > 0) {
            html += `<div>${p.marker}${p.seriesName}: $${p.value.toFixed(6)}</div>`
            total += p.value
          }
        }
        html += `<div style="margin-top:4px;font-weight:600;border-top:1px solid #e5e7eb;padding-top:4px">合計: $${total.toFixed(6)}</div>`
        return html
      },
    },
    legend: { top: 0, data: groups, textStyle: { fontSize: 12 } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '40px', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: dates.length > 14 ? 45 : 0,
        fontSize: 11,
        formatter: (v: string) => dates.length > 30 ? v.slice(5) : v,
      },
    },
    yAxis: {
      type: 'value',
      name: 'USD',
      axisLabel: { formatter: (v: number) => `$${v}` },
    },
    series: groups.map((g, i) => ({
      name: g,
      type: 'bar',
      stack: 'total',
      emphasis: { focus: 'series' },
      itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] },
      data: dates.map(d => +((data[g][d] || 0).toFixed(6))),
    })),
  }
})

const groupButtons: { v: GroupBy; l: string }[] = [
  { v: 'type', l: '按類型' },
  { v: 'key', l: '按 Key' },
  { v: 'model', l: '按模型' },
]
</script>

<template>
  <Card>
    <CardHeader class="pb-4">
      <div class="flex items-center justify-between">
        <CardTitle class="text-base">每日費用趨勢</CardTitle>
        <div class="flex border rounded-lg overflow-hidden">
          <Button
            v-for="g in groupButtons"
            :key="g.v"
            :variant="groupBy === g.v ? 'default' : 'ghost'"
            size="sm"
            class="rounded-none h-7 text-xs px-3"
            @click="emit('update:groupBy', g.v)"
          >
            {{ g.l }}
          </Button>
        </div>
      </div>
    </CardHeader>
    <CardContent class="pt-0">
      <VChart :option="chartOption" autoresize style="height: 300px; width: 100%" />
    </CardContent>
  </Card>
</template>
