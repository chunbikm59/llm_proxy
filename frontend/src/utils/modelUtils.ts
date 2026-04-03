import type { UsageRow } from '@/api'

export interface Rates {
  chat_input: number
  chat_output: number
  embed_input: number
  audio_per_minute: number
}

export function getModelType(model: string, request_type?: string): 'chat' | 'embedding' | 'audio' {
  if (request_type === 'audio') return 'audio'
  const m = (model || '').toLowerCase()
  if (m.includes('embed') || m.includes('bge') || m.includes('e5-')) return 'embedding'
  return 'chat'
}

export function calcCost(row: UsageRow, rates: Rates): number {
  const type = getModelType(row.model, row.request_type)
  if (type === 'audio') {
    return ((row.audio_duration_ms ?? 0) / 60000) * rates.audio_per_minute
  }
  if (type === 'embedding') {
    return (row.input_tokens / 1e6) * rates.embed_input
  }
  return (row.input_tokens / 1e6) * rates.chat_input
       + (row.output_tokens / 1e6) * rates.chat_output
}
