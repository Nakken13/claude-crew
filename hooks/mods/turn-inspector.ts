/**
 * Mod 3 — turn-inspector.ts
 *
 * Panneau latéral (`/crew-turns`) historisant chaque tour :
 * tokens in/out, cache read/write, outils appelés, durée et barre de progression.
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  extractTurnUsage,
  formatCompactTokens,
  formatDurationCompact,
  PANE_META,
  renderBar,
  resolvePaneRequestId,
  type ModRegistrar,
} from './shared.ts';

export interface TurnRecord {
  turnNumber: number;
  startedAtMs: number;
  completedAtMs: number;
  durationMs: number;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheWriteTokens: number;
  contextTokens: number;
  contextWindow: number;
  tools: string[];
}

export interface TurnInspectorState {
  turns: TurnRecord[];
  activeTurnStartMs: number | null;
  activeTurnTools: Map<string, number>;
}

export const turnInspectorState: TurnInspectorState = {
  turns: [],
  activeTurnStartMs: null,
  activeTurnTools: new Map<string, number>(),
};

const MAX_STORED_TURNS = 50;

export function summarizeToolCounts(toolCounts: Map<string, number>): string[] {
  const out: string[] = [];
  for (const [name, count] of toolCounts.entries()) {
    out.push(count > 1 ? `${name}×${count}` : name);
  }
  return out;
}

export function formatTurnRow(turn: TurnRecord): string {
  const ratio = turn.contextWindow > 0 ? turn.contextTokens / turn.contextWindow : 0;
  const bar = renderBar(ratio, 6);
  const inFmt = formatCompactTokens(turn.inputTokens);
  const outFmt = formatCompactTokens(turn.outputTokens);
  const crFmt = formatCompactTokens(turn.cacheReadTokens);
  const cwFmt = formatCompactTokens(turn.cacheWriteTokens);
  const durFmt = formatDurationCompact(turn.durationMs);
  const toolsFmt = turn.tools.length > 0 ? turn.tools.join(', ') : '—';

  return `#${String(turn.turnNumber).padStart(2, '0')} ${bar} ${durFmt.padStart(5, ' ')} | in:${inFmt} out:${outFmt} | R:${crFmt} W:${cwFmt} | 🔧 ${toolsFmt}`;
}

export function registerTurnInspector(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    await $.command
      .register({
        name: 'crew-turns',
        description: 'Ouvrir/fermer le panneau latéral Turn Inspector (0-token)',
      })
      .catch(() => undefined);
    return next(e);
  });

  on('turn.start', async (_$, e, next) => {
    turnInspectorState.activeTurnStartMs = Date.now();
    turnInspectorState.activeTurnTools.clear();
    return next(e);
  });

  on('tool.call', async (_$, e, next) => {
    try {
      const ev = (e || {}) as Record<string, unknown>;
      const toolName = String(ev.tool ?? ev.name ?? 'Tool').trim();
      if (toolName) {
        if (turnInspectorState.activeTurnStartMs === null) {
          turnInspectorState.activeTurnStartMs = Date.now();
        }
        const prev = turnInspectorState.activeTurnTools.get(toolName) || 0;
        turnInspectorState.activeTurnTools.set(toolName, prev + 1);
      }
    } catch {
      // Never block tool execution
    }
    return next(e);
  });

  on('turn.complete', async ($, e, next) => {
    const nowMs = Date.now();
    const ev = (e || {}) as Record<string, unknown>;
    const usage = extractTurnUsage(ev);
    const explicitDuration =
      typeof ev.durationMs === 'number'
        ? ev.durationMs
        : typeof ev.duration_ms === 'number'
          ? ev.duration_ms
          : null;
    const startedAtMs =
      turnInspectorState.activeTurnStartMs ??
      (explicitDuration !== null ? nowMs - explicitDuration : nowMs);
    const durationMs =
      explicitDuration !== null ? Math.max(0, explicitDuration) : Math.max(0, nowMs - startedAtMs);

    const turnNumber = crewRuntimeState.turnCount + 1;
    crewRuntimeState.turnCount = turnNumber;
    crewRuntimeState.totalInputTokens += usage.inputTokens;
    crewRuntimeState.totalOutputTokens += usage.outputTokens;

    const record: TurnRecord = {
      turnNumber,
      startedAtMs,
      completedAtMs: nowMs,
      durationMs,
      inputTokens: usage.inputTokens,
      outputTokens: usage.outputTokens,
      cacheReadTokens: usage.cacheReadInputTokens,
      cacheWriteTokens: usage.cacheCreationInputTokens,
      contextTokens: usage.contextTokens,
      contextWindow: usage.contextWindow,
      tools: summarizeToolCounts(turnInspectorState.activeTurnTools),
    };

    turnInspectorState.turns.push(record);
    if (turnInspectorState.turns.length > MAX_STORED_TURNS) {
      turnInspectorState.turns.splice(0, turnInspectorState.turns.length - MAX_STORED_TURNS);
    }

    turnInspectorState.activeTurnStartMs = null;
    turnInspectorState.activeTurnTools.clear();

    $.ui.invalidate('ui.render');
    return next(e);
  });

  on('command.run', { command: 'crew-turns' }, async ($, e) => {
    try {
      const arg = String((e as Record<string, unknown>)?.args ?? '').trim().toLowerCase();
      const shouldOpen =
        arg === 'open' || arg === 'on'
          ? true
          : arg === 'close' || arg === 'off'
            ? false
            : !crewUiState.panes['crew-turns'];

      crewUiState.panes['crew-turns'] = shouldOpen;
      if (shouldOpen) {
        await $.ui.open({
          id: PANE_META['crew-turns'].id,
          title: PANE_META['crew-turns'].title,
          focus: true,
          immediate: true,
          closeOnEscape: true,
        });
      } else {
        await $.ui.close({ id: PANE_META['crew-turns'].id });
      }
      $.ui.invalidate('ui.render');
      return {
        text: shouldOpen
          ? `🔍 Turn Inspector ouvert (${turnInspectorState.turns.length} tour(s) enregistrés).`
          : '🔍 Turn Inspector fermé.',
      };
    } catch {
      return { text: '🔍 Impossible de basculer le panneau Turn Inspector.' };
    }
  });

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (resolvePaneRequestId(e as Record<string, unknown>) !== PANE_META['crew-turns'].id) {
      return next(e);
    }

    const { Box, Text } = $.ui.resolve(e);
    const totalIn = formatCompactTokens(crewRuntimeState.totalInputTokens);
    const totalOut = formatCompactTokens(crewRuntimeState.totalOutputTokens);
    const totalCR = formatCompactTokens(crewRuntimeState.totalCacheReadTokens);
    const totalCW = formatCompactTokens(crewRuntimeState.totalCacheCreationTokens);

    const rows =
      turnInspectorState.turns.length === 0
        ? [
            Text({
              dimColor: true,
              children: ['Aucun tour complété dans cette session pour le moment.'],
            }),
          ]
        : [...turnInspectorState.turns]
            .reverse()
            .slice(0, 25)
            .map((turn) =>
              Text({
                color: turn.contextTokens / Math.max(1, turn.contextWindow) >= 0.75 ? 'yellow' : undefined,
                children: [formatTurnRow(turn)],
              }),
            );

    return Box({
      flexDirection: 'column',
      padding: 1,
      gap: 1,
      children: [
        Text({
          bold: true,
          color: 'cyan',
          children: [`🔍 Historique des tours (${turnInspectorState.turns.length})`],
        }),
        Text({
          dimColor: true,
          children: [`Cumul session — in:${totalIn} · out:${totalOut} · cache R:${totalCR} W:${totalCW}`],
        }),
        Box({
          flexDirection: 'column',
          children: rows,
        }),
      ],
    });
  });
}

export const register = registerTurnInspector;
