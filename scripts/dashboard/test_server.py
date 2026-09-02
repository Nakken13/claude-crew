# -*- coding: utf-8 -*-
"""Tests pour le dashboard crew (server.py). Meme pattern que
crew/test_crew_hook.py : depot git temporaire isole, constantes de
crew_hook monkeypatchees pour y pointer avant d'importer server (qui
importe crew_hook a son tour)."""
import datetime
import json
import pathlib
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import crew_hook as h  # noqa: E402


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path
    crew = root / "crew"
    ctx = crew / "CLAUDE_CONTEXT"
    dirs = {
        "PROBLEMS": crew / "PROBLEMS",
        "TODO": crew / "TODO",
        "ICEBOX": crew / "ICEBOX",
        "CURRENT_TASKS": crew / "CURRENT_TASKS",
        "PAUSED": crew / "PAUSED",
        "TESTS": crew / "TESTS",
        "TESTS/IA": crew / "TESTS" / "IA",
        "TESTS/DEV": crew / "TESTS" / "DEV",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    ctx.mkdir(parents=True, exist_ok=True)
    (crew / "CLAUDE_BATCH.md").write_text("# Batching\n", encoding="utf-8")

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@test.local")
    _git(root, "config", "user.name", "test")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")

    monkeypatch.setattr(h, "ROOT", root)
    monkeypatch.setattr(h, "CREW", crew)
    monkeypatch.setattr(h, "DIRS", dirs)
    monkeypatch.setattr(h, "CTX", ctx)
    monkeypatch.setattr(h, "BATCH_FILE", crew / "CLAUDE_BATCH.md")
    monkeypatch.setattr(h, "LOCKS_FILE", ctx / "crew_lock.json")
    monkeypatch.setattr(h, "LOCKS_MUTEX", ctx / ".crew_lock.mutex")

    import server as srv

    return {"root": root, "crew": crew, "ctx": ctx, "dirs": dirs, "srv": srv}


def _write_task(dirs, folder, slug, title="Une tache", root=None):
    path = dirs[folder] / slug
    path.write_text(f"# {title}\n", encoding="utf-8")
    if root is not None:
        _git(root, "add", str(path))


def test_state_lists_tasks_batches_sessions(repo):
    _write_task(repo["dirs"], "TODO", "a.md", "Tache A")
    _write_task(repo["dirs"], "CURRENT_TASKS", "b.md", "Tache B")
    repo["ctx"].joinpath("crew_lock.json").write_text(
        json.dumps({"sessions": {"s1": {"batch": "Batch X", "tasks": ["b.md"],
                                         "worktree": None, "branch": None,
                                         "since": datetime.datetime.now().isoformat()}}}),
        encoding="utf-8",
    )
    client = TestClient(repo["srv"].app)
    state = client.get("/api/state").json()
    assert [t["slug"] for t in state["tasks"]["TODO"]] == ["a.md"]
    assert [t["slug"] for t in state["tasks"]["CURRENT_TASKS"]] == ["b.md"]
    assert state["sessions"][0]["session_id"] == "s1"
    assert state["sessions"][0]["stale"] is False


def test_move_task_updates_folders(repo):
    _write_task(repo["dirs"], "TODO", "a.md", root=repo["root"])
    client = TestClient(repo["srv"].app)
    res = client.post("/api/tasks/a.md/move", json={"to": "CURRENT_TASKS"})
    assert res.status_code == 200
    assert not (repo["dirs"]["TODO"] / "a.md").exists()
    assert (repo["dirs"]["CURRENT_TASKS"] / "a.md").exists()


def test_move_into_current_tasks_registers_lock(repo):
    _write_task(repo["dirs"], "TODO", "a.md", root=repo["root"])
    client = TestClient(repo["srv"].app)
    client.post("/api/tasks/a.md/move", json={"to": "CURRENT_TASKS"})
    locks = json.loads(repo["ctx"].joinpath("crew_lock.json").read_text(encoding="utf-8"))
    assert "a.md" in locks["sessions"][repo["srv"].DASHBOARD_SESSION_ID]["tasks"]


def test_move_out_of_current_tasks_releases_lock(repo):
    _write_task(repo["dirs"], "CURRENT_TASKS", "a.md", root=repo["root"])
    repo["ctx"].joinpath("crew_lock.json").write_text(
        json.dumps({"sessions": {"s1": {"batch": None, "tasks": ["a.md"], "worktree": None,
                                         "branch": None, "since": datetime.datetime.now().isoformat()}}}),
        encoding="utf-8",
    )
    client = TestClient(repo["srv"].app)
    res = client.post("/api/tasks/a.md/move", json={"to": "TODO"})
    assert res.status_code == 200
    locks = json.loads(repo["ctx"].joinpath("crew_lock.json").read_text(encoding="utf-8"))
    assert "s1" not in locks["sessions"]


def test_move_task_blocked_by_collision(repo):
    repo["crew"].joinpath("CLAUDE_BATCH.md").write_text(
        "## Batch X\n\nZone : `foo/**`\n\n- `a.md`\n- `b.md`\n", encoding="utf-8"
    )
    _write_task(repo["dirs"], "TODO", "a.md", root=repo["root"])
    _write_task(repo["dirs"], "CURRENT_TASKS", "b.md", root=repo["root"])
    repo["ctx"].joinpath("crew_lock.json").write_text(
        json.dumps({"sessions": {"other": {"batch": "Batch X", "tasks": ["b.md"],
                                            "worktree": None, "branch": None,
                                            "since": datetime.datetime.now().isoformat()}}}),
        encoding="utf-8",
    )
    client = TestClient(repo["srv"].app)
    res = client.post("/api/tasks/a.md/move", json={"to": "CURRENT_TASKS"})
    assert res.status_code == 409
    assert (repo["dirs"]["TODO"] / "a.md").exists()


def test_move_rejects_unknown_slug(repo):
    client = TestClient(repo["srv"].app)
    res = client.post("/api/tasks/does-not-exist.md/move", json={"to": "CURRENT_TASKS"})
    assert res.status_code == 404


def test_move_rejects_path_traversal(repo):
    _write_task(repo["dirs"], "TODO", "a.md", root=repo["root"])
    client = TestClient(repo["srv"].app)
    # Starlette decode %2f avant le matching de route : la requete est deviee
    # vers le mount StaticFiles (scope a static/, jamais crew/) plutot que
    # d'atteindre move_task — 405 (methode non supportee par StaticFiles),
    # jamais 200. L'invariant teste : aucun mouvement de fichier n'a eu lieu.
    res = client.post("/api/tasks/..%2f..%2fetc%2fpasswd/move", json={"to": "CURRENT_TASKS"})
    assert res.status_code in (404, 405)
    assert (repo["dirs"]["TODO"] / "a.md").exists()


def test_toggle_rejects_path_traversal(repo):
    f = repo["dirs"]["TESTS/IA"] / "chantier.md"
    f.write_text("# Chantier\n\n- [ ] item un\n", encoding="utf-8")
    client = TestClient(repo["srv"].app)
    res = client.post("/api/tests/..%2f..%2fetc%2fpasswd/toggle", json={"item_index": 0})
    assert res.status_code in (404, 405)
    assert "[ ] item un" in f.read_text(encoding="utf-8")


def test_toggle_test_item_flips_checkbox(repo):
    f = repo["dirs"]["TESTS/IA"] / "chantier.md"
    f.write_text("# Chantier\n\n- [ ] item un\n- [x] item deux\n", encoding="utf-8")
    client = TestClient(repo["srv"].app)
    res = client.post("/api/tests/chantier.md/toggle", json={"item_index": 0})
    assert res.status_code == 200
    assert res.json()["checked"] is True
    assert "[x] item un" in f.read_text(encoding="utf-8")


def test_purge_session_removes_entry(repo):
    repo["ctx"].joinpath("crew_lock.json").write_text(
        json.dumps({"sessions": {"s1": {"batch": None, "tasks": [], "worktree": None,
                                         "branch": None, "since": datetime.datetime.now().isoformat()}}}),
        encoding="utf-8",
    )
    client = TestClient(repo["srv"].app)
    res = client.post("/api/sessions/s1/purge")
    assert res.status_code == 200
    locks = json.loads(repo["ctx"].joinpath("crew_lock.json").read_text(encoding="utf-8"))
    assert "s1" not in locks["sessions"]


def test_purge_unknown_session_404(repo):
    client = TestClient(repo["srv"].app)
    res = client.post("/api/sessions/nope/purge")
    assert res.status_code == 404
