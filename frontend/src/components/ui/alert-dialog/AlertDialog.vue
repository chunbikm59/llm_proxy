<script setup lang="ts">
import { TriangleAlert } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

interface Props {
  open: boolean
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  confirmVariant?: 'default' | 'destructive'
}

const props = withDefaults(defineProps<Props>(), {
  confirmLabel: '確認',
  cancelLabel: '取消',
  confirmVariant: 'destructive',
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
      @click.self="emit('cancel')"
    >
      <div class="w-full max-w-sm bg-white rounded-xl border shadow-lg p-6 flex flex-col gap-4">
        <div class="flex flex-col items-center text-center gap-3">
          <div class="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
            <TriangleAlert class="h-6 w-6 text-destructive" />
          </div>
          <div>
            <h3 class="font-semibold text-lg">{{ title }}</h3>
            <p v-if="description" class="text-sm text-muted-foreground mt-1">{{ description }}</p>
          </div>
        </div>
        <div class="flex gap-2 justify-end">
          <Button variant="outline" @click="emit('cancel')">{{ cancelLabel }}</Button>
          <Button :variant="confirmVariant" @click="emit('confirm')">{{ confirmLabel }}</Button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
