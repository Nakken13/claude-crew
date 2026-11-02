import { atom, read, update } from 'claude-code'
import type { Register, SessionUsage } from 'claude-code'

import type { UsageLine } from '../types'

const ORANGE = '#ff8c00'

const line = atom({ plugin: 'usage-orange', key: 'line' } as const, null)

const LABELS: Record<string, string> = {
  five_hour: '5h',
  seven_day: '7j',
  spend_limit: 'budget',
}

const resetIn = (iso?: string): string => {
  if (!iso) return ''
  const ms = Date.parse(iso) - Date.now()
  if (!Number.isFinite(ms) || ms <= 0) return ''
  const min = Math.round(ms / 60000)
  if (min < 60) return ` (reset ${min}m)`
  const h = Math.floor(min / 60)
  if (h < 48) return ` (reset ${h}h${String(min % 60).padStart(2, '0')})`
  return ` (reset ${Math.round(h / 24)}j)`
}

const format = (u: UsageLine): string => {
  const parts: string[] = []
  for (const l of u.limits) {
    parts.push(`${LABELS[l.kind] ?? l.kind} ${Math.round(l.percentUsed)}%${resetIn(l.resetsAt)}`)
  }
  if (u.contextPercent !== null) parts.push(`ctx ${Math.round(u.contextPercent)}%`)
  if (u.costUsd !== null) parts.push(`$${u.costUsd.toFixed(2)}`)
  return parts.join('  ·  ')
}

function toLine(usage: SessionUsage): UsageLine {
  return {
    limits: usage.rateLimits.map(l => ({
      kind: l.kind,
      percentUsed: l.percentUsed,
      resetsAt: l.resetsAt,
    })),
    contextPercent: usage.context.percent ?? null,
    costUsd: usage.cost?.usd ?? null,
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const usage = await $.session.usage()
    await update($, line, () => toLine(usage))
    return next(e)
  })

  on('session.measure', async ($, e, next) => {
    const usage = await $.session.usage()
    await update($, line, () => toLine(usage))
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const u = await read($, line)
    if (e.props.hasSurvey || u === null) return next(e)

    const text = format(u)
    if (text === '') return next(e)

    const { Box, Text } = $.ui.resolve(e)

    return (
      <Box>
        <Text color={ORANGE} bold>
          Usage{' '}
        </Text>
        <Text color={ORANGE}>{text}</Text>
      </Box>
    )
  })
}
