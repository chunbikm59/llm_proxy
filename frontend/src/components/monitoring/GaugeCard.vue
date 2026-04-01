<script setup lang="ts">
import { computed } from 'vue'
import { Card, CardContent } from '@/components/ui/card'

interface Props {
  title: string
  subtitle?: string
  percent: number
  color: string
}

const props = defineProps<Props>()

const statusColor = computed(() => {
  if (props.percent >= 90) return { text: 'text-red-500', bar: 'bg-red-500' }
  if (props.percent >= 70) return { text: 'text-amber-500', bar: 'bg-amber-500' }
  return { text: '', bar: '' }
})

const barStyle = computed(() => ({
  width: `${props.percent}%`,
  backgroundColor: props.color,
  transition: 'width 0.6s ease',
}))
</script>

<template>
  <Card>
    <CardContent class="p-5">
      <!-- Header row -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <slot name="icon" />
          <span class="text-sm font-medium text-foreground">{{ title }}</span>
        </div>
        <span v-if="subtitle" class="text-xs text-muted-foreground">{{ subtitle }}</span>
      </div>

      <!-- Big number -->
      <div class="mb-3">
        <span
          class="text-4xl font-bold tabular-nums leading-none"
          :class="statusColor.text || 'text-foreground'"
        >{{ percent }}</span>
        <span class="text-lg font-medium text-muted-foreground ml-1">%</span>
      </div>

      <!-- Progress bar -->
      <div class="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div class="h-full rounded-full" :style="barStyle" />
      </div>
    </CardContent>
  </Card>
</template>
