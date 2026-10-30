/**
 * Mod 7 — batch-progress.ts (Avancement Task & Batch)
 *
 * - Parse le fichier de tâche actif pour compter les cases cochées (`- [x]` vs `- [s]`/`- [ ]`) :
 *   `Task : [████░░] 4/6 (66%)`
 * - Parse le fichier de batch global (`crew/CLAUDE_BATCH.md`) pour afficher la progression globale :
 *   `Batch : [██████░░] 3/4 tasks (75%)`
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  filterCrewTaskSlugs,
  joinPath,
  parseClaudeBatch,
  parseCrewLock,
  parseTaskMarkdown,
  renderDiscreteBar,
  resolveSessionIdFromEvent,
  type ModRegistrar,
  type ParsedBatchSection,
  addBandSegments,
} from './shared.ts';

export interface BatchProgressState {
  hasCrewScaffold: boolean;
  taskSlug: string | null;
  taskTitle: string | null;
  taskDone: number;
  taskStarted: number;
  taskTodo: number;
  taskTotal: number;
  taskPercent: number;
  batchKey: string | null;
  batchHeader: string | null;
  batchDoneTasks: number;
  batchTotalTasks: number;
  batchPercent: number;
}

export const batchProgressState: BatchProgressState = {
  hasCrewScaffold: false,
  taskSlug: null,
  taskTitle: null,
  taskDone: 0,
  taskStarted: 0,
  taskTodo: 0,
  taskTotal: 0,
  taskPercent: 0,
  batchKey: null,
  batchHeader: null,
  batchDoneTasks: 0,
  batchTotalTasks: 0,
  batchPercent: 0,
};

export function formatTaskProgressSegment(state: BatchProgressState = batchProgressState): string {
  if (!state.taskSlug) {
    return 'Task : [░░░░░░] 0/0 (aucune tâche active)';
  }
  const bar = renderDiscreteBar(state.taskDone, state.taskTotal, 6);
  return `Task : ${bar} ${state.taskDone}/${state.taskTotal} (${state.taskPercent}%)`;
}

export function formatBatchProgressSegment(state: BatchProgressState = batchProgressState): string {
  if (!state.batchKey || state.batchTotalTasks === 0) {
    return 'Batch : [░░░░░░░░] 0/0 tasks (0%)';
  }
  const bar = renderDiscreteBar(state.batchDoneTasks, state.batchTotalTasks, 8);
  return `Batch : ${bar} ${state.batchDoneTasks}/${state.batchTotalTasks} tasks (${state.batchPercent}%)`;
}

export function formatCombinedBatchProgressLine(
  state: BatchProgressState = batchProgressState,
): string {
  const parts = [formatTaskProgressSegment(state), formatBatchProgressSegment(state)];
  if (crewRuntimeState.etaSummaryLine) {
    parts.push(crewRuntimeState.etaSummaryLine);
  }
  return parts.join('  │  ');
}

export function selectActiveBatchSection(
  sections: ParsedBatchSection[],
  preferredBatchKey: string | null,
  activeTaskSlug: string | null,
): ParsedBatchSection | null {
  if (preferredBatchKey) {
    const byKey = sections.find((s) => s.key === preferredBatchKey);
    if (byKey && byKey.tasks.length > 0) return byKey;
  }
  if (activeTaskSlug) {
    const byTask = sections.find((s) => s.tasks.some((t) => t.slug === activeTaskSlug));
    if (byTask) return byTask;
  }
  return sections.find((s) => s.tasks.length > 0) || null;
}

const MUTATING_TOOLS = new Set(['edit', 'write', 'multiedit', 'bash']);

export function registerBatchProgress(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    const sid = resolveSessionIdFromEvent(e as Record<string, unknown>);
    const projectRoot = $.env.get('CLAUDE_PROJECT_DIR') || crewRuntimeState.projectRoot || '.';
    const mainRoot = crewRuntimeState.mainRoot || projectRoot;

    const crewStat = await $.fs.stat(joinPath(projectRoot, 'crew')).catch(() => null);
    batchProgressState.hasCrewScaffold = Boolean(crewStat);

    const crewLockText = await $.fs
      .read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_lock.json'))
      .catch(() => '');
    const crewLocks = parseCrewLock(crewLockText, Date.now());
    const myLock = crewLocks[sid];
    const takenByOthers = new Set<string>();
    for (const [otherSid, info] of Object.entries(crewLocks)) {
      if (otherSid !== sid) {
        for (const t of info.tasks) takenByOthers.add(t);
      }
    }

    const localCurrent = filterCrewTaskSlugs(
      await $.fs.list(joinPath(projectRoot, 'crew/CURRENT_TASKS')).catch(() => []),
    );
    const mainCurrent =
      mainRoot !== projectRoot
        ? filterCrewTaskSlugs(
            await $.fs.list(joinPath(mainRoot, 'crew/CURRENT_TASKS')).catch(() => []),
          )
        : [];
    const currentCandidates = Array.from(new Set([...localCurrent, ...mainCurrent]));

    let chosenSlug: string | null = null;
    if (myLock && myLock.tasks.length > 0) {
      chosenSlug = myLock.tasks[0];
    } else {
      chosenSlug = currentCandidates.find((s) => !takenByOthers.has(s)) || currentCandidates[0] || null;
    }

    if (chosenSlug) {
      const taskMd =
        (await $.fs
          .read(joinPath(projectRoot, 'crew/CURRENT_TASKS', chosenSlug))
          .catch(() => '')) ||
        (await $.fs.read(joinPath(mainRoot, 'crew/CURRENT_TASKS', chosenSlug)).catch(() => ''));

      if (taskMd) {
        const parsedTask = parseTaskMarkdown(chosenSlug, taskMd);
        batchProgressState.taskSlug = parsedTask.slug;
        batchProgressState.taskTitle = parsedTask.title;
        batchProgressState.taskDone = parsedTask.done;
        batchProgressState.taskStarted = parsedTask.started;
        batchProgressState.taskTodo = parsedTask.todo;
        batchProgressState.taskTotal = parsedTask.total;
        batchProgressState.taskPercent = parsedTask.percent;
      } else {
        batchProgressState.taskSlug = chosenSlug;
        batchProgressState.taskTitle = chosenSlug.replace(/\.md$/i, '');
        batchProgressState.taskDone = 0;
        batchProgressState.taskStarted = 0;
        batchProgressState.taskTodo = 0;
        batchProgressState.taskTotal = 0;
        batchProgressState.taskPercent = 0;
      }
    } else {
      batchProgressState.taskSlug = null;
      batchProgressState.taskTitle = null;
      batchProgressState.taskDone = 0;
      batchProgressState.taskStarted = 0;
      batchProgressState.taskTodo = 0;
      batchProgressState.taskTotal = 0;
      batchProgressState.taskPercent = 0;
    }

    const batchMd =
      (await $.fs.read(joinPath(projectRoot, 'crew/CLAUDE_BATCH.md')).catch(() => '')) ||
      (await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_BATCH.md')).catch(() => ''));
    const parsedBatch = parseClaudeBatch(batchMd);

    const todoSet = new Set(
      filterCrewTaskSlugs(await $.fs.list(joinPath(mainRoot, 'crew/TODO')).catch(() => [])),
    );
    const pausedSet = new Set(
      filterCrewTaskSlugs(await $.fs.list(joinPath(mainRoot, 'crew/PAUSED')).catch(() => [])),
    );
    const currentSet = new Set([
      ...currentCandidates,
      ...Object.values(crewLocks).flatMap((l) => l.tasks),
    ]);

    const section = selectActiveBatchSection(
      parsedBatch.sections,
      myLock?.batch ?? null,
      batchProgressState.taskSlug,
    );

    if (section) {
      let doneTasks = 0;
      for (const t of section.tasks) {
        const stillOpen = todoSet.has(t.slug) || currentSet.has(t.slug) || pausedSet.has(t.slug);
        if (t.closed || !stillOpen) {
          doneTasks += 1;
        }
      }
      const totalTasks = section.tasks.length;
      batchProgressState.batchKey = section.key;
      batchProgressState.batchHeader = section.header;
      batchProgressState.batchDoneTasks = doneTasks;
      batchProgressState.batchTotalTasks = totalTasks;
      batchProgressState.batchPercent =
        totalTasks > 0 ? Math.floor((doneTasks / totalTasks) * 100) : 0;
      batchProgressState.hasCrewScaffold = true;
    } else {
      batchProgressState.batchKey = null;
      batchProgressState.batchHeader = null;
      batchProgressState.batchDoneTasks = 0;
      batchProgressState.batchTotalTasks = 0;
      batchProgressState.batchPercent = 0;
    }

    crewRuntimeState.activeTaskSlug = batchProgressState.taskSlug;
    crewRuntimeState.activeTaskDone = batchProgressState.taskDone;
    crewRuntimeState.activeTaskTotal = batchProgressState.taskTotal;
    crewRuntimeState.activeBatchKey = batchProgressState.batchKey;
    crewRuntimeState.activeBatchHeader = batchProgressState.batchHeader;
    crewRuntimeState.activeBatchDoneTasks = batchProgressState.batchDoneTasks;
    crewRuntimeState.activeBatchTotalTasks = batchProgressState.batchTotalTasks;

    $.ui.invalidate('ui.render');
    return next(e);
  });

  on('tool.call', async ($, e, next) => {
    const result = await next(e);
    try {
      const ev = (e || {}) as Record<string, unknown>;
      const toolName = String(ev.tool ?? ev.name ?? '').toLowerCase();
      if (!MUTATING_TOOLS.has(toolName)) return result;

      const projectRoot = crewRuntimeState.projectRoot || '.';
      const mainRoot = crewRuntimeState.mainRoot || projectRoot;
      const sid = crewRuntimeState.sessionId;

      const crewLockText = await $.fs
        .read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_lock.json'))
        .catch(() => '');
      const crewLocks = parseCrewLock(crewLockText, Date.now());
      const myLock = crewLocks[sid];

      const localCurrent = filterCrewTaskSlugs(
        await $.fs.list(joinPath(projectRoot, 'crew/CURRENT_TASKS')).catch(() => []),
      );
      const chosenSlug = myLock?.tasks?.[0] || localCurrent[0] || null;

      if (chosenSlug) {
        const taskMd =
          (await $.fs
            .read(joinPath(projectRoot, 'crew/CURRENT_TASKS', chosenSlug))
            .catch(() => '')) ||
          (await $.fs.read(joinPath(mainRoot, 'crew/CURRENT_TASKS', chosenSlug)).catch(() => ''));
        if (taskMd) {
          const parsedTask = parseTaskMarkdown(chosenSlug, taskMd);
          batchProgressState.taskSlug = parsedTask.slug;
          batchProgressState.taskTitle = parsedTask.title;
          batchProgressState.taskDone = parsedTask.done;
          batchProgressState.taskStarted = parsedTask.started;
          batchProgressState.taskTodo = parsedTask.todo;
          batchProgressState.taskTotal = parsedTask.total;
          batchProgressState.taskPercent = parsedTask.percent;
        }
      } else {
        batchProgressState.taskSlug = null;
        batchProgressState.taskDone = 0;
        batchProgressState.taskTotal = 0;
        batchProgressState.taskPercent = 0;
      }

      const batchMd =
        (await $.fs.read(joinPath(projectRoot, 'crew/CLAUDE_BATCH.md')).catch(() => '')) ||
        (await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_BATCH.md')).catch(() => ''));
      const parsedBatch = parseClaudeBatch(batchMd);
      const todoSet = new Set(
        filterCrewTaskSlugs(await $.fs.list(joinPath(mainRoot, 'crew/TODO')).catch(() => [])),
      );
      const pausedSet = new Set(
        filterCrewTaskSlugs(await $.fs.list(joinPath(mainRoot, 'crew/PAUSED')).catch(() => [])),
      );
      const currentSet = new Set([
        ...localCurrent,
        ...Object.values(crewLocks).flatMap((l) => l.tasks),
      ]);

      const section = selectActiveBatchSection(
        parsedBatch.sections,
        myLock?.batch ?? batchProgressState.batchKey,
        batchProgressState.taskSlug,
      );
      if (section) {
        let doneTasks = 0;
        for (const t of section.tasks) {
          const stillOpen = todoSet.has(t.slug) || currentSet.has(t.slug) || pausedSet.has(t.slug);
          if (t.closed || !stillOpen) doneTasks += 1;
        }
        batchProgressState.batchKey = section.key;
        batchProgressState.batchHeader = section.header;
        batchProgressState.batchDoneTasks = doneTasks;
        batchProgressState.batchTotalTasks = section.tasks.length;
        batchProgressState.batchPercent =
          section.tasks.length > 0 ? Math.floor((doneTasks / section.tasks.length) * 100) : 0;
      }

      crewRuntimeState.activeTaskSlug = batchProgressState.taskSlug;
      crewRuntimeState.activeTaskDone = batchProgressState.taskDone;
      crewRuntimeState.activeTaskTotal = batchProgressState.taskTotal;
      crewRuntimeState.activeBatchKey = batchProgressState.batchKey;
      crewRuntimeState.activeBatchHeader = batchProgressState.batchHeader;
      crewRuntimeState.activeBatchDoneTasks = batchProgressState.batchDoneTasks;
      crewRuntimeState.activeBatchTotalTasks = batchProgressState.batchTotalTasks;

      $.ui.invalidate('ui.render');
    } catch {
      // Never disrupt tool execution
    }
    return result;
  });

  on('ui.render', { component: 'AbovePrompt' }, async (_$, e, next) => {
    const prev = await next(e);
    if (!crewUiState.bands.progress) return prev;
    if (
      !batchProgressState.hasCrewScaffold &&
      !batchProgressState.taskSlug &&
      !batchProgressState.batchKey
    ) {
      return prev;
    }
    return addBandSegments(prev, {
      slot: 'left',
      order: 20,
      color: batchProgressState.taskSlug ? 'green' : 'gray',
      text: formatCombinedBatchProgressLine(),
    });
  });
}

export const register = registerBatchProgress;
