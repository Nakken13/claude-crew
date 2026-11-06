# -*- coding: utf-8 -*-
"""Tests for crew_hook.py. No pytest suite existed before (checked -
the only existing validation = the crew/TESTS/IA|DEV/ checklists, not
automated). Focuses on auto_commit_closure (task
hook-auto-commit-cloture-tache): each test builds an isolated temporary
git repo (never the real repo) and monkeypatches the module-level
constants of crew_hook to point to it, before calling the
real function — no mock on subprocess/git, real behavior verified."""
import datetime
import io
import json
import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import crew_hook as h


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, stdin=subprocess.DEVNULL)


def _last_commit_message(root):
    r = _git(root, "log", "-1", "--format=%s")
    return r.stdout.strip()


def _last_commit_files(root):
    r = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
    return sorted(r.stdout.strip().splitlines())


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Temporary git repo with the minimal crew/ tree, HEAD already
    set (initial commit), and the crew_hook constants monkeypatched
    to point to it for the duration of the test."""
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
    (ctx / "HISTORIQUE.md").write_text("# Historique\n\n", encoding="utf-8")
    for d in dirs.values():
        (d / "INDEX.md").write_text("# Index\n", encoding="utf-8")
    batch_file = crew / "CLAUDE_BATCH.md"
    batch_file.write_text("# Batching\n", encoding="utf-8")
    changelog = ctx / "CHANGELOG_TACHES.md"
    changelog.write_text("# Changelog\n", encoding="utf-8")
    batch_locks_md = ctx / "BATCH_LOCKS.md"
    locks_file = ctx / "crew_lock.json"
    locks_mutex = ctx / ".crew_lock.mutex"

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@test.local")
    _git(root, "config", "user.name", "test")
    # BATCH_LOCKS.md is gitignored and never tracked in the real repo (see
    # root .gitignore) but regenerated every turn by regen_batch_locks_md
    # -> always exists on disk in practice. Reproduce that here, otherwise the
    # fixture would diverge from reality and mask a real bug (see code
    # review: _closure_commit_scope must filter ignored-and-
    # never-tracked paths, not only never-tracked-and-absent paths).
    (root / ".gitignore").write_text("crew/CLAUDE_CONTEXT/BATCH_LOCKS.md\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    batch_locks_md.write_text("# Locks\n", encoding="utf-8")

    monkeypatch.setattr(h, "ROOT", root)
    monkeypatch.setattr(h, "CREW", crew)
    monkeypatch.setattr(h, "DIRS", dirs)
    monkeypatch.setattr(h, "CTX", ctx)
    # SNAP is computed ONCE at import (`SNAP = CTX / ".task_state.json"`
    # with the real CTX): re-patching `h.CTX` alone does not recompute it. Without this
    # monkeypatch, any test calling `h.main()` reads/writes the real
    # `.task_state.json` of the project instead of the isolated tmp_path (real bug found
    # while writing the PAUSED tests: `main()` had clobbered the real snapshot).
    monkeypatch.setattr(h, "SNAP", ctx / ".task_state.json")
    # Same trap as SNAP: HISTORIQUE/HISTORIQUE_ARCHIVE are computed once
    # at import from the real CTX. Without this monkeypatch,
    # _closure_commit_scope (via HISTORIQUE_ARCHIVE) crashes with "not in the
    # subpath" as soon as ROOT points to tmp_path (real bug found while writing
    # rotate_historique).
    monkeypatch.setattr(h, "BATCH_FILE", batch_file)
    monkeypatch.setattr(h, "BATCH_LOCKS_MD", batch_locks_md)
    monkeypatch.setattr(h, "LOCKS_FILE", locks_file)
    monkeypatch.setattr(h, "LOCKS_MUTEX", locks_mutex)
    monkeypatch.setattr(h, "MAIN_ROOT", root)
    monkeypatch.setattr(h, "IGNORED_FILE", ctx / "crew_ignored.json", raising=False)
    return root, dirs, ctx


def _simulate_closure(root, dirs, ctx, slug):
    """Simulates what the hook has already done before calling auto_commit_closure:
    the CURRENT_TASKS/<slug>.md file disappears (it was tracked), HISTORIQUE.md
    gains an entry. Both changes are left UNSTAGED,
    like a real hook turn (auto_commit_closure must stage them itself)."""
    task_file = dirs["CURRENT_TASKS"] / f"{slug}.md"
    task_file.write_text(f"# {slug}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", f"seed: {slug} in CURRENT_TASKS")
    task_file.unlink()
    histo = ctx / "HISTORIQUE.md"
    histo.write_text(histo.read_text(encoding="utf-8") + f"\n## {slug}\nWhat: done.\n", encoding="utf-8")


def test_auto_commit_closure_creates_commit_with_scope_and_message(repo):
    root, dirs, ctx = repo
    slug = "my-task"
    _simulate_closure(root, dirs, ctx, slug)

    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))

    assert _git(root, "diff", "--cached", "--quiet").returncode == 0, "nothing must remain staged after the commit"
    msg = _last_commit_message(root)
    assert slug in msg, msg
    files = _last_commit_files(root)
    assert "crew/CLAUDE_CONTEXT/HISTORIQUE.md" in files
    assert f"crew/CURRENT_TASKS/{slug}.md" in files
    assert "crew/CLAUDE_CONTEXT/BATCH_LOCKS.md" not in files, \
        "BATCH_LOCKS.md is gitignored/never tracked -> must never be offered to git add"


def test_auto_commit_closure_ignores_gitignored_regenerated_file(repo):
    """Regression: BATCH_LOCKS.md is regenerated on disk every turn by
    regen_batch_locks_md but is gitignored/never tracked — an explicit `git add`
    on it is refused by git and used to make the WHOLE `git add` fail
    (no commit was ever created, silently, in the real repo)."""
    root, dirs, ctx = repo
    slug = "my-task"
    _simulate_closure(root, dirs, ctx, slug)
    assert (ctx / "BATCH_LOCKS.md").exists()  # regenerated by the "hook", never tracked

    sha_before = _git(root, "rev-parse", "HEAD").stdout.strip()
    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))
    sha_after = _git(root, "rev-parse", "HEAD").stdout.strip()

    assert sha_before != sha_after, "the commit must succeed despite the gitignored BATCH_LOCKS.md present on disk"


def test_auto_commit_closure_never_sweeps_unrelated_staged_changes(repo):
    """Regression: the commit must NEVER sweep up a file already staged
    by the user outside the computed crew/ scope — this is exactly the
    incident (backend config committed/pushed without review) that this
    feature exists to prevent."""
    root, dirs, ctx = repo
    slug = "my-task"
    _simulate_closure(root, dirs, ctx, slug)

    unrelated = root / "app_config.py"
    unrelated.write_text("PORT = 8080\n", encoding="utf-8")
    _git(root, "add", "--", "app_config.py")

    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))

    files = _last_commit_files(root)
    assert "app_config.py" not in files, "a file outside crew/ already staged by the user must never be committed"
    still_staged = _git(root, "diff", "--cached", "--name-only", "--", "app_config.py").stdout.strip()
    assert still_staged == "app_config.py", \
        "the user's file must stay staged as is, untouched by the closure commit"


def test_auto_commit_closure_only_includes_slugs_with_matching_histo_entry(repo):
    """2 tasks finish the same turn, only one has a real matching
    HISTORIQUE.md entry (the other: CURRENT_TASKS file gone
    without real history logging, e.g. manual deletion) -> only the
    first must appear in the commit, not just 'HISTORIQUE.md changed
    somewhere' (per-slug detection, not global)."""
    root, dirs, ctx = repo
    real_slug, fake_slug = "real-task", "fake-task"
    fake_task_file = dirs["CURRENT_TASKS"] / f"{fake_slug}.md"
    fake_task_file.write_text(f"# {fake_slug}\n", encoding="utf-8")
    _git(root, "add", "--", str(fake_task_file.relative_to(root)).replace("\\", "/"))
    _git(root, "commit", "-qm", f"seed: {fake_slug}")
    fake_task_file.unlink()
    _simulate_closure(root, dirs, ctx, real_slug)  # touches HISTORIQUE.md AFTER, unstaged

    h.auto_commit_closure({f"{real_slug}.md", f"{fake_slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))

    msg = _last_commit_message(root)
    assert real_slug in msg and fake_slug not in msg, msg
    files = _last_commit_files(root)
    assert f"crew/CURRENT_TASKS/{fake_slug}.md" not in files


def test_auto_commit_closure_idempotent_no_new_commit_without_new_closure(repo):
    root, dirs, ctx = repo
    slug = "my-task"
    _simulate_closure(root, dirs, ctx, slug)
    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))
    sha_after_first = _git(root, "rev-parse", "HEAD").stdout.strip()

    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 5, 0))
    sha_after_second = _git(root, "rev-parse", "HEAD").stdout.strip()

    assert sha_after_first == sha_after_second, "a second call without a new closure must commit nothing"


def test_auto_commit_closure_swallows_commit_failure(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    slug = "my-task"
    _simulate_closure(root, dirs, ctx, slug)

    hooks_dir = root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    pre_commit.chmod(0o755)

    sha_before = _git(root, "rev-parse", "HEAD").stdout.strip()
    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))
    sha_after = _git(root, "rev-parse", "HEAD").stdout.strip()

    assert sha_before == sha_after, "a rejecting pre-commit hook must produce no commit"
    assert "auto-commit" in capsys.readouterr().err.lower()


def test_auto_commit_closure_no_op_when_finished_empty(repo):
    root, dirs, ctx = repo
    sha_before = _git(root, "rev-parse", "HEAD").stdout.strip()

    h.auto_commit_closure(set(), datetime.datetime(2026, 8, 22, 23, 0, 0))

    sha_after = _git(root, "rev-parse", "HEAD").stdout.strip()
    assert sha_before == sha_after


def _git_mv_command(slug):
    return f"git mv crew/TODO/{slug} crew/CURRENT_TASKS/{slug}"


def _git_mv_payload(slug, session_id="S1"):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "session_id": session_id,
        "tool_input": {"command": _git_mv_command(slug)},
    }


def _write_single_task_batch(dirs, header="Batch Zone1", zone="zone1/", slugs=("my-task.md",)):
    """Writes CLAUDE_BATCH.md with a single batch section containing
    `slugs`, and creates the first slug in TODO/ (source file of the `git mv`
    that the gate_pretooluse tests simulate)."""
    refs = "\n".join(f"- `{s}`" for s in slugs)
    h.BATCH_FILE.write_text(
        f"# Batching\n\n## {header}\n\nZone : `{zone}`\n\n{refs}\n",
        encoding="utf-8",
    )
    (dirs["TODO"] / slugs[0]).write_text(f"# {slugs[0]}\n", encoding="utf-8")


def _write_other_session_lock(root, tasks, session_id="OTHER"):
    """Pre-fills crew_lock.json with a concurrent session already holding
    `tasks`, via the module's canonical write (`save_locks`) rather than
    hand-written JSON. `since` relative to the real time (not a
    frozen date): purge_stale_locks purges anything beyond LOCK_TTL (6h)
    relative to `datetime.datetime.now()` at test time, a frozen date
    would eventually exceed that threshold and break the test permanently."""
    since = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    h.save_locks({"sessions": {session_id: {
        "batch": "Batch Zone1",
        "tasks": list(tasks),
        "worktree": f"../{root.name}-batch-zone1",
        "branch": "crew/batch-zone1",
        "since": since,
    }}})


def test_gate_pretooluse_git_mv_registers_lock_immediately_from_worktree(repo):
    """Core of the bug: from a batch worktree, the `git mv` TODO->CURRENT_TASKS
    must no longer wait for the next Stop turn to lock the task —
    gate_pretooluse must write crew_lock.json before the mv even runs."""
    root, dirs, ctx = repo
    slug = "my-task.md"
    _write_single_task_batch(dirs, slugs=(slug,))

    h.gate_pretooluse(_git_mv_payload(slug))  # must not raise SystemExit

    info = h.load_locks()["sessions"]["S1"]
    assert info["tasks"] == [slug]
    assert info["batch"] == "Batch Zone1"
    assert info["worktree"] == f"../{root.name}-batch-zone1"
    assert info["branch"] == "crew/batch-zone1"


def test_gate_pretooluse_git_mv_regenerates_batch_locks_md_immediately(repo):
    """Same scenario, but checks that BATCH_LOCKS.md (human doc) also reflects
    the lock right away, without waiting for an extra Stop turn."""
    root, dirs, ctx = repo
    slug = "my-task.md"
    _write_single_task_batch(dirs, slugs=(slug,))

    h.gate_pretooluse(_git_mv_payload(slug))

    content = (ctx / "BATCH_LOCKS.md").read_text(encoding="utf-8")
    assert f"🔒 `{slug}`" in content
    assert "session `S1`" in content


def test_gate_pretooluse_git_mv_blocks_when_same_slug_already_locked(repo):
    """Another session already holds EXACTLY this slug (not just a
    batch neighbour) -> must block, even if check_batch_collisions (which only
    looks at neighbours) would not have caught it on its own."""
    root, dirs, ctx = repo
    slug = "my-task.md"
    _write_single_task_batch(dirs, slugs=(slug,))
    _write_other_session_lock(root, [slug])

    with pytest.raises(SystemExit) as exc:
        h.gate_pretooluse(_git_mv_payload(slug))
    assert exc.value.code == 2

    locks = h.load_locks()
    assert "S1" not in locks["sessions"], "the blocked session must not be registered"
    assert locks["sessions"]["OTHER"]["tasks"] == [slug]


def test_gate_pretooluse_git_mv_toctou_blocks_on_fresh_reload(repo, monkeypatch):
    """Simulates the race: the first read of `locks` in gate_pretooluse
    (before the mutex) is stale (empty), but ANOTHER session has already set
    its lock on the batch neighbour in the meantime. The fresh re-check
    under mutex must still block."""
    root, dirs, ctx = repo
    slug_a, slug_b = "a.md", "b.md"
    _write_single_task_batch(dirs, slugs=(slug_a, slug_b))
    _write_other_session_lock(root, [slug_b])

    orig_load_locks = h.load_locks
    calls = {"n": 0}

    def stale_then_real_load_locks():
        calls["n"] += 1
        if calls["n"] == 1:
            return {"sessions": {}}  # stale read, before the concurrent write
        return orig_load_locks()

    monkeypatch.setattr(h, "load_locks", stale_then_real_load_locks)

    with pytest.raises(SystemExit) as exc:
        h.gate_pretooluse(_git_mv_payload(slug_a))
    assert exc.value.code == 2

    locks = orig_load_locks()
    assert "S1" not in locks["sessions"]


def test_gate_pretooluse_git_mv_then_stop_started_loop_is_idempotent(repo):
    """The Stop `started` loop (documented fallback, see main()) replays
    the registration for the same task/session after the fact: it must not
    duplicate the entry nor overwrite batch/worktree/branch."""
    root, dirs, ctx = repo
    slug = "my-task.md"
    _write_single_task_batch(dirs, slugs=(slug,))
    h.gate_pretooluse(_git_mv_payload(slug))

    locks = h.load_locks()
    sections = h.load_sections()
    later = datetime.datetime(2026, 8, 22, 23, 30, 0)
    h._register_task_lock(slug, "S1", locks, later, sections)
    h.save_locks(locks)

    locks = h.load_locks()
    info = locks["sessions"]["S1"]
    assert info["tasks"] == [slug]
    assert info["batch"] == "Batch Zone1"
    assert info["worktree"] == f"../{root.name}-batch-zone1"


def test_stop_started_fallback_does_not_steal_lock_from_other_session(repo, monkeypatch, capsys):
    """Root cause of the "multi-session collisions" bug reported by
    the user: `.task_state.json` (SNAP) is a SINGLE file shared
    by all the sessions working in the same checkout (no
    dedicated worktree). A session S2 running for the first time therefore
    sees an empty `prev`, and EVERY file already in CURRENT_TASKS/ (including
    a task started by ANOTHER session S1, already properly
    locked via gate_pretooluse) looks "started" to it. The
    main() fallback must NOT steal that lock: `_slug_session_map`
    must be consulted before `_register_task_lock` to leave the task to
    its real owner."""
    root, dirs, ctx = repo
    slug = "my-task.md"
    _write_single_task_batch(dirs, slugs=(slug,))
    h.gate_pretooluse(_git_mv_payload(slug, session_id="S1"))  # S1 starts cleanly
    (dirs["TODO"] / slug).unlink()
    (dirs["CURRENT_TASKS"] / slug).write_text(f"# {slug}\n", encoding="utf-8")

    _run_stop(monkeypatch, capsys, session_id="S2")  # S2's 1st Stop turn: shared prev empty

    locks = h.load_locks()
    assert locks["sessions"]["S1"]["tasks"] == [slug], "S1 must remain the sole owner of the lock"
    assert slug not in locks["sessions"].get("S2", {}).get("tasks", []), (
        "S2 must not take over a task already locked by another active session"
    )


def test_stop_started_fallback_mis_attribution_does_not_trigger_false_batch_collision(repo, monkeypatch, capsys):
    """Same mis-attribution as the previous test, but via a second
    unfiltered consumer of `started`: `check_batch_collisions` does NOT
    check that `f` belongs to the current session, only that the batch
    NEIGHBOURS of `f` are not locked by another session.
    A session S2 whose 1st Stop turn wrongly mis-attributes `task-a.md`
    (already started by S1) would thus be blocked for a "collision" with
    `task-b.md` (locked by a 3rd session) even though S2 never
    started anything itself."""
    root, dirs, ctx = repo
    slug_a, slug_b = "task-a.md", "task-b.md"
    _write_single_task_batch(dirs, slugs=(slug_a, slug_b))
    h.gate_pretooluse(_git_mv_payload(slug_a, session_id="S1"))  # S1 starts task-a cleanly
    (dirs["TODO"] / slug_a).unlink()
    (dirs["CURRENT_TASKS"] / slug_a).write_text(f"# {slug_a}\n", encoding="utf-8")
    # _write_other_session_lock() OVERWRITES the whole crew_lock.json (save_locks replaces
    # the entire file): calling it here would erase the S1 lock set right
    # above. So we merge directly into the existing locks to
    # add the batch neighbour locked by a 3rd session.
    locks = h.load_locks()
    since = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    locks["sessions"]["OTHER"] = {
        "batch": "Batch Zone1", "tasks": [slug_b],
        "worktree": f"../{root.name}-batch-zone1", "branch": "crew/batch-zone1", "since": since,
    }
    h.save_locks(locks)

    decision = _run_stop(monkeypatch, capsys, session_id="S2")  # S2's 1st Stop turn: started nothing

    assert decision is None or decision.get("decision") != "block", (
        "S2 must not be blocked for a batch collision caused by a task "
        f"it never started (shared SNAP mis-attribution): {decision}"
    )


def test_auto_commit_closure_no_op_when_finished_but_historique_untouched(repo):
    """finished non-empty but HISTORIQUE.md not modified (e.g. manual
    deletion of the file without going through the crew closure) -> no commit."""
    root, dirs, ctx = repo
    slug = "my-task"
    task_file = dirs["CURRENT_TASKS"] / f"{slug}.md"
    task_file.write_text(f"# {slug}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", f"seed: {slug}")
    task_file.unlink()
    sha_before = _git(root, "rev-parse", "HEAD").stdout.strip()

    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))

    sha_after = _git(root, "rev-parse", "HEAD").stdout.strip()
    assert sha_before == sha_after


def test_throttle_warnings_emits_new_warning_and_records_it(monkeypatch):
    monkeypatch.setattr(h, "MAIN_ROOT", h.ROOT)  # `batch` key = main checkout case
    locks = {"sessions": {}}
    now = datetime.datetime(2026, 8, 29, 10, 0, 0)
    due = h._throttle_warnings("batch", ["[batch] warning A"], locks, now)
    assert due == ["[batch] warning A"]
    assert locks["warned"]["batch"]["[batch] warning A"] == now.isoformat()


def test_throttle_warnings_suppresses_repeat_within_cooldown():
    locks = {"sessions": {}}
    t0 = datetime.datetime(2026, 8, 29, 10, 0, 0)
    h._throttle_warnings("batch", ["[batch] warning A"], locks, t0)
    t1 = t0 + datetime.timedelta(minutes=5)
    due = h._throttle_warnings("batch", ["[batch] warning A"], locks, t1)
    assert due == []


def test_throttle_warnings_re_emits_after_cooldown_elapsed():
    locks = {"sessions": {}}
    t0 = datetime.datetime(2026, 8, 29, 10, 0, 0)
    h._throttle_warnings("batch", ["[batch] warning A"], locks, t0)
    t1 = t0 + datetime.timedelta(minutes=h.WARNING_COOLDOWN_MINUTES + 1)
    due = h._throttle_warnings("batch", ["[batch] warning A"], locks, t1)
    assert due == ["[batch] warning A"]


def test_throttle_warnings_drops_state_for_resolved_warning(monkeypatch):
    monkeypatch.setattr(h, "MAIN_ROOT", h.ROOT)  # `batch` key = main checkout case
    """A condition that has disappeared (task categorized, overlap resolved) must
    not leave a dead entry growing locks['warned'] indefinitely,
    and if it reappears later it must warn again immediately."""
    locks = {"sessions": {}}
    t0 = datetime.datetime(2026, 8, 29, 10, 0, 0)
    h._throttle_warnings("batch", ["[batch] warning A"], locks, t0)
    t1 = t0 + datetime.timedelta(minutes=5)
    h._throttle_warnings("batch", [], locks, t1)  # condition resolved
    assert locks["warned"]["batch"] == {}

    t2 = t1 + datetime.timedelta(minutes=5)
    due = h._throttle_warnings("batch", ["[batch] warning A"], locks, t2)
    assert due == ["[batch] warning A"]  # reappears -> no inherited cooldown


def test_throttle_warnings_categories_are_independent():
    locks = {"sessions": {}}
    now = datetime.datetime(2026, 8, 29, 10, 0, 0)
    h._throttle_warnings("batch", ["same text"], locks, now)
    due = h._throttle_warnings("zone", ["same text"], locks, now)
    assert due == ["same text"]


def _run_stop_capture_err(monkeypatch, capsys, session_id="S1"):
    """Like _run_stop, but returns stderr instead of leaving it drained without
    being read (capsys.readouterr() empties out AND err in a single call)."""
    payload = {"hook_event_name": "Stop", "session_id": session_id}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    return capsys.readouterr().err


def test_stop_hook_does_not_renag_same_batch_warning_next_turn(repo, monkeypatch, capsys):
    """check_batches() fires every turn as long as a task stays uncategorized
    in CLAUDE_BATCH.md: without throttling, the same stderr warning
    would be re-printed on EVERY Stop turn (context cost proportional
    to the number of turns, not to the reality of the backlog)."""
    root, dirs, ctx = repo
    (dirs["TODO"] / "orphan.md").write_text("# orphan\n", encoding="utf-8")

    first_err = _run_stop_capture_err(monkeypatch, capsys)
    assert "orphan.md" in first_err

    second_err = _run_stop_capture_err(monkeypatch, capsys)
    assert "orphan.md" not in second_err


def test_check_batches_ignores_md_refs_outside_list_lines(repo):
    """`.md` refs in header prose (`CLAUDE.md`) or in the Zone line are
    not tasks: only the list lines count."""
    root, dirs, ctx = repo
    (dirs["TODO"] / "real-task.md").write_text("# t\n", encoding="utf-8")
    h.BATCH_FILE.write_text(
        "# Batching\n\nSee § Batching in `crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md`.\n\n"
        "## Batch A\n\nZone : `src/`, `README.md`\n\n- `real-task.md`\n",
        encoding="utf-8",
    )
    assert h.check_batches() == []


def test_check_batches_still_flags_vanished_and_uncategorized_tasks(repo):
    root, dirs, ctx = repo
    (dirs["TODO"] / "orphan.md").write_text("# o\n", encoding="utf-8")
    h.BATCH_FILE.write_text(
        "## Batch A\n\nZone : `src/`\n\n- `vanished.md`\n", encoding="utf-8"
    )
    warnings = h.check_batches()
    assert any("does not exist" in w and "vanished.md" in w for w in warnings)
    assert any("not categorized" in w and "orphan.md" in w for w in warnings)


def test_prune_closed_batches_removes_fully_closed_section():
    text = (
        "# Batching\n\n"
        "## A classer\n\nplaceholder\n\n"
        "## Batch A\n\nZone : `files/modules`\n\n- `<slug>.md`\n\n"
        "## Batch demo\n\nZone : `src/`\n\n"
        "1. ~~`task-one.md`~~ - done. See `HISTORIQUE.md`.\n"
        "2. ~~`task-two.md`~~ - also done.\n\n"
    )
    new_text, removed = h.prune_closed_batches(text)
    assert removed == ["Batch demo"]
    assert "Batch demo" not in new_text
    assert "task-one.md" not in new_text
    # Unaffected sections intact
    assert "## Batch A" in new_text
    assert "<slug>.md" in new_text
    assert "## A classer" in new_text


def test_prune_closed_batches_keeps_placeholder_batch_untouched():
    """A batch never filled in (0 real task) is not 'closed': nothing to remove."""
    text = "## Batch A\n\nZone : `files/modules`\n\n- `<slug>.md`\n\n"
    new_text, removed = h.prune_closed_batches(text)
    assert removed == []
    assert new_text == text


def test_prune_closed_batches_keeps_partially_closed_batch():
    text = (
        "## Batch open\n\nZone : `other/`\n\n"
        "1. ~~`closed-one.md`~~ - closed.\n"
        "2. `still-open.md` - not finished.\n\n"
    )
    new_text, removed = h.prune_closed_batches(text)
    assert removed == []
    assert new_text == text


def test_prune_closed_batches_ignores_incidental_md_refs_in_zone_and_prose():
    """`*.md` refs in the Zone line (e.g. README.md, CHANGELOG.md) or in
    prose (e.g. 'see HISTORIQUE.md') must not be counted as
    open tasks — only the leading list lines (`- `/`N. `) count."""
    text = (
        "## Batch pkg\n\n"
        "Zone : `README.md`, `CHANGELOG.md`, `scripts/`\n\n"
        "1. ~~`only-task.md`~~ - done, see `HISTORIQUE.md` for details.\n\n"
    )
    new_text, removed = h.prune_closed_batches(text)
    assert removed == ["Batch pkg"]
    assert new_text.strip() == ""


def _write_transcript(tmp_path, usages, model=None):
    """Writes a minimal JSONL transcript: one assistant message per given
    usage (in order), interleaved with non-assistant/empty/corrupted lines
    to check that only the LAST valid assistant entry is kept."""
    path = tmp_path / "transcript.jsonl"
    lines = []
    for u in usages:
        lines.append('{"message": {"role": "user", "content": "hi"}}')
        lines.append("")  # empty line, must be ignored
        lines.append("not json")  # corrupted line, must be ignored
        msg = {"role": "assistant", "usage": u}
        if model:
            msg["model"] = model
        lines.append(json.dumps({"message": msg}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_check_context_budget_no_transcript_path_returns_empty():
    assert h.check_context_budget({}) == []


def test_check_context_budget_missing_file_returns_empty(tmp_path):
    missing = str(tmp_path / "does-not-exist.jsonl")
    assert h.check_context_budget({"transcript_path": missing}) == []


def test_check_context_budget_under_threshold_no_warning(tmp_path):
    transcript = _write_transcript(tmp_path, [{"input_tokens": 1000, "cache_read_input_tokens": 2000}])
    assert h.check_context_budget({"transcript_path": transcript}) == []


def test_check_context_budget_over_threshold_warns(tmp_path):
    transcript = _write_transcript(tmp_path, [{
        "input_tokens": 100_000,
        "cache_read_input_tokens": 40_000,
        "cache_creation_input_tokens": 20_000,
    }])
    warnings = h.check_context_budget({"transcript_path": transcript})
    assert len(warnings) == 1
    assert "160" in warnings[0].replace(",", "").replace(" ", "")
    assert "context" in warnings[0]


def test_check_context_budget_uses_last_assistant_usage_not_first(tmp_path):
    """Context grows turn after turn: only the last value counts,
    even if a previous turn already exceeded the threshold and then /clear happened."""
    transcript = _write_transcript(tmp_path, [
        {"input_tokens": 200_000},
        {"input_tokens": 1000},
    ])
    assert h.check_context_budget({"transcript_path": transcript}) == []


def _ctx(tokens):
    return {"input_tokens": tokens}


def test_check_context_budget_200k_window_alerts_at_160k(tmp_path):
    transcript = _write_transcript(tmp_path, [_ctx(160_000)], model="claude-sonnet-5-5")
    assert len(h.check_context_budget({"transcript_path": transcript})) == 1


def test_check_context_budget_same_threshold_for_1m_model(tmp_path):
    """Single 150k threshold, including the [1m] model or total > 210k."""
    model = "claude-opus-5-5[1m]"
    low = _write_transcript(tmp_path, [_ctx(140_000)], model=model)
    assert h.check_context_budget({"transcript_path": low}) == []
    high = _write_transcript(tmp_path, [_ctx(160_000)], model=model)
    assert len(h.check_context_budget({"transcript_path": high})) == 1
    big = _write_transcript(tmp_path, [_ctx(300_000)], model="claude-sonnet-5-5")
    assert len(h.check_context_budget({"transcript_path": big})) == 1


def test_check_context_budget_repeats_only_every_50k_per_session(tmp_path):
    state = {}
    payload = lambda t, sid="S1": {"transcript_path": _write_transcript(
        tmp_path, [_ctx(t)], model="claude-opus-5-5[1m]"), "session_id": sid}
    assert len(h.check_context_budget(payload(160_000), state)) == 1
    assert h.check_context_budget(payload(180_000), state) == []  # < +50k
    assert len(h.check_context_budget(payload(215_000), state)) == 1  # +50k step
    # another session: independent state
    assert len(h.check_context_budget(payload(180_000, "S2"), state)) == 1


def test_check_context_budget_state_resets_when_back_under_threshold(tmp_path):
    state = {}
    p = lambda t: {"transcript_path": _write_transcript(tmp_path, [_ctx(t)]), "session_id": "S1"}
    assert len(h.check_context_budget(p(160_000), state)) == 1
    assert h.check_context_budget(p(20_000), state) == []  # /clear or compaction
    assert len(h.check_context_budget(p(160_000), state)) == 1  # alerts again


def test_stop_context_alert_goes_to_system_message_not_stderr(repo, monkeypatch, capsys, tmp_path):
    transcript = _write_transcript(tmp_path, [_ctx(160_000)])
    payload = {"hook_event_name": "Stop", "session_id": "S1", "transcript_path": transcript}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    cap = capsys.readouterr()
    assert "[context]" not in cap.err
    out = json.loads(cap.out.strip())
    assert "[context]" in out["systemMessage"]
    assert "decision" not in out

    # 2nd Stop, same level: no new alert (50k step per session)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    assert "systemMessage" not in capsys.readouterr().out


def test_stop_context_state_keeps_concurrent_session_entry(repo, monkeypatch, capsys, tmp_path):
    """Another Stop wrote warned.context['S2'] in the meantime: S1's save does not overwrite it."""
    locks = h.load_locks()
    locks.setdefault("warned", {})["context"] = {"S2": 900_000}
    h.save_locks(locks)
    transcript = _write_transcript(tmp_path, [_ctx(160_000)])
    payload = {"hook_event_name": "Stop", "session_id": "S1", "transcript_path": transcript}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    ctx = h.load_locks()["warned"]["context"]
    assert ctx == {"S2": 900_000, "S1": 160_000}


def test_session_end_purges_context_state_without_alert(repo, monkeypatch, capsys, tmp_path):
    transcript = _write_transcript(tmp_path, [_ctx(160_000)])
    stop = {"hook_event_name": "Stop", "session_id": "S1", "transcript_path": transcript}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stop)))
    h.main()
    capsys.readouterr()
    end = dict(stop, hook_event_name="SessionEnd")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(end)))
    h.main()
    assert "systemMessage" not in capsys.readouterr().out
    assert "S1" not in h.load_locks()["warned"]["context"]


def _run_stop(monkeypatch, capsys, session_id="S1"):
    """Invokes h.main() like the real Stop hook: stdin = JSON payload,
    stdout captured (possible decision JSON if the turn is blocked).
    No transcript_path -> check_context_budget no-op."""
    payload = {"hook_event_name": "Stop", "session_id": session_id}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


def test_pause_move_not_reported_finished_keeps_lock(repo, monkeypatch, capsys):
    """CURRENT_TASKS -> PAUSED is not a closure: no 'finished' in the
    changelog, no purge of the live lock (see task
    add-paused-lifecycle-state, code review)."""
    root, dirs, ctx = repo
    slug = "my-task.md"
    _write_single_task_batch(dirs, slugs=(slug,))
    (dirs["TODO"] / slug).unlink()
    (dirs["CURRENT_TASKS"] / slug).write_text(f"# {slug}\n", encoding="utf-8")

    sections = h.load_sections()
    locks = h.load_locks()
    h._register_task_lock(slug, "S1", locks, datetime.datetime.now(), sections)
    h.save_locks(locks)

    _run_stop(monkeypatch, capsys)  # establishes the reference snapshot (empty prev)

    (dirs["CURRENT_TASKS"] / slug).replace(dirs["PAUSED"] / slug)  # simulates the pause git mv

    _run_stop(monkeypatch, capsys)

    changelog = (ctx / "CHANGELOG_TACHES.md").read_text(encoding="utf-8")
    assert f"**paused**: `{slug}`" in changelog
    assert "**finished**" not in changelog
    assert slug in h.load_locks()["sessions"]["S1"]["tasks"]


def test_resumed_task_relabeled_and_rechecked_for_batch_collision(repo, monkeypatch, capsys):
    """PAUSED -> CURRENT_TASKS is a resume ('resumed (post-pause)'), not
    a first start, AND must go through check_batch_collisions again like
    a real start. Before the fix (code review): `started` was mutated to
    exclude resumed tasks, hence never revalidated -> this test would wrongly block
    on unfixed code (no collision detected) and confirms the
    fix (collision properly detected)."""
    root, dirs, ctx = repo
    slug_a, slug_b = "task-a.md", "task-b.md"
    _write_single_task_batch(dirs, slugs=(slug_a, slug_b))
    (dirs["TODO"] / slug_a).unlink()
    (dirs["PAUSED"] / slug_a).write_text(f"# {slug_a}\n", encoding="utf-8")
    (dirs["CURRENT_TASKS"] / slug_b).write_text(f"# {slug_b}\n", encoding="utf-8")

    sections = h.load_sections()
    locks = h.load_locks()
    h._register_task_lock(slug_a, "S1", locks, datetime.datetime.now(), sections)
    h._register_task_lock(slug_b, "OTHER", locks, datetime.datetime.now(), sections)
    h.save_locks(locks)

    _run_stop(monkeypatch, capsys, session_id="S1")  # baseline: task-a in PAUSED, task-b in CURRENT_TASKS

    (dirs["PAUSED"] / slug_a).replace(dirs["CURRENT_TASKS"] / slug_a)  # post-pause resume

    decision = _run_stop(monkeypatch, capsys, session_id="S1")

    changelog = (ctx / "CHANGELOG_TACHES.md").read_text(encoding="utf-8")
    assert f"**resumed (post-pause)**: `{slug_a}`" in changelog
    assert f"**started**: `{slug_a}`" not in changelog

    assert decision is not None
    assert decision["decision"] == "block"
    assert "collision" in decision["reason"].lower()


def test_dup_paused_and_current_tasks_blocks(repo, monkeypatch, capsys):
    """Reuses the existing invariant (never two folders at once) for
    PAUSED: a slug present in both PAUSED/ and CURRENT_TASKS/ must
    block the turn."""
    root, dirs, ctx = repo
    slug = "my-task.md"
    (dirs["CURRENT_TASKS"] / slug).write_text(f"# {slug}\n", encoding="utf-8")
    (dirs["PAUSED"] / slug).write_text(f"# {slug}\n", encoding="utf-8")

    decision = _run_stop(monkeypatch, capsys)

    assert decision is not None
    assert decision["decision"] == "block"
    assert "PAUSED" in decision["reason"]


def test_rotate_historique_entries_moves_old_entries_keeps_recent():
    cutoff = datetime.date(2026, 3, 1)
    text = (
        "# History of finished tasks\n\n"
        "Intro.\n\n"
        "## old-task — 2025-01-10\n"
        "What: ancienne.\n\n"
        "## recent-task — 2026-08-20\n"
        "What: recente.\n\n"
    )
    kept, archived, slugs = h.rotate_historique_entries(text, cutoff)
    assert slugs == ["old-task"]
    assert "old-task" not in kept
    assert "recent-task" in kept
    assert "Intro." in kept  # preamble never archived
    assert "old-task" in archived
    assert "recent-task" not in archived


def test_rotate_historique_entries_ignores_undated_entries():
    """Header with no parseable date (malformed entry): never rotated
    blindly, since it cannot be compared to the cutoff."""
    cutoff = datetime.date(2026, 3, 1)
    text = "# Historique\n\n## verif-fork-throwaway\nWhat: no date.\n\n"
    kept, archived, slugs = h.rotate_historique_entries(text, cutoff)
    assert slugs == []
    assert kept == text
    assert archived == ""


def test_rotate_historique_entries_ignores_entries_inside_html_comment():
    """The format example documented in an HTML comment (see real HISTORIQUE.md:
    block <!-- Example: ## <slug> — YYYY-MM-DD ... -->) must
    never be mistaken for a real entry to archive."""
    cutoff = datetime.date(2026, 3, 1)
    text = (
        "# Historique\n\n"
        "<!-- Example:\n"
        "## <task slug> — YYYY-MM-DD\n"
        "What: ...\n"
        "-->\n\n"
        "## real-entry — 2025-01-10\n"
        "What: reelle.\n\n"
    )
    kept, archived, slugs = h.rotate_historique_entries(text, cutoff)
    assert slugs == ["real-entry"]
    assert "<!-- Example:" in kept  # the comment stays in the live file
    assert "<task slug>" in kept
    assert "real-entry" not in kept
    assert "real-entry" in archived


def test_rotate_historique_entries_no_op_when_nothing_old():
    cutoff = datetime.date(2020, 1, 1)
    text = "# Historique\n\n## recent-task — 2026-08-20\nWhat: recente.\n\n"
    kept, archived, slugs = h.rotate_historique_entries(text, cutoff)
    assert slugs == []
    assert kept == text
    assert archived == ""


def test_rotate_historique_writes_archive_and_trims_live_file(repo, monkeypatch):
    root, dirs, ctx = repo
    histo = ctx / "HISTORIQUE.md"
    histo.write_text(
        "# History of finished tasks\n\nIntro.\n\n"
        "## old-task — 2025-01-10\nWhat: ancienne.\n\n"
        "## recent-task — 2026-08-20\nWhat: recente.\n\n",
        encoding="utf-8",
    )
    archive = ctx / "HISTORIQUE_ARCHIVE.md"

    rotated = h.rotate_historique(datetime.datetime(2026, 8, 29))

    assert rotated == ["old-task"]
    live = histo.read_text(encoding="utf-8")
    assert "old-task" not in live
    assert "recent-task" in live
    assert archive.exists()
    assert "old-task" in archive.read_text(encoding="utf-8")


def _seed_session_lock(root, slug, session_id="S1"):
    since = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    h.save_locks({"sessions": {session_id: {
        "batch": "Batch Zone1", "tasks": [slug],
        "worktree": f"../{root.name}-batch-zone1", "branch": "crew/batch-zone1", "since": since,
    }}})


def test_stop_purges_lock_of_task_closed_in_worktree(repo, monkeypatch, capsys):
    """Task started AND closed in a worktree: the main checkout never
    saw it in CURRENT_TASKS/, so never in `finished` -> the lock
    stayed forever (ghost session in crew_lock.json). A task
    absent from the main checkout AND the session's worktree is closed."""
    root, dirs, ctx = repo
    slug = "closed-in-worktree.md"
    _seed_session_lock(root, slug)

    _run_stop(monkeypatch, capsys, session_id="OTHER")

    assert "S1" not in h.load_locks()["sessions"]


def test_stop_keeps_lock_of_task_current_in_session_worktree(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    slug = "in-progress-worktree.md"
    wt_current = root.parent / f"{root.name}-batch-zone1" / "crew" / "CURRENT_TASKS"
    wt_current.mkdir(parents=True)
    (wt_current / slug).write_text(f"# {slug}\n", encoding="utf-8")
    _seed_session_lock(root, slug)

    _run_stop(monkeypatch, capsys, session_id="OTHER")

    assert h.load_locks()["sessions"]["S1"]["tasks"] == [slug]


def test_stop_keeps_lock_of_task_still_in_main_todo(repo, monkeypatch, capsys):
    """Worktree not merged yet: the task is still in TODO/ of the main
    checkout -> still alive, lock kept."""
    root, dirs, ctx = repo
    slug = "not-yet-merged.md"
    (dirs["TODO"] / slug).write_text(f"# {slug}\n", encoding="utf-8")
    _seed_session_lock(root, slug)

    _run_stop(monkeypatch, capsys, session_id="OTHER")

    assert h.load_locks()["sessions"]["S1"]["tasks"] == [slug]


def test_purge_closed_task_locks_skipped_outside_main_checkout(repo, monkeypatch):
    """From a worktree (`.git` = file), ROOT does not see the crew state of the
    main checkout: purge nothing rather than release a real lock."""
    root, dirs, ctx = repo
    worktree_root = root.parent / f"{root.name}-wt"
    (worktree_root / "crew" / "TODO").mkdir(parents=True)
    (worktree_root / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    monkeypatch.setattr(h, "ROOT", worktree_root)
    locks = {"sessions": {"S1": {"tasks": ["unknown.md"], "worktree": None}}}

    assert h.purge_closed_task_locks(locks) == []
    assert locks["sessions"]["S1"]["tasks"] == ["unknown.md"]


def _write_two_overlapping_batches(slug_a="task-a.md", slug_b="task-b.md"):
    """Two batches whose `Zone :` entries overlap (`shared/` vs `shared/x.py`).
    Creates no task file: each test places a and b where it wants."""
    h.BATCH_FILE.write_text(
        "# Batching\n\n"
        f"## Batch A · ⏳ not started\n\nZone : `shared/`\n\n- `{slug_a}`\n\n"
        f"## Batch B · ⏳ not started\n\nZone : `shared/x.py`\n\n- `{slug_b}`\n",
        encoding="utf-8",
    )


def _lock_sessions(root, by_session):
    """crew_lock.json with one live session per entry {session_id: [slugs]}."""
    since = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    h.save_locks({"sessions": {
        sid: {"batch": None, "tasks": list(tasks), "worktree": f"../{root.name}-batch-{sid.lower()}",
              "branch": f"crew/batch-{sid.lower()}", "since": since}
        for sid, tasks in by_session.items()
    }})


def test_zone_overlap_ignores_batches_with_only_todo_tasks(repo, monkeypatch, capsys):
    """False positive observed (voyageo/time2cook): two 'not started' batches
    whose tasks are all in TODO/ were treated as active ->
    a `[zone]` warning every turn. Active = >=1 task in
    CURRENT_TASKS/PAUSED or held by a lock (crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md § Batching)."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    for s in ("task-a.md", "task-b.md"):
        (dirs["TODO"] / s).write_text(f"# {s}\n", encoding="utf-8")

    err = _run_stop_capture_err(monkeypatch, capsys)

    assert "[zone]" not in err


def test_zone_overlap_warns_when_both_batches_in_progress(repo, monkeypatch, capsys):
    """Safeguard kept: one batch in CURRENT_TASKS and the other in PAUSED
    (pause = still active) overlapping -> warning."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    (dirs["CURRENT_TASKS"] / "task-a.md").write_text("# a\n", encoding="utf-8")
    (dirs["PAUSED"] / "task-b.md").write_text("# b\n", encoding="utf-8")

    err = _run_stop_capture_err(monkeypatch, capsys)

    assert "[zone]" in err


def test_zone_overlap_counts_task_locked_from_worktree(repo, monkeypatch, capsys):
    """Task started in a batch worktree: still in TODO/ in the main
    checkout, but held by a live lock -> its batch is active."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    (dirs["TODO"] / "task-a.md").write_text("# a\n", encoding="utf-8")
    (dirs["CURRENT_TASKS"] / "task-b.md").write_text("# b\n", encoding="utf-8")
    _lock_sessions(root, {"WT": ["task-a.md"]})

    # S1 (the turn's session) takes over task-b via the `started` fallback:
    # cross-session overlap -> blocking (stdout) rather than a warning.
    decision = _run_stop(monkeypatch, capsys, session_id="S1")

    assert decision and decision.get("decision") == "block", decision
    assert "zone" in decision["reason"]


def test_zone_overlap_does_not_block_uninvolved_third_session(repo, monkeypatch, capsys):
    """Two colliding batches locked by S1 and S2: a 3rd session S3,
    foreign to both, must not be blocked (it can do nothing about it;
    blocking it loops Stop->reinvoke). Warning only."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    for s in ("task-a.md", "task-b.md"):
        (dirs["TODO"] / s).write_text(f"# {s}\n", encoding="utf-8")
    _lock_sessions(root, {"S1": ["task-a.md"], "S2": ["task-b.md"]})

    decision = _run_stop(monkeypatch, capsys, session_id="S3")

    assert decision is None or decision.get("decision") != "block", decision


def test_zone_overlap_blocks_involved_session(repo, monkeypatch, capsys):
    """Same collision, seen by S1 (involved): blocking kept."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    for s in ("task-a.md", "task-b.md"):
        (dirs["TODO"] / s).write_text(f"# {s}\n", encoding="utf-8")
    _lock_sessions(root, {"S1": ["task-a.md"], "S2": ["task-b.md"]})

    decision = _run_stop(monkeypatch, capsys, session_id="S1")

    assert decision and decision.get("decision") == "block", decision


def test_in_progress_task_slugs_ignores_expired_session_lock(repo):
    """A dead session (since > LOCK_TTL, not purged yet: dashboard or
    non-Stop read) must not make its batch active."""
    root, dirs, ctx = repo
    old = (datetime.datetime.now() - h.LOCK_TTL - datetime.timedelta(minutes=1)).isoformat()
    fresh = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    locks = {"sessions": {
        "DEAD": {"tasks": ["dead.md"], "since": old},
        "LIVE": {"tasks": ["alive.md"], "since": fresh},
    }}

    assert h.in_progress_task_slugs(locks) == {"alive.md"}


def test_check_zone_overlaps_observer_view_blocks_cross_session(repo):
    """observer=True (dashboard): observer view, any
    cross-session conflict is still reported as blocking."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    _lock_sessions(root, {"S1": ["task-a.md"], "S2": ["task-b.md"]})
    locks = h.load_locks()

    warnings, blocking = h.check_zone_overlaps(
        h.load_sections(), h.in_progress_task_slugs(locks), locks, observer=True)

    assert blocking and not warnings


# --- Lock shared between the main checkout and worktrees (task verrou-partage-worktrees) ---

def _fake_main(tmp_path, with_crew=True):
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    if with_crew:
        (main / "crew" / "CLAUDE_CONTEXT").mkdir(parents=True)
    return main


def _fake_worktree(tmp_path, main, gitdir_text=None, commondir="../.."):
    wt = tmp_path / "wt"
    wt.mkdir()
    gitdir = main / ".git" / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text(commondir + "\n", encoding="utf-8")
    (wt / ".git").write_text(f"gitdir: {gitdir_text or gitdir}\n", encoding="utf-8")
    return wt


def test_main_root_from_worktree_git_file(tmp_path):
    main = _fake_main(tmp_path)
    wt = _fake_worktree(tmp_path, main)
    assert h._resolve_main_root(wt) == main.resolve()


def test_main_root_is_root_when_git_is_dir(tmp_path):
    main = _fake_main(tmp_path)
    assert h._resolve_main_root(main) == main


def test_main_root_relative_gitdir_and_backslashes(tmp_path):
    main = _fake_main(tmp_path)
    wt = _fake_worktree(tmp_path, main, gitdir_text=r"..\main\.git\worktrees\wt", commondir=r"..\..")
    assert h._resolve_main_root(wt) == main.resolve()


def test_main_root_fallback_no_git(tmp_path):
    assert h._resolve_main_root(tmp_path) == tmp_path


def test_main_root_fallback_bare_repo(tmp_path):
    bare = tmp_path / "bare.git"
    (bare / "worktrees" / "wt").mkdir(parents=True)
    (bare / "worktrees" / "wt" / "commondir").write_text("../..\n", encoding="utf-8")
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {bare / 'worktrees' / 'wt'}\n", encoding="utf-8")
    assert h._resolve_main_root(wt) == wt


def test_main_root_fallback_main_without_crew(tmp_path):
    main = _fake_main(tmp_path, with_crew=False)
    wt = _fake_worktree(tmp_path, main)
    assert h._resolve_main_root(wt) == wt


def test_main_root_fallback_unreadable_git_file(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text("garbage\n", encoding="utf-8")
    assert h._resolve_main_root(wt) == wt


def _as_checkout(monkeypatch, root, main):
    """Points the module at `root` (main checkout or worktree) as
    if the hook were running there: local ROOT/CTX/BATCH_FILE, shared lock."""
    monkeypatch.setattr(h, "ROOT", root)
    monkeypatch.setattr(h, "MAIN_ROOT", main)
    monkeypatch.setattr(h, "CTX", root / "crew" / "CLAUDE_CONTEXT")
    monkeypatch.setattr(h, "BATCH_FILE", root / "crew" / "CLAUDE_BATCH.md")
    _, locks_file, locks_mutex = h._shared_lock_paths(root)
    monkeypatch.setattr(h, "LOCKS_FILE", locks_file)
    monkeypatch.setattr(h, "LOCKS_MUTEX", locks_mutex)


def _two_checkouts(tmp_path):
    main = _fake_main(tmp_path)
    wt = _fake_worktree(tmp_path, main)
    (wt / "crew" / "CLAUDE_CONTEXT").mkdir(parents=True)
    for r in (main, wt):
        (r / "crew" / "CLAUDE_BATCH.md").write_text(
            "# Batching\n\n## Batch Zone1\n\nZone : `zone1/`\n\n- `t.md`\n", encoding="utf-8")
    return main.resolve(), wt


def _seed_lock(session_id, now=None):
    since = (now or datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    h.save_locks({"sessions": {session_id: {
        "batch": "Batch Zone1", "tasks": ["t.md"],
        "worktree": "../main-batch-zone1", "branch": "crew/batch-zone1", "since": since}}})


def test_worktree_session_writes_main_lock(tmp_path):
    main, wt = _two_checkouts(tmp_path)
    resolved_main, locks_file, mutex = h._shared_lock_paths(wt)
    assert resolved_main == main
    assert locks_file == main / "crew" / "CLAUDE_CONTEXT" / "crew_lock.json"
    assert mutex.parent == locks_file.parent


def test_gate_main_blocks_zone_claimed_from_worktree(tmp_path, monkeypatch):
    main, wt = _two_checkouts(tmp_path)
    _as_checkout(monkeypatch, wt, main)
    _seed_lock("WT")
    _as_checkout(monkeypatch, main, main)
    with pytest.raises(SystemExit) as ei:
        h.gate_pretooluse({"tool_name": "Edit", "session_id": "MAIN",
                           "tool_input": {"file_path": str(main / "zone1" / "x.py")}})
    assert ei.value.code == 2


def test_gate_worktree_blocks_zone_claimed_from_main(tmp_path, monkeypatch):
    main, wt = _two_checkouts(tmp_path)
    _as_checkout(monkeypatch, main, main)
    _seed_lock("MAIN")
    _as_checkout(monkeypatch, wt, main)
    with pytest.raises(SystemExit) as ei:
        h.gate_pretooluse({"tool_name": "Edit", "session_id": "WT",
                           "tool_input": {"file_path": str(wt / "zone1" / "x.py")}})
    assert ei.value.code == 2


def test_worktree_paths_use_main_root_name(tmp_path, monkeypatch):
    main, wt = _two_checkouts(tmp_path)
    _as_checkout(monkeypatch, wt, main)
    assert h._worktree_paths_for("Batch X") == ("../main-batch-x", "crew/batch-x")


def test_throttle_warned_scoped_per_checkout(tmp_path, monkeypatch):
    main, wt = _two_checkouts(tmp_path)
    locks = {"sessions": {}}
    now = datetime.datetime(2026, 8, 29, 10, 0, 0)
    _as_checkout(monkeypatch, main, main)
    assert h._throttle_warnings("batch", ["same"], locks, now) == ["same"]
    _as_checkout(monkeypatch, wt, main)
    assert h._throttle_warnings("batch", ["same"], locks, now) == ["same"]
    assert h._throttle_warnings("batch", ["same"], locks, now) == []


def test_batch_locks_md_not_written_from_worktree(tmp_path, monkeypatch):
    main, wt = _two_checkouts(tmp_path)
    _as_checkout(monkeypatch, wt, main)
    out = wt / "crew" / "CLAUDE_CONTEXT" / "BATCH_LOCKS.md"
    monkeypatch.setattr(h, "BATCH_LOCKS_MD", out)
    h.regen_batch_locks_md([], {"sessions": {}}, set())
    assert not out.exists()
    _as_checkout(monkeypatch, main, main)
    out_main = main / "crew" / "CLAUDE_CONTEXT" / "BATCH_LOCKS.md"
    monkeypatch.setattr(h, "BATCH_LOCKS_MD", out_main)
    h.regen_batch_locks_md([], {"sessions": {}}, set())
    assert out_main.exists()


def test_legacy_worktree_lock_merged_then_removed(tmp_path, monkeypatch):
    main, wt = _two_checkouts(tmp_path)
    _as_checkout(monkeypatch, main, main)
    old = (datetime.datetime.now() - datetime.timedelta(minutes=30)).isoformat()
    new = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    h.save_locks({"sessions": {"A": {"tasks": ["a.md"], "since": old},
                               "B": {"tasks": ["old-b.md"], "since": old}}})
    legacy = wt / "crew" / "CLAUDE_CONTEXT" / "crew_lock.json"
    legacy.write_text(json.dumps({"sessions": {"B": {"tasks": ["new-b.md"], "since": new},
                                               "C": {"tasks": ["c.md"], "since": new}}}), encoding="utf-8")
    _as_checkout(monkeypatch, wt, main)

    h.migrate_legacy_worktree_lock()

    sessions = h.load_locks()["sessions"]
    assert sessions["A"]["tasks"] == ["a.md"]
    assert sessions["B"]["tasks"] == ["new-b.md"]  # the most recent since wins
    assert sessions["C"]["tasks"] == ["c.md"]
    assert not legacy.exists()


def test_task_state_snapshot_stays_local():
    """SNAP (per-checkout state diff) stays under ROOT; only the lock migrates."""
    assert h.SNAP == h.ROOT / "crew" / "CLAUDE_CONTEXT" / ".task_state.json"
    assert h.LOCKS_FILE == h.MAIN_ROOT / "crew" / "CLAUDE_CONTEXT" / "crew_lock.json"


def test_main_root_fallback_main_without_claude_context(tmp_path):
    main = _fake_main(tmp_path, with_crew=False)
    (main / "crew").mkdir()
    wt = _fake_worktree(tmp_path, main)
    assert h._resolve_main_root(wt) == wt


# --- batch identity independent of the status (header truncated at the first " · ") ---

def _status_sections(status):
    header = f"Batch Yuna · {status}" if status else "Batch Yuna"
    return [{"header": header, "slugs": ["a.md", "b.md"], "zone_paths": []}]


def test_batch_key_strips_status_suffix():
    assert h._batch_key("Batch Yuna determinism · 🔄 in progress (next: 04)") == "Batch Yuna determinism"
    assert h._batch_key("Batch A — Audit ECC : tokens") == "Batch A — Audit ECC : tokens"
    assert h._batch_key("  Batch X  ·  not started ") == "Batch X"


def test_header_status_change_no_incoherence(capsys):
    now = datetime.datetime(2026, 10, 3, 10, 0, 0)
    locks = {"sessions": {}}
    h._register_task_lock("a.md", "S1", locks, now, _status_sections("🔄 in progress (next: 04)"))
    h._register_task_lock("b.md", "S1", locks, now, _status_sections("🔄 in progress (next: 05)"))
    assert "inconsistency" not in capsys.readouterr().err
    assert locks["sessions"]["S1"]["batch"] == "Batch Yuna"


def test_worktree_slug_stable_across_status_change():
    assert h._worktree_paths_for("Batch Yuna · not started") == h._worktree_paths_for(
        "Batch Yuna · 🔄 in progress (next: 04)")
    assert h._batch_slug("Batch Yuna · not started") == "yuna"


def test_legacy_long_batch_key_matches_normalized(capsys):
    now = datetime.datetime(2026, 10, 3, 10, 0, 0)
    legacy = "Batch Yuna · 🔄 in progress (next: 04)"
    locks = {"sessions": {"S1": {"batch": legacy, "tasks": ["a.md"], "worktree": None,
                                  "branch": None, "since": now.isoformat()}}}
    h._register_task_lock("b.md", "S1", locks, now, _status_sections("🔄 in progress (next: 05)"))
    assert "inconsistency" not in capsys.readouterr().err


def test_different_batch_still_triggers_incoherence(capsys):
    now = datetime.datetime(2026, 10, 3, 10, 0, 0)
    locks = {"sessions": {"S1": {"batch": "Batch Other · not started", "tasks": ["x.md"],
                                  "worktree": None, "branch": None, "since": now.isoformat()}}}
    h._register_task_lock("a.md", "S1", locks, now, _status_sections("not started"))
    assert "inconsistency" in capsys.readouterr().err
    assert locks["sessions"]["S1"]["batch"] == "Batch Other · not started"


# --- .gate_armed marker (shell pre-filter of the PreToolUse hook) -------------

def _sess(worktree=None):
    return {"batch": None, "tasks": [], "worktree": worktree, "branch": None,
            "since": datetime.datetime.now().isoformat()}


@pytest.mark.parametrize("n_sessions,armed", [(1, False), (2, True)])
def test_save_locks_arms_gate_marker_from_two_sessions(repo, n_sessions, armed):
    root, dirs, ctx = repo
    h.save_locks({"sessions": {f"S{i}": _sess() for i in range(n_sessions)}})
    assert (ctx / ".gate_armed").exists() is armed


def test_save_locks_back_to_one_or_zero_sessions_removes_marker(repo):
    root, dirs, ctx = repo
    h.save_locks({"sessions": {"A": _sess(), "B": _sess()}})
    h.save_locks({"sessions": {"A": _sess()}})
    assert not (ctx / ".gate_armed").exists()
    h.save_locks({"sessions": {"A": _sess(), "B": _sess()}})
    h.save_locks({"sessions": {}})
    assert not (ctx / ".gate_armed").exists()


def test_gate_marker_idempotent_and_tolerates_errors(repo, monkeypatch):
    root, dirs, ctx = repo
    two = {"sessions": {"A": _sess(), "B": _sess()}}
    h.save_locks(two)
    h.save_locks(two)  # re-arming raises nothing
    assert (ctx / ".gate_armed").exists()
    # Unreadable/unwritable marker: best-effort, never an exception.
    (ctx / ".gate_armed").unlink()
    (ctx / ".gate_armed").mkdir()  # a folder in place of the file -> unlink/write fail
    h.save_locks({"sessions": {"A": _sess()}})
    h.save_locks(two)  # does not raise either


def test_gate_marker_armed_in_main_and_each_registered_worktree(repo):
    """The shell pre-filter tests $CLAUDE_PROJECT_DIR/... (= current worktree) while
    the lock lives in the main checkout: the marker must be set in both."""
    root, dirs, ctx = repo
    wt_a = root.parent / f"{root.name}-batch-a"
    wt_b = root.parent / f"{root.name}-batch-b"
    for wt in (wt_a, wt_b):
        (wt / "crew" / "CLAUDE_CONTEXT").mkdir(parents=True)
    locks = {"sessions": {"A": _sess(f"../{root.name}-batch-a"),
                          "B": _sess(f"../{root.name}-batch-b")}}
    h.save_locks(locks)
    for wt in (wt_a, wt_b):
        assert (wt / "crew" / "CLAUDE_CONTEXT" / ".gate_armed").exists()
    assert (ctx / ".gate_armed").exists()
    # Back to 1 session: markers removed everywhere, including the worktree
    # of the session that just disappeared from the lock.
    h.save_locks({"sessions": {"A": _sess(f"../{root.name}-batch-a")}})
    for wt in (wt_a, wt_b):
        assert not (wt / "crew" / "CLAUDE_CONTEXT" / ".gate_armed").exists()
    assert not (ctx / ".gate_armed").exists()


# --- CREW_HOOK_PROFILE=minimal escape hatch -------------------------------

def _run_main_pretooluse(monkeypatch):
    calls = []
    monkeypatch.setattr(h, "gate_pretooluse", lambda payload: calls.append(payload))
    stdin = json.dumps({"hook_event_name": "PreToolUse", "session_id": "S",
                        "tool_name": "Edit", "tool_input": {"file_path": "x"}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    h.main()
    return calls


def test_profile_minimal_skips_pretooluse_gate(repo, monkeypatch):
    monkeypatch.setenv("CREW_HOOK_PROFILE", "minimal")
    assert _run_main_pretooluse(monkeypatch) == []


def test_profile_default_runs_pretooluse_gate(repo, monkeypatch):
    monkeypatch.delenv("CREW_HOOK_PROFILE", raising=False)
    assert len(_run_main_pretooluse(monkeypatch)) == 1


def test_profile_minimal_keeps_stop_sync(repo, monkeypatch):
    """Stop/SessionEnd keep running under `minimal` (index, locks): only PreToolUse is skipped."""
    monkeypatch.setenv("CREW_HOOK_PROFILE", "minimal")
    called = []
    monkeypatch.setattr(h, "regen_index", lambda name, d: called.append(name) or [])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"hook_event_name": "Stop", "session_id": "S"})))
    try:
        h.main()
    except SystemExit:
        pass
    assert called


# --- SessionStart: crew digest (task continuite-session-sessionstart-precompact) ---

def _digest_kwargs(**over):
    base = dict(current=[], paused=[], batches=[], other_locks=[], warnings=[], history=[])
    base.update(over)
    return base


def test_digest_content_and_order():
    d = h.build_session_digest(**_digest_kwargs(
        current=[("a.md", "Task A", 1, 4)],
        paused=[("p.md", "Task P", 0, 2)],
        batches=[("Batch X", "`src/`")],
        other_locks=["S2: b.md"],
        warnings=["[batch] Task not categorized : `z.md`"],
        history=["2026-10-01 — done Y"],
    ))
    for needle in ("a.md", "Task A", "1/4", "p.md", "Batch X", "`src/`", "S2: b.md", "z.md", "done Y"):
        assert needle in d
    pos = [d.index(n) for n in ("a.md", "p.md", "Batch X", "S2: b.md", "z.md", "done Y")]
    assert pos == sorted(pos)


def test_digest_cap_truncates_and_keeps_head_sections():
    current = [(f"t{i}.md", "T" * 120, 0, 3) for i in range(20)]
    d = h.build_session_digest(**_digest_kwargs(current=current, history=["HISTORIQUE-ENTRY"]))
    assert len(d) <= 2000
    assert "t0.md" in d
    assert "(+" in d
    assert "HISTORIQUE-ENTRY" not in d


def test_digest_empty_crew_is_one_line():
    d = h.build_session_digest(**_digest_kwargs())
    assert d.strip() and "\n" not in d.strip()


def test_session_digest_reads_files_readonly(repo, monkeypatch):
    root, dirs, ctx = repo
    (dirs["CURRENT_TASKS"] / "a.md").write_text("# Task A\n\n- [x] one\n- [ ] two\n", encoding="utf-8")
    h.BATCH_FILE.write_text("# Batching\n\n## Batch A — X\n\nZone : `src/`\n\n1. `a.md` — t\n", encoding="utf-8")
    (ctx / "HISTORIQUE.md").write_text("# Historique\n\n## H4 newest\n\n## H3\n\n## H2\n\n## H1 oldest\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in (root / "crew").rglob("*") if p.is_file()}
    d = h.session_digest("S1")
    assert "a.md" in d and "1/2" in d and "H4 newest" in d and "H1 oldest" not in d and "Batch A" in d
    after = {p: p.read_bytes() for p in (root / "crew").rglob("*") if p.is_file()}
    assert before == after


def test_main_sessionstart_emits_additional_context(repo, monkeypatch, capsys):
    monkeypatch.delenv("CREW_SESSION_DIGEST", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"hook_event_name": "SessionStart", "session_id": "S1"})))
    h.main()
    out = json.loads(capsys.readouterr().out)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart" and hso["additionalContext"]


def test_main_sessionstart_off_switch_is_silent(repo, monkeypatch, capsys):
    monkeypatch.setenv("CREW_SESSION_DIGEST", "off")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"hook_event_name": "SessionStart", "session_id": "S1"})))
    h.main()
    assert capsys.readouterr().out == ""


def _run_sessionstart(monkeypatch, capsys, **extra):
    monkeypatch.delenv("CREW_SESSION_DIGEST", raising=False)
    payload = {"hook_event_name": "SessionStart", "session_id": "S1", "source": "startup", **extra}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    return json.loads(capsys.readouterr().out)["hookSpecificOutput"]


def test_sessionstart_title_from_single_unlocked_current_task(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    _put(dirs, "CURRENT_TASKS", "a1.md")
    assert _run_sessionstart(monkeypatch, capsys)["sessionTitle"] == "a1"


def test_sessionstart_title_prefers_own_lock_over_others(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    _put(dirs, "CURRENT_TASKS", "a1.md")
    _put(dirs, "CURRENT_TASKS", "b1.md")
    now = datetime.datetime.now().isoformat()
    h.save_locks({"sessions": {
        "S1": {"batch": None, "tasks": ["b1.md"], "worktree": None, "branch": None, "since": now},
        "S2": {"batch": None, "tasks": ["a1.md"], "worktree": None, "branch": None, "since": now},
    }})
    assert _run_sessionstart(monkeypatch, capsys)["sessionTitle"] == "b1"


def test_sessionstart_color_title_when_ambiguous_or_after_clear(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    _put(dirs, "CURRENT_TASKS", "a1.md")
    _put(dirs, "CURRENT_TASKS", "b1.md")
    assert _run_sessionstart(monkeypatch, capsys)["sessionTitle"] in h.SESSION_COLORS
    assert _run_sessionstart(monkeypatch, capsys, source="clear")["sessionTitle"] in h.SESSION_COLORS
    # a single task takes priority over the color
    (dirs["CURRENT_TASKS"] / "b1.md").unlink()
    assert _run_sessionstart(monkeypatch, capsys)["sessionTitle"] == "a1"


def test_sessionstart_no_title_when_user_named_or_compact(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    _put(dirs, "CURRENT_TASKS", "a1.md")
    assert "sessionTitle" not in _run_sessionstart(monkeypatch, capsys, session_title="my name")
    assert "sessionTitle" not in _run_sessionstart(monkeypatch, capsys, source="compact")


def test_session_color_is_stable_per_session_id():
    assert h.session_color("S1") == h.session_color("S1")
    assert len({h.session_color(f"S{i}") for i in range(40)}) > 1


def test_session_digest_none_without_crew_dir(repo, monkeypatch, tmp_path):
    monkeypatch.setattr(h, "CREW", tmp_path / "absent")
    assert h.session_digest("S1") is None


def test_session_digest_survives_unreadable_batch_file(repo):
    root, dirs, ctx = repo
    (dirs["CURRENT_TASKS"] / "a.md").write_text("# Task A\n- [ ] x\n", encoding="utf-8")
    h.BATCH_FILE.write_bytes(bytes([0xff, 0xfe, 0, 0x62]))
    assert "a.md" in h.session_digest("S1")


def test_digest_tiny_cap_never_exceeds():
    d = h.build_session_digest(**_digest_kwargs(current=[("a.md", "T", 0, 1)]), cap=10)
    assert len(d) <= 10


# --- next-task: deterministic task choice for /crew-start -----------

def _batch_md(*sections):
    return "# Batching\n\n" + "\n".join(sections)


def _sec(name, zone, *slugs):
    refs = "\n".join(f"{i}. `{s}` — t" for i, s in enumerate(slugs, 1))
    return f"## Batch {name}\n\nZone : `{zone}`\n\n{refs}\n"


def _put(dirs, folder, slug, body="# T\n- [ ] x\n"):
    (dirs[folder] / slug).write_text(body, encoding="utf-8")


def _lock(ctx, sid, tasks):
    data = {"sessions": {sid: {"batch": None, "tasks": tasks, "worktree": None, "branch": None,
                               "since": datetime.datetime.now().isoformat()}}}
    (ctx / "crew_lock.json").write_text(json.dumps(data), encoding="utf-8")


def test_next_task_nothing_when_all_empty(repo):
    assert h.next_task("S1")["action"] == "none"


def test_next_task_starts_first_todo_of_first_inactive_batch(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md", "a2.md"), _sec("B", "src/b/", "b1.md")), encoding="utf-8")
    for s in ("a2.md", "a1.md", "b1.md"):
        _put(dirs, "TODO", s)
    r = h.next_task("S1")
    assert (r["action"], r["task"]) == ("start", "a1.md")  # batch order, not alphabetical/reversed
    assert r["batch"].startswith("Batch A")
    assert r["worktree"].endswith("-batch-a") and r["branch"] == "crew/batch-a"


def test_next_task_resumes_current_task_not_locked(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(dirs, "CURRENT_TASKS", "a1.md", "# T\n- [x] x\n- [ ] y\n")
    r = h.next_task("S1")
    assert (r["action"], r["task"]) == ("resume", "a1.md")


def test_next_task_resume_prefers_most_advanced(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md", "a2.md")), encoding="utf-8")
    _put(dirs, "CURRENT_TASKS", "a1.md", "# T\n- [x] x\n- [ ] y\n- [ ] z\n")
    _put(dirs, "CURRENT_TASKS", "a2.md", "# T\n- [x] x\n- [x] y\n- [ ] z\n")
    assert h.next_task("S1")["task"] == "a2.md"


def test_next_task_locked_current_falls_back_to_independent_todo(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md"), _sec("B", "src/b/", "b1.md")), encoding="utf-8")
    _put(dirs, "CURRENT_TASKS", "a1.md")
    _put(dirs, "TODO", "b1.md")
    _lock(ctx, "OTHER", ["a1.md"])
    r = h.next_task("S1")
    assert (r["action"], r["task"]) == ("start", "b1.md")
    assert any(s["slug"] == "a1.md" and "lock" in s["reason"] for s in r["skipped"])


def test_next_task_own_lock_is_not_a_conflict(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(dirs, "CURRENT_TASKS", "a1.md")
    _lock(ctx, "S1", ["a1.md"])
    assert h.next_task("S1")["action"] == "resume"


def test_next_task_skips_batch_active_in_other_session_even_for_todo_sibling(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md", "a2.md")), encoding="utf-8")
    _put(dirs, "CURRENT_TASKS", "a1.md")
    _put(dirs, "TODO", "a2.md")
    _lock(ctx, "OTHER", ["a1.md"])
    r = h.next_task("S1")
    assert r["action"] == "none"
    assert {s["slug"] for s in r["skipped"]} >= {"a1.md", "a2.md"}


def test_next_task_skips_batch_with_paused_task(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md", "a2.md"), _sec("B", "src/b/", "b1.md")), encoding="utf-8")
    _put(dirs, "PAUSED", "a1.md")
    _put(dirs, "TODO", "a2.md")
    _put(dirs, "TODO", "b1.md")
    r = h.next_task("S1")
    assert (r["action"], r["task"]) == ("start", "b1.md")
    assert r["paused"] == ["a1.md"]


def test_next_task_skips_candidate_whose_zone_overlaps_active_batch(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/", "a1.md"), _sec("B", "src/b/", "b1.md"), _sec("C", "docs/", "c1.md")), encoding="utf-8")
    _put(dirs, "CURRENT_TASKS", "a1.md")
    _lock(ctx, "OTHER", ["a1.md"])
    _put(dirs, "TODO", "b1.md")
    _put(dirs, "TODO", "c1.md")
    r = h.next_task("S1")
    assert (r["action"], r["task"]) == ("start", "c1.md")
    assert any(s["slug"] == "b1.md" and "overlaps" in s["reason"] for s in r["skipped"])


def test_next_task_unclassified_todo_asks_classification(repo):
    root, dirs, ctx = repo
    # "À classer" is the literal French section header the engine parses
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/")) + "\n## À classer\n\n- `orphan.md`\n", encoding="utf-8")
    _put(dirs, "TODO", "orphan.md")
    _put(dirs, "TODO", "other-orphan.md")
    r = h.next_task("S1")
    assert r["action"] == "classify"
    assert r["unclassified"] == ["orphan.md", "other-orphan.md"]


def test_next_task_ignores_index_readme_and_icebox(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(dirs, "ICEBOX", "a1.md")
    assert h.next_task("S1")["action"] == "none"


def test_next_task_is_readonly(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(dirs, "TODO", "a1.md")
    before = {p: p.read_bytes() for p in (root / "crew").rglob("*") if p.is_file()}
    h.next_task("S1")
    assert before == {p: p.read_bytes() for p in (root / "crew").rglob("*") if p.is_file()}


def test_main_next_task_cli_prints_json(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(dirs, "TODO", "a1.md")
    monkeypatch.setattr(sys, "argv", ["crew_hook.py", "next-task"])
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "S1")
    h.main()
    assert json.loads(capsys.readouterr().out)["task"] == "a1.md"


# --- count / status: deterministic reports (crew-count / crew-status skills) ---

def test_count_launchable_active_and_overlap(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(
        _sec("A", "src/a/", "a1.md"),
        _sec("B", "src/", "b1.md"),          # overlaps A (active) -> excluded
        _sec("C", "docs/", "c1.md"),
        _sec("D", "docs/guide/", "d1.md"),   # overlaps C (launchable) -> excluded
        _sec("E", "x/", "e1.md") .replace("`e1.md`", "~~`e1.md`~~"),  # all struck through -> ignored
    ), encoding="utf-8")
    _put(dirs, "CURRENT_TASKS", "a1.md")
    for s in ("b1.md", "c1.md", "d1.md"):
        _put(dirs, "TODO", s)
    r = h.count_batches()
    assert r["launchable_count"] == 1
    assert [b["name"] for b in r["launchable"]] == ["Batch C"]
    assert [b["name"] for b in r["active"]] == ["Batch A"]
    ex = {b["name"]: b["reason"] for b in r["excluded"]}
    assert "overlaps" in ex["Batch B"] and "overlaps" in ex["Batch D"]
    assert "Batch E" not in ex and r["launchable"][0]["remaining"] == 1


def test_count_ignores_template_placeholders_and_reports_them(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("<A>", "<files/modules>", "<slug>.md")), encoding="utf-8")
    r = h.count_batches()
    assert r["launchable_count"] == 0 and r["placeholders"] == ["Batch <A>"]


def test_status_reports_current_paused_orphans_and_overlaps(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/", "a1.md"), _sec("B", "src/b/", "b1.md")), encoding="utf-8")
    _put(dirs, "CURRENT_TASKS", "a1.md", "# T\n- [x] x\n- [ ] y\n")
    _put(dirs, "PAUSED", "b1.md")
    _put(dirs, "TODO", "orphan.md")
    (dirs["TESTS/IA"] / "feat.md").write_text("- [x] ok\n- [ ] todo\n", encoding="utf-8")
    (dirs["TESTS/IA"] / "done.md").write_text("- [x] ok\n", encoding="utf-8")
    r = h.crew_status()
    assert r["current"] == [{"slug": "a1.md", "done": 1, "total": 2}]
    assert r["paused"] == ["b1.md"]
    assert r["todo_orphans"] == ["orphan.md"]
    assert r["tests_ia_unchecked"] == [{"file": "feat.md", "unchecked": 1}]
    assert [b["name"] for b in r["active_batches"]] == ["Batch A", "Batch B"]
    assert len(r["zone_overlaps"]) == 1


def test_status_is_readonly(repo):
    root, dirs, ctx = repo
    before = {p: p.read_bytes() for p in (root / "crew").rglob("*") if p.is_file()}
    h.crew_status(); h.count_batches()
    assert before == {p: p.read_bytes() for p in (root / "crew").rglob("*") if p.is_file()}


@pytest.mark.parametrize("cmd", ["count", "status"])
def test_main_report_cli_prints_json(repo, monkeypatch, capsys, cmd):
    monkeypatch.setattr(sys, "argv", ["crew_hook.py", cmd])
    h.main()
    assert isinstance(json.loads(capsys.readouterr().out), dict)


def test_count_report_gives_exact_count_and_session_titles(repo):
    root, dirs, ctx = repo
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md", "a2.md"),
                                      _sec("B", "src/b/", "b1.md")), encoding="utf-8")
    r = h.count_batches()
    assert [b["task"] for b in r["launchable"]] == ["a1", "b1"]
    assert r["report"].startswith("**2 terminals in parallel**")
    assert "| `a1` | Batch A | src/a/ |" in r["report"]


# --- Local ignore list: another dev's tasks that /crew-start must not start ---

@pytest.fixture
def ign(repo, monkeypatch):
    root, dirs, ctx = repo
    monkeypatch.setattr(h, "IGNORED_FILE", ctx / "crew_ignored.json", raising=False)
    return dirs


def test_ignore_snapshot_makes_next_task_skip_existing_todo(ign):
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md", "a2.md")), encoding="utf-8")
    _put(ign, "TODO", "a1.md")
    _put(ign, "TODO", "a2.md")
    assert h.ignore_cli(["snapshot", "--owner", "Bob"])["ok"] is True
    r = h.next_task("S1")
    assert r["action"] == "none"
    assert {"slug": "a1.md", "reason": "ignored locally (task of Bob)"} in r["skipped"]


def test_ignore_snapshot_leaves_later_todo_startable(ign):
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md", "mine.md")), encoding="utf-8")
    _put(ign, "TODO", "a1.md")
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    _put(ign, "TODO", "mine.md")  # added after the snapshot
    r = h.next_task("S1")
    assert (r["action"], r["task"]) == ("start", "mine.md")


def test_ignored_todo_is_not_reported_unclassified(ign):
    _put(ign, "TODO", "orphan.md")  # in no batch
    assert h.next_task("S1")["unclassified"] == ["orphan.md"]
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    r = h.next_task("S1")
    assert r["unclassified"] == [] and r["action"] == "none"


def test_ignore_remove_makes_task_startable_again(ign):
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(ign, "TODO", "a1.md")
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    assert h.ignore_cli(["remove", "a1.md"])["ignored"] == []
    assert h.next_task("S1")["task"] == "a1.md"


def test_ignore_add_list_and_idempotent_snapshot(ign):
    _put(ign, "TODO", "a1.md")
    h.ignore_cli(["add", "x.md"])
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    assert h.ignore_cli(["list"])["ignored"] == ["a1.md", "x.md"]


def test_ignore_cli_rejects_unknown_subcommand_and_missing_slug(ign):
    assert h.ignore_cli(["nope"])["ok"] is False
    assert h.ignore_cli(["add"])["ok"] is False
    assert h.ignore_cli([])["ok"] is False


def test_ignore_corrupt_file_degrades_to_empty(ign):
    h.IGNORED_FILE.write_text("{not json", encoding="utf-8")
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(ign, "TODO", "a1.md")
    assert h.next_task("S1")["task"] == "a1.md"


# --- Collab mode: dev name + remote claims, switched on by /crew-collab only ---

def _cfg(ctx):
    return (ctx / "CREW_CONFIG.md").read_text(encoding="utf-8")


def test_collab_on_enables_claims_and_sets_owner_name(ign):
    assert h.claims_enabled() is False
    r = h.collab_cli(["on", "--name", "Dana"])
    assert r["ok"] is True and r["name"] == "Dana"
    assert h.claims_enabled() is True
    assert h._claims_identity() == "Dana"


def test_collab_on_keeps_other_config_lines_and_is_idempotent(ign):
    cfg = h.CTX / "CREW_CONFIG.md"
    cfg.write_text("# My config\n\nremote_claims : false\nclaims_remote : upstream\n", encoding="utf-8")
    h.collab_cli(["on", "--name", "A"])
    h.collab_cli(["on", "--name", "B"])
    txt = _cfg(h.CTX)
    assert txt.count("remote_claims") == 1 and txt.count("collab_name") == 1
    assert "# My config" in txt and "claims_remote : upstream" in txt
    assert h._claims_identity() == "B"


@pytest.mark.parametrize("argv", [["on"], ["on", "--name", "   "], ["on", "--name", "a\nremote_claims : false"], ["on", "--name", "x" * 200]])
def test_collab_on_rejects_missing_or_unsafe_name(ign, argv):
    assert h.collab_cli(argv)["ok"] is False
    assert not (h.CTX / "CREW_CONFIG.md").exists() or h.claims_enabled() is False


def test_collab_off_resets_to_base_form(ign):
    _put(ign, "TODO", "a1.md")
    h.collab_cli(["on", "--name", "Dana"])
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    assert h.collab_cli(["off"])["ok"] is True
    assert h.claims_enabled() is False
    assert "collab_name" not in _cfg(h.CTX)
    assert not h.IGNORED_FILE.exists()
    assert h._claims_identity() != "Dana"


def test_collab_status_reports_mode_name_and_ignored_count(ign):
    off = h.collab_cli(["status"])
    assert (off["ok"], off["collab"]) == (True, False)
    _put(ign, "TODO", "a1.md")
    h.collab_cli(["on", "--name", "Dana"])
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    on = h.collab_cli(["status"])
    assert (on["collab"], on["name"], on["ignored"]) == (True, "Dana", 1)
    assert on["people"] == [{"name": "Bob", "tasks": 1, "me": False}]


def test_ignore_snapshot_owner_is_named_in_skip_reason_and_list(ign):
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(ign, "TODO", "a1.md")
    assert h.ignore_cli(["snapshot", "--owner", "Bob"])["ok"] is True
    assert h.ignore_cli(["list"])["by_owner"] == {"Bob": 1}
    assert {"slug": "a1.md", "reason": "ignored locally (task of Bob)"} in h.next_task("S1")["skipped"]
    h.ignore_cli(["snapshot"])  # without --owner: keeps the known owner
    assert h.ignore_cli(["list"])["by_owner"] == {"Bob": 1}


def test_ignore_off_deletes_the_file(ign):
    _put(ign, "TODO", "a1.md")
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    assert h.IGNORED_FILE.exists()
    assert h.ignore_cli(["off"])["ignored"] == []
    assert not h.IGNORED_FILE.exists()
    assert h.ignore_cli(["off"])["ok"] is True  # idempotent


# --- Per-task owner: mention in the TODO, remote claim, else --owner ---

def test_snapshot_uses_owner_mention_written_in_the_todo(ign):
    _put(ign, "TODO", "a1.md", body="# T\n- **Owner** : Alice\n- [ ] x\n")
    # "Assigné à" is a French owner alias still accepted by the engine
    _put(ign, "TODO", "a2.md", body="# T\nAssigné à : Bob\n- [ ] x\n")
    r = h.ignore_cli(["snapshot"])
    assert r["unmarked"] == []
    assert h.ignore_cli(["list"])["by_owner"] == {"Alice": 1, "Bob": 1}


def test_snapshot_skips_tasks_marked_with_my_own_name(ign):
    h.collab_cli(["on", "--name", "Dana"])
    _put(ign, "TODO", "mine.md", body="# T\nOwner : dana\n- [ ] x\n")
    _put(ign, "TODO", "theirs.md", body="# T\nOwner : Alice\n- [ ] x\n")
    h.ignore_cli(["snapshot"])
    assert h.ignore_cli(["list"])["ignored"] == ["theirs.md"]


def test_snapshot_ignores_unmarked_by_default_as_unassigned_and_owner_option_names_them(ign):
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "plain.md")), encoding="utf-8")
    _put(ign, "TODO", "marked.md", body="# T\nOwner : Alice\n- [ ] x\n")
    _put(ign, "TODO", "plain.md")
    r = h.ignore_cli(["snapshot"])
    assert r["unmarked"] == ["plain.md"]
    assert h.ignore_cli(["list"])["by_owner"] == {"Alice": 1, "(unassigned)": 1}
    assert h.next_task("S1")["action"] == "none"  # never started, without answering anything
    h.ignore_cli(["snapshot", "--owner", "Bob"])
    assert h.ignore_cli(["list"])["by_owner"] == {"Alice": 1, "Bob": 1}  # Alice keeps her mention
    assert h.ignore_cli(["snapshot"])["unmarked"] == []



def test_snapshot_uses_remote_claim_owner_without_asking(ign, monkeypatch):
    h.collab_cli(["on", "--name", "Dana"])
    _put(ign, "TODO", "c1.md")
    _put(ign, "TODO", "c2.md")
    claims = {"c1.md": {"status": "current", "owner": "carol"}, "c2.md": {"status": "current", "owner": "Dana"}}
    monkeypatch.setattr(h, "_claims_local", lambda: ("tip", claims))
    r = h.ignore_cli(["snapshot"])
    assert r["unmarked"] == []
    assert h.ignore_cli(["list"])["by_owner"] == {"carol": 1}  # c2 is mine: never ignored


def test_collab_status_lists_people_with_counts_and_me(ign):
    h.collab_cli(["on", "--name", "Dana"])
    for slug, who in (("a.md", "Bob"), ("b.md", "Bob"), ("c.md", "Alice")):
        _put(ign, "TODO", slug, body=f"# T\nOwner : {who}\n- [ ] x\n")
    _put(ign, "CURRENT_TASKS", "my-own.md")
    h.ignore_cli(["snapshot"])
    people = h.collab_cli(["status"])["people"]
    assert people == [{"name": "Bob", "tasks": 2, "me": False}, {"name": "Alice", "tasks": 1, "me": False},
                      {"name": "Dana", "tasks": 1, "me": True}]


def test_legacy_ignored_file_with_single_owner_still_works(ign):
    h.BATCH_FILE.write_text(_batch_md(_sec("A", "src/a/", "a1.md")), encoding="utf-8")
    _put(ign, "TODO", "a1.md")
    h.IGNORED_FILE.write_text('{"owner": "Bob", "ignored": ["a1.md"]}', encoding="utf-8")
    assert {"slug": "a1.md", "reason": "ignored locally (task of Bob)"} in h.next_task("S1")["skipped"]
    assert h.ignore_cli(["list"])["by_owner"] == {"Bob": 1}


# --- stdin isolation -------------------------------------------------------
# On Windows a hook can be started with an invalid inherited stdin handle; any
# child process that inherits it dies with `[WinError 6] invalid handle`, which
# made the closure auto-commit fail silently. Every subprocess the engine
# spawns must therefore pin stdin AND stdout/stderr explicitly (no inheritance;
# pytest's fd capture leaves the OS-level std handles stale for the same reason).

def _unpinned_subprocess_calls(path):
    import ast
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("run", "Popen", "check_output", "call")
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"):
            kw = {k.arg for k in node.keywords}
            pinned_in = bool(kw & {"stdin", "input"})
            pinned_out = "capture_output" in kw or {"stdout", "stderr"} <= kw
            if not (pinned_in and pinned_out):
                bad.append(f"{path}:{node.lineno}")
    return bad


def test_engine_subprocess_calls_pin_stdin():
    repo = pathlib.Path(__file__).resolve().parent.parent
    files = [repo / "crew" / "crew_hook.py", repo / "scripts" / "crew_hook.py",
             repo / "crew" / "crew_update.py", repo / "scripts" / "crew_update.py",
             repo / "scripts" / "dashboard" / "server.py"]
    bad = [b for f in files if f.exists() for b in _unpinned_subprocess_calls(f)]
    assert not bad, "subprocess call(s) inherit stdin: " + ", ".join(bad)


# --- English file/section names with French legacy names still honored ------
# New projects use HISTORY.md / HISTORY_ARCHIVE.md / TASK_CHANGELOG.md / LIFECYCLE.md and
# an "Unsorted" section; projects created earlier keep HISTORIQUE.md, HISTORIQUE_ARCHIVE.md,
# CHANGELOG_TACHES.md, CYCLE_DE_VIE.md and "À classer". Both must work, English wins if both exist.

def _drop_legacy_names(ctx):
    for n in ("HISTORIQUE.md", "HISTORIQUE_ARCHIVE.md", "CHANGELOG_TACHES.md"):
        (ctx / n).unlink(missing_ok=True)


def test_names_default_to_english_when_nothing_exists(repo):
    root, dirs, ctx = repo
    _drop_legacy_names(ctx)
    assert h.history_file() == ctx / "HISTORY.md"
    assert h.history_archive_file() == ctx / "HISTORY_ARCHIVE.md"
    assert h.changelog_file() == ctx / "TASK_CHANGELOG.md"


def test_legacy_french_names_are_kept_when_they_exist(repo):
    root, dirs, ctx = repo
    (ctx / "HISTORIQUE_ARCHIVE.md").write_text("# a\n", encoding="utf-8")
    assert h.history_file() == ctx / "HISTORIQUE.md"
    assert h.history_archive_file() == ctx / "HISTORIQUE_ARCHIVE.md"
    assert h.changelog_file() == ctx / "CHANGELOG_TACHES.md"


def test_english_name_wins_when_both_exist(repo):
    root, dirs, ctx = repo
    (ctx / "HISTORY.md").write_text("# new\n", encoding="utf-8")
    assert h.history_file() == ctx / "HISTORY.md"


def test_rotate_works_with_english_names(repo):
    root, dirs, ctx = repo
    _drop_legacy_names(ctx)
    (ctx / "HISTORY.md").write_text(
        "# History\n\n## old-task — 2025-01-10\nWhat: old.\n\n## recent-task — 2026-08-20\nWhat: recent.\n\n",
        encoding="utf-8")
    assert h.rotate_historique(datetime.datetime(2026, 8, 29)) == ["old-task"]
    assert "old-task" in (ctx / "HISTORY_ARCHIVE.md").read_text(encoding="utf-8")
    assert "old-task" not in (ctx / "HISTORY.md").read_text(encoding="utf-8")
    assert not (ctx / "HISTORIQUE_ARCHIVE.md").exists()


def test_closure_commit_includes_english_named_history(repo):
    root, dirs, ctx = repo
    _git(root, "mv", "crew/CLAUDE_CONTEXT/HISTORIQUE.md", "crew/CLAUDE_CONTEXT/HISTORY.md")
    _git(root, "mv", "crew/CLAUDE_CONTEXT/CHANGELOG_TACHES.md", "crew/CLAUDE_CONTEXT/TASK_CHANGELOG.md")
    _git(root, "commit", "-qm", "english names")
    slug = "ma-tache"
    task_file = dirs["CURRENT_TASKS"] / f"{slug}.md"
    task_file.write_text(f"# {slug}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    task_file.unlink()
    histo = ctx / "HISTORY.md"
    histo.write_text(histo.read_text(encoding="utf-8") + f"\n## {slug}\nWhat: done.\n", encoding="utf-8")
    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))
    assert "crew/CLAUDE_CONTEXT/HISTORY.md" in _last_commit_files(root)


@pytest.mark.parametrize("header", ["## Unsorted", "## À classer", "### A classer"])
def test_unsorted_section_bounds_the_last_batch(header):
    text = ("## Batch A\n- `a.md`\nZone : `src/a/`\n\n" + header + "\n- `loose.md`\n")
    sections = h.slugs_by_batch_section(text)
    assert [s["slugs"] for s in sections] == [{"a.md"}]


def test_lifecycle_doc_resolves_english_then_legacy(repo):
    root, dirs, ctx = repo
    assert h.lifecycle_doc_rel() == "crew/CLAUDE_CONTEXT/LIFECYCLE.md"          # nothing yet: English default
    (ctx / "CYCLE_DE_VIE.md").write_text("x", encoding="utf-8")
    assert h.lifecycle_doc_rel() == "crew/CLAUDE_CONTEXT/CYCLE_DE_VIE.md"       # legacy project
    (ctx / "LIFECYCLE.md").write_text("x", encoding="utf-8")
    assert h.lifecycle_doc_rel() == "crew/CLAUDE_CONTEXT/LIFECYCLE.md"          # English wins


def test_mods_accept_the_same_unsorted_header_as_the_engine():
    ts = (pathlib.Path(__file__).resolve().parent.parent / "hooks" / "mods" / "shared.ts").read_text(encoding="utf-8")
    line = next(l for l in ts.splitlines() if l.startswith("const UNCLASSIFIED_HEADER_RE"))
    assert "Unsorted" in line and "classer" in line
