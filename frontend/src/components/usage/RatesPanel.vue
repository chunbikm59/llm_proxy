<script setup lang="ts">
import type { Rates } from '@/utils/modelUtils'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

defineProps<{ rates: Rates }>()
const emit = defineEmits<{ reset: [] }>()
</script>

<template>
  <Card class="border-blue-200 bg-blue-50/50">
    <CardContent class="p-4">
      <div class="flex items-center justify-between mb-4">
        <span class="font-semibold text-sm">費率設定（USD / 1M tokens）</span>
        <Button variant="ghost" size="sm" class="text-primary h-7 text-xs" @click="emit('reset')">
          恢復預設
        </Button>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div class="space-y-1.5">
          <Label class="text-xs text-muted-foreground">Chat Input</Label>
          <div class="flex items-center gap-1.5">
            <span class="text-muted-foreground text-sm">$</span>
            <Input type="number" :model-value="rates.chat_input" min="0" step="0.01"
              @update:model-value="rates.chat_input = Number($event)" />
          </div>
        </div>
        <div class="space-y-1.5">
          <Label class="text-xs text-muted-foreground">Chat Output</Label>
          <div class="flex items-center gap-1.5">
            <span class="text-muted-foreground text-sm">$</span>
            <Input type="number" :model-value="rates.chat_output" min="0" step="0.01"
              @update:model-value="rates.chat_output = Number($event)" />
          </div>
        </div>
        <div class="space-y-1.5">
          <Label class="text-xs text-muted-foreground">Embedding Input</Label>
          <div class="flex items-center gap-1.5">
            <span class="text-muted-foreground text-sm">$</span>
            <Input type="number" :model-value="rates.embed_input" min="0" step="0.01"
              @update:model-value="rates.embed_input = Number($event)" />
          </div>
        </div>
        <div class="space-y-1.5">
          <Label class="text-xs text-muted-foreground">Audio（/ min）</Label>
          <div class="flex items-center gap-1.5">
            <span class="text-muted-foreground text-sm">$</span>
            <Input type="number" :model-value="rates.audio_per_minute" min="0" step="0.001"
              @update:model-value="rates.audio_per_minute = Number($event)" />
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>
