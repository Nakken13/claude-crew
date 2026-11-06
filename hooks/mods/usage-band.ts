/**
 * Mod 11 — usage-band.ts
 *
 * `/usage` stats (5h / 7d limits, context, cost) on the AbovePrompt band,
 * in orange, right side. Read-only use of `$.session.usage()`; 0 LLM calls.
 */

import {
  addBandSegments,
  crewUiState,
  type ModRegistrar,
} from './shared.ts';

const ORANGE = '#ff8c00';

const LABELS: Record<string, string> = {
  five_hour: '5h',
  seven_day: '7j',
  spend_limit: 'budget',
};

export interface UsageSnapshot {
  limits: Array<{ kind: string; percentUsed: number; resetsAt?: string }>;
  contextPercent: number | null;
  costUsd: number | null;
}

export const usageBandState: { snapshot: UsageSnapshot | null } = { snapshot: null };

function resetIn(iso?: string): string {
  if (!iso) return '';
  const ms = Date.parse(iso) - Date.now();
  if (!Number.isFinite(ms) || ms <= 0) return '';
  const min = Math.round(ms / 60000);
  if (min < 60) return ` ↻${min}m`;
  const h = Math.floor(min / 60);
  if (h < 48) return ` ↻${h}h${String(min % 60).padStart(2, '0')}`;
  return ` ↻${Math.round(h / 24)}j`;
}

export function formatUsageLine(u: UsageSnapshot | null = usageBandState.snapshot): string {
  if (!u) return 'Usage indisponible';
  const parts: string[] = [];
  for (const l of u.limits) {
    parts.push(`${LABELS[l.kind] ?? l.kind} ${Math.round(l.percentUsed)}%${resetIn(l.resetsAt)}`);
  }
  if (u.costUsd !== null) parts.push(`$${u.costUsd.toFixed(2)}`);
  return parts.length ? parts.join('   │   ') : 'Usage indisponible';
}

async function refresh($: unknown): Promise<void> {
  try {
    const session = ($ as { session?: { usage?: () => Promise<any> } }).session;
    if (!session?.usage) return;
    const u = await session.usage();
    usageBandState.snapshot = {
      limits: Array.isArray(u?.rateLimits)
        ? u.rateLimits.map((l: any) => ({
            kind: String(l.kind),
            percentUsed: Number(l.percentUsed) || 0,
            resetsAt: l.resetsAt,
          }))
        : [],
      contextPercent: typeof u?.context?.percent === 'number' ? u.context.percent : null,
      costUsd: typeof u?.cost?.usd === 'number' ? u.cost.usd : null,
    };
  } catch {
    // previous state kept
  }
}

export function registerUsageBand(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    await refresh($);
    return next(e);
  });

  on('turn.complete', async ($, e, next) => {
    await refresh($);
    $.ui.invalidate('ui.render');
    return next(e);
  });

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const prev = await next(e);
    if (!crewUiState.bands.usage) return prev;
    // After /reload-plugins neither session.start nor turn.complete fires: read on first render.
    if (!usageBandState.snapshot) await refresh($);
    if (!usageBandState.snapshot) return prev;
    const text = formatUsageLine();
    if (text === 'Usage indisponible') return prev;
    return addBandSegments(prev, { slot: 'right', color: ORANGE, bold: false, text });
  });
}

export const register = registerUsageBand;
