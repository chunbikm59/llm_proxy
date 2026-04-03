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
  request_type: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd: number
  audio_duration_ms: number | null
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

export interface LlamaInstanceConfig {
  executable_path: string
  model_path: string
  mmproj_path: string | null
  host: string
  port: number
  context_size: number
  n_threads: number | null
  n_gpu_layers: number
  parallel: number
  batch_size: number
  ubatch_size: number | null
  split_mode: string | null
  defrag_thold: number | null
  cache_type_k: string | null
  cache_type_v: string | null
  flash_attn: boolean
  cont_batching: boolean
  no_webui: boolean
  extra_args: string[]
  auto_start: boolean
  auto_restart: boolean
  max_restart_attempts: number
  startup_timeout: number
}

export interface LlamaInstance {
  name: string
  status: 'stopped' | 'starting' | 'running' | 'failed' | 'restarting'
  pid: number | null
  started_at: string | null
  restart_count: number
  config: LlamaInstanceConfig
}

export interface WhisperClusterConfig {
  executable_path: string
  model_path: string
  n_threads: number | null
  n_processors: number | null
  beam_size: number | null
  best_of: number | null
  audio_ctx: number | null
  max_instances: number
  is_default: boolean
}

export interface WhisperCluster {
  name: string
  status: 'stopped' | 'running' | 'failed'
  active_count: number
  config: WhisperClusterConfig
}

export interface WhisperTranscriptionJob {
  id: number
  cluster_name: string | null
  filename: string
  language: string | null
  audio_duration_ms: number | null
  processing_time_ms: number | null
  status: 'pending' | 'processing' | 'done' | 'failed'
  response_format: string
  error_message: string | null
  created_at: string
  completed_at: string | null
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
  getUsage: (start: string, end: string) =>
    _fetch<UsageRow[]>(`/admin/keys/usage?start=${start}&end=${end}`),
  getSystemStats: () => _fetch<SystemStats>('/admin/system/stats'),
  listLlamaInstances: () => _fetch<LlamaInstance[]>('/llama/instances'),
  getLlamaInstance: (name: string) => _fetch<LlamaInstance>(`/llama/instances/${name}`),
  createLlamaInstance: (body: { name: string } & LlamaInstanceConfig) =>
    _fetch<LlamaInstance>('/llama/instances', { method: 'POST', body: JSON.stringify(body) }),
  stopLlamaInstance: (name: string) =>
    _fetch<LlamaInstance>(`/llama/instances/${name}/stop`, { method: 'POST' }),
  restartLlamaInstance: (name: string) =>
    _fetch<LlamaInstance>(`/llama/instances/${name}/restart`, { method: 'POST' }),
  deleteLlamaInstance: (name: string) =>
    _fetch<null>(`/llama/instances/${name}`, { method: 'DELETE' }),
  getLlamaInstanceLogs: (name: string, lines = 100) =>
    _fetch<string[]>(`/llama/instances/${name}/logs?lines=${lines}`),
  updateLlamaInstance: (name: string, body: Partial<LlamaInstanceConfig>, restart = false) =>
    _fetch<LlamaInstance>(`/llama/instances/${name}?restart=${restart}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // Whisper cluster management
  listWhisperClusters: () => _fetch<WhisperCluster[]>('/whisper/clusters'),
  getWhisperCluster: (name: string) => _fetch<WhisperCluster>(`/whisper/clusters/${name}`),
  createWhisperCluster: (body: { name: string } & WhisperClusterConfig) =>
    _fetch<WhisperCluster>('/whisper/clusters', { method: 'POST', body: JSON.stringify(body) }),
  deleteWhisperCluster: (name: string) =>
    _fetch<null>(`/whisper/clusters/${name}`, { method: 'DELETE' }),
  getWhisperClusterLogs: (name: string, lines = 100) =>
    _fetch<string[]>(`/whisper/clusters/${name}/logs?lines=${lines}`),
  updateWhisperCluster: (name: string, body: Partial<WhisperClusterConfig>) =>
    _fetch<WhisperCluster>(`/whisper/clusters/${name}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  listTranscriptionJobs: (limit = 50, offset = 0) =>
    _fetch<WhisperTranscriptionJob[]>(`/whisper/jobs?limit=${limit}&offset=${offset}`),
}
