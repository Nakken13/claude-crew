# -*- coding: utf-8 -*-
"""Tests for spec_to_task_hook.py: a superpowers spec becomes a `📝 draft` task in crew/TODO/,
never a task in progress. Each test copies the real hook into an isolated temporary project and
runs it as Claude Code does (PostToolUse JSON on stdin), so ROOT resolution is exercised for real."""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
DOGFOOD = HERE / "spec_to_task_hook.py"
PLUGIN = REPO / "scripts" / "spec_to_task_hook.py"

sys.path.insert(0, str(HERE))
import crew_hook as h  # noqa: E402


@pytest.fixture
def proj(tmp_path):
    for d in (*h.LINT_FOLDERS, "CLAUDE_CONTEXT"):
        (tmp_path / "crew" / d).mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    shutil.copy(DOGFOOD, tmp_path / "crew" / "spec_to_task_hook.py")
    return tmp_path


def _run(proj, spec_name="2026-11-22-foo-bar-design.md", body="# Foo bar — Design\n\ntext\n", script=None, env=None):
    spec = proj / "docs" / "superpowers" / "specs" / spec_name
    spec.write_text(body, encoding="utf-8")
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(spec)}})
    full_env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    full_env.update(env or {})
    r = subprocess.run([sys.executable, str(script or proj / "crew" / "spec_to_task_hook.py")],
                       input=payload, capture_output=True, text=True, encoding="utf-8", env=full_env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


def test_spec_creates_task_in_todo_not_current_tasks(proj):
    _run(proj)
    assert (proj / "crew" / "TODO" / "foo-bar.md").exists()
    assert not (proj / "crew" / "CURRENT_TASKS" / "foo-bar.md").exists()


def test_created_task_carries_the_draft_marker_and_metadata_placeholders(proj):
    _run(proj)
    text = (proj / "crew" / "TODO" / "foo-bar.md").read_text(encoding="utf-8")
    assert text.startswith("# Foo bar\n")
    assert "**Status:** 📝 draft" in text
    assert "**Spec :** `docs/superpowers/specs/2026-11-22-foo-bar-design.md`" in text
    assert re.search(r"^Zone :", text, re.M)
    assert "## Acceptance" in text
    assert re.search(r"^Verification:", text, re.M)
    assert h._is_draft(text)


def test_additional_context_lists_what_to_complete(proj):
    out = _run(proj)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "crew/TODO/foo-bar.md" in ctx
    for word in ("Zone", "Actions", "Acceptance", "CLAUDE_BATCH.md", "draft"):
        assert word in ctx
    assert "crew/TODO/foo-bar.md" in out["systemMessage"]


@pytest.mark.parametrize("folder", h.LINT_FOLDERS)
def test_no_duplicate_when_slug_already_tracked(proj, folder):
    existing = proj / "crew" / folder / "foo-bar.md"
    existing.write_text("# mine\n", encoding="utf-8")
    assert _run(proj) is None
    assert existing.read_text(encoding="utf-8") == "# mine\n"
    assert folder == "TODO" or not (proj / "crew" / "TODO" / "foo-bar.md").exists()


@pytest.mark.parametrize("history_name", ["HISTORY.md", "HISTORIQUE.md", "HISTORY_ARCHIVE.md"])
def test_no_duplicate_when_slug_already_closed_in_history(proj, history_name):
    (proj / "crew" / "CLAUDE_CONTEXT" / history_name).write_text(
        "# History\n\n## foo-bar — 2026-10-01\n\ndone\n", encoding="utf-8")
    assert _run(proj) is None
    assert not (proj / "crew" / "TODO" / "foo-bar.md").exists()


@pytest.mark.parametrize("heading", ["## **foo-bar** — 2026-10-01", "##  foo-bar — 2026-10-01", "## `foo-bar.md` — x"])
def test_history_heading_rule_matches_the_engine(proj, monkeypatch, heading):
    """Same text, same verdict: the hook dedupes exactly the slugs the engine reads as closed."""
    ctx = proj / "crew" / "CLAUDE_CONTEXT"
    (ctx / "HISTORY.md").write_text(f"# History\n\n{heading}\n", encoding="utf-8")
    monkeypatch.setattr(h, "CTX", ctx)
    assert "foo-bar.md" in h._history_slugs()
    assert _run(proj) is None


def test_non_utf8_history_does_not_crash_the_hook(proj):
    (proj / "crew" / "CLAUDE_CONTEXT" / "HISTORY.md").write_bytes("# Histoire\n\n## autre — été\n".encode("cp1252"))
    _run(proj)
    assert (proj / "crew" / "TODO" / "foo-bar.md").exists()


def test_history_mention_in_a_comment_or_other_slug_does_not_dedupe(proj):
    (proj / "crew" / "CLAUDE_CONTEXT" / "HISTORY.md").write_text(
        "# History\n\n<!--\n## foo-bar — 2026-10-01\n-->\n## foo-bar-v2 — 2026-10-02\n", encoding="utf-8")
    _run(proj)
    assert (proj / "crew" / "TODO" / "foo-bar.md").exists()


def test_generated_draft_lints_as_draft_only(proj, monkeypatch):
    """The placeholders must not trip other lint rules: the draft marker is the single signal."""
    _run(proj)
    crew = proj / "crew"
    dirs = {d: crew / d for d in h.LINT_FOLDERS}
    batch = crew / "CLAUDE_BATCH.md"
    batch.write_text("# Batching\n", encoding="utf-8")
    monkeypatch.setattr(h, "DIRS", dirs)
    monkeypatch.setattr(h, "CTX", crew / "CLAUDE_CONTEXT")
    monkeypatch.setattr(h, "BATCH_FILE", batch)
    r = h.lint_crew()
    assert r["errors"] == []
    assert [(w["code"], w["task"]) for w in r["warnings"]] == [("draft", "foo-bar.md")]


def test_plugin_copy_resolves_project_from_env(proj):
    _run(proj, script=PLUGIN, env={"CLAUDE_PROJECT_DIR": str(proj)})
    assert h._is_draft((proj / "crew" / "TODO" / "foo-bar.md").read_text(encoding="utf-8"))


def _strip_root_preamble(text):
    """The two copies differ only by how ROOT is resolved (plugin: CLAUDE_PROJECT_DIR + git root)."""
    text = text.replace("import os\n", "")
    text = re.sub(r"\ndef _git_root\(start\):.*?\n\n\n", "\n", text, flags=re.S)
    return re.sub(r"^ROOT = .*$", "ROOT = <resolved>", text, flags=re.M)


def test_plugin_and_dogfood_copies_differ_only_by_root_resolution():
    assert _strip_root_preamble(PLUGIN.read_text(encoding="utf-8")) == \
        _strip_root_preamble(DOGFOOD.read_text(encoding="utf-8"))
