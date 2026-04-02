<script setup lang="ts">
import { cn } from '@/lib/utils'
import { X } from 'lucide-vue-next'

interface Props {
  class?: string
  hideClose?: boolean
  maxWidth?: string
  disableOverlayClose?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  maxWidth: 'max-w-lg',
  disableOverlayClose: false,
})
const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <!-- Overlay -->
  <div
    class="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
    @click.self="!props.disableOverlayClose && emit('close')"
  >
    <!-- Content -->
    <div
      :class="cn(
        'relative w-full bg-white rounded-xl border shadow-lg p-6 flex flex-col gap-4 max-h-[90vh] overflow-y-auto',
        props.maxWidth,
        props.class
      )"
    >
      <button
        v-if="!hideClose"
        class="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100 transition-opacity focus:outline-none"
        @click="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
      <slot />
    </div>
  </div>
</template>
