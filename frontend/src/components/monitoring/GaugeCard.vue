<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GaugeChart } from 'echarts/charts'
import { Card, CardContent } from '@/components/ui/card'

use([CanvasRenderer, GaugeChart])

interface Props {
  title: string
  subtitle?: string
  percent: number
  color: string
}

const props = defineProps<Props>()

const gaugeOption = computed(() => ({
  series: [{
    type: 'gauge',
    startAngle: 200,
    endAngle: -20,
    min: 0,
    max: 100,
    radius: '85%',
    axisLine: {
      lineStyle: { width: 12, color: [[1, '#e5e7eb']] },
    },
    progress: {
      show: true,
      width: 12,
      itemStyle: { color: props.color },
    },
    pointer: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { show: false },
    detail: {
      valueAnimation: true,
      formatter: '{value}%',
      color: '#1f2937',
      fontSize: 18,
      fontWeight: 'bold',
      offsetCenter: [0, '10%'],
    },
    data: [{ value: props.percent }],
  }],
}))
</script>

<template>
  <Card>
    <CardContent class="p-5">
      <div class="flex items-center gap-2 mb-1">
        <slot name="icon" />
        <span class="font-medium text-sm">{{ title }}</span>
        <span v-if="subtitle" class="ml-auto text-xs text-muted-foreground shrink-0">{{ subtitle }}</span>
      </div>
      <VChart :option="gaugeOption" autoresize style="height: 160px; width: 100%" />
    </CardContent>
  </Card>
</template>
