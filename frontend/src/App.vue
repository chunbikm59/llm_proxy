<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Toaster } from 'sonner'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import KeysView from '@/views/KeysView.vue'
import UsageView from '@/views/UsageView.vue'
import MonitoringView from '@/views/MonitoringView.vue'
import LlamaView from '@/views/LlamaView.vue'
import WhisperView from '@/views/WhisperView.vue'
import { AlertDialog } from '@/components/ui/alert-dialog'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useKeys } from '@/composables/useKeys'
import { useRates } from '@/composables/useRates'

type Page = 'keys' | 'usage' | 'monitor' | 'llama' | 'whisper'

const currentPage = ref<Page>('keys')
const { visible, title, description, onConfirm, onCancel } = useConfirmDialog()
const keysState = useKeys()
const { rates, reset: resetRates } = useRates()

onMounted(() => keysState.fetchKeys())
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-muted/30">
    <AppSidebar :current-page="currentPage" @navigate="currentPage = $event" />

    <main class="flex-1 overflow-y-auto">
      <KeysView
        v-if="currentPage === 'keys'"
        :keys-state="keysState"
      />
      <UsageView
        v-else-if="currentPage === 'usage'"
        :all-keys="keysState.keys"
        :rates="rates"
        :reset-rates="resetRates"
      />
      <MonitoringView v-else-if="currentPage === 'monitor'" />
      <LlamaView v-else-if="currentPage === 'llama'" />
      <WhisperView v-else-if="currentPage === 'whisper'" />
    </main>
  </div>

  <!-- 全域確認 Dialog -->
  <AlertDialog
    :open="visible"
    :title="title"
    :description="description"
    confirm-label="確認刪除"
    @confirm="onConfirm"
    @cancel="onCancel"
  />

  <!-- Toast 通知 -->
  <Toaster position="top-right" :duration="3000" rich-colors />
</template>
