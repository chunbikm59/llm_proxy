import {
  createApp, ref, reactive, computed, onMounted, nextTick, watch
} from 'vue'

// ─────────────────────────────────────────────────────────────────
// API 層
// ─────────────────────────────────────────────────────────────────
const api = {
  async _fetch(path, opts = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText)
      throw new Error(text || `HTTP ${res.status}`)
    }
    if (res.status === 204) return null
    return res.json()
  },
  listKeys: () => api._fetch('/admin/keys'),
  createKey: (name, description) =>
    api._fetch('/admin/keys', { method: 'POST', body: JSON.stringify({ name, description }) }),
  revokeKey: (id) => api._fetch(`/admin/keys/${id}`, { method: 'DELETE' }),
  activateKey: (id) => api._fetch(`/admin/keys/${id}/activate`, { method: 'POST' }),
  deleteKeyPermanent: (id) => api._fetch(`/admin/keys/${id}/permanent`, { method: 'DELETE' }),
  getKeyUsage: (id) => api._fetch(`/admin/keys/${id}/usage`),
}

// ─────────────────────────────────────────────────────────────────
// Composables
// ─────────────────────────────────────────────────────────────────

function useNotification() {
  const notifications = ref([])
  function push(msg, type = 'success') {
    const id = Date.now() + Math.random()
    notifications.value.push({ id, msg, type })
    setTimeout(() => {
      notifications.value = notifications.value.filter(n => n.id !== id)
    }, 3000)
  }
  return { notifications, push }
}

function useConfirmModal() {
  const visible = ref(false)
  const message = ref('')
  const subMessage = ref('')
  let _resolve = null

  function confirm(msg, sub = '') {
    message.value = msg
    subMessage.value = sub
    visible.value = true
    return new Promise(resolve => { _resolve = resolve })
  }
  function onConfirm() { visible.value = false; _resolve(true) }
  function onCancel() { visible.value = false; _resolve(false) }

  return { visible, message, subMessage, confirm, onConfirm, onCancel }
}

function useKeys(notify, confirm) {
  const keys = ref([])
  const loading = ref(false)

  async function fetchKeys() {
    loading.value = true
    try { keys.value = await api.listKeys() }
    catch (e) { notify.push(`載入失敗：${e.message}`, 'error') }
    finally { loading.value = false }
  }

  async function revokeKey(k) {
    try {
      await api.revokeKey(k.id)
      k.is_active = 0
      notify.push(`已停用 Key "${k.name}"`)
    } catch (e) { notify.push(`停用失敗：${e.message}`, 'error') }
  }

  async function activateKey(k) {
    try {
      await api.activateKey(k.id)
      k.is_active = 1
      notify.push(`已啟用 Key "${k.name}"`)
    } catch (e) { notify.push(`啟用失敗：${e.message}`, 'error') }
  }

  async function deleteKey(k) {
    const ok = await confirm.confirm(
      `確定要永久刪除「${k.name}」？`,
      '此操作不可復原，Key 及所有用量記錄都將被刪除。'
    )
    if (!ok) return
    try {
      await api.deleteKeyPermanent(k.id)
      keys.value = keys.value.filter(x => x.id !== k.id)
      notify.push(`已刪除 Key "${k.name}"`)
    } catch (e) { notify.push(`刪除失敗：${e.message}`, 'error') }
  }

  return { keys, loading, fetchKeys, revokeKey, activateKey, deleteKey }
}

function useCreateModal(onSuccess) {
  const visible = ref(false)
  const form = reactive({ name: '', description: '' })
  const submitting = ref(false)
  const formError = ref('')
  const createdKey = ref(null)  // 建立成功後暫存，顯示給用戶複製

  function open() {
    form.name = ''; form.description = ''; formError.value = ''; createdKey.value = null
    visible.value = true
    nextTick(() => document.getElementById('create-name-input')?.focus())
  }
  function close() { visible.value = false; createdKey.value = null }

  async function submit() {
    if (!form.name.trim()) { formError.value = 'Name 為必填'; return }
    submitting.value = true; formError.value = ''
    try {
      const newKey = await api.createKey(form.name.trim(), form.description.trim())
      createdKey.value = newKey
      await onSuccess(newKey)
    } catch (e) { formError.value = e.message }
    finally { submitting.value = false }
  }

  return { visible, form, submitting, formError, createdKey, open, close, submit }
}

// ─────────────────────────────────────────────────────────────────
// 複製到剪貼簿
// ─────────────────────────────────────────────────────────────────
async function copyText(text, notify) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // fallback for non-secure contexts
    const el = document.createElement('input')
    el.value = text
    el.style.position = 'fixed'; el.style.opacity = '0'
    document.body.appendChild(el)
    el.select(); el.setSelectionRange(0, 99999)
    document.body.removeChild(el)
  }
  notify.push('已複製到剪貼簿')
}

// ─────────────────────────────────────────────────────────────────
// 費率管理（localStorage 持久化）
// ─────────────────────────────────────────────────────────────────
const DEFAULT_RATES = {
  chat_input: 0.40,
  chat_output: 3.20,
  embed_input: 0.13,
}

function useRates() {
  const STORAGE_KEY = 'llm_proxy_rates'
  function load() {
    try {
      const s = localStorage.getItem(STORAGE_KEY)
      return s ? { ...DEFAULT_RATES, ...JSON.parse(s) } : { ...DEFAULT_RATES }
    } catch { return { ...DEFAULT_RATES } }
  }
  const rates = reactive(load())
  function save() { localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...rates })) }
  watch(() => ({ ...rates }), save, { deep: true })
  function reset() { Object.assign(rates, DEFAULT_RATES) }
  return { rates, reset }
}

// ─────────────────────────────────────────────────────────────────
// 模型類型判斷
// ─────────────────────────────────────────────────────────────────
function getModelType(model) {
  const m = (model || '').toLowerCase()
  if (m.includes('embed') || m.includes('bge') || m.includes('e5-')) return 'embedding'
  return 'chat'
}

function calcCost(row, rates) {
  const type = getModelType(row.model)
  if (type === 'embedding') {
    return (row.input_tokens / 1e6) * rates.embed_input
  }
  return (row.input_tokens / 1e6) * rates.chat_input
       + (row.output_tokens / 1e6) * rates.chat_output
}

// ─────────────────────────────────────────────────────────────────
// 用量資料 Composable
// ─────────────────────────────────────────────────────────────────
function useUsageData(allKeys, rates) {
  // 日期預設：過去 30 天
  function defaultDates() {
    const end = new Date()
    const start = new Date(); start.setDate(start.getDate() - 29)
    const fmt = d => d.toISOString().slice(0, 10)
    return { start: fmt(start), end: fmt(end) }
  }

  const dates = reactive(defaultDates())
  const filterKeys = ref([])    // 空 = 全部
  const filterType = ref('')    // '' | 'chat' | 'embedding'
  const filterModels = ref([])  // 空 = 全部

  // 所有用量原始資料（按 key 分開拉取後合併）
  const allUsage = ref([])
  const loading = ref(false)

  async function fetchAll() {
    if (!allKeys.value.length) return
    loading.value = true
    try {
      const results = await Promise.all(
        allKeys.value.map(k => api.getKeyUsage(k.id).then(rows =>
          rows.map(r => ({ ...r, key_id: k.id, key_name: k.name }))
        ))
      )
      allUsage.value = results.flat()
    } catch (e) {
      console.error('fetch usage error', e)
    } finally { loading.value = false }
  }

  // 可選的模型列表（從原始資料提取）
  const availableModels = computed(() =>
    [...new Set(allUsage.value.map(r => r.model))].sort()
  )

  // 篩選後的資料
  const filtered = computed(() => {
    return allUsage.value.filter(r => {
      if (r.date < dates.start || r.date > dates.end) return false
      if (filterKeys.value.length && !filterKeys.value.includes(r.key_id)) return false
      const type = getModelType(r.model)
      if (filterType.value && type !== filterType.value) return false
      if (filterModels.value.length && !filterModels.value.includes(r.model)) return false
      return true
    })
  })

  // 統計卡片
  const summary = computed(() => {
    const rows = filtered.value
    const total_requests = rows.reduce((s, r) => s + (r.requests || 1), 0)
    const total_tokens = rows.reduce((s, r) => s + r.total_tokens, 0)
    const total_cost = rows.reduce((s, r) => s + calcCost(r, rates), 0)
    const avg_tokens = total_requests > 0 ? Math.round(total_tokens / total_requests) : 0
    return { total_requests, total_tokens, total_cost, avg_tokens }
  })

  return {
    dates, filterKeys, filterType, filterModels,
    allUsage, loading, fetchAll,
    availableModels, filtered, summary,
  }
}

// ─────────────────────────────────────────────────────────────────
// ECharts 堆疊長條圖
// ─────────────────────────────────────────────────────────────────
const CHART_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#f97316', '#84cc16', '#ec4899', '#6366f1'
]

function buildChartOption(filtered, groupBy, rates, dateRange) {
  // 產生日期軸（連續）
  const start = new Date(dateRange.start)
  const end = new Date(dateRange.end)
  const dates = []
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    dates.push(d.toISOString().slice(0, 10))
  }

  // 取得所有群組 key
  function getGroup(r) {
    if (groupBy === 'type') return getModelType(r.model) === 'embedding' ? 'Embedding' : 'Chat'
    if (groupBy === 'key') return r.key_name || `Key ${r.key_id}`
    return r.model || 'unknown'
  }

  const groups = [...new Set(filtered.map(r => getGroup(r)))].sort()

  // 建立 { group -> { date -> cost } }
  const data = {}
  for (const g of groups) data[g] = {}
  for (const r of filtered) {
    const g = getGroup(r)
    const cost = calcCost(r, rates)
    data[g][r.date] = (data[g][r.date] || 0) + cost
  }

  const series = groups.map((g, i) => ({
    name: g,
    type: 'bar',
    stack: 'total',
    emphasis: { focus: 'series' },
    itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] },
    data: dates.map(d => +(data[g][d] || 0).toFixed(6)),
  }))

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(params) {
        const date = params[0].axisValue
        let html = `<div class="font-medium mb-1">${date}</div>`
        let total = 0
        for (const p of params) {
          if (p.value > 0) {
            html += `<div>${p.marker}${p.seriesName}: $${p.value.toFixed(6)}</div>`
            total += p.value
          }
        }
        html += `<div class="mt-1 font-medium border-t pt-1">合計: $${total.toFixed(6)}</div>`
        return html
      }
    },
    legend: {
      top: 0,
      data: groups,
      textStyle: { fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '40px', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: dates.length > 14 ? 45 : 0,
        fontSize: 11,
        formatter: v => dates.length > 30 ? v.slice(5) : v
      }
    },
    yAxis: {
      type: 'value',
      name: 'USD',
      axisLabel: { formatter: v => `$${v}` }
    },
    series,
  }
}

// ─────────────────────────────────────────────────────────────────
// 格式化工具
// ─────────────────────────────────────────────────────────────────
function fmtNum(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return String(n)
}
function fmtCost(n) {
  if (n >= 1) return '$' + n.toFixed(4)
  if (n >= 0.0001) return '$' + n.toFixed(6)
  return '$' + n.toFixed(8)
}
function fmtDate(s) {
  return s ? s.replace('T', ' ').slice(0, 16) : ''
}

// ─────────────────────────────────────────────────────────────────
// 多選下拉組件
// ─────────────────────────────────────────────────────────────────
const MultiSelect = {
  props: {
    modelValue: { type: Array, default: () => [] },
    options: { type: Array, default: () => [] }, // [{ value, label }]
    placeholder: { type: String, default: '全部' },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const open = ref(false)
    const toggle = (v) => {
      const cur = [...props.modelValue]
      const idx = cur.indexOf(v)
      if (idx >= 0) cur.splice(idx, 1)
      else cur.push(v)
      emit('update:modelValue', cur)
    }
    const clear = () => emit('update:modelValue', [])
    const displayText = computed(() => {
      if (!props.modelValue.length) return props.placeholder
      if (props.modelValue.length === 1) {
        const opt = props.options.find(o => o.value === props.modelValue[0])
        return opt ? opt.label : props.modelValue[0]
      }
      return `已選 ${props.modelValue.length} 項`
    })
    return { open, toggle, clear, displayText }
  },
  template: `
    <div class="relative">
      <button type="button" @click="open = !open"
        class="select select-bordered select-sm w-full text-left text-sm">
        <span :class="modelValue.length ? '' : 'text-base-content/40'">{{ displayText }}</span>
      </button>
      <div v-if="open" class="absolute z-30 mt-1 w-full bg-base-100 border border-base-300 rounded-box shadow-lg max-h-48 overflow-y-auto">
        <div v-if="modelValue.length" @click="clear()" class="px-3 py-2 text-xs text-primary hover:bg-base-200 cursor-pointer border-b border-base-200">清除選擇</div>
        <div v-for="opt in options" :key="opt.value" @click="toggle(opt.value)"
          class="flex items-center gap-2 px-3 py-2 text-sm hover:bg-base-200 cursor-pointer">
          <span :class="modelValue.includes(opt.value) ? 'text-primary' : 'text-base-content/20'">✓</span>
          <span :class="modelValue.includes(opt.value) ? 'font-medium' : 'text-base-content/60'">{{ opt.label }}</span>
        </div>
        <div v-if="!options.length" class="px-3 py-2 text-sm text-base-content/40 text-center">無選項</div>
      </div>
      <div v-if="open" class="fixed inset-0 z-20" @click="open = false"></div>
    </div>
  `
}

// ─────────────────────────────────────────────────────────────────
// Keys 管理頁面
// ─────────────────────────────────────────────────────────────────
const KeysPage = {
  props: ['keysState', 'notify'],
  setup(props) {
    const { keys, loading, fetchKeys, revokeKey, activateKey, deleteKey } = props.keysState
    const notify = props.notify

    const createModal = useCreateModal(async (newKey) => {
      await fetchKeys()
      notify.push(`Key「${newKey.name}」建立成功`)
    })

    function copy(key) { copyText(key, notify) }

    // 用量詳情 Modal（在此頁面內）
    const usageModal = reactive({
      visible: false,
      key: null,
      data: [],
      loading: false,
    })

    async function openUsage(k) {
      usageModal.key = k
      usageModal.visible = true
      usageModal.loading = true
      usageModal.data = []
      try {
        usageModal.data = await api.getKeyUsage(k.id)
      } finally { usageModal.loading = false }
    }

    return {
      keys, loading, fetchKeys, revokeKey, activateKey, deleteKey,
      createModal, copy, usageModal, openUsage,
      fmtNum, fmtCost, fmtDate,
    }
  },
  template: `
<div class="p-6 space-y-5">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <div>
      <h2 class="text-xl font-bold text-gray-800">API Key 管理</h2>
      <p class="text-sm text-gray-500 mt-0.5">管理所有虛擬 API Key</p>
    </div>
    <button @click="createModal.open()" class="btn btn-primary flex items-center gap-2">
      <span>＋</span> 建立新 Key
    </button>
  </div>

  <!-- 表格 -->
  <div class="bg-base-100 rounded-xl shadow-sm border border-base-200 overflow-x-auto">
    <div v-if="loading" class="py-16 text-center text-base-content/40">
      <i data-lucide="loader-circle" class="mx-auto mb-2 w-8 h-8 animate-spin opacity-40"></i>載入中...
    </div>
    <table v-else class="table table-zebra w-full">
      <thead>
        <tr>
          <th>ID</th>
          <th>Name</th>
          <th>Description</th>
          <th>Key</th>
          <th>建立時間</th>
          <th>狀態</th>
          <th class="text-right">Requests</th>
          <th class="text-right">Tokens</th>
          <th class="text-right">Cost</th>
          <th class="text-center">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!keys.length">
          <td colspan="10" class="py-16 text-center text-base-content/40">
            <i data-lucide="key-round" class="mx-auto mb-2 w-10 h-10 opacity-30"></i>
            尚無 API Key，點擊右上角建立第一個
          </td>
        </tr>
        <tr v-for="k in keys" :key="k.id">
          <td class="text-base-content/40 font-mono">#{{ k.id }}</td>
          <td class="font-medium">{{ k.name }}</td>
          <td class="text-base-content/60">{{ k.description || '—' }}</td>
          <td>
            <div class="flex items-center gap-1.5">
              <span class="font-mono text-xs bg-base-200 px-2 py-0.5 rounded select-all">
                {{ k.key.slice(0, 12) }}…
              </span>
              <button @click="copy(k.key)" title="複製"
                class="text-base-content/40 hover:text-primary transition-colors"><i data-lucide="copy" class="w-3.5 h-3.5"></i></button>
            </div>
          </td>
          <td class="text-base-content/40 text-xs">{{ fmtDate(k.created_at) }}</td>
          <td>
            <span :class="k.is_active ? 'badge' : 'badge badge-error'" :style="k.is_active ? 'background:#4ade80;border-color:#4ade80;color:#fff' : ''">
              {{ k.is_active ? 'Active' : 'Revoked' }}
            </span>
          </td>
          <td class="text-right font-mono">{{ fmtNum(k.total_requests) }}</td>
          <td class="text-right font-mono">{{ fmtNum(k.total_tokens) }}</td>
          <td class="text-right font-mono">{{ fmtCost(k.total_cost_usd) }}</td>
          <td>
            <div class="flex items-center justify-center gap-1.5">
              <button @click="openUsage(k)"
                class="btn btn-xs btn-info btn-outline" title="查看用量"><i data-lucide="bar-chart-2" class="w-3.5 h-3.5"></i></button>
              <button v-if="k.is_active" @click="revokeKey(k)"
                class="btn btn-xs btn-warning btn-outline" title="停用"><i data-lucide="pause" class="w-3.5 h-3.5"></i></button>
              <button v-else @click="activateKey(k)"
                class="btn btn-xs btn-success btn-outline" title="啟用"><i data-lucide="play" class="w-3.5 h-3.5"></i></button>
              <button @click="deleteKey(k)"
                class="btn btn-xs btn-error btn-outline" title="刪除"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- 建立 Key Modal -->
  <teleport to="body">
    <div :class="createModal.visible.value ? 'modal modal-open' : 'modal'">
      <div class="modal-box max-w-md">
        <!-- 建立成功：顯示 Key -->
        <template v-if="createModal.createdKey.value">
          <div class="text-center mb-5">
            <div class="text-3xl mb-2">🎉</div>
            <h3 class="text-lg font-semibold">Key 建立成功</h3>
            <p class="text-sm text-base-content/50 mt-1">請立即複製，此 Key 不會再次顯示</p>
          </div>
          <div class="bg-base-200 rounded-lg p-3 flex items-center gap-2">
            <code class="flex-1 text-sm font-mono break-all text-base-content/80">{{ createModal.createdKey.value.key }}</code>
            <button @click="copyText(createModal.createdKey.value.key, notify)" class="btn btn-sm btn-ghost shrink-0">複製</button>
          </div>
          <div class="modal-action">
            <button @click="createModal.close()" class="btn btn-primary w-full">完成</button>
          </div>
        </template>
        <!-- 建立表單 -->
        <template v-else>
          <h3 class="text-lg font-semibold mb-5">建立新 API Key</h3>
          <form @submit.prevent="createModal.submit()">
            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium mb-1.5">
                  Name <span class="text-error">*</span>
                </label>
                <input id="create-name-input" v-model="createModal.form.name"
                  class="input input-bordered w-full" placeholder="例如：team-a、john-dev" required />
              </div>
              <div>
                <label class="block text-sm font-medium mb-1.5">Description</label>
                <input v-model="createModal.form.description"
                  class="input input-bordered w-full" placeholder="選填說明" />
              </div>
              <p v-if="createModal.formError.value" class="text-error text-sm">
                {{ createModal.formError.value }}
              </p>
            </div>
            <div class="modal-action">
              <button type="button" @click="createModal.close()" class="btn btn-ghost">取消</button>
              <button type="submit" :disabled="createModal.submitting.value" class="btn btn-primary disabled:opacity-50">
                {{ createModal.submitting.value ? '建立中…' : '建立' }}
              </button>
            </div>
          </form>
        </template>
      </div>
      <div class="modal-backdrop" @click="createModal.close()"></div>
    </div>
  </teleport>

  <!-- 用量詳情 Modal -->
  <teleport to="body">
    <div :class="usageModal.visible ? 'modal modal-open' : 'modal'">
      <div class="modal-box w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div class="flex items-center justify-between pb-4 border-b border-base-200">
          <div>
            <h3 class="text-lg font-semibold">{{ usageModal.key?.name }} 用量記錄</h3>
            <p class="text-xs text-base-content/40 font-mono mt-0.5">{{ usageModal.key?.key }}</p>
          </div>
          <button @click="usageModal.visible = false" class="btn btn-sm btn-ghost btn-circle">✕</button>
        </div>
        <div class="overflow-y-auto flex-1 pt-4">
          <div v-if="usageModal.loading" class="py-10 text-center text-base-content/40">載入中…</div>
          <div v-else-if="!usageModal.data.length" class="py-10 text-center text-base-content/40">尚無用量記錄</div>
          <table v-else class="table table-zebra table-sm w-full">
            <thead>
              <tr>
                <th>日期</th>
                <th>模型</th>
                <th class="text-right">Input</th>
                <th class="text-right">Output</th>
                <th class="text-right">Total</th>
                <th class="text-right">Requests</th>
                <th class="text-right">Cost</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in usageModal.data" :key="i">
                <td class="font-mono text-xs">{{ r.date }}</td>
                <td class="text-xs text-base-content/60">{{ r.model }}</td>
                <td class="text-right font-mono">{{ fmtNum(r.input_tokens) }}</td>
                <td class="text-right font-mono">{{ fmtNum(r.output_tokens) }}</td>
                <td class="text-right font-mono">{{ fmtNum(r.total_tokens) }}</td>
                <td class="text-right font-mono">{{ r.requests || 1 }}</td>
                <td class="text-right font-mono text-success">—</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="modal-backdrop" @click="usageModal.visible = false"></div>
    </div>
  </teleport>
</div>
`
}

// ─────────────────────────────────────────────────────────────────
// 用量分析頁面
// ─────────────────────────────────────────────────────────────────
const UsagePage = {
  props: ['allKeys', 'rates', 'resetRates'],
  components: { MultiSelect },
  setup(props) {
    const { rates, resetRates } = props

    const usageData = useUsageData(props.allKeys, rates)
    const {
      dates, filterKeys, filterType, filterModels,
      loading, fetchAll, availableModels, filtered, summary,
    } = usageData

    const groupBy = ref('type') // 'type' | 'key' | 'model'
    const showRates = ref(false)

    let chartInstance = null

    function initChart() {
      const el = document.getElementById('usage-chart')
      if (!el) return
      if (chartInstance) chartInstance.dispose()
      chartInstance = echarts.init(el, null, { renderer: 'canvas' })
    }

    function updateChart() {
      if (!chartInstance) initChart()
      if (!chartInstance) return
      const option = buildChartOption(filtered.value, groupBy.value, rates, dates)
      chartInstance.setOption(option, true)
    }

    // 監聽資料或篩選條件變化 → 更新圖表
    watch([filtered, groupBy, () => ({...rates})], () => nextTick(updateChart), { deep: true })

    // 監聽視窗大小
    function onResize() { chartInstance?.resize() }

    onMounted(async () => {
      window.addEventListener('resize', onResize)
      await fetchAll()
      await nextTick()
      initChart()
      updateChart()
    })

    // allKeys 載入後重新拉資料
    watch(() => props.allKeys.value, (v) => {
      if (v && v.length) fetchAll()
    })

    const keyOptions = computed(() =>
      (props.allKeys.value || []).map(k => ({ value: k.id, label: k.name }))
    )
    const modelOptions = computed(() =>
      availableModels.value.map(m => ({ value: m, label: m }))
    )

    return {
      dates, filterKeys, filterType, filterModels,
      loading, fetchAll, filtered, summary,
      groupBy, showRates, rates, resetRates,
      keyOptions, modelOptions,
      fmtNum, fmtCost, getModelType, calcCost,
    }
  },
  template: `
<div class="p-6 space-y-5">
  <!-- Header -->
  <div class="flex items-center justify-between flex-wrap gap-3">
    <div>
      <h2 class="text-xl font-bold text-gray-800">用量分析</h2>
      <p class="text-sm text-gray-500 mt-0.5">依日期、Key、模型分析 Token 用量與費用估算</p>
    </div>
    <div class="flex gap-2">
      <button @click="showRates = !showRates"
        class="btn btn-ghost btn-sm flex items-center gap-1.5">
        <i data-lucide="settings-2" class="w-4 h-4"></i> 費率設定
      </button>
      <button @click="fetchAll()" :disabled="loading"
        class="btn btn-ghost btn-sm flex items-center gap-1.5 disabled:opacity-50">
        <i data-lucide="refresh-cw" :class="loading ? 'w-4 h-4 animate-spin' : 'w-4 h-4'"></i>
        重新整理
      </button>
    </div>
  </div>

  <!-- 費率設定 Panel -->
  <div v-if="showRates" class="card bg-base-100 border border-info/30 shadow-sm">
    <div class="card-body p-4">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-semibold">費率設定（USD / 1M tokens）</h3>
        <button @click="resetRates()" class="btn btn-xs btn-ghost text-primary">恢復預設</button>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label class="block text-xs font-medium text-base-content/60 mb-1">Chat Input</label>
          <div class="flex items-center gap-1">
            <span class="text-base-content/60 text-sm">$</span>
            <input type="number" v-model.number="rates.chat_input" min="0" step="0.01"
              class="input input-bordered input-sm flex-1" />
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-base-content/60 mb-1">Chat Output</label>
          <div class="flex items-center gap-1">
            <span class="text-base-content/60 text-sm">$</span>
            <input type="number" v-model.number="rates.chat_output" min="0" step="0.01"
              class="input input-bordered input-sm flex-1" />
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-base-content/60 mb-1">Embedding Input</label>
          <div class="flex items-center gap-1">
            <span class="text-base-content/60 text-sm">$</span>
            <input type="number" v-model.number="rates.embed_input" min="0" step="0.01"
              class="input input-bordered input-sm flex-1" />
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 篩選列 -->
  <div class="card bg-base-100 shadow-sm border border-base-200">
    <div class="card-body p-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label class="block text-xs font-medium text-base-content/60 mb-1.5">日期範圍</label>
          <div class="flex items-center gap-2">
            <input type="date" v-model="dates.start" class="input input-bordered input-sm flex-1" />
            <span class="text-base-content/40 text-sm">～</span>
            <input type="date" v-model="dates.end" class="input input-bordered input-sm flex-1" />
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-base-content/60 mb-1.5">API Key</label>
          <MultiSelect v-model="filterKeys" :options="keyOptions" placeholder="全部 Key" />
        </div>
        <div>
          <label class="block text-xs font-medium text-base-content/60 mb-1.5">類型</label>
          <select v-model="filterType" class="select select-bordered select-sm w-full">
            <option value="">全部類型</option>
            <option value="chat">Chat</option>
            <option value="embedding">Embedding</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-base-content/60 mb-1.5">模型</label>
          <MultiSelect v-model="filterModels" :options="modelOptions" placeholder="全部模型" />
        </div>
      </div>
    </div>
  </div>

  <!-- 統計卡片 -->
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
    <div class="card bg-base-100 shadow-sm border border-base-200 text-center">
      <div class="card-body p-4">
        <div class="text-4xl font-bold">{{ fmtNum(summary.total_requests) }}</div>
        <div class="text-sm text-base-content/50 mt-1.5">總請求數</div>
      </div>
    </div>
    <div class="card bg-base-100 shadow-sm border border-base-200 text-center">
      <div class="card-body p-4">
        <div class="text-4xl font-bold text-primary">{{ fmtNum(summary.total_tokens) }}</div>
        <div class="text-sm text-base-content/50 mt-1.5">總 Tokens</div>
      </div>
    </div>
    <div class="card bg-base-100 shadow-sm border border-base-200 text-center">
      <div class="card-body p-4">
        <div class="text-4xl font-bold" style="color: rgb(237 157 0)">{{ fmtCost(summary.total_cost) }}</div>
        <div class="text-sm text-base-content/50 mt-1.5">估算費用（USD）</div>
      </div>
    </div>
    <div class="card bg-base-100 shadow-sm border border-base-200 text-center">
      <div class="card-body p-4">
        <div class="text-4xl font-bold text-secondary">{{ fmtNum(summary.avg_tokens) }}</div>
        <div class="text-sm text-base-content/50 mt-1.5">平均 Tokens / 請求</div>
      </div>
    </div>
  </div>

  <!-- ECharts 圖表 -->
  <div class="card bg-base-100 shadow-sm border border-base-200">
    <div class="card-body p-4">
      <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 class="font-semibold">每日費用趨勢</h3>
        <div class="join">
          <button v-for="g in [{v:'type',l:'按類型'},{v:'key',l:'按 Key'},{v:'model',l:'按模型'}]"
            :key="g.v" @click="groupBy = g.v"
            :class="groupBy === g.v ? 'btn-active' : ''"
            class="btn btn-sm join-item">
            {{ g.l }}
          </button>
        </div>
      </div>
      <div id="usage-chart" style="width:100%;height:320px;"></div>
      <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-base-100/70 rounded-xl">
        <span class="loading loading-spinner loading-md"></span>
      </div>
    </div>
  </div>

  <!-- 明細表格 -->
  <div class="card bg-base-100 shadow-sm border border-base-200 overflow-x-auto">
    <div class="card-body p-4">
      <h3 class="font-semibold mb-4">
        明細記錄
        <span class="ml-2 text-sm font-normal text-base-content/40">（{{ filtered.length }} 筆）</span>
      </h3>
      <div v-if="!filtered.length" class="py-10 text-center text-base-content/40">
        <div class="text-3xl mb-2">📭</div>
        無符合條件的記錄
      </div>
      <table v-else class="table table-zebra table-sm w-full">
        <thead>
          <tr>
            <th>日期</th>
            <th>模型</th>
            <th>類型</th>
            <th>Key</th>
            <th class="text-right">Input</th>
            <th class="text-right">Output</th>
            <th class="text-right">Total</th>
            <th class="text-right">Requests</th>
            <th class="text-right">估算費用</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in filtered" :key="i">
            <td class="font-mono text-xs">{{ r.date }}</td>
            <td class="text-xs text-base-content/60">{{ r.model }}</td>
            <td>
              <span :class="getModelType(r.model) === 'chat' ? 'badge badge-info badge-outline' : 'badge badge-secondary badge-outline'">
                {{ getModelType(r.model) === 'chat' ? 'Chat' : 'Embed' }}
              </span>
            </td>
            <td class="text-xs">{{ r.key_name }}</td>
            <td class="text-right font-mono">{{ fmtNum(r.input_tokens) }}</td>
            <td class="text-right font-mono">{{ fmtNum(r.output_tokens) }}</td>
            <td class="text-right font-mono">{{ fmtNum(r.total_tokens) }}</td>
            <td class="text-right font-mono">{{ r.requests || 1 }}</td>
            <td class="text-right font-mono" style="color: rgb(237 157 0)">{{ fmtCost(calcCost(r, rates)) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</div>
`
}

// ─────────────────────────────────────────────────────────────────
// 根應用
// ─────────────────────────────────────────────────────────────────
const App = {
  components: { KeysPage, UsagePage, MultiSelect },
  setup() {
    const notify = useNotification()
    const confirm = useConfirmModal()
    const { rates, reset: resetRates } = useRates()
    const currentPage = ref('keys')

    const keysState = useKeys(notify, confirm)

    onMounted(() => keysState.fetchKeys())

    return {
      notify, confirm, rates, resetRates,
      currentPage, keysState,
    }
  },
  template: `
<div class="flex h-screen overflow-hidden bg-base-200">
  <!-- Sidebar -->
  <aside class="w-56 shrink-0 bg-neutral flex flex-col">
    <div class="px-5 py-5 border-b border-neutral-content/10">
      <h1 class="text-neutral-content font-bold text-base leading-tight">LLM Proxy</h1>
      <p class="text-neutral-content/40 text-xs mt-0.5">管理後台</p>
    </div>
    <nav class="flex-1 py-2">
      <ul class="menu menu-md w-full text-neutral-content">
        <li>
          <a :class="currentPage === 'keys' ? 'active' : ''" @click="currentPage = 'keys'">
            <i data-lucide="key-round" class="w-4 h-4"></i>
            <span class="text-sm font-medium">API Key 管理</span>
          </a>
        </li>
        <li>
          <a :class="currentPage === 'usage' ? 'active' : ''" @click="currentPage = 'usage'">
            <i data-lucide="chart-column" class="w-4 h-4"></i>
            <span class="text-sm font-medium">用量分析</span>
          </a>
        </li>
      </ul>
    </nav>
    <div class="px-4 py-3 border-t border-neutral-content/10">
      <p class="text-neutral-content/40 text-xs">{{ new Date().toLocaleDateString('zh-TW') }}</p>
    </div>
  </aside>

  <!-- 主內容 -->
  <main class="flex-1 overflow-y-auto">
    <KeysPage v-if="currentPage === 'keys'" :keysState="keysState" :notify="notify" />
    <UsagePage v-if="currentPage === 'usage'" :allKeys="keysState.keys" :rates="rates" :resetRates="resetRates" />
  </main>
</div>

<!-- 確認 Modal -->
<teleport to="body">
  <div :class="confirm.visible.value ? 'modal modal-open' : 'modal'">
    <div class="modal-box max-w-sm">
      <i data-lucide="triangle-alert" class="w-8 h-8 mb-3 text-error mx-auto"></i>
      <h3 class="font-semibold mb-1">{{ confirm.message.value }}</h3>
      <p v-if="confirm.subMessage.value" class="text-sm text-base-content/60 mb-5">{{ confirm.subMessage.value }}</p>
      <div v-else class="mb-5"></div>
      <div class="modal-action">
        <button @click="confirm.onCancel()" class="btn btn-ghost">取消</button>
        <button @click="confirm.onConfirm()" class="btn btn-error">確認刪除</button>
      </div>
    </div>
    <div class="modal-backdrop" @click="confirm.onCancel()"></div>
  </div>
</teleport>

<!-- Toast 通知 -->
<teleport to="body">
  <div class="toast toast-end toast-top z-[200]">
    <transition-group name="toast">
      <div v-for="n in notify.notifications.value" :key="n.id"
        :class="n.type === 'success' ? 'alert alert-success' : 'alert alert-error'"
        class="text-sm flex items-center gap-2 shadow-xl">
        <span>{{ n.type === 'success' ? '✓' : '✕' }}</span>
        {{ n.msg }}
      </div>
    </transition-group>
  </div>
</teleport>
`
}

const app = createApp(App)
app.config.globalProperties.$nextTick = () => {}

// 每次 Vue 更新後重新初始化 Lucide icons
app.mixin({
  updated() { if (window.lucide) lucide.createIcons() },
  mounted() { if (window.lucide) lucide.createIcons() },
})

app.mount('#app')
