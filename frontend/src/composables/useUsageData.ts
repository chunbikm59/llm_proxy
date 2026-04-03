import { ref, reactive, computed } from 'vue'
import { api, type UsageRow } from '@/api'
import { calcCost, type Rates } from '@/utils/modelUtils'
import { getModelType } from '@/utils/modelUtils'

function defaultDates() {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 29)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return { start: fmt(start), end: fmt(end) }
}

export function useUsageData(rates: Rates) {
  const dates = reactive(defaultDates())
  const filterKeys = ref<number[]>([])
  const filterType = ref('')
  const filterModels = ref<string[]>([])

  const allUsage = ref<UsageRow[]>([])
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try {
      allUsage.value = await api.getUsage(dates.start, dates.end)
    } catch (e) {
      console.error('fetch usage error', e)
    } finally {
      loading.value = false
    }
  }

  const availableModels = computed(() =>
    [...new Set(allUsage.value.map(r => r.model))].sort()
  )

  const filtered = computed(() => {
    return allUsage.value
      .filter(r => {
        if (r.date < dates.start || r.date > dates.end) return false
        if (filterKeys.value.length && !filterKeys.value.includes(r.key_id!)) return false
        const type = getModelType(r.model, r.request_type)
        if (filterType.value && type !== filterType.value) return false
        if (filterModels.value.length && !filterModels.value.includes(r.model)) return false
        return true
      })
      .sort((a, b) => b.date.localeCompare(a.date))
  })

  const summary = computed(() => {
    const rows = filtered.value
    return {
      total_requests: rows.reduce((s, r) => s + (r.requests || 1), 0),
      total_tokens: rows.reduce((s, r) => s + r.total_tokens, 0),
      input_tokens: rows.reduce((s, r) => s + r.input_tokens, 0),
      output_tokens: rows.reduce((s, r) => s + r.output_tokens, 0),
      total_cost: rows.reduce((s, r) => s + calcCost(r, rates), 0),
    }
  })

  return {
    dates, filterKeys, filterType, filterModels,
    allUsage, loading, fetchAll,
    availableModels, filtered, summary,
  }
}
