/**
 * Mod 9 — file-lock-monitor.ts (Anti-collision multi-sessions)
 *
 * Écoute les événements `tool.call` (`Edit`, `Write`, `MultiEdit`).
 * Si une session tente de modifier un fichier déjà verrouillé (Zone `CLAUDE_BATCH.md`
 * détenue dans `crew_lock.json` ou fichier activement modifié dans `.claude/crew-sessions.lock`
 * par un autre agent du crew), affiche une alerte visuelle immédiate dans l'UI.
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  joinPath,
  normalizeRepoRelativePath,
  parseClaudeBatch,
  parseCrewLock,
  parseSessionsLock,
  pathMatchesZone,
  type CrewLockSessionEntry,
  type ModRegistrar,
  type ParsedBatchSection,
  type SessionsLockFile,
  addBandSegments,
} from './shared.ts';
import { SESSIONS_LOCK_REL_PATH } from './crew-radar.ts';

export interface FileCollisionAlert {
  filePath: string;
  toolName: string;
  ownerSessionId: string;
  ownerBatch: string | null;
  source: 'batch-zone' | 'active-file';
  detectedAtMs: number;
  message: string;
}

export const fileLockMonitorState: {
  alerts: FileCollisionAlert[];
} = {
  alerts: [],
};

const ALERT_VISIBLE_TTL_MS = 3 * 60 * 1000; // Keep visual banner highlighted for 3 minutes
const FILE_WRITE_TOOLS = new Set(['edit', 'write', 'multiedit']);

export function extractTargetPathsFromToolEvent(event: Record<string, unknown>): string[] {
  const input =
    (event.input as Record<string, unknown> | undefined) ||
    (event.tool_input as Record<string, unknown> | undefined) ||
    (event.args as Record<string, unknown> | undefined) ||
    event;

  const candidates: string[] = [];
  const primary = input.file_path ?? input.filePath ?? input.path ?? event.file_path ?? event.path;
  if (typeof primary === 'string' && primary.trim()) {
    candidates.push(primary.trim());
  }

  if (Array.isArray(input.files)) {
    for (const f of input.files) {
      if (typeof f === 'string' && f.trim()) candidates.push(f.trim());
      else if (f && typeof (f as Record<string, unknown>).file_path === 'string') {
        candidates.push(String((f as Record<string, unknown>).file_path).trim());
      }
    }
  }
  return Array.from(new Set(candidates));
}

export function detectFileCollision(params: {
  repoRelPath: string;
  toolName: string;
  currentSessionId: string;
  sections: ParsedBatchSection[];
  crewLocks: Record<string, CrewLockSessionEntry>;
  sessionsLock: SessionsLockFile;
  nowMs?: number;
}): FileCollisionAlert | null {
  const {
    repoRelPath,
    toolName,
    currentSessionId,
    sections,
    crewLocks,
    sessionsLock,
    nowMs = Date.now(),
  } = params;
  if (!repoRelPath) return null;

  // 1. Check live file modification lock in `.claude/crew-sessions.lock`
  for (const [otherSid, info] of Object.entries(sessionsLock.sessions)) {
    if (otherSid === currentSessionId) continue;
    const touchedAt = info.activeFiles?.[repoRelPath];
    if (typeof touchedAt === 'number') {
      const msg = `🚨 COLLISION FICHIER : \`${repoRelPath}\` (${toolName}) est en cours de modification par la session @${otherSid.slice(0, 8)}${info.batch ? ` (${info.batch})` : ''} !`;
      return {
        filePath: repoRelPath,
        toolName,
        ownerSessionId: otherSid,
        ownerBatch: info.batch ?? null,
        source: 'active-file',
        detectedAtMs: nowMs,
        message: msg,
      };
    }
  }

  // 2. Check batch Zone lock in `crew_lock.json` + `CLAUDE_BATCH.md`
  const slugOwners = new Map<string, string>();
  for (const [sid, entry] of Object.entries(crewLocks)) {
    for (const slug of entry.tasks) {
      slugOwners.set(slug, sid);
    }
  }

  for (const sec of sections) {
    const foreignHolders = new Set<string>();
    for (const t of sec.tasks) {
      const holder = slugOwners.get(t.slug);
      if (holder && holder !== currentSessionId) foreignHolders.add(holder);
    }
    for (const [sid, entry] of Object.entries(crewLocks)) {
      if (sid !== currentSessionId && entry.batch === sec.key) {
        foreignHolders.add(sid);
      }
    }

    if (foreignHolders.size === 0) continue;

    for (const zp of sec.zonePaths) {
      if (pathMatchesZone(repoRelPath, zp)) {
        const ownerSid = Array.from(foreignHolders)[0];
        const msg = `🚨 COLLISION ZONE : \`${repoRelPath}\` (${toolName}) tombe sous la Zone \`${zp}\` verrouillée par @${ownerSid.slice(0, 8)} (${sec.key}) !`;
        return {
          filePath: repoRelPath,
          toolName,
          ownerSessionId: ownerSid,
          ownerBatch: sec.key,
          source: 'batch-zone',
          detectedAtMs: nowMs,
          message: msg,
        };
      }
    }
  }

  return null;
}

export function getActiveCollisionAlerts(nowMs = Date.now()): FileCollisionAlert[] {
  fileLockMonitorState.alerts = fileLockMonitorState.alerts.filter(
    (a) => nowMs - a.detectedAtMs <= ALERT_VISIBLE_TTL_MS,
  );
  return fileLockMonitorState.alerts;
}

export function registerFileLockMonitor(on: ModRegistrar): void {
  on('tool.call', async ($, e, next) => {
    try {
      const ev = (e || {}) as Record<string, unknown>;
      const rawTool = String(ev.tool ?? ev.name ?? '').trim();
      if (!FILE_WRITE_TOOLS.has(rawTool.toLowerCase())) {
        return next(e);
      }

      const targetPaths = extractTargetPathsFromToolEvent(ev);
      if (targetPaths.length === 0) {
        return next(e);
      }

      const projectRoot = crewRuntimeState.projectRoot || '.';
      const mainRoot = crewRuntimeState.mainRoot || projectRoot;
      const sid = crewRuntimeState.sessionId;
      const nowMs = Date.now();

      const crewLockText = await $.fs
        .read(joinPath(mainRoot, 'crew/CLAUDE_CONTEXT/crew_lock.json'))
        .catch(() => '');
      const crewLocks = parseCrewLock(crewLockText, nowMs);
      const knownWorktrees = Object.values(crewLocks)
        .map((l) => l.worktree)
        .filter((w): w is string => Boolean(w));

      const batchMd =
        (await $.fs.read(joinPath(projectRoot, 'crew/CLAUDE_BATCH.md')).catch(() => '')) ||
        (await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_BATCH.md')).catch(() => ''));
      const parsedBatch = parseClaudeBatch(batchMd);

      const sessionsLockPath = joinPath(mainRoot, SESSIONS_LOCK_REL_PATH);
      const rawSessionsLock = await $.fs.read(sessionsLockPath).catch(() => '');
      const sessionsLock = parseSessionsLock(rawSessionsLock, nowMs);

      let hadCollision = false;
      const uncontestedRelPaths: string[] = [];

      for (const rawTarget of targetPaths) {
        const relPath = normalizeRepoRelativePath(
          rawTarget,
          projectRoot === mainRoot ? [mainRoot] : [projectRoot, mainRoot],
          knownWorktrees,
        );

        const collision = detectFileCollision({
          repoRelPath: relPath,
          toolName: rawTool,
          currentSessionId: sid,
          sections: parsedBatch.sections,
          crewLocks,
          sessionsLock,
          nowMs,
        });

        if (collision) {
          hadCollision = true;
          fileLockMonitorState.alerts.push(collision);
          if (fileLockMonitorState.alerts.length > 8) {
            fileLockMonitorState.alerts.splice(0, fileLockMonitorState.alerts.length - 8);
          }
          $.ui.toast(collision.message);
        } else if (relPath) {
          uncontestedRelPaths.push(relPath);
        }
      }

      // Register our own active file locks so concurrent sessions detect collisions immediately
      if (uncontestedRelPaths.length > 0) {
        const nowIso = new Date(nowMs).toISOString();
        const myEntry = sessionsLock.sessions[sid] || {
          sessionId: sid,
          startedAt: nowIso,
          updatedAt: nowIso,
          cwd: projectRoot,
          activeTask: crewRuntimeState.activeTaskSlug,
          batch: crewRuntimeState.activeBatchKey,
          activeFiles: {},
        };
        myEntry.updatedAt = nowIso;
        myEntry.activeFiles = myEntry.activeFiles || {};
        for (const rp of uncontestedRelPaths) {
          myEntry.activeFiles[rp] = nowMs;
        }
        sessionsLock.sessions[sid] = myEntry;
        await $.fs
          .write(sessionsLockPath, JSON.stringify(sessionsLock, null, 2) + '\n')
          .catch(() => undefined);
      }

      if (hadCollision) {
        $.ui.invalidate('ui.render');
      }
    } catch {
      // Never crash tool pipeline on lock read error
    }

    return next(e);
  });

  on('ui.render', { component: 'AbovePrompt' }, async (_$, e, next) => {
    const prev = await next(e);
    if (!crewUiState.bands.locks) return prev;

    const activeAlerts = getActiveCollisionAlerts(Date.now());
    if (activeAlerts.length === 0) return prev;

    return addBandSegments(
      prev,
      ...activeAlerts.slice(-3).map((alert) => ({
        slot: 'alert' as const,
        color: 'red',
        bold: true,
        text: alert.message,
      })),
    );
  });
}

export const register = registerFileLockMonitor;
