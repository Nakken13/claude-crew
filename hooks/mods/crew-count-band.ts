/**
 * Mod 12 — crew-count-band.ts
 *
 * `Crew x/n` en rouge, sur la même ligne, à gauche juste après le radar crew (🟢 ⚡ 📋 ⏸️), avant la météo :
 * x = batchs en cours (hors pause), n = en cours + lançables en parallèle (même calcul que `/crew-count`,
 * via `crew_hook.py count`). Masqué tant que le comptage n'a pas réussi (jamais de valeur par défaut
 * ni périmée). Recalculé après un outil qui touche `crew/` et, entre les tours, dès que l'état crew
 * change sur disque (autre session). 0 appel LLM.
 */

import {
  addBandSegments,
  coalesce,
  crewRuntimeState,
  crewUiState,
  ensurePoller,
  filterCrewTaskSlugs,
  joinPath,
  touchesCrewState,
  type HookHandler,
  type ModApi,
  type ModRegistrar,
} from './shared.ts';

const RED = '#ff3b30';
const AFTER_CREW = 40; // à gauche, après radar (10), progression (20) et agents (30)

// active = batchs en cours (tâche en CURRENT_TASKS ; les PAUSED ne comptent pas) ; launchable = lançables en plus maintenant.
export const crewCountState: { launchable: number | null; active: number; error: string | null } = {
  launchable: null,
  active: 0,
  error: null,
};

// `Crew x/n` : x = batchs en cours, n = en cours + lançables (max en parallèle avec les zones actuelles ; les batchs en pause sont mis de côté).
// Inconnu ou en échec : chaîne vide → segment masqué (le détail de l'échec reste dans crewCountState.error).
export function formatCrewCount(n: number | null = crewCountState.launchable, x: number = crewCountState.active): string {
  return n !== null ? `Crew ${x}/${x + n}` : '';
}

// Sécurité : on n'exécute QUE le script livré avec le plugin (jamais un `crew_hook.py` pris dans le
// repo ouvert, qui peut être non fiable). cwd = racine du plugin ; le projet passe par CLAUDE_PROJECT_DIR.
// Un seul calcul à la fois (évite d'empiler des sous-processus python) ; un appel pendant un calcul en
// relance un seul après lui, qui relit le disque : un comptage parti avant un `git mv` n'est jamais le dernier.
const refresh = coalesce(doRefresh);

async function doRefresh($: unknown, project: string): Promise<void> {
  const fail = (why: string): void => {
    crewCountState.launchable = null;
    lastSignature = null; // échec passager (timeout…) : le prochain poll retente au lieu d'attendre un changement
    crewCountState.error = why.replace(/\s+/g, ' ').slice(0, 70);
  };
  try {
    const api = $ as { process?: { run?: (argv: string[], init?: object) => Promise<any> }; plugin?: { root?: () => string | undefined } };
    const run = api.process?.run;
    const pluginRoot = api.plugin?.root?.();
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
        const parsed = JSON.parse(String(r.stdout));
        const n = parsed.launchable_count;
        if (typeof n !== 'number') {
          last = `${py} bad json`;
          continue;
        }
        crewCountState.launchable = n;
        crewCountState.active =
          typeof parsed.running_count === 'number' ? parsed.running_count : Array.isArray(parsed.active) ? parsed.active.length : 0;
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

// Dossier projet lu dans l'env (comme les autres mods) : au session.start, le radar n'a pas
// forcément encore renseigné crewRuntimeState.projectRoot (défaut '.').
const projectOf = async ($: { env: { get: (k: string) => unknown } }): Promise<string> =>
  String((await $.env.get('CLAUDE_PROJECT_DIR')) || crewRuntimeState.projectRoot || '.');

// Empreinte de ce que lit `crew_hook.py count` : on ne relance python que si elle change.
let lastSignature: string | null = null;
async function crewSignature($: ModApi, project: string): Promise<string> {
  const root = crewRuntimeState.mainRoot || project;
  const list = async (rel: string) =>
    filterCrewTaskSlugs(await $.fs.list(joinPath(root, rel)).catch(() => [])).sort().join(',');
  const read = (rel: string) => $.fs.read(joinPath(root, rel)).catch(() => '');
  return [
    await list('crew/TODO'),
    await list('crew/CURRENT_TASKS'),
    await list('crew/PAUSED'),
    await read('crew/CLAUDE_BATCH.md'),
    await read('crew/CLAUDE_CONTEXT/crew_lock.json'),
    // Mode collab : seules mes tâches comptent (liste des tâches des autres + activation du mode).
    await read('crew/CLAUDE_CONTEXT/crew_ignored.json'),
    await read('crew/CLAUDE_CONTEXT/CREW_CONFIG.md'),
  ].join('|');
}

/**
 * Recompte seulement si l'état crew a changé sur disque (autre session, git mv, git pull…), ou toujours
 * avec `force` (fin de tour). La signature ne couvre pas la ref locale des claims (lue par python en mode
 * collab) : un claim récupéré entre deux tours n'apparaît qu'au prochain `turn.complete`.
 */
export async function pollCrewCount($: ModApi, force = false): Promise<void> {
  const project = await projectOf($);
  const sig = await crewSignature($, project);
  if (!force && sig === lastSignature) return;
  lastSignature = sig;
  const before = formatCrewCount();
  await refresh($, project);
  if (force || formatCrewCount() !== before) $.ui.invalidate('ui.render');
}

export function registerCrewCountBand(on: ModRegistrar): void {
  // Début de session et fin de tour : recompte forcé (la ref des claims n'est pas dans la signature).
  const forced: HookHandler<any, any> = async ($, e, next) => {
    await pollCrewCount($, true);
    ensurePoller('crew-count', () => pollCrewCount($));
    return next(e);
  };
  on('session.start', forced);
  on('turn.complete', forced);

  // Tâche déplacée pendant le tour (git mv, /crew-start, Write sous crew/) : recompte juste après l'outil.
  on('tool.call', async ($, e, next) => {
    const result = await next(e);
    if (touchesCrewState(e as Record<string, unknown>)) await pollCrewCount($).catch(() => undefined);
    return result;
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
