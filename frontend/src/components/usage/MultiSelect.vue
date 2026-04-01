<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronDown, X } from 'lucide-vue-next'

interface Option { value: string | number; label: string }

interface Props {
  modelValue: (string | number)[]
  options: Option[]
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), { placeholder: '全部' })
const emit = defineEmits<{ 'update:modelValue': [v: (string | number)[]] }>()

const open = ref(false)

function toggle(v: string | number) {
  const cur = [...props.modelValue]
  const idx = cur.indexOf(v)
  if (idx >= 0) cur.splice(idx, 1)
  else cur.push(v)
  emit('update:modelValue', cur)
}

function clear() { emit('update:modelValue', []) }

const displayText = computed(() => {
  if (!props.modelValue.length) return props.placeholder
  if (props.modelValue.length === 1) {
    const opt = props.options.find(o => o.value === props.modelValue[0])
    return opt ? opt.label : String(props.modelValue[0])
  }
  return `已選 ${props.modelValue.length} 項`
})
</script>

<template>
  <div class="relative">
    <button
      type="button"
      class="flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      @click="open = !open"
    >
      <span :class="modelValue.length ? '' : 'text-muted-foreground'">{{ displayText }}</span>
      <ChevronDown class="h-4 w-4 opacity-50 shrink-0" />
    </button>

    <div
      v-if="open"
      class="absolute z-30 mt-1 w-full bg-popover border rounded-md shadow-lg max-h-48 overflow-y-auto"
    >
      <button
        v-if="modelValue.length"
        type="button"
        class="w-full flex items-center gap-1.5 px-3 py-2 text-xs text-primary hover:bg-muted border-b"
        @click="clear"
      >
        <X class="h-3 w-3" /> 清除選擇
      </button>
      <div v-if="!options.length" class="px-3 py-2 text-sm text-muted-foreground text-center">無選項</div>
      <button
        v-for="opt in options"
        :key="opt.value"
        type="button"
        class="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted text-left"
        @click="toggle(opt.value)"
      >
        <span :class="modelValue.includes(opt.value) ? 'text-primary font-bold' : 'text-muted-foreground'">✓</span>
        <span :class="modelValue.includes(opt.value) ? 'font-medium' : 'text-muted-foreground'">{{ opt.label }}</span>
      </button>
    </div>

    <!-- 點外側關閉 -->
    <div v-if="open" class="fixed inset-0 z-20" @click="open = false" />
  </div>
</template>
