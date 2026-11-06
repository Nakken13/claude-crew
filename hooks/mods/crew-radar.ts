/**
 * Mod 6 — crew-radar.ts (Compteurs globaux)
 *
 * Shows in the status bar (line above the prompt):
 * `🟢 X Sessions online | ⚡ Y Current Tasks | 📋 Z Todo`
 *
 * Uses a lightweight lock system (`.claude/crew-sessions.lock`) updated on
 * `session.start` / `session.end` (and heartbeat on every turn) and reads the
 * project's global task state (`crew/CURRENT_TASKS/`, `crew/TODO/`, `crew_lock.json`).
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  filterCrewTaskSlugs,
  joinPath,
  parseCrewLock,
  parseGitdirPointer,
  parseSessionsLock,
  resolveSessionIdFromEvent,
  resolveWorktreeMainRoot,
  type ModRegistrar,
  addBandSegments,
} from './shared.ts';

export const SESSIONS_LOCK_REL_PATH = '.claude/crew-sessions.lock';

export interface CrewRadarState {
  onlineSessions: number;
  currentTasks: number;
  todoTasks: number;
  /** TODO set aside locally (crew_ignored.json): another dev's tasks, excluded from todoTasks. */
  othersTasks: number;
  pausedTasks: number;
  sessionIds: string[];
}

export const crewRadarState: CrewRadarState = {
  onlineSessions: 1,
  currentTasks: 0,
  todoTasks: 0,
  othersTasks: 0,
  pausedTasks: 0,
  sessionIds: [],
};

export function formatCrewRadarLine(state: CrewRadarState = crewRadarState): string {
  const base = `🟢 ${state.onlineSessions} Sessions online | ⚡ ${state.currentTasks} Current Tasks | 📋 ${state.todoTasks} Todo`;
  return state.pausedTasks > 0 ? `${base} | ⏸️ ${state.pausedTasks} Paused` : base;
}

/** Short version for the band: `🟢2 ⚡1 📋5 ⏸0` (sessions, in progress, todo, paused); 0 is shown, never omitted; ` 👤N` appended if collab mode sets aside N tasks of other devs. */
export function formatCrewRadarCompact(state: CrewRadarState = crewRadarState): string {
  const others = state.othersTasks > 0 ? ` 👤${state.othersTasks}` : '';
  return `🟢${state.onlineSessions} ⚡${state.currentTasks} 📋${state.todoTasks} ⏸️${state.pausedTasks}${others}`;
}

/** Slugs of `crew/CLAUDE_CONTEXT/crew_ignored.json` ({"ignored": {"x.md": "name"}} or the older list); missing/corrupt -> empty. */
export function parseIgnoredSlugs(text: string): Set<string> {
  try {
    const raw = JSON.parse(text)?.ignored;
    if (Array.isArray(raw)) return new Set(raw.filter((x: unknown): x is string => typeof x === 'string'));
    return raw && typeof raw === 'object' ? new Set(Object.keys(raw)) : new Set();
  } catch {
    return new Set();
  }
}

/** Team mode is on = `remote_claims : true` in crew/CLAUDE_CONTEXT/CREW_CONFIG.md (set by /crew-collab on). */
export function parseCollabOn(configText: string): boolean {
  return /^\s*remote_claims\s*[:=]\s*(true|1|yes|oui|on)\s*$/im.test(configText);
}

export function registerCrewRadar(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    const previousSid = crewRuntimeState.sessionId;
    const sid = resolveSessionIdFromEvent(e as Record<string, unknown>);
    const projectRoot = $.env.get('CLAUDE_PROJECT_DIR') || '.';
    crewRuntimeState.projectRoot = projectRoot;

    // Detect git worktree main root without spawning git (mirrors crew_hook.py _resolve_main_root)
    let mainRoot = projectRoot;
    const gitFileText = await $.fs.read(joinPath(projectRoot, '.git')).catch(() => '');
    const gitdir = gitFileText ? parseGitdirPointer(gitFileText) : null;
    if (gitdir) {
      const absGitdir = joinPath(projectRoot, gitdir);
      const commondirText = await $.fs.read(joinPath(absGitdir, 'commondir')).catch(() => '');
      if (commondirText) {
        mainRoot = resolveWorktreeMainRoot(projectRoot, gitdir, commondirText);
      }
    }
    crewRuntimeState.mainRoot = mainRoot;

    const nowMs = Date.now();
    const nowIso = new Date(nowMs).toISOString();
    const lockPath = joinPath(mainRoot, SESSIONS_LOCK_REL_PATH);
    const rawLock = await $.fs.read(lockPath).catch(() => '');
    const parsedLock = parseSessionsLock(rawLock, nowMs);
    // The fallback id generated when the mod loads is replaced by the real id: do not leave a ghost.
    if (previousSid !== sid) delete parsedLock.sessions[previousSid];

    const existing = parsedLock.sessions[sid];
    parsedLock.sessions[sid] = {
      sessionId: sid,
      startedAt: existing?.startedAt || nowIso,
      updatedAt: nowIso,
      cwd: projectRoot,
      activeTask: existing?.activeTask ?? crewRuntimeState.activeTaskSlug,
      batch: existing?.batch ?? crewRuntimeState.activeBatchKey,
      activeFiles: existing?.activeFiles ?? {},
    };

    await $.fs.write(lockPath, JSON.stringify(parsedLock, null, 2) + '\n').catch(() => undefined);

    const crewLockText = await $.fs
      .read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_lock.json'))
      .catch(() => '');
    const crewLocks = parseCrewLock(crewLockText, nowMs);

    const allSessionIds = new Set<string>([
      sid,
      ...Object.keys(parsedLock.sessions),
      ...Object.keys(crewLocks),
    ]);

    const currentSlugsMain = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/CURRENT_TASKS')).catch(() => []),
    );
    const currentSlugsLocal =
      projectRoot !== mainRoot
        ? filterCrewTaskSlugs(
            await $.fs.list(joinPath(projectRoot, 'crew/CURRENT_TASKS')).catch(() => []),
          )
        : [];
    const lockedSlugs = Object.values(crewLocks).flatMap((s) => s.tasks);
    const uniqueCurrentTasks = new Set<string>([
      ...currentSlugsMain,
      ...currentSlugsLocal,
      ...lockedSlugs,
    ]);

    const todoAll = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/TODO')).catch(() => []),
    );
    const collabOn = parseCollabOn(
      await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/CREW_CONFIG.md')).catch(() => ''),
    );
    const ignored = collabOn
      ? parseIgnoredSlugs(
          await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_ignored.json')).catch(() => ''),
        )
      : new Set<string>();
    const todoSlugs = todoAll.filter((slug) => !ignored.has(slug));
    const pausedSlugs = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/PAUSED')).catch(() => []),
    );

    // Exclude paused tasks from currentTasks count so each task is counted in its true state
    for (const p of pausedSlugs) {
      uniqueCurrentTasks.delete(p);
    }

    crewRadarState.sessionIds = Array.from(allSessionIds).sort();
    crewRadarState.onlineSessions = crewRadarState.sessionIds.length;
    crewRadarState.currentTasks = uniqueCurrentTasks.size;
    crewRadarState.todoTasks = todoSlugs.length;
    crewRadarState.othersTasks = todoAll.length - todoSlugs.length;
    crewRadarState.pausedTasks = pausedSlugs.length;

    crewRuntimeState.onlineSessionsCount = crewRadarState.onlineSessions;
    crewRuntimeState.currentTasksCount = crewRadarState.currentTasks;
    crewRuntimeState.todoTasksCount = crewRadarState.todoTasks;
    crewRuntimeState.pausedTasksCount = crewRadarState.pausedTasks;

    $.ui.invalidate('ui.render');
    return next(e);
  });

  on('turn.complete', async ($, e, next) => {
    const sid = crewRuntimeState.sessionId;
    const mainRoot = crewRuntimeState.mainRoot || crewRuntimeState.projectRoot || '.';
    const projectRoot = crewRuntimeState.projectRoot || mainRoot;
    const nowMs = Date.now();
    const nowIso = new Date(nowMs).toISOString();

    const lockPath = joinPath(mainRoot, SESSIONS_LOCK_REL_PATH);
    const rawLock = await $.fs.read(lockPath).catch(() => '');
    const parsedLock = parseSessionsLock(rawLock, nowMs);

    const existing = parsedLock.sessions[sid];
    parsedLock.sessions[sid] = {
      sessionId: sid,
      startedAt: existing?.startedAt || nowIso,
      updatedAt: nowIso,
      cwd: projectRoot,
      activeTask: crewRuntimeState.activeTaskSlug,
      batch: crewRuntimeState.activeBatchKey,
      activeFiles: existing?.activeFiles ?? {},
    };

    await $.fs.write(lockPath, JSON.stringify(parsedLock, null, 2) + '\n').catch(() => undefined);

    const crewLockText = await $.fs
      .read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_lock.json'))
      .catch(() => '');
    const crewLocks = parseCrewLock(crewLockText, nowMs);

    const allSessionIds = new Set<string>([
      sid,
      ...Object.keys(parsedLock.sessions),
      ...Object.keys(crewLocks),
    ]);

    const currentSlugsMain = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/CURRENT_TASKS')).catch(() => []),
    );
    const currentSlugsLocal =
      projectRoot !== mainRoot
        ? filterCrewTaskSlugs(
            await $.fs.list(joinPath(projectRoot, 'crew/CURRENT_TASKS')).catch(() => []),
          )
        : [];
    const lockedSlugs = Object.values(crewLocks).flatMap((s) => s.tasks);
    const uniqueCurrentTasks = new Set<string>([
      ...currentSlugsMain,
      ...currentSlugsLocal,
      ...lockedSlugs,
    ]);

    const todoAll = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/TODO')).catch(() => []),
    );
    const collabOn = parseCollabOn(
      await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/CREW_CONFIG.md')).catch(() => ''),
    );
    const ignored = collabOn
      ? parseIgnoredSlugs(
          await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_ignored.json')).catch(() => ''),
        )
      : new Set<string>();
    const todoSlugs = todoAll.filter((slug) => !ignored.has(slug));
    const pausedSlugs = filterCrewTaskSlugs(
      await $.fs.list(joinPath(mainRoot, 'crew/PAUSED')).catch(() => []),
    );
    for (const p of pausedSlugs) {
      uniqueCurrentTasks.delete(p);
    }

    crewRadarState.sessionIds = Array.from(allSessionIds).sort();
    crewRadarState.onlineSessions = crewRadarState.sessionIds.length;
    crewRadarState.currentTasks = uniqueCurrentTasks.size;
    crewRadarState.todoTasks = todoSlugs.length;
    crewRadarState.othersTasks = todoAll.length - todoSlugs.length;
    crewRadarState.pausedTasks = pausedSlugs.length;

    crewRuntimeState.onlineSessionsCount = crewRadarState.onlineSessions;
    crewRuntimeState.currentTasksCount = crewRadarState.currentTasks;
    crewRuntimeState.todoTasksCount = crewRadarState.todoTasks;
    crewRuntimeState.pausedTasksCount = crewRadarState.pausedTasks;

    $.ui.invalidate('ui.render');
    return next(e);
  });

  on('session.end', async ($, e, next) => {
    const sid = resolveSessionIdFromEvent(e as Record<string, unknown>);
    const mainRoot = crewRuntimeState.mainRoot || crewRuntimeState.projectRoot || '.';
    const lockPath = joinPath(mainRoot, SESSIONS_LOCK_REL_PATH);
    const rawLock = await $.fs.read(lockPath).catch(() => '');
    const parsedLock = parseSessionsLock(rawLock, Date.now());

    if (parsedLock.sessions[sid]) {
      delete parsedLock.sessions[sid];
      await $.fs
        .write(lockPath, JSON.stringify(parsedLock, null, 2) + '\n')
        .catch(() => undefined);
    }

    crewRadarState.sessionIds = Object.keys(parsedLock.sessions).sort();
    crewRadarState.onlineSessions = crewRadarState.sessionIds.length;
    crewRuntimeState.onlineSessionsCount = crewRadarState.onlineSessions;

    return next(e);
  });

  on('ui.render', { component: 'AbovePrompt' }, async (_$, e, next) => {
    const prev = await next(e);
    if (!crewUiState.bands.radar) return prev;
    return addBandSegments(prev, {
      slot: 'left',
      order: 10,
      color: 'cyan',
      bold: true,
      text: formatCrewRadarCompact(),
    });
  });
}

export const register = registerCrewRadar;
