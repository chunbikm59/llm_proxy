export function fmtNum(n: number): string {
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return String(n)
}

export function fmtCost(n: number): string {
  if (n >= 1) return '$' + n.toFixed(4)
  if (n >= 0.0001) return '$' + n.toFixed(6)
  return '$' + n.toFixed(8)
}

export function fmtDate(s: string): string {
  return s ? s.replace('T', ' ').slice(0, 16) : ''
}
