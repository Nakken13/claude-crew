# -*- coding: utf-8 -*-
"""Tests pour crew_hook.py. Aucune suite pytest n'existait avant (verifie -
seule validation existante = les checklists crew/TESTS/IA|DEV/, non
automatisees). Se concentre sur auto_commit_closure (tache
hook-auto-commit-cloture-tache) : chaque test construit un depot git
temporaire isole (jamais le vrai depot) et monkeypatch les constantes
module-level de crew_hook pour y pointer, avant d'appeler la fonction
reelle — pas de mock sur subprocess/git, comportement reel verifie."""
import datetime
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
    monkeypatch.setattr(h, "BATCH_FILE", batch_file)
    monkeypatch.setattr(h, "CHANGELOG", changelog)
    monkeypatch.setattr(h, "BATCH_LOCKS_MD", batch_locks_md)
    monkeypatch.setattr(h, "LOCKS_FILE", locks_file)
    monkeypatch.setattr(h, "LOCKS_MUTEX", locks_mutex)
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
