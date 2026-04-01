<script setup lang="ts">
import { KeyRound, ChartColumnBig, Activity } from 'lucide-vue-next'
import { Separator } from '@/components/ui/separator'

type Page = 'keys' | 'usage' | 'monitor'

interface Props { currentPage: Page }
defineProps<Props>()
const emit = defineEmits<{ navigate: [page: Page] }>()

const navItems: { id: Page; label: string; icon: typeof KeyRound }[] = [
  { id: 'keys', label: 'API Key 管理', icon: KeyRound },
  { id: 'usage', label: '用量分析', icon: ChartColumnBig },
  { id: 'monitor', label: '系統監控', icon: Activity },
]
</script>

<template>
  <aside class="w-56 shrink-0 flex flex-col border-r" style="background: hsl(240 5.9% 10%); color: hsl(0 0% 98%);">
    <!-- Logo -->
    <div class="px-5 py-5">
      <h1 class="font-bold text-base leading-tight" style="color: hsl(0 0% 98%)">LLM Proxy</h1>
      <p class="text-xs mt-0.5" style="color: hsl(0 0% 60%)">管理後台</p>
    </div>

    <Separator style="background: hsl(0 0% 98% / 0.1)" />

    <!-- Nav -->
    <nav class="flex-1 py-3 px-3 space-y-1">
      <button
        v-for="item in navItems"
        :key="item.id"
        class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left"
        :style="currentPage === item.id
          ? 'background: hsl(0 0% 98% / 0.12); color: hsl(0 0% 98%)'
          : 'color: hsl(0 0% 70%)'"
        @click="emit('navigate', item.id)"
        @mouseenter="($event.currentTarget as HTMLElement).style.cssText = currentPage === item.id ? 'background: hsl(0 0% 98% / 0.12); color: hsl(0 0% 98%)' : 'background: hsl(0 0% 98% / 0.07); color: hsl(0 0% 90%)'"
        @mouseleave="($event.currentTarget as HTMLElement).style.cssText = currentPage === item.id ? 'background: hsl(0 0% 98% / 0.12); color: hsl(0 0% 98%)' : 'color: hsl(0 0% 70%)'"
      >
        <component :is="item.icon" class="h-4 w-4 shrink-0" />
        {{ item.label }}
      </button>
    </nav>

    <Separator style="background: hsl(0 0% 98% / 0.1)" />

    <div class="px-5 py-3">
      <p class="text-xs" style="color: hsl(0 0% 40%)">
        {{ new Date().toLocaleDateString('zh-TW') }}
      </p>
    </div>
  </aside>
</template>
