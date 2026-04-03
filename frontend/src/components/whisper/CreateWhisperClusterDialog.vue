<script setup lang="ts">
import { ref, reactive } from 'vue'
import { api, type WhisperClusterConfig, type WhisperCluster } from '@/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const emit = defineEmits<{
  created: [cluster: WhisperCluster]
  updated: [cluster: WhisperCluster]
}>()

const visible = ref(false)
const submitting = ref(false)
const formError = ref('')
const mode = ref<'create' | 'edit'>('create')
const editingName = ref('')

type FormData = {
  name: string
  executable_path: string
  model_path: string
  n_threads: number | ''
  n_processors: number | ''
  beam_size: number | ''
  best_of: number | ''
  audio_ctx: number | ''
  max_instances: number
  is_default: boolean
}

function defaultForm(): FormData {
  return {
    name: '',
    executable_path: 'C:\\whisper\\whisper-cli.exe',
    model_path: '',
    n_threads: '',
    n_processors: '',
    beam_size: '',
    best_of: '',
    audio_ctx: '',
    max_instances: 2,
    is_default: false,
  }
}

const form = reactive<FormData>(defaultForm())

function open() {
  mode.value = 'create'
  editingName.value = ''
  formError.value = ''
  Object.assign(form, defaultForm())
  visible.value = true
}

function openEdit(cluster: WhisperCluster) {
  mode.value = 'edit'
  editingName.value = cluster.name
  Object.assign(form, {
    name: cluster.name,
    executable_path: cluster.config.executable_path,
    model_path: cluster.config.model_path,
    n_threads: cluster.config.n_threads ?? '',
    n_processors: cluster.config.n_processors ?? '',
    beam_size: cluster.config.beam_size ?? '',
    best_of: cluster.config.best_of ?? '',
    audio_ctx: cluster.config.audio_ctx ?? '',
    max_instances: cluster.config.max_instances,
    is_default: cluster.config.is_default,
  })
  formError.value = ''
  visible.value = true
}

function close() {
  visible.value = false
}

async function submit() {
  if (!form.executable_path.trim()) { formError.value = '執行檔路徑為必填'; return }
  if (!form.model_path.trim()) { formError.value = '模型路徑為必填'; return }

  submitting.value = true
  formError.value = ''

  try {
    if (mode.value === 'create') {
      if (!form.name.trim()) { formError.value = '名稱為必填'; submitting.value = false; return }
      const body: { name: string } & WhisperClusterConfig = {
        name: form.name.trim(),
        executable_path: form.executable_path.trim(),
        model_path: form.model_path.trim(),
        n_threads: form.n_threads === '' ? null : Number(form.n_threads),
        n_processors: form.n_processors === '' ? null : Number(form.n_processors),
        beam_size: form.beam_size === '' ? null : Number(form.beam_size),
        best_of: form.best_of === '' ? null : Number(form.best_of),
        audio_ctx: form.audio_ctx === '' ? null : Number(form.audio_ctx),
        max_instances: form.max_instances,
        is_default: form.is_default,
      }
      const created = await api.createWhisperCluster(body)
      emit('created', created)
      Object.assign(form, defaultForm())
      close()
    } else {
      const patchBody: Partial<WhisperClusterConfig> = {
        executable_path: form.executable_path.trim(),
        model_path: form.model_path.trim(),
        n_threads: form.n_threads === '' ? null : Number(form.n_threads),
        n_processors: form.n_processors === '' ? null : Number(form.n_processors),
        beam_size: form.beam_size === '' ? null : Number(form.beam_size),
        best_of: form.best_of === '' ? null : Number(form.best_of),
        audio_ctx: form.audio_ctx === '' ? null : Number(form.audio_ctx),
        max_instances: form.max_instances,
        is_default: form.is_default,
      }
      const updated = await api.updateWhisperCluster(editingName.value, patchBody)
      emit('updated', updated)
      close()
    }
  } catch (e: unknown) {
    formError.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}

defineExpose({ open, openEdit })
</script>

<template>
  <Dialog :open="visible">
    <DialogContent max-width="max-w-xl" disable-overlay-close @close="close">
      <DialogHeader>
        <DialogTitle>{{ mode === 'edit' ? '編輯 Whisper Cluster' : '新增 Whisper Cluster' }}</DialogTitle>
      </DialogHeader>

      <form class="space-y-5 max-h-[70vh] overflow-y-auto pr-1" @submit.prevent>

        <!-- 基本設定 -->
        <fieldset class="space-y-3">
          <legend class="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">基本設定</legend>

          <div class="space-y-1.5">
            <Label>名稱 <span class="text-destructive">*</span></Label>
            <Input v-model="form.name" placeholder="例如：whisper-base" :disabled="mode === 'edit'" />
            <p v-if="mode === 'edit'" class="text-xs text-muted-foreground">名稱建立後不可修改</p>
          </div>

          <div class="space-y-1.5">
            <Label>執行檔路徑 <span class="text-destructive">*</span></Label>
            <Input v-model="form.executable_path" placeholder="例如：C:\whisper\whisper-cli.exe" />
          </div>

          <div class="space-y-1.5">
            <Label>模型路徑 <span class="text-destructive">*</span></Label>
            <Input v-model="form.model_path" placeholder="例如：C:\models\ggml-base.bin" />
          </div>
        </fieldset>

        <!-- 並發設定 -->
        <fieldset class="space-y-3">
          <legend class="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">並發設定</legend>
          <div class="grid grid-cols-2 gap-3 items-end">
            <div class="space-y-1.5">
              <Label>最大並發數</Label>
              <Input v-model.number="form.max_instances" type="number" min="1" max="32" placeholder="預設 2" />
            </div>
            <div class="flex items-center gap-2 pb-1.5">
              <input
                id="is-default"
                v-model="form.is_default"
                type="checkbox"
                class="h-4 w-4 rounded border-input accent-primary"
              />
              <Label for="is-default" class="cursor-pointer">設為預設 Cluster</Label>
            </div>
          </div>
        </fieldset>

        <!-- 效能參數 -->
        <fieldset class="space-y-3">
          <legend class="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">效能參數</legend>
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <Label>Threads <span class="text-muted-foreground text-xs">（選填）</span></Label>
              <Input v-model="form.n_threads" type="number" placeholder="預設自動" />
            </div>
            <div class="space-y-1.5">
              <Label>Processors <span class="text-muted-foreground text-xs">（選填）</span></Label>
              <Input v-model="form.n_processors" type="number" placeholder="預設 1" />
            </div>
            <div class="space-y-1.5">
              <Label>Beam Size <span class="text-muted-foreground text-xs">（選填）</span></Label>
              <Input v-model="form.beam_size" type="number" placeholder="預設 5" />
            </div>
            <div class="space-y-1.5">
              <Label>Best Of <span class="text-muted-foreground text-xs">（選填）</span></Label>
              <Input v-model="form.best_of" type="number" placeholder="預設 5" />
            </div>
            <div class="space-y-1.5">
              <Label>Audio Context <span class="text-muted-foreground text-xs">（選填）</span></Label>
              <Input v-model="form.audio_ctx" type="number" placeholder="預設 0（最大）" />
            </div>
          </div>
        </fieldset>

        <p v-if="formError" class="text-sm text-destructive">{{ formError }}</p>

        <DialogFooter>
          <Button type="button" variant="outline" @click="close">取消</Button>
          <Button type="button" :disabled="submitting" @click="submit">
            {{ submitting ? (mode === 'edit' ? '儲存中…' : '建立中…') : (mode === 'edit' ? '儲存設定' : '建立 Cluster') }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
