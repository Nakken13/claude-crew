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
