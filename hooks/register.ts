/**
 * Point d'entrée unique des 10 Mods "Zero-Token" de `crew-mates`.
 * Déclaré dans `hooks/hooks.json` via `"modules": ["./register.ts"]`.
 *
 * Architecture :
 * - Multiplexeur middleware en oignon (`createModBus`) permettant aux 10 mods de
 *   `hooks/mods/*.ts` d'utiliser chacun l'API idiomatique `register(on)` / `($, e, next)`
 *   tout en exposant exactement un handler consolidé par couple `(event, matcher)` au
 *   validateur statique de Claude Code (`claude plugin validate`).
 * - Règles d'or : 0 appel LLM (`$.model.*` / `$.prompt.*` / `prompt.compose` interdits),
 *   0 dépendance npm externe, 0 import `node:*`.
 */

import {
  crewUiState,
  PANE_META,
  resolvePaneRequestId,
  isBandAccumulator,
  renderBandAccumulator,
  type CrewPaneId,
  type HookHandler,
  type ModApi,
  type ModRegistrar,
} from './mods/shared.ts';
import {
  computePromptCacheStatus,
  registerPromptCacheControl,
} from './mods/prompt-cache-control.ts';
import {
  computeTokenWeather,
  registerTokenWeather,
} from './mods/token-weather.ts';
import {
  registerTurnInspector,
  turnInspectorState,
} from './mods/turn-inspector.ts';
import {
  registerStackViewer,
  stackViewerState,
} from './mods/stack-viewer.ts';
import {
  agentFlowState,
  registerAgentFlow,
} from './mods/agent-flow.ts';
import {
  formatCrewRadarLine,
  registerCrewRadar,
} from './mods/crew-radar.ts';
import {
  formatCombinedBatchProgressLine,
  registerBatchProgress,
} from './mods/batch-progress.ts';
import {
  batchBoardState,
  registerBatchDependencyGraph,
} from './mods/batch-dependency-graph.ts';
import {
  registerFileLockMonitor,
} from './mods/file-lock-monitor.ts';
import {
  registerBatchEtaCost,
} from './mods/batch-eta-cost.ts';

interface ModBusBuckets {
  sessionStart: Array<HookHandler<any, any>>;
  sessionEnd: Array<HookHandler<any, any>>;
  turnStart: Array<HookHandler<any, any>>;
  turnComplete: Array<HookHandler<any, any>>;
  toolCall: Array<HookHandler<any, any>>;
  abovePrompt: Array<HookHandler<any, any>>;
  pane: Array<HookHandler<any, any>>;
  commands: Map<string, HookHandler<any, any>>;
}

function createModBus(): { buckets: ModBusBuckets; registrar: ModRegistrar } {
  const buckets: ModBusBuckets = {
    sessionStart: [],
    sessionEnd: [],
    turnStart: [],
    turnComplete: [],
    toolCall: [],
    abovePrompt: [],
    pane: [],
    commands: new Map<string, HookHandler<any, any>>(),
  };

  const registrar: ModRegistrar = (
    event: string,
    matcherOrHandler: Record<string, unknown> | HookHandler<any, any>,
    maybeHandler?: HookHandler<any, any>,
  ) => {
    const hasMatcher = typeof matcherOrHandler === 'object' && matcherOrHandler !== null;
    const matcher = hasMatcher ? (matcherOrHandler as Record<string, unknown>) : undefined;
    const handler = (hasMatcher ? maybeHandler : matcherOrHandler) as HookHandler<any, any>;
    if (typeof handler !== 'function') return;

    switch (event) {
      case 'session.start':
        buckets.sessionStart.push(handler);
        break;
      case 'session.end':
        buckets.sessionEnd.push(handler);
        break;
      case 'turn.start':
        buckets.turnStart.push(handler);
        break;
      case 'turn.complete':
        buckets.turnComplete.push(handler);
        break;
      case 'tool.call':
        buckets.toolCall.push(handler);
        break;
      case 'ui.render':
        if (matcher?.component === 'AbovePrompt') {
          buckets.abovePrompt.push(handler);
        } else if (matcher?.component === 'Pane') {
          buckets.pane.push(handler);
        }
        break;
      case 'command.run':
        if (typeof matcher?.command === 'string') {
          buckets.commands.set(matcher.command, handler);
        }
        break;
      default:
        break;
    }
  };

  return { buckets, registrar };
}

function composeMiddlewareChain(
  handlers: Array<HookHandler<any, any>>,
  api: ModApi,
  initialEvent: unknown,
  terminalNext: (ev: any) => Promise<any>,
): Promise<any> {
  const dispatch = (index: number, currentEvent: any): Promise<any> => {
    if (index >= handlers.length) {
      return Promise.resolve(terminalNext(currentEvent));
    }
    const fn = handlers[index];
    return Promise.resolve(fn(api, currentEvent, (nextEv: any) => dispatch(index + 1, nextEv ?? currentEvent)));
  };
  return dispatch(0, initialEvent);
}

function parseToggleIntent(modeArg: string | undefined, currentValue: boolean): boolean {
  if (modeArg === 'on' || modeArg === 'open' || modeArg === 'show') return true;
  if (modeArg === 'off' || modeArg === 'close' || modeArg === 'hide') return false;
  return !currentValue;
}

export function formatCrewUiOverview(): string {
  const b = crewUiState.bands;
  const p = crewUiState.panes;
  const flag = (v: boolean) => (v ? '🟢 ON' : '⚪ OFF');

  return [
    '🎛️ crew-mates Zero-Token UI (10 Mods 100% locaux)',
    'Usage : /crew-ui [all|radar|progress|board|turns|stack|agents] [on|off]',
    '',
    'Bande unique AbovePrompt (crew à gauche, météo à droite) :',
    `  • radar    (${flag(b.radar)})    — ${formatCrewRadarLine()}`,
    `  • progress (${flag(b.progress)}) — ${formatCombinedBatchProgressLine()}`,
    `  • weather  (${flag(b.weather)})  — ${computeTokenWeather().line}`,
    `  • locks    (${flag(b.locks)})    — Anti-collision multi-sessions (Edit/Write)`,
    '',
    'Volets interactifs (Panes) :',
    `  • board    (${flag(p['crew-board'])})  — /crew-board  (${batchBoardState.allBoards.length} batch(s))`,
    `  • cache    (${flag(p['crew-cache'])})  — /crew-ui cache  (${computePromptCacheStatus().line})`,
    `  • turns    (${flag(p['crew-turns'])})  — /crew-turns  (${turnInspectorState.turns.length} tour(s))`,
    `  • stack    (${flag(p['crew-stack'])})  — /crew-stack  (${stackViewerState.snapshot.modsAndHooks.length} mods/hooks)`,
    `  • agents   (${flag(p['crew-agents'])}) — /crew-agents (${agentFlowState.nodes.length} subagent(s))`,
  ].join('\n');
}

export function register(on: ModRegistrar): void {
  const { buckets, registrar } = createModBus();

  // Initialisation ordonnée des 10 Mods dans le bus modulaire :
  // Étape 3 (Tâches, Batchs & Multi-sessions) + Étape 2 (Visibilité & Contexte)
  registerCrewRadar(registrar);
  registerBatchProgress(registrar);
  registerBatchEtaCost(registrar);
  registerBatchDependencyGraph(registrar);
  registerFileLockMonitor(registrar);
  registerAgentFlow(registrar);
  registerTurnInspector(registrar);
  registerStackViewer(registrar);
  registerTokenWeather(registrar);
  registerPromptCacheControl(registrar);

  on('session.start', async ($, e, next) => {
    const preRegistered = new Set([
      'crew-ui',
      'crew-turns',
      'crew-stack',
      'crew-board',
      'crew-agents',
    ]);

    await $.command
      .register({
        name: 'crew-ui',
        description: 'Contrôler les 10 Mods Zero-Token crew-mates (bandes de statut & volets UI)',
        argumentHint: '[all|radar|progress|board|turns|stack|agents]',
      })
      .catch(() => undefined);
    await $.command
      .register({
        name: 'crew-turns',
        description: 'Ouvrir/fermer le panneau latéral Turn Inspector (0-token)',
      })
      .catch(() => undefined);
    await $.command
      .register({
        name: 'crew-stack',
        description: 'Afficher l’arbre de la stack chargée (CLAUDE.md, règles, MCP, skills, agents, mods)',
      })
      .catch(() => undefined);
    await $.command
      .register({
        name: 'crew-board',
        description: 'Ouvrir/fermer le Kanban & graphe de dépendances du batch (Todo | In Progress | Done | Blocked)',
      })
      .catch(() => undefined);
    await $.command
      .register({
        name: 'crew-agents',
        description: 'Afficher l’arbre d’exécution en direct des subagents crew-mates (0-token)',
      })
      .catch(() => undefined);

    const api: ModApi = {
      ui: {
        resolve: (ev) => $.ui.resolve(ev),
        invalidate: (target) => $.ui.invalidate(target),
        open: (opts) => $.ui.open(opts),
        close: (opts) => $.ui.close(opts),
        toast: (msg) => $.ui.toast(msg),
      },
      command: {
        register: (opts) =>
          preRegistered.has(opts.name) ? Promise.resolve() : $.command.register(opts),
      },
      fs: {
        read: (p) => $.fs.read(p),
        write: (p, c) => $.fs.write(p, c),
        list: (p) => $.fs.list(p),
        stat: (p) => $.fs.stat(p),
      },
      env: {
        get: (k) =>
          k === 'CLAUDE_PROJECT_DIR'
            ? $.env.get('CLAUDE_PROJECT_DIR') || ((e as { cwd?: string }).cwd ?? undefined)
            : k === 'CLAUDE_CACHE_TTL'
              ? $.env.get('CLAUDE_CACHE_TTL')
              : undefined,
      },
    };

    return composeMiddlewareChain(buckets.sessionStart, api, e, next);
  });

  on('turn.start', async ($, e, next) => {
    const api: ModApi = {
      ui: {
        resolve: (ev) => $.ui.resolve(ev),
        invalidate: (target) => $.ui.invalidate(target),
        open: (opts) => $.ui.open(opts),
        close: (opts) => $.ui.close(opts),
        toast: (msg) => $.ui.toast(msg),
      },
      command: { register: (opts) => $.command.register(opts) },
      fs: {
        read: (p) => $.fs.read(p),
        write: (p, c) => $.fs.write(p, c),
        list: (p) => $.fs.list(p),
        stat: (p) => $.fs.stat(p),
      },
      env: {
        get: (k) =>
          k === 'CLAUDE_PROJECT_DIR'
            ? $.env.get('CLAUDE_PROJECT_DIR')
            : k === 'CLAUDE_CACHE_TTL'
              ? $.env.get('CLAUDE_CACHE_TTL')
              : undefined,
      },
    };
    return composeMiddlewareChain(buckets.turnStart, api, e, next);
  });

  on('tool.call', async ($, e, next) => {
    const api: ModApi = {
      ui: {
        resolve: (ev) => $.ui.resolve(ev),
        invalidate: (target) => $.ui.invalidate(target),
        open: (opts) => $.ui.open(opts),
        close: (opts) => $.ui.close(opts),
        toast: (msg) => $.ui.toast(msg),
      },
      command: { register: (opts) => $.command.register(opts) },
      fs: {
        read: (p) => $.fs.read(p),
        write: (p, c) => $.fs.write(p, c),
        list: (p) => $.fs.list(p),
        stat: (p) => $.fs.stat(p),
      },
      env: {
        get: (k) =>
          k === 'CLAUDE_PROJECT_DIR'
            ? $.env.get('CLAUDE_PROJECT_DIR')
            : k === 'CLAUDE_CACHE_TTL'
              ? $.env.get('CLAUDE_CACHE_TTL')
              : undefined,
      },
    };
    return composeMiddlewareChain(buckets.toolCall, api, e, next).catch(() => next(e));
  });

  on('turn.complete', async ($, e, next) => {
    const api: ModApi = {
      ui: {
        resolve: (ev) => $.ui.resolve(ev),
        invalidate: (target) => $.ui.invalidate(target),
        open: (opts) => $.ui.open(opts),
        close: (opts) => $.ui.close(opts),
        toast: (msg) => $.ui.toast(msg),
      },
      command: { register: (opts) => $.command.register(opts) },
      fs: {
        read: (p) => $.fs.read(p),
        write: (p, c) => $.fs.write(p, c),
        list: (p) => $.fs.list(p),
        stat: (p) => $.fs.stat(p),
      },
      env: {
        get: (k) =>
          k === 'CLAUDE_PROJECT_DIR'
            ? $.env.get('CLAUDE_PROJECT_DIR')
            : k === 'CLAUDE_CACHE_TTL'
              ? $.env.get('CLAUDE_CACHE_TTL')
              : undefined,
      },
    };
    // e.usage somme les requêtes du tour ; la taille réelle du contexte vient de la session.
    let enriched: unknown = e;
    const ev = e as Record<string, unknown>;
    if (ev.contextTokens === undefined) {
      try {
        const ctx = (await $.session.usage()).context;
        if (ctx.tokens && ctx.tokens > 0) {
          enriched = { ...ev, contextTokens: ctx.tokens, contextWindow: ctx.window };
        }
      } catch {
        // session.usage indisponible : on garde l'événement tel quel (météo à 0 %)
      }
    }
    return composeMiddlewareChain(buckets.turnComplete, api, enriched, next);
  });

  on('session.end', async ($, e, next) => {
    const api: ModApi = {
      ui: {
        resolve: (ev) => $.ui.resolve(ev),
        invalidate: (target) => $.ui.invalidate(target),
        open: (opts) => $.ui.open(opts),
        close: (opts) => $.ui.close(opts),
        toast: (msg) => $.ui.toast(msg),
      },
      command: { register: (opts) => $.command.register(opts) },
      fs: {
        read: (p) => $.fs.read(p),
        write: (p, c) => $.fs.write(p, c),
        list: (p) => $.fs.list(p),
        stat: (p) => $.fs.stat(p),
      },
      env: {
        get: (k) =>
          k === 'CLAUDE_PROJECT_DIR'
            ? $.env.get('CLAUDE_PROJECT_DIR')
            : k === 'CLAUDE_CACHE_TTL'
              ? $.env.get('CLAUDE_CACHE_TTL')
              : undefined,
      },
    };
    return composeMiddlewareChain(buckets.sessionEnd, api, e, next);
  });

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const api: ModApi = {
      ui: {
        resolve: (ev) => $.ui.resolve(ev),
        invalidate: (target) => $.ui.invalidate(target),
        open: (opts) => $.ui.open(opts),
        close: (opts) => $.ui.close(opts),
        toast: (msg) => $.ui.toast(msg),
      },
      command: { register: (opts) => $.command.register(opts) },
      fs: {
        read: (p) => $.fs.read(p),
        write: (p, c) => $.fs.write(p, c),
        list: (p) => $.fs.list(p),
        stat: (p) => $.fs.stat(p),
      },
      env: {
        get: (k) =>
          k === 'CLAUDE_PROJECT_DIR'
            ? $.env.get('CLAUDE_PROJECT_DIR')
            : k === 'CLAUDE_CACHE_TTL'
              ? $.env.get('CLAUDE_CACHE_TTL')
              : undefined,
      },
    };
    // Une seule ligne : crew à gauche, météo à droite (segments versés par chaque mod)
    const orderedBands = [...buckets.abovePrompt].reverse();
    return composeMiddlewareChain(orderedBands, api, e, next)
      .then((tree) => (isBandAccumulator(tree) ? renderBandAccumulator(tree, $.ui.resolve(e)) : tree))
      .catch(() => next(e));
  });

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    const reqId = resolvePaneRequestId(e as Record<string, unknown>);
    if (
      reqId !== 'crew-turns' &&
      reqId !== 'crew-stack' &&
      reqId !== 'crew-board' &&
      reqId !== 'crew-agents' &&
      reqId !== 'crew-cache'
    ) {
      return next(e);
    }
    const api: ModApi = {
      ui: {
        resolve: (ev) => $.ui.resolve(ev),
        invalidate: (target) => $.ui.invalidate(target),
        open: (opts) => $.ui.open(opts),
        close: (opts) => $.ui.close(opts),
        toast: (msg) => $.ui.toast(msg),
      },
      command: { register: (opts) => $.command.register(opts) },
      fs: {
        read: (p) => $.fs.read(p),
        write: (p, c) => $.fs.write(p, c),
        list: (p) => $.fs.list(p),
        stat: (p) => $.fs.stat(p),
      },
      env: {
        get: (k) =>
          k === 'CLAUDE_PROJECT_DIR'
            ? $.env.get('CLAUDE_PROJECT_DIR')
            : k === 'CLAUDE_CACHE_TTL'
              ? $.env.get('CLAUDE_CACHE_TTL')
              : undefined,
      },
    };
    return composeMiddlewareChain(buckets.pane, api, e, next).catch(() => next(e));
  });

  // Commandes dédiées de chaque volet (interceptées localement, 0-token)
  on('command.run', { command: 'crew-turns' }, async ($, e) => {
    return Promise.resolve()
      .then(() => {
        const handler = buckets.commands.get('crew-turns');
        if (!handler) return { text: '🔍 Commande indisponible.' };
        const api: ModApi = {
          ui: {
            resolve: (ev) => $.ui.resolve(ev),
            invalidate: (target) => $.ui.invalidate(target),
            open: (opts) => $.ui.open(opts),
            close: (opts) => $.ui.close(opts),
            toast: (msg) => $.ui.toast(msg),
          },
          command: { register: (opts) => $.command.register(opts) },
          fs: {
            read: (p) => $.fs.read(p),
            write: (p, c) => $.fs.write(p, c),
            list: (p) => $.fs.list(p),
            stat: (p) => $.fs.stat(p),
          },
          env: {
            get: (k) =>
              k === 'CLAUDE_PROJECT_DIR'
                ? $.env.get('CLAUDE_PROJECT_DIR')
                : k === 'CLAUDE_CACHE_TTL'
                  ? $.env.get('CLAUDE_CACHE_TTL')
                  : undefined,
          },
        };
        return handler(api, e, async () => undefined);
      })
      .catch(() => ({ text: '🔍 Erreur locale sur /crew-turns.' }));
  });

  on('command.run', { command: 'crew-stack' }, async ($, e) => {
    return Promise.resolve()
      .then(() => {
        const handler = buckets.commands.get('crew-stack');
        if (!handler) return { text: '📚 Commande indisponible.' };
        const api: ModApi = {
          ui: {
            resolve: (ev) => $.ui.resolve(ev),
            invalidate: (target) => $.ui.invalidate(target),
            open: (opts) => $.ui.open(opts),
            close: (opts) => $.ui.close(opts),
            toast: (msg) => $.ui.toast(msg),
          },
          command: { register: (opts) => $.command.register(opts) },
          fs: {
            read: (p) => $.fs.read(p),
            write: (p, c) => $.fs.write(p, c),
            list: (p) => $.fs.list(p),
            stat: (p) => $.fs.stat(p),
          },
          env: {
            get: (k) =>
              k === 'CLAUDE_PROJECT_DIR'
                ? $.env.get('CLAUDE_PROJECT_DIR')
                : k === 'CLAUDE_CACHE_TTL'
                  ? $.env.get('CLAUDE_CACHE_TTL')
                  : undefined,
          },
        };
        return handler(api, e, async () => undefined);
      })
      .catch(() => ({ text: '📚 Erreur locale sur /crew-stack.' }));
  });

  on('command.run', { command: 'crew-board' }, async ($, e) => {
    return Promise.resolve()
      .then(() => {
        const handler = buckets.commands.get('crew-board');
        if (!handler) return { text: '📋 Commande indisponible.' };
        const api: ModApi = {
          ui: {
            resolve: (ev) => $.ui.resolve(ev),
            invalidate: (target) => $.ui.invalidate(target),
            open: (opts) => $.ui.open(opts),
            close: (opts) => $.ui.close(opts),
            toast: (msg) => $.ui.toast(msg),
          },
          command: { register: (opts) => $.command.register(opts) },
          fs: {
            read: (p) => $.fs.read(p),
            write: (p, c) => $.fs.write(p, c),
            list: (p) => $.fs.list(p),
            stat: (p) => $.fs.stat(p),
          },
          env: {
            get: (k) =>
              k === 'CLAUDE_PROJECT_DIR'
                ? $.env.get('CLAUDE_PROJECT_DIR')
                : k === 'CLAUDE_CACHE_TTL'
                  ? $.env.get('CLAUDE_CACHE_TTL')
                  : undefined,
          },
        };
        return handler(api, e, async () => undefined);
      })
      .catch(() => ({ text: '📋 Erreur locale sur /crew-board.' }));
  });

  on('command.run', { command: 'crew-agents' }, async ($, e) => {
    return Promise.resolve()
      .then(() => {
        const handler = buckets.commands.get('crew-agents');
        if (!handler) return { text: '🎭 Commande indisponible.' };
        const api: ModApi = {
          ui: {
            resolve: (ev) => $.ui.resolve(ev),
            invalidate: (target) => $.ui.invalidate(target),
            open: (opts) => $.ui.open(opts),
            close: (opts) => $.ui.close(opts),
            toast: (msg) => $.ui.toast(msg),
          },
          command: { register: (opts) => $.command.register(opts) },
          fs: {
            read: (p) => $.fs.read(p),
            write: (p, c) => $.fs.write(p, c),
            list: (p) => $.fs.list(p),
            stat: (p) => $.fs.stat(p),
          },
          env: {
            get: (k) =>
              k === 'CLAUDE_PROJECT_DIR'
                ? $.env.get('CLAUDE_PROJECT_DIR')
                : k === 'CLAUDE_CACHE_TTL'
                  ? $.env.get('CLAUDE_CACHE_TTL')
                  : undefined,
          },
        };
        return handler(api, e, async () => undefined);
      })
      .catch(() => ({ text: '🎭 Erreur locale sur /crew-agents.' }));
  });

  // Commande slash unifiée `/crew-ui [all|radar|progress|board|turns|stack|agents]` (0-token)
  on('command.run', { command: 'crew-ui' }, async ($, e) => {
    return Promise.resolve()
      .then(async () => {
        const rawArgs = String((e as Record<string, unknown>)?.args ?? '').trim();
        const tokens = rawArgs.toLowerCase().split(/\s+/).filter(Boolean);
        const target = tokens[0] || '';
        const modeArg = tokens[1];

        if (!target || target === 'status' || target === 'help') {
          return { text: formatCrewUiOverview() };
        }

        if (target === 'radar') {
          crewUiState.bands.radar = parseToggleIntent(modeArg, crewUiState.bands.radar);
          $.ui.invalidate('ui.render');
          return {
            text: crewUiState.bands.radar
              ? `🟢 Crew Radar activé : ${formatCrewRadarLine()}`
              : '⚪ Crew Radar masqué.',
          };
        }

        if (target === 'progress') {
          crewUiState.bands.progress = parseToggleIntent(modeArg, crewUiState.bands.progress);
          $.ui.invalidate('ui.render');
          return {
            text: crewUiState.bands.progress
              ? `📊 Batch & Task Progress activé : ${formatCombinedBatchProgressLine()}`
              : '⚪ Batch & Task Progress masqué.',
          };
        }

        if (target === 'weather') {
          crewUiState.bands.weather = parseToggleIntent(modeArg, crewUiState.bands.weather);
          $.ui.invalidate('ui.render');
          return {
            text: crewUiState.bands.weather
              ? `☀️ Token Weather activé : ${computeTokenWeather().line}`
              : '⚪ Token Weather masqué.',
          };
        }

        const paneMap: Record<string, CrewPaneId> = {
          board: 'crew-board',
          turns: 'crew-turns',
          stack: 'crew-stack',
          agents: 'crew-agents',
          cache: 'crew-cache',
        };

        if (target in paneMap) {
          const paneId = paneMap[target];
          const nextOpen = parseToggleIntent(modeArg, crewUiState.panes[paneId]);
          crewUiState.panes[paneId] = nextOpen;
          if (target === 'agents' && modeArg) {
            crewUiState.bands.agents = nextOpen;
          }

          if (nextOpen) {
            await $.ui.open({
              id: PANE_META[paneId].id,
              title: PANE_META[paneId].title,
              focus: true,
              immediate: true,
              closeOnEscape: true,
            });
          } else {
            await $.ui.close({ id: PANE_META[paneId].id });
          }
          $.ui.invalidate('ui.render');
          return {
            text: nextOpen
              ? `${PANE_META[paneId].title} ouvert.`
              : `${PANE_META[paneId].title} fermé.`,
          };
        }

        if (target === 'all') {
          const allPanesCurrentlyOpen = (Object.keys(PANE_META) as CrewPaneId[]).every(
            (id) => crewUiState.panes[id],
          );
          const shouldEnable = parseToggleIntent(modeArg, !allPanesCurrentlyOpen);

          const isExplicitOff = modeArg === 'off' || modeArg === 'close' || modeArg === 'hide';
          crewUiState.bands.radar = isExplicitOff ? false : true;
          crewUiState.bands.progress = isExplicitOff ? false : true;
          crewUiState.bands.weather = isExplicitOff ? false : true;
          crewUiState.bands.agents = isExplicitOff ? false : true;
          crewUiState.bands.locks = true;

          for (const paneId of Object.keys(PANE_META) as CrewPaneId[]) {
            crewUiState.panes[paneId] = shouldEnable;
            if (shouldEnable) {
              await $.ui.open({
                id: PANE_META[paneId].id,
                title: PANE_META[paneId].title,
                focus: paneId === 'crew-board',
                immediate: true,
                closeOnEscape: true,
              });
            } else {
              await $.ui.close({ id: PANE_META[paneId].id });
            }
          }

          $.ui.invalidate('ui.render');
          return {
            text: shouldEnable
              ? '🎛️ Tous les volets et bandes Zero-Token crew-mates sont ouverts.'
              : '⚪ Volets Zero-Token crew-mates fermés.',
          };
        }

        return {
          text: `❓ Sous-commande inconnue "${target}". Utilisez : /crew-ui [all|radar|progress|board|turns|stack|agents]`,
        };
      })
      .catch(() => ({ text: '❌ Erreur locale lors de l’exécution de /crew-ui.' }));
  });
}

export default register;
