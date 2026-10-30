/**
 * Mod 8 — batch-dependency-graph.ts (Kanban & Dépendances)
 *
 * Panneau UI (`/crew-board`) affichant les colonnes :
 * `Todo | In Progress | Done | Blocked`
 * du batch en cours (et les inter-dépendances de zones entre batchs),
 * liant chaque tâche à la session active correspondante.
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  filterCrewTaskSlugs,
  joinPath,
  PANE_META,
  parseClaudeBatch,
  parseCrewLock,
  parseSessionsLock,
  parseTaskMarkdown,
  resolvePaneRequestId,
  zonesOverlap,
  type CrewLockSessionEntry,
  type ModRegistrar,
  type ParsedBatchSection,
  type ParsedTaskInfo,
} from './shared.ts';
import { SESSIONS_LOCK_REL_PATH } from './crew-radar.ts';

export type KanbanColumnId = 'todo' | 'inProgress' | 'done' | 'blocked';

export interface KanbanCard {
  slug: string;
  title: string;
  column: KanbanColumnId;
  sessionId: string | null;
  worktree: string | null;
  checkboxSummary: string | null;
  blockReason: string | null;
}

export interface BatchBoardView {
  batchHeader: string;
  batchKey: string;
  zonePaths: string[];
  overlappingBatches: Array<{ batchKey: string; sessionId: string | null }>;
  columns: {
    todo: KanbanCard[];
    inProgress: KanbanCard[];
    done: KanbanCard[];
    blocked: KanbanCard[];
  };
}

export const batchBoardState: {
  activeBoard: BatchBoardView | null;
  allBoards: BatchBoardView[];
  unclassified: string[];
} = {
  activeBoard: null,
  allBoards: [],
  unclassified: [],
};

export interface BuildBoardsInput {
  sections: ParsedBatchSection[];
  unclassified: string[];
  todoSlugs: Set<string>;
  currentSlugs: Set<string>;
  pausedSlugs: Set<string>;
  taskInfos: Map<string, ParsedTaskInfo>;
  crewLocks: Record<string, CrewLockSessionEntry>;
  liveSessionTasks: Record<string, string>;
  preferredBatchKey: string | null;
  currentSessionId: string;
}

export function buildKanbanBoards(input: BuildBoardsInput): {
  activeBoard: BatchBoardView | null;
  allBoards: BatchBoardView[];
} {
  const slugToSession = new Map<string, { sessionId: string; worktree: string | null }>();
  for (const [sid, entry] of Object.entries(input.crewLocks)) {
    for (const slug of entry.tasks) {
      slugToSession.set(slug, { sessionId: sid, worktree: entry.worktree });
    }
  }
  for (const [slug, sid] of Object.entries(input.liveSessionTasks)) {
    if (!slugToSession.has(slug)) {
      slugToSession.set(slug, { sessionId: sid, worktree: null });
    }
  }

  // Determine which batch sections currently hold active tasks and by which session
  const sectionActiveSessions = new Map<string, Set<string>>();
  for (const sec of input.sections) {
    const sids = new Set<string>();
    for (const t of sec.tasks) {
      const owner = slugToSession.get(t.slug);
      if (owner) sids.add(owner.sessionId);
      else if (input.currentSlugs.has(t.slug) || input.pausedSlugs.has(t.slug)) {
        sids.add(input.currentSessionId);
      }
    }
    for (const [sid, entry] of Object.entries(input.crewLocks)) {
      if (entry.batch === sec.key) sids.add(sid);
    }
    sectionActiveSessions.set(sec.key, sids);
  }

  const boards: BatchBoardView[] = [];

  for (const sec of input.sections) {
    const overlappingBatches: Array<{ batchKey: string; sessionId: string | null }> = [];
    for (const other of input.sections) {
      if (other.key === sec.key) continue;
      if (zonesOverlap(sec.zonePaths, other.zonePaths)) {
        const otherSids = Array.from(sectionActiveSessions.get(other.key) || []);
        overlappingBatches.push({
          batchKey: other.key,
          sessionId: otherSids[0] || null,
        });
      }
    }

    // Active zone conflict with a DIFFERENT session blocks starting Todo tasks in this batch
    const foreignZoneBlocker = overlappingBatches.find(
      (o) => o.sessionId !== null && o.sessionId !== input.currentSessionId,
    );

    const columns: BatchBoardView['columns'] = {
      todo: [],
      inProgress: [],
      done: [],
      blocked: [],
    };

    let seenActiveOrPausedPredecessor: string | null = null;

    for (const taskRef of sec.tasks) {
      const slug = taskRef.slug;
      const info = input.taskInfos.get(slug);
      const title = info?.title || slug.replace(/\.md$/i, '');
      const checkboxSummary = info && info.total > 0 ? `${info.done}/${info.total}` : null;
      const sessionLink = slugToSession.get(slug) || null;

      const isPaused = input.pausedSlugs.has(slug);
      const isInCurrent = input.currentSlugs.has(slug) || (Boolean(sessionLink) && !isPaused);
      const isInTodo = input.todoSlugs.has(slug);
      const isDone = taskRef.closed || (!isPaused && !isInCurrent && !isInTodo);

      if (isDone) {
        columns.done.push({
          slug,
          title,
          column: 'done',
          sessionId: null,
          worktree: null,
          checkboxSummary,
          blockReason: null,
        });
        continue;
      }

      if (isPaused) {
        seenActiveOrPausedPredecessor = seenActiveOrPausedPredecessor || slug;
        columns.blocked.push({
          slug,
          title,
          column: 'blocked',
          sessionId: sessionLink?.sessionId || null,
          worktree: sessionLink?.worktree || null,
          checkboxSummary,
          blockReason: '⏸️ PAUSED (validation dev)',
        });
        continue;
      }

      if (isInCurrent) {
        seenActiveOrPausedPredecessor = seenActiveOrPausedPredecessor || slug;
        columns.inProgress.push({
          slug,
          title,
          column: 'inProgress',
          sessionId: sessionLink?.sessionId || input.currentSessionId,
          worktree: sessionLink?.worktree || null,
          checkboxSummary,
          blockReason: null,
        });
        continue;
      }

      // Task is in TODO: check explicit dependencies, cross-session zone lock, or active batch sequence
      const unmetExplicitDep = (info?.explicitDeps || []).find(
        (dep) => input.todoSlugs.has(dep) || input.currentSlugs.has(dep) || input.pausedSlugs.has(dep),
      );

      if (foreignZoneBlocker) {
        columns.blocked.push({
          slug,
          title,
          column: 'blocked',
          sessionId: foreignZoneBlocker.sessionId,
          worktree: null,
          checkboxSummary,
          blockReason: `🔒 Zone verrouillée par ${foreignZoneBlocker.batchKey} (@${(foreignZoneBlocker.sessionId || '').slice(0, 8)})`,
        });
      } else if (unmetExplicitDep) {
        columns.blocked.push({
          slug,
          title,
          column: 'blocked',
          sessionId: slugToSession.get(unmetExplicitDep)?.sessionId || null,
          worktree: null,
          checkboxSummary,
          blockReason: `⛓️ Dépend de ${unmetExplicitDep}`,
        });
      } else if (seenActiveOrPausedPredecessor) {
        columns.blocked.push({
          slug,
          title,
          column: 'blocked',
          sessionId: slugToSession.get(seenActiveOrPausedPredecessor)?.sessionId || null,
          worktree: null,
          checkboxSummary,
          blockReason: `⏳ Séquence après ${seenActiveOrPausedPredecessor}`,
        });
      } else {
        columns.todo.push({
          slug,
          title,
          column: 'todo',
          sessionId: null,
          worktree: null,
          checkboxSummary,
          blockReason: null,
        });
      }
    }

    boards.push({
      batchHeader: sec.header,
      batchKey: sec.key,
      zonePaths: sec.zonePaths,
      overlappingBatches,
      columns,
    });
  }

  let activeBoard: BatchBoardView | null = null;
  if (input.preferredBatchKey) {
    activeBoard = boards.find((b) => b.batchKey === input.preferredBatchKey) || null;
  }
  if (!activeBoard) {
    activeBoard =
      boards.find((b) => b.columns.inProgress.length > 0 || b.columns.blocked.length > 0) ||
      boards.find(
        (b) => b.columns.todo.length > 0 || b.columns.done.length > 0,
      ) ||
      null;
  }

  return { activeBoard, allBoards: boards };
}

export function formatKanbanCardLine(card: KanbanCard): string {
  const sessBadge = card.sessionId ? ` [@sess:${card.sessionId.slice(0, 8)}]` : '';
  const cbBadge = card.checkboxSummary ? ` (${card.checkboxSummary})` : '';
  const reasonBadge = card.blockReason ? ` — ${card.blockReason}` : '';
  return `• ${card.slug}${cbBadge}${sessBadge}${reasonBadge}`;
}

export function registerBatchDependencyGraph(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    await $.command
      .register({
        name: 'crew-board',
        description: 'Ouvrir/fermer le Kanban & graphe de dépendances du batch (Todo | In Progress | Done | Blocked)',
      })
      .catch(() => undefined);

    const projectRoot = $.env.get('CLAUDE_PROJECT_DIR') || crewRuntimeState.projectRoot || '.';
    const mainRoot = crewRuntimeState.mainRoot || projectRoot;

    const batchMd =
      (await $.fs.read(joinPath(projectRoot, 'crew/CLAUDE_BATCH.md')).catch(() => '')) ||
      (await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_BATCH.md')).catch(() => ''));
    const parsedBatch = parseClaudeBatch(batchMd);

    const todoList = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/TODO')).catch(() => []),
    );
    const currentListMain = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/CURRENT_TASKS')).catch(() => []),
    );
    const currentListLocal =
      projectRoot !== mainRoot
        ? filterCrewTaskSlugs(
            await $.fs.list(joinPath(projectRoot, 'crew/CURRENT_TASKS')).catch(() => []),
          )
        : [];
    const pausedList = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/PAUSED')).catch(() => []),
    );

    const taskInfos = new Map<string, ParsedTaskInfo>();
    for (const slug of todoList) {
      const md = await $.fs.read(joinPath(mainRoot, 'crew/TODO', slug)).catch(() => '');
      if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
    }
    for (const slug of new Set([...currentListMain, ...currentListLocal])) {
      const md =
        (await $.fs.read(joinPath(projectRoot, 'crew/CURRENT_TASKS', slug)).catch(() => '')) ||
        (await $.fs.read(joinPath(mainRoot, 'crew/CURRENT_TASKS', slug)).catch(() => ''));
      if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
    }
    for (const slug of pausedList) {
      const md = await $.fs.read(joinPath(mainRoot, 'crew/PAUSED', slug)).catch(() => '');
      if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
    }

    const crewLockText = await $.fs
      .read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_lock.json'))
      .catch(() => '');
    const crewLocks = parseCrewLock(crewLockText, Date.now());
    const liveLockText = await $.fs
      .read(joinPath(mainRoot, SESSIONS_LOCK_REL_PATH))
      .catch(() => '');
    const liveLocks = parseSessionsLock(liveLockText, Date.now());
    const liveSessionTasks: Record<string, string> = {};
    for (const [sid, info] of Object.entries(liveLocks.sessions)) {
      if (info.activeTask) liveSessionTasks[info.activeTask] = sid;
    }

    const built = buildKanbanBoards({
      sections: parsedBatch.sections,
      unclassified: parsedBatch.unclassified,
      todoSlugs: new Set(todoList),
      currentSlugs: new Set([...currentListMain, ...currentListLocal]),
      pausedSlugs: new Set(pausedList),
      taskInfos,
      crewLocks,
      liveSessionTasks,
      preferredBatchKey: crewRuntimeState.activeBatchKey,
      currentSessionId: crewRuntimeState.sessionId,
    });

    batchBoardState.activeBoard = built.activeBoard;
    batchBoardState.allBoards = built.allBoards;
    batchBoardState.unclassified = parsedBatch.unclassified;

    return next(e);
  });

  on('turn.complete', async ($, e, next) => {
    const projectRoot = crewRuntimeState.projectRoot || '.';
    const mainRoot = crewRuntimeState.mainRoot || projectRoot;

    const batchMd =
      (await $.fs.read(joinPath(projectRoot, 'crew/CLAUDE_BATCH.md')).catch(() => '')) ||
      (await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_BATCH.md')).catch(() => ''));
    const parsedBatch = parseClaudeBatch(batchMd);

    const todoList = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/TODO')).catch(() => []),
    );
    const currentListMain = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/CURRENT_TASKS')).catch(() => []),
    );
    const currentListLocal =
      projectRoot !== mainRoot
        ? filterCrewTaskSlugs(
            await $.fs.list(joinPath(projectRoot, 'crew/CURRENT_TASKS')).catch(() => []),
          )
        : [];
    const pausedList = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/PAUSED')).catch(() => []),
    );

    const taskInfos = new Map<string, ParsedTaskInfo>();
    for (const slug of todoList) {
      const md = await $.fs.read(joinPath(mainRoot, 'crew/TODO', slug)).catch(() => '');
      if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
    }
    for (const slug of new Set([...currentListMain, ...currentListLocal])) {
      const md =
        (await $.fs.read(joinPath(projectRoot, 'crew/CURRENT_TASKS', slug)).catch(() => '')) ||
        (await $.fs.read(joinPath(mainRoot, 'crew/CURRENT_TASKS', slug)).catch(() => ''));
      if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
    }
    for (const slug of pausedList) {
      const md = await $.fs.read(joinPath(mainRoot, 'crew/PAUSED', slug)).catch(() => '');
      if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
    }

    const crewLockText = await $.fs
      .read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_lock.json'))
      .catch(() => '');
    const crewLocks = parseCrewLock(crewLockText, Date.now());

    const liveLockText = await $.fs
      .read(joinPath(mainRoot, SESSIONS_LOCK_REL_PATH))
      .catch(() => '');
    const liveLocks = parseSessionsLock(liveLockText, Date.now());
    const liveSessionTasks: Record<string, string> = {};
    for (const [sid, info] of Object.entries(liveLocks.sessions)) {
      if (info.activeTask) liveSessionTasks[info.activeTask] = sid;
    }

    const built = buildKanbanBoards({
      sections: parsedBatch.sections,
      unclassified: parsedBatch.unclassified,
      todoSlugs: new Set(todoList),
      currentSlugs: new Set([...currentListMain, ...currentListLocal]),
      pausedSlugs: new Set(pausedList),
      taskInfos,
      crewLocks,
      liveSessionTasks,
      preferredBatchKey: crewRuntimeState.activeBatchKey,
      currentSessionId: crewRuntimeState.sessionId,
    });

    batchBoardState.activeBoard = built.activeBoard;
    batchBoardState.allBoards = built.allBoards;
    batchBoardState.unclassified = parsedBatch.unclassified;

    $.ui.invalidate('ui.render');
    return next(e);
  });

  on('command.run', { command: 'crew-board' }, async ($, e) => {
    try {
      const projectRoot = crewRuntimeState.projectRoot || '.';
      const mainRoot = crewRuntimeState.mainRoot || projectRoot;

      // Refresh snapshot immediately on command invocation
      const batchMd =
        (await $.fs.read(joinPath(projectRoot, 'crew/CLAUDE_BATCH.md')).catch(() => '')) ||
        (await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_BATCH.md')).catch(() => ''));
      const parsedBatch = parseClaudeBatch(batchMd);
      const todoList = filterCrewTaskSlugs(
        await $.fs.list(joinPath(mainRoot, 'crew/TODO')).catch(() => []),
      );
      const currentListMain = filterCrewTaskSlugs(
        await $.fs.list(joinPath(mainRoot, 'crew/CURRENT_TASKS')).catch(() => []),
      );
      const currentListLocal =
        projectRoot !== mainRoot
          ? filterCrewTaskSlugs(
              await $.fs.list(joinPath(projectRoot, 'crew/CURRENT_TASKS')).catch(() => []),
            )
          : [];
      const pausedList = filterCrewTaskSlugs(
        await $.fs.list(joinPath(mainRoot, 'crew/PAUSED')).catch(() => []),
      );

      const taskInfos = new Map<string, ParsedTaskInfo>();
      for (const slug of todoList) {
        const md = await $.fs.read(joinPath(mainRoot, 'crew/TODO', slug)).catch(() => '');
        if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
      }
      for (const slug of new Set([...currentListMain, ...currentListLocal])) {
        const md =
          (await $.fs.read(joinPath(projectRoot, 'crew/CURRENT_TASKS', slug)).catch(() => '')) ||
          (await $.fs.read(joinPath(mainRoot, 'crew/CURRENT_TASKS', slug)).catch(() => ''));
        if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
      }
      for (const slug of pausedList) {
        const md = await $.fs.read(joinPath(mainRoot, 'crew/PAUSED', slug)).catch(() => '');
        if (md) taskInfos.set(slug, parseTaskMarkdown(slug, md));
      }

      const crewLockText = await $.fs
        .read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_lock.json'))
        .catch(() => '');
      const crewLocks = parseCrewLock(crewLockText, Date.now());
      const liveLockText = await $.fs
        .read(joinPath(mainRoot, SESSIONS_LOCK_REL_PATH))
        .catch(() => '');
      const liveLocks = parseSessionsLock(liveLockText, Date.now());
      const liveSessionTasks: Record<string, string> = {};
      for (const [sid, info] of Object.entries(liveLocks.sessions)) {
        if (info.activeTask) liveSessionTasks[info.activeTask] = sid;
      }

      const built = buildKanbanBoards({
        sections: parsedBatch.sections,
        unclassified: parsedBatch.unclassified,
        todoSlugs: new Set(todoList),
        currentSlugs: new Set([...currentListMain, ...currentListLocal]),
        pausedSlugs: new Set(pausedList),
        taskInfos,
        crewLocks,
        liveSessionTasks,
        preferredBatchKey: crewRuntimeState.activeBatchKey,
        currentSessionId: crewRuntimeState.sessionId,
      });

      batchBoardState.activeBoard = built.activeBoard;
      batchBoardState.allBoards = built.allBoards;
      batchBoardState.unclassified = parsedBatch.unclassified;

      const arg = String((e as Record<string, unknown>)?.args ?? '').trim().toLowerCase();
      const shouldOpen =
        arg === 'open' || arg === 'on'
          ? true
          : arg === 'close' || arg === 'off'
            ? false
            : !crewUiState.panes['crew-board'];

      crewUiState.panes['crew-board'] = shouldOpen;
      if (shouldOpen) {
        await $.ui.open({
          id: PANE_META['crew-board'].id,
          title: PANE_META['crew-board'].title,
          focus: true,
          immediate: true,
          closeOnEscape: true,
        });
      } else {
        await $.ui.close({ id: PANE_META['crew-board'].id });
      }
      $.ui.invalidate('ui.render');

      return {
        text: shouldOpen
          ? `📋 Crew Kanban Board ouvert (${built.allBoards.length} batch(s) analysés).`
          : '📋 Crew Kanban Board fermé.',
      };
    } catch {
      return { text: '📋 Impossible de basculer le panneau Crew Board.' };
    }
  });

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (resolvePaneRequestId(e as Record<string, unknown>) !== PANE_META['crew-board'].id) {
      return next(e);
    }

    const { Box, Text } = $.ui.resolve(e);
    const board = batchBoardState.activeBoard;

    if (!board) {
      return Box({
        flexDirection: 'column',
        padding: 1,
        children: [
          Text({
            bold: true,
            color: 'cyan',
            children: ['📋 Crew Kanban & Dépendances (Todo | In Progress | Done | Blocked)'],
          }),
          Text({
            dimColor: true,
            children: ['Aucun batch actif trouvé dans crew/CLAUDE_BATCH.md.'],
          }),
        ],
      });
    }

    const renderCol = (title: string, color: string, cards: KanbanCard[]) =>
      Box({
        flexDirection: 'column',
        paddingX: 1,
        children: [
          Text({ bold: true, color, children: [`${title} (${cards.length})`] }),
          ...(cards.length === 0
            ? [Text({ dimColor: true, children: ['  (vide)'] })]
            : cards.map((c) => Text({ children: [`  ${formatKanbanCardLine(c)}`] }))),
        ],
      });

    const overlapText =
      board.overlappingBatches.length > 0
        ? board.overlappingBatches
            .map(
              (o) =>
                `${o.batchKey}${o.sessionId ? ` (@sess:${o.sessionId.slice(0, 8)})` : ' (libre)'}`,
            )
            .join(', ')
        : 'aucune collision de zone';

    return Box({
      flexDirection: 'column',
      padding: 1,
      gap: 1,
      children: [
        Text({
          bold: true,
          color: 'cyan',
          children: [`📋 ${board.batchHeader}`],
        }),
        Text({
          dimColor: true,
          children: [
            `Zone : ${board.zonePaths.join(', ') || '(non déclarée)'}  │  Dépendances zones : ${overlapText}`,
          ],
        }),
        Text({
          bold: true,
          children: ['Colonnes : Todo | In Progress | Done | Blocked'],
        }),
        renderCol('📋 Todo', 'cyan', board.columns.todo),
        renderCol('⚡ In Progress', 'green', board.columns.inProgress),
        renderCol('✅ Done', 'gray', board.columns.done),
        renderCol('🔒 Blocked', 'red', board.columns.blocked),
      ],
    });
  });
}

export const register = registerBatchDependencyGraph;
