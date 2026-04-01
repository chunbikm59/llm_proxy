// ─── Types ────────────────────────────────────────────────────────────────────

export interface ApiKey {
  id: number
  name: string
  description: string | null
  key: string
  created_at: string
  is_active: 0 | 1
  total_requests: number
  total_tokens: number
  total_cost_usd: number
}

export interface UsageRow {
  date: string
  model: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
  requests: number
  key_id?: number
  key_name?: string
}

export interface GpuInfo {
  index: number
  name: string
  util_percent: number
  vram_used_gb: number
  vram_total_gb: number
  vram_percent: number
  temperature_c: number | null
}

export interface SystemStats {
  cpu: { percent: number; count_logical: number; count_physical: number }
  ram: { percent: number; used_gb: number; total_gb: number }
  gpu: GpuInfo[]
  gpu_available: boolean
  timestamp: string
}

// ─── API layer ────────────────────────────────────────────────────────────────

async function _fetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }
  if (res.status === 204) return null as T
  return res.json() as T
}

export const api = {
  listKeys: () => _fetch<ApiKey[]>('/admin/keys'),
  createKey: (name: string, description: string) =>
    _fetch<ApiKey>('/admin/keys', { method: 'POST', body: JSON.stringify({ name, description }) }),
  updateKey: (id: number, name: string, description: string) =>
    _fetch<ApiKey>(`/admin/keys/${id}`, { method: 'PATCH', body: JSON.stringify({ name, description }) }),
  revokeKey: (id: number) => _fetch<null>(`/admin/keys/${id}`, { method: 'DELETE' }),
  activateKey: (id: number) => _fetch<{ message: string }>(`/admin/keys/${id}/activate`, { method: 'POST' }),
  deleteKeyPermanent: (id: number) => _fetch<null>(`/admin/keys/${id}/permanent`, { method: 'DELETE' }),
  getKeyUsage: (id: number) => _fetch<UsageRow[]>(`/admin/keys/${id}/usage`),
  getSystemStats: () => _fetch<SystemStats>('/admin/system/stats'),
}
