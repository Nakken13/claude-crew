/**
 * Mod 5 — agent-flow.ts
 *
 * Intercepts subagent launches (`tool.call` on the `crew-mates` agents:
 * `Agent`, `Task`, `ceo`, `manager`, `comms`, `architect`, `designer`, `legal`, `social`, `seo`)
 * and draws the live execution tree (status, tools, duration).
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  formatDurationCompact,
  PANE_META,
  resolvePaneRequestId,
  type ModRegistrar,
  addBandSegments,
} from './shared.ts';

export type SubagentRunStatus = 'running' | 'done' | 'denied' | 'error';

export interface SubagentExecutionNode {
  id: number;
  turnNumber: number;
  agentName: string;
  label: string;
  status: SubagentRunStatus;
  tools: string[];
  startedAtMs: number;
  endedAtMs: number | null;
  durationMs: number;
}

export const CREW_PERSONA_DEFAULT_TOOLS: Record<string, string[]> = {
  ceo: ['Read', 'Glob', 'Grep'],
  manager: ['Read', 'Glob', 'Grep', 'Write', 'Edit', 'Bash'],
  comms: ['Read', 'Glob', 'Grep'],
  architect: ['Read', 'Glob', 'Grep'],
  designer: ['Read', 'Glob', 'Grep'],
  legal: ['Read', 'Glob', 'Grep', 'WebSearch'],
  social: ['Read', 'Glob', 'Grep', 'WebSearch'],
  seo: ['Read', 'Glob', 'Grep', 'WebSearch'],
};

const SUBAGENT_TOOL_NAMES = new Set([
  'agent',
  'task',
  'subagent',
  'dispatch_agent',
  'invoke_subagent',
  ...Object.keys(CREW_PERSONA_DEFAULT_TOOLS),
]);

export interface AgentFlowState {
  nextId: number;
  nodes: SubagentExecutionNode[];
  activeStack: number[];
}

export const agentFlowState: AgentFlowState = {
  nextId: 1,
  nodes: [],
  activeStack: [],
};

export function detectSubagentLaunch(event: Record<string, unknown>): {
  agentName: string;
  label: string;
} | null {
  const rawTool = String(event.tool ?? event.name ?? '').trim();
  if (!rawTool) return null;

  const lowerTool = rawTool.toLowerCase();
  const input =
    (event.input as Record<string, unknown> | undefined) ||
    (event.args as Record<string, unknown> | undefined) ||
    (event.tool_input as Record<string, unknown> | undefined) ||
    event;

  const subagentType = String(
    input.subagent_type ?? input.subagentType ?? input.agent ?? input.persona ?? '',
  ).trim();

  if (!SUBAGENT_TOOL_NAMES.has(lowerTool) && !subagentType) {
    return null;
  }

  const agentName = (subagentType || rawTool).trim();
  const rawDesc = String(input.description ?? input.role ?? input.prompt ?? '').trim();
  const firstLine = rawDesc.split(/\r?\n/)[0]?.slice(0, 48) || '';
  const label = firstLine ? `${agentName} — ${firstLine}` : agentName;

  return { agentName, label };
}

export function statusIcon(status: SubagentRunStatus): string {
  switch (status) {
    case 'running':
      return '🔄';
    case 'done':
      return '✅';
    case 'denied':
      return '🚫';
    case 'error':
      return '❌';
  }
}

export function formatAgentNodeLine(
  node: SubagentExecutionNode,
  isLast: boolean,
  nowMs = Date.now(),
): string {
  const branch = isLast ? '└──' : '├──';
  const elapsed = node.status === 'running' ? Math.max(0, nowMs - node.startedAtMs) : node.durationMs;
  const durFmt = formatDurationCompact(elapsed);
  const toolsFmt = node.tools.length > 0 ? node.tools.slice(0, 5).join(', ') : 'Read, Grep';
  return `${branch} ${statusIcon(node.status)} ${node.agentName} [${toolsFmt}] · ${durFmt}`;
}

export function registerAgentFlow(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    await $.command
      .register({
        name: 'crew-agents',
        description: 'Show the live execution tree of crew-mates subagents (0-token)',
      })
      .catch(() => undefined);
    return next(e);
  });

  on('tool.call', async ($, e, next) => {
    const ev = (e || {}) as Record<string, unknown>;
    const launch = detectSubagentLaunch(ev);

    if (!launch) {
      // If a subagent is currently active in-process, record the nested tool it invoked
      if (agentFlowState.activeStack.length > 0) {
        const activeId = agentFlowState.activeStack[agentFlowState.activeStack.length - 1];
        const parentNode = agentFlowState.nodes.find((n) => n.id === activeId);
        const toolName = String(ev.tool ?? ev.name ?? '').trim();
        if (parentNode && toolName && !parentNode.tools.includes(toolName)) {
          parentNode.tools.push(toolName);
          $.ui.invalidate('ui.render');
        }
      }
      return next(e);
    }

    const personaKey = launch.agentName.toLowerCase();
    const defaultTools = CREW_PERSONA_DEFAULT_TOOLS[personaKey]
      ? [...CREW_PERSONA_DEFAULT_TOOLS[personaKey]]
      : [];

    const node: SubagentExecutionNode = {
      id: agentFlowState.nextId++,
      turnNumber: crewRuntimeState.turnCount + 1,
      agentName: launch.agentName,
      label: launch.label,
      status: 'running',
      tools: defaultTools,
      startedAtMs: Date.now(),
      endedAtMs: null,
      durationMs: 0,
    };

    agentFlowState.nodes.push(node);
    if (agentFlowState.nodes.length > 40) {
      agentFlowState.nodes.splice(0, agentFlowState.nodes.length - 40);
    }
    agentFlowState.activeStack.push(node.id);
    $.ui.invalidate('ui.render');

    try {
      const result = await next(e);
      const nowMs = Date.now();
      node.endedAtMs = nowMs;
      node.durationMs = Math.max(0, nowMs - node.startedAtMs);
      const denied = Boolean((result as Record<string, unknown> | null | undefined)?.deny);
      node.status = denied ? 'denied' : 'done';
      return result;
    } catch (err) {
      const nowMs = Date.now();
      node.endedAtMs = nowMs;
      node.durationMs = Math.max(0, nowMs - node.startedAtMs);
      node.status = 'error';
      throw err;
    } finally {
      const idx = agentFlowState.activeStack.lastIndexOf(node.id);
      if (idx >= 0) agentFlowState.activeStack.splice(idx, 1);
      $.ui.invalidate('ui.render');
    }
  });

  on('command.run', { command: 'crew-agents' }, async ($, e) => {
    try {
      const arg = String((e as Record<string, unknown>)?.args ?? '').trim().toLowerCase();
      const shouldOpen =
        arg === 'open' || arg === 'on'
          ? true
          : arg === 'close' || arg === 'off'
            ? false
            : !crewUiState.panes['crew-agents'];

      crewUiState.panes['crew-agents'] = shouldOpen;
      if (shouldOpen) {
        await $.ui.open({
          id: PANE_META['crew-agents'].id,
          title: PANE_META['crew-agents'].title,
          focus: true,
          immediate: true,
          closeOnEscape: true,
        });
      } else {
        await $.ui.close({ id: PANE_META['crew-agents'].id });
      }
      $.ui.invalidate('ui.render');
      return {
        text: shouldOpen
          ? `🎭 Agent Flow opened (${agentFlowState.nodes.length} subagent(s) traced).`
          : '🎭 Agent Flow closed.',
      };
    } catch {
      return { text: '🎭 Unable to toggle the Agent Flow panel.' };
    }
  });

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const prev = await next(e);
    if (!crewUiState.bands.agents || agentFlowState.nodes.length === 0) {
      return prev;
    }

    const running = agentFlowState.nodes.filter((n) => n.status === 'running');
    if (running.length === 0) return prev;
    const names = running.slice(0, 2).map((n) => n.agentName).join(',');
    const more = running.length > 2 ? `+${running.length - 2}` : '';
    return addBandSegments(prev, {
      slot: 'left',
      order: 30,
      color: 'magenta',
      text: `🎭${names}${more}`,
    });
  });

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (resolvePaneRequestId(e as Record<string, unknown>) !== PANE_META['crew-agents'].id) {
      return next(e);
    }

    const { Box, Text } = $.ui.resolve(e);
    const nodes = agentFlowState.nodes;

    return Box({
      flexDirection: 'column',
      padding: 1,
      gap: 1,
      children: [
        Text({
          bold: true,
          color: 'magenta',
          children: [`🎭 Subagent Execution Tree (${nodes.length})`],
        }),
        ...(nodes.length === 0
          ? [
              Text({
                dimColor: true,
                children: ['No crew-mates subagent launched during this session.'],
              }),
            ]
          : nodes.map((node, idx) =>
              Text({
                color:
                  node.status === 'running'
                    ? 'yellow'
                    : node.status === 'done'
                      ? 'green'
                      : 'red',
                children: [
                  `Tour #${node.turnNumber} ${formatAgentNodeLine(node, idx === nodes.length - 1)} — ${node.label}`,
                ],
              }),
            )),
      ],
    });
  });
}

export const register = registerAgentFlow;
