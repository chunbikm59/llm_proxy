<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api, type SystemStats } from '@/api'
import GaugeCard from '@/components/monitoring/GaugeCard.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Cpu, MemoryStick, Zap, Layers, MonitorOff, RefreshCw, AlertCircle } from 'lucide-vue-next'

const stats = ref<SystemStats | null>(null)
const loading = ref(false)
const error = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchStats() {
  loading.value = true
  error.value = ''
  try {
    stats.value = await api.getSystemStats()
  } catch (e: unknown) {
    error.value = (e as Error).message || '無法取得系統資源資料'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchStats()
  pollTimer = setInterval(fetchStats, 4000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="p-6 max-w-4xl space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold tracking-tight">系統資源監控</h2>
        <p class="text-xs text-muted-foreground mt-0.5">每 4 秒自動更新</p>
      </div>
      <Button variant="outline" size="sm" :disabled="loading" @click="fetchStats">
        <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
        刷新
      </Button>
    </div>

    <!-- Error -->
    <div v-if="error" class="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      <AlertCircle class="h-4 w-4 shrink-0" />
      {{ error }}
    </div>

    <!-- 初次載入 -->
    <div v-if="!stats && loading" class="flex justify-center py-16">
      <RefreshCw class="h-6 w-6 animate-spin text-muted-foreground" />
    </div>

    <!-- 主內容 -->
    <template v-else-if="stats">
      <!-- Section: 系統 -->
      <section class="space-y-3">
        <h3 class="text-xs font-medium text-muted-foreground uppercase tracking-widest">系統</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <GaugeCard
            title="CPU 使用率"
            :subtitle="`${stats.cpu.count_physical}C / ${stats.cpu.count_logical}T`"
            :percent="stats.cpu.percent"
            color="#3b82f6"
          >
            <template #icon><Cpu class="h-4 w-4 text-blue-500" /></template>
          </GaugeCard>

          <GaugeCard
            title="記憶體（RAM）"
            :subtitle="`${stats.ram.used_gb} / ${stats.ram.total_gb} GB`"
            :percent="stats.ram.percent"
            color="#10b981"
          >
            <template #icon><MemoryStick class="h-4 w-4 text-emerald-500" /></template>
          </GaugeCard>
        </div>
      </section>

      <!-- Section: GPU -->
      <section class="space-y-3">
        <h3 class="text-xs font-medium text-muted-foreground uppercase tracking-widest">GPU</h3>

        <template v-if="stats.gpu_available">
          <div v-for="g in stats.gpu" :key="g.index" class="space-y-3">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <GaugeCard
                :title="g.name"
                :subtitle="g.temperature_c !== null ? `${g.temperature_c}°C` : undefined"
                :percent="g.util_percent"
                color="#f59e0b"
              >
                <template #icon><Zap class="h-4 w-4 text-amber-500" /></template>
              </GaugeCard>

              <GaugeCard
                title="VRAM"
                :subtitle="`${g.vram_used_gb} / ${g.vram_total_gb} GB`"
                :percent="g.vram_percent"
                color="#8b5cf6"
              >
                <template #icon><Layers class="h-4 w-4 text-violet-500" /></template>
              </GaugeCard>
            </div>
          </div>
        </template>

        <!-- 無 GPU -->
        <Card v-else>
          <CardContent class="py-8 flex flex-col items-center gap-2 text-muted-foreground">
            <MonitorOff class="h-8 w-8 opacity-25" />
            <p class="text-sm">未偵測到 NVIDIA GPU</p>
          </CardContent>
        </Card>
      </section>

      <p class="text-xs text-muted-foreground">最後更新：{{ stats.timestamp }}</p>
    </template>
  </div>
</template>
