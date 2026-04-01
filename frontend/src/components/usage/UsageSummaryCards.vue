<script setup lang="ts">
import { Card, CardContent } from '@/components/ui/card'
import { fmtNum, fmtCost } from '@/utils/format'

interface Summary {
  total_requests: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  total_cost: number
}

defineProps<{ summary: Summary }>()

const cards = [
  { label: '總請求數', key: 'total_requests', format: 'num', color: '' },
  { label: '輸入 Tokens', key: 'input_tokens', format: 'num', color: '' },
  { label: '輸出 Tokens', key: 'output_tokens', format: 'num', color: '' },
  { label: '總 Tokens', key: 'total_tokens', format: 'num', color: '' },
  { label: '估算費用 (USD)', key: 'total_cost', format: 'cost', color: 'text-amber-600' },
] as const
</script>

<template>
  <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
    <Card v-for="card in cards" :key="card.key">
      <CardContent class="p-5 text-center">
        <div class="text-3xl font-bold tracking-tight" :class="card.color">
          {{ card.format === 'cost' ? fmtCost(summary[card.key]) : fmtNum(summary[card.key]) }}
        </div>
        <div class="text-xs text-muted-foreground mt-1.5">{{ card.label }}</div>
      </CardContent>
    </Card>
  </div>
</template>
