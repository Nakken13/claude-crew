/**
 * Single entry point for the 10 "Zero-Token" Mods of `crew-mates`.
 * Declared in `hooks/hooks.json` via `"modules": ["./register.ts"]`.
 *
 * Architecture:
 * - Onion-style middleware multiplexer (`createModBus`) that lets the 10 mods of
 *   `hooks/mods/*.ts` each use the idiomatic `register(on)` / `($, e, next)` API
 *   while exposing exactly one consolidated handler per `(event, matcher)` pair to
 *   Claude Code's static validator (`claude plugin validate`).
 * - Golden rules: 0 LLM calls (`$.model.*` / `$.prompt.*` / `prompt.compose` forbidden),
 *   0 external npm dependencies, 0 `node:*` imports.
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
import {
  formatUsageLine,
  registerUsageBand,
} from './mods/usage-band.ts';

import { registerCrewCountBand } from './mods/crew-count-band.ts';

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

// $.env.get is asynchronous in the engine; the mods read env synchronously: resolve it once.
const envCache: Record<string, string | undefined> = {};

async function refreshEnvCache(
  $: { env: { get: (name: string) => unknown } },
  cwd?: string,
): Promise<void> {
  const str = (v: unknown) => (typeof v === 'string' && v ? v : undefined);
  envCache.CLAUDE_PROJECT_DIR = await Promise.resolve($.env.get('CLAUDE_PROJECT_DIR')).then(str, () => undefined);
  envCache.CLAUDE_CACHE_TTL = await Promise.resolve($.env.get('CLAUDE_CACHE_TTL')).then(str, () => undefined);
  if (!envCache.CLAUDE_PROJECT_DIR && cwd) envCache.CLAUDE_PROJECT_DIR = cwd;
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
    '🎛️ crew-mates Zero-Token UI (10 fully local Mods)',
    'Usage: /crew-ui [all|radar|progress|usage|board|turns|stack|agents] [on|off]',
    '',
    'Single AbovePrompt band (crew on the left, weather on the right):',
    `  • radar    (${flag(b.radar)})    — ${formatCrewRadarLine()}`,
    `  • progress (${flag(b.progress)}) — ${formatCombinedBatchProgressLine()}`,
    `  • weather  (${flag(b.weather)})  — ${computeTokenWeather().line}`,
    `  • usage    (${flag(b.usage)})    — ${formatUsageLine()}`,
    `  • locks    (${flag(b.locks)})    — Multi-session anti-collision (Edit/Write)`,
    '',
    'Interactive panes:',
    `  • board    (${flag(p['crew-board'])})  — /crew-board  (${batchBoardState.allBoards.length} batch(s))`,
    `  • cache    (${flag(p['crew-cache'])})  — /crew-ui cache  (${computePromptCacheStatus().line})`,
    `  • turns    (${flag(p['crew-turns'])})  — /crew-turns  (${turnInspectorState.turns.length} turn(s))`,
    `  • stack    (${flag(p['crew-stack'])})  — /crew-stack  (${stackViewerState.snapshot.modsAndHooks.length} mods/hooks)`,
    `  • agents   (${flag(p['crew-agents'])}) — /crew-agents (${agentFlowState.nodes.length} subagent(s))`,
  ].join('\n');
}

export function register(on: ModRegistrar): void {
  const { buckets, registrar } = createModBus();

  // Ordered initialization of the 10 Mods in the modular bus:
  // Step 3 (Tasks, Batches & Multi-sessions) + Step 2 (Visibility & Context)
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
  registerUsageBand(registrar);
  registerCrewCountBand(registrar);

  on('session.start', async ($, e, next) => {
    await refreshEnvCache($, (e as { cwd?: string }).cwd);
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
        description: 'Control the 10 crew-mates Zero-Token Mods (status bands & UI panes)',
        argumentHint: '[all|radar|progress|usage|board|turns|stack|agents]',
      })
      .catch(() => undefined);
    await $.command
      .register({
        name: 'crew-turns',
        description: 'Open/close the Turn Inspector side panel (0-token)',
      })
      .catch(() => undefined);
    await $.command
      .register({
        name: 'crew-stack',
        description: 'Show the loaded stack tree (CLAUDE.md, rules, MCP, skills, agents, mods)',
      })
      .catch(() => undefined);
    await $.command
      .register({
        name: 'crew-board',
        description: 'Open/close the batch Kanban & dependency graph (Todo | In Progress | Done | Blocked)',
      })
      .catch(() => undefined);
    await $.command
      .register({
        name: 'crew-agents',
        description: 'Show the live execution tree of crew-mates subagents (0-token)',
      })
      .catch(() => undefined);

    // Bands are active by default; panes are opened here (equivalent of `/crew-ui all`).
    for (const paneId of Object.keys(PANE_META) as CrewPaneId[]) {
      crewUiState.panes[paneId] = true;
      await Promise.resolve(
        $.ui.open({
          id: PANE_META[paneId].id,
          title: PANE_META[paneId].title,
          immediate: true,
          closeOnEscape: true,
        }),
      ).catch(() => undefined);
    }

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
      env: { get: (k) => envCache[k] },
      session: { usage: () => ($ as any).session.usage() },
      process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
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
      env: { get: (k) => envCache[k] },
      session: { usage: () => ($ as any).session.usage() },
      process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
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
      env: { get: (k) => envCache[k] },
      session: { usage: () => ($ as any).session.usage() },
      process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
    };
    return composeMiddlewareChain(buckets.toolCall, api, e, next).catch(() => next(e));
  });

  on('turn.complete', async ($, e, next) => {
    await refreshEnvCache($);
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
      env: { get: (k) => envCache[k] },
      session: { usage: () => ($ as any).session.usage() },
      process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
    };
    // e.usage sums the turn's requests; the real context size comes from the session.
    let enriched: unknown = e;
    const ev = e as Record<string, unknown>;
    if (ev.contextTokens === undefined) {
      try {
        const ctx = (await $.session.usage()).context;
        if (ctx.tokens && ctx.tokens > 0) {
          enriched = { ...ev, contextTokens: ctx.tokens, contextWindow: ctx.window };
        }
      } catch {
        // session.usage unavailable: keep the event as is (weather at 0 %)
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
      env: { get: (k) => envCache[k] },
      session: { usage: () => ($ as any).session.usage() },
      process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
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
      env: { get: (k) => envCache[k] },
      session: { usage: () => ($ as any).session.usage() },
      process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
    };
    // Single line: crew on the left, weather on the right (segments contributed by each mod)
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
      env: { get: (k) => envCache[k] },
      session: { usage: () => ($ as any).session.usage() },
      process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
    };
    return composeMiddlewareChain(buckets.pane, api, e, next).catch(() => next(e));
  });

  // Dedicated command of each pane (intercepted locally, 0-token)
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
          env: { get: (k) => envCache[k] },
          session: { usage: () => ($ as any).session.usage() },
          process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
        };
        return handler(api, e, async () => undefined);
      })
      .catch(() => ({ text: '🔍 Local error on /crew-turns.' }));
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
          env: { get: (k) => envCache[k] },
          session: { usage: () => ($ as any).session.usage() },
          process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
        };
        return handler(api, e, async () => undefined);
      })
      .catch(() => ({ text: '📚 Local error on /crew-stack.' }));
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
          env: { get: (k) => envCache[k] },
          session: { usage: () => ($ as any).session.usage() },
          process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
        };
        return handler(api, e, async () => undefined);
      })
      .catch(() => ({ text: '📋 Local error on /crew-board.' }));
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
          env: { get: (k) => envCache[k] },
          session: { usage: () => ($ as any).session.usage() },
          process: { run: (a: string[], i?: object) => ($ as any).process.run(a, i) },
        };
        return handler(api, e, async () => undefined);
      })
      .catch(() => ({ text: '🎭 Local error on /crew-agents.' }));
  });

  // Unified slash command `/crew-ui [all|radar|progress|usage|board|turns|stack|agents]` (0-token)
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
              ? `🟢 Crew Radar enabled: ${formatCrewRadarLine()}`
              : '⚪ Crew Radar hidden.',
          };
        }

        if (target === 'progress') {
          crewUiState.bands.progress = parseToggleIntent(modeArg, crewUiState.bands.progress);
          $.ui.invalidate('ui.render');
          return {
            text: crewUiState.bands.progress
              ? `📊 Batch & Task Progress enabled: ${formatCombinedBatchProgressLine()}`
              : '⚪ Batch & Task Progress hidden.',
          };
        }

        if (target === 'usage') {
          crewUiState.bands.usage = parseToggleIntent(modeArg, crewUiState.bands.usage);
          $.ui.invalidate('ui.render');
          return {
            text: crewUiState.bands.usage
              ? `🟧 Usage enabled: ${formatUsageLine()}`
              : '⚪ Usage hidden.',
          };
        }

        if (target === 'weather') {
          crewUiState.bands.weather = parseToggleIntent(modeArg, crewUiState.bands.weather);
          $.ui.invalidate('ui.render');
          return {
            text: crewUiState.bands.weather
              ? `☀️ Token Weather enabled: ${computeTokenWeather().line}`
              : '⚪ Token Weather hidden.',
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
              ? `${PANE_META[paneId].title} opened.`
              : `${PANE_META[paneId].title} closed.`,
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
          crewUiState.bands.usage = isExplicitOff ? false : true;
          crewUiState.bands.agents = isExplicitOff ? false : true;
          crewUiState.bands.locks = true;

          for (const paneId of Object.keys(PANE_META) as CrewPaneId[]) {
            crewUiState.panes[paneId] = shouldEnable;
            if (shouldEnable) {
              await $.ui.open({
                id: PANE_META[paneId].id,
                title: PANE_META[paneId].title,
                ...(paneId === 'crew-board' ? { focus: true as const } : {}),
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
              ? '🎛️ All crew-mates Zero-Token panes and bands are open.'
              : '⚪ crew-mates Zero-Token panes closed.',
          };
        }

        return {
          text: `❓ Unknown subcommand "${target}". Use: /crew-ui [all|radar|progress|usage|board|turns|stack|agents]`,
        };
      })
      .catch((err: unknown) => ({
        text: `❌ Local error while running /crew-ui: ${err instanceof Error ? err.message : String(err)}`,
      }));
  });
}

export default register;
