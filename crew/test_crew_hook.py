# -*- coding: utf-8 -*-
"""Tests pour crew_hook.py. Aucune suite pytest n'existait avant (verifie -
seule validation existante = les checklists crew/TESTS/IA|DEV/, non
automatisees). Se concentre sur auto_commit_closure (tache
hook-auto-commit-cloture-tache) : chaque test construit un depot git
temporaire isole (jamais le vrai depot) et monkeypatch les constantes
module-level de crew_hook pour y pointer, avant d'appeler la fonction
reelle — pas de mock sur subprocess/git, comportement reel verifie."""
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
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)


def _last_commit_message(root):
    r = _git(root, "log", "-1", "--format=%s")
    return r.stdout.strip()


def _last_commit_files(root):
    r = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
    return sorted(r.stdout.strip().splitlines())


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Depot git temporaire avec l'arborescence crew/ minimale, HEAD deja
    pose (commit initial), et les constantes de crew_hook monkeypatchees
    pour y pointer pendant la duree du test."""
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
    # BATCH_LOCKS.md est gitignore et jamais suivi dans le vrai depot (voir
    # .gitignore racine) mais regenere a chaque tour par regen_batch_locks_md
    # -> existe toujours sur disque en pratique. Reproduire ca ici, sinon le
    # fixture divergerait de la realite et masquerait un vrai bug (cf. code
    # review : _closure_commit_scope doit filtrer les chemins ignores-et-
    # jamais-suivis, pas seulement les chemins jamais-suivis-et-absents).
    (root / ".gitignore").write_text("crew/CLAUDE_CONTEXT/BATCH_LOCKS.md\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    batch_locks_md.write_text("# Verrous\n", encoding="utf-8")

    monkeypatch.setattr(h, "ROOT", root)
    monkeypatch.setattr(h, "CREW", crew)
    monkeypatch.setattr(h, "DIRS", dirs)
    monkeypatch.setattr(h, "CTX", ctx)
    # SNAP est calcule UNE FOIS a l'import (`SNAP = CTX / ".task_state.json"`
    # avec le CTX reel) : repatcher `h.CTX` seul ne le recalcule pas. Sans ce
    # monkeypatch, tout test appelant `h.main()` lit/ecrit le vrai
    # `.task_state.json` du projet au lieu du tmp_path isole (bug reel trouve
    # en ecrivant les tests PAUSED : `main()` avait clobber le snapshot reel).
    monkeypatch.setattr(h, "SNAP", ctx / ".task_state.json")
    # Meme piege que SNAP : HISTORIQUE/HISTORIQUE_ARCHIVE sont calcules une
    # fois a l'import depuis le vrai CTX. Sans ce monkeypatch,
    # _closure_commit_scope (via HISTORIQUE_ARCHIVE) plante avec "not in the
    # subpath" des que ROOT pointe vers tmp_path (bug reel trouve en ecrivant
    # rotate_historique).
    monkeypatch.setattr(h, "HISTORIQUE", ctx / "HISTORIQUE.md")
    monkeypatch.setattr(h, "HISTORIQUE_ARCHIVE", ctx / "HISTORIQUE_ARCHIVE.md")
    monkeypatch.setattr(h, "BATCH_FILE", batch_file)
    monkeypatch.setattr(h, "CHANGELOG", changelog)
    monkeypatch.setattr(h, "BATCH_LOCKS_MD", batch_locks_md)
    monkeypatch.setattr(h, "LOCKS_FILE", locks_file)
    monkeypatch.setattr(h, "LOCKS_MUTEX", locks_mutex)
    monkeypatch.setattr(h, "MAIN_ROOT", root)
    return root, dirs, ctx


def _simulate_closure(root, dirs, ctx, slug):
    """Simule ce que le hook a deja fait avant d'appeler auto_commit_closure :
    le fichier CURRENT_TASKS/<slug>.md disparait (etait tracke), HISTORIQUE.md
    gagne une entree. Les deux modifications sont laissees NON stagees,
    comme un vrai tour de hook (auto_commit_closure doit stager lui-meme)."""
    task_file = dirs["CURRENT_TASKS"] / f"{slug}.md"
    task_file.write_text(f"# {slug}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", f"seed: {slug} in CURRENT_TASKS")
    task_file.unlink()
    histo = ctx / "HISTORIQUE.md"
    histo.write_text(histo.read_text(encoding="utf-8") + f"\n## {slug}\nQuoi : fait.\n", encoding="utf-8")


def test_auto_commit_closure_creates_commit_with_scope_and_message(repo):
    root, dirs, ctx = repo
    slug = "ma-tache"
    _simulate_closure(root, dirs, ctx, slug)

    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))

    assert _git(root, "diff", "--cached", "--quiet").returncode == 0, "rien ne doit rester staged apres le commit"
    msg = _last_commit_message(root)
    assert slug in msg, msg
    files = _last_commit_files(root)
    assert "crew/CLAUDE_CONTEXT/HISTORIQUE.md" in files
    assert f"crew/CURRENT_TASKS/{slug}.md" in files
    assert "crew/CLAUDE_CONTEXT/BATCH_LOCKS.md" not in files, \
        "BATCH_LOCKS.md est gitignore/jamais suivi -> ne doit jamais etre propose a git add"


def test_auto_commit_closure_ignores_gitignored_regenerated_file(repo):
    """Regression : BATCH_LOCKS.md est regenere sur disque a chaque tour par
    regen_batch_locks_md mais gitignore/jamais suivi — un `git add` explicite
    dessus est refuse par git et faisait auparavant echouer TOUT le `git add`
    (aucun commit n'etait jamais cree, silencieusement, dans le vrai depot)."""
    root, dirs, ctx = repo
    slug = "ma-tache"
    _simulate_closure(root, dirs, ctx, slug)
    assert (ctx / "BATCH_LOCKS.md").exists()  # regenere par le "hook", jamais suivi

    sha_before = _git(root, "rev-parse", "HEAD").stdout.strip()
    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))
    sha_after = _git(root, "rev-parse", "HEAD").stdout.strip()

    assert sha_before != sha_after, "le commit doit reussir malgre BATCH_LOCKS.md gitignore present sur disque"


def test_auto_commit_closure_never_sweeps_unrelated_staged_changes(repo):
    """Regression : le commit ne doit JAMAIS embarquer un fichier deja stage
    par l'utilisateur en dehors du scope crew/ calcule — c'est exactement
    l'incident (config backend committee/poussee sans revue) que cette
    fonctionnalite existe pour eviter."""
    root, dirs, ctx = repo
    slug = "ma-tache"
    _simulate_closure(root, dirs, ctx, slug)

    unrelated = root / "app_config.py"
    unrelated.write_text("PORT = 8080\n", encoding="utf-8")
    _git(root, "add", "--", "app_config.py")

    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))

    files = _last_commit_files(root)
    assert "app_config.py" not in files, "un fichier hors crew/ deja stage par l'utilisateur ne doit jamais etre committe"
    still_staged = _git(root, "diff", "--cached", "--name-only", "--", "app_config.py").stdout.strip()
    assert still_staged == "app_config.py", \
        "le fichier de l'utilisateur doit rester stage tel quel, pas touche par le commit de cloture"


def test_auto_commit_closure_only_includes_slugs_with_matching_histo_entry(repo):
    """2 taches finissent le meme tour, une seule a une vraie entree
    HISTORIQUE.md correspondante (l'autre : fichier CURRENT_TASKS disparu
    sans historisation reelle, ex. suppression manuelle) -> seule la
    premiere doit apparaitre dans le commit, pas juste 'HISTORIQUE.md a
    bouge quelque part' (detection par slug, pas globale)."""
    root, dirs, ctx = repo
    real_slug, fake_slug = "vraie-tache", "fausse-tache"
    fake_task_file = dirs["CURRENT_TASKS"] / f"{fake_slug}.md"
    fake_task_file.write_text(f"# {fake_slug}\n", encoding="utf-8")
    _git(root, "add", "--", str(fake_task_file.relative_to(root)).replace("\\", "/"))
    _git(root, "commit", "-qm", f"seed: {fake_slug}")
    fake_task_file.unlink()
    _simulate_closure(root, dirs, ctx, real_slug)  # touche HISTORIQUE.md APRES, non stage

    h.auto_commit_closure({f"{real_slug}.md", f"{fake_slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))

    msg = _last_commit_message(root)
    assert real_slug in msg and fake_slug not in msg, msg
    files = _last_commit_files(root)
    assert f"crew/CURRENT_TASKS/{fake_slug}.md" not in files


def test_auto_commit_closure_idempotent_no_new_commit_without_new_closure(repo):
    root, dirs, ctx = repo
    slug = "ma-tache"
    _simulate_closure(root, dirs, ctx, slug)
    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))
    sha_after_first = _git(root, "rev-parse", "HEAD").stdout.strip()

    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 5, 0))
    sha_after_second = _git(root, "rev-parse", "HEAD").stdout.strip()

    assert sha_after_first == sha_after_second, "un deuxieme appel sans nouvelle cloture ne doit rien committer"


def test_auto_commit_closure_swallows_commit_failure(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    slug = "ma-tache"
    _simulate_closure(root, dirs, ctx, slug)

    hooks_dir = root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    pre_commit.chmod(0o755)

    sha_before = _git(root, "rev-parse", "HEAD").stdout.strip()
    h.auto_commit_closure({f"{slug}.md"}, datetime.datetime(2026, 8, 22, 23, 0, 0))
    sha_after = _git(root, "rev-parse", "HEAD").stdout.strip()

    assert sha_before == sha_after, "un hook pre-commit qui rejette ne doit produire aucun commit"
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


def _write_single_task_batch(dirs, header="Batch Zone1", zone="zone1/", slugs=("ma-tache.md",)):
    """Ecrit CLAUDE_BATCH.md avec une seule section de batch contenant
    `slugs`, et cree le premier slug dans TODO/ (fichier source du `git mv`
    que les tests de gate_pretooluse simulent)."""
    refs = "\n".join(f"- `{s}`" for s in slugs)
    h.BATCH_FILE.write_text(
        f"# Batching\n\n## {header}\n\nZone : `{zone}`\n\n{refs}\n",
        encoding="utf-8",
    )
    (dirs["TODO"] / slugs[0]).write_text(f"# {slugs[0]}\n", encoding="utf-8")


def _write_other_session_lock(root, tasks, session_id="OTHER"):
    """Pre-remplit crew_lock.json avec une session concurrente detenant deja
    `tasks`, via l'ecriture canonique du module (`save_locks`) plutot qu'un
    JSON ecrit a la main. `since` relatif a l'heure reelle (pas une date
    figee) : purge_stale_locks purge tout ce qui depasse LOCK_TTL (6h) par
    rapport a `datetime.datetime.now()` au moment du test, une date figee
    finirait par depasser ce seuil et casser le test en continu."""
    since = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    h.save_locks({"sessions": {session_id: {
        "batch": "Batch Zone1",
        "tasks": list(tasks),
        "worktree": f"../{root.name}-batch-zone1",
        "branch": "crew/batch-zone1",
        "since": since,
    }}})


def test_gate_pretooluse_git_mv_registers_lock_immediately_from_worktree(repo):
    """Coeur du bug : depuis un worktree de batch, le `git mv` TODO->CURRENT_TASKS
    ne doit plus attendre le prochain tour Stop pour verrouiller la tache —
    gate_pretooluse doit ecrire crew_lock.json avant meme que le mv ne s'execute."""
    root, dirs, ctx = repo
    slug = "ma-tache.md"
    _write_single_task_batch(dirs, slugs=(slug,))

    h.gate_pretooluse(_git_mv_payload(slug))  # ne doit pas lever SystemExit

    info = h.load_locks()["sessions"]["S1"]
    assert info["tasks"] == [slug]
    assert info["batch"] == "Batch Zone1"
    assert info["worktree"] == f"../{root.name}-batch-zone1"
    assert info["branch"] == "crew/batch-zone1"


def test_gate_pretooluse_git_mv_regenerates_batch_locks_md_immediately(repo):
    """Meme scenario, mais verifie BATCH_LOCKS.md (doc humaine) reflete aussi
    le verrou tout de suite, sans attendre un tour Stop supplementaire."""
    root, dirs, ctx = repo
    slug = "ma-tache.md"
    _write_single_task_batch(dirs, slugs=(slug,))

    h.gate_pretooluse(_git_mv_payload(slug))

    content = (ctx / "BATCH_LOCKS.md").read_text(encoding="utf-8")
    assert f"🔒 `{slug}`" in content
    assert "session `S1`" in content


def test_gate_pretooluse_git_mv_blocks_when_same_slug_already_locked(repo):
    """Une autre session detient deja EXACTEMENT ce slug (pas juste une
    voisine de batch) -> doit bloquer, meme si check_batch_collisions (qui ne
    regarde que les voisines) ne l'aurait pas vu tout seul."""
    root, dirs, ctx = repo
    slug = "ma-tache.md"
    _write_single_task_batch(dirs, slugs=(slug,))
    _write_other_session_lock(root, [slug])

    with pytest.raises(SystemExit) as exc:
        h.gate_pretooluse(_git_mv_payload(slug))
    assert exc.value.code == 2

    locks = h.load_locks()
    assert "S1" not in locks["sessions"], "la session bloquee ne doit pas etre enregistree"
    assert locks["sessions"]["OTHER"]["tasks"] == [slug]


def test_gate_pretooluse_git_mv_toctou_blocks_on_fresh_reload(repo, monkeypatch):
    """Simule la course : la premiere lecture de `locks` dans gate_pretooluse
    (avant le mutex) est perimee (vide), mais une AUTRE session a deja pose
    son verrou sur la voisine de batch entre-temps. La re-verification fraiche
    sous mutex doit quand meme bloquer."""
    root, dirs, ctx = repo
    slug_a, slug_b = "a.md", "b.md"
    _write_single_task_batch(dirs, slugs=(slug_a, slug_b))
    _write_other_session_lock(root, [slug_b])

    orig_load_locks = h.load_locks
    calls = {"n": 0}

    def stale_then_real_load_locks():
        calls["n"] += 1
        if calls["n"] == 1:
            return {"sessions": {}}  # lecture perimee, avant l'ecriture concurrente
        return orig_load_locks()

    monkeypatch.setattr(h, "load_locks", stale_then_real_load_locks)

    with pytest.raises(SystemExit) as exc:
        h.gate_pretooluse(_git_mv_payload(slug_a))
    assert exc.value.code == 2

    locks = orig_load_locks()
    assert "S1" not in locks["sessions"]


def test_gate_pretooluse_git_mv_then_stop_started_loop_is_idempotent(repo):
    """La boucle `started` du Stop (fallback documente, cf. main()) rejoue
    l'enregistrement pour la meme tache/session apres coup : ne doit pas
    dupliquer l'entree ni écraser batch/worktree/branch."""
    root, dirs, ctx = repo
    slug = "ma-tache.md"
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
    """Root cause du bug de "collisions multi-sessions" remonte par
    l'utilisateur : `.task_state.json` (SNAP) est un fichier UNIQUE partage
    par toutes les sessions travaillant dans le meme checkout (pas de
    worktree dedie). Une session S2 qui tourne pour la premiere fois voit
    donc `prev` vide, et TOUT fichier deja present dans CURRENT_TASKS/ (y
    compris une tache demarree par une AUTRE session S1, deja proprement
    verrouillee via gate_pretooluse) lui apparait comme "started". Le
    fallback de main() ne doit PAS voler ce verrou : `_slug_session_map`
    doit etre consulte avant `_register_task_lock` pour laisser la tache a
    son proprietaire reel."""
    root, dirs, ctx = repo
    slug = "ma-tache.md"
    _write_single_task_batch(dirs, slugs=(slug,))
    h.gate_pretooluse(_git_mv_payload(slug, session_id="S1"))  # S1 demarre proprement
    (dirs["TODO"] / slug).unlink()
    (dirs["CURRENT_TASKS"] / slug).write_text(f"# {slug}\n", encoding="utf-8")

    _run_stop(monkeypatch, capsys, session_id="S2")  # 1er tour Stop de S2 : prev partage vide

    locks = h.load_locks()
    assert locks["sessions"]["S1"]["tasks"] == [slug], "S1 doit rester seul proprietaire du verrou"
    assert slug not in locks["sessions"].get("S2", {}).get("tasks", []), (
        "S2 ne doit pas s'approprier une tache deja verrouillee par une autre session active"
    )


def test_stop_started_fallback_mis_attribution_does_not_trigger_false_batch_collision(repo, monkeypatch, capsys):
    """Meme mis-attribution que le test precedent, mais via un second
    consommateur non filtre de `started` : `check_batch_collisions` ne
    verifie PAS que `f` appartient a la session courante, seulement que les
    VOISINES de batch de `f` ne sont pas verrouillees par une autre session.
    Une session S2 dont le 1er tour Stop mis-attribue a tort `task-a.md`
    (deja demarree par S1) se voit donc bloquee pour une "collision" avec
    `task-b.md` (verrouillee par une 3e session) alors que S2 n'a jamais
    rien demarre elle-meme."""
    root, dirs, ctx = repo
    slug_a, slug_b = "task-a.md", "task-b.md"
    _write_single_task_batch(dirs, slugs=(slug_a, slug_b))
    h.gate_pretooluse(_git_mv_payload(slug_a, session_id="S1"))  # S1 demarre proprement task-a
    (dirs["TODO"] / slug_a).unlink()
    (dirs["CURRENT_TASKS"] / slug_a).write_text(f"# {slug_a}\n", encoding="utf-8")
    # _write_other_session_lock() ECRASE tout crew_lock.json (save_locks remplace
    # le fichier entier) : l'appeler ici effacerait le verrou de S1 pose juste
    # au-dessus. On fusionne donc directement dans les locks existants pour
    # ajouter la voisine de batch verrouillee par une 3e session.
    locks = h.load_locks()
    since = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    locks["sessions"]["OTHER"] = {
        "batch": "Batch Zone1", "tasks": [slug_b],
        "worktree": f"../{root.name}-batch-zone1", "branch": "crew/batch-zone1", "since": since,
    }
    h.save_locks(locks)

    decision = _run_stop(monkeypatch, capsys, session_id="S2")  # 1er tour Stop de S2 : n'a rien demarre

    assert decision is None or decision.get("decision") != "block", (
        "S2 ne doit pas etre bloquee pour une collision batch causee par une tache "
        f"qu'elle n'a jamais demarree (mis-attribution shared SNAP) : {decision}"
    )


def test_auto_commit_closure_no_op_when_finished_but_historique_untouched(repo):
    """finished non vide mais HISTORIQUE.md pas modifie (ex. suppression
    manuelle du fichier sans passer par la cloture crew) -> pas de commit."""
    root, dirs, ctx = repo
    slug = "ma-tache"
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
    monkeypatch.setattr(h, "MAIN_ROOT", h.ROOT)  # cle `batch` = cas checkout principal
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
    monkeypatch.setattr(h, "MAIN_ROOT", h.ROOT)  # cle `batch` = cas checkout principal
    """Une condition disparue (tache categorisee, chevauchement resolu) ne
    doit pas laisser une entree morte grossir locks['warned'] indefiniment,
    et si elle reapparait plus tard elle doit re-avertir immediatement."""
    locks = {"sessions": {}}
    t0 = datetime.datetime(2026, 8, 29, 10, 0, 0)
    h._throttle_warnings("batch", ["[batch] warning A"], locks, t0)
    t1 = t0 + datetime.timedelta(minutes=5)
    h._throttle_warnings("batch", [], locks, t1)  # condition resolue
    assert locks["warned"]["batch"] == {}

    t2 = t1 + datetime.timedelta(minutes=5)
    due = h._throttle_warnings("batch", ["[batch] warning A"], locks, t2)
    assert due == ["[batch] warning A"]  # reapparait -> pas de cooldown herite


def test_throttle_warnings_categories_are_independent():
    locks = {"sessions": {}}
    now = datetime.datetime(2026, 8, 29, 10, 0, 0)
    h._throttle_warnings("batch", ["same text"], locks, now)
    due = h._throttle_warnings("zone", ["same text"], locks, now)
    assert due == ["same text"]


def _run_stop_capture_err(monkeypatch, capsys, session_id="S1"):
    """Comme _run_stop, mais renvoie stderr au lieu de le laisser draine sans
    etre lu (capsys.readouterr() vide out ET err en un seul appel)."""
    payload = {"hook_event_name": "Stop", "session_id": session_id}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    return capsys.readouterr().err


def test_stop_hook_does_not_renag_same_batch_warning_next_turn(repo, monkeypatch, capsys):
    """check_batches() se declenche a chaque tour tant qu'une tache reste non
    categorisee dans CLAUDE_BATCH.md : sans throttle, le meme avertissement
    stderr serait re-imprime a CHAQUE tour Stop (cout contexte proportionnel
    au nombre de tours, pas a la realite du backlog)."""
    root, dirs, ctx = repo
    (dirs["TODO"] / "orpheline.md").write_text("# orpheline\n", encoding="utf-8")

    first_err = _run_stop_capture_err(monkeypatch, capsys)
    assert "orpheline.md" in first_err

    second_err = _run_stop_capture_err(monkeypatch, capsys)
    assert "orpheline.md" not in second_err


def test_prune_closed_batches_removes_fully_closed_section():
    text = (
        "# Batching\n\n"
        "## A classer\n\nplaceholder\n\n"
        "## Batch A\n\nZone : `fichiers/modules`\n\n- `<slug>.md`\n\n"
        "## Batch demo\n\nZone : `src/`\n\n"
        "1. ~~`task-one.md`~~ - fait. Voir `HISTORIQUE.md`.\n"
        "2. ~~`task-two.md`~~ - fait aussi.\n\n"
    )
    new_text, removed = h.prune_closed_batches(text)
    assert removed == ["Batch demo"]
    assert "Batch demo" not in new_text
    assert "task-one.md" not in new_text
    # Sections non concernées intactes
    assert "## Batch A" in new_text
    assert "<slug>.md" in new_text
    assert "## A classer" in new_text


def test_prune_closed_batches_keeps_placeholder_batch_untouched():
    """Un batch jamais rempli (0 tache reelle) n'est pas 'clos' : rien a retirer."""
    text = "## Batch A\n\nZone : `fichiers/modules`\n\n- `<slug>.md`\n\n"
    new_text, removed = h.prune_closed_batches(text)
    assert removed == []
    assert new_text == text


def test_prune_closed_batches_keeps_partially_closed_batch():
    text = (
        "## Batch open\n\nZone : `other/`\n\n"
        "1. ~~`closed-one.md`~~ - clos.\n"
        "2. `still-open.md` - pas fini.\n\n"
    )
    new_text, removed = h.prune_closed_batches(text)
    assert removed == []
    assert new_text == text


def test_prune_closed_batches_ignores_incidental_md_refs_in_zone_and_prose():
    """Des refs `*.md` dans la ligne Zone (ex. README.md, CHANGELOG.md) ou en
    prose (ex. 'voir HISTORIQUE.md') ne doivent pas etre comptees comme des
    taches ouvertes — seules les lignes de liste en tete (`- `/`N. `) comptent."""
    text = (
        "## Batch pkg\n\n"
        "Zone : `README.md`, `CHANGELOG.md`, `scripts/`\n\n"
        "1. ~~`only-task.md`~~ - fait, voir `HISTORIQUE.md` pour details.\n\n"
    )
    new_text, removed = h.prune_closed_batches(text)
    assert removed == ["Batch pkg"]
    assert new_text.strip() == ""


def _write_transcript(tmp_path, usages):
    """Ecrit un transcript JSONL minimal : un message assistant par usage
    donne (dans l'ordre), entrelace de lignes non-assistant/vides/corrompues
    pour verifier que seule la DERNIERE entree assistant valide est retenue."""
    path = tmp_path / "transcript.jsonl"
    lines = []
    for u in usages:
        lines.append('{"message": {"role": "user", "content": "hi"}}')
        lines.append("")  # ligne vide, doit etre ignoree
        lines.append("not json")  # ligne corrompue, doit etre ignoree
        lines.append(json.dumps({"message": {"role": "assistant", "usage": u}}))
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
    assert "contexte" in warnings[0]


def test_check_context_budget_uses_last_assistant_usage_not_first(tmp_path):
    """Contexte grandit tour apres tour : seule la derniere valeur compte,
    meme si un tour precedent depassait deja le seuil puis /clear a eu lieu."""
    transcript = _write_transcript(tmp_path, [
        {"input_tokens": 200_000},
        {"input_tokens": 1000},
    ])
    assert h.check_context_budget({"transcript_path": transcript}) == []


def _run_stop(monkeypatch, capsys, session_id="S1"):
    """Invoque h.main() comme le vrai hook Stop : stdin = payload JSON,
    stdout capture (decision JSON eventuelle si le tour est bloque).
    Pas de transcript_path -> check_context_budget no-op."""
    payload = {"hook_event_name": "Stop", "session_id": session_id}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    h.main()
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


def test_pause_move_not_reported_finished_keeps_lock(repo, monkeypatch, capsys):
    """CURRENT_TASKS -> PAUSED n'est pas une cloture : pas de 'terminee' au
    changelog, pas de purge du verrou live (cf. tache
    add-paused-lifecycle-state, code review)."""
    root, dirs, ctx = repo
    slug = "ma-tache.md"
    _write_single_task_batch(dirs, slugs=(slug,))
    (dirs["TODO"] / slug).unlink()
    (dirs["CURRENT_TASKS"] / slug).write_text(f"# {slug}\n", encoding="utf-8")

    sections = h.load_sections()
    locks = h.load_locks()
    h._register_task_lock(slug, "S1", locks, datetime.datetime.now(), sections)
    h.save_locks(locks)

    _run_stop(monkeypatch, capsys)  # etablit le snapshot de reference (prev vide)

    (dirs["CURRENT_TASKS"] / slug).replace(dirs["PAUSED"] / slug)  # simule le git mv de pause

    _run_stop(monkeypatch, capsys)

    changelog = (ctx / "CHANGELOG_TACHES.md").read_text(encoding="utf-8")
    assert f"**mise en pause** : `{slug}`" in changelog
    assert "terminée" not in changelog
    assert slug in h.load_locks()["sessions"]["S1"]["tasks"]


def test_resumed_task_relabeled_and_rechecked_for_batch_collision(repo, monkeypatch, capsys):
    """PAUSED -> CURRENT_TASKS est une reprise ('reprise (post-pause)'), pas
    un premier demarrage, ET doit repasser sous check_batch_collisions comme
    un vrai demarrage. Avant fix (code review) : `started` etait mute pour
    exclure les taches reprises, donc jamais revalidees -> ce test bloquerait
    a tort sur du code non fixe (pas de collision detectee) et confirme le
    fix (collision bien detectee)."""
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

    _run_stop(monkeypatch, capsys, session_id="S1")  # baseline : task-a en PAUSED, task-b en CURRENT_TASKS

    (dirs["PAUSED"] / slug_a).replace(dirs["CURRENT_TASKS"] / slug_a)  # reprise post-pause

    decision = _run_stop(monkeypatch, capsys, session_id="S1")

    changelog = (ctx / "CHANGELOG_TACHES.md").read_text(encoding="utf-8")
    assert f"**reprise (post-pause)** : `{slug_a}`" in changelog
    assert f"**démarrée** : `{slug_a}`" not in changelog

    assert decision is not None
    assert decision["decision"] == "block"
    assert "collision" in decision["reason"].lower()


def test_dup_paused_and_current_tasks_blocks(repo, monkeypatch, capsys):
    """Reutilise l'invariant existant (jamais deux dossiers a la fois) pour
    PAUSED : un slug present a la fois dans PAUSED/ et CURRENT_TASKS/ doit
    bloquer le tour."""
    root, dirs, ctx = repo
    slug = "ma-tache.md"
    (dirs["CURRENT_TASKS"] / slug).write_text(f"# {slug}\n", encoding="utf-8")
    (dirs["PAUSED"] / slug).write_text(f"# {slug}\n", encoding="utf-8")

    decision = _run_stop(monkeypatch, capsys)

    assert decision is not None
    assert decision["decision"] == "block"
    assert "PAUSED" in decision["reason"]


def test_rotate_historique_entries_moves_old_entries_keeps_recent():
    cutoff = datetime.date(2026, 3, 1)
    text = (
        "# Historique des tâches terminées\n\n"
        "Intro.\n\n"
        "## tache-vieille — 2025-01-10\n"
        "Quoi : ancienne.\n\n"
        "## tache-recente — 2026-08-20\n"
        "Quoi : recente.\n\n"
    )
    kept, archived, slugs = h.rotate_historique_entries(text, cutoff)
    assert slugs == ["tache-vieille"]
    assert "tache-vieille" not in kept
    assert "tache-recente" in kept
    assert "Intro." in kept  # préambule jamais archivé
    assert "tache-vieille" in archived
    assert "tache-recente" not in archived


def test_rotate_historique_entries_ignores_undated_entries():
    """En-tete sans date parseable (entree malformee) : jamais rotee a
    l'aveugle, faute de pouvoir la comparer au cutoff."""
    cutoff = datetime.date(2026, 3, 1)
    text = "# Historique\n\n## verif-fork-throwaway\nQuoi : sans date.\n\n"
    kept, archived, slugs = h.rotate_historique_entries(text, cutoff)
    assert slugs == []
    assert kept == text
    assert archived == ""


def test_rotate_historique_entries_ignores_entries_inside_html_comment():
    """L'exemple de format documente en commentaire HTML (cf. HISTORIQUE.md
    reel : bloc <!-- Exemple : ## <slug> — AAAA-MM-JJ ... -->) ne doit
    jamais etre confondu avec une vraie entree a archiver."""
    cutoff = datetime.date(2026, 3, 1)
    text = (
        "# Historique\n\n"
        "<!-- Exemple :\n"
        "## <slug de la tâche> — AAAA-MM-JJ\n"
        "Quoi : ...\n"
        "-->\n\n"
        "## tache-reelle — 2025-01-10\n"
        "Quoi : reelle.\n\n"
    )
    kept, archived, slugs = h.rotate_historique_entries(text, cutoff)
    assert slugs == ["tache-reelle"]
    assert "<!-- Exemple :" in kept  # le commentaire reste dans le fichier vivant
    assert "<slug de la tâche>" in kept
    assert "tache-reelle" not in kept
    assert "tache-reelle" in archived


def test_rotate_historique_entries_no_op_when_nothing_old():
    cutoff = datetime.date(2020, 1, 1)
    text = "# Historique\n\n## tache-recente — 2026-08-20\nQuoi : recente.\n\n"
    kept, archived, slugs = h.rotate_historique_entries(text, cutoff)
    assert slugs == []
    assert kept == text
    assert archived == ""


def test_rotate_historique_writes_archive_and_trims_live_file(repo, monkeypatch):
    root, dirs, ctx = repo
    histo = ctx / "HISTORIQUE.md"
    histo.write_text(
        "# Historique des tâches terminées\n\nIntro.\n\n"
        "## tache-vieille — 2025-01-10\nQuoi : ancienne.\n\n"
        "## tache-recente — 2026-08-20\nQuoi : recente.\n\n",
        encoding="utf-8",
    )
    archive = ctx / "HISTORIQUE_ARCHIVE.md"
    monkeypatch.setattr(h, "HISTORIQUE", histo)
    monkeypatch.setattr(h, "HISTORIQUE_ARCHIVE", archive)

    rotated = h.rotate_historique(datetime.datetime(2026, 8, 29))

    assert rotated == ["tache-vieille"]
    live = histo.read_text(encoding="utf-8")
    assert "tache-vieille" not in live
    assert "tache-recente" in live
    assert archive.exists()
    assert "tache-vieille" in archive.read_text(encoding="utf-8")


def _seed_session_lock(root, slug, session_id="S1"):
    since = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    h.save_locks({"sessions": {session_id: {
        "batch": "Batch Zone1", "tasks": [slug],
        "worktree": f"../{root.name}-batch-zone1", "branch": "crew/batch-zone1", "since": since,
    }}})


def test_stop_purges_lock_of_task_closed_in_worktree(repo, monkeypatch, capsys):
    """Tache demarree ET close dans un worktree : le checkout principal ne l'a
    jamais vue en CURRENT_TASKS/, donc jamais dans `finished` -> le verrou
    restait indefiniment (session fantome dans crew_lock.json). Une tache
    absente du checkout principal ET du worktree de la session est close."""
    root, dirs, ctx = repo
    slug = "close-en-worktree.md"
    _seed_session_lock(root, slug)

    _run_stop(monkeypatch, capsys, session_id="OTHER")

    assert "S1" not in h.load_locks()["sessions"]


def test_stop_keeps_lock_of_task_current_in_session_worktree(repo, monkeypatch, capsys):
    root, dirs, ctx = repo
    slug = "en-cours-worktree.md"
    wt_current = root.parent / f"{root.name}-batch-zone1" / "crew" / "CURRENT_TASKS"
    wt_current.mkdir(parents=True)
    (wt_current / slug).write_text(f"# {slug}\n", encoding="utf-8")
    _seed_session_lock(root, slug)

    _run_stop(monkeypatch, capsys, session_id="OTHER")

    assert h.load_locks()["sessions"]["S1"]["tasks"] == [slug]


def test_stop_keeps_lock_of_task_still_in_main_todo(repo, monkeypatch, capsys):
    """Worktree pas encore merge : la tache est encore dans TODO/ du checkout
    principal -> toujours vivante, verrou conserve."""
    root, dirs, ctx = repo
    slug = "pas-encore-merge.md"
    (dirs["TODO"] / slug).write_text(f"# {slug}\n", encoding="utf-8")
    _seed_session_lock(root, slug)

    _run_stop(monkeypatch, capsys, session_id="OTHER")

    assert h.load_locks()["sessions"]["S1"]["tasks"] == [slug]


def test_purge_closed_task_locks_skipped_outside_main_checkout(repo, monkeypatch):
    """Depuis un worktree (`.git` = fichier), ROOT ne voit pas l'etat crew du
    checkout principal : ne rien purger plutot que de liberer un vrai verrou."""
    root, dirs, ctx = repo
    worktree_root = root.parent / f"{root.name}-wt"
    (worktree_root / "crew" / "TODO").mkdir(parents=True)
    (worktree_root / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    monkeypatch.setattr(h, "ROOT", worktree_root)
    locks = {"sessions": {"S1": {"tasks": ["inconnue.md"], "worktree": None}}}

    assert h.purge_closed_task_locks(locks) == []
    assert locks["sessions"]["S1"]["tasks"] == ["inconnue.md"]


def _write_two_overlapping_batches(slug_a="task-a.md", slug_b="task-b.md"):
    """Deux batchs dont les `Zone :` se chevauchent (`shared/` vs `shared/x.py`).
    Ne cree aucun fichier de tache : chaque test place a et b ou il veut."""
    h.BATCH_FILE.write_text(
        "# Batching\n\n"
        f"## Batch A · ⏳ pas démarré\n\nZone : `shared/`\n\n- `{slug_a}`\n\n"
        f"## Batch B · ⏳ pas démarré\n\nZone : `shared/x.py`\n\n- `{slug_b}`\n",
        encoding="utf-8",
    )


def _lock_sessions(root, by_session):
    """crew_lock.json avec une session live par entree {session_id: [slugs]}."""
    since = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    h.save_locks({"sessions": {
        sid: {"batch": None, "tasks": list(tasks), "worktree": f"../{root.name}-batch-{sid.lower()}",
              "branch": f"crew/batch-{sid.lower()}", "since": since}
        for sid, tasks in by_session.items()
    }})


def test_zone_overlap_ignores_batches_with_only_todo_tasks(repo, monkeypatch, capsys):
    """Faux positif constate (voyageo/time2cook) : deux batchs « pas demarre »
    dont toutes les taches sont en TODO/ etaient traites comme actifs ->
    avertissement `[zone]` a chaque tour. Actif = >=1 tache en
    CURRENT_TASKS/PAUSED ou tenue par un verrou (CLAUDE.md § Batching)."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    for s in ("task-a.md", "task-b.md"):
        (dirs["TODO"] / s).write_text(f"# {s}\n", encoding="utf-8")

    err = _run_stop_capture_err(monkeypatch, capsys)

    assert "[zone]" not in err


def test_zone_overlap_warns_when_both_batches_in_progress(repo, monkeypatch, capsys):
    """Garde-fou conserve : un batch en CURRENT_TASKS et l'autre en PAUSED
    (pause = toujours actif) se chevauchant -> avertissement."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    (dirs["CURRENT_TASKS"] / "task-a.md").write_text("# a\n", encoding="utf-8")
    (dirs["PAUSED"] / "task-b.md").write_text("# b\n", encoding="utf-8")

    err = _run_stop_capture_err(monkeypatch, capsys)

    assert "[zone]" in err


def test_zone_overlap_counts_task_locked_from_worktree(repo, monkeypatch, capsys):
    """Tache demarree dans un worktree de batch : encore en TODO/ dans le
    checkout principal, mais tenue par un verrou live -> son batch est actif."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    (dirs["TODO"] / "task-a.md").write_text("# a\n", encoding="utf-8")
    (dirs["CURRENT_TASKS"] / "task-b.md").write_text("# b\n", encoding="utf-8")
    _lock_sessions(root, {"WT": ["task-a.md"]})

    # S1 (session du tour) s'approprie task-b via le fallback `started` :
    # chevauchement cross-session -> bloquant (stdout) plutot qu'avertissement.
    decision = _run_stop(monkeypatch, capsys, session_id="S1")

    assert decision and decision.get("decision") == "block", decision
    assert "zone" in decision["reason"]


def test_zone_overlap_does_not_block_uninvolved_third_session(repo, monkeypatch, capsys):
    """Deux batchs en collision verrouilles par S1 et S2 : une 3e session S3,
    etrangere aux deux, ne doit pas etre bloquee (elle ne peut rien y faire ;
    la bloquer boucle Stop->reinvoke). Avertissement seulement."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    for s in ("task-a.md", "task-b.md"):
        (dirs["TODO"] / s).write_text(f"# {s}\n", encoding="utf-8")
    _lock_sessions(root, {"S1": ["task-a.md"], "S2": ["task-b.md"]})

    decision = _run_stop(monkeypatch, capsys, session_id="S3")

    assert decision is None or decision.get("decision") != "block", decision


def test_zone_overlap_blocks_involved_session(repo, monkeypatch, capsys):
    """Meme collision, vue par S1 (impliquee) : blocage conserve."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    for s in ("task-a.md", "task-b.md"):
        (dirs["TODO"] / s).write_text(f"# {s}\n", encoding="utf-8")
    _lock_sessions(root, {"S1": ["task-a.md"], "S2": ["task-b.md"]})

    decision = _run_stop(monkeypatch, capsys, session_id="S1")

    assert decision and decision.get("decision") == "block", decision


def test_in_progress_task_slugs_ignores_expired_session_lock(repo):
    """Une session morte (since > LOCK_TTL, pas encore purgee : dashboard ou
    lecture hors Stop) ne doit pas rendre son batch actif."""
    root, dirs, ctx = repo
    old = (datetime.datetime.now() - h.LOCK_TTL - datetime.timedelta(minutes=1)).isoformat()
    fresh = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
    locks = {"sessions": {
        "DEAD": {"tasks": ["morte.md"], "since": old},
        "LIVE": {"tasks": ["vivante.md"], "since": fresh},
    }}

    assert h.in_progress_task_slugs(locks) == {"vivante.md"}


def test_check_zone_overlaps_observer_view_blocks_cross_session(repo):
    """observer=True (dashboard) : vue observateur, tout conflit
    cross-session reste signale comme bloquant."""
    root, dirs, ctx = repo
    _write_two_overlapping_batches()
    _lock_sessions(root, {"S1": ["task-a.md"], "S2": ["task-b.md"]})
    locks = h.load_locks()

    warnings, blocking = h.check_zone_overlaps(
        h.load_sections(), h.in_progress_task_slugs(locks), locks, observer=True)

    assert blocking and not warnings


# --- Verrou partage entre checkout principal et worktrees (tache verrou-partage-worktrees) ---

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
    """Fait pointer le module sur `root` (checkout principal ou worktree) comme
    si le hook y tournait : ROOT/CTX/BATCH_FILE locaux, verrou partage."""
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
    assert sessions["B"]["tasks"] == ["new-b.md"]  # since le plus recent gagne
    assert sessions["C"]["tasks"] == ["c.md"]
    assert not legacy.exists()


def test_task_state_snapshot_stays_local():
    """SNAP (diff d'etat par checkout) reste sous ROOT ; seul le verrou migre."""
    assert h.SNAP == h.ROOT / "crew" / "CLAUDE_CONTEXT" / ".task_state.json"
    assert h.LOCKS_FILE == h.MAIN_ROOT / "crew" / "CLAUDE_CONTEXT" / "crew_lock.json"


def test_main_root_fallback_main_without_claude_context(tmp_path):
    main = _fake_main(tmp_path, with_crew=False)
    (main / "crew").mkdir()
    wt = _fake_worktree(tmp_path, main)
    assert h._resolve_main_root(wt) == wt
