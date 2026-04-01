import { reactive, watch } from 'vue'
import type { Rates } from '@/utils/modelUtils'

const STORAGE_KEY = 'llm_proxy_rates'

export const DEFAULT_RATES: Rates = {
  chat_input: 0.40,
  chat_output: 3.20,
  embed_input: 0.13,
}

function load(): Rates {
  try {
    const s = localStorage.getItem(STORAGE_KEY)
    return s ? { ...DEFAULT_RATES, ...JSON.parse(s) } : { ...DEFAULT_RATES }
  } catch {
    return { ...DEFAULT_RATES }
  }
}

export function useRates() {
  const rates = reactive<Rates>(load())

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...rates }))
  }

  watch(() => ({ ...rates }), save, { deep: true })

  function reset() {
    Object.assign(rates, DEFAULT_RATES)
  }

  return { rates, reset }
}
