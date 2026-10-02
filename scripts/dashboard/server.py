# -*- coding: utf-8 -*-
"""Dashboard crew — visualisation temps reel + gestion (tasks/batches/
sessions) du crew/ d'un projet quelconque bootstrappe depuis ce scaffold.

Reutilise directement la logique de parsing/anti-collision de crew_hook.py
(meme module que celui invoque par les hooks Stop/PreToolUse) plutot que de
la reimplementer, pour ne jamais diverger de l'invariant qu'ils font deja
respecter. Lance via le skill `crew-dashboard` depuis la racine du projet
cible (cwd = racine projet) ; CLAUDE_PROJECT_DIR est force sur cwd avant
l'import de crew_hook pour que son ROOT/CREW pointent sur CE projet et non
sur l'installation du plugin.
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
import crew_hook as h  # noqa: E402  (import apres setup sys.path/env, voir docstring)

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Crew Dashboard")

TASK_FOLDERS = ("TODO", "CURRENT_TASKS", "PAUSED", "ICEBOX")
DASHBOARD_SESSION_ID = "dashboard-ui"  # identite de session stable utilisee quand le
# dashboard revendique lui-meme un verrou live (cf. _claim_current_tasks_lock) — au meme
# titre qu'une session Claude, pour que check_batch_collisions/check_zone_overlaps voient
# une tache demarree depuis le dashboard comme deja prise, exactement comme via /crew-start.
CHECKBOX_RE = re.compile(r"^([ \t]*[-*]\s*\[)( |x|X)(\].*)$", re.MULTILINE)


def _validate_basename(name, kind):
    """Rejette tout `name` qui n'est pas un simple nom de fichier : separateurs
    ('/' ou '\\', quel que soit l'OS hote), chemin absolu, lettre de lecteur
    Windows ('C:...'), ou '.'/'..'. Sans ca, `h.DIRS[sub] / name` (pathlib `/`)
    ignore silencieusement `h.DIRS[sub]` des qu'on lui passe un chemin absolu —
    permettant une ecriture/lecture arbitraire hors de `crew/` (cf. code review)."""
    if not name or "/" in name or "\\" in name or name in (".", "..") or re.match(r"^[A-Za-z]:", name):
        raise HTTPException(400, f"{kind} invalide (nom de fichier simple attendu) : {name}")
    return name


def _release_task_lock(slug):
    """Retire `slug` de la session qui le detient (sous mutex), quelle que
    soit cette session — le dashboard deplace le fichier hors de
    CURRENT_TASKS de toute facon (admin action explicite), donc plus aucune
    session ne devrait continuer a le tenir verrouille apres coup. Sans ca,
    un verrou pose par `_claim_current_tasks_lock` (ou par une vraie session
    /crew-start) resterait fantome jusqu'au TTL des qu'on renvoie la tache
    en TODO/PAUSED/ICEBOX depuis le dashboard. Supprime aussi l'entree
    session si elle ne porte plus aucune tache."""
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
    """Enregistre sous mutex le verrou live pour une tache que le dashboard
    deplace vers CURRENT_TASKS — miroir HTTP-friendly de `h._claim_git_mv_lock`
    (meme sequence : reload+purge sous mutex, re-verifie la collision de slug
    exact ET de voisinage de batch fraiches sous mutex plutot que de se fier au
    pre-check fait hors mutex par l'appelant, enregistre, regenere
    BATCH_LOCKS.md), sauf qu'elle leve HTTPException au lieu de `sys.exit(2)`
    (un serveur ASGI ne doit jamais mourir sur une collision cote client).
    Sans ceci, une tache demarree depuis le dashboard restait invisible aux
    verifications anti-collision (cf. code review, issue #5)."""
    with h.LocksMutex():
        locks = h.load_locks()
        now_dt = datetime.datetime.now()
        h.purge_stale_locks(locks, now_dt)
        other_session = h._slug_session_map(locks).get(slug)
        if other_session and other_session != session_id:
            since = locks.get("sessions", {}).get(other_session, {}).get("since", "?")
            raise HTTPException(409, f"`{slug}` deja verrouille par une autre session (depuis {since})")
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
    active = h.in_progress_task_slugs(locks)  # pas TODO : un batch du backlog n'est pas actif
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


class MoveRequest(BaseModel):
    to: str


@app.post("/api/tasks/{slug}/move")
def move_task(slug: str, body: MoveRequest):
    _validate_basename(slug, "slug")
    if body.to not in TASK_FOLDERS:
        raise HTTPException(400, f"destination invalide : {body.to}")
    source = next((name for name in TASK_FOLDERS if (h.DIRS[name] / slug).is_file()), None)
    if source is None:
        raise HTTPException(404, f"tache introuvable : {slug}")
    if source == body.to:
        raise HTTPException(400, "source et destination identiques")

    if body.to == "CURRENT_TASKS":
        _claim_current_tasks_lock(slug, DASHBOARD_SESSION_ID, h.load_sections())
    elif source == "CURRENT_TASKS":
        _release_task_lock(slug)

    rel_src = (h.DIRS[source] / slug).relative_to(h.ROOT).as_posix()
    rel_dst = (h.DIRS[body.to] / slug).relative_to(h.ROOT).as_posix()
    result = subprocess.run(
        ["git", "mv", rel_src, rel_dst], cwd=str(h.ROOT), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise HTTPException(500, f"git mv a echoue : {result.stderr.strip()}")
    return {"slug": slug, "from": source, "to": body.to}


class ToggleRequest(BaseModel):
    item_index: int


@app.post("/api/tests/{file}/toggle")
def toggle_test_item(file: str, body: ToggleRequest):
    _validate_basename(file, "fichier")
    target = next(
        (h.DIRS[sub] / file for sub in ("TESTS/IA", "TESTS/DEV") if (h.DIRS[sub] / file).is_file()),
        None,
    )
    if target is None:
        raise HTTPException(404, f"fichier de test introuvable : {file}")
    text = target.read_text(encoding="utf-8")
    matches = list(CHECKBOX_RE.finditer(text))
    if not (0 <= body.item_index < len(matches)):
        raise HTTPException(400, f"item_index hors bornes (0-{len(matches) - 1})")
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
            raise HTTPException(404, f"session introuvable : {session_id}")
        del sessions[session_id]
        h.save_locks(locks)
    return {"session_id": session_id, "purged": True}


STATIC_DIR = pathlib.Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def _pick_port(preferred=8943):
    """Port par defaut distinctif (evite 3000/8000, deja pris par Next.js/uvicorn
    de projets cibles) ; fallback sur un port libre assigne par l'OS si pris."""
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
    print(f"Crew Dashboard : http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
