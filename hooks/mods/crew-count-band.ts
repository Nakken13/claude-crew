/**
 * Mod 12 — crew-count-band.ts
 *
 * `Crew N` en rouge, sur la même ligne, à gauche juste après le radar crew (🟢 ⚡ 📋 ⏸️), avant la météo :
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
const AFTER_CREW = 40; // à gauche, après radar (10), progression (20) et agents (30)

export const crewCountState: { launchable: number | null; error: string | null } = { launchable: null, error: null };

export function formatCrewCount(n: number | null = crewCountState.launchable): string {
  if (n !== null) return `Crew ${n}`;
  // Échec du comptage : `Crew ?` seul (le détail reste dans crewCountState.error).
  return crewCountState.error ? 'Crew ?' : '';
}

// Sécurité : on n'exécute QUE le script livré avec le plugin (jamais un `crew_hook.py` pris dans le
// repo ouvert, qui peut être non fiable). cwd = racine du plugin ; le projet passe par CLAUDE_PROJECT_DIR.
let inFlight: Promise<void> | null = null;

// Un seul calcul à la fois (évite d'empiler des sous-processus python).
function refresh($: unknown): Promise<void> {
  inFlight ??= doRefresh($).finally(() => {
    inFlight = null;
  });
  return inFlight;
}

async function doRefresh($: unknown): Promise<void> {
  const fail = (why: string): void => {
    crewCountState.error = why.replace(/\s+/g, ' ').slice(0, 70);
  };
  try {
    const api = $ as { process?: { run?: (argv: string[], init?: object) => Promise<any> }; plugin?: { root?: () => string | undefined } };
    const run = api.process?.run;
    const pluginRoot = api.plugin?.root?.();
    const project = crewRuntimeState.projectRoot;
    if (!run) return fail('no $.process.run');
    if (!pluginRoot) return fail('no plugin root');
    if (!project) return fail('no project root');
    const script = `${pluginRoot}/scripts/crew_hook.py`;
    let last = 'no python';
    for (const py of ['python3', 'python', 'py']) {
      try {
        const r = await run([py, script, 'count'], {
          cwd: pluginRoot,
          env: { CLAUDE_PROJECT_DIR: project },
          timeoutMs: 10_000,
        });
        if (r?.exitCode !== 0) {
          last = `${py} exit ${r?.exitCode} ${String(r?.stderr ?? '')}`;
          continue;
        }
        const n = JSON.parse(String(r.stdout)).launchable_count;
        if (typeof n !== 'number') {
          last = `${py} bad json`;
          continue;
        }
        crewCountState.launchable = n;
        crewCountState.error = null;
        return;
      } catch (err) {
        last = `${py}: ${(err as Error)?.message ?? err}`;
      }
    }
    fail(last);
  } catch (err) {
    fail(`refresh: ${(err as Error)?.message ?? err}`);
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
    // Jamais d'await ici : un sous-processus lent ne doit pas bloquer le rendu de toute la barre.
    // Le compteur est alimenté par session.start / turn.complete.
    const text = formatCrewCount();
    if (!text) return prev;
    return addBandSegments(prev, { slot: 'left', color: RED, bold: true, text, order: AFTER_CREW });
  });
}

export const register = registerCrewCountBand;
