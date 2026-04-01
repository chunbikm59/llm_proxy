<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue'
import { api, type ApiKey } from '@/api'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const emit = defineEmits<{ updated: [key: ApiKey] }>()

const visible = ref(false)
const editingKey = ref<ApiKey | null>(null)
const form = reactive({ name: '', description: '' })
const submitting = ref(false)
const formError = ref('')

function open(k: ApiKey) {
  editingKey.value = k
  form.name = k.name
  form.description = k.description || ''
  formError.value = ''
  visible.value = true
  nextTick(() => (document.getElementById('edit-name-input') as HTMLInputElement)?.focus())
}

function close() {
  visible.value = false
  editingKey.value = null
}

async function submit() {
  if (!form.name.trim()) { formError.value = 'Name 為必填'; return }
  submitting.value = true
  formError.value = ''
  try {
    const updated = await api.updateKey(editingKey.value!.id, form.name.trim(), form.description.trim())
    emit('updated', updated)
    toast.success(`Key「${updated.name}」已更新`)
    close()
  } catch (e: unknown) {
    formError.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}

defineExpose({ open })
</script>

<template>
  <Dialog :open="visible">
    <DialogContent max-width="max-w-md" @close="close">
      <DialogHeader>
        <DialogTitle>編輯 API Key</DialogTitle>
      </DialogHeader>
      <form class="space-y-4" @submit.prevent="submit">
        <div class="space-y-1.5">
          <Label for="edit-name-input">
            Name <span class="text-destructive">*</span>
          </Label>
          <Input id="edit-name-input" v-model="form.name" placeholder="Key 名稱" />
        </div>
        <div class="space-y-1.5">
          <Label>Description</Label>
          <Input v-model="form.description" placeholder="選填說明" />
        </div>
        <p v-if="formError" class="text-sm text-destructive">{{ formError }}</p>
        <DialogFooter>
          <Button type="button" variant="outline" @click="close">取消</Button>
          <Button type="submit" :disabled="submitting">
            {{ submitting ? '保存中…' : '保存' }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
