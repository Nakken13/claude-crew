/**
 * Mod 11 — usage-band.ts
 *
 * Stats `/usage` (limites 5h / 7j, contexte, coût) sur la bande AbovePrompt,
 * en orange, côté droit. Lecture seule de `$.session.usage()` ; 0 appel LLM.
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
  if (min < 60) return ` (reset ${min}m)`;
  const h = Math.floor(min / 60);
  if (h < 48) return ` (reset ${h}h${String(min % 60).padStart(2, '0')})`;
  return ` (reset ${Math.round(h / 24)}j)`;
}

export function formatUsageLine(u: UsageSnapshot | null = usageBandState.snapshot): string {
  if (!u) return 'Usage indisponible';
  const parts: string[] = [];
  for (const l of u.limits) {
    parts.push(`${LABELS[l.kind] ?? l.kind} ${Math.round(l.percentUsed)}%${resetIn(l.resetsAt)}`);
  }
  if (u.contextPercent !== null) parts.push(`ctx ${Math.round(u.contextPercent)}%`);
  if (u.costUsd !== null) parts.push(`$${u.costUsd.toFixed(2)}`);
  return parts.length ? `Usage ${parts.join('  ·  ')}` : 'Usage indisponible';
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
    // ancien état conservé
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

  on('ui.render', { component: 'AbovePrompt' }, async (_$, e, next) => {
    const prev = await next(e);
    if (!crewUiState.bands.usage || !usageBandState.snapshot) return prev;
    const text = formatUsageLine();
    if (text === 'Usage indisponible') return prev;
    return addBandSegments(prev, { slot: 'right', color: ORANGE, bold: false, text });
  });
}

export const register = registerUsageBand;
