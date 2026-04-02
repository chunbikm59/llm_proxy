<script setup lang="ts">
import { ref, reactive } from 'vue'
import { api, type LlamaInstanceConfig, type LlamaInstance } from '@/api'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'

const emit = defineEmits<{
  created: [instance: LlamaInstance]
  updated: [instance: LlamaInstance]
}>()

const visible = ref(false)
const submitting = ref(false)
const formError = ref('')
const showAdvanced = ref(false)
const mode = ref<'create' | 'edit'>('create')
const editingName = ref('')
const restartOnSave = ref(false)

type FormData = { name: string } & {
  executable_path: string
  model_path: string
  host: string
  port: number | ''
  context_size: number
  n_threads: number | ''
  n_gpu_layers: number
  parallel: number
  batch_size: number
  split_mode: string
  defrag_thold: number | ''
  cache_type_k: string
  cache_type_v: string
  flash_attn: boolean
  cont_batching: boolean
  no_webui: boolean
  auto_start: boolean
  auto_restart: boolean
  max_restart_attempts: number
  startup_timeout: number
}

function defaultForm(): FormData {
  return {
    name: '',
    executable_path: 'C:\\llama\\llama-server.exe',
    model_path: '',
    host: '127.0.0.1',
    port: '',
    context_size: 4096,
    n_threads: '',
    n_gpu_layers: 0,
    parallel: 1,
    batch_size: 512,
    split_mode: '',
    defrag_thold: '',
    cache_type_k: '',
    cache_type_v: '',
    flash_attn: false,
    cont_batching: false,
    no_webui: true,
    auto_start: true,
    auto_restart: false,
    max_restart_attempts: 3,
    startup_timeout: 120,
  }
}

const form = reactive<FormData>(defaultForm())

function open() {
  mode.value = 'create'
  editingName.value = ''
  formError.value = ''
  showAdvanced.value = false
  visible.value = true
  // 不重設表單，保留上次輸入內容；只有成功提交後才重設
}

function openEdit(instance: LlamaInstance) {
  mode.value = 'edit'
  editingName.value = instance.name
  Object.assign(form, {
    name: instance.name,
    executable_path: instance.config.executable_path,
    model_path: instance.config.model_path,
    host: instance.config.host,
    port: instance.config.port,
    context_size: instance.config.context_size,
    n_threads: instance.config.n_threads ?? '',
    n_gpu_layers: instance.config.n_gpu_layers,
    parallel: instance.config.parallel,
    batch_size: instance.config.batch_size,
    split_mode: instance.config.split_mode ?? '',
    defrag_thold: instance.config.defrag_thold ?? '',
    cache_type_k: instance.config.cache_type_k ?? '',
    cache_type_v: instance.config.cache_type_v ?? '',
    flash_attn: instance.config.flash_attn,
    cont_batching: instance.config.cont_batching,
    no_webui: instance.config.no_webui,
    auto_start: instance.config.auto_start,
    auto_restart: instance.config.auto_restart,
    max_restart_attempts: instance.config.max_restart_attempts,
    startup_timeout: instance.config.startup_timeout,
  })
  formError.value = ''
  showAdvanced.value = false
  visible.value = true
}

function close() {
  visible.value = false
}

async function submit() {
  if (!form.executable_path.trim()) { formError.value = '執行檔路徑為必填'; return }
  if (!form.model_path.trim()) { formError.value = '模型路徑為必填'; return }
  if (!form.port) { formError.value = 'Port 為必填'; return }

  submitting.value = true
  formError.value = ''

  try {
    if (mode.value === 'create') {
      if (!form.name.trim()) { formError.value = '名稱為必填'; submitting.value = false; return }
      const body: { name: string } & LlamaInstanceConfig = {
        name: form.name.trim(),
        executable_path: form.executable_path.trim(),
        model_path: form.model_path.trim(),
        host: form.host.trim() || '127.0.0.1',
        port: Number(form.port),
        context_size: form.context_size,
        n_threads: form.n_threads === '' ? null : Number(form.n_threads),
        n_gpu_layers: form.n_gpu_layers,
        parallel: form.parallel,
        batch_size: form.batch_size,
        split_mode: form.split_mode || null,
        defrag_thold: form.defrag_thold === '' ? null : Number(form.defrag_thold),
        cache_type_k: form.cache_type_k || null,
        cache_type_v: form.cache_type_v || null,
        flash_attn: form.flash_attn,
        cont_batching: form.cont_batching,
        no_webui: form.no_webui,
        extra_args: [],
        auto_start: form.auto_start,
        auto_restart: form.auto_restart,
        max_restart_attempts: form.max_restart_attempts,
        startup_timeout: form.startup_timeout,
      }
      const created = await api.createLlamaInstance(body)
      emit('created', created)
      Object.assign(form, defaultForm())  // 成功後重設
      close()
    } else {
      const patchBody: Partial<LlamaInstanceConfig> = {
        executable_path: form.executable_path.trim(),
        model_path: form.model_path.trim(),
        host: form.host.trim() || '127.0.0.1',
        port: Number(form.port),
        context_size: form.context_size,
        n_threads: form.n_threads === '' ? null : Number(form.n_threads),
        n_gpu_layers: form.n_gpu_layers,
        parallel: form.parallel,
        batch_size: form.batch_size,
        split_mode: form.split_mode || null,
        defrag_thold: form.defrag_thold === '' ? null : Number(form.defrag_thold),
        cache_type_k: form.cache_type_k || null,
        cache_type_v: form.cache_type_v || null,
        flash_attn: form.flash_attn,
        cont_batching: form.cont_batching,
        no_webui: form.no_webui,
        auto_start: form.auto_start,
        auto_restart: form.auto_restart,
        max_restart_attempts: form.max_restart_attempts,
        startup_timeout: form.startup_timeout,
      }
      const updated = await api.updateLlamaInstance(editingName.value, patchBody, restartOnSave.value)
      emit('updated', updated)
      close()
    }
  } catch (e: unknown) {
    formError.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}

function submitSave() {
  restartOnSave.value = false
  submit()
}

function submitSaveAndRestart() {
  restartOnSave.value = true
  submit()
}

defineExpose({ open, openEdit })

const splitModeOptions = [
  { value: 'layer', label: 'layer' },
  { value: 'row', label: 'row' },
]
const cacheTypeOptions = [
  { value: 'f16', label: 'f16' },
  { value: 'q8_0', label: 'q8_0' },
  { value: 'q4_0', label: 'q4_0' },
]
</script>

<template>
  <Dialog :open="visible">
    <DialogContent max-width="max-w-2xl" disable-overlay-close @close="close">
      <DialogHeader>
        <DialogTitle>{{ mode === 'edit' ? '編輯 llama.cpp 實例' : '新增 llama.cpp 實例' }}</DialogTitle>
      </DialogHeader>

      <form class="space-y-5 max-h-[70vh] overflow-y-auto pr-1" @submit.prevent="mode === 'create' ? submit() : undefined">

        <!-- 基本設定 -->
        <fieldset class="space-y-3">
          <legend class="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">基本設定</legend>

          <div class="space-y-1.5">
            <Label>名稱 <span class="text-destructive">*</span></Label>
            <Input v-model="form.name" placeholder="例如：mistral-7b" :disabled="mode === 'edit'" />
            <p v-if="mode === 'edit'" class="text-xs text-muted-foreground">名稱建立後不可修改</p>
          </div>

          <div class="space-y-1.5">
            <Label>執行檔路徑 <span class="text-destructive">*</span></Label>
            <Input v-model="form.executable_path" placeholder="例如：C:\llama\llama-server.exe" />
          </div>

          <div class="space-y-1.5">
            <Label>模型路徑 <span class="text-destructive">*</span></Label>
            <Input v-model="form.model_path" placeholder="例如：C:\models\mistral-7b.gguf" />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <Label>Host</Label>
              <Input v-model="form.host" placeholder="127.0.0.1" />
            </div>
            <div class="space-y-1.5">
              <Label>Port <span class="text-destructive">*</span></Label>
              <Input v-model="form.port" type="number" placeholder="例如：8080" />
            </div>
          </div>
        </fieldset>

        <!-- 效能參數 -->
        <fieldset class="space-y-3">
          <legend class="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">效能參數</legend>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <Label>Context Size</Label>
              <Input v-model="form.context_size" type="number" />
            </div>
            <div class="space-y-1.5">
              <Label>GPU Layers</Label>
              <Input v-model="form.n_gpu_layers" type="number" placeholder="0 = CPU only, 999 = all" />
            </div>
            <div class="space-y-1.5">
              <Label>Parallel</Label>
              <Input v-model="form.parallel" type="number" />
            </div>
            <div class="space-y-1.5">
              <Label>Batch Size</Label>
              <Input v-model="form.batch_size" type="number" />
            </div>
            <div class="space-y-1.5">
              <Label>Threads <span class="text-muted-foreground text-xs">（選填）</span></Label>
              <Input v-model="form.n_threads" type="number" placeholder="預設自動" />
            </div>
          </div>

          <div class="flex gap-6">
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input v-model="form.flash_attn" type="checkbox" class="h-4 w-4 rounded border" />
              Flash Attention
            </label>
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input v-model="form.cont_batching" type="checkbox" class="h-4 w-4 rounded border" />
              Continuous Batching
            </label>
          </div>
        </fieldset>

        <!-- 進階選項（Collapsible） -->
        <fieldset>
          <button
            type="button"
            class="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase tracking-widest mb-3 hover:text-foreground transition-colors"
            @click="showAdvanced = !showAdvanced"
          >
            <component :is="showAdvanced ? ChevronDown : ChevronRight" class="h-3.5 w-3.5" />
            進階選項
          </button>

          <div v-if="showAdvanced" class="space-y-3">
            <div class="grid grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <Label>Cache Type K</Label>
                <Select v-model="form.cache_type_k" :options="cacheTypeOptions" placeholder="預設 (f16)" />
              </div>
              <div class="space-y-1.5">
                <Label>Cache Type V</Label>
                <Select v-model="form.cache_type_v" :options="cacheTypeOptions" placeholder="預設 (f16)" />
              </div>
              <div class="space-y-1.5">
                <Label>Split Mode</Label>
                <Select v-model="form.split_mode" :options="splitModeOptions" placeholder="預設" />
              </div>
              <div class="space-y-1.5">
                <Label>Defrag Threshold <span class="text-muted-foreground text-xs">（選填）</span></Label>
                <Input v-model="form.defrag_thold" type="number" step="0.01" placeholder="例如：0.1" />
              </div>
            </div>
          </div>
        </fieldset>

        <!-- 管理設定 -->
        <fieldset class="space-y-3">
          <legend class="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">管理設定</legend>

          <div class="flex gap-6">
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input v-model="form.auto_start" type="checkbox" class="h-4 w-4 rounded border" />
              啟動時自動開始
            </label>
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input v-model="form.auto_restart" type="checkbox" class="h-4 w-4 rounded border" />
              崩潰後自動重啟
            </label>
          </div>

          <div>
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input v-model="form.no_webui" type="checkbox" class="h-4 w-4 rounded border" />
              停用 Web UI（<code class="text-xs font-mono bg-muted px-1 rounded">--no-webui</code>）
            </label>
            <p class="text-xs text-muted-foreground mt-1 ml-6">
              取消勾選後，可透過 http://{{ form.host || '127.0.0.1' }}:{{ form.port || '&lt;port&gt;' }} 開啟內建 Web UI
            </p>
          </div>

          <div v-if="form.auto_restart" class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <Label>最大重啟次數</Label>
              <Input v-model="form.max_restart_attempts" type="number" min="1" />
            </div>
            <div class="space-y-1.5">
              <Label>啟動等待時間（秒）</Label>
              <Input v-model="form.startup_timeout" type="number" min="10" />
            </div>
          </div>
        </fieldset>

        <p v-if="formError" class="text-sm text-destructive">{{ formError }}</p>

        <DialogFooter>
          <template v-if="mode === 'edit'">
            <Button type="button" variant="outline" @click="close">取消</Button>
            <Button type="button" variant="outline" :disabled="submitting" @click="submitSave">
              {{ submitting && !restartOnSave ? '儲存中…' : '儲存設定' }}
            </Button>
            <Button type="button" :disabled="submitting" @click="submitSaveAndRestart">
              {{ submitting && restartOnSave ? '更新中…' : '儲存並重啟' }}
            </Button>
          </template>
          <template v-else>
            <Button type="button" variant="outline" @click="close">取消</Button>
            <Button type="submit" :disabled="submitting">
              {{ submitting ? '建立中…' : '建立實例' }}
            </Button>
          </template>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
