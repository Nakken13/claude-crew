# -*- coding: utf-8 -*-
"""Tests for sync_engine.py: the mirrors (crew/ -> scripts/, .claude/ -> skills|agents)
are generated, never edited by hand."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sync_engine as se

REPO = pathlib.Path(__file__).resolve().parents[2]

SRC_ROOT_LINE = 'ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parent.parent)  # racine du projet'
HOOK = "import os\nimport pathlib\n\ndef _git_root(s):\n    return s\n\n" + SRC_ROOT_LINE + "\nprint(ROOT)\n"


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def _mini_repo(tmp_path, *, hook=HOOK, mirror_hook=None):
    _write(tmp_path, "crew/crew_hook.py", hook)
    if mirror_hook is not None:
        _write(tmp_path, "scripts/crew_hook.py", mirror_hook)
    _write(tmp_path, "crew/crew_update.py", "print('update')\n")
    _write(tmp_path, ".claude/skills/crew-start/SKILL.md", "start\n")
    _write(tmp_path, ".claude/agents/ceo.md", "ceo\n")
    return tmp_path


def test_derive_plugin_hook_swaps_only_the_root_line():
    out = se.derive_plugin_hook(HOOK)
    assert 'ROOT = _git_root(pathlib.Path(os.environ["CLAUDE_PROJECT_DIR"]))' in out
    assert out.endswith("# racine du projet\nprint(ROOT)\n")
    assert se.PLUGIN_ROOT_LINE in out and len(out.splitlines()) == len(HOOK.splitlines())


def test_derive_fails_loudly_when_root_line_is_missing():
    import pytest
    with pytest.raises(ValueError):
        se.derive_plugin_hook("print('no root line here')\n")


def test_check_reports_drift_and_sync_repairs_it(tmp_path):
    root = _mini_repo(tmp_path, mirror_hook="stale\n")
    drift = se.sync(root, check=True)
    assert "scripts/crew_hook.py" in drift
    assert "scripts/crew_update.py" in drift          # missing mirror
    assert "skills/crew-start/SKILL.md" in drift
    assert "agents/ceo.md" in drift
    assert (root / "scripts/crew_hook.py").read_text(encoding="utf-8") == "stale\n"  # check never writes

    assert sorted(se.sync(root)) == sorted(drift)      # sync fixes exactly what drifted
    assert se.sync(root, check=True) == []
    assert (root / "agents/ceo.md").read_text(encoding="utf-8") == "ceo\n"


def test_crlf_only_difference_is_not_drift(tmp_path):
    root = _mini_repo(tmp_path)
    se.sync(root)
    p = root / "skills/crew-start/SKILL.md"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert se.sync(root, check=True) == []


def test_sync_removes_orphan_mirror_agents(tmp_path):
    root = _mini_repo(tmp_path)
    _write(root, "agents/gone.md", "orphan\n")
    assert "agents/gone.md" in se.sync(root, check=True)
    se.sync(root)
    assert not (root / "agents/gone.md").exists()


def test_real_repo_has_no_mirror_drift():
    assert se.sync(REPO, check=True) == [], "run: python scripts/dev/sync_engine.py"
