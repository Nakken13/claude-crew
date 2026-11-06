# -*- coding: utf-8 -*-
"""Crew dashboard — real-time view + management (tasks/batches/sessions) of
the crew/ folder of any project bootstrapped from this scaffold.

Directly reuses the parsing/anti-collision logic of crew_hook.py (the same
module invoked by the Stop/PreToolUse hooks) rather than reimplementing it,
so it never diverges from the invariant they already enforce. Launched via
the `crew-dashboard` skill from the root of the target project (cwd =
project root); CLAUDE_PROJECT_DIR is forced to cwd before importing
crew_hook so its ROOT/CREW point at THIS project and not at the plugin
installation.
"""
import datetime
import os
import pathlib
import re
import socket
import subprocess
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
os.environ.setdefault("CLAUDE_PROJECT_DIR", os.getcwd())
import crew_hook as h  # noqa: E402  (import after sys.path/env setup, see docstring)

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Crew Dashboard")

TASK_FOLDERS = ("TODO", "CURRENT_TASKS", "PAUSED", "ICEBOX")
DASHBOARD_SESSION_ID = "dashboard-ui"  # stable session identity used when the
# dashboard itself claims a live lock (see _claim_current_tasks_lock) — on a par
# with a Claude session, so check_batch_collisions/check_zone_overlaps see a task
# started from the dashboard as already taken, exactly as via /crew-start.
CHECKBOX_RE = re.compile(r"^([ \t]*[-*]\s*\[)( |x|X)(\].*)$", re.MULTILINE)


def _validate_basename(name, kind):
    """Rejects any `name` that is not a plain file name: separators
    ('/' or '\\', whatever the host OS), absolute path, Windows drive letter
    ('C:...'), or '.'/'..'. Without this, `h.DIRS[sub] / name` (pathlib `/`)
    silently ignores `h.DIRS[sub]` as soon as an absolute path is passed —
    allowing arbitrary read/write outside `crew/` (see code review)."""
    if not name or "/" in name or "\\" in name or name in (".", "..") or re.match(r"^[A-Za-z]:", name):
        raise HTTPException(400, f"invalid {kind} (plain file name expected): {name}")
    return name


def _release_task_lock(slug):
    """Removes `slug` from the session holding it (under mutex), whichever
    session that is — the dashboard moves the file out of CURRENT_TASKS
    anyway (explicit admin action), so no session should keep it locked
    afterwards. Without this, a lock set by `_claim_current_tasks_lock` (or
    by a real /crew-start session) would stay a ghost until the TTL as soon
    as the task is sent back to TODO/PAUSED/ICEBOX from the dashboard. Also
    deletes the session entry if it no longer carries any task."""
    with h.LocksMutex():
        locks = h.load_locks()
        sid = h._slug_session_map(locks).get(slug)
        if sid is not None:
            tasks = locks["sessions"][sid]["tasks"]
            tasks.remove(slug)
            if not tasks:
                del locks["sessions"][sid]
        h.save_locks(locks)


def _claim_current_tasks_lock(slug, session_id, sections):
    """Registers under mutex the live lock for a task the dashboard moves to
    CURRENT_TASKS — HTTP-friendly mirror of `h._claim_git_mv_lock` (same
    sequence: reload+purge under mutex, re-check the exact-slug collision AND
    the batch-neighbourhood collision freshly under mutex rather than
    trusting the pre-check done outside the mutex by the caller, register,
    regenerate BATCH_LOCKS.md), except that it raises HTTPException instead
    of `sys.exit(2)` (an ASGI server must never die on a client-side
    collision). Without this, a task started from the dashboard stayed
    invisible to the anti-collision checks (see code review, issue #5)."""
    with h.LocksMutex():
        locks = h.load_locks()
        now_dt = datetime.datetime.now()
        h.purge_stale_locks(locks, now_dt)
        other_session = h._slug_session_map(locks).get(slug)
        if other_session and other_session != session_id:
            since = locks.get("sessions", {}).get(other_session, {}).get("since", "?")
            raise HTTPException(409, f"`{slug}` already locked by another session (since {since})")
        reason = h.check_batch_collisions({slug}, sections, locks, session_id)
        if reason:
            raise HTTPException(409, reason)
        h._register_task_lock(slug, session_id, locks, now_dt, sections)
        h.save_locks(locks)
        h.regen_batch_locks_md(sections, locks, h.active_task_slugs())


def _list_tasks():
    return {
        name: [{"slug": fn, "title": title} for fn, title in h.task_files(h.DIRS[name]).items()]
        for name in TASK_FOLDERS
    }


def _list_batches(locks):
    sections = h.load_sections()
    active = h.in_progress_task_slugs(locks)  # not TODO: a backlog batch is not active
    warnings, blocking = h.check_zone_overlaps(sections, active, locks, observer=True)
    batches = [
        {
            "header": s["header"],
            "slugs": sorted(s["slugs"]),
            "zone_paths": sorted(s["zone_paths"]),
            "active": bool(s["slugs"] & active),
        }
        for s in sections
    ]
    return batches, warnings, blocking


def _list_sessions(locks):
    now = datetime.datetime.now()
    sessions = []
    for sid, info in locks.get("sessions", {}).items():
        stale = h._session_expired(info, now)
        sessions.append(
            {
                "session_id": sid,
                "batch": info.get("batch"),
                "tasks": info.get("tasks", []),
                "worktree": info.get("worktree"),
                "branch": info.get("branch"),
                "since": info.get("since"),
                "stale": stale,
            }
        )
    return sorted(sessions, key=lambda s: s["session_id"])


@app.get("/api/state")
def get_state():
    tasks = _list_tasks()
    locks = h.load_locks()
    batches, warnings, blocking = _list_batches(locks)
    return {
        "tasks": tasks,
        "batches": batches,
        "batch_warnings": warnings,
        "batch_blocking": blocking,
        "sessions": _list_sessions(locks),
    }


@app.get("/api/claims")
def get_claims(refresh: bool = False):
    """Multi-dev kanban (read-only, nothing written from the dashboard).
    Without `refresh`: local ref, no network; `refresh=1`: fetch from the remote."""
    return h.claims_board(refresh=refresh)


class MoveRequest(BaseModel):
    to: str


@app.post("/api/tasks/{slug}/move")
def move_task(slug: str, body: MoveRequest):
    _validate_basename(slug, "slug")
    if body.to not in TASK_FOLDERS:
        raise HTTPException(400, f"invalid destination: {body.to}")
    source = next((name for name in TASK_FOLDERS if (h.DIRS[name] / slug).is_file()), None)
    if source is None:
        raise HTTPException(404, f"task not found: {slug}")
    if source == body.to:
        raise HTTPException(400, "source and destination are identical")

    if body.to == "CURRENT_TASKS":
        _claim_current_tasks_lock(slug, DASHBOARD_SESSION_ID, h.load_sections())
    elif source == "CURRENT_TASKS":
        _release_task_lock(slug)

    rel_src = (h.DIRS[source] / slug).relative_to(h.ROOT).as_posix()
    rel_dst = (h.DIRS[body.to] / slug).relative_to(h.ROOT).as_posix()
    result = subprocess.run(
        ["git", "mv", rel_src, rel_dst], cwd=str(h.ROOT), capture_output=True, text=True
    , stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise HTTPException(500, f"git mv failed: {result.stderr.strip()}")
    return {"slug": slug, "from": source, "to": body.to}


class ToggleRequest(BaseModel):
    item_index: int


@app.post("/api/tests/{file}/toggle")
def toggle_test_item(file: str, body: ToggleRequest):
    _validate_basename(file, "file")
    target = next(
        (h.DIRS[sub] / file for sub in ("TESTS/IA", "TESTS/DEV") if (h.DIRS[sub] / file).is_file()),
        None,
    )
    if target is None:
        raise HTTPException(404, f"test file not found: {file}")
    text = target.read_text(encoding="utf-8")
    matches = list(CHECKBOX_RE.finditer(text))
    if not (0 <= body.item_index < len(matches)):
        raise HTTPException(400, f"item_index out of range (0-{len(matches) - 1})")
    m = matches[body.item_index]
    new_mark = " " if m.group(2).lower() == "x" else "x"
    target.write_text(text[: m.start(2)] + new_mark + text[m.end(2) :], encoding="utf-8")
    return {"file": file, "item_index": body.item_index, "checked": new_mark == "x"}


@app.post("/api/sessions/{session_id}/purge")
def purge_session(session_id: str):
    with h.LocksMutex():
        locks = h.load_locks()
        sessions = locks.get("sessions", {})
        if session_id not in sessions:
            raise HTTPException(404, f"session not found: {session_id}")
        del sessions[session_id]
        h.save_locks(locks)
    return {"session_id": session_id, "purged": True}


STATIC_DIR = pathlib.Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def _pick_port(preferred=8943):
    """Distinctive default port (avoids 3000/8000, already taken by Next.js/uvicorn
    of target projects); falls back to a free port assigned by the OS if taken."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", preferred))
        return preferred
    except OSError:
        probe.close()
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
    finally:
        probe.close()


if __name__ == "__main__":
    import uvicorn

    port = _pick_port()
    print(f"Crew Dashboard: http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
