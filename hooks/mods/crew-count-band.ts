/**
 * Mod 12 — crew-count-band.ts
 *
 * `Crew N` en rouge, à droite sur la même ligne que la météo (juste après) :
 * N = nombre de sessions lançables en parallèle (même calcul que `/crew-count`,
 * via `crew_hook.py count`). 0 appel LLM.
 */

import {
  addBandSegments,
  crewRuntimeState,
  crewUiState,
  type ModRegistrar,
} from './shared.ts';

const RED = '#ff3b30';
const AFTER_WEATHER = 110; // la météo n'a pas d'`order` (défaut 100)

export const crewCountState: { launchable: number | null } = { launchable: null };

export function formatCrewCount(n: number | null = crewCountState.launchable): string {
  return n === null ? '' : `Crew ${n}`;
}

async function refresh($: unknown): Promise<void> {
  try {
    const run = ($ as { process?: { run?: (argv: string[], init?: object) => Promise<any> } }).process?.run;
    const root = crewRuntimeState.projectRoot;
    if (!run || !root) return;
    for (const script of [`${root}/crew/crew_hook.py`, `${root}/scripts/crew_hook.py`]) {
      for (const py of ['python', 'python3', 'py']) {
        try {
          const r = await run([py, script, 'count'], {
            cwd: root,
            env: { CLAUDE_PROJECT_DIR: root },
            timeoutMs: 10_000,
          });
          if (r?.exitCode !== 0) continue;
          const n = JSON.parse(String(r.stdout)).launchable_count;
          if (typeof n !== 'number') continue;
          crewCountState.launchable = n;
          return;
        } catch {
          // interpréteur / script suivant
        }
      }
    }
  } catch {
    // ancien état conservé
  }
}

export function registerCrewCountBand(on: ModRegistrar): void {
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
    if (!crewUiState.bands.count) return prev;
    if (crewCountState.launchable === null) await refresh($);
    const text = formatCrewCount();
    if (!text) return prev;
    return addBandSegments(prev, { slot: 'right', color: RED, bold: true, text, order: AFTER_WEATHER });
  });
}

export const register = registerCrewCountBand;
