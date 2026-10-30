/**
 * Shared pure types, parsers, formatters, and local UI state for crew-mates Zero-Token Mods.
 *
 * Strict constraints:
 * - Zero LLM / token usage (no model calls, no prompt injection, no LLM tool registration).
 * - Zero external dependencies and zero `node:*` built-in imports (100% sandbox-safe).
 * - `$` is NEVER passed into helper functions here (Claude Code's static validator requires
 *   `$` to be invoked directly as `$.noun.verb(...)` inside `on("<event>", ...)` callbacks).
 */

export interface UiNodeProps {
  flexDirection?: 'row' | 'column';
  gap?: number;
  padding?: number;
  paddingX?: number;
  paddingY?: number;
  marginTop?: number;
  marginBottom?: number;
  borderStyle?: 'single' | 'round' | 'double' | 'bold';
  borderColor?: string;
  justifyContent?: 'flex-start' | 'center' | 'space-between' | 'flex-end';
  alignItems?: 'flex-start' | 'center' | 'stretch' | 'flex-end';
  bold?: boolean;
  dimColor?: boolean;
  italic?: boolean;
  underline?: boolean;
  color?: string;
  backgroundColor?: string;
  children?: unknown[];
  [key: string]: unknown;
}

export type UiComponent = (props: UiNodeProps) => unknown;

export interface ResolvedUi {
  Box: UiComponent;
  Text: UiComponent;
  Button?: UiComponent;
  [key: string]: UiComponent | undefined;
}

export interface FsStatResult {
  size?: number;
  mtimeMs?: number;
  isDirectory?: boolean | (() => boolean);
  isFile?: boolean | (() => boolean);
  type?: string;
}

export interface FsDirEntry {
  name: string;
  type?: string;
  isDirectory?: boolean | (() => boolean);
}

export interface ModApi {
  ui: {
    resolve: (event: unknown) => ResolvedUi;
    invalidate: (target: 'ui.render') => void;
    open: (options: {
      id: string;
      title: string;
      focus?: boolean;
      immediate?: boolean;
      closeOnEscape?: boolean;
      holdToasts?: boolean;
    }) => Promise<void>;
    close: (options: { id: string }) => Promise<void>;
    toast: (message: string) => void;
  };
  command: {
    register: (options: {
      name: string;
      description: string;
      argumentHint?: string;
    }) => Promise<void>;
  };
  fs: {
    read: (path: string) => Promise<string>;
    write: (path: string, content: string) => Promise<void>;
    list: (path: string) => Promise<Array<string | FsDirEntry>>;
    stat: (path: string) => Promise<FsStatResult | null>;
  };
  env: {
    get: (name: string) => string | undefined;
  };
}

export type HookHandler<TEvent = Record<string, unknown>, TResult = unknown> = (
  $: ModApi,
  event: TEvent,
  next: (event: TEvent) => Promise<TResult>,
) => Promise<TResult> | TResult;

export interface ModRegistrar {
  (event: string, handler: HookHandler<any, any>): void;
  (event: string, matcher: Record<string, unknown>, handler: HookHandler<any, any>): void;
}

export type CrewPaneId = 'crew-turns' | 'crew-stack' | 'crew-board' | 'crew-agents' | 'crew-cache';
export type CrewBandId = 'weather' | 'radar' | 'progress' | 'agents' | 'locks';

export const PANE_META: Record<CrewPaneId, { id: CrewPaneId; title: string; command: string }> = {
  'crew-turns': {
    id: 'crew-turns',
    title: '🔍 Crew Turn Inspector',
    command: '/crew-turns',
  },
  'crew-stack': {
    id: 'crew-stack',
    title: '📚 Crew Stack Viewer',
    command: '/crew-stack',
  },
  'crew-board': {
    id: 'crew-board',
    title: '📋 Crew Kanban & Dépendances',
    command: '/crew-board',
  },
  'crew-agents': {
    id: 'crew-agents',
    title: '🎭 Crew Agent Flow',
    command: '/crew-agents',
  },
  'crew-cache': {
    id: 'crew-cache',
    title: '🔥 Prompt Cache',
    command: '/crew-ui cache',
  },
};

export interface CrewUiVisibilityState {
  bands: Record<CrewBandId, boolean>;
  panes: Record<CrewPaneId, boolean>;
}

export interface CrewSharedRuntimeState {
  sessionId: string;
  projectRoot: string;
  mainRoot: string;
  sessionStartedAtMs: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCacheReadTokens: number;
  totalCacheCreationTokens: number;
  lastContextTokens: number;
  lastContextWindow: number;
  turnCount: number;
  activeTaskSlug: string | null;
  activeTaskDone: number;
  activeTaskTotal: number;
  activeBatchKey: string | null;
  activeBatchHeader: string | null;
  activeBatchDoneTasks: number;
  activeBatchTotalTasks: number;
  onlineSessionsCount: number;
  currentTasksCount: number;
  todoTasksCount: number;
  pausedTasksCount: number;
  etaSummaryLine: string | null;
}

const DEFAULT_SESSION_ID = `sess-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export const crewUiState: CrewUiVisibilityState = {
  bands: {
    weather: true,
    radar: true,
    progress: true,
    agents: true,
    locks: true,
  },
  panes: {
    'crew-turns': false,
    'crew-stack': false,
    'crew-board': false,
    'crew-agents': false,
    'crew-cache': false,
  },
};

export const crewRuntimeState: CrewSharedRuntimeState = {
  sessionId: DEFAULT_SESSION_ID,
  projectRoot: '.',
  mainRoot: '.',
  sessionStartedAtMs: Date.now(),
  totalInputTokens: 0,
  totalOutputTokens: 0,
  totalCacheReadTokens: 0,
  totalCacheCreationTokens: 0,
  lastContextTokens: 0,
  lastContextWindow: 200_000,
  turnCount: 0,
  activeTaskSlug: null,
  activeTaskDone: 0,
  activeTaskTotal: 0,
  activeBatchKey: null,
  activeBatchHeader: null,
  activeBatchDoneTasks: 0,
  activeBatchTotalTasks: 0,
  onlineSessionsCount: 1,
  currentTasksCount: 0,
  todoTasksCount: 0,
  pausedTasksCount: 0,
  etaSummaryLine: null,
};

export function resolveSessionIdFromEvent(event: Record<string, unknown> | null | undefined): string {
  if (!event) return crewRuntimeState.sessionId;
  const candidate =
    (typeof event.sessionId === 'string' && event.sessionId) ||
    (typeof event.session_id === 'string' && event.session_id) ||
    (typeof (event.session as Record<string, unknown> | undefined)?.id === 'string' &&
      ((event.session as Record<string, unknown>).id as string));
  if (candidate && candidate.trim().length > 0) {
    crewRuntimeState.sessionId = candidate.trim();
  }
  return crewRuntimeState.sessionId;
}

export function resolvePaneRequestId(event: Record<string, unknown> | null | undefined): string {
  if (!event) return '';
  if (typeof event.requestId === 'string') return event.requestId;
  if (typeof event.id === 'string') return event.id;
  const props = event.props as Record<string, unknown> | undefined;
  if (props && typeof props.id === 'string') return props.id;
  return '';
}

/* -------------------------------------------------------------------------- */
/* Pure Cross-Platform Path Utilities (Zero node:path import)                 */
/* -------------------------------------------------------------------------- */

export function normalizeSlashes(rawPath: string): string {
  return rawPath.replace(/\\/g, '/').replace(/\/+/g, '/');
}

export function isAbsolutePath(rawPath: string): boolean {
  const norm = normalizeSlashes(rawPath);
  return norm.startsWith('/') || /^[A-Za-z]:\//.test(norm);
}

export function joinPath(...parts: Array<string | undefined | null>): string {
  const filtered = parts.filter((p): p is string => Boolean(p && p.trim().length > 0));
  if (filtered.length === 0) return '.';
  const rawJoined = filtered
    .map((segment, idx) => {
      const s = normalizeSlashes(segment.trim());
      if (idx === 0) return s === '.' ? '' : s.replace(/\/+$/, '');
      return s.replace(/^\/+/, '').replace(/\/+$/, '');
    })
    .filter((s) => s.length > 0)
    .join('/');
  if (!rawJoined) return '.';

  // Collapse `.` and `..` segments cleanly while preserving leading `/` or `C:`
  const prefixMatch = rawJoined.match(/^([A-Za-z]:\/|\/)/);
  const prefix = prefixMatch ? prefixMatch[1] : '';
  const rest = prefix ? rawJoined.slice(prefix.length) : rawJoined;
  const stack: string[] = [];
  for (const seg of rest.split('/')) {
    if (!seg || seg === '.') continue;
    if (seg === '..') {
      if (stack.length > 0 && stack[stack.length - 1] !== '..') {
        stack.pop();
      } else if (!prefix) {
        stack.push('..');
      }
    } else {
      stack.push(seg);
    }
  }
  if (prefix) return prefix + stack.join('/');
  return stack.length > 0 ? stack.join('/') : '.';
}

export function dirnamePath(rawPath: string): string {
  const norm = normalizeSlashes(rawPath).replace(/\/+$/, '');
  const idx = norm.lastIndexOf('/');
  if (idx < 0) return '.';
  if (idx === 0) return '/';
  if (idx === 2 && /^[A-Za-z]:$/.test(norm.slice(0, 2))) return norm.slice(0, 3);
  return norm.slice(0, idx);
}

export function parseGitdirPointer(gitFileContent: string): string | null {
  for (const rawLine of gitFileContent.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (line.startsWith('gitdir:')) {
      const target = line.slice('gitdir:'.length).trim();
      return target ? normalizeSlashes(target) : null;
    }
  }
  return null;
}

export function resolveWorktreeMainRoot(
  projectRoot: string,
  gitdirPath: string,
  commondirContent: string,
): string {
  const absGitdir = isAbsolutePath(gitdirPath)
    ? joinPath(gitdirPath)
    : joinPath(projectRoot, gitdirPath);
  const commonDir = joinPath(absGitdir, commondirContent.trim());
  const normalizedCommon = normalizeSlashes(commonDir).replace(/\/+$/, '');
  if (normalizedCommon.endsWith('/.git') || normalizedCommon === '.git') {
    return dirnamePath(normalizedCommon);
  }
  return projectRoot;
}

export function normalizeRepoRelativePath(
  filePath: string,
  roots: string[],
  worktrees: string[] = [],
): string {
  const norm = normalizeSlashes(filePath.trim());
  if (!isAbsolutePath(norm)) {
    return norm.replace(/^\.\//, '');
  }
  const lowerNorm = norm.toLowerCase();
  const candidates = [...roots];
  const mainBase = roots[roots.length - 1] || roots[0];
  if (mainBase) {
    for (const wt of worktrees) {
      if (wt) candidates.push(joinPath(mainBase, wt));
    }
  }
  for (const base of candidates) {
    if (!base || base === '.') continue;
    const normBase = normalizeSlashes(base).replace(/\/+$/, '');
    if (!normBase) continue;
    const lowerBase = normBase.toLowerCase();
    if (lowerNorm === lowerBase) return '';
    if (lowerNorm.startsWith(lowerBase + '/')) {
      return norm.slice(normBase.length + 1);
    }
  }
  return norm.replace(/^\.\//, '');
}

/* -------------------------------------------------------------------------- */
/* Directory Entry & Markdown / Batch / Lock Parsers                          */
/* -------------------------------------------------------------------------- */

export function extractEntryNames(entries: Array<string | FsDirEntry> | null | undefined): string[] {
  if (!Array.isArray(entries)) return [];
  const names: string[] = [];
  for (const item of entries) {
    if (typeof item === 'string') {
      const base = normalizeSlashes(item).split('/').pop() || '';
      if (base) names.push(base);
    } else if (item && typeof item.name === 'string') {
      names.push(item.name);
    }
  }
  return names.sort();
}

export function filterCrewTaskSlugs(entries: Array<string | FsDirEntry> | null | undefined): string[] {
  return extractEntryNames(entries).filter(
    (name) =>
      name.endsWith('.md') &&
      name !== 'INDEX.md' &&
      name !== 'README.md' &&
      !name.startsWith('_'),
  );
}

export interface ParsedTaskInfo {
  slug: string;
  title: string;
  done: number;
  started: number;
  todo: number;
  total: number;
  percent: number;
  explicitDeps: string[];
}

const CHECKBOX_LINE_RE = /^[ \t]*[-*]\s*\[([ xXsS])\]/gm;
const EXPLICIT_DEP_LINE_RE =
  /(?:d[ée]pend(?:s)?(?:\s+de|\s+on)?|bloqu[ée]e?(?:\s+par)?|blocked\s+by|apr[èe]s|requires)\s*:?\s*([^\n]+)/gi;
const SLUG_BACKTICK_RE = /`(?:[\w\-./]*\/)?([\w\-.]+\.md)`/g;

export function parseTaskMarkdown(slug: string, content: string): ParsedTaskInfo {
  let title = slug.replace(/\.md$/i, '');
  for (const line of content.split(/\r?\n/)) {
    if (line.startsWith('# ')) {
      title = line.slice(2).trim() || title;
      break;
    }
  }

  let done = 0;
  let started = 0;
  let todo = 0;
  CHECKBOX_LINE_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CHECKBOX_LINE_RE.exec(content)) !== null) {
    const mark = match[1];
    if (mark === 'x' || mark === 'X') done += 1;
    else if (mark === 's' || mark === 'S') started += 1;
    else todo += 1;
  }

  const total = done + started + todo;
  const percent = total > 0 ? Math.floor((done / total) * 100) : 0;

  const depsSet = new Set<string>();
  EXPLICIT_DEP_LINE_RE.lastIndex = 0;
  let depMatch: RegExpExecArray | null;
  while ((depMatch = EXPLICIT_DEP_LINE_RE.exec(content)) !== null) {
    const rhs = depMatch[1] || '';
    SLUG_BACKTICK_RE.lastIndex = 0;
    let slugMatch: RegExpExecArray | null;
    while ((slugMatch = SLUG_BACKTICK_RE.exec(rhs)) !== null) {
      const refSlug = slugMatch[1];
      if (refSlug && refSlug !== slug && !refSlug.includes('<')) {
        depsSet.add(refSlug);
      }
    }
  }

  return {
    slug,
    title,
    done,
    started,
    todo,
    total,
    percent,
    explicitDeps: Array.from(depsSet),
  };
}

export interface BatchTaskRef {
  slug: string;
  closed: boolean;
}

export interface ParsedBatchSection {
  header: string;
  key: string;
  slugId: string;
  zonePaths: string[];
  tasks: BatchTaskRef[];
}

export interface ParsedBatchFile {
  sections: ParsedBatchSection[];
  unclassified: string[];
}

export function batchKeyFromHeader(header: string): string {
  return (header || '').split(' · ', 1)[0].trim();
}

export function batchSlugFromHeader(header: string): string {
  const stripped = batchKeyFromHeader(header).replace(/^Batch\b\s*[:\-—]?\s*/i, '').trim();
  const slug = stripped.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();
  return slug || 'batch';
}

const BATCH_HEADER_RE = /^#{2,3}\s*Batch\b.*$/gm;
const UNCLASSIFIED_HEADER_RE = /^#{2,3}\s*[AÀ] classer\b.*$/im;
const BATCH_TASK_LINE_RE =
  /^[ \t]*(?:\d+\.|[-*])\s*(~~\s*)?`(?:[\w\-./]*\/)?([\w\-.]+\.md)`(\s*~~)?/gm;

export function parseClaudeBatch(markdown: string): ParsedBatchFile {
  if (!markdown || !markdown.trim()) {
    return { sections: [], unclassified: [] };
  }

  BATCH_HEADER_RE.lastIndex = 0;
  const headers: Array<{ text: string; start: number; end: number }> = [];
  let hm: RegExpExecArray | null;
  while ((hm = BATCH_HEADER_RE.exec(markdown)) !== null) {
    headers.push({
      text: hm[0].replace(/^#+\s*/, '').trim(),
      start: hm.index,
      end: hm.index + hm[0].length,
    });
  }

  const unclassifiedMatch = UNCLASSIFIED_HEADER_RE.exec(markdown);
  const unclassifiedStart = unclassifiedMatch ? unclassifiedMatch.index : -1;

  const sections: ParsedBatchSection[] = [];
  for (let i = 0; i < headers.length; i += 1) {
    const current = headers[i];
    const bodyStart = current.end;
    let bodyEnd = i + 1 < headers.length ? headers[i + 1].start : markdown.length;
    if (unclassifiedStart >= 0 && bodyStart < unclassifiedStart && unclassifiedStart < bodyEnd) {
      bodyEnd = unclassifiedStart;
    }
    const body = markdown.slice(bodyStart, bodyEnd);

    const zoneLineMatch = body.match(/^\*{0,2}Zone\b[^:\n]*:\*{0,2}\s*(.+)$/m);
    const zonePaths: string[] = [];
    if (zoneLineMatch && zoneLineMatch[1]) {
      const zoneBacktickRe = /`([^`]+)`/g;
      let zm: RegExpExecArray | null;
      while ((zm = zoneBacktickRe.exec(zoneLineMatch[1])) !== null) {
        const zp = zm[1].trim();
        if (zp && !zp.includes('<')) zonePaths.push(zp);
      }
    }

    const seen = new Map<string, boolean>();
    BATCH_TASK_LINE_RE.lastIndex = 0;
    let tm: RegExpExecArray | null;
    while ((tm = BATCH_TASK_LINE_RE.exec(body)) !== null) {
      const taskSlug = tm[2];
      if (!taskSlug || taskSlug.includes('<')) continue;
      const isClosed = Boolean(tm[1] && tm[3]);
      seen.set(taskSlug, Boolean(seen.get(taskSlug)) || isClosed);
    }

    const tasks: BatchTaskRef[] = [];
    for (const [slug, closed] of seen.entries()) {
      tasks.push({ slug, closed });
    }

    sections.push({
      header: current.text,
      key: batchKeyFromHeader(current.text),
      slugId: batchSlugFromHeader(current.text),
      zonePaths,
      tasks,
    });
  }

  const unclassified: string[] = [];
  if (unclassifiedStart >= 0 && unclassifiedMatch) {
    const uStart = unclassifiedStart + unclassifiedMatch[0].length;
    const nextBatch = headers.find((h) => h.start > unclassifiedStart);
    const uEnd = nextBatch ? nextBatch.start : markdown.length;
    const uBody = markdown.slice(uStart, uEnd);
    BATCH_TASK_LINE_RE.lastIndex = 0;
    let um: RegExpExecArray | null;
    while ((um = BATCH_TASK_LINE_RE.exec(uBody)) !== null) {
      const taskSlug = um[2];
      const isClosed = Boolean(um[1] && um[3]);
      if (taskSlug && !taskSlug.includes('<') && !isClosed && !unclassified.includes(taskSlug)) {
        unclassified.push(taskSlug);
      }
    }
  }

  return { sections, unclassified };
}

/* -------------------------------------------------------------------------- */
/* Lock Schemas & Zone Collision Matchers                                     */
/* -------------------------------------------------------------------------- */

export const CREW_LOCK_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours (matches crew_hook.py)
export const SESSIONS_LOCK_TTL_MS = 30 * 60 * 1000; // heartbeat a chaque tour : une session muette 30 min est consideree morte
export const ACTIVE_FILE_TOUCH_TTL_MS = 15 * 60 * 1000; // 15 minutes for live file edit locks

export interface CrewLockSessionEntry {
  sessionId: string;
  batch: string | null;
  tasks: string[];
  worktree: string | null;
  branch: string | null;
  since: string;
}

export function parseCrewLock(jsonText: string, nowMs = Date.now()): Record<string, CrewLockSessionEntry> {
  if (!jsonText || !jsonText.trim()) return {};
  try {
    const parsed = JSON.parse(jsonText) as { sessions?: Record<string, Record<string, unknown>> };
    const sessions = parsed?.sessions;
    if (!sessions || typeof sessions !== 'object') return {};
    const out: Record<string, CrewLockSessionEntry> = {};
    for (const [sid, raw] of Object.entries(sessions)) {
      if (!raw || typeof raw !== 'object') continue;
      const since = typeof raw.since === 'string' ? raw.since : '';
      const sinceMs = since ? Date.parse(since) : NaN;
      if (!Number.isFinite(sinceMs) || nowMs - sinceMs > CREW_LOCK_TTL_MS) {
        continue;
      }
      const tasks = Array.isArray(raw.tasks)
        ? raw.tasks.filter((t): t is string => typeof t === 'string')
        : [];
      out[sid] = {
        sessionId: sid,
        batch: typeof raw.batch === 'string' ? raw.batch : null,
        tasks,
        worktree: typeof raw.worktree === 'string' ? raw.worktree : null,
        branch: typeof raw.branch === 'string' ? raw.branch : null,
        since,
      };
    }
    return out;
  } catch {
    return {};
  }
}

export interface LiveSessionEntry {
  sessionId: string;
  startedAt: string;
  updatedAt: string;
  cwd?: string;
  activeTask?: string | null;
  batch?: string | null;
  activeFiles?: Record<string, number>;
}

export interface SessionsLockFile {
  sessions: Record<string, LiveSessionEntry>;
}

export function parseSessionsLock(jsonText: string, nowMs = Date.now()): SessionsLockFile {
  if (!jsonText || !jsonText.trim()) return { sessions: {} };
  try {
    const parsed = JSON.parse(jsonText) as Partial<SessionsLockFile>;
    const rawSessions = parsed?.sessions;
    if (!rawSessions || typeof rawSessions !== 'object') return { sessions: {} };
    const clean: Record<string, LiveSessionEntry> = {};
    for (const [sid, entry] of Object.entries(rawSessions)) {
      if (!entry || typeof entry !== 'object') continue;
      const tsStr = entry.updatedAt || entry.startedAt || '';
      const ts = tsStr ? Date.parse(tsStr) : NaN;
      if (!Number.isFinite(ts) || nowMs - ts > SESSIONS_LOCK_TTL_MS) continue;

      const activeFiles: Record<string, number> = {};
      if (entry.activeFiles && typeof entry.activeFiles === 'object') {
        for (const [fp, touchedMs] of Object.entries(entry.activeFiles)) {
          if (typeof touchedMs === 'number' && nowMs - touchedMs <= ACTIVE_FILE_TOUCH_TTL_MS) {
            activeFiles[fp] = touchedMs;
          }
        }
      }

      clean[sid] = {
        sessionId: sid,
        startedAt: entry.startedAt || new Date(nowMs).toISOString(),
        updatedAt: entry.updatedAt || new Date(nowMs).toISOString(),
        cwd: entry.cwd,
        activeTask: entry.activeTask ?? null,
        batch: entry.batch ?? null,
        activeFiles,
      };
    }
    return { sessions: clean };
  } catch {
    return { sessions: {} };
  }
}

// Borne l'explosion combinatoire de `{a,b}{c,d}…` (2^N) dans une ligne `Zone :`.
const MAX_BRACE_EXPANSIONS = 64;

export function expandBraceGlob(pattern: string): string[] {
  const norm = normalizeSlashes(pattern.trim()).replace(/\/+\*\*$/, '').replace(/\/+$/, '');
  const braceMatch = norm.match(/\{([^{}]+)\}/);
  if (!braceMatch || braceMatch.index === undefined) {
    return norm ? [norm] : [];
  }
  const prefix = norm.slice(0, braceMatch.index);
  const suffix = norm.slice(braceMatch.index + braceMatch[0].length);
  const results: string[] = [];
  for (const choice of braceMatch[1].split(',')) {
    for (const sub of expandBraceGlob(`${prefix}${choice.trim()}${suffix}`)) {
      results.push(sub);
      if (results.length >= MAX_BRACE_EXPANSIONS) return results;
    }
  }
  return results;
}

function globToRegExp(glob: string): RegExp {
  let regexStr = '^';
  for (let i = 0; i < glob.length; i += 1) {
    const ch = glob[i];
    if (ch === '*') {
      if (glob[i + 1] === '*') {
        regexStr += '.*';
        i += 1;
      } else {
        regexStr += '[^/]*';
      }
    } else if (ch === '?') {
      regexStr += '[^/]';
    } else if ('\\^$.|+()[]{}'.includes(ch)) {
      regexStr += `\\${ch}`;
    } else {
      regexStr += ch;
    }
  }
  regexStr += '$';
  return new RegExp(regexStr);
}

export function pathMatchesZone(repoRelPath: string, rawZonePattern: string): boolean {
  const normPath = normalizeSlashes(repoRelPath).replace(/^\.\//, '').replace(/\/+$/, '');
  if (!normPath) return false;
  for (const zdir of expandBraceGlob(rawZonePattern)) {
    if (!zdir) continue;
    if (/[*?[]/.test(zdir)) {
      const directRe = globToRegExp(zdir);
      const childRe = globToRegExp(`${zdir}/**`);
      if (directRe.test(normPath) || childRe.test(normPath)) return true;
    } else if (normPath === zdir || normPath.startsWith(`${zdir}/`)) {
      return true;
    }
  }
  return false;
}

export function zonesOverlap(zonesA: string[], zonesB: string[]): boolean {
  const expA = zonesA.flatMap((z) => expandBraceGlob(z));
  const expB = zonesB.flatMap((z) => expandBraceGlob(z));
  for (const a of expA) {
    for (const b of expB) {
      if (a === b) return true;
      if (pathMatchesZone(a, b) || pathMatchesZone(b, a)) return true;
    }
  }
  return false;
}

/* -------------------------------------------------------------------------- */
/* Usage Extraction & Formatting Helpers                                      */
/* -------------------------------------------------------------------------- */

export interface NormalizedTurnUsage {
  inputTokens: number;
  outputTokens: number;
  cacheReadInputTokens: number;
  cacheCreationInputTokens: number;
  contextTokens: number;
  contextWindow: number;
  ttlSeconds: number;
  model: string;
}

export function extractTurnUsage(
  event: Record<string, unknown> | null | undefined,
  envTtlOverride?: string,
): NormalizedTurnUsage {
  const e = event || {};
  const usageObj =
    (e.usage as Record<string, unknown> | undefined) ||
    ((e.response as Record<string, unknown> | undefined)?.usage as Record<string, unknown> | undefined) ||
    ((e.message as Record<string, unknown> | undefined)?.usage as Record<string, unknown> | undefined) ||
    ((e.metrics as Record<string, unknown> | undefined)?.usage as Record<string, unknown> | undefined) ||
    e;

  const num = (val: unknown): number => (typeof val === 'number' && Number.isFinite(val) ? Math.max(0, val) : 0);

  const inputTokens = num(usageObj.input_tokens ?? usageObj.inputTokens);
  const outputTokens = num(usageObj.output_tokens ?? usageObj.outputTokens);
  const cacheReadInputTokens = num(
    usageObj.cache_read_input_tokens ?? usageObj.cacheReadInputTokens ?? usageObj.cache_read_tokens,
  );
  const cacheCreationInputTokens = num(
    usageObj.cache_creation_input_tokens ??
      usageObj.cacheCreationInputTokens ??
      usageObj.cache_write_tokens,
  );

  const contextTokens =
    num(e.contextTokens ?? e.context_tokens ?? usageObj.context_tokens) ||
    inputTokens + cacheReadInputTokens + cacheCreationInputTokens;

  const model = String(
    e.model ??
      (e.message as Record<string, unknown> | undefined)?.model ??
      (e.response as Record<string, unknown> | undefined)?.model ??
      '',
  );

  const explicitWindow = num(e.contextWindow ?? e.context_window ?? usageObj.context_window);
  const is1M = model.toLowerCase().includes('1m') || contextTokens > 210_000;
  const contextWindow = explicitWindow > 0 ? explicitWindow : is1M ? 1_000_000 : 200_000;

  const cacheCreationDetail = usageObj.cache_creation as Record<string, unknown> | undefined;
  const ephemeral1h = num(cacheCreationDetail?.ephemeral_1h_input_tokens);
  const rawTtl = String(
    envTtlOverride ?? e.cacheTtl ?? e.cache_ttl ?? usageObj.cache_ttl ?? '',
  ).toLowerCase();
  const is1hTtl = ephemeral1h > 0 || rawTtl === '1h' || rawTtl === '3600' || rawTtl === '60m';
  const ttlSeconds = is1hTtl ? 3600 : 300;

  return {
    inputTokens,
    outputTokens,
    cacheReadInputTokens,
    cacheCreationInputTokens,
    contextTokens,
    contextWindow,
    ttlSeconds,
    model,
  };
}

export function renderBar(ratio: number, width = 6, filledChar = '█', emptyChar = '░'): string {
  const clamped = Number.isFinite(ratio) ? Math.max(0, Math.min(1, ratio)) : 0;
  const filled = Math.round(clamped * width);
  return `[${filledChar.repeat(filled)}${emptyChar.repeat(Math.max(0, width - filled))}]`;
}

export function renderDiscreteBar(done: number, total: number, width = 6): string {
  if (total <= 0) return `[${'░'.repeat(width)}]`;
  if (total === width) {
    const clampedDone = Math.max(0, Math.min(width, done));
    return `[${'█'.repeat(clampedDone)}${'░'.repeat(width - clampedDone)}]`;
  }
  return renderBar(done / total, width);
}

export function formatCompactTokens(tokens: number): string {
  const n = Math.max(0, Math.round(tokens));
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `${m >= 10 ? Math.round(m) : Number(m.toFixed(1))}M`;
  }
  if (n >= 1_000) {
    const k = n / 1_000;
    return `${k >= 100 || Number.isInteger(k) ? Math.round(k) : Number(k.toFixed(1))}k`;
  }
  return String(n);
}

export function formatDurationCompact(durationMs: number): string {
  const sec = Math.max(0, Math.round(durationMs / 1000));
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const remSec = sec % 60;
  if (min < 60) return remSec > 0 ? `${min}m ${remSec}s` : `${min}m`;
  const hr = Math.floor(min / 60);
  const remMin = min % 60;
  return `${hr}h ${remMin}m`;
}

export function formatEtaMinutes(durationMs: number): string {
  const totalSec = Math.max(0, Math.round(durationMs / 1000));
  if (totalSec < 60) return `< 1 min`;
  const mins = Math.max(1, Math.round(totalSec / 60));
  if (mins < 60) return `~${mins} min`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem > 0 ? `~${hrs}h${String(rem).padStart(2, '0')}` : `~${hrs}h`;
}

export function formatCountdownClock(remainingSeconds: number): string {
  const clamped = Math.max(0, Math.floor(remainingSeconds));
  const hrs = Math.floor(clamped / 3600);
  const mins = Math.floor((clamped % 3600) / 60);
  const secs = clamped % 60;
  if (hrs > 0) {
    return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

/**
 * Bande unique au-dessus du prompt : chaque mod y verse des segments (gauche = crew,
 * droite = météo) au lieu de dessiner sa propre ligne, ce qui évitait l'empilement.
 */
export interface BandSegment {
  slot: 'left' | 'right' | 'alert';
  text: string;
  order?: number;
  color?: string;
  bold?: boolean;
  dimColor?: boolean;
}

export interface BandAccumulator {
  crewBand: true;
  foreign: unknown;
  blocks: unknown[];
  segments: BandSegment[];
}

export function isBandAccumulator(value: unknown): value is BandAccumulator {
  return typeof value === 'object' && value !== null && (value as BandAccumulator).crewBand === true;
}

export function addBandSegments(prev: unknown, ...segments: BandSegment[]): BandAccumulator {
  if (isBandAccumulator(prev)) return { ...prev, segments: [...prev.segments, ...segments] };
  return { crewBand: true, foreign: prev ?? null, blocks: [], segments };
}

/** Bloc multi-lignes déjà dessiné (ex. arbre des subagents), posé au-dessus de la ligne unique. */
export function addBandBlock(prev: unknown, block: unknown): BandAccumulator {
  const acc = addBandSegments(prev);
  return { ...acc, blocks: [...acc.blocks, block] };
}

export function renderBandAccumulator(
  acc: BandAccumulator,
  ui: { Box: (p: any) => unknown; Text: (p: any) => unknown },
): unknown {
  const byOrder = (a: BandSegment, b: BandSegment) => (a.order ?? 100) - (b.order ?? 100);
  const text = (s: BandSegment) =>
    ui.Text({ color: s.color, bold: s.bold, dimColor: s.dimColor, children: [s.text] });
  const side = (slot: 'left' | 'right') =>
    ui.Box({
      flexDirection: 'row',
      gap: 2,
      children: acc.segments.filter((s) => s.slot === slot).sort(byOrder).map(text),
    });
  const alerts = acc.segments.filter((s) => s.slot === 'alert').map((s) =>
    ui.Box({ flexDirection: 'row', paddingX: 1, children: [text(s)] }),
  );
  const hasMain = acc.segments.some((s) => s.slot !== 'alert');
  const rows = [
    ...(acc.foreign ? [acc.foreign] : []),
    ...acc.blocks,
    ...alerts,
    ...(hasMain
      ? [
          ui.Box({
            flexDirection: 'row',
            paddingX: 1,
            justifyContent: 'space-between',
            children: [side('left'), side('right')],
          }),
        ]
      : []),
  ];
  if (rows.length === 0) return null;
  return ui.Box({ flexDirection: 'column', children: rows });
}
