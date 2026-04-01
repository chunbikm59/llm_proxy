<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue'
import { api, type ApiKey } from '@/api'
import { copyText } from '@/utils/clipboard'
import { Dialog } from '@/components/ui/dialog'
import { DialogContent } from '@/components/ui/dialog'
import { DialogHeader } from '@/components/ui/dialog'
import { DialogTitle } from '@/components/ui/dialog'
import { DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Copy, Check, PartyPopper } from 'lucide-vue-next'

const emit = defineEmits<{ created: [key: ApiKey] }>()

const visible = ref(false)
const form = reactive({ name: '', description: '' })
const submitting = ref(false)
const formError = ref('')
const createdKey = ref<ApiKey | null>(null)
const copied = ref(false)

function open() {
  form.name = ''
  form.description = ''
  formError.value = ''
  createdKey.value = null
  visible.value = true
  nextTick(() => (document.getElementById('create-name-input') as HTMLInputElement)?.focus())
}

function close() {
  visible.value = false
  createdKey.value = null
}

async function submit() {
  if (!form.name.trim()) { formError.value = 'Name 為必填'; return }
  submitting.value = true
  formError.value = ''
  try {
    const newKey = await api.createKey(form.name.trim(), form.description.trim())
    createdKey.value = newKey
    emit('created', newKey)
  } catch (e: unknown) {
    formError.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}

async function copyKey() {
  if (!createdKey.value) return
  await copyText(createdKey.value.key)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

defineExpose({ open })
</script>

<template>
  <Dialog :open="visible">
    <DialogContent max-width="max-w-md" @close="close">
      <!-- 建立成功 -->
      <template v-if="createdKey">
        <div class="flex flex-col items-center text-center gap-3 py-2">
          <div class="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
            <PartyPopper class="h-7 w-7 text-emerald-600" />
          </div>
          <div>
            <h3 class="text-lg font-semibold">Key 建立成功</h3>
            <p class="text-sm text-muted-foreground mt-1">請立即複製，此 Key 不會再次完整顯示</p>
          </div>
        </div>
        <div class="flex items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2.5">
          <code class="flex-1 text-xs font-mono break-all text-foreground/80">{{ createdKey.key }}</code>
          <Button variant="ghost" size="icon-sm" @click="copyKey">
            <Check v-if="copied" class="h-3.5 w-3.5 text-emerald-600" />
            <Copy v-else class="h-3.5 w-3.5" />
          </Button>
        </div>
        <DialogFooter>
          <Button class="w-full" @click="close">完成</Button>
        </DialogFooter>
      </template>

      <!-- 建立表單 -->
      <template v-else>
        <DialogHeader>
          <DialogTitle>建立新 API Key</DialogTitle>
        </DialogHeader>
        <form class="space-y-4" @submit.prevent="submit">
          <div class="space-y-1.5">
            <Label for="create-name-input">
              Name <span class="text-destructive">*</span>
            </Label>
            <Input
              id="create-name-input"
              v-model="form.name"
              placeholder="例如：team-a、john-dev"
            />
          </div>
          <div class="space-y-1.5">
            <Label>Description</Label>
            <Input v-model="form.description" placeholder="選填說明" />
          </div>
          <p v-if="formError" class="text-sm text-destructive">{{ formError }}</p>
          <DialogFooter>
            <Button type="button" variant="outline" @click="close">取消</Button>
            <Button type="submit" :disabled="submitting">
              {{ submitting ? '建立中…' : '建立' }}
            </Button>
          </DialogFooter>
        </form>
      </template>
    </DialogContent>
  </Dialog>
</template>
