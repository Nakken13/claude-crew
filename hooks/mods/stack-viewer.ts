/**
 * Mod 4 — stack-viewer.ts
 *
 * UI pane (`/crew-stack`) showing the tree of what is loaded in the session
 * (`CLAUDE.md`, rules, MCP, skills, agents, mods) with their source and priority.
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  extractEntryNames,
  joinPath,
  PANE_META,
  resolvePaneRequestId,
  type ModRegistrar,
} from './shared.ts';

export interface StackEntry {
  name: string;
  source: string;
  priority: string;
}

export interface StackSnapshot {
  refreshedAtIso: string;
  contextAndRules: StackEntry[];
  mcpServers: StackEntry[];
  skills: StackEntry[];
  agents: StackEntry[];
  modsAndHooks: StackEntry[];
}

const BUILTIN_ZERO_TOKEN_MODS: string[] = [
  'prompt-cache-control.ts',
  'token-weather.ts',
  'turn-inspector.ts',
  'stack-viewer.ts',
  'agent-flow.ts',
  'crew-radar.ts',
  'batch-progress.ts',
  'batch-dependency-graph.ts',
  'file-lock-monitor.ts',
  'batch-eta-cost.ts',
];

export const stackViewerState: { snapshot: StackSnapshot } = {
  snapshot: {
    refreshedAtIso: '',
    contextAndRules: [],
    mcpServers: [],
    skills: [],
    agents: [],
    modsAndHooks: [],
  },
};

export function parseMcpNamesFromJson(jsonText: string): string[] {
  if (!jsonText || !jsonText.trim()) return [];
  try {
    const parsed = JSON.parse(jsonText) as Record<string, unknown>;
    const container =
      (parsed.mcpServers as Record<string, unknown> | undefined) ||
      (parsed.mcp as Record<string, unknown> | undefined);
    if (!container || typeof container !== 'object') return [];
    return Object.keys(container).sort();
  } catch {
    return [];
  }
}

export function parseHooksSummaryFromJson(jsonText: string): {
  modules: string[];
  hookEvents: string[];
} {
  if (!jsonText || !jsonText.trim()) return { modules: [], hookEvents: [] };
  try {
    const parsed = JSON.parse(jsonText) as {
      modules?: unknown[];
      hooks?: Record<string, unknown>;
    };
    const modules = Array.isArray(parsed.modules)
      ? parsed.modules.filter((m): m is string => typeof m === 'string')
      : [];
    const hookEvents =
      parsed.hooks && typeof parsed.hooks === 'object' ? Object.keys(parsed.hooks) : [];
    return { modules, hookEvents };
  } catch {
    return { modules: [], hookEvents: [] };
  }
}

export function renderStackCategoryLines(title: string, items: StackEntry[]): string[] {
  const lines: string[] = [`${title} (${items.length})`];
  if (items.length === 0) {
    lines.push('  └── (no item detected)');
    return lines;
  }
  items.forEach((item, index) => {
    const branch = index === items.length - 1 ? '└──' : '├──';
    lines.push(`  ${branch} ${item.name}  [${item.priority}] (${item.source})`);
  });
  return lines;
}

export function formatFullStackTree(snap: StackSnapshot = stackViewerState.snapshot): string[] {
  return [
    ...renderStackCategoryLines('📄 Context & Rules', snap.contextAndRules),
    ...renderStackCategoryLines('🔌 Serveurs MCP', snap.mcpServers),
    ...renderStackCategoryLines('⚡ Skills', snap.skills),
    ...renderStackCategoryLines('🎭 Agents (Personas)', snap.agents),
    ...renderStackCategoryLines('🧩 Mods & Hooks (0-token)', snap.modsAndHooks),
  ];
}

export function registerStackViewer(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    await $.command
      .register({
        name: 'crew-stack',
        description: 'Show the loaded stack tree (CLAUDE.md, rules, MCP, skills, agents, mods)',
      })
      .catch(() => undefined);

    const root = $.env.get('CLAUDE_PROJECT_DIR') || crewRuntimeState.projectRoot || '.';

    const contextCandidates: Array<{ rel: string; source: string; priority: string }> = [
      { rel: '.claude/settings.local.json', source: 'Projet local', priority: 'P1 · Haute (override)' },
      { rel: 'CLAUDE.md', source: 'Racine projet', priority: 'P2 · Projet' },
      { rel: 'AGENTS.md', source: 'Racine projet', priority: 'P2 · Invariants agents' },
      { rel: 'crew/CLAUDE_CONTEXT/AGENTS.md', source: 'Crew Context', priority: 'P2 · Contexte crew' },
      { rel: '.claude/settings.json', source: 'Shared project', priority: 'P2 · Team settings' },
      { rel: 'PRODUCT.md', source: 'Racine projet', priority: 'P3 · Produit' },
      { rel: 'SECURITY.md', source: 'Project root', priority: 'P3 · Security' },
      { rel: 'CONTRIBUTING.md', source: 'Racine projet', priority: 'P3 · Conventions' },
    ];

    const contextAndRules: StackEntry[] = [];
    for (const c of contextCandidates) {
      const st = await $.fs.stat(joinPath(root, c.rel)).catch(() => null);
      if (st) {
        contextAndRules.push({ name: c.rel, source: c.source, priority: c.priority });
      }
    }

    const ruleFiles = extractEntryNames(
      await $.fs.list(joinPath(root, '.claude/rules')).catch(() => []),
    ).filter((n) => n.endsWith('.md'));
    for (const rf of ruleFiles) {
      contextAndRules.push({
        name: `.claude/rules/${rf}`,
        source: 'Modular rules',
        priority: 'P2 · Project rule',
      });
    }

    const mcpServers: StackEntry[] = [];
    const seenMcp = new Set<string>();
    const mcpSources: Array<{ rel: string; source: string; priority: string }> = [
      { rel: '.claude/settings.local.json', source: '.claude/settings.local.json', priority: 'P1 · Local' },
      { rel: '.mcp.json', source: '.mcp.json', priority: 'P2 · Projet' },
      { rel: '.claude/settings.json', source: '.claude/settings.json', priority: 'P2 · Projet' },
      { rel: '.claude-plugin/plugin.json', source: 'plugin.json', priority: 'P3 · Plugin' },
    ];
    for (const ms of mcpSources) {
      const txt = await $.fs.read(joinPath(root, ms.rel)).catch(() => '');
      for (const serverName of parseMcpNamesFromJson(txt)) {
        const key = `${serverName}@${ms.rel}`;
        if (!seenMcp.has(key)) {
          seenMcp.add(key);
          mcpServers.push({ name: serverName, source: ms.source, priority: ms.priority });
        }
      }
    }

    const skills: StackEntry[] = [];
    const localSkills = extractEntryNames(
      await $.fs.list(joinPath(root, '.claude/skills')).catch(() => []),
    );
    const localSkillSet = new Set(localSkills);
    for (const sk of localSkills) {
      skills.push({
        name: sk,
        source: '.claude/skills/',
        priority: 'P1 · Projet (prioritaire)',
      });
    }
    const pluginSkills = extractEntryNames(
      await $.fs.list(joinPath(root, 'skills')).catch(() => []),
    );
    for (const sk of pluginSkills) {
      if (!localSkillSet.has(sk)) {
        skills.push({
          name: sk,
          source: 'plugin crew-mates',
          priority: 'P2 · Plugin',
        });
      }
    }

    const agents: StackEntry[] = [];
    const localAgents = extractEntryNames(
      await $.fs.list(joinPath(root, '.claude/agents')).catch(() => []),
    ).filter((n) => n.endsWith('.md'));
    const localAgentSet = new Set(localAgents);
    for (const ag of localAgents) {
      agents.push({
        name: ag.replace(/\.md$/i, ''),
        source: '.claude/agents/',
        priority: 'P1 · Projet (prioritaire)',
      });
    }
    const pluginAgents = extractEntryNames(
      await $.fs.list(joinPath(root, 'agents')).catch(() => []),
    ).filter((n) => n.endsWith('.md'));
    for (const ag of pluginAgents) {
      if (!localAgentSet.has(ag)) {
        agents.push({
          name: ag.replace(/\.md$/i, ''),
          source: 'plugin crew-mates',
          priority: 'P2 · Plugin',
        });
      }
    }

    const hooksJsonText = await $.fs.read(joinPath(root, 'hooks/hooks.json')).catch(() => '');
    const parsedHooks = parseHooksSummaryFromJson(hooksJsonText);
    const modEntries = extractEntryNames(
      await $.fs.list(joinPath(root, 'hooks/mods')).catch(() => []),
    ).filter((n) => n.endsWith('.ts') && !n.endsWith('.test.ts') && n !== 'shared.ts');
    const finalModFiles = modEntries.length > 0 ? modEntries : BUILTIN_ZERO_TOKEN_MODS;

    const modsAndHooks: StackEntry[] = finalModFiles.map((modFile) => ({
      name: modFile.replace(/\.ts$/i, ''),
      source: 'hooks/mods/ (register.ts)',
      priority: 'P1 · Mod 0-token in-process',
    }));

    for (const evName of parsedHooks.hookEvents) {
      modsAndHooks.push({
        name: `hook:${evName}`,
        source: 'hooks/hooks.json',
        priority: 'P2 · Garde shell/Python',
      });
    }

    stackViewerState.snapshot = {
      refreshedAtIso: new Date().toISOString(),
      contextAndRules,
      mcpServers,
      skills,
      agents,
      modsAndHooks,
    };

    return next(e);
  });

  on('command.run', { command: 'crew-stack' }, async ($, e) => {
    try {
      const arg = String((e as Record<string, unknown>)?.args ?? '').trim().toLowerCase();
      const shouldOpen =
        arg === 'open' || arg === 'on'
          ? true
          : arg === 'close' || arg === 'off'
            ? false
            : !crewUiState.panes['crew-stack'];

      crewUiState.panes['crew-stack'] = shouldOpen;
      if (shouldOpen) {
        await $.ui.open({
          id: PANE_META['crew-stack'].id,
          title: PANE_META['crew-stack'].title,
          focus: true,
          immediate: true,
          closeOnEscape: true,
        });
      } else {
        await $.ui.close({ id: PANE_META['crew-stack'].id });
      }
      $.ui.invalidate('ui.render');

      const s = stackViewerState.snapshot;
      return {
        text: shouldOpen
          ? `📚 Stack Viewer opened — ${s.contextAndRules.length} context/rules, ${s.mcpServers.length} MCP, ${s.skills.length} skills, ${s.agents.length} agents, ${s.modsAndHooks.length} mods/hooks.`
          : '📚 Stack Viewer closed.',
      };
    } catch {
      return { text: '📚 Unable to toggle the Stack Viewer panel.' };
    }
  });

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (resolvePaneRequestId(e as Record<string, unknown>) !== PANE_META['crew-stack'].id) {
      return next(e);
    }

    const { Box, Text } = $.ui.resolve(e);
    const lines = formatFullStackTree(stackViewerState.snapshot);

    return Box({
      flexDirection: 'column',
      padding: 1,
      children: [
        Text({
          bold: true,
          color: 'cyan',
          children: ['📚 Session Stack Tree (Source & Priority)'],
        }),
        ...lines.map((line) =>
          Text({
            bold: !line.startsWith('  '),
            color: !line.startsWith('  ') ? 'green' : undefined,
            dimColor: line.includes('(no item'),
            children: [line],
          }),
        ),
      ],
    });
  });
}

export const register = registerStackViewer;
