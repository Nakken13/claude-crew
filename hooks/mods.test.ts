import { describe, expect, test } from 'claude-code/testing';
import { register } from './register.ts';
import { crewRuntimeState, crewUiState, type HookHandler, type ModApi } from './mods/shared.ts';
import { computePromptCacheStatus, promptCacheState } from './mods/prompt-cache-control.ts';
import { computeTokenWeather } from './mods/token-weather.ts';
import { formatTurnRow, turnInspectorState } from './mods/turn-inspector.ts';
import { stackViewerState } from './mods/stack-viewer.ts';
import { agentFlowState } from './mods/agent-flow.ts';
import { crewRadarState, formatCrewRadarLine } from './mods/crew-radar.ts';
import {
  batchProgressState,
  formatBatchProgressSegment,
  formatTaskProgressSegment,
} from './mods/batch-progress.ts';
import { batchBoardState } from './mods/batch-dependency-graph.ts';
import { fileLockMonitorState } from './mods/file-lock-monitor.ts';
import { computeBatchEta } from './mods/batch-eta-cost.ts';

interface HarnessContext {
  files: Map<string, string>;
  dirs: Map<string, string[]>;
  openedPanes: string[];
  closedPanes: string[];
  toasts: string[];
  registeredCommands: string[];
  invalidations: number;
  api: ModApi;
  emit: (event: string, payload?: Record<string, unknown>, matcherKey?: string) => Promise<any>;
}

function createHarness(initialFiles: Record<string, string> = {}): HarnessContext {
  const files = new Map<string, string>(Object.entries(initialFiles));
  const dirs = new Map<string, string[]>();
  const openedPanes: string[] = [];
  const closedPanes: string[] = [];
  const toasts: string[] = [];
  const registeredCommands: string[] = [];
  let invalidations = 0;

  const rebuildDirs = () => {
    dirs.clear();
    for (const fullPath of files.keys()) {
      const norm = fullPath.replace(/\\/g, '/').replace(/^\.\//, '');
      const parts = norm.split('/');
      for (let i = 1; i < parts.length; i += 1) {
        const parent = parts.slice(0, i).join('/');
        const child = parts[i];
        const list = dirs.get(parent) || [];
        if (!list.includes(child)) list.push(child);
        dirs.set(parent, list);
      }
    }
  };
  rebuildDirs();

  const handlers = new Map<string, HookHandler<any, any>>();

  const registrar = (
    event: string,
    matcherOrFn: Record<string, unknown> | HookHandler<any, any>,
    maybeFn?: HookHandler<any, any>,
  ) => {
    if (typeof matcherOrFn === 'function') {
      handlers.set(event, matcherOrFn);
    } else if (maybeFn) {
      const suffix =
        typeof matcherOrFn.component === 'string'
          ? `component=${matcherOrFn.component}`
          : typeof matcherOrFn.command === 'string'
            ? `command=${matcherOrFn.command}`
            : JSON.stringify(matcherOrFn);
      handlers.set(`${event}:${suffix}`, maybeFn);
    }
  };

  register(registrar);

  const api: ModApi = {
    ui: {
      resolve: () => ({
        Box: (props) => ({ type: 'Box', ...props }),
        Text: (props) => ({ type: 'Text', ...props }),
      }),
      invalidate: () => {
        invalidations += 1;
      },
      open: async (opts) => {
        if (!openedPanes.includes(opts.id)) openedPanes.push(opts.id);
        const idx = closedPanes.indexOf(opts.id);
        if (idx >= 0) closedPanes.splice(idx, 1);
      },
      close: async (opts) => {
        closedPanes.push(opts.id);
        const idx = openedPanes.indexOf(opts.id);
        if (idx >= 0) openedPanes.splice(idx, 1);
      },
      toast: (msg) => {
        toasts.push(msg);
      },
    },
    command: {
      register: async (opts) => {
        if (!registeredCommands.includes(opts.name)) {
          registeredCommands.push(opts.name);
        }
      },
    },
    fs: {
      read: async (p) => {
        const norm = p.replace(/\\/g, '/').replace(/^\.\//, '');
        if (!files.has(norm)) throw new Error(`ENOENT: ${norm}`);
        return files.get(norm) || '';
      },
      write: async (p, content) => {
        const norm = p.replace(/\\/g, '/').replace(/^\.\//, '');
        files.set(norm, content);
        rebuildDirs();
      },
      list: async (p) => {
        const norm = p.replace(/\\/g, '/').replace(/^\.\//, '').replace(/\/+$/, '');
        return dirs.get(norm) || [];
      },
      stat: async (p) => {
        const norm = p.replace(/\\/g, '/').replace(/^\.\//, '').replace(/\/+$/, '');
        if (files.has(norm)) return { isFile: true, size: (files.get(norm) || '').length };
        if (dirs.has(norm)) return { isDirectory: true };
        return null;
      },
    },
    env: {
      get: (k) => (k === 'CLAUDE_PROJECT_DIR' ? '.' : undefined),
    },
  };

  const emit = async (
    event: string,
    payload: Record<string, unknown> = {},
    matcherKey?: string,
  ) => {
    const key = matcherKey ? `${event}:${matcherKey}` : event;
    const fn = handlers.get(key);
    if (!fn) throw new Error(`No handler registered for ${key}`);
    return fn(api, payload, async (ev) => ev);
  };

  return {
    files,
    dirs,
    openedPanes,
    closedPanes,
    toasts,
    registeredCommands,
    get invalidations() {
      return invalidations;
    },
    api,
    emit,
  };
}

function collectTexts(node: unknown): string {
  if (!node) return '';
  if (typeof node === 'string') return node;
  if (Array.isArray(node)) return node.map(collectTexts).join('\n');
  if (typeof node === 'object') {
    const children = (node as { children?: unknown[] }).children;
    if (Array.isArray(children)) return children.map(collectTexts).join('\n');
  }
  return '';
}

describe('crew-mates 10 Zero-Token Mods suite', () => {
  test('Étape 2 (Mods 1-5): cache TTL, token weather, turn inspector, stack viewer, agent flow', async () => {
    const h = createHarness({
      'CLAUDE.md': '# Project Rules\n',
      'AGENTS.md': '# Agents\n',
      '.mcp.json': JSON.stringify({ mcpServers: { github: {}, postgres: {} } }),
      'skills/crew-start/SKILL.md': '---\nname: crew-start\n---\n',
      'agents/manager.md': '---\nname: manager\n---\n',
      'hooks/hooks.json': JSON.stringify({
        modules: ['./register.ts'],
        hooks: { PreToolUse: [], SessionStart: [], Stop: [] },
      }),
    });

    await h.emit('session.start', { sessionId: 'sess-alpha-1234' });

    // Slash commands registered locally (0-token)
    expect(h.registeredCommands).toContain('crew-ui');
    expect(h.registeredCommands).toContain('crew-turns');
    expect(h.registeredCommands).toContain('crew-stack');
    expect(h.registeredCommands).toContain('crew-board');
    expect(h.registeredCommands).toContain('crew-agents');

    // Mod 4: Stack Viewer populated context, MCP, skills, agents, mods
    expect(stackViewerState.snapshot.contextAndRules.some((c) => c.name === 'CLAUDE.md')).toBe(true);
    expect(stackViewerState.snapshot.mcpServers.map((m) => m.name)).toEqual(['github', 'postgres']);
    expect(stackViewerState.snapshot.skills.some((s) => s.name === 'crew-start')).toBe(true);
    expect(stackViewerState.snapshot.agents.some((a) => a.name === 'manager')).toBe(true);
    expect(stackViewerState.snapshot.modsAndHooks.length).toBeGreaterThanOrEqual(10);

    // Mod 5: Agent Flow live interception around subagent tool.call
    agentFlowState.nodes = [];
    await h.emit('turn.start', {});
    await h.emit('tool.call', {
      tool: 'Agent',
      input: { subagent_type: 'manager', description: 'Découpage du batch' },
    });
    expect(agentFlowState.nodes.length).toBe(1);
    expect(agentFlowState.nodes[0].agentName).toBe('manager');
    expect(agentFlowState.nodes[0].status).toBe('done');
    expect(agentFlowState.nodes[0].tools).toContain('Write');

    // Mod 1, 2, 3: Turn completion updates Cache TTL, Token Weather & Turn Inspector
    turnInspectorState.turns = [];
    await h.emit('tool.call', { tool: 'Read' });
    await h.emit('tool.call', { tool: 'Read' });
    await h.emit('turn.complete', {
      durationMs: 4200,
      usage: {
        input_tokens: 12_000,
        output_tokens: 1_500,
        cache_read_input_tokens: 140_000,
        cache_creation_input_tokens: 8_000,
      },
    });

    // Mod 1: Prompt cache counters & <60s expiring alert
    const warmStatus = computePromptCacheStatus(Date.now());
    expect(warmStatus.isWarm).toBe(true);
    expect(warmStatus.line).toContain('cache_read: 140k');
    expect(warmStatus.line).toContain('cache_creation: 8k');

    // Simulate 255s elapsed on 300s TTL -> 45s left (< 60s alert!)
    const expiringStatus = computePromptCacheStatus((promptCacheState.lastRefreshAtMs || Date.now()) + 255_000);
    expect(expiringStatus.isExpiringSoon).toBe(true);
    expect(expiringStatus.line).toContain('<60s');

    // Mod 2: Token Weather stages
    expect(computeTokenWeather(40_000, 200_000).label).toBe('☀️ Clear');
    expect(computeTokenWeather(110_000, 200_000).label).toBe('⛅ Cloudy');
    expect(computeTokenWeather(160_000, 200_000).label).toBe('⛈️ Storm');
    expect(computeTokenWeather(185_000, 200_000).label).toBe('🚨 Compact soon');

    // Mod 3: Turn Inspector row & pane rendering
    expect(turnInspectorState.turns.length).toBe(1);
    const row = formatTurnRow(turnInspectorState.turns[0]);
    expect(row).toContain('Read×2');
    expect(row).toContain('R:140k');

    await h.emit('command.run', { args: '' }, 'command=crew-turns');
    expect(h.openedPanes).toContain('crew-turns');
    const turnsPaneTree = await h.emit('ui.render', { requestId: 'crew-turns' }, 'component=Pane');
    expect(collectTexts(turnsPaneTree)).toContain('Historique des tours');

    await h.emit('session.end', { sessionId: 'sess-alpha-1234' });
  });

  test('Étape 3 (Mods 6-10) & /crew-ui: radar, progress 4/6 & 3/4, kanban board, file collision alert, ETA', async () => {
    const nowIso = new Date().toISOString();
    const h = createHarness({
      '.claude/crew-sessions.lock': JSON.stringify({
        sessions: {
          'other-sess-9999': {
            sessionId: 'other-sess-9999',
            startedAt: nowIso,
            updatedAt: nowIso,
            batch: 'Batch B',
            activeTask: 'payment-api.md',
            activeFiles: { 'src/shared/hotfile.ts': Date.now() },
          },
        },
      }),
      'crew/CLAUDE_CONTEXT/crew_lock.json': JSON.stringify({
        sessions: {
          'my-sess-1111': {
            batch: 'Batch A',
            tasks: ['active-feature.md'],
            worktree: '../repo-batch-a',
            branch: 'crew/batch-a',
            since: nowIso,
          },
          'other-sess-9999': {
            batch: 'Batch B',
            tasks: ['payment-api.md'],
            worktree: '../repo-batch-b',
            branch: 'crew/batch-b',
            since: nowIso,
          },
        },
      }),
      'crew/CURRENT_TASKS/active-feature.md': [
        '# Implémenter les Mods',
        '- [x] Étape 1',
        '- [x] Étape 2',
        '- [x] Étape 3',
        '- [x] Étape 4',
        '- [s] Étape 5 en cours',
        '- [ ] Étape 6 restante',
      ].join('\n'),
      'crew/CURRENT_TASKS/payment-api.md': '# Payment API\n- [ ] Step 1\n',
      'crew/TODO/next-in-a.md': '# Suite Batch A\n- [ ] Action 1\n',
      'crew/TODO/blocked-by-b.md': '# Conflit Zone B\n- [ ] Action 1\n',
      'crew/PAUSED/waiting-design.md': '# Validation UI\n- [x] Mock\n- [ ] Review\n',
      'crew/CLAUDE_BATCH.md': [
        '# Batching',
        '',
        '## Batch A',
        'Zone : `hooks/`',
        '- ~~`done-1.md`~~',
        '- ~~`done-2.md`~~',
        '- ~~`done-3.md`~~',
        '- `active-feature.md`',
        '',
        '## Batch B',
        'Zone : `backend/payments/`',
        '- `payment-api.md`',
        '',
        '## Batch C',
        'Zone : `backend/payments/webhooks/`',
        '- `blocked-by-b.md`',
        '- `waiting-design.md`',
        '',
        '## Batch D',
        'Zone : `docs/`',
        '- `next-in-a.md`',
      ].join('\n'),
    });

    await h.emit('session.start', { sessionId: 'my-sess-1111' });

    // Mod 6: Crew Radar counts 2 online sessions, 2 Current Tasks, 2 Todo, 1 Paused
    expect(crewRadarState.onlineSessions).toBe(2);
    expect(crewRadarState.currentTasks).toBe(2);
    expect(crewRadarState.todoTasks).toBe(2);
    expect(formatCrewRadarLine()).toContain('🟢 2 Sessions en ligne | ⚡ 2 Current Tasks | 📋 2 Todo');

    // Mod 7: Batch Progress exact specification formatting:
    // 4 [x] out of 6 ([x]×4 + [s]×1 + [ ]×1) => Task : [████░░] 4/6 (66%)
    // 3 closed tasks out of 4 in Batch A => Batch : [██████░░] 3/4 tasks (75%)
    expect(formatTaskProgressSegment(batchProgressState)).toBe('Task : [████░░] 4/6 (66%)');
    expect(formatBatchProgressSegment(batchProgressState)).toBe('Batch : [██████░░] 3/4 tasks (75%)');

    // Mod 8: Kanban & Dependency Graph
    expect(batchBoardState.allBoards.length).toBe(4);
    const boardA = batchBoardState.allBoards.find((b) => b.batchKey === 'Batch A');
    expect(boardA?.columns.done.length).toBe(3);
    expect(boardA?.columns.inProgress.length).toBe(1);
    expect(boardA?.columns.inProgress[0].sessionId).toBe('my-sess-1111');

    const boardC = batchBoardState.allBoards.find((b) => b.batchKey === 'Batch C');
    // Batch C overlaps Batch B (`backend/payments/`), which is locked by `other-sess-9999` -> Blocked!
    expect(boardC?.columns.blocked.length).toBe(2);

    // Mod 9: File Lock Monitor anti-collision on Edit/Write
    fileLockMonitorState.alerts = [];
    // Case A: Zone collision with Batch B locked by other-sess-9999
    await h.emit('tool.call', {
      tool: 'Edit',
      input: { file_path: 'backend/payments/stripe.ts' },
    });
    expect(fileLockMonitorState.alerts.length).toBe(1);
    expect(fileLockMonitorState.alerts[0].source).toBe('batch-zone');
    expect(h.toasts.some((t) => t.includes('COLLISION ZONE'))).toBe(true);

    // Case B: Direct active-file collision via `.claude/crew-sessions.lock`
    await h.emit('tool.call', {
      tool: 'Write',
      input: { file_path: 'src/shared/hotfile.ts' },
    });
    expect(fileLockMonitorState.alerts.length).toBe(2);
    expect(fileLockMonitorState.alerts[1].source).toBe('active-file');

    // Render AbovePrompt and confirm radar, progress, and collision banner appear
    const aboveTree = await h.emit('ui.render', {}, 'component=AbovePrompt');
    const aboveText = collectTexts(aboveTree);
    expect(aboveText).toContain('🟢 2 Sessions en ligne');
    expect(aboveText).toContain('Task : [████░░] 4/6 (66%)');
    expect(aboveText).toContain('Batch : [██████░░] 3/4 tasks (75%)');
    expect(aboveText).toContain('COLLISION');

    // Mod 10: Batch ETA & Cost calculation from completed tasks
    const eta = computeBatchEta({
      batchKey: 'Batch A',
      batchTotalTasks: 4,
      batchDoneTasks: 3,
      activeTaskSlug: 'active-feature.md',
      activeTaskDone: 0,
      activeTaskTotal: 6,
      metrics: {
        completedTasks: [
          { slug: 'done-1.md', batchKey: 'Batch A', durationMs: 8 * 60_000, tokensUsed: 45_000, completedAtMs: 1 },
          { slug: 'done-2.md', batchKey: 'Batch A', durationMs: 8 * 60_000, tokensUsed: 45_000, completedAtMs: 2 },
        ],
        inFlightTasks: {},
      },
    });
    expect(eta.line).toBe('⏱️ Fin estimée : ~8 min (~45k tokens restants)');

    // Step 4: Unified `/crew-ui` slash command toggles panes and bands locally
    const boardRes = await h.emit('command.run', { args: 'board' }, 'command=crew-ui');
    expect(String(boardRes.text)).toContain('ouvert');
    expect(h.openedPanes).toContain('crew-board');

    const allOpenRes = await h.emit('command.run', { args: 'all on' }, 'command=crew-ui');
    expect(String(allOpenRes.text)).toContain('ouverts');
    expect(crewUiState.panes['crew-turns']).toBe(true);
    expect(crewUiState.panes['crew-stack']).toBe(true);
    expect(crewUiState.panes['crew-board']).toBe(true);
    expect(crewUiState.panes['crew-agents']).toBe(true);

    const radarOffRes = await h.emit('command.run', { args: 'radar off' }, 'command=crew-ui');
    expect(String(radarOffRes.text)).toContain('masqué');
    expect(crewUiState.bands.radar).toBe(false);
    crewUiState.bands.radar = true;

    // Session end removes my-sess-1111 from `.claude/crew-sessions.lock`
    await h.emit('session.end', { sessionId: 'my-sess-1111' });
    const finalSessionsLock = JSON.parse(h.files.get('.claude/crew-sessions.lock') || '{}');
    expect(finalSessionsLock.sessions['my-sess-1111']).toBeUndefined();
    expect(finalSessionsLock.sessions['other-sess-9999']).toBeDefined();
    expect(crewRuntimeState.sessionId).toBe('my-sess-1111');
  });

  test('Panes rendering (/crew-board, /crew-stack, /crew-agents), 1h TTL & live task completion velocity', async () => {
    const nowIso = new Date().toISOString();
    const h = createHarness({
      'CLAUDE.md': '# Root Rules\n',
      'crew/CLAUDE_CONTEXT/crew_lock.json': JSON.stringify({
        sessions: {
          'sess-vel-1': {
            batch: 'Batch Velocity',
            tasks: ['task-one.md'],
            worktree: null,
            branch: null,
            since: nowIso,
          },
        },
      }),
      'crew/CURRENT_TASKS/task-one.md': '# Task One\n- [x] Sub 1\n- [ ] Sub 2\n',
      'crew/TODO/task-two.md': '# Task Two\n- [ ] Sub A\n',
      'crew/CLAUDE_BATCH.md': [
        '# Batching',
        '## Batch Velocity',
        'Zone : `hooks/mods/`',
        '- `task-one.md`',
        '- `task-two.md`',
      ].join('\n'),
    });

    await h.emit('session.start', { sessionId: 'sess-vel-1' });
    expect(formatTaskProgressSegment(batchProgressState)).toBe('Task : [███░░░] 1/2 (50%)');

    // Simulate checking the second checkbox via Write tool.call -> mid-turn update to 2/2 (100%)
    await h.api.fs.write('crew/CURRENT_TASKS/task-one.md', '# Task One\n- [x] Sub 1\n- [x] Sub 2\n');
    await h.emit('tool.call', {
      tool: 'Write',
      input: { file_path: 'crew/CURRENT_TASKS/task-one.md' },
    });
    expect(formatTaskProgressSegment(batchProgressState)).toBe('Task : [██████] 2/2 (100%)');

    // Complete turn with 1-hour cache TTL (`ephemeral_1h_input_tokens`)
    await h.emit('turn.complete', {
      durationMs: 120_000,
      usage: {
        input_tokens: 15_000,
        output_tokens: 5_000,
        cache_read_input_tokens: 50_000,
        cache_creation_input_tokens: 10_000,
        cache_creation: { ephemeral_1h_input_tokens: 10_000 },
      },
    });
    expect(computePromptCacheStatus(Date.now()).ttlLabel).toBe('1h');

    // Close task-one.md (struck in CLAUDE_BATCH.md & deleted from CURRENT_TASKS) -> batch-eta-cost records velocity!
    h.files.delete('crew/CURRENT_TASKS/task-one.md');
    await h.api.fs.write(
      'crew/CLAUDE_BATCH.md',
      [
        '# Batching',
        '## Batch Velocity',
        'Zone : `hooks/mods/`',
        '- ~~`task-one.md`~~',
        '- `task-two.md`',
      ].join('\n'),
    );
    await h.emit('tool.call', { tool: 'Bash' });
    await h.emit('turn.complete', {
      durationMs: 60_000,
      usage: { input_tokens: 5_000, output_tokens: 2_000 },
    });

    const savedMetrics = JSON.parse(h.files.get('.claude/crew-batch-metrics.json') || '{}');
    expect(Array.isArray(savedMetrics.completedTasks)).toBe(true);
    expect(savedMetrics.completedTasks.some((t: { slug: string }) => t.slug === 'task-one.md')).toBe(
      true,
    );

    // Render all remaining Panes: crew-board, crew-stack, crew-agents
    const boardTree = await h.emit('ui.render', { requestId: 'crew-board' }, 'component=Pane');
    expect(collectTexts(boardTree)).toContain('Batch Velocity');
    expect(collectTexts(boardTree)).toContain('Todo | In Progress | Done | Blocked');

    const stackTree = await h.emit('ui.render', { requestId: 'crew-stack' }, 'component=Pane');
    expect(collectTexts(stackTree)).toContain('Arbre de la Stack Session');

    const agentsTree = await h.emit('ui.render', { requestId: 'crew-agents' }, 'component=Pane');
    expect(collectTexts(agentsTree)).toContain("Arbre d'exécution Subagents");

    // Le cache vit dans son volet latéral, plus dans la bande au-dessus du prompt
    const cacheTree = await h.emit('ui.render', { requestId: 'crew-cache' }, 'component=Pane');
    expect(collectTexts(cacheTree)).toContain('Prompt Cache');
    expect(collectTexts(await h.emit('ui.render', {}, 'component=AbovePrompt'))).not.toContain('cache_read');

    await h.emit('session.end', { sessionId: 'sess-vel-1' });
  });

  test('météo : le contexte vient de $.session.usage() quand turn.complete ne porte pas de tokens', async () => {
    const h = createHarness();
    (h.api as unknown as Record<string, unknown>).session = {
      usage: async () => ({ context: { tokens: 160_000, window: 200_000, percent: 80 } }),
    };
    await h.emit('session.start', { sessionId: 'sess-weather-1' });
    await h.emit('turn.complete', { reason: 'answer', answer: 'ok', durationMs: 1_000 });
    expect(computeTokenWeather().percent).toBe(80);
    await h.emit('session.end', { sessionId: 'sess-weather-1' });
  });

  test('événement turn.complete réaliste (usage du moteur) : météo et compteurs de cache bougent', async () => {
    const h = createHarness();
    const cacheBefore = promptCacheState.sessionCacheReadTokens;
    await h.emit('session.start', { sessionId: 'sess-real-1' });
    await h.emit('turn.complete', {
      reason: 'answer',
      answer: 'ok',
      durationMs: 4_000,
      isAborted: false,
      turnId: 't1',
      usage: {
        input_tokens: 2_000,
        output_tokens: 500,
        cache_read_input_tokens: 150_000,
        cache_creation_input_tokens: 8_000,
        model: 'claude-sonnet-5-5',
      },
    });
    expect(computeTokenWeather().percent).toBeGreaterThan(0);
    expect(promptCacheState.sessionCacheReadTokens - cacheBefore).toBe(150_000);
    await h.emit('session.end', { sessionId: 'sess-real-1' });
  });

  test("env asynchrone du moteur ($.env.get renvoie une promesse) : projectRoot reste une chaîne", async () => {
    const h = createHarness();
    (h.api.env as { get: unknown }).get = async (k: string) => (k === 'CLAUDE_PROJECT_DIR' ? '/proj' : undefined);
    await h.emit('session.start', { sessionId: 'sess-env-1', cwd: '/proj' });
    expect(crewRuntimeState.projectRoot).toBe('/proj');
    const lock = JSON.parse(h.files.get('/proj/.claude/crew-sessions.lock') ?? h.files.get('.claude/crew-sessions.lock') ?? '{}');
    expect(typeof lock.sessions?.['sess-env-1']?.cwd).toBe('string');
    await h.emit('session.end', { sessionId: 'sess-env-1' });
  });
});
