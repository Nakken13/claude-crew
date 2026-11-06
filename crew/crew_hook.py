# -*- coding: utf-8 -*-
"""Stop/SessionEnd/SessionStart/PreToolUse hook — project task management.
At the end of every turn (Stop):
  1. regenerates crew/<dir>/INDEX.md (titles + links),
  2. logs transitions (started / finished / added) in
     crew/CLAUDE_CONTEXT/CHANGELOG_TACHES.md,
  3. blocks the end of the turn if a task is in TODO/, CURRENT_TASKS/ and/or
     PAUSED/ at the same time (never two folders at once),
  4. reminds to log into the history + extract the tests when a task has just been finished,
  5. maintains live PER-SESSION locks (crew_lock.json, multi-Claude
     anti-collision, writes protected by LocksMutex) and blocks the turn if a
     started task has a batch neighbour already locked by another
     session, or if two active batches with overlapping zones are locked
     by different sessions (see crew/CLAUDE_CONTEXT/BATCH_LOCKS.md,
     regenerated every turn),
  6. LOCAL-ONLY git commit (never a push, see `auto_commit_closure`)
     scoped to `crew/` when a task has actually been closed in this
     same turn (file gone from `CURRENT_TASKS/` + `HISTORIQUE.md`
     actually modified) — systematic git trace of every closure without
     pushing anything automatically, the push stays a human decision.
  7. removes from crew/CLAUDE_BATCH.md every `## Batch`/`### Batch` section
     whose listed tasks are ALL struck through (~~`slug.md`~~) — fully
     closed batch (see `prune_closed_batches`) — to keep the
     file from growing indefinitely; the full history stays in
     HISTORIQUE.md, already written when each task is closed. Empty/
     placeholder sections (0 referenced tasks) are never touched.
On PreToolUse (matcher Bash|Edit|Write|MultiEdit, see gate_pretooluse):
  - `Edit`/`Write`/`MultiEdit`: blocks before writing if `file_path` falls
    under a batch `Zone:` locked by ANOTHER session.
  - `Bash`: preventive check before running a `git mv` TODO->CURRENT_TASKS
    (categorized task + no collision), plus a best-effort scan of mutating
    commands (`rm`/`mv`/`cp`/`>` redirection) against the same locked
    zones — Layer 2, a safety net complementing the physical isolation
    by worktree (Layer 1, handled by `/crew-start`).
Never breaks the turn: any internal error -> silent exit 0 (except the
deliberate exit(2) block of gate_pretooluse).
"""
import json, os, re, sys, shlex, time, datetime, pathlib, shutil, fnmatch, subprocess, hashlib

def _git_root(start):
    """First git root (folder or worktree `.git` file) walking up
    from `start`. A session launched in a subfolder (backend/, frontend/)
    must not create a phantom `crew/` there: with no `.git` found, `start` as is."""
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parent.parent)  # project root


def _resolve_main_root(root):
    """Root of the main checkout for `root`, without spawning git: `root/.git`
    folder -> `root`; file (worktree) -> `gitdir:` line then `commondir`
    of that gitdir, whose parent (`.git`) gives the main checkout. Silent fallback
    to `root` if reading fails, bare repo, or no `crew/CLAUDE_CONTEXT/` in the
    resolved main checkout — never raises."""
    try:
        git = root / ".git"
        if not git.is_file():
            return root
        line = next((l for l in git.read_text(encoding="utf-8").splitlines()
                     if l.startswith("gitdir:")), None)
        if line is None:
            return root
        gitdir = pathlib.Path(line[len("gitdir:"):].strip().replace("\\", "/"))
        if not gitdir.is_absolute():
            gitdir = root / gitdir
        common_rel = (gitdir / "commondir").read_text(encoding="utf-8").strip().replace("\\", "/")
        common = (gitdir / common_rel).resolve()
        if common.name != ".git":
            return root
        main = common.parent
        return main if (main / "crew" / "CLAUDE_CONTEXT").is_dir() else root
    except Exception:
        return root


def _shared_lock_paths(root):
    """(MAIN_ROOT, crew_lock.json, mutex) of the lock shared between the main
    checkout and all its batch worktrees."""
    main = _resolve_main_root(root)
    ctx = main / "crew" / "CLAUDE_CONTEXT"
    return main, ctx / "crew_lock.json", ctx / ".crew_lock.mutex"


MAIN_ROOT, LOCKS_FILE, LOCKS_MUTEX = _shared_lock_paths(ROOT)
# TODO tasks from other devs that /crew-start must ignore (local, not versioned).
IGNORED_FILE = LOCKS_FILE.with_name("crew_ignored.json")
CREW = ROOT / "crew"
DIRS = {
    "PROBLEMS": CREW / "PROBLEMS",
    "TODO": CREW / "TODO",
    "ICEBOX": CREW / "ICEBOX",
    "CURRENT_TASKS": CREW / "CURRENT_TASKS",
    "PAUSED": CREW / "PAUSED",
    "TESTS": CREW / "TESTS",
    "TESTS/IA": CREW / "TESTS" / "IA",
    "TESTS/DEV": CREW / "TESTS" / "DEV",
}
CTX = CREW / "CLAUDE_CONTEXT"
SNAP = CTX / ".task_state.json"
CHANGELOG = CTX / "CHANGELOG_TACHES.md"
BATCH_FILE = CREW / "CLAUDE_BATCH.md"
# LOCKS_FILE/LOCKS_MUTEX: lock shared in the main checkout (see
# _shared_lock_paths above), schema session->{batch,tasks,worktree,branch,since}.
BATCH_LOCKS_MD = CTX / "BATCH_LOCKS.md"
HISTORIQUE = CTX / "HISTORIQUE.md"
HISTORIQUE_ARCHIVE = CTX / "HISTORIQUE_ARCHIVE.md"
HISTORIQUE_ROTATE_MONTHS = 6  # beyond this, an entry leaves the live file (see rotate_historique)
LOCK_TTL = datetime.timedelta(hours=6)
MUTEX_TTL_SEC = 30  # mutex held longer -> session crashed mid-write, we clear it
MUTEX_WAIT_SEC = 2.0  # max wait before continuing without the mutex (best-effort, never blocks the turn)

INTRO = {
    "PROBLEMS": "Problems. Resolved → move the context to `HISTORIQUE.md`.\n\n",
    "TODO": "Tasks not started yet. Start = move the file to `crew/CURRENT_TASKS/` (see `CLAUDE.md`).\n\n",
    "ICEBOX": "Ideas/tasks deliberately parked (distinct from TODO). To resume: move to `crew/TODO/` first.\n\n",
    "CURRENT_TASKS": "Tasks in progress. Done → delete + `crew/CLAUDE_CONTEXT/HISTORIQUE.md` entry + `crew/TESTS/<chantier>.md`.\n\n",
    "PAUSED": "Tasks started but blocked on a visual/dev validation the AI cannot do alone. To resume: move to `crew/CURRENT_TASKS/` once the validation is done.\n\n",
    "TESTS": ("Validation checklists for finished features (see `README.md`). "
              "Sorted by who runs them:\n"
              "- [IA](IA/INDEX.md) — tests the AI can run on its own (🤖 auto + 🔍 config/curl/DB/logs)\n"
              "- [DEV](DEV/INDEX.md) — tests that need the dev (🖱️ manual/visual + items without tooling)\n\n"),
    "TESTS/IA": "Tests the AI can run (🤖 auto + 🔍 config/direct request). Single source per chantier; its 🖱️ counterpart is in `../DEV/`.\n\n",
    "TESTS/DEV": "Tests that need the dev (🖱️ manual/visual in the browser, or an item with no AI tooling). The automatable counterpart is in `../IA/`.\n\n",
}


def title_of(f):
    try:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return f.stem


def task_files(d):
    out = {}
    if d.exists():
        for f in sorted(d.glob("*.md")):
            if f.name in ("INDEX.md", "README.md") or f.name.startswith("_"):
                continue
            out[f.name] = title_of(f)
    return out


def regen_index(name, d):
    files = task_files(d)
    lines = [f"# Index {name}\n\n", INTRO.get(name, "")]
    for fn, t in files.items():
        lines.append(f"- [{t}]({fn})\n")
    if d.exists():
        (d / "INDEX.md").write_text("".join(lines), encoding="utf-8")
    return list(files.keys())


def process_completed_tests():
    """Checks the test files in TESTS/IA/. If they are fully checked
    ([x] present, 0 [ ]), moves them to CLAUDE_CONTEXT/TESTS_DONE/."""
    done_dir = CTX / "TESTS_DONE"
    done_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    ia_dir = DIRS["TESTS/IA"]
    if ia_dir.exists():
        for f in ia_dir.glob("*.md"):
            if f.name in ("INDEX.md", "README.md") or f.name.startswith("_"):
                continue
            content = f.read_text(encoding="utf-8")
            if "[ ]" not in content and ("[x]" in content.lower() or "[X]" in content):
                # Use replace() to overwrite if the file already exists
                f.replace(done_dir / f.name)
                moved.append(f.name)
    return moved


TASK_LINE_RE = re.compile(
    r"^[ \t]*(?:\d+\.|[-*])\s*(~~)?`(?:[\w\-./]*/)?([\w\-.]+\.md)`(~~)?",
    re.MULTILINE,
)


def check_batches():
    """Warns (non-blocking) if a TODO/CURRENT/PAUSED task is not categorized
    in CLAUDE_BATCH.md, or if the file references a task that no longer exists. Refs = slugs
    of the list lines only (TASK_LINE_RE) → header prose (`CLAUDE.md`), the
    Zone line and `<...>.md` placeholders are ignored. Struck-through refs
    (~~`slug.md`~~) mark a task already finished/removed by project
    convention: its file has normally been deleted, so they are excluded from the
    scan to avoid a false positive on every closure."""
    warnings = []
    if not BATCH_FILE.exists():
        return warnings
    text = BATCH_FILE.read_text(encoding="utf-8")
    referenced = {
        m.group(2) for m in TASK_LINE_RE.finditer(text) if not (m.group(1) and m.group(3))
    }
    actual = active_task_slugs()  # same TODO/CURRENT_TASKS/PAUSED scan, single source
    for f in sorted(actual - referenced):
        warnings.append(f"[batch] Task not categorized in CLAUDE_BATCH.md: `{f}`")
    for f in sorted(referenced - actual):
        warnings.append(f"[batch] CLAUDE_BATCH.md references a task that does not exist: `{f}`")
    return warnings


def _task_line_counts(body):
    """Counts, over the list lines of a batch section (`- `/`N. ` followed
    by a `slug.md` ref), how many reference a task and how many are
    struck through (~~...~~). Anchored at line start to ignore incidental .md refs
    in prose (e.g. 'see `HISTORIQUE.md`') or in the Zone line."""
    total = closed = 0
    for m in TASK_LINE_RE.finditer(body):
        total += 1
        if m.group(1) and m.group(3):
            closed += 1
    return total, closed


def prune_closed_batches(text):
    """Removes from CLAUDE_BATCH.md the '## Batch'/'### Batch' sections whose
    listed tasks are ALL struck through (fully closed batch) — avoids
    the file growing indefinitely with finished batches (their
    full history stays in HISTORIQUE.md, already written when each
    task is closed). Sections with no referenced task (empty batch/
    placeholder, e.g. 'Batch A' with `<slug>.md`) are left intact.
    Returns (new_text, removed_headers)."""
    headers = list(re.finditer(r"^#{2,3}\s*Batch\b.*$", text, re.MULTILINE))
    removed = []
    keep_spans = []
    cursor = 0
    for i, m in enumerate(headers):
        body_start = m.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        total, closed = _task_line_counts(text[body_start:body_end])
        if total and total == closed:
            removed.append(m.group().lstrip("#").strip())
            keep_spans.append((cursor, m.start()))
            cursor = body_end
    if not removed:
        return text, []
    keep_spans.append((cursor, len(text)))
    new_text = "".join(text[a:b] for a, b in keep_spans)
    new_text = re.sub(r"\n{3,}", "\n\n\n", new_text)
    return new_text, removed


def rotate_graphify_snapshots(keep=3):
    """Purges the dated snapshots graphify-out/YYYY-MM-DD (regenerable via
    `graphify update .`), keeping the `keep` most recent. Lexical sort
    = chronological sort with this name format."""
    out = ROOT / "graphify-out"
    if not out.exists():
        return
    dated = sorted(d for d in out.glob("20??-??-??") if d.is_dir())
    for d in dated[:-keep]:
        shutil.rmtree(d, ignore_errors=True)


_HISTORIQUE_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HISTORIQUE_HEADER_RE = re.compile(r"^## (?P<rest>.+)$", re.MULTILINE)
_HISTORIQUE_DATE_RE = re.compile(r"^(?P<title>.+?) — (?P<date>\d{4}-\d{2}-\d{2})(?:\s.*)?$")


def rotate_historique_entries(text, cutoff):
    """Splits HISTORIQUE.md into (text to keep, text to archive, archived
    slugs): an entry `## <slug> — YYYY-MM-DD` whose date is
    earlier than `cutoff` (date) goes into the second. Without rotation the
    file grows endlessly — every future full read (agent,
    skill) gets more expensive in tokens even when following the rule
    'read by slices' (crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md § Context efficiency), since
    finding the right slice already assumes knowing where to look. A header
    with no parseable date (malformed entry, e.g. `## verif-fork-throwaway`)
    is NEVER rotated blindly — unable to compare it to the cutoff,
    it stays in the live file. A header inside an HTML
    comment block `<!-- ... -->` (e.g. the format example documented in
    HISTORIQUE.md) is ignored: it is not a real entry."""
    comment_spans = [m.span() for m in _HISTORIQUE_COMMENT_RE.finditer(text)]

    def _in_comment(pos):
        return any(start <= pos < end for start, end in comment_spans)

    headers = [m for m in _HISTORIQUE_HEADER_RE.finditer(text) if not _in_comment(m.start())]
    if not headers:
        return text, "", []

    bounds = [m.start() for m in headers] + [len(text)]
    kept = [text[:headers[0].start()]]  # preamble (file intro) always kept
    archived = []
    slugs = []
    for i, m in enumerate(headers):
        entry = text[bounds[i]:bounds[i + 1]]
        dm = _HISTORIQUE_DATE_RE.match(m.group("rest"))
        entry_date = None
        if dm:
            try:
                entry_date = datetime.date.fromisoformat(dm.group("date"))
            except ValueError:
                entry_date = None
        if entry_date and entry_date < cutoff:
            archived.append(entry)
            slugs.append(dm.group("title"))
        else:
            kept.append(entry)
    return "".join(kept), "".join(archived), slugs


def rotate_historique(now_dt, months=HISTORIQUE_ROTATE_MONTHS):
    """Applies rotate_historique_entries to HISTORIQUE.md on disk: archived
    entries are removed from the live file and appended
    to HISTORIQUE_ARCHIVE.md, never lost. Returns the archived slugs
    (empty list = nothing to do, the normal case most turns)."""
    if not HISTORIQUE.exists():
        return []
    text = HISTORIQUE.read_text(encoding="utf-8")
    cutoff = now_dt.date() - datetime.timedelta(days=30 * months)
    kept, archived, slugs = rotate_historique_entries(text, cutoff)
    if not slugs:
        return []
    HISTORIQUE.write_text(kept, encoding="utf-8")
    head = ""
    if not HISTORIQUE_ARCHIVE.exists():
        head = ("# Archived history\n\n"
                f"> Entries older than {months} months, moved automatically "
                "from `HISTORIQUE.md` by the Stop hook (`rotate_historique`). "
                "Same content, just outside the default reading path — grep here "
                "if an old entry seems to be missing.\n\n")
    with HISTORIQUE_ARCHIVE.open("a", encoding="utf-8") as fh:
        fh.write(head + archived)
    return slugs


class LocksMutex:
    """Portable file lock (Windows included: no fcntl) around the
    read-modify-write critical section of crew_lock.json. Implemented via
    O_CREAT|O_EXCL on a separate marker file (atomic creation guaranteed
    by the OS on both sides). Best-effort: a few short attempts, then we
    continue without the mutex rather than risk blocking the turn (the hook must
    never break a turn); a mutex held longer than MUTEX_TTL_SEC is discarded
    (session probably crashed mid-write)."""

    def __init__(self):
        self._acquired = False

    def __enter__(self):
        self._acquired = False
        deadline = time.monotonic() + MUTEX_WAIT_SEC
        while True:
            try:
                fd = os.open(str(LOCKS_MUTEX), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self._acquired = True
                return self
            except FileExistsError:
                try:
                    if time.time() - LOCKS_MUTEX.stat().st_mtime > MUTEX_TTL_SEC:
                        LOCKS_MUTEX.unlink(missing_ok=True)
                        continue
                except Exception:
                    pass
                if time.monotonic() >= deadline:
                    return self  # best-effort: not acquired, carry on anyway
                time.sleep(0.05)
            except Exception:
                return self  # best-effort: no mutex, carry on anyway

    def __exit__(self, *exc_info):
        # Never remove the marker if THIS instance did not create it
        # (timeout/error at enter): otherwise we would delete the lock of ANOTHER
        # session still writing (see code-review).
        if self._acquired:
            try:
                LOCKS_MUTEX.unlink()
            except Exception:
                pass


def load_locks():
    """Loads crew_lock.json. Guaranteed return shape: {"sessions": {...}}
    (one entry per active session, see module docstring) — a missing,
    corrupted, or old flat-format (.batch_locks.json) file falls back to an empty
    base rather than propagating an unexpected shape to callers."""
    if LOCKS_FILE.exists():
        try:
            data = json.loads(LOCKS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("sessions"), dict):
                return data
        except Exception:
            pass
    return {"sessions": {}}


def save_locks(locks):
    """Atomic write (temp file + os.replace): avoids a truncated
    crew_lock.json if the process is killed mid-write."""
    tmp = LOCKS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(locks, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(LOCKS_FILE))
    _sync_gate_marker(locks)


GATE_MARKER = ".gate_armed"


def _sync_gate_marker(locks):
    """Marker `crew/CLAUDE_CONTEXT/.gate_armed`: present iff >= 2 sessions in
    `locks`, otherwise the anti-collision guard is moot and the shell command of
    hooks.json skips the Python spawn (see PreToolUse). The pre-filter tests
    `$CLAUDE_PROJECT_DIR/...` (= current worktree) while the lock lives in the
    main checkout: the marker is set in the main checkout AND in every registered
    worktree. Its content lists the armed worktrees, so they can be disarmed
    even after their session has disappeared from the lock. Best-effort: never
    raises."""
    try:
        main_marker = LOCKS_FILE.parent / GATE_MARKER
        previous = []
        try:
            previous = json.loads(main_marker.read_text(encoding="utf-8"))
        except Exception:
            pass
        sessions = locks.get("sessions", {})
        armed = len(sessions) >= 2
        wanted = []
        for info in sessions.values() if armed else ():
            wt = info.get("worktree") if isinstance(info, dict) else None
            ctx = str((MAIN_ROOT / wt).resolve() / "crew" / "CLAUDE_CONTEXT") if wt else None
            if ctx and pathlib.Path(ctx).is_dir() and ctx not in wanted:
                wanted.append(ctx)
        for ctx in previous if isinstance(previous, list) else []:
            if ctx not in wanted:
                _unlink_quiet(pathlib.Path(ctx) / GATE_MARKER)
        if armed:
            for ctx in wanted:
                _write_quiet(pathlib.Path(ctx) / GATE_MARKER, "[]")
            _write_quiet(main_marker, json.dumps(wanted))
        else:
            _unlink_quiet(main_marker)
    except Exception:
        pass


def _unlink_quiet(path):
    try:
        path.unlink()
    except Exception:
        pass


def _write_quiet(path, text):
    try:
        if not (path.is_file() and path.read_text(encoding="utf-8") == text):
            path.write_text(text, encoding="utf-8")
    except Exception:
        pass


WARNING_COOLDOWN_MINUTES = 30


def migrate_legacy_worktree_lock():
    """Merges into the shared lock the old local `crew_lock.json` of a
    worktree (before centralization in the main checkout), under mutex, then
    deletes it. Per session, the most recent `since` wins. No-op from the
    main checkout or without a legacy file; never raises."""
    try:
        legacy = CTX / "crew_lock.json"
        if ROOT == MAIN_ROOT or not legacy.exists() or legacy.resolve() == LOCKS_FILE.resolve():
            return
        old = json.loads(legacy.read_text(encoding="utf-8")).get("sessions", {})
        with LocksMutex():
            locks = load_locks()
            sessions = locks["sessions"]
            for sid, info in old.items():
                if not isinstance(info, dict):
                    continue
                if sid not in sessions or str(info.get("since", "")) > str(sessions[sid].get("since", "")):
                    sessions[sid] = info
            save_locks(locks)
        legacy.unlink()
    except Exception:
        pass


def _throttle_warnings(category, warnings, locks, now_dt, cooldown_minutes=WARNING_COOLDOWN_MINUTES):
    """Only surfaces a non-blocking warning (check_batches/check_zone_overlaps)
    once, then at most once per `cooldown_minutes` while the
    condition that triggered it stays true — without this the same line is
    re-printed on stderr on EVERY Stop turn (context cost proportional to the
    number of turns, not to the number of real conditions to fix). State
    persisted in locks["warned"][category]: {text -> last ISO
    timestamp emitted}, saved by the same save_locks(locks) as the rest of the
    lock file. A key whose condition has disappeared is purged (no
    memory leak) and warns again immediately if it reappears later
    rather than inheriting a stale cooldown."""
    # Scoped per checkout (the lock is shared): otherwise two checkouts
    # mask each other's warnings. Key unchanged for the main checkout.
    key = category if ROOT == MAIN_ROOT else f"{category}@{ROOT.name}"
    bucket = locks.setdefault("warned", {}).setdefault(key, {})
    current = set(warnings)
    for stale in set(bucket) - current:
        del bucket[stale]
    due = []
    for w in warnings:
        last = bucket.get(w)
        if last is not None:
            try:
                elapsed_min = (now_dt - datetime.datetime.fromisoformat(last)).total_seconds() / 60
            except Exception:
                elapsed_min = cooldown_minutes + 1
            if elapsed_min < cooldown_minutes:
                continue
        bucket[w] = now_dt.isoformat()
        due.append(w)
    return due


def _session_expired(info, now_dt):
    """Session entry older than LOCK_TTL (session probably
    crashed) or corrupted (no readable ISO `since`)."""
    since_raw = info.get("since") if isinstance(info, dict) else None
    try:
        return now_dt - datetime.datetime.fromisoformat(since_raw) > LOCK_TTL
    except Exception:
        return True


def purge_stale_locks(locks, now_dt):
    """Removes SESSION entries older than LOCK_TTL (session probably
    crashed) — tasks + worktree + branch go together, a session cannot
    be half purged. Returns the sorted list of purged session_ids."""
    sessions = locks.setdefault("sessions", {})
    stale = []
    for sid, info in list(sessions.items()):
        if _session_expired(info, now_dt):
            stale.append(sid)
            del sessions[sid]
    return sorted(stale)


def _slug_session_map(locks):
    """Derived slug -> session_id view built from sessions[*].tasks — single
    source consumed by check_batch_collisions / _section_lock_sessions /
    regen_batch_locks_md, to avoid duplicating the derivation logic.
    A slug should never belong to 2 sessions at once (an invariant
    violation rather than a normal case); if it happens anyway (bug
    elsewhere or manual edit of crew_lock.json), the last iterated session
    silently wins without this warning — report it on stderr rather than
    letting it pass without a trace."""
    out = {}
    for sid, info in locks.get("sessions", {}).items():
        for slug in info.get("tasks", []) or []:
            if slug in out and out[slug] != sid:
                sys.stderr.write(
                    f"[crew_lock] inconsistency: `{slug}` appears in the tasks of 2 sessions "
                    f"(`{out[slug]}` and `{sid}`) — lock probably corrupted, "
                    f"session `{sid}` kept.\n"
                )
            out[slug] = sid
    return out


def _batch_key(header):
    """Stable identity of a batch: header truncated at the first ' · ' (the suffix
    is a displayed status — 'pas demarre', 'en cours (prochaine : 04)' — that
    changes without the batch changing)."""
    return (header or "").split(" · ", 1)[0].strip()


def _batch_slug(header):
    """Filesystem/branch-safe slug derived from the batch key (e.g.
    'Batch plugin-packaging' -> 'plugin-packaging'), used to name the
    dedicated worktree and branch of this batch deterministically."""
    text = re.sub(r"^Batch\b\s*[:\-—]?\s*", "", _batch_key(header), flags=re.IGNORECASE).strip()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "batch"


def _worktree_paths_for(header):
    """Worktree path (sibling of the main checkout) + deterministic branch
    name for a batch, derived from its header (see _batch_slug)."""
    slug = _batch_slug(header)
    return f"../{MAIN_ROOT.name}-batch-{slug}", f"crew/batch-{slug}"


def _register_task_lock(slug, session_id, locks, now_dt, sections=None):
    """Adds `slug` to the tasks of session `session_id` in `locks`
    (creates the session entry if missing, deriving batch/worktree/branch
    from CLAUDE_BATCH.md via find_section_for), refreshes its `since`.
    Idempotent: does not duplicate `slug` if already present. A session is
    assumed to carry only one batch at a time (product rule of
    /crew-start, § 'What this skill does not do'); if a slug from ANOTHER
    batch is registered on a session that already has one, the entry's batch/worktree/
    branch are NOT overwritten (keeps the first source of
    truth) but the inconsistency is reported on stderr rather than staying
    invisible (same spirit as the _slug_session_map warning). Returns
    the updated session entry."""
    sections = sections if sections is not None else load_sections()
    section = find_section_for(slug, sections)
    sessions = locks.setdefault("sessions", {})
    info = sessions.setdefault(session_id, {"batch": None, "tasks": [], "worktree": None,
                                              "branch": None, "since": now_dt.isoformat()})
    info["since"] = now_dt.isoformat()
    if section and info.get("batch") is None:
        info["batch"] = _batch_key(section["header"])
        info["worktree"], info["branch"] = _worktree_paths_for(section["header"])
    elif section and _batch_key(info.get("batch")) != _batch_key(section["header"]):
        sys.stderr.write(
            f"[crew_lock] inconsistency: session `{session_id}` registers `{slug}` "
            f"(batch \"{section['header']}\") while it already holds batch "
            f"\"{info.get('batch')}\" — a session should only carry one batch at a time.\n"
        )
    if slug not in info["tasks"]:
        info["tasks"].append(slug)
    return info


def slugs_by_batch_section(text):
    """Parses CLAUDE_BATCH.md: splits on the '## Batch'/'### Batch' headers,
    extracts for each section the `xxx.md` slugs referenced in backticks
    (bare format or full path `crew/<subfolder>/xxx.md`), and the paths
    declared on its `Zone : ...` line (for cross-batch overlap
    detection, see check_zone_overlaps)."""
    sections = []
    headers = list(re.finditer(r"^#{2,3}\s*Batch\b.*$", text, re.MULTILINE))
    # The "À classer" section (unknown zone) is not a batch: it bounds the
    # last section instead of being swallowed into it.
    unclassified = re.search(r"^#{2,3}\s*[AÀ] classer\b", text, re.MULTILINE | re.IGNORECASE)
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        if unclassified and start < unclassified.start() < end:
            end = unclassified.start()
        body = text[start:end]
        raw_refs = re.findall(r"`(?:[\w\-./]*/)?([\w\-.]+\.md)`", body)
        slugs = set(raw_refs)
        struck = set(re.findall(r"~~\s*`(?:[\w\-./]*/)?([\w\-.]+\.md)`\s*~~", body))  # closed tasks
        ordered = list(dict.fromkeys(raw_refs))  # order of appearance = intended sequencing of the batch
        zone_match = re.search(r"^\*{0,2}Zone\b[^:\n]*:\*{0,2}\s*(.+)$", body, re.MULTILINE)
        zone_paths = set(re.findall(r"`([^`]+)`", zone_match.group(1))) if zone_match else set()
        sections.append({"header": m.group().lstrip("#").strip(), "slugs": slugs, "zone_paths": zone_paths,
                         "ordered": ordered, "struck": struck})
    return sections


def find_section_for(slug, sections):
    for section in sections:
        if slug in section["slugs"]:
            return section
    return None


def load_sections():
    """Parses CLAUDE_BATCH.md into batch sections (empty list if missing).
    Used by both the Stop hook (main) and the PreToolUse guard
    (gate_pretooluse) — single source to avoid duplication."""
    return slugs_by_batch_section(BATCH_FILE.read_text(encoding="utf-8")) if BATCH_FILE.exists() else []


def check_batch_collisions(started, sections, locks, session_id):
    """For each task that starts, checks that its neighbours in the same batch
    section are not already locked by ANOTHER session. Returns a
    combined blocking reason (or None)."""
    slug_sessions = _slug_session_map(locks)
    reasons = []
    for f in sorted(started):
        section = find_section_for(f, sections)
        if not section:
            continue
        for neighbor in sorted(section["slugs"] - {f}):
            other_session = slug_sessions.get(neighbor)
            if other_session and other_session != session_id:
                since = locks.get("sessions", {}).get(other_session, {}).get("since", "?")
                reasons.append(
                    f"batch \"{section['header']}\": `{f}` starts while `{neighbor}` "
                    f"is already locked by another session (since {since})"
                )
    if not reasons:
        return None
    return ("Live batch lock — collision detected: " + " ; ".join(reasons) +
            ". Wait for the other session to finish or pick a task from another batch.")


def _tokenize_command(command):
    """Best-effort tokenization of a Bash command (possibly compound:
    `a; b && c`) into tokens normalized to the POSIX separator (`/`). `posix=True`
    is pinned (not `sys.platform`-dependent): the Bash tool always runs
    a POSIX shell (Git Bash), whatever the host OS — otherwise quotes
    around a path stay in the token on Windows. Falls back to a plain
    `.split()` if `shlex` fails (shell too exotic for it) —
    single source shared by `_extract_git_mv_task` and
    `_extract_candidate_paths`, the two best-effort scans of the Bash gate."""
    try:
        tokens = shlex.split(command, posix=True)
    except Exception:
        tokens = command.split()
    return [t.replace("\\", "/") for t in tokens]


def _extract_git_mv_task(command):
    """If `command` contains a `git mv` moving a file from
    crew/TODO/ OR crew/PAUSED/ to crew/CURRENT_TASKS/, returns its slug
    (file name). Otherwise None. Best-effort: does not parse a complex
    shell, only covers the documented case `git mv crew/{TODO,PAUSED}/
    x.md crew/CURRENT_TASKS/x.md` (with possible flags before the two
    paths). PAUSED is treated like TODO here: a post-pause resume must
    fall under the same preventive batch anti-collision check
    (`_claim_git_mv_lock`/`check_batch_collisions`) as a first start,
    see code review. Tries ALL occurrences of `mv` in the command
    (not only the first): a compound command may have an unrelated `mv`
    before the real `git mv` to watch."""
    todo_name, current_name = DIRS["TODO"].name, DIRS["CURRENT_TASKS"].name
    paused_name = DIRS["PAUSED"].name
    if "mv" not in command or current_name not in command:
        return None
    if todo_name not in command and paused_name not in command:
        return None
    norm = _tokenize_command(command)
    for mv_i, tok in enumerate(norm):
        if tok != "mv":
            continue
        args = [t for t in norm[mv_i + 1:] if not t.startswith("-")]
        if len(args) < 2:
            continue
        src, dst = args[0], args[1]
        if f"{current_name}/" not in dst:
            continue
        if f"{todo_name}/" not in src and f"{paused_name}/" not in src:
            continue
        if not src.endswith(".md"):
            continue
        return src.rsplit("/", 1)[-1]
    return None


def _extract_resume_claim(command):
    """Recognizes the no-op marker `: "crew-resume:<slug>.md"` that a
    `/crew-start` (Case A: resuming a task ALREADY in CURRENT_TASKS, no
    `git mv` so nothing for `_extract_git_mv_task` to intercept) must run
    before resuming work. `:` is the Bash no-op (no side effect)
    — only the command text carries the intent to the hook.
    Returns the slug if found, otherwise None."""
    m = re.search(r"crew-resume:([\w\-.]+\.md)", command)
    return m.group(1) if m else None


def _claim_lock(slug, session_id, action_verb, sections=None, extra_check=None, on_success=None):
    """Primitive shared by `_claim_resume_lock` and `_claim_git_mv_lock`:
    under mutex, reload + purge + check that no OTHER session already holds
    this exact slug (TOCTOU-safe with respect to any read of `locks`
    done by the caller BEFORE the mutex), then an optional `extra_check(locks) ->
    reason|None` (e.g. `check_batch_collisions` for batch
    neighbours), registers the lock (`_register_task_lock`) and saves.
    Blocks (exit 2 + stderr) on any collision — `action_verb` ('resume'/
    'start') humanizes the message. Optional `on_success(locks)` runs
    right after `save_locks`, still under mutex (e.g. regen_batch_locks_md)."""
    with LocksMutex():
        locks = load_locks()
        now_dt = datetime.datetime.now()
        purge_stale_locks(locks, now_dt)
        other_session = _slug_session_map(locks).get(slug)
        if other_session and other_session != session_id:
            since = locks.get("sessions", {}).get(other_session, {}).get("since", "?")
            sys.stderr.write(
                f"Live lock — `{slug}` has already been picked up by another session "
                f"(since {since}). Wait for that session to finish before you {action_verb} the same task "
                "(or pick another task).\n"
            )
            sys.exit(2)
        if extra_check is not None:
            reason = extra_check(locks)
            if reason:
                sys.stderr.write(reason + "\n")
                sys.exit(2)
        _register_task_lock(slug, session_id, locks, now_dt, sections)
        save_locks(locks)
        if on_success is not None:
            on_success(locks)


def _claim_resume_lock(slug, session_id):
    """Claims (or refreshes) the live lock for a task ALREADY present in
    CURRENT_TASKS that a session resumes (`/crew-start` Case A). Closes the hole
    in the historical mechanism: the lock was only set at the time of the `git mv`
    TODO->CURRENT_TASKS (see `_extract_git_mv_task`/`started` in `main()`),
    so two sessions independently resuming the SAME task already
    in CURRENT_TASKS (no `git mv`, hence no `started`) never
    triggered any check — neither lock nor collision.
    Preventive (before the session starts editing the task), not
    retroactive like the Stop check. See `_claim_lock` for details."""
    _claim_lock(slug, session_id, "resume")


def _claim_git_mv_lock(slug, session_id, sections):
    """Registers the live lock for a task started via `git mv`
    TODO->CURRENT_TASKS (gate_pretooluse), BEFORE the mv actually runs
    — closes the worktree hole (the Stop hook is ROOT-anchored, it never sees
    a `git mv` done from `../<repo>-batch-<slug>/`, see task
    fix-worktree-gitmv-lock-registration-gap). Adds to `_claim_lock` the
    batch-neighbour check (`check_batch_collisions`, fresh under
    mutex — closes the TOCTOU with the `locks` read already done earlier in
    gate_pretooluse for the generic scan of the same invocation) and the
    regeneration of BATCH_LOCKS.md: otherwise the human doc would lag
    behind crew_lock.json until the next Stop turn. `active` computed OUTSIDE
    the mutex (disk I/O unrelated to crew_lock.json, same reasoning as
    in `main()`)."""
    active = active_task_slugs()
    _claim_lock(
        slug, session_id, "start", sections=sections,
        extra_check=lambda locks: check_batch_collisions({slug}, sections, locks, session_id),
        on_success=lambda locks: regen_batch_locks_md(sections, locks, active),
    )


def _locked_zones_by_others(sections, locks, session_id):
    """Returns [(zone_path, section_header, other_session_id, since), ...]
    for each `Zone:` of an ACTIVE batch (>=1 task locked) by a
    session != session_id — the list the hardened gate must block."""
    out = []
    sessions = locks.get("sessions", {})
    slug_sessions = _slug_session_map(locks)
    for section in sections:
        others = sorted(_section_lock_sessions(section, locks, slug_sessions) - {session_id})
        if not others:
            continue
        other = others[0]
        since = sessions.get(other, {}).get("since", "?")
        for zp in section["zone_paths"]:
            out.append((zp, section["header"], other, since))
    return out


def _repo_relative_path(path, locks=None):
    """Normalizes `path` (absolute or relative, Windows or POSIX separators) into a
    POSIX path relative to the logical repo, for comparison with the `Zone:`
    entries of CLAUDE_BATCH.md (always expressed relative to the repo root).
    `Edit`/`Write`/`MultiEdit` always provide an ABSOLUTE `file_path`:
    without this normalization a direct comparison with a relative Zone:
    never matches (bug found in the worktree-batch-isolation code review).
    A path under the worktree of a known batch (crew_lock.json) is brought back
    to the same logical relative path as under ROOT, since a `git worktree`
    mirrors the structure of the main repo. Fail-open if
    resolution fails (falls back to a plain separator cleanup)."""
    try:
        p = pathlib.Path(str(path))
    except Exception:
        return str(path).replace("\\", "/").lstrip("./")
    if not p.is_absolute():
        return str(p).replace("\\", "/").lstrip("./")
    rp = p.resolve()
    for base in ((ROOT,) if ROOT == MAIN_ROOT else (ROOT, MAIN_ROOT)):
        try:
            return rp.relative_to(base.resolve()).as_posix()
        except Exception:
            pass
    locks = locks if locks is not None else load_locks()
    for info in locks.get("sessions", {}).values():
        wt = info.get("worktree")
        if not wt:
            continue
        try:
            wt_root = (MAIN_ROOT / wt).resolve()
            return rp.relative_to(wt_root).as_posix()
        except Exception:
            continue
    return str(p).replace("\\", "/").lstrip("./")


def _path_matches_zone(norm, zdir):
    """Does `norm` (POSIX relative path, see _repo_relative_path) fall under
    the zone `zdir` (a member already expanded by _expand_brace_glob)? Handles the
    simple prefix case (`crew/`) AND the `*` glob case (e.g. `.claude/skills/
    crew-*`, used as is by this repo in CLAUDE_BATCH.md) via fnmatch
    — best-effort, not a full glob engine."""
    zdir = zdir.rstrip("/")
    if any(ch in zdir for ch in "*?["):
        return fnmatch.fnmatchcase(norm, zdir) or fnmatch.fnmatchcase(norm, zdir + "/*")
    return norm == zdir or norm.startswith(zdir + "/")


def _path_locked_by_other(path, zones, locks=None):
    """Does `path` (raw path, absolute or relative, Windows or POSIX) fall
    under one of the `zones` (output of _locked_zones_by_others)?
    Returns (header, other_session, since) if so, otherwise None."""
    norm = _repo_relative_path(path, locks)
    for zp, header, other, since in zones:
        for expanded in _expand_brace_glob(zp):
            if _path_matches_zone(norm, expanded):
                return header, other, since
    return None


def _gate_check_path(path, session_id, locks=None, sections=None):
    """Blocks (exit 2) if `path` falls under a batch `Zone:` locked
    by ANOTHER session. Fail-open (returns silently) if no active
    zone is locked by someone else, or if the path crosses none of them —
    consistent with the 'never break the turn on ambiguity' contract of the
    rest of the hook (Layer 2 = safety net, not the only defense).
    Optional `locks`/`sections`: a caller scanning several paths
    in the same invocation (e.g. `gate_pretooluse` on a Bash command with
    several candidates) loads them once and passes them here rather
    than re-reading/re-parsing crew_lock.json/CLAUDE_BATCH.md for every path."""
    if not path:
        return
    locks = locks if locks is not None else load_locks()
    sections = sections if sections is not None else load_sections()
    zones = _locked_zones_by_others(sections, locks, session_id)
    if not zones:
        return
    hit = _path_locked_by_other(path, zones, locks)
    if not hit:
        return
    header, other, since = hit
    sys.stderr.write(
        f"[worktree-gate] `{path}` is under the Zone: of batch \"{header}\", already "
        f"locked by another session (since {since}). Potential collision — "
        "work from the worktree of your own batch (see /crew-start), or wait for "
        "the other session to finish.\n"
    )
    sys.exit(2)


def _extract_candidate_paths(command):
    """Best-effort scan (not a full shell parser, same spirit as
    `_extract_git_mv_task`): spots tokens that look like a file path
    after `rm`/`mv`/`cp`, plus any `>`/`>>` redirection target,
    in a possibly compound Bash command. Fail-open on the rest —
    Layer 2 is a safety net, not the only line of defense (see spec § Error
    handling > 'Gate false positive')."""
    norm = _tokenize_command(command)
    paths = []
    mutating = {"rm", "mv", "cp"}
    for i, tok in enumerate(norm):
        if tok.rsplit("/", 1)[-1] not in mutating:
            continue
        for arg in norm[i + 1:]:
            if arg.startswith("-"):
                continue
            if "/" in arg or "." in arg:
                paths.append(arg)
    for m in re.finditer(r">>?\s*([^\s|&;><]+)", command):
        paths.append(m.group(1).replace("\\", "/"))
    return paths


def gate_pretooluse(payload):
    """PreToolUse hook (matcher Bash|Edit|Write|MultiEdit): Layer 2 of the
    worktree-batch-isolation design (see docs/superpowers/specs/2026-08-22-worktree-
    batch-isolation-design.md) — safety net for anything that bypasses
    the physical worktree isolation (Layer 1, handled by /crew-start).

    - `Edit`/`Write`/`MultiEdit`: blocks before writing if `tool_input.file_path`
      falls under a `Zone:` locked by ANOTHER session (`_gate_check_path`).
    - `Bash`:
        1. resume marker `crew-resume:<slug>` (Case A of `/crew-start`,
           see `_claim_resume_lock`);
        2. `git mv` TODO->CURRENT_TASKS: blocks if the task is not categorized
           in any batch, or if a neighbour in its batch is already
           locked by ANOTHER session (same rule as
           check_batch_collisions at Stop);
        3. best-effort generic scan (`_extract_candidate_paths`) against the
           same locked zones, for `rm`/`mv`/`cp`/redirection.

    Preventive rather than retroactive: unlike the Stop check (which
    fires after the turn's edits have already happened), this one prevents
    the action from running. Blocks via exit(2) + stderr (standard hook
    protocol). The `crew-resume:` AND `git mv` TODO->CURRENT_TASKS paths
    both write to `crew_lock.json` (under mutex, see `_claim_resume_lock`/
    `_claim_git_mv_lock`) — needed for the `git mv` because from a batch
    worktree the Stop hook (ROOT-anchored) never sees that move (see task
    fix-worktree-gitmv-lock-registration-gap); only the generic scan
    (`rm`/`mv`/`cp`/redirection) stays read-only."""
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    session_id = payload.get("session_id")

    if tool_name in ("Edit", "Write", "MultiEdit"):
        _gate_check_path(tool_input.get("file_path"), session_id)
        return

    if tool_name != "Bash":
        return

    command = str(tool_input.get("command") or "")

    resume_slug = _extract_resume_claim(command)
    if resume_slug is not None:
        _claim_resume_lock(resume_slug, session_id)
        return

    # Loaded once for the rest of the command (git mv +
    # generic scan below) rather than re-read/re-parsed per candidate —
    # a compound command may produce several paths to check.
    sections = load_sections()
    locks = load_locks()

    slug = _extract_git_mv_task(command)
    if slug:
        section = find_section_for(slug, sections)
        if section is None:
            sys.stderr.write(
                f"[batch] `{slug}` is not categorized in any batch of CLAUDE_BATCH.md. "
                "Add it to a batch (with its Zone :) before starting it — see crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md § Batching, "
                "or dispatch the manager persona (/crew-start), which does it for you.\n"
            )
            sys.exit(2)
        reason = check_batch_collisions({slug}, sections, locks, session_id)
        if reason:
            sys.stderr.write(reason + "\n")
            sys.exit(2)
        if session_id:
            _claim_git_mv_lock(slug, session_id, sections)

    for p in _extract_candidate_paths(command):
        _gate_check_path(p, session_id, locks, sections)


def _task_slugs(*dirs):
    """Task slugs (.md excluding INDEX/README/_*) present in `dirs`."""
    return {f.name for d in dirs if d.exists() for f in d.glob("*.md")
            if f.name not in ("INDEX.md", "README.md") and not f.name.startswith("_")}


def active_task_slugs():
    """Slugs (.md files) currently in crew/TODO/, crew/CURRENT_TASKS/ or
    crew/PAUSED/ (a paused task stays blocked, not abandoned: it
    keeps its file zone for the batch anti-collision)."""
    return _task_slugs(DIRS["TODO"], DIRS["CURRENT_TASKS"], DIRS["PAUSED"])


def in_progress_task_slugs(locks, now_dt=None):
    """'Active batch' of CLAUDE.md: slugs in CURRENT_TASKS/ + PAUSED/, plus
    those held by a non-expired session (tasks started in a worktree,
    still in TODO/ here). No TODO alone, unlike active_task_slugs()."""
    slugs = _task_slugs(DIRS["CURRENT_TASKS"], DIRS["PAUSED"])
    now_dt = now_dt or datetime.datetime.now()
    for info in locks.get("sessions", {}).values():
        if not _session_expired(info, now_dt):
            slugs |= set(info.get("tasks", []) or [])
    return slugs


def purge_closed_task_locks(locks):
    """Removes from the locks the tasks closed outside the main checkout: a
    task started then closed in a worktree was never seen in
    CURRENT_TASKS/ here, so it never enters `finished` and its lock
    survived (ghost session). Alive = present in TODO/CURRENT_TASKS
    (/PAUSED) of the main checkout OR of the session's worktree. A session
    with no remaining task is removed. No-op outside the main checkout (`.git`
    file): the crew state seen from a worktree may be stale.
    Returns the sorted list of purged slugs."""
    if not (ROOT / ".git").is_dir():
        return []
    rel_dirs = [DIRS[k].relative_to(ROOT) for k in ("TODO", "CURRENT_TASKS", "PAUSED")]
    main_live = active_task_slugs()
    purged = set()
    sessions = locks.get("sessions", {})
    for sid, info in list(sessions.items()):
        live = set(main_live)
        if info.get("worktree"):
            wt = MAIN_ROOT / info["worktree"]
            for rel in rel_dirs:
                if (wt / rel).exists():
                    live |= {f.name for f in (wt / rel).glob("*.md")}
        dead = [t for t in info.get("tasks", []) if t not in live]
        if dead:
            purged.update(dead)
            info["tasks"] = [t for t in info["tasks"] if t in live]
            if not info["tasks"]:
                del sessions[sid]
    return sorted(purged)


def _expand_brace_glob(path):
    """Expands every `{a,b,c}` segment of a path into concrete paths
    (cartesian product of the members). Without a brace-glob, returns [path] unchanged."""
    m = re.search(r"\{([^{}]+)\}", path)
    if not m:
        return [path]
    expanded = [path[:m.start()] + member + path[m.end():] for member in m.group(1).split(",")]
    return [p for e in expanded for p in _expand_brace_glob(e)]


def _path_overlaps(a, b):
    """Two paths overlap if one is a prefix (per segment) of the other,
    after expanding the brace-globs (`{a,b,c}/`) on each side into concrete paths."""
    for pa in _expand_brace_glob(a):
        sa = pa.rstrip("/").split("/")
        for pb in _expand_brace_glob(b):
            sb = pb.rstrip("/").split("/")
            n = min(len(sa), len(sb))
            if sa[:n] == sb[:n]:
                return True
    return False


def _section_lock_sessions(section, locks, slug_sessions=None):
    """Sessions currently holding a live lock on at least one task of the
    section (derived from sessions[*].tasks via _slug_session_map, fed by
    the `for f in started` loop of main()). Optional `slug_sessions`: a
    caller looping over several sections (check_zone_overlaps,
    _locked_zones_by_others) computes it once and passes it here rather
    than rebuilding the full map for every section."""
    slug_sessions = slug_sessions if slug_sessions is not None else _slug_session_map(locks)
    return {slug_sessions[s] for s in section["slugs"] if s in slug_sessions}


def check_zone_overlaps(sections, active, locks, session_id=None, observer=False):
    """Detects `Zone :` overlaps between two ACTIVE batches (>=1 slug
    of `active` — the caller passes in_progress_task_slugs()). Becomes blocking
    (`blocking` list) only when the two colliding batches are
    locked by different session_ids AND the current session
    (`session_id`) is one of the two (or `observer=True`: dashboard view,
    any cross-session conflict is reported as blocking): a 3rd session foreign to the
    collision can do nothing about it, blocking it loops Stop->reinvoke. Same rules
    as check_batch_collisions, so as NOT to block a solo session that
    works sequentially on two batches with neighbouring zones (neither
    is then locked by ANOTHER session).
    Otherwise stays a non-blocking warning: automated safeguard
    complementing the manager's manual check before starting."""
    warnings = []
    blocking = []
    slug_sessions = _slug_session_map(locks)
    active_sections = [s for s in sections if s["slugs"] & active and s["zone_paths"]]
    for i, sec_a in enumerate(active_sections):
        sessions_a = _section_lock_sessions(sec_a, locks, slug_sessions)
        for sec_b in active_sections[i + 1:]:
            sessions_b = _section_lock_sessions(sec_b, locks, slug_sessions)
            cross_session = bool(sessions_a) and bool(sessions_b) and sessions_a != sessions_b
            involved = observer or session_id in sessions_a or session_id in sessions_b
            for pa in sec_a["zone_paths"]:
                for pb in sec_b["zone_paths"]:
                    if not _path_overlaps(pa, pb):
                        continue
                    base = (f"[zone] Overlap detected between active batches \"{sec_a['header']}\" "
                            f"and \"{sec_b['header']}\": `{pa}` vs `{pb}`.")
                    if cross_session and involved:
                        blocking.append(base + " Locked by different sessions — "
                                         "wait for one to finish before continuing the other.")
                    else:
                        warnings.append(base + " Check CLAUDE_BATCH.md before starting a "
                                         "task of either one (risk of file collision).")
    return warnings, blocking


CONTEXT_BUDGET_TOKENS = 150_000
CONTEXT_REPEAT_STEP = 50_000


def _iter_lines_reverse(path, chunk_size=65536):
    """Yields the lines of a text file starting from the end, without
    loading it entirely into memory. The transcript grows every turn;
    what we look for (the last assistant message) is almost always very
    close to the end, so reading from the end keeps the cost proportional to the
    distance to that message, not to the total size of the transcript."""
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        pos = fh.tell()
        carry = b""
        while pos > 0:
            read_size = min(chunk_size, pos)
            pos -= read_size
            fh.seek(pos)
            chunk = fh.read(read_size) + carry
            lines = chunk.split(b"\n")
            carry = lines[0]
            for line in reversed(lines[1:]):
                yield line
        if carry:
            yield carry


def check_context_budget(payload, state=None):
    """Warns (non-blocking) when the main session's context
    exceeds ~150k tokens, whatever the window size (see
    crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md § Context efficiency / Reset de session). No dedicated token-counting API
    is exposed to Claude Code hooks: approximated via the last
    assistant message of the transcript (`transcript_path` of the Stop payload) —
    usage.input_tokens + cache_read_input_tokens + cache_creation_input_tokens,
    a reasonable proxy since every turn sends the full history as
    input. Single threshold (200k or 1M window: quality degrades before the
    limit). `state` ({session_id -> total at the last
    warning}, mutated in place) limits repetition to a step of
    CONTEXT_REPEAT_STEP tokens; going back under the threshold (/clear, compaction)
    -> entry purged, warns again at the next crossing. state=None ->
    no memory (a warning on every call above the threshold).
    Best-effort: any error (missing transcript, unexpected format, corrupted
    line) -> no warning."""
    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return []
    path = pathlib.Path(transcript_path)
    if not path.exists():
        return []
    try:
        last_usage = None
        for raw_line in _iter_lines_reverse(path):
            line = raw_line.strip()
            if not line:
                continue
            entry = json.loads(line)
            msg = entry.get("message") or {}
            if msg.get("role") == "assistant" and msg.get("usage"):
                last_usage = msg["usage"]
                break
    except Exception:
        return []
    if not last_usage:
        return []
    total = (
        (last_usage.get("input_tokens") or 0)
        + (last_usage.get("cache_read_input_tokens") or 0)
        + (last_usage.get("cache_creation_input_tokens") or 0)
    )
    sid = str(payload.get("session_id"))
    if total <= CONTEXT_BUDGET_TOKENS:
        if state is not None:
            state.pop(sid, None)
        return []
    if state is not None:
        last = state.get(sid)
        if isinstance(last, int) and total < last + CONTEXT_REPEAT_STEP:
            return []
        state[sid] = total
    return [
        f"[context] ~{total:,} estimated context tokens (threshold "
        f"{CONTEXT_BUDGET_TOKENS:,}) — /clear or a new session "
        "recommended before continuing (see crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md "
        "§ Context efficiency)."
    ]


def regen_batch_locks_md(sections, locks, active):
    """Regenerates crew/CLAUDE_CONTEXT/BATCH_LOCKS.md: one entry per batch
    section having at least one task currently in TODO/, CURRENT_TASKS/ or
    PAUSED/. `worktree` column shown when the session entry carries one.
    No-op outside the main checkout: a worktree's view may be stale."""
    if ROOT != MAIN_ROOT:
        return
    lines = ["# Batch locks (real time)\n\n",
              "> Regenerated automatically by `crew/crew_hook.py` every turn. "
              "Do not edit by hand.\n\n"]
    slug_sessions = _slug_session_map(locks)
    sessions = locks.get("sessions", {})
    any_section = False
    for section in sections:
        relevant = sorted(section["slugs"] & active)
        if not relevant:
            continue
        any_section = True
        lines.append(f"## {section['header']}\n\n")
        for slug in relevant:
            sid = slug_sessions.get(slug)
            if sid:
                info = sessions.get(sid, {})
                try:
                    since_fmt = datetime.datetime.fromisoformat(info.get("since", "")).strftime("%H:%M")
                except Exception:
                    since_fmt = info.get("since", "?")
                worktree = info.get("worktree")
                suffix = f", worktree `{worktree}`" if worktree else ""
                lines.append(f"- 🔒 `{slug}` — locked (session `{sid}`, since {since_fmt}{suffix})\n")
            else:
                lines.append(f"- 🔓 `{slug}` — free\n")
        lines.append("\n")
    if not any_section:
        lines.append("_No active batch with a task in TODO/CURRENT_TASKS/PAUSED for now._\n")
    BATCH_LOCKS_MD.write_text("".join(lines), encoding="utf-8")


def _git_tracked(rel):
    r = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel],
                        cwd=str(ROOT), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return r.returncode == 0


def _git_ignored(rel):
    r = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=str(ROOT),
                       stdin=subprocess.DEVNULL, capture_output=True)
    return r.returncode == 0


def _closure_commit_scope(slug):
    """crew/ paths (relative to ROOT, POSIX) to include in the automatic
    closure commit for `slug` (without the `.md` extension): the CURRENT_TASKS file
    that disappeared, HISTORIQUE.md, the extracted tests (IA/DEV, if they exist), and
    all INDEX.md + CLAUDE_BATCH.md + BATCH_LOCKS.md + CHANGELOG_TACHES.md
    regenerated by the hook in the same pass. Only returns paths that
    `git add` will actually accept:
    - already tracked by git -> always included (covers a deletion
      to stage, even if the file no longer exists on disk);
    - never tracked but absent -> excluded (a `git add` on it would fail with
      'did not match any files');
    - never tracked, present on disk, but gitignored (e.g.
      `crew/CLAUDE_CONTEXT/BATCH_LOCKS.md`, regenerated every turn but
      never meant to be committed — an explicit `git add` on it is
      refused by git) -> excluded."""
    candidates = [
        DIRS["CURRENT_TASKS"] / f"{slug}.md",
        CTX / "HISTORIQUE.md",
        HISTORIQUE_ARCHIVE,
        DIRS["TESTS/IA"] / f"{slug}.md",
        DIRS["TESTS/DEV"] / f"{slug}.md",
        BATCH_FILE,
        CHANGELOG,
        BATCH_LOCKS_MD,
    ]
    for d in DIRS.values():
        candidates.append(d / "INDEX.md")
    paths = []
    for p in candidates:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if _git_tracked(rel):
            paths.append(rel)
            continue
        if not p.exists():
            continue
        if _git_ignored(rel):
            continue
        paths.append(rel)
    return sorted(set(paths))


def auto_commit_closure(finished, now_dt):
    """LOCAL-ONLY git commit (never a push) scoped to crew/, triggered
    per slug actually closed: a slug of `finished` (gone from
    CURRENT_TASKS/ this turn) is only kept if it has a matching entry
    in the (uncommitted) diff of HISTORIQUE.md — not just "the file
    changed somewhere" (covers the case where 2 tasks finish the same turn
    but only one has a real entry, and the case where `finished` is non-empty
    without any real history entry, e.g. manual deletion of the file).
    Idempotent by construction: nothing NEW on the computed scope ->
    no commit (checked via `git diff --cached` restricted to the scope, not
    the whole index). Commit SCOPED to the
    pathspec (`git commit -- <paths>`) rather than a bare `git commit`: never
    touches a user change already staged elsewhere in the
    repo at hook time, even if `git add` left it in the index before
    this commit — this is exactly the incident (ProjetA) this task
    fixes. Never breaks the turn: any error (git missing, rejecting
    pre-commit hook, etc.) is logged on stderr and swallowed, never
    raised — same contract as the rest of the hook."""
    if not finished:
        return
    paths = []
    try:
        histo_rel = str((CTX / "HISTORIQUE.md").relative_to(ROOT)).replace("\\", "/")
        diff_text = (
            subprocess.run(["git", "diff", "--", histo_rel], cwd=str(ROOT),
                            capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
            + subprocess.run(["git", "diff", "--cached", "--", histo_rel], cwd=str(ROOT),
                              capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
        )
        all_slugs = sorted(f[:-3] if f.endswith(".md") else f for f in finished)
        # Only keep the slugs that really have a matching entry
        # in the HISTORIQUE.md diff (not just "the file changed somewhere"):
        # if 2 tasks finish the same turn and only one has a
        # real entry, the other is not included in this commit.
        slugs = [s for s in all_slugs if s in diff_text]
        if not slugs:
            return  # no finished slug has a matching entry in HISTORIQUE.md
        paths = sorted({p for slug in slugs for p in _closure_commit_scope(slug)})
        if not paths:
            return
        subprocess.run(["git", "add", "--"] + paths, cwd=str(ROOT), check=True,
                        capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if subprocess.run(["git", "diff", "--cached", "--quiet", "--"] + paths,
                           cwd=str(ROOT), stdin=subprocess.DEVNULL, capture_output=True).returncode == 0:
            return  # nothing really new on THIS scope -> already committed (idempotence)
        msg = "chore(crew): close task " + ", ".join(slugs)
        subprocess.run(["git", "commit", "-m", msg, "--"] + paths, cwd=str(ROOT),
                        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except Exception as e:
        sys.stderr.write(f"[auto-commit] closure commit not made (non-blocking): {e}\n")
        # Best-effort: if `git add` partially succeeded before the failure
        # (e.g. an invalid path of the scope further down the list), do not
        # leave those paths staged for the user — unstage only
        # OUR scope, never the rest of the index (same guarantees as the
        # commit itself).
        if paths:
            try:
                subprocess.run(["git", "reset", "--"] + paths, cwd=str(ROOT), capture_output=True, stdin=subprocess.DEVNULL)
            except Exception:
                pass


DIGEST_CAP = 2000
DIGEST_LINE_MAX = 160
_CHECKBOX_RE = re.compile(r"^[ \t]*[-*]\s*\[( |x|X)\]", re.MULTILINE)


def build_session_digest(current, paused, batches, other_locks, warnings, history, cap=DIGEST_CAP, remote=()):
    """Crew digest <= `cap` characters (pure function). Fixed order: CURRENT_TASKS,
    PAUSED, active batches, locks of other sessions, warnings, HISTORIQUE. When
    a line no longer fits, everything else is replaced by "… (+N)": the
    leading sections are therefore never sacrificed in favour of the following ones."""
    items = [
        "[%s] %s — %s (%d/%d)" % (tag, slug, title, done, total)
        for tag, rows in (("in progress", current), ("paused", paused))
        for slug, title, done, total in rows
    ]
    items += ["[active batch] %s — Zone : %s" % (header, zone) for header, zone in batches]
    items += ["[lock] %s" % lock for lock in other_locks]
    items += ["[remote] %s" % r for r in remote]
    items += list(warnings)
    items += ["[history] %s" % t for t in history]
    if not items:
        return "crew: no task in progress or paused."
    items = [i if len(i) <= DIGEST_LINE_MAX else i[:DIGEST_LINE_MAX - 1] + "…" for i in items]
    lines = ["Crew digest (derived view — check the file before writing):"] + items
    dropped = 0
    while len("\n".join(lines)) > cap and len(lines) > 1:
        lines.pop()
        dropped += 1
    if dropped:
        # the marker replaces at least the last kept line if it does not fit
        while len("\n".join(lines + ["… (+%d)" % dropped])) > cap and len(lines) > 1:
            lines.pop()
            dropped += 1
        lines.append("… (+%d)" % dropped)
    return "\n".join(lines)[:cap]


def _digest_task_rows(d):
    """(file, title, checked boxes, total boxes) per task, in a single read."""
    rows = []
    for f in sorted(d.glob("*.md")) if d.exists() else []:
        if f.name in ("INDEX.md", "README.md") or f.name.startswith("_"):
            continue
        text = f.read_text(encoding="utf-8")
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), f.stem)
        marks = _CHECKBOX_RE.findall(text)
        rows.append((f.name, title, sum(1 for m in marks if m != " "), len(marks)))
    return rows


def _safe(fn, default):
    """An unreadable source must not kill the whole digest: fall back to `default`."""
    try:
        return fn()
    except Exception:
        return default


def _digest_batches(active):
    return [
        (_batch_key(sec["header"]), ", ".join(sorted(sec["zone_paths"])) or "?")
        for sec in load_sections() if sec["slugs"] & active
    ]


def _digest_locks(session_id):
    now_dt = datetime.datetime.now()
    out = []
    for sid, info in sorted(load_locks().get("sessions", {}).items()):
        if sid == session_id or _session_expired(info, now_dt):
            continue
        tasks = info.get("tasks")
        out.append("%s: %s" % (str(sid)[:8], ", ".join(tasks) if isinstance(tasks, list) else "?"))
    return out


def _digest_history(n=3):
    # HISTORIQUE.md is sorted from most recent to oldest: stop at the n-th title.
    titles = []
    with open(HISTORIQUE, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("## "):
                titles.append(line[3:].strip())
                if len(titles) == n:
                    break
    return titles


def _digest_remote_claims():
    """One line per open task published by a dev (local ref, NO network),
    excluding tasks already present in crew/ here. The texts have already been reduced to
    one line by `_claims_clean`."""
    if not claims_enabled():
        return []
    local = active_task_slugs()
    rows = [(s, e) for s, e in sorted(_claims_expire(_claims_local()[1], _claims_now()).items()) if s not in local]
    if not rows:
        return []                                   # common case: no identity git spawn
    me = _claims_identity()
    return ["%s — %s (%s)" % (s, (e.get("title") or "?")[:80],
                              "me" if e.get("owner") == me else (e.get("owner") or e.get("author") or "?")[:40])
            for s, e in rows]


def session_digest(session_id):
    """Reads crew/ (read-only: no write, no save_locks) and renders the
    digest; None if the project has no crew/ (nothing to inject)."""
    if not CREW.is_dir():
        return None
    current = _safe(lambda: _digest_task_rows(DIRS["CURRENT_TASKS"]), [])
    paused = _safe(lambda: _digest_task_rows(DIRS["PAUSED"]), [])
    active = {r[0] for r in current + paused}
    return build_session_digest(
        current, paused,
        _safe(lambda: _digest_batches(active), []),
        _safe(lambda: _digest_locks(session_id), []),
        _safe(check_batches, []),
        _safe(_digest_history, []),
        remote=_safe(_digest_remote_claims, []),
    )


SESSION_COLORS = ("🔴 red", "🟠 orange", "🟡 yellow", "🟢 green", "🔵 blue", "🟣 purple", "🟤 brown")


def session_color(session_id):
    """Stable dot + colour name for a session (sessionTitle fallback
    when no single task names it); tells sessions apart at a glance."""
    h = hashlib.sha1(str(session_id).encode("utf-8")).digest()
    return SESSION_COLORS[h[0] % len(SESSION_COLORS)]


def session_title(session_id, payload):
    """Title (task slug) for the SessionStart `sessionTitle`; None if
    the session is already named, if the source is not startup/resume/fork, or if
    the task is ambiguous. This session's lock first, otherwise the only task in
    CURRENT_TASKS not locked by another session. Read-only."""
    if payload.get("session_title") or payload.get("source") not in ("startup", "resume", "fork", "clear"):
        return None
    now_dt = datetime.datetime.now()
    sessions = load_locks().get("sessions", {})
    names = [n for n in sessions.get(session_id, {}).get("tasks") or [] if isinstance(n, str)]
    if not names:
        taken = {t for sid, info in sessions.items()
                 if sid != session_id and not _session_expired(info, now_dt)
                 for t in info.get("tasks") or []}
        names = [n for n in _task_names(DIRS["CURRENT_TASKS"]) if n not in taken]
    return names[0].removesuffix(".md") if len(names) == 1 else session_color(session_id)


def _task_names(d):
    return [f.name for f in sorted(d.glob("*.md"))
            if d.exists() and f.name not in ("INDEX.md", "README.md") and not f.name.startswith("_")]


def _read_ignored():
    """{slug: owner | None} from crew_ignored.json; missing/corrupt -> {}.
    The older format (list + a single `owner`) is still read."""
    try:
        data = json.loads(IGNORED_FILE.read_text(encoding="utf-8"))
        raw = data.get("ignored", {})
        if isinstance(raw, list):
            owner = data.get("owner") if isinstance(data.get("owner"), str) and data.get("owner") else None
            return {x: owner for x in raw if isinstance(x, str)}
        return {k: (v if isinstance(v, str) and v else None) for k, v in raw.items() if isinstance(k, str)}
    except Exception:
        return {}


def load_ignored():
    """`.md` slugs skipped by `next_task`."""
    return set(_read_ignored())


def _valid_person_name(name):
    """Name safe for a config line, a claim and a shell argument: 1-60 chars
    (letters, digits, space, `.` `@` `-` `_`), single line."""
    return isinstance(name, str) and re.fullmatch(r"[\w .@-]{1,60}", name.strip()) is not None


def _opts(argv, known):
    """(known `--key value` options, positionals); an unknown option or one without a value -> ValueError."""
    opts, pos, i = {}, [], 0
    while i < len(argv):
        if argv[i].startswith("--"):
            if argv[i][2:] not in known or i + 1 >= len(argv):
                raise ValueError(f"invalid option: {argv[i]}")
            opts[argv[i][2:]], i = argv[i + 1], i + 2
        else:
            pos.append(argv[i])
            i += 1
    return opts, pos


_OWNER_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\**\s*(?:owner|assigned(?:\s+to)?|assign[ée]e?(?:\s+[àa])?|claimed?(?:\s+by)?|responsible|responsable)\s*\**\s*:\s*\**\s*(.+?)\s*\**\s*$",
    re.IGNORECASE)
_UNASSIGNED = "(unassigned)"


def _todo_owner_mention(slug):
    """Name written in the TODO file (`Owner: x`, `Assigned to: x`, `Claimed by: x`, `Responsible: x`,
    French aliases `Assigné à` / `Responsable` accepted; first 40 lines); None if there is no mention."""
    try:
        with open(DIRS["TODO"] / slug, encoding="utf-8-sig") as fh:
            for _ in range(40):
                line = fh.readline()
                if not line:
                    break
                m = _OWNER_LINE_RE.match(line)
                if m and _valid_person_name(m.group(1)):
                    return m.group(1).strip()
    except OSError:
        pass
    return None


def _collab_name():
    return _claims_config().get("collab_name", "").strip() or None


def _same_person(a, b):
    return bool(a) and bool(b) and a.strip().casefold() == b.strip().casefold()


def _by_owner(store):
    out = {}
    for who in store.values():
        out[who or _UNASSIGNED] = out.get(who or _UNASSIGNED, 0) + 1
    return out


def ignore_cli(argv):
    """`crew_hook.py ignore <snapshot [--owner <name>]|add <slug> [--owner <name>]|remove <slug>|list|off>`:
    local list of TODO tasks that `/crew-start` must not start, with their owner (a teammate's tasks
    brought in by a pull). `snapshot` assigns every TODO present: a mention in the file, else a remote
    claim, else `--owner`; with none of the three it is set aside anyway as "unassigned" (listed in
    `unmarked`). Tasks marked with your own name are never ignored. `off` deletes the list."""
    usage = {"ok": False, "reason": "usage: ignore snapshot [--owner <name>]|add <slug> [--owner <name>]|remove <slug>|list|off"}
    try:
        opts, slugs = _opts(argv[1:], {"owner"}) if argv else ({}, [])
    except ValueError as e:
        return {"ok": False, "reason": str(e)}
    sub = argv[0] if argv else None
    if sub not in ("snapshot", "add", "remove", "list", "off"):
        return usage
    if "owner" in opts and not _valid_person_name(opts["owner"]):
        return {"ok": False, "reason": "invalid --owner (1-60 chars: letters, digits, space . @ - _)"}
    if sub in ("add", "remove") and not slugs:
        return {"ok": False, "reason": f"`ignore {sub}`: slug required"}
    slugs = [x if x.endswith(".md") else x + ".md" for x in slugs]
    if sub == "off":
        try:
            IGNORED_FILE.unlink()
        except FileNotFoundError:
            pass
        return {"ok": True, "ignored": [], "by_owner": {}}
    before = _read_ignored()
    store, owner = dict(before), opts.get("owner", "").strip() or None
    if sub == "snapshot":
        me = _collab_name()
        claims = _claims_local()[1] if claims_enabled() else {}
        for slug in _task_names(DIRS["TODO"]):
            if store.get(slug):
                continue
            c = claims.get(slug) or {}
            who = _todo_owner_mention(slug) or c.get("owner") or c.get("author")
            if _same_person(who, me):
                continue  # it is mine
            store[slug] = who or owner  # no known owner: still ignored ("unassigned"), never started
    elif sub == "add":
        for slug in slugs:
            store[slug] = owner or store.get(slug)
    elif sub == "remove":
        for slug in slugs:
            store.pop(slug, None)
    if store != before:
        IGNORED_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = IGNORED_FILE.with_name(IGNORED_FILE.name + ".tmp")
        tmp.write_text(json.dumps({"ignored": dict(sorted(store.items()))}, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, IGNORED_FILE)
    out = {"ok": True, "ignored": sorted(store), "added": sorted(set(store) - set(before)), "by_owner": _by_owner(store)}
    if sub == "snapshot":
        out["unmarked"] = sorted(t for t, who in store.items() if not who)
    return out


def next_task(session_id):
    """Deterministic task choice for `/crew-start` (read-only: neither
    lock nor move — the skill sets them afterwards via the `crew-resume:` marker
    or the `git mv`, which gate_pretooluse checks under mutex).
    Returns a dict `action` in {resume, start, classify, none} + `task`,
    `batch`, `worktree`, `branch` when applicable, `skipped` [{slug, reason}]
    for every candidate set aside, `paused`, `unclassified` (TODO tasks in no
    batch) and `ambiguous` (ties on resume)."""
    sections = load_sections()
    locks = load_locks()
    now_dt = datetime.datetime.now()
    locks = {"sessions": {sid: i for sid, i in locks.get("sessions", {}).items() if not _session_expired(i, now_dt)}}
    owners = _slug_session_map(locks)
    rows = _digest_task_rows(DIRS["CURRENT_TASKS"])
    current = [r[0] for r in rows]
    paused = _task_names(DIRS["PAUSED"])
    ignored = _read_ignored()
    todo_all = _task_names(DIRS["TODO"])
    todo = [t for t in todo_all if t not in ignored]
    skipped = [{"slug": t, "reason": f"ignored locally (task of {ignored[t]})" if ignored[t]
                else "ignored locally (another dev's task)"}
               for t in todo_all if t in ignored]
    out = {"action": "none", "paused": paused, "skipped": skipped,
           "unclassified": [t for t in todo if find_section_for(t, sections) is None]}

    remote = {}  # active claims of OTHER devs (opt-in remote_claims); empty otherwise
    if claims_enabled():
        warning, remote, remote_todo = claims_remote_view()
        if warning:
            out["claims_warning"] = warning
        if remote_todo:
            out["remote_todo"] = remote_todo

    mine = []
    for name, _title, done, _total in rows:
        owner = owners.get(name)
        if owner and owner != session_id:
            skipped.append({"slug": name, "reason": f"lock: picked up by session {str(owner)[:8]}"})
        elif name in remote:
            skipped.append({"slug": name, "reason": f"remote claim: {remote[name]['owner']}"})
        else:
            mine.append((done, name))
    if mine:
        best = max(d for d, _ in mine)
        tied = sorted(n for d, n in mine if d == best)
        out.update(action="resume", task=tied[0])
        if len(tied) > 1:
            out["ambiguous"] = tied
        sec = find_section_for(tied[0], sections)
        if sec:
            out["batch"] = _batch_key(sec["header"])
            out["zone"] = sorted(sec["zone_paths"])
            out["worktree"], out["branch"] = _worktree_paths_for(sec["header"])
        return out

    held = set(current) | set(paused)
    active = [s for s in sections if s["slugs"] & held or _section_lock_sessions(s, locks, owners) - {session_id}]
    for sec in sections:
        cands = [t for t in sec["ordered"] if t in todo]
        if not cands:
            continue
        if sec in active:
            skipped += [{"slug": t, "reason": f"active batch: {_batch_key(sec['header'])}"} for t in cands]
            continue
        if not sec["zone_paths"]:
            skipped += [{"slug": t, "reason": f"unknown zone: {_batch_key(sec['header'])}"} for t in cands]
            continue
        sec_claims = sec["slugs"] & set(remote)
        if sec_claims:
            first_owner = remote[sorted(sec_claims)[0]]["owner"]
            skipped += [{"slug": t, "reason": f"remote claim: {remote[t]['owner']}" if t in remote
                         else f"active batch (remote claim: {first_owner})"} for t in cands]
            continue
        rclash = next(((s, e) for s, e in remote.items()
                       if _claims_zone_clash(sec["zone_paths"], e.get("zone"))), None)
        if rclash:
            skipped += [{"slug": t, "reason": f"remote claim: zone overlaps {rclash[0]} ({rclash[1]['owner']})"}
                        for t in cands]
            continue
        clash = next((a for a in active if any(_path_overlaps(x, y) for x in sec["zone_paths"] for y in a["zone_paths"])), None)
        if clash:
            skipped += [{"slug": t, "reason": f"zone overlaps the active batch {_batch_key(clash['header'])}"} for t in cands]
            continue
        out.update(action="start", task=cands[0], batch=_batch_key(sec["header"]), zone=sorted(sec["zone_paths"]))
        out["worktree"], out["branch"] = _worktree_paths_for(sec["header"])
        return out
    if out["unclassified"]:
        out["action"] = "classify"
    return out


def _zones_overlap(a, b):
    """First pair of paths that overlap between two sections (or None)."""
    return next(((x, y) for x in a["zone_paths"] for y in b["zone_paths"] if _path_overlaps(x, y)), None)


def _is_placeholder_section(sec):
    return "<" in sec["header"] or any("<" in z for z in sec["zone_paths"])


def count_batches():
    """Read-only report for `/crew-count`: active batches, launchable in
    parallel (zones disjoint from the active ones AND from each other, file order =
    priority), excluded (overlap). A batch with no remaining task (all
    struck through) or with a template placeholder is ignored (the latter is reported)."""
    held = set(_task_names(DIRS["CURRENT_TASKS"])) | set(_task_names(DIRS["PAUSED"]))
    active, launchable, excluded, placeholders = [], [], [], []
    secs = []
    for sec in load_sections():
        if _is_placeholder_section(sec):
            placeholders.append(_batch_key(sec["header"]))
            continue
        remaining = [t for t in sec["ordered"] if t not in sec["struck"]]
        if remaining:
            secs.append((sec, remaining))
    info = lambda sec, rem: {"name": _batch_key(sec["header"]), "zone": sorted(sec["zone_paths"]), "remaining": len(rem),
                                  "task": rem[0].removesuffix(".md")}
    taken = []  # active then launchable sections kept, in order
    for sec, rem in secs:
        if set(rem) & held:
            active.append(info(sec, rem))
            taken.append(sec)
    for sec, rem in secs:
        if set(rem) & held:
            continue
        clash = next(((o, _zones_overlap(sec, o)) for o in taken if _zones_overlap(sec, o)), None)
        if not sec["zone_paths"]:
            excluded.append({**info(sec, rem), "reason": "unknown zone"})
        elif clash:
            o, (x, y) = clash
            excluded.append({**info(sec, rem), "reason": f"overlaps {_batch_key(o['header'])} ({x} / {y})"})
        else:
            launchable.append(info(sec, rem))
            taken.append(sec)
    return {"launchable_count": len(launchable), "launchable": launchable, "active": active,
            "excluded": excluded, "placeholders": placeholders,
            "report": _count_report(launchable, active, excluded, placeholders)}


def _count_report(launchable, active, excluded, placeholders):
    """Compact text rendering of `/crew-count`: number of terminals and, per terminal,
    the session title (= slug of the batch's next task)."""
    n = len(launchable)
    if n:
        lines = [f"**{n} {'terminals' if n > 1 else 'terminal'} in parallel**", "",
                 "| Session title | Batch | Zone |", "|---|---|---|"]
        lines += [f"| `{b['task']}` | {b['name']} | {', '.join(b['zone'])} |" for b in launchable]
    else:
        why = "all active" if active else "nothing launchable (closed batches, 'A classer' or conflicting zones)"
        lines = [f"**0 terminals**: {why}"]
    if active:
        lines.append("Active: " + ", ".join(b["name"] for b in active))
    if excluded:
        lines.append("Excluded: " + " ; ".join(f"{b['name']} ({b['reason']})" for b in excluded))
    if placeholders:
        lines.append("Unresolved placeholder, ignored: " + ", ".join(placeholders))
    return "\n".join(lines)


def _orphan_worktrees(locks):
    """`*-batch-*` worktrees present on disk with no session carrying them."""
    try:
        out = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=str(MAIN_ROOT),
                             capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL).stdout
    except Exception:
        return []
    norm = lambda x: str(pathlib.Path(x).resolve()).replace("\\", "/").lower()
    known = {norm(MAIN_ROOT / i["worktree"]) for i in locks.get("sessions", {}).values() if i.get("worktree")}
    paths = [l[len("worktree "):].strip() for l in out.splitlines() if l.startswith("worktree ")]
    return [w for w in paths if "-batch-" in pathlib.Path(w).name and norm(w) not in known]


def crew_status():
    """Read-only report for `/crew-status`."""
    sections = [s for s in load_sections() if not _is_placeholder_section(s)]
    current = _digest_task_rows(DIRS["CURRENT_TASKS"])
    paused = _task_names(DIRS["PAUSED"])
    held = {r[0] for r in current} | set(paused)
    active = [s for s in sections if s["slugs"] & held]
    overlaps = []
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            hit = _zones_overlap(a, b)
            if hit:
                overlaps.append({"batches": [_batch_key(a["header"]), _batch_key(b["header"])], "paths": list(hit)})
    tests = []
    for f in sorted(DIRS["TESTS/IA"].glob("*.md")) if DIRS["TESTS/IA"].exists() else []:
        if f.name in ("INDEX.md", "README.md"):
            continue
        n = sum(1 for m in _CHECKBOX_RE.findall(f.read_text(encoding="utf-8")) if m == " ")
        if n:
            tests.append({"file": f.name, "unchecked": n})
    return {
        "active_batches": [{"name": _batch_key(s["header"]), "zone": sorted(s["zone_paths"])} for s in active],
        "zone_overlaps": overlaps,
        "current": [{"slug": r[0], "done": r[2], "total": r[3]} for r in current],
        "paused": paused,
        "tests_ia_unchecked": tests,
        "todo_orphans": [t for t in _task_names(DIRS["TODO"]) if find_section_for(t, sections) is None],
        "bootstrap_pending": (ROOT / "check_placeholders.py").exists(),
        "orphan_worktrees": _orphan_worktrees(load_locks()),
    }


# --- Remote claims: git ref `refs/crew/claims` (multi-dev sync) -------------
# Shared layer "who does what + open tasks", pushed ALONE (never on
# main). The crew/ folders remain the truth of the task state. The claim is
# a compare-and-swap: `push --force-with-lease=<ref>:<tip>` only overwrites the ref
# if it still equals the tip we based ourselves on. Opt-in via CREW_CONFIG.md
# (`remote_claims : true`). Never called from a hook (no network in
# PreToolUse): only `claims ...` and `next-task`, launched by the skills.
CLAIMS_REF = "refs/crew/claims"
CLAIMS_FILE = "claims.json"
CLAIMS_CONFIG = "CREW_CONFIG.md"
CLAIMS_TTL = datetime.timedelta(hours=8)
CLAIMS_RETRIES = 3
CLAIMS_GIT_TIMEOUT_SEC = 20
_CLAIMS_GIT_ENV = {"LC_ALL": "C", "LANGUAGE": "C", "GIT_TERMINAL_PROMPT": "0"}  # stable git messages, never a prompt
_CLAIMS_SLUG_RE = re.compile(r"[A-Za-z0-9][\w.-]*\.md")
_CLAIMS_REF_RE = re.compile(r"refs/crew/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*|refs/heads/crew-[A-Za-z0-9_-]+")
_CLAIMS_REMOTE_RE = re.compile(r"[A-Za-z0-9_][\w.@:/~-]*")
# Stop words of French and English task titles (matching data: keep the French words)
_CLAIMS_STOPWORDS = {"des", "les", "une", "pour", "avec", "dans", "sur", "the", "and", "for", "ajouter",
                     "creer", "faire", "tache", "task", "mise", "jour"}


def _claims_now():
    """Current time in UTC (aware): a TTL must stay correct between devs in different time zones."""
    return datetime.datetime.now(datetime.timezone.utc)


def _claims_config():
    out = {}
    try:
        for line in (CTX / CLAIMS_CONFIG).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Za-z_][\w-]*)\s*[:=]\s*(.*?)\s*$", line)
            if m:
                out[m.group(1)] = m.group(2)
    except Exception:
        pass
    return out


def claims_enabled():
    return _claims_config().get("remote_claims", "").strip().lower() in ("true", "1", "yes", "oui", "on")


def _claims_git(*args, input_bytes=None, env=None):
    """(returncode, stdout, stderr); never raises (git missing, timeout...)."""
    try:
        r = subprocess.run(["git", *args], cwd=str(ROOT), input=input_bytes, capture_output=True,
                           stdin=None if input_bytes is not None else subprocess.DEVNULL,
                           timeout=CLAIMS_GIT_TIMEOUT_SEC, env={**os.environ, **_CLAIMS_GIT_ENV, **(env or {})})
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except Exception as e:
        return 1, "", str(e)


_CLAIMS_ID_CACHE = {}


def _claims_identity():
    """Name chosen via `/crew-collab` (config `collab_name`), else the checkout's
    user.email (memoised per root: one git spawn per process)."""
    name = _claims_config().get("collab_name", "").strip()
    if name:
        return name
    key = str(ROOT)
    if key not in _CLAIMS_ID_CACHE:
        rc, out, _ = _claims_git("config", "user.email")
        _CLAIMS_ID_CACHE[key] = out.strip() if rc == 0 and out.strip() else \
            (os.environ.get("USERNAME") or os.environ.get("USER") or "unknown") + "@local"
    return _CLAIMS_ID_CACHE[key]


def _claims_valid_slug(slug):
    return isinstance(slug, str) and ".." not in slug and _CLAIMS_SLUG_RE.fullmatch(slug) is not None


_CLAIMS_STR_FIELDS = (("owner", 200), ("author", 200), ("session", 200), ("batch", 200), ("branch", 200), ("title", 300))


def _claims_str(value, cap=500):
    """Text from someone else: a single line (no fake multi-line instruction) and capped."""
    return re.sub(r"\s+", " ", value).strip()[:cap] if isinstance(value, str) else None


def _claims_clean(data):
    """Normalizes the remote ref: this is data from OTHER devs, hence untrusted.
    Invalid keys (path traversal...) and non-dict entries discarded; types forced;
    unreadable `ts` -> None (the claim then never expires: visible, to be released by hand)."""
    out = {}
    for slug, e in (data or {}).items():
        if not _claims_valid_slug(slug) or not isinstance(e, dict):
            continue
        zone = e.get("zone")
        ts = _claims_parse_ts(e.get("ts")) if isinstance(e.get("ts"), str) else None
        out[slug] = {
            "status": "current" if e.get("status") == "current" else "todo",
            **{k: _claims_str(e.get(k), cap) for k, cap in _CLAIMS_STR_FIELDS},
            "body": e.get("body") if isinstance(e.get("body"), str) else None,
            "zone": [z[:300] for z in zone if isinstance(z, str)] if isinstance(zone, list) else [],
            "ts": ts.isoformat(timespec="seconds") if ts else None}
    return out


def _claims_local():
    """(tip, tasks) read from the local ref — no network."""
    rc, out, _ = _claims_git("rev-parse", "--verify", "-q", _claims_ref())
    if rc != 0 or not out.strip():
        return None, {}
    tip = out.strip()
    rc, blob, _ = _claims_git("show", f"{tip}:{CLAIMS_FILE}")
    try:
        data = json.loads(blob) if rc == 0 else {}
    except Exception:
        data = {}
    return tip, _claims_clean(data if isinstance(data, dict) else {})


def claims_fetch():
    """Fetches the remote ref. {ok, offline, tasks, tip}. Offline: ok False,
    tasks/tip = last local view (stale information, never blocking)."""
    ref = _claims_ref()
    rc, _, err = _claims_git("fetch", "--quiet", _claims_remote(), f"+{ref}:{ref}")
    if rc != 0:
        if "couldn't find remote ref" in err or "could not find remote ref" in err:
            return {"ok": True, "offline": False, "tasks": {}, "tip": None}  # nobody has published anything yet
        tip, tasks = _claims_local()
        return {"ok": False, "offline": True, "tasks": tasks, "tip": tip}
    tip, tasks = _claims_local()
    return {"ok": True, "offline": False, "tasks": tasks, "tip": tip}


def _claims_ref():
    """Ref carrying the claims. `claims_ref` (CREW_CONFIG.md) allows falling back to a `refs/heads/crew-*`
    branch if the server rejects custom refs. Confined to `refs/crew/*` or
    `refs/heads/crew-*`: never `main` (the config file is versioned). Invalid = default."""
    ref = _claims_config().get("claims_ref", "")
    return ref if _CLAIMS_REF_RE.fullmatch(ref) else CLAIMS_REF


def _claims_remote():
    remote = _claims_config().get("claims_remote", "")
    return remote if _CLAIMS_REMOTE_RE.fullmatch(remote) else "origin"  # never a value read as a git option


def _claims_parse_ts(value):
    try:
        ts = datetime.datetime.fromisoformat(value)
    except Exception:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=datetime.timezone.utc)


def _claims_to_todo(e):
    """Entry returned to the `todo` queue (released or expired), body and title kept."""
    return {**e, "status": "todo", "owner": None, "session": None, "batch": None, "branch": None}


def _claims_expire(tasks, now):
    """Copy of `tasks` where claims older than CLAIMS_TTL are released:
    back to `todo` if the entry has a body, removed otherwise."""
    out = {}
    for slug, e in tasks.items():
        ts = _claims_parse_ts(e.get("ts")) if e.get("status") == "current" else None
        if ts is not None and now - ts > CLAIMS_TTL:
            if not e.get("body"):
                continue
            e = _claims_to_todo(e)
        out[slug] = e
    return out


def _claims_commit(tasks, parent, message):
    blob = json.dumps(tasks, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")
    rc, sha, _ = _claims_git("hash-object", "-w", "--stdin", input_bytes=blob)
    if rc != 0:
        return None
    rc, tree, _ = _claims_git("mktree", input_bytes=f"100644 blob {sha.strip()}\t{CLAIMS_FILE}\n".encode())
    if rc != 0:
        return None
    me = _claims_identity()
    env = {**os.environ, "GIT_AUTHOR_NAME": me, "GIT_AUTHOR_EMAIL": me,
           "GIT_COMMITTER_NAME": me, "GIT_COMMITTER_EMAIL": me}
    args = ["commit-tree", tree.strip(), "-m", message] + (["-p", parent] if parent else [])
    rc, commit, _ = _claims_git(*args, env=env)
    return commit.strip() if rc == 0 and commit.strip() else None


_CLAIMS_NOOP = object()


def _claims_mutate(fn, message):
    """CAS loop: fetch -> `fn(tasks)` (mutates; returns None = write, str = refusal,
    _CLAIMS_NOOP = nothing to write) -> commit -> push with lease on the tip read.
    Push refused (someone wrote in the meantime): we refetch and revalidate.
    Offline: `ok True` + `offline True` + `warning` (soft mode, NOTHING is published:
    callers read `offline`, never only `ok`)."""
    ref, remote = _claims_ref(), _claims_remote()
    for _ in range(CLAIMS_RETRIES):
        f = claims_fetch()
        if not f["ok"]:
            return {"ok": True, "offline": True, "warning": "offline: remote claims not checked, "
                    "action not published (best-effort)"}
        tasks = _claims_expire(f["tasks"], _claims_now())
        verdict = fn(tasks)
        if verdict is _CLAIMS_NOOP:
            return {"ok": True}
        if verdict is not None:
            return {"ok": False, "reason": verdict}
        commit = _claims_commit(tasks, f["tip"], message)
        if not commit:
            return {"ok": False, "reason": "cannot write the ref (git)"}
        rc, _, _ = _claims_git("push", "--quiet", f"--force-with-lease={ref}:{f['tip'] or ''}",
                               remote, f"{commit}:{ref}")
        if rc == 0:
            _claims_git("update-ref", ref, commit)
            return {"ok": True}
    return {"ok": False, "reason": f"conflict: push rejected after {CLAIMS_RETRIES} attempts (retry)"}


def _claims_zone_clash(zone_a, zone_b):
    return any(_path_overlaps(a, b) for a in zone_a or [] for b in zone_b or [])


def _claims_op(slug, message, fn):
    """Single entry point for writes: validates the slug once, then runs the CAS loop."""
    if not _claims_valid_slug(slug):
        return {"ok": False, "reason": "invalid slug"}
    return _claims_mutate(fn, message)


def claims_claim(slug, session, batch, zone, branch):
    me, zone = _claims_identity(), list(zone or [])

    def fn(tasks):
        e = tasks.get(slug) or {}
        if e.get("status") == "current" and e.get("owner") not in (None, me):
            return f"already taken by {e['owner']} ({e.get('batch') or 'unknown batch'})"
        for other, oe in tasks.items():
            if other != slug and oe.get("status") == "current" and oe.get("owner") not in (None, me) \
                    and _claims_zone_clash(zone, oe.get("zone")):
                return f"zone overlaps the claim of {oe['owner']} on {other}"
        tasks[slug] = {**e, "status": "current", "owner": me, "session": session, "batch": batch,
                       "zone": zone or e.get("zone") or [], "branch": branch,
                       "ts": _claims_now().isoformat(timespec="seconds")}
        return None

    return _claims_op(slug, f"claim {slug}", fn)


def claims_release(slug, done=False):
    me = _claims_identity()

    def fn(tasks):
        e = tasks.get(slug)
        if e is None:
            return _CLAIMS_NOOP
        if e.get("owner") not in (None, me):
            return f"claim of {e['owner']}: release refused"
        if done or not e.get("body"):
            del tasks[slug]
        else:
            tasks[slug] = _claims_to_todo(e)
        return None

    return _claims_op(slug, f"{'close' if done else 'release'} {slug}", fn)


def claims_publish(slug, title, zone, body):
    me, zone = _claims_identity(), list(zone or [])

    def fn(tasks):
        e = tasks.get(slug)
        if e is not None:
            if e.get("author") not in (None, me):
                return _CLAIMS_NOOP if e.get("body") == body else \
                    f"existing entry by {e['author']}: modification by another dev refused"
            if e.get("status") == "current" and e.get("owner") not in (None, me):
                return f"already taken by {e['owner']}: modification refused"
        base = e or {"status": "todo", "owner": None}
        tasks[slug] = {**base, "title": title, "zone": zone, "body": body, "author": me,
                       "ts": base.get("ts") or _claims_now().isoformat(timespec="seconds")}
        return None

    return _claims_op(slug, f"publish {slug}", fn)


def _claims_tokens(title):
    s = re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower().translate(str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")))
    return {t for t in s.split() if len(t) >= 3 and t not in _CLAIMS_STOPWORDS}


def claims_check_dup(title, zone):
    """Nearby open entries (overlapping zone OR >= 2 significant words
    in common, >= 60 % of the shorter title). Reads the local ref: no network."""
    mine = _claims_tokens(title)
    out = []
    for slug, e in sorted(_claims_local()[1].items()):
        theirs = _claims_tokens(e.get("title"))
        common = mine & theirs
        by_title = len(common) >= 2 and len(common) / max(1, min(len(mine), len(theirs))) >= 0.6
        by_zone = _claims_zone_clash(list(zone or []), e.get("zone"))
        if by_title or by_zone:
            out.append({"slug": slug, "title": e.get("title"), "owner": e.get("owner") or e.get("author"),
                        "reason": "similar title" if by_title else "overlapping zone"})
    return out


def _claims_local_path(slug):
    """Local path of the task (TODO / CURRENT_TASKS / PAUSED) or None."""
    return next((DIRS[d] / slug for d in ("TODO", "CURRENT_TASKS", "PAUSED") if (DIRS[d] / slug).exists()), None)


def claims_materialize(slug):
    if not _claims_valid_slug(slug):
        return {"ok": False, "reason": "invalid slug"}
    existing = _claims_local_path(slug)
    if existing:
        return {"ok": True, "path": str(existing), "exists": True}
    e = _claims_local()[1].get(slug)
    if e is None or not e.get("body"):
        e = claims_fetch()["tasks"].get(slug)       # missing from the local view: a single fetch, not systematic
    if e is None or not e.get("body"):
        return {"ok": False, "reason": f"`{slug}` not found in the remote claims"}
    target = DIRS["TODO"] / slug
    if target.resolve().parent != DIRS["TODO"].resolve():
        return {"ok": False, "reason": "path outside crew/TODO refused"}
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(target, "x", encoding="utf-8", newline="\n") as fh:  # "x": never overwrites
            fh.write(e["body"])
    except FileExistsError:
        return {"ok": True, "path": str(target), "exists": True}
    return {"ok": True, "path": str(target), "exists": False}


def _claims_ref_on_disk():
    """Does the claims ref exist here? Reads the filesystem only
    (no subprocess): called by the Stop hook on EVERY project, solo ones included."""
    try:
        ref = _claims_ref()
        git = MAIN_ROOT / ".git"
        if git.joinpath(*ref.split("/")).is_file():
            return True
        packed = git / "packed-refs"
        return packed.is_file() and ref.encode() in packed.read_bytes()
    except Exception:
        return False


def check_claims_optin():
    """Warns (non-blocking) if claims exist in the repo but
    `remote_claims` is not enabled: this dev is then not protected from duplicates."""
    if claims_enabled() or not _claims_ref_on_disk():
        return []
    return ["[claims] `refs/crew/claims` exists in this repo but `remote_claims : true` is missing from "
            "crew/CLAUDE_CONTEXT/CREW_CONFIG.md: you are not protected from tasks taken by other devs."]


def claims_board(refresh=False):
    """READ-ONLY Kanban view of the claims for the dashboard: `todo` /
    `current` columns. `refresh=True` does a fetch (network); otherwise reads the local ref.
    Expired claims (> TTL) stay displayed but marked `expired`."""
    empty = {"enabled": False, "offline": False, "me": None, "columns": {"todo": [], "current": []}}
    if not claims_enabled():
        return empty
    offline = False
    if refresh:
        f = claims_fetch()
        tasks, offline = f["tasks"], not f["ok"]
    else:
        tasks = _claims_local()[1]
    now, me = _claims_now(), _claims_identity()
    cols = {"todo": [], "current": []}
    for slug, e in sorted(tasks.items()):
        current = e.get("status") == "current"
        ts = _claims_parse_ts(e.get("ts")) if current else None
        age = max(0, int((now - ts).total_seconds() // 60)) if ts else None
        cols["current" if current else "todo"].append({
            "slug": slug, "title": e.get("title") or slug, "owner": e.get("owner") or e.get("author"),
            "mine": e.get("owner") == me, "batch": e.get("batch"), "zone": e.get("zone") or [],
            "branch": e.get("branch"), "age_minutes": age,
            "expired": age is not None and age > CLAIMS_TTL.total_seconds() // 60})
    return {**empty, "enabled": True, "offline": offline, "me": me, "columns": cols}


def claims_remote_view():
    """Claims view for next-task: (warning, claims_of_others, remote_todos).
    `claims_of_others` = {slug: entry} for the active claims of OTHER devs."""
    me = _claims_identity()
    f = claims_fetch()
    tasks = _claims_expire(f["tasks"], _claims_now())
    warning = None if f["ok"] else "remote claims not checked (offline or remote unreachable)"
    others = {s: e for s, e in tasks.items() if e.get("status") == "current" and e.get("owner") not in (None, me)}
    local = active_task_slugs()
    todo = [{"slug": s, "title": e.get("title"), "zone": e.get("zone")} for s, e in sorted(tasks.items())
            if e.get("status") == "todo" and s not in local]
    return warning, others, todo


def claims_cli(argv):
    """`crew_hook.py claims <fetch|claim|release|publish|check-dup|materialize|list> ...`"""
    if not argv:
        return {"ok": False, "reason": "usage: claims fetch|claim|release|publish|check-dup|materialize|list"}
    if not claims_enabled():
        return {"ok": False, "disabled": True, "reason": "remote_claims disabled (crew/CLAUDE_CONTEXT/CREW_CONFIG.md)"}
    sub, rest = argv[0], argv[1:]
    opts, pos, i = {}, [], 0
    while i < len(rest):
        if rest[i].startswith("--"):
            key = rest[i][2:]
            if key == "done":
                opts[key], i = True, i + 1
            else:
                opts[key], i = (rest[i + 1] if i + 1 < len(rest) else ""), i + 2
        else:
            pos.append(rest[i])
            i += 1
    zone = [z for z in (opts.get("zone") or "").split(",") if z]
    slug = pos[0] if pos else ""
    if sub == "fetch":
        f = claims_fetch()
        return {"ok": f["ok"], "offline": f["offline"], "tasks": f["tasks"]}
    if sub == "list":
        return {"ok": True, "tasks": _claims_expire(_claims_local()[1], _claims_now())}
    if sub == "check-dup":
        return {"ok": True, "duplicates": claims_check_dup(opts.get("title", ""), zone)}
    if not slug:
        return {"ok": False, "reason": f"`claims {sub}`: slug required"}
    if sub == "claim":
        return claims_claim(slug, opts.get("session") or os.environ.get("CLAUDE_CODE_SESSION_ID"),
                            opts.get("batch"), zone, opts.get("branch"))
    if sub == "release":
        return claims_release(slug, done=bool(opts.get("done")))
    if sub == "publish":
        try:
            body = pathlib.Path(opts["body-file"]).read_text(encoding="utf-8-sig")  # without any BOM
        except Exception:
            return {"ok": False, "reason": "--body-file unreadable"}
        return claims_publish(slug, opts.get("title", slug), zone, body)
    if sub == "materialize":
        return claims_materialize(slug)
    return {"ok": False, "reason": f"unknown subcommand: {sub}"}


def _config_set(key, value):
    """Set `key : value` in CREW_CONFIG.md (a single line, the rest is kept);
    value=None removes the key. Atomic write."""
    path = CTX / CLAIMS_CONFIG
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    pat, out, done = re.compile(rf"^\s*{re.escape(key)}\s*[:=]"), [], False
    for ln in lines:
        if pat.match(ln):
            if value is not None and not done:
                out.append(f"{key} : {value}")
                done = True
            continue
        out.append(ln)
    if value is not None and not done:
        out.append(f"{key} : {value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _collab_people():
    """[{name, tasks, me}] sorted by task count: ignored TODO (per owner), other devs' remote claims
    (local view, no network) and my own current / paused tasks."""
    me, store = _collab_name(), _read_ignored()
    slugs = {}
    for slug, who in store.items():
        slugs.setdefault(who or _UNASSIGNED, set()).add(slug)
    if claims_enabled():
        for slug, e in _claims_expire(_claims_local()[1], _claims_now()).items():
            who = e.get("owner") or e.get("author")
            if who and slug not in store:
                slugs.setdefault(who, set()).add(slug)
    if me:
        mine = set(_task_names(DIRS["CURRENT_TASKS"])) | set(_task_names(DIRS["PAUSED"]))
        key = next((k for k in slugs if _same_person(k, me)), me)
        slugs[key] = slugs.get(key, set()) | mine
    people = [{"name": k, "tasks": len(v), "me": _same_person(k, me)} for k, v in slugs.items() if v]
    return sorted(people, key=lambda x: (-x["tasks"], x["name"]))


def collab_cli(argv):
    """`crew_hook.py collab <on --name <name>|off|status>`: team mode, switched by `/crew-collab`.
    `on` sets `remote_claims : true` + `collab_name` (the name owning your claims);
    `off` returns to the base form (claims off, name removed, ignore list deleted)."""
    try:
        opts, _ = _opts(argv[1:], {"name"}) if argv else ({}, [])
    except ValueError as e:
        return {"ok": False, "reason": str(e)}
    sub = argv[0] if argv else None
    if sub == "on":
        if not _valid_person_name(opts.get("name")):
            return {"ok": False, "reason": "`collab on`: --name required (1-60 chars: letters, digits, space . @ - _)"}
        name = opts["name"].strip()
        _config_set("remote_claims", "true")
        _config_set("collab_name", name)
        out = {"ok": True, "collab": True, "name": name}
        if _claims_git("remote", "get-url", _claims_remote())[0] != 0:
            out["warning"] = f"git remote `{_claims_remote()}` not found: claims run in soft mode (nothing is published)"
        return out
    if sub == "off":
        _config_set("remote_claims", "false")
        _config_set("collab_name", None)
        ignore_cli(["off"])
        return {"ok": True, "collab": False}
    if sub == "status":
        return {"ok": True, "collab": claims_enabled(), "name": _collab_name(),
                "ignored": len(_read_ignored()), "people": _collab_people()}
    return {"ok": False, "reason": "usage: collab on --name <name>|off|status"}


def _utf8_stdout():
    """JSON in UTF-8 whatever the console (cp1252 on Windows): the titles come from other devs."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "claims":
        _utf8_stdout()
        print(json.dumps(claims_cli(sys.argv[2:]), ensure_ascii=False))
        return
    if cmd in ("ignore", "collab"):
        _utf8_stdout()
        print(json.dumps((ignore_cli if cmd == "ignore" else collab_cli)(sys.argv[2:]), ensure_ascii=False))
        return
    if cmd in ("count", "status"):
        print(json.dumps(count_batches() if cmd == "count" else crew_status(), ensure_ascii=False))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "next-task":
        _utf8_stdout()
        print(json.dumps(next_task(os.environ.get("CLAUDE_CODE_SESSION_ID")), ensure_ascii=False))
        return
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}
    session_id = payload.get("session_id")
    hook_event = payload.get("hook_event_name")

    if hook_event == "SessionStart":
        # Read-only digest (additionalContext); CREW_SESSION_DIGEST=off turns it off.
        # Deliberately before all the Stop/SessionEnd plumbing (purge, locks, index):
        # this path must write nothing.
        if os.environ.get("CREW_SESSION_DIGEST", "").strip().lower() == "off":
            return
        out = {"hookEventName": "SessionStart"}
        digest = session_digest(session_id)
        if digest:
            out["additionalContext"] = digest
        title = _safe(lambda: session_title(session_id, payload), None)
        if title:
            out["sessionTitle"] = title
        if len(out) > 1:
            print(json.dumps({"hookSpecificOutput": out}))
        return

    if hook_event == "PreToolUse":
        # Escape hatch: CREW_HOOK_PROFILE=minimal disables the guard (latency).
        # Stop/SessionEnd stay active (index, locks).
        if os.environ.get("CREW_HOOK_PROFILE", "").strip().lower() == "minimal":
            return
        # Preventive guard only (git mv TODO->CURRENT_TASKS): no sync of
        # index/journal/locks here, that stays the Stop hook's job.
        gate_pretooluse(payload)
        return

    rotate_graphify_snapshots()
    migrate_legacy_worktree_lock()
    now_dt = datetime.datetime.now()

    state = {name: regen_index(name, d) for name, d in DIRS.items()}

    prev = {}
    if SNAP.exists():
        try:
            prev = json.loads(SNAP.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    cur_c, prev_c = set(state["CURRENT_TASKS"]), set(prev.get("CURRENT_TASKS", []))
    cur_t, prev_t = set(state["TODO"]), set(prev.get("TODO", []))
    cur_p, prev_p = set(state["PAUSED"]), set(prev.get("PAUSED", []))
    started = cur_c - prev_c
    # NB: `resumed` is a subset of `started`, never subtracted from
    # `started` — otherwise `check_batch_collisions(started, ...)` below
    # would skip the batch anti-collision check for a task
    # resuming right after a pause (see code review).
    resumed = started & prev_p  # back from PAUSED, not a real first pick-up
    paused_now = cur_p - prev_p
    # A task leaving CURRENT_TASKS/ for PAUSED/ is NOT finished.
    finished = prev_c - cur_c - cur_p
    added = (cur_t - prev_t) - started

    now = now_dt.date().isoformat()
    entries = []
    for f in sorted(started - resumed):
        entries.append(f"- {now} ▶️ **started**: `{f}`")
    for f in sorted(resumed):
        entries.append(f"- {now} ▶️ **resumed (post-pause)**: `{f}`")
    for f in sorted(paused_now):
        entries.append(f"- {now} ⏸️ **paused**: `{f}`")
    for f in sorted(finished):
        entries.append(f"- {now} ✅ **finished**: `{f}`")
    for f in sorted(added):
        entries.append(f"- {now} ➕ **added to backlog**: `{f}`")

    if finished:  # non-blocking reminder logged in the changelog
        entries.append(f"  ↳ ⚠️ check: entry in `HISTORIQUE.md` + checklist `crew/TESTS/<chantier>.md` "
                       "for " + ", ".join(sorted(finished)))

    completed_tests = process_completed_tests()
    for f in sorted(completed_tests):
        entries.append(f"- {now} 🧪 **tests validated**: `{f}` (moved to `TESTS_DONE/`)")
        # Force regeneration of the IA index since a file was moved
        state["TESTS/IA"] = regen_index("TESTS/IA", DIRS["TESTS/IA"])

    rotated_historique = rotate_historique(now_dt)
    for slug in rotated_historique:
        entries.append(f"- {now} 🗄️ **history archived**: `{slug}` → `HISTORIQUE_ARCHIVE.md` "
                       f"(> {HISTORIQUE_ROTATE_MONTHS} months)")

    pruned_headers = []
    if BATCH_FILE.exists():
        batch_text = BATCH_FILE.read_text(encoding="utf-8")
        pruned_text, pruned_headers = prune_closed_batches(batch_text)
        if pruned_headers:
            BATCH_FILE.write_text(pruned_text, encoding="utf-8")
            for h in pruned_headers:
                entries.append(f"- {now} 🧹 **closed batch removed from CLAUDE_BATCH.md**: `{h}` "
                               "(history already in HISTORIQUE.md)")

    # Live locks per batch (multi-Claude anti-collision). Only the
    # read-modify-write section of crew_lock.json (load -> mutate -> save) is
    # protected by the file mutex (LocksMutex), to prevent a concurrent
    # write (two sessions finishing their turn in the same second)
    # from silently overwriting another, without holding the mutex longer
    # than necessary (check_zone_overlaps is pure computation, not part of the
    # critical section — it runs after release, on the already up-to-date `locks`).
    sections = load_sections()
    active = active_task_slugs()
    collision_reason = None

    with LocksMutex():
        locks = load_locks()
        for sid in purge_stale_locks(locks, now_dt):
            entries.append(f"- {now} ⚠️ **expired lock (>6h) purged (session `{sid}`)**")
        for slug in purge_closed_task_locks(locks):
            entries.append(f"- {now} 🧹 **lock of a task closed outside the main checkout purged**: `{slug}`")

        # Finished task: leaves the `tasks` of ALL the sessions that held it
        # (normally just one). If a session ends up with no task at all,
        # its whole entry (batch/worktree/branch) is purged immediately —
        # no implicit chaining onto another task of the same batch (that
        # caused stale batch/worktree assignments when the session
        # later restarted on a different batch, see bug reported by
        # other sessions). Restarting a task re-registers a fresh entry
        # via _register_task_lock.
        if finished:
            sessions = locks.get("sessions", {})
            for sid, info in list(sessions.items()):
                info["tasks"] = [t for t in info.get("tasks", []) if t not in finished]
                if not info["tasks"]:
                    del sessions[sid]

        if hook_event == "SessionEnd":
            if session_id:
                locks.get("sessions", {}).pop(session_id, None)
        else:
            # `started_for_collision` is the subset of `started` that THIS
            # session really owns (or that nobody owns yet) —
            # computed once and shared by ALL the consumers that
            # attribute an action to `session_id` (registration loop +
            # check_batch_collisions just below). Needed because `SNAP`
            # (.task_state.json) is a SINGLE file shared by all the sessions
            # of the same checkout (no dedicated worktree): the first
            # Stop turn of a session B with `prev` still empty sees EVERY
            # task already in CURRENT_TASKS/ as "started", including
            # a task already locked by a different session A.
            # Without this upstream filtering, B would wrongly claim it at registration
            # time AND trigger a false batch collision
            # if a neighbour of that task is locked by a 3rd
            # session (reported bug: false "multi-session collisions"
            # that were actually this silent mis-attribution).
            started_for_collision = started
            if session_id:
                slug_sessions = _slug_session_map(locks)
                started_for_collision = {
                    f for f in started
                    if not slug_sessions.get(f) or slug_sessions.get(f) == session_id
                }
                for f in started - started_for_collision:
                    sys.stderr.write(
                        f"[crew_lock] `{f}` detected as started by session "
                        f"`{session_id}` but already locked by `{slug_sessions[f]}` — "
                        "lock NOT stolen, existing owner kept.\n"
                    )
                # Fallback kept deliberately (not redundant): covers the
                # `git mv` done directly in the main checkout WITHOUT going
                # through gate_pretooluse (e.g. PreToolUse hook disabled/
                # bypassed, or mutex not acquired in best-effort). For the normal
                # worktree flow, `_claim_git_mv_lock` has already registered the
                # lock upstream — `_register_task_lock` is idempotent (slug
                # not duplicated, batch/worktree/branch already set not overwritten),
                # so this replay only refreshes `since`.
                for f in started_for_collision:
                    _register_task_lock(f, session_id, locks, now_dt, sections)
                # Also refreshes the lock already held by THIS session if it
                # still has active tasks (Case A resume via _claim_resume_lock,
                # or simply a long session): without this, purge_stale_locks
                # would end up releasing the lock of a session still at work.
                info = locks.get("sessions", {}).get(session_id)
                if info and any(f in cur_c for f in info.get("tasks", [])):
                    info["since"] = now_dt.isoformat()
            collision_reason = check_batch_collisions(started_for_collision, sections, locks, session_id)

        save_locks(locks)
        regen_batch_locks_md(sections, locks, active)

    zone_warnings, zone_blocking = check_zone_overlaps(
        sections, in_progress_task_slugs(locks, now_dt), locks, session_id=session_id)

    # Throttling of non-blocking warnings (see _throttle_warnings): mutates
    # locks["warned"], hence saved again behind the mutex like any other
    # mutation of crew_lock.json. Best-effort if two sessions finish their
    # turn in the same second (worst case: a line re-emitted once too many,
    # not a lock inconsistency) — no need to hold the mutex any
    # longer for that.
    due_batch_warnings = _throttle_warnings("batch", check_batches(), locks, now_dt)
    due_zone_warnings = _throttle_warnings("zone", zone_warnings, locks, now_dt)
    due_claims_warnings = _throttle_warnings("claims", _safe(check_claims_optin, []), locks, now_dt)
    # Context alert: step per session in locks["warned"]["context"]
    # (persisted with the rest of `warned` below, no new file).
    # Without session_id: no memory (key shared between sessions otherwise).
    # SessionEnd: no alert, the session's entry is purged.
    ctx_state = locks.setdefault("warned", {}).setdefault("context", {})
    ctx_key = str(session_id)
    if hook_event == "SessionEnd":
        ctx_state.pop(ctx_key, None)
        context_warnings = []
    else:
        context_warnings = check_context_budget(payload, ctx_state if session_id else None)
    with LocksMutex():
        # Reload: only `warned` is to be persisted here. Re-saving the `locks` object
        # loaded above would overwrite a session registered in the meantime (and
        # wrongly disarm the .gate_armed marker).
        fresh = load_locks()
        fresh_ctx = (fresh.get("warned") or {}).get("context") or {}
        fresh["warned"] = locks.get("warned", {})
        # `context`: only carry over THIS session's entry (those of
        # concurrent sessions, re-read under mutex, are kept).
        merged_ctx = dict(fresh_ctx)
        if session_id:
            if ctx_key in ctx_state:
                merged_ctx[ctx_key] = ctx_state[ctx_key]
            else:
                merged_ctx.pop(ctx_key, None)
        fresh["warned"]["context"] = merged_ctx
        save_locks(fresh)

    if entries and prev:  # do not log the first reference snapshot
        head = ""
        if not CHANGELOG.exists():
            head = ("# Task changelog\n\n"
                    "> Fed automatically by the Stop hook (`crew/crew_hook.py`).\n\n")
        with CHANGELOG.open("a", encoding="utf-8") as fh:
            fh.write(head + "\n".join(entries) + "\n")

    auto_commit_closure(finished, now_dt)

    SNAP.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    # Batching: non-blocking warnings (stderr) — does not interfere with the
    # decision JSON emitted on stdout. Throttled (see _throttle_warnings) so as
    # not to re-print the same line every turn as long as nothing has changed.
    # The context alert (context_warnings) goes instead into the stdout JSON under
    # "systemMessage" (50k step per session, see check_context_budget).
    for w in due_batch_warnings:
        sys.stderr.write(w + "\n")
    for w in due_zone_warnings:
        sys.stderr.write(w + "\n")
    for w in due_claims_warnings:
        sys.stderr.write(w + "\n")

    # Blocking invariants (combined into a single decision if several fire)
    reasons = []

    t_stems, c_stems, p_stems = ({f[:-3] for f in s} for s in (cur_t, cur_c, cur_p))

    dup = t_stems & c_stems
    if dup:
        reasons.append("Lifecycle inconsistency: task(s) present in both "
                        "crew/TODO/ and crew/CURRENT_TASKS/: " + ", ".join(sorted(dup)) +
                        ". Remove them from crew/TODO/ (a started task does not stay in the backlog).")

    dup_p = p_stems & (t_stems | c_stems)
    if dup_p:
        reasons.append("Lifecycle inconsistency: task(s) present in both "
                        "crew/PAUSED/ and crew/TODO/ or crew/CURRENT_TASKS/: " + ", ".join(sorted(dup_p)) +
                        ". A task is never in two folders at once.")

    if collision_reason:
        reasons.append(collision_reason)

    if zone_blocking:
        reasons.append("Live zone lock — overlap between active batches locked by "
                        "different sessions: " + " ; ".join(zone_blocking) +
                        " Wait for the other session to finish before continuing.")

    out = {}
    if reasons:
        out["decision"] = "block"
        out["reason"] = "\n\n".join(reasons)
    if context_warnings:
        out["systemMessage"] = "\n".join(context_warnings)
    if out:
        print(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
