import { describe, expect, test } from 'claude-code/testing';
import { register } from './register.ts';
import { crewRuntimeState, crewUiState, parseClaudeBatch, type HookHandler, type ModApi } from './mods/shared.ts';
import { computePromptCacheStatus, promptCacheState } from './mods/prompt-cache-control.ts';
import { computeTokenWeather } from './mods/token-weather.ts';
import { formatTurnRow, turnInspectorState } from './mods/turn-inspector.ts';
import { stackViewerState } from './mods/stack-viewer.ts';
import { agentFlowState } from './mods/agent-flow.ts';
import { crewRadarState, formatCrewRadarLine, formatCrewRadarCompact } from './mods/crew-radar.ts';
import {
  batchProgressState,
  formatBatchProgressSegment,
  formatTaskProgressSegment,
} from './mods/batch-progress.ts';
import { crewCountState } from './mods/crew-count-band.ts';
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
  test('Step 2 (Mods 1-5): cache TTL, token weather, turn inspector, stack viewer, agent flow', async () => {
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
      input: { subagent_type: 'manager', description: 'Batch breakdown' },
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
        cache_creation: { ephemeral_5m_input_tokens: 8_000 },
      },
    });

    // Mod 1: Prompt cache counters & <60s expiring alert
    const warmStatus = computePromptCacheStatus(Date.now());
    expect(warmStatus.isWarm).toBe(true);
    expect(warmStatus.line).toContain('cache_read: 140k');
    expect(warmStatus.line).toContain('cache_creation: 8k');

    // Default TTL is 1h (5 min only via CLAUDE_CACHE_TTL=5m): 3555s elapsed -> 45s left (< 60s alert!)
    const expiringStatus = computePromptCacheStatus((promptCacheState.lastRefreshAtMs || Date.now()) + 3_555_000);
    expect(expiringStatus.isExpiringSoon).toBe(true);
    expect(expiringStatus.line).toContain('<60s');

    // Mod 2: Token Weather stages
    expect(computeTokenWeather(40_000, 200_000).label).toBe('☀️ Clear');
    expect(computeTokenWeather(110_000, 200_000).label).toBe('⛅ Cloudy');
    expect(computeTokenWeather(120_000, 200_000).label).toBe('⛈️ Storm');
    expect(computeTokenWeather(185_000, 200_000).label).toBe('🚨 Compact soon');

    // Mod 3: Turn Inspector row & pane rendering
    expect(turnInspectorState.turns.length).toBe(1);
    const row = formatTurnRow(turnInspectorState.turns[0]);
    expect(row).toContain('Read×2');
    expect(row).toContain('R:140k');

    // Panes are opened at session start: restart from a closed state to test the toggle
    await h.emit('command.run', { args: 'turns off' }, 'command=crew-ui');
    await h.emit('command.run', { args: '' }, 'command=crew-turns');
    expect(h.openedPanes).toContain('crew-turns');
    const turnsPaneTree = await h.emit('ui.render', { requestId: 'crew-turns' }, 'component=Pane');
    expect(collectTexts(turnsPaneTree)).toContain('Turn history');

    await h.emit('session.end', { sessionId: 'sess-alpha-1234' });
  });

  test('Step 3 (Mods 6-10) & /crew-ui: radar, progress 4/6 & 3/4, kanban board, file collision alert, ETA', async () => {
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
        '# Implement the Mods',
        '- [x] Step 1',
        '- [x] Step 2',
        '- [x] Step 3',
        '- [x] Step 4',
        '- [s] Step 5 in progress',
        '- [ ] Step 6 remaining',
      ].join('\n'),
      'crew/CURRENT_TASKS/payment-api.md': '# Payment API\n- [ ] Step 1\n',
      'crew/TODO/next-in-a.md': '# Next in Batch A\n- [ ] Action 1\n',
      'crew/TODO/blocked-by-b.md': '# Zone B conflict\n- [ ] Action 1\n',
      'crew/PAUSED/waiting-design.md': '# UI validation\n- [x] Mock\n- [ ] Review\n',
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
    expect(formatCrewRadarLine()).toContain('🟢 2 Sessions online | ⚡ 2 Current Tasks | 📋 2 Todo');

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
    expect(h.toasts.some((t) => t.includes('ZONE COLLISION'))).toBe(true);

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
    expect(aboveText).toContain('🟢2 ⚡2 📋2 ⏸️1');
    expect(aboveText).toContain('T 4/6  ·  B 3/4');
    expect(aboveText).toContain('B 3/4');
    expect(aboveText).toContain('🚨 2 collisions : stripe.ts, hotfile.ts');

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
    expect(eta.line).toBe('⏱️ ETA: ~8 min (~45k tokens left)');

    // Step 4: Unified `/crew-ui` slash command toggles panes and bands locally
    await h.emit('command.run', { args: 'board off' }, 'command=crew-ui');
    const boardRes = await h.emit('command.run', { args: 'board' }, 'command=crew-ui');
    expect(String(boardRes.text)).toContain('opened');
    expect(h.openedPanes).toContain('crew-board');

    const allOpenRes = await h.emit('command.run', { args: 'all on' }, 'command=crew-ui');
    expect(String(allOpenRes.text)).toContain('are open');
    expect(crewUiState.panes['crew-turns']).toBe(true);
    expect(crewUiState.panes['crew-stack']).toBe(true);
    expect(crewUiState.panes['crew-board']).toBe(true);
    expect(crewUiState.panes['crew-agents']).toBe(true);

    const radarOffRes = await h.emit('command.run', { args: 'radar off' }, 'command=crew-ui');
    expect(String(radarOffRes.text)).toContain('hidden');
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
    expect(collectTexts(stackTree)).toContain('Session Stack Tree');

    const agentsTree = await h.emit('ui.render', { requestId: 'crew-agents' }, 'component=Pane');
    expect(collectTexts(agentsTree)).toContain('Subagent Execution Tree');

    // The cache lives in its side pane, no longer in the band above the prompt
    const cacheTree = await h.emit('ui.render', { requestId: 'crew-cache' }, 'component=Pane');
    expect(collectTexts(cacheTree)).toContain('Prompt Cache');
    expect(collectTexts(await h.emit('ui.render', {}, 'component=AbovePrompt'))).not.toContain('cache_read');

    await h.emit('session.end', { sessionId: 'sess-vel-1' });
  });

  test('Crew N: launchable sessions in red, same line, right after the weather', async () => {
    const h = createHarness();
    (h.api as unknown as Record<string, unknown>).session = {
      usage: async () => ({ context: { tokens: 120_000, window: 200_000, percent: 80 } }),
    };
    (h.api as unknown as Record<string, unknown>).process = {
      run: async () => ({ exitCode: 0, stdout: JSON.stringify({ launchable_count: 3, active: [] }), stderr: '' }),
    };
    (h.api as unknown as Record<string, unknown>).plugin = { root: () => '/plugin' };
    crewRuntimeState.projectRoot = '/repo';
    await h.emit('session.start', { sessionId: 'sess-count-1', cwd: '/repo' });
    await h.emit('turn.complete', { reason: 'answer', answer: 'ok', durationMs: 1_000 });
    const text = collectTexts(await h.emit('ui.render', {}, 'component=AbovePrompt'));
    expect(text).toContain('Crew 3');
    expect(text.indexOf('Crew 3')).toBeGreaterThan(text.indexOf('80%'));
    await h.emit('session.end', { sessionId: 'sess-count-1' });
  });

  test('Crew N: a hanging process.run never blocks the AbovePrompt render', async () => {
    const h = createHarness();
    (h.api as unknown as Record<string, unknown>).process = { run: () => new Promise(() => {}) };
    (h.api as unknown as Record<string, unknown>).plugin = { root: () => '/plugin' };
    crewRuntimeState.projectRoot = '/repo';
    crewCountState.launchable = null;
    crewCountState.error = null;
    const tree = await Promise.race([
      h.emit('ui.render', {}, 'component=AbovePrompt'),
      new Promise(resolve => setTimeout(() => resolve('BLOCKED'), 500)),
    ]);
    expect(tree).not.toBe('BLOCKED');
    expect(collectTexts(tree as never)).not.toContain('Crew');
  });

  test('weather: context comes from $.session.usage() when turn.complete carries no tokens', async () => {
    const h = createHarness();
    (h.api as unknown as Record<string, unknown>).session = {
      usage: async () => ({ context: { tokens: 120_000, window: 200_000, percent: 80 } }),
    };
    await h.emit('session.start', { sessionId: 'sess-weather-1' });
    await h.emit('turn.complete', { reason: 'answer', answer: 'ok', durationMs: 1_000 });
    expect(computeTokenWeather().percent).toBe(80);
    await h.emit('session.end', { sessionId: 'sess-weather-1' });
  });

  test('realistic turn.complete event (engine usage): weather and cache counters move', async () => {
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

  test('cache: the detected 1h TTL stays 1h on a read-only turn (no cache_creation)', async () => {
    const h = createHarness();
    await h.emit('session.start', { sessionId: 'sess-ttl-1' });
    await h.emit('turn.complete', {
      durationMs: 1_000,
      usage: {
        input_tokens: 10,
        cache_read_input_tokens: 5_000,
        cache_creation_input_tokens: 1_000,
        cache_creation: { ephemeral_1h_input_tokens: 1_000 },
      },
    });
    expect(computePromptCacheStatus(Date.now()).ttlLabel).toBe('1h');
    await h.emit('turn.complete', {
      durationMs: 1_000,
      usage: { input_tokens: 10, cache_read_input_tokens: 6_000, cache_creation_input_tokens: 0 },
    });
    expect(computePromptCacheStatus(Date.now()).ttlLabel).toBe('1h');
    await h.emit('session.end', { sessionId: 'sess-ttl-1' });
  });

  test('ghost sessions: inactive entry > 30 min purged, old id replaced by the real id', async () => {
    const h = createHarness();
    const nowMs = Date.now();
    const iso = (ms: number) => new Date(ms).toISOString();
    const entry = (sid: string, ms: number) => ({
      sessionId: sid, startedAt: iso(ms), updatedAt: iso(ms), cwd: '.', activeTask: null, batch: null, activeFiles: {},
    });
    h.files.set(
      '.claude/crew-sessions.lock',
      JSON.stringify({
        sessions: {
          'sess-stale-1': entry('sess-stale-1', nowMs - 2 * 60 * 60 * 1000),
          'sess-fresh-1': entry('sess-fresh-1', nowMs - 60 * 1000),
        },
      }),
    );
    crewRuntimeState.sessionId = 'sess-fresh-1';
    await h.emit('session.start', { sessionId: 'real-uuid-1' });
    const lock = JSON.parse(h.files.get('.claude/crew-sessions.lock') ?? '{}');
    expect(Object.keys(lock.sessions).sort()).toEqual(['real-uuid-1']);
    await h.emit('session.end', { sessionId: 'real-uuid-1' });
  });

  test('radar: TODO tasks listed in crew_ignored.json leave 📋 and move to 👤', async () => {
    const h = createHarness({
      'crew/TODO/mine.md': '# My task\n- [ ] x\n',
      'crew/TODO/theirs-1.md': '# Theirs\n- [ ] x\n',
      'crew/TODO/theirs-2.md': '# Theirs too\n- [ ] x\n',
      'crew/CLAUDE_CONTEXT/CREW_CONFIG.md': 'remote_claims : true\n',
      'crew/CLAUDE_CONTEXT/crew_ignored.json': JSON.stringify({ ignored: { 'theirs-1.md': 'Bob', 'theirs-2.md': 'Alice', 'already-deleted.md': 'Bob' } }),
    });
    await h.emit('session.start', { sessionId: 'sess-ign-1' });
    expect(crewRadarState.todoTasks).toBe(1);
    expect(crewRadarState.othersTasks).toBe(2);
    expect(formatCrewRadarCompact()).toContain('📋1');
    expect(formatCrewRadarCompact()).toContain('👤2');
    expect(formatCrewRadarCompact()).not.toContain('Bob');
    await h.emit('session.end', { sessionId: 'sess-ign-1' });
  });

  test('radar: team mode off -> base bar even if crew_ignored.json exists (no 👤, 📋 counts everything)', async () => {
    const h = createHarness({
      'crew/TODO/a.md': '# A\n- [ ] x\n',
      'crew/TODO/b.md': '# B\n- [ ] x\n',
      'crew/CLAUDE_CONTEXT/CREW_CONFIG.md': 'remote_claims : false\n',
      'crew/CLAUDE_CONTEXT/crew_ignored.json': JSON.stringify({ ignored: ['b.md'] }),
    });
    await h.emit('session.start', { sessionId: 'sess-ign-3' });
    expect(crewRadarState.todoTasks).toBe(2);
    expect(crewRadarState.othersTasks).toBe(0);
    expect(formatCrewRadarCompact()).not.toContain('👤');
    await h.emit('session.end', { sessionId: 'sess-ign-3' });
  });

  test('radar: older crew_ignored.json format (list) is still counted while team mode is on', async () => {
    const h = createHarness({
      'crew/TODO/a.md': '# A\n- [ ] x\n',
      'crew/TODO/b.md': '# B\n- [ ] x\n',
      'crew/CLAUDE_CONTEXT/CREW_CONFIG.md': '# cfg\nremote_claims : true\n',
      'crew/CLAUDE_CONTEXT/crew_ignored.json': JSON.stringify({ owner: 'Bob', ignored: ['b.md'] }),
    });
    await h.emit('session.start', { sessionId: 'sess-ign-4' });
    expect(crewRadarState.todoTasks).toBe(1);
    expect(crewRadarState.othersTasks).toBe(1);
    await h.emit('session.end', { sessionId: 'sess-ign-4' });
  });

  test('radar: without crew_ignored.json (or corrupt), no 👤 and 📋 counts everything', async () => {
    const h = createHarness({
      'crew/TODO/a.md': '# A\n- [ ] x\n',
      'crew/CLAUDE_CONTEXT/crew_ignored.json': '{not json',
    });
    await h.emit('session.start', { sessionId: 'sess-ign-2' });
    expect(crewRadarState.todoTasks).toBe(1);
    expect(crewRadarState.othersTasks).toBe(0);
    expect(formatCrewRadarCompact()).not.toContain('👤');
    await h.emit('session.end', { sessionId: 'sess-ign-2' });
  });

  test('/crew-ui: an internal error surfaces its message instead of generic text', async () => {
    const h = createHarness();
    await h.emit('session.start', { sessionId: 'sess-err-1' });
    (h.api.ui as { open: unknown }).open = async () => {
      throw new Error('boom-ui-open');
    };
    const res = await h.emit('command.run', { args: 'board on' }, 'command=crew-ui');
    expect(String(res.text)).toContain('boom-ui-open');
    await h.emit('session.end', { sessionId: 'sess-err-1' });
  });

  test("engine async env ($.env.get returns a promise): projectRoot stays a string", async () => {
    const h = createHarness();
    (h.api.env as { get: unknown }).get = async (k: string) => (k === 'CLAUDE_PROJECT_DIR' ? '/proj' : undefined);
    await h.emit('session.start', { sessionId: 'sess-env-1', cwd: '/proj' });
    expect(crewRuntimeState.projectRoot).toBe('/proj');
    const lock = JSON.parse(h.files.get('/proj/.claude/crew-sessions.lock') ?? h.files.get('.claude/crew-sessions.lock') ?? '{}');
    expect(typeof lock.sessions?.['sess-env-1']?.cwd).toBe('string');
    await h.emit('session.end', { sessionId: 'sess-env-1' });
  });
  test('weather: thresholds 49/50/74/75/89/90 % -> tier, never NaN', () => {
    const cases: Array<[number, string]> = [
      [49, '☀️ Clear'],
      [50, '⛅ Cloudy'],
      [74, '⛅ Cloudy'],
      [75, '⛈️ Storm'],
      [89, '⛈️ Storm'],
      [90, '🚨 Compact soon'],
    ];
    for (const [pct, label] of cases) {
      const snap = computeTokenWeather(pct * 1_500, 200_000);
      expect(snap.percent).toBe(pct);
      expect(snap.label).toBe(label);
    }
    // direct invalid inputs (see crew/PROBLEMS/token-weather-nan-entree-invalide.md)
    for (const bad of [-5, 0, Number.NaN, Number.POSITIVE_INFINITY]) {
      const snap = computeTokenWeather(bad, 0);
      expect(snap.line).not.toContain('NaN');
      expect(Number.isFinite(snap.percent)).toBe(true);
      expect(snap.label).toBe('☀️ Clear');
    }
    expect(computeTokenWeather(500_000, 200_000).percent).toBe(100);
  });

  test('weather: any window > 150k capped at 150k (crew policy)', () => {
    const big = computeTokenWeather(150_000, 1_000_000);
    expect(big.contextWindow).toBe(150_000);
    expect(big.percent).toBe(100);
    expect(big.label).toBe('🚨 Compact soon');
    expect(computeTokenWeather(60_000, 1_000_000).label).toBe('☀️ Clear');
    expect(computeTokenWeather(120_000, 1_000_000).label).toBe('⛈️ Storm');
    expect(computeTokenWeather(100_000, 200_000).contextWindow).toBe(150_000);
  });

  test('weather: session.usage() erroring or turn.complete without usage -> previous state kept', async () => {
    const h = createHarness();
    (h.api as unknown as Record<string, unknown>).session = {
      usage: async () => ({ context: { tokens: 90_000, window: 200_000, percent: 60 } }),
    };
    await h.emit('session.start', { sessionId: 'sess-weather-2' });
    await h.emit('turn.complete', { reason: 'answer', durationMs: 1_000 });
    expect(computeTokenWeather().percent).toBe(60);

    (h.api as unknown as Record<string, unknown>).session = {
      usage: async () => {
        throw new Error('indisponible');
      },
    };
    await h.emit('turn.complete', { reason: 'answer', durationMs: 1_000 });
    expect(computeTokenWeather().percent).toBe(60);
    await h.emit('session.end', { sessionId: 'sess-weather-2' });
  });

  // --- verif-mod-prompt-cache-control ---
  function resetPromptCacheState(): void {
    promptCacheState.ttlSeconds = 3600;
    promptCacheState.saw1h = false;
    promptCacheState.lastRefreshAtMs = null;
    promptCacheState.lastCacheReadTokens = 0;
    promptCacheState.lastCacheCreationTokens = 0;
    promptCacheState.alertedExpiringForRefreshMs = null;
  }
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  test('cache: default 1h; CLAUDE_CACHE_TTL=5m -> 300', async () => {
    resetPromptCacheState();
    const h1 = createHarness();
    (h1.api.env as { get: (k: string) => unknown }).get = (k) =>
      k === 'CLAUDE_CACHE_TTL' ? Promise.resolve('5m') : k === 'CLAUDE_PROJECT_DIR' ? '.' : undefined;
    await h1.emit('session.start', { sessionId: 'sess-cache-ttl-1h' });
    expect(promptCacheState.ttlSeconds).toBe(300);
    await h1.emit('session.end', { sessionId: 'sess-cache-ttl-1h' });

    resetPromptCacheState();
    const h2 = createHarness();
    await h2.emit('session.start', { sessionId: 'sess-cache-ttl-default' });
    expect(promptCacheState.ttlSeconds).toBe(3600);
    await h2.emit('session.end', { sessionId: 'sess-cache-ttl-default' });
  });

  test('cache: default 1h with countdown; a lone 5m write never downgrades', async () => {
    resetPromptCacheState();
    const h = createHarness();
    await h.emit('session.start', { sessionId: 'sess-cache-default' });
    await h.emit('turn.complete', {
      usage: { input_tokens: 10, cache_read_input_tokens: 50_000, cache_creation_input_tokens: 1_000 },
    });
    const dflt = computePromptCacheStatus((promptCacheState.lastRefreshAtMs || Date.now()) + 280_000);
    expect(dflt.ttlLabel).toBe('1h');
    expect(dflt.isExpiringSoon).toBe(false);

    await h.emit('turn.complete', {
      usage: { input_tokens: 10, cache_creation_input_tokens: 596, cache_creation: { ephemeral_5m_input_tokens: 596 } },
    });
    expect(computePromptCacheStatus(Date.now()).ttlLabel).toBe('1h');

    await h.emit('turn.complete', {
      usage: { input_tokens: 10, cache_creation_input_tokens: 1_000, cache_creation: { ephemeral_1h_input_tokens: 1_000 } },
    });
    await h.emit('turn.complete', {
      usage: { input_tokens: 10, cache_creation_input_tokens: 500, cache_creation: { ephemeral_5m_input_tokens: 500 } },
    });
    expect(computePromptCacheStatus(Date.now()).ttlLabel).toBe('1h');
    await h.emit('session.end', { sessionId: 'sess-cache-default' });
  });

  test('cache: no turn (lastRefreshAtMs null) -> placeholder, no toast; usage without cache fields -> no crash', async () => {
    resetPromptCacheState();
    const h = createHarness();
    await h.emit('session.start', { sessionId: 'sess-cache-edge' });
    const idle = computePromptCacheStatus(Date.now());
    expect(idle.line).toContain('--:--');
    expect(idle.isExpiringSoon).toBe(false);
    await sleep(1_300);
    expect(h.toasts.filter((t) => t.includes('Prompt cache expires'))).toHaveLength(0);

    await h.emit('turn.complete', { reason: 'answer', durationMs: 500, usage: { input_tokens: 10, output_tokens: 2 } });
    expect(Number.isFinite(computePromptCacheStatus().hitRatePercent)).toBe(true);
    expect(computePromptCacheStatus().line).not.toContain('NaN');
    await h.emit('session.end', { sessionId: 'sess-cache-edge' });
  });

  test('cache: < 60 s -> a single toast per refresh, nothing after session.end', async () => {
    resetPromptCacheState();
    const h = createHarness();
    await h.emit('session.start', { sessionId: 'sess-cache-toast' });
    promptCacheState.ttlSeconds = 300; // TTL 5 min observed
    promptCacheState.lastRefreshAtMs = Date.now() - 245_000; // 55 s remaining
    await sleep(2_300);
    const alerts = () => h.toasts.filter((t) => t.includes('Prompt cache expires'));
    expect(alerts()).toHaveLength(1);

    await h.emit('session.end', { sessionId: 'sess-cache-toast' });
    const toastsAfterEnd = h.toasts.length;
    const invalidationsAfterEnd = h.invalidations;
    promptCacheState.lastRefreshAtMs = Date.now() - 250_000; // new refresh to alert on
    promptCacheState.alertedExpiringForRefreshMs = null;
    await sleep(1_500);
    expect(h.toasts.length).toBe(toastsAfterEnd);
    expect(h.invalidations).toBe(invalidationsAfterEnd);
  });
  test('session start: the 5 Zero-Token panes are open without stealing focus', async () => {
    const h = createHarness();
    await h.emit('session.start', { sessionId: 'sess-autostart-1' });
    expect([...h.openedPanes].sort()).toEqual(
      ['crew-agents', 'crew-board', 'crew-cache', 'crew-stack', 'crew-turns'],
    );
    await h.emit('session.end', { sessionId: 'sess-autostart-1' });
  });

  test("ui.open: the host only accepts focus:true or the field being absent (never focus:false)", async () => {
    const h = createHarness();
    const opened: Array<Record<string, unknown>> = [];
    const realOpen = h.api.ui.open;
    h.api.ui.open = async (opts: any) => {
      opened.push({ ...opts });
      return realOpen(opts);
    };
    await h.emit('session.start', { sessionId: 'sess-focus-1' });
    await h.emit('command.run', { args: 'all off' }, 'command=crew-ui');
    await h.emit('command.run', { args: 'all on' }, 'command=crew-ui');
    expect(opened.length).toBeGreaterThanOrEqual(10);
    for (const o of opened) {
      expect('focus' in o ? o.focus : true).toBe(true);
    }
    await h.emit('session.end', { sessionId: 'sess-focus-1' });
  });
});

describe('CLAUDE_BATCH.md unsorted section: English header, French legacy header', () => {
  const md = (header: string) =>
    `## Batch A
- \`a.md\`
Zone : \`src/a/\`

${header}
- \`loose.md\`
`;

  for (const header of ['## Unsorted', '## À classer', '### A classer']) {
    test(`'${header}' bounds the last batch and lists the loose task`, () => {
      const parsed = parseClaudeBatch(md(header));
      expect(parsed.sections.length).toBe(1);
      expect(parsed.sections[0].tasks.map((t) => t.slug)).toEqual(['a.md']);
      expect(parsed.unclassified).toContain('loose.md');
    });
  }
});
