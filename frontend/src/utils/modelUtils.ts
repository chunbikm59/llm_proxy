import type { UsageRow } from '@/api'

export interface Rates {
  chat_input: number
  chat_output: number
  embed_input: number
}

export function getModelType(model: string): 'chat' | 'embedding' {
  const m = (model || '').toLowerCase()
  if (m.includes('embed') || m.includes('bge') || m.includes('e5-')) return 'embedding'
  return 'chat'
}

export function calcCost(row: UsageRow, rates: Rates): number {
  const type = getModelType(row.model)
  if (type === 'embedding') {
    return (row.input_tokens / 1e6) * rates.embed_input
  }
  return (row.input_tokens / 1e6) * rates.chat_input
       + (row.output_tokens / 1e6) * rates.chat_output
}
