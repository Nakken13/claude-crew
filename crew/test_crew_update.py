# -*- coding: utf-8 -*-
"""Tests pour crew_update.py (tache mecanisme-mise-a-jour-scaffold-multi-projets).
Chaque test travaille sur un projet-cible et une source-scaffold factices
dans tmp_path (jamais le vrai depot), fichiers reels sur disque, hashing
reel — pas de mock."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import crew_update as u


# --- classify() : logique pure de decision par fichier ---------------------

def test_classify_new_when_missing_locally_but_present_in_source():
    assert u.classify(local_hash=None, recorded_hash=None, source_hash="abc") == "new"


def test_classify_absent_when_missing_everywhere():
    assert u.classify(local_hash=None, recorded_hash=None, source_hash=None) == "absent"


def test_classify_up_to_date_when_local_matches_source():
    assert u.classify(local_hash="abc", recorded_hash="abc", source_hash="abc") == "up_to_date"


def test_classify_apply_when_unmodified_since_last_write_and_source_changed():
    # local == ce qu'on a ecrit la derniere fois, mais source a change depuis
    assert u.classify(local_hash="old", recorded_hash="old", source_hash="new") == "apply"


def test_classify_conflict_when_local_diverges_from_recorded():
    # l'utilisateur a touche le fichier depuis notre derniere ecriture
    assert u.classify(local_hash="user-edit", recorded_hash="old", source_hash="new") == "conflict"


def test_classify_up_to_date_when_local_equals_source_despite_recorded_mismatch():
    # local != recorded mais local == source : convergence, rien a appliquer.
    assert u.classify(local_hash="new", recorded_hash="old", source_hash="new") == "up_to_date"


def test_classify_removed_when_local_exists_but_source_no_longer_has_it():
    # Le fichier a disparu de la source (deplace/supprime en amont) : ne
    # jamais tomber dans "apply" (shutil.copyfile planterait sur un fichier
    # source inexistant), quel que soit l'etat de recorded_hash.
    assert u.classify(local_hash="old", recorded_hash="old", source_hash=None) == "removed"
    assert u.classify(local_hash="user-edit", recorded_hash="old", source_hash=None) == "removed"


# --- fixtures : arborescences projet-cible / source-scaffold factices ------

@pytest.fixture
def source_root(tmp_path):
    src = tmp_path / "source"
    (src / "crew").mkdir(parents=True)
    (src / ".claude" / "skills" / "crew-init").mkdir(parents=True)
    (src / "CLAUDE.md").write_text("claude v2\n", encoding="utf-8")
    (src / "check_placeholders.py").write_text("print('v2')\n", encoding="utf-8")
    (src / "crew" / "crew_hook.py").write_text("hook v2\n", encoding="utf-8")
    (src / ".claude" / "skills" / "crew-init" / "SKILL.md").write_text("skill v2\n", encoding="utf-8")
    return src


@pytest.fixture
def project_root(tmp_path):
    proj = tmp_path / "project"
    (proj / "crew" / "CLAUDE_CONTEXT").mkdir(parents=True)
    (proj / "crew" / "TODO").mkdir(parents=True)
    (proj / "crew" / "CURRENT_TASKS").mkdir(parents=True)
    (proj / ".claude" / "skills" / "crew-init").mkdir(parents=True)
    (proj / "CLAUDE.md").write_text("claude v1\n", encoding="utf-8")
    (proj / "check_placeholders.py").write_text("print('v1')\n", encoding="utf-8")
    (proj / "crew" / "crew_hook.py").write_text("hook v1\n", encoding="utf-8")
    (proj / ".claude" / "skills" / "crew-init" / "SKILL.md").write_text("skill v1\n", encoding="utf-8")
    (proj / "crew" / "TODO" / "user-task.md").write_text("# une tache utilisateur\n", encoding="utf-8")
    (proj / "crew" / "CLAUDE_CONTEXT" / "HISTORIQUE.md").write_text("# historique utilisateur\n", encoding="utf-8")
    return proj


WHITELIST = ["CLAUDE.md", "check_placeholders.py", "crew/crew_hook.py",
             ".claude/skills/crew-init/SKILL.md"]


# --- plan() / apply() : jamais de donnees utilisateur touchees -------------

def test_plan_flags_conflict_when_no_recorded_hash_exists_yet(project_root, source_root):
    # Aucun SCAFFOLD_VERSION.json existant encore -> recorded_hash absent pour
    # tous les fichiers -> tout diff local/source doit ressortir en conflict
    # (pas en apply), car on ne peut pas prouver l'absence de personnalisation.
    decisions = u.plan(project_root, source_root, WHITELIST)
    statuses = {d["path"]: d["status"] for d in decisions}
    assert statuses == {
        "CLAUDE.md": "conflict",
        "check_placeholders.py": "conflict",
        "crew/crew_hook.py": "conflict",
        ".claude/skills/crew-init/SKILL.md": "conflict",
    }


def test_plan_flags_apply_once_recorded_hash_matches_current_local_content(project_root, source_root):
    # Simule un crew-init initial : on enregistre le hash de la version v1
    # deja presente localement comme "derniere version ecrite par nous".
    recorded = u.seed(project_root, WHITELIST, "1.0.0")["files"]

    decisions = u.plan(project_root, source_root, WHITELIST)
    statuses = {d["path"]: d["status"] for d in decisions}
    assert statuses == {
        "CLAUDE.md": "apply",
        "check_placeholders.py": "apply",
        "crew/crew_hook.py": "apply",
        ".claude/skills/crew-init/SKILL.md": "apply",
    }


def test_plan_flags_conflict_when_user_edited_file_after_last_recorded_write(project_root, source_root):
    recorded = u.seed(project_root, WHITELIST, "1.0.0")["files"]

    # L'utilisateur personnalise CLAUDE.md apres coup.
    (project_root / "CLAUDE.md").write_text("claude v1 + notes perso\n", encoding="utf-8")

    decisions = u.plan(project_root, source_root, WHITELIST)
    statuses = {d["path"]: d["status"] for d in decisions}
    assert statuses["CLAUDE.md"] == "conflict"
    assert statuses["check_placeholders.py"] == "apply"


def test_apply_writes_only_apply_and_new_files_and_skips_conflicts(project_root, source_root):
    recorded = u.seed(project_root, WHITELIST, "1.0.0")["files"]
    (project_root / "CLAUDE.md").write_text("claude v1 + notes perso\n", encoding="utf-8")

    decisions = u.plan(project_root, source_root, WHITELIST)
    applied = u.apply(project_root, source_root, decisions)

    assert sorted(applied) == sorted([
        "check_placeholders.py", "crew/crew_hook.py",
        ".claude/skills/crew-init/SKILL.md",
    ])
    # Le fichier en conflit n'est jamais ecrase.
    assert (project_root / "CLAUDE.md").read_text(encoding="utf-8") == "claude v1 + notes perso\n"
    # Les fichiers "apply" recoivent bien le contenu source.
    assert (project_root / "check_placeholders.py").read_text(encoding="utf-8") == "print('v2')\n"
    assert (project_root / "crew" / "crew_hook.py").read_text(encoding="utf-8") == "hook v2\n"


def test_apply_never_touches_user_data_directories(project_root, source_root):
    recorded = u.seed(project_root, WHITELIST, "1.0.0")["files"]

    decisions = u.plan(project_root, source_root, WHITELIST)
    u.apply(project_root, source_root, decisions)

    assert (project_root / "crew" / "TODO" / "user-task.md").read_text(encoding="utf-8") == "# une tache utilisateur\n"
    assert (project_root / "crew" / "CLAUDE_CONTEXT" / "HISTORIQUE.md").read_text(encoding="utf-8") == "# historique utilisateur\n"


def test_apply_never_crashes_on_a_file_removed_from_source(project_root, source_root):
    # Reproduction du bug trouve en code review : un fichier de la liste
    # blanche existe encore localement mais a disparu de la source (deplace/
    # supprime en amont, ex. crew_hook.py deplace de crew/ vers scripts/).
    recorded = u.seed(project_root, WHITELIST, "1.0.0")["files"]
    (source_root / "crew" / "crew_hook.py").unlink()

    decisions = u.plan(project_root, source_root, WHITELIST)
    statuses = {d["path"]: d["status"] for d in decisions}
    assert statuses["crew/crew_hook.py"] == "removed"

    applied = u.apply(project_root, source_root, decisions)  # ne doit pas lever

    assert "crew/crew_hook.py" not in applied
    assert (project_root / "crew" / "crew_hook.py").read_text(encoding="utf-8") == "hook v1\n"


def test_apply_creates_new_engine_file_absent_locally(project_root, source_root):
    (source_root / "NEW_ENGINE_FILE.md").write_text("nouveau fichier moteur\n", encoding="utf-8")
    whitelist = WHITELIST + ["NEW_ENGINE_FILE.md"]
    recorded = u.seed(project_root, WHITELIST, "1.0.0")["files"]

    decisions = u.plan(project_root, source_root, whitelist)
    applied = u.apply(project_root, source_root, decisions)

    assert "NEW_ENGINE_FILE.md" in applied
    assert (project_root / "NEW_ENGINE_FILE.md").read_text(encoding="utf-8") == "nouveau fichier moteur\n"


# --- record_version() : bump version + hashes apres application -----------

def test_record_version_stores_new_hashes_only_for_applied_files(project_root, source_root):
    recorded = u.seed(project_root, WHITELIST, "1.0.0")["files"]
    (project_root / "CLAUDE.md").write_text("claude v1 + notes perso\n", encoding="utf-8")

    decisions = u.plan(project_root, source_root, WHITELIST)
    u.apply(project_root, source_root, decisions)
    data = u.record_version(project_root, "2.0.0", decisions)

    assert data["version"] == "2.0.0"
    # Fichier applique -> hash source enregistre.
    assert data["files"]["crew/crew_hook.py"] == u.hash_file(source_root / "crew/crew_hook.py")
    # Fichier en conflit -> hash enregistre inchange (pas celui de la source).
    assert data["files"]["CLAUDE.md"] == recorded["CLAUDE.md"]

    on_disk = json.loads((project_root / "crew" / "CLAUDE_CONTEXT" / "SCAFFOLD_VERSION.json").read_text(encoding="utf-8"))
    assert on_disk == data


def test_load_scaffold_version_defaults_when_file_absent(project_root):
    assert u.load_scaffold_version(project_root) == {"version": None, "files": {}}


# --- seed() : bootstrap d'un projet legacy sans SCAFFOLD_VERSION.json ------

def test_seed_records_current_local_content_as_trusted_baseline(project_root):
    # Cas des projets bootstrapes avant l'existence de ce mecanisme (aucun
    # SCAFFOLD_VERSION.json) : on accepte le contenu local actuel comme etant
    # "notre derniere ecriture connue", pour que le prochain plan() compare
    # les vrais changements source au lieu de tout marquer conflict.
    data = u.seed(project_root, WHITELIST, "1.0.0")

    assert data["version"] == "1.0.0"
    assert data["files"] == {rel: u.hash_file(project_root / rel) for rel in WHITELIST}
    on_disk = json.loads((project_root / "crew" / "CLAUDE_CONTEXT" / "SCAFFOLD_VERSION.json").read_text(encoding="utf-8"))
    assert on_disk == data


def test_seed_skips_whitelist_entries_missing_locally(project_root):
    data = u.seed(project_root, WHITELIST + ["does-not-exist.md"], "1.0.0")
    assert "does-not-exist.md" not in data["files"]


def test_plan_flags_apply_after_seeding_when_source_has_since_changed(project_root, source_root):
    u.seed(project_root, WHITELIST, "1.0.0")

    decisions = u.plan(project_root, source_root, WHITELIST)
    statuses = {d["path"]: d["status"] for d in decisions}
    # Rien n'a ete personnalise depuis le seed -> tout diff avec la source
    # ressort en apply, pas en conflict (c'est le probleme trouve en review :
    # sans seed, le premier run classe tout en conflict).
    assert statuses == {
        "CLAUDE.md": "apply",
        "check_placeholders.py": "apply",
        "crew/crew_hook.py": "apply",
        ".claude/skills/crew-init/SKILL.md": "apply",
    }


def test_seed_refuses_to_clobber_existing_recorded_hashes_without_force(project_root):
    # Trouve en review "altitude" : contrairement a record_version() qui
    # merge, seed() ecrasait sans condition — un second appel (par erreur,
    # ou sur un projet deja seede) perdait silencieusement l'historique.
    u.seed(project_root, WHITELIST, "1.0.0")

    with pytest.raises(ValueError):
        u.seed(project_root, WHITELIST, "2.0.0")

    # L'historique du premier seed n'a pas bouge.
    assert u.load_scaffold_version(project_root)["version"] == "1.0.0"


def test_seed_overwrites_when_force_is_true(project_root):
    u.seed(project_root, WHITELIST, "1.0.0")
    data = u.seed(project_root, WHITELIST, "2.0.0", force=True)
    assert data["version"] == "2.0.0"
    assert u.load_scaffold_version(project_root)["version"] == "2.0.0"


# --- detect_mode() : legacy (skills/agents copies localement) vs plugin ---

def test_detect_mode_returns_legacy_when_local_crew_init_skill_present(project_root):
    assert u.detect_mode(project_root) == "legacy"


def test_detect_mode_returns_plugin_when_no_local_crew_init_skill(tmp_path):
    plugin_project = tmp_path / "plugin-project"
    (plugin_project / "crew" / "CLAUDE_CONTEXT").mkdir(parents=True)
    (plugin_project / "CLAUDE.md").write_text("claude\n", encoding="utf-8")
    assert u.detect_mode(plugin_project) == "plugin"


# --- detect_double_hook() : plugin actif + hook local crew_hook.py ---------

LOCAL_HOOK_CMD = 'python "$CLAUDE_PROJECT_DIR/crew/crew_hook.py"'
PLUGIN_HOOK_CMD = 'python "${CLAUDE_PLUGIN_ROOT}/scripts/crew_hook.py"'


def _write_settings(root, name, data):
    d = pathlib.Path(root) / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(data), encoding="utf-8")


def _hooks(cmd, *events):
    return {"hooks": {e: [{"matcher": "", "hooks": [{"type": "command", "command": cmd}]}] for e in events}}


def test_detect_double_hook_plugin_and_local(tmp_path):
    settings = {"enabledPlugins": {"claude-crew@nakken13": True}}
    settings.update(_hooks(LOCAL_HOOK_CMD, "PreToolUse", "Stop"))
    _write_settings(tmp_path, "settings.json", settings)

    found = u.detect_double_hook(tmp_path, user_settings_path=tmp_path / "none.json")

    assert found == {"PreToolUse": [LOCAL_HOOK_CMD], "Stop": [LOCAL_HOOK_CMD]}


def test_detect_double_hook_plugin_enabled_in_user_settings(tmp_path):
    project = tmp_path / "proj"
    _write_settings(project, "settings.json", _hooks(LOCAL_HOOK_CMD, "Stop"))
    user = tmp_path / "user-settings.json"
    user.write_text(json.dumps({"enabledPlugins": {"claude-crew@x": True}}), encoding="utf-8")

    assert u.detect_double_hook(project, user_settings_path=user) == {"Stop": [LOCAL_HOOK_CMD]}


@pytest.mark.parametrize("plugins,cmd", [
    ({"claude-crew@nakken13": True}, PLUGIN_HOOK_CMD),  # plugin hook only
    (None, LOCAL_HOOK_CMD),  # legacy local hook without plugin = normal
    ({"claude-crew@nakken13": False}, LOCAL_HOOK_CMD),  # plugin disabled
    ({"claude-crew@nakken13": True}, "python mycrew/crew_hook.py"),  # lookalike path
])
def test_no_double_hook_cases(tmp_path, plugins, cmd):
    settings = _hooks(cmd, "Stop")
    if plugins is not None:
        settings["enabledPlugins"] = plugins
    _write_settings(tmp_path, "settings.json", settings)

    assert u.detect_double_hook(tmp_path, user_settings_path=tmp_path / "none.json") == {}


def test_detect_double_hook_tolerates_missing_or_invalid_settings(tmp_path):
    assert u.detect_double_hook(tmp_path, user_settings_path=tmp_path / "none.json") == {}

    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text("{not json", encoding="utf-8")
    (d / "settings.local.json").write_text('["wrong", "shape"]', encoding="utf-8")
    assert u.detect_double_hook(tmp_path, user_settings_path=tmp_path / "none.json") == {}


def test_double_hook_not_removed_without_confirmation(tmp_path, capsys, monkeypatch):
    settings = {"enabledPlugins": {"claude-crew@nakken13": True}}
    settings.update(_hooks(LOCAL_HOOK_CMD, "Stop"))
    _write_settings(tmp_path, "settings.json", settings)
    before = (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8")
    source = tmp_path / "src"
    source.mkdir()
    monkeypatch.setattr(sys, "argv", ["crew_update.py", "--project", str(tmp_path), "--source", str(source)])
    monkeypatch.setattr(u, "USER_SETTINGS_PATH", tmp_path / "none.json")

    u._main()

    out = capsys.readouterr().out
    assert "crew/crew_hook.py" in out and "--remove-double-hook" in out
    assert (tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8") == before


def test_remove_double_hook_with_flag_strips_only_local_crew_entries(tmp_path, monkeypatch):
    settings = {"enabledPlugins": {"claude-crew@nakken13": True}}
    settings["hooks"] = {
        "Stop": [
            {"matcher": "", "hooks": [{"type": "command", "command": LOCAL_HOOK_CMD}]},
            {"matcher": "", "hooks": [{"type": "command", "command": "echo other"}]},
        ],
        "PreToolUse": [{"matcher": "", "hooks": [{"type": "command", "command": LOCAL_HOOK_CMD}]}],
    }
    _write_settings(tmp_path, "settings.json", settings)
    source = tmp_path / "src"
    source.mkdir()
    monkeypatch.setattr(sys, "argv", ["crew_update.py", "--project", str(tmp_path), "--source", str(source),
                                      "--remove-double-hook"])
    monkeypatch.setattr(u, "USER_SETTINGS_PATH", tmp_path / "none.json")

    u._main()

    after = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert after["enabledPlugins"] == {"claude-crew@nakken13": True}
    assert "PreToolUse" not in after["hooks"]
    assert after["hooks"]["Stop"] == [{"matcher": "", "hooks": [{"type": "command", "command": "echo other"}]}]


def test_detect_double_hook_windows_backslash_command(tmp_path):
    win_cmd = r'python "%CLAUDE_PROJECT_DIR%\crew\crew_hook.py"'
    settings = {"enabledPlugins": {"claude-crew@nakken13": True}}
    settings.update(_hooks(win_cmd, "Stop"))
    _write_settings(tmp_path, "settings.json", settings)

    assert u.detect_double_hook(tmp_path, user_settings_path=tmp_path / "none.json") == {"Stop": [win_cmd]}


def test_double_hook_detected_and_removed_via_settings_local(tmp_path):
    _write_settings(tmp_path, "settings.json", {"enabledPlugins": {"claude-crew@nakken13": True}})
    _write_settings(tmp_path, "settings.local.json", {**_hooks(LOCAL_HOOK_CMD, "Stop"), "model": "x"})

    assert u.detect_double_hook(tmp_path, user_settings_path=tmp_path / "none.json") == {"Stop": [LOCAL_HOOK_CMD]}
    changed = u.remove_double_hook(tmp_path)

    assert [pathlib.Path(c).name for c in changed] == ["settings.local.json"]
    after = json.loads((tmp_path / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert after == {"model": "x"}
    assert u.remove_double_hook(tmp_path) == []  # idempotent


def test_remove_double_hook_keeps_preexisting_empty_groups(tmp_path):
    settings = {"hooks": {"Stop": [{"matcher": "", "hooks": []},
                                   {"matcher": "", "hooks": [{"type": "command", "command": LOCAL_HOOK_CMD}]}]}}
    _write_settings(tmp_path, "settings.json", settings)

    u.remove_double_hook(tmp_path)

    after = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert after["hooks"]["Stop"] == [{"matcher": "", "hooks": []}]
