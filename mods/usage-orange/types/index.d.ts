export type UsageLine = {
  limits: { kind: string; percentUsed: number; resetsAt?: string }[]
  contextPercent: number | null
  costUsd: number | null
}

declare module 'claude-code' {
  interface PluginState {
    'usage-orange': { line: UsageLine | null }
  }
}
