# -*- coding: utf-8 -*-
"""Hook Stop/SessionEnd/PreToolUse — gestion des tâches du projet.
À chaque fin de tour (Stop) :
  1. régénère crew/<dir>/INDEX.md (titres + liens),
  2. journalise les transitions (démarrée / terminée / ajoutée) dans
     crew/CLAUDE_CONTEXT/CHANGELOG_TACHES.md,
  3. bloque la fin de tour si une tâche est à la fois dans TODO/ et CURRENT_TASKS/,
  4. rappelle d'historiser + sortir les tests quand une tâche vient d'être terminée,
  5. maintient des verrous live PAR SESSION (crew_lock.json, anti-collision
     multi-Claude, écriture protégée par LocksMutex) et bloque le tour si une
     tâche démarrée a une voisine de batch déjà verrouillée par une autre
     session, ou si deux batchs actifs à zones chevauchantes sont verrouillés
     par des sessions différentes (cf. crew/CLAUDE_CONTEXT/BATCH_LOCKS.md,
     régénéré à chaque tour),
  6. commit git LOCAL UNIQUEMENT (jamais de push, cf. `auto_commit_closure`)
     scopé à `crew/` quand une tâche vient d'être réellement clôturée dans ce
     même tour (fichier disparu de `CURRENT_TASKS/` + `HISTORIQUE.md`
     effectivement modifié) — trace git systématique de chaque clôture sans
     rien pousser automatiquement, le push reste une décision humaine.
En PreToolUse (matcher Bash|Edit|Write|MultiEdit, cf. gate_pretooluse) :
  - `Edit`/`Write`/`MultiEdit` : bloque avant écriture si `file_path` tombe
    sous une `Zone:` de batch verrouillée par une AUTRE session.
  - `Bash` : contrôle préventif avant exécution d'un `git mv` TODO->CURRENT_TASKS
    (tâche catégorisée + pas de collision), plus un scan best-effort des
    commandes mutantes (`rm`/`mv`/`cp`/redirection `>`) contre les mêmes zones
    verrouillées — Layer 2, filet de sécurité en complément de l'isolation
    physique par worktree (Layer 1, portée par `/crew-start`).
Ne casse jamais le tour : toute erreur interne -> exit 0 silencieux (sauf le
blocage volontaire exit(2) de gate_pretooluse).
"""
import json, os, re, sys, shlex, time, datetime, pathlib, shutil, fnmatch, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent  # racine du projet
CREW = ROOT / "crew"
DIRS = {
    "PROBLEMS": CREW / "PROBLEMS",
    "TODO": CREW / "TODO",
    "ICEBOX": CREW / "ICEBOX",
    "CURRENT_TASKS": CREW / "CURRENT_TASKS",
    "TESTS": CREW / "TESTS",
    "TESTS/IA": CREW / "TESTS" / "IA",
    "TESTS/DEV": CREW / "TESTS" / "DEV",
}
CTX = CREW / "CLAUDE_CONTEXT"
SNAP = CTX / ".task_state.json"
CHANGELOG = CTX / "CHANGELOG_TACHES.md"
BATCH_FILE = CREW / "CLAUDE_BATCH.md"
LOCKS_FILE = CTX / "crew_lock.json"  # remplace .batch_locks.json (schema session->{batch,tasks,worktree,branch,since})
LOCKS_MUTEX = CTX / ".crew_lock.mutex"
BATCH_LOCKS_MD = CTX / "BATCH_LOCKS.md"
LOCK_TTL = datetime.timedelta(hours=6)
MUTEX_TTL_SEC = 30  # mutex bloque plus longtemps -> session crashee en pleine ecriture, on le degage
MUTEX_WAIT_SEC = 2.0  # attente max avant de continuer sans le mutex (best-effort, ne bloque jamais le tour)

INTRO = {
    "PROBLEMS": "Problèmes. Résolu → déplacer le contexte vers `HISTORIQUE.md`.\n\n",
    "TODO": "Tâches pas commencées. Démarrer = déplacer le fichier vers `crew/CURRENT_TASKS/` (cf. `CLAUDE.md`).\n\n",
    "ICEBOX": "Idées/tâches parkées volontairement (distinct de TODO). Pour reprendre : déplacer vers `crew/TODO/` d'abord.\n\n",
    "CURRENT_TASKS": "Tâches en cours. Finie → supprimer + entrée `crew/CLAUDE_CONTEXT/HISTORIQUE.md` + `crew/TESTS/<chantier>.md`.\n\n",
    "TESTS": ("Checklists de validation des features finies (cf. `README.md`). "
              "Triées par exécutant :\n"
              "- [IA](IA/INDEX.md) — tests que l'IA peut dérouler seule (🤖 auto + 🔍 config/curl/DB/logs)\n"
              "- [DEV](DEV/INDEX.md) — tests nécessitant le dev (🖱️ manuel/visuel + items non outillés)\n\n"),
    "TESTS/IA": "Tests exécutables par l'IA (🤖 auto + 🔍 config/requête directe). Source unique par chantier ; le pendant 🖱️ est dans `../DEV/`.\n\n",
    "TESTS/DEV": "Tests nécessitant le dev (🖱️ manuel/visuel navigateur, ou item non outillé pour l'IA). Le pendant automatisable est dans `../IA/`.\n\n",
}


def title_of(f):
    try:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return f.stem


def task_files(d):
    out = {}
    if d.exists():
        for f in sorted(d.glob("*.md")):
            if f.name in ("INDEX.md", "README.md") or f.name.startswith("_"):
                continue
            out[f.name] = title_of(f)
    return out


def regen_index(name, d):
    files = task_files(d)
    lines = [f"# Index {name}\n\n", INTRO.get(name, "")]
    for fn, t in files.items():
        lines.append(f"- [{t}]({fn})\n")
    if d.exists():
        (d / "INDEX.md").write_text("".join(lines), encoding="utf-8")
    return list(files.keys())


def process_completed_tests():
    """Vérifie les fichiers de test dans TESTS/IA/. S'ils sont entièrement cochés
    ([x] présents, 0 [ ]), les déplace vers CLAUDE_CONTEXT/TESTS_DONE/."""
    done_dir = CTX / "TESTS_DONE"
    done_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    ia_dir = DIRS["TESTS/IA"]
    if ia_dir.exists():
        for f in ia_dir.glob("*.md"):
            if f.name in ("INDEX.md", "README.md") or f.name.startswith("_"):
                continue
            content = f.read_text(encoding="utf-8")
            if "[ ]" not in content and ("[x]" in content.lower() or "[X]" in content):
                # Utiliser replace() pour écraser si le fichier existe déjà
                f.replace(done_dir / f.name)
                moved.append(f.name)
    return moved


def check_batches():
    """Avertit (non bloquant) si une tâche TODO/CURRENT n'est pas catégorisée dans
    CLAUDE_BATCH.md, ou si le fichier référence une tâche disparue. Refs = slugs
    entre backticks (`slug.md`) → les placeholders `<...>.md` sont ignorés. Les
    refs barrées (~~`slug.md`~~) marquent une tâche déjà terminée/retirée par
    convention du projet : leur fichier a normalement été supprimé, donc elles
    sont exclues du scan pour ne pas générer un faux positif à chaque clôture."""
    warnings = []
    if not BATCH_FILE.exists():
        return warnings
    text = re.sub(r"~~.*?~~", "", BATCH_FILE.read_text(encoding="utf-8"), flags=re.DOTALL)
    referenced = set(re.findall(r"`([\w\-.]+\.md)`", text))
    actual = set()
    for d in (DIRS["TODO"], DIRS["CURRENT_TASKS"]):
        if d.exists():
            for f in d.glob("*.md"):
                if f.name in ("INDEX.md", "README.md") or f.name.startswith("_"):
                    continue
                actual.add(f.name)
    for f in sorted(actual - referenced):
        warnings.append(f"[batch] Tache non categorisee dans CLAUDE_BATCH.md : `{f}`")
    for f in sorted(referenced - actual):
        warnings.append(f"[batch] CLAUDE_BATCH.md reference une tache inexistante : `{f}`")
    return warnings


def rotate_graphify_snapshots(keep=3):
    """Purge les snapshots datés graphify-out/AAAA-MM-JJ (régénérables via
    `graphify update .`), en gardant les `keep` plus récents. Tri lexical
    = tri chronologique sur ce format de nom."""
    out = ROOT / "graphify-out"
    if not out.exists():
        return
    dated = sorted(d for d in out.glob("20??-??-??") if d.is_dir())
    for d in dated[:-keep]:
        shutil.rmtree(d, ignore_errors=True)


class LocksMutex:
    """Verrou fichier portable (Windows compris : pas de fcntl) autour de la
    section critique read-modify-write de crew_lock.json. Implemente via
    O_CREAT|O_EXCL sur un fichier marqueur a part (creation atomique garantie
    par l'OS des deux cotes). Best-effort : quelques tentatives courtes puis on
    continue sans le mutex plutot que de risquer de bloquer le tour (le hook ne
    doit jamais casser un tour) ; un mutex tenu plus de MUTEX_TTL_SEC est jete
    (session probablement crashee en pleine ecriture)."""

    def __init__(self):
        self._acquired = False

    def __enter__(self):
        self._acquired = False
        deadline = time.monotonic() + MUTEX_WAIT_SEC
        while True:
            try:
                fd = os.open(str(LOCKS_MUTEX), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self._acquired = True
                return self
            except FileExistsError:
                try:
                    if time.time() - LOCKS_MUTEX.stat().st_mtime > MUTEX_TTL_SEC:
                        LOCKS_MUTEX.unlink(missing_ok=True)
                        continue
                except Exception:
                    pass
                if time.monotonic() >= deadline:
                    return self  # best-effort : pas acquis, on continue quand meme
                time.sleep(0.05)
            except Exception:
                return self  # best-effort : pas de mutex, on continue quand meme

    def __exit__(self, *exc_info):
        # Ne jamais retirer le marqueur si CETTE instance ne l'a pas cree
        # (timeout/erreur au enter) : sinon on efface le verrou d'une AUTRE
        # session encore en train d'ecrire (cf. code-review).
        if self._acquired:
            try:
                LOCKS_MUTEX.unlink()
            except Exception:
                pass


def load_locks():
    """Charge crew_lock.json. Forme garantie en retour : {"sessions": {...}}
    (une entree par session active, cf. module docstring) — un fichier absent,
    corrompu, ou a l'ancien format plat (.batch_locks.json) retombe sur une
    base vide plutot que de propager une forme inattendue aux appelants."""
    if LOCKS_FILE.exists():
        try:
            data = json.loads(LOCKS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("sessions"), dict):
                return data
        except Exception:
            pass
    return {"sessions": {}}


def save_locks(locks):
    """Ecriture atomique (temp file + os.replace) : evite un crew_lock.json
    tronque si le process est tue en cours d'ecriture."""
    tmp = LOCKS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(locks, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(LOCKS_FILE))


def purge_stale_locks(locks, now_dt):
    """Retire les entrees SESSION plus vieilles que LOCK_TTL (session probablement
    crashee) — tasks + worktree + branch partent ensemble, une session ne peut
    pas etre a moitie purgee. Retourne la liste triee des session_id purgees."""
    sessions = locks.setdefault("sessions", {})
    stale = []
    for sid, info in list(sessions.items()):
        since_raw = info.get("since") if isinstance(info, dict) else None
        try:
            since = datetime.datetime.fromisoformat(since_raw)
            expired = now_dt - since > LOCK_TTL
        except Exception:
            expired = True  # entree corrompue -> on la degage aussi
        if expired:
            stale.append(sid)
            del sessions[sid]
    return sorted(stale)


def _slug_session_map(locks):
    """Vue derivee slug -> session_id a partir de sessions[*].tasks — source
    unique consommee par check_batch_collisions / _section_lock_sessions /
    regen_batch_locks_md, pour eviter de dupliquer la logique de derivation.
    Un slug ne devrait jamais appartenir a 2 sessions a la fois (violation
    d'invariant plutot qu'un cas normal) ; si ca arrive quand meme (bug
    ailleurs ou edit manuel de crew_lock.json), la derniere session iteree
    gagne silencieusement sans ce warning — le signaler sur stderr plutot que
    de laisser passer sans trace."""
    out = {}
    for sid, info in locks.get("sessions", {}).items():
        for slug in info.get("tasks", []) or []:
            if slug in out and out[slug] != sid:
                sys.stderr.write(
                    f"[crew_lock] incoherence : `{slug}` apparait dans les tasks de 2 sessions "
                    f"(`{out[slug]}` et `{sid}`) — verrou probablement corrompu, "
                    f"session `{sid}` retenue.\n"
                )
            out[slug] = sid
    return out


def _batch_slug(header):
    """Slug filesystem/branch-safe derive du header de section batch (ex.
    'Batch plugin-packaging' -> 'plugin-packaging'), utilise pour nommer le
    worktree et la branche dediee de ce batch de facon deterministe."""
    text = re.sub(r"^Batch\b\s*[:\-—]?\s*", "", header or "", flags=re.IGNORECASE).strip()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "batch"


def _worktree_paths_for(header):
    """Chemin worktree (sibling du checkout principal) + nom de branche
    deterministes pour un batch, derives de son header (cf. _batch_slug)."""
    slug = _batch_slug(header)
    return f"../{ROOT.name}-batch-{slug}", f"crew/batch-{slug}"


def _register_task_lock(slug, session_id, locks, now_dt, sections=None):
    """Ajoute `slug` aux tasks de la session `session_id` dans `locks`
    (cree l'entree session si absente, en derivant batch/worktree/branch
    depuis CLAUDE_BATCH.md via find_section_for), rafraichit son `since`.
    Idempotent : ne duplique pas `slug` si deja present. Une session est
    supposee ne porter qu'un seul batch a la fois (regle produit de
    /crew-start, § 'Ce que ce skill ne fait pas') ; si un slug d'un AUTRE
    batch est enregistre sur une session qui en a deja un, le batch/worktree/
    branch de l'entree ne sont PAS ecrases (garde la premiere source de
    verite) mais l'incoherence est signalee sur stderr plutot que de rester
    invisible (meme esprit que le warning de _slug_session_map). Retourne
    l'entree session mise a jour."""
    sections = sections if sections is not None else load_sections()
    section = find_section_for(slug, sections)
    sessions = locks.setdefault("sessions", {})
    info = sessions.setdefault(session_id, {"batch": None, "tasks": [], "worktree": None,
                                              "branch": None, "since": now_dt.isoformat()})
    info["since"] = now_dt.isoformat()
    if section and info.get("batch") is None:
        info["batch"] = section["header"]
        info["worktree"], info["branch"] = _worktree_paths_for(section["header"])
    elif section and info.get("batch") != section["header"]:
        sys.stderr.write(
            f"[crew_lock] incoherence : session `{session_id}` enregistre `{slug}` "
            f"(batch « {section['header']} ») alors qu'elle detient deja le batch "
            f"« {info.get('batch')} » — une session ne devrait porter qu'un seul batch a la fois.\n"
        )
    if slug not in info["tasks"]:
        info["tasks"].append(slug)
    return info


def slugs_by_batch_section(text):
    """Parse CLAUDE_BATCH.md : decoupe sur les en-tetes '## Batch'/'### Batch',
    extrait pour chaque section les slugs `xxx.md` references entre backticks
    (format nu ou chemin complet `crew/<sous-dossier>/xxx.md`), et les chemins
    declares sur sa ligne `Zone : ...` (pour la detection de chevauchement
    inter-batchs, cf. check_zone_overlaps)."""
    sections = []
    headers = list(re.finditer(r"^#{2,3}\s*Batch\b.*$", text, re.MULTILINE))
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end]
        raw_refs = re.findall(r"`(?:[\w\-./]*/)?([\w\-.]+\.md)`", body)
        slugs = set(raw_refs)
        zone_match = re.search(r"^\*{0,2}Zone\b[^:\n]*:\*{0,2}\s*(.+)$", body, re.MULTILINE)
        zone_paths = set(re.findall(r"`([^`]+)`", zone_match.group(1))) if zone_match else set()
        sections.append({"header": m.group().lstrip("#").strip(), "slugs": slugs, "zone_paths": zone_paths})
    return sections


def find_section_for(slug, sections):
    for section in sections:
        if slug in section["slugs"]:
            return section
    return None


def load_sections():
    """Parse CLAUDE_BATCH.md en sections de batch (liste vide si absent).
    Utilise a la fois par le hook Stop (main) et la garde PreToolUse
    (gate_pretooluse) — source unique pour eviter la duplication."""
    return slugs_by_batch_section(BATCH_FILE.read_text(encoding="utf-8")) if BATCH_FILE.exists() else []


def check_batch_collisions(started, sections, locks, session_id):
    """Pour chaque tache qui demarre, verifie que ses voisines de meme section
    de batch ne sont pas deja verrouillees par une AUTRE session. Retourne une
    raison de blocage combinee (ou None)."""
    slug_sessions = _slug_session_map(locks)
    reasons = []
    for f in sorted(started):
        section = find_section_for(f, sections)
        if not section:
            continue
        for neighbor in sorted(section["slugs"] - {f}):
            other_session = slug_sessions.get(neighbor)
            if other_session and other_session != session_id:
                since = locks.get("sessions", {}).get(other_session, {}).get("since", "?")
                reasons.append(
                    f"batch « {section['header']} » : `{f}` demarre alors que `{neighbor}` "
                    f"est deja verrouille par une autre session (depuis {since})"
                )
    if not reasons:
        return None
    return ("Verrou live batch — collision detectee : " + " ; ".join(reasons) +
            ". Attendre la fin de l'autre session ou choisir une tache d'un autre batch.")


def _tokenize_command(command):
    """Tokenise best-effort une commande Bash (potentiellement composee :
    `a; b && c`) en tokens normalises separateur POSIX (`/`). `posix=True`
    est fige (pas `sys.platform`-dependant) : le tool Bash execute toujours
    du shell POSIX (Git Bash), quel que soit l'OS hote — sinon les guillemets
    autour d'un chemin restent dans le token sur Windows. Fallback sur un
    simple `.split()` si `shlex` echoue (shell trop exotique pour lui) —
    source unique partagee par `_extract_git_mv_task` et
    `_extract_candidate_paths`, les deux scans best-effort du gate Bash."""
    try:
        tokens = shlex.split(command, posix=True)
    except Exception:
        tokens = command.split()
    return [t.replace("\\", "/") for t in tokens]


def _extract_git_mv_task(command):
    """Si `command` contient un `git mv` deplacant un fichier depuis
    crew/TODO/ vers crew/CURRENT_TASKS/, retourne son slug (nom de fichier).
    Sinon None. Best-effort : ne parse pas un shell complexe, couvre
    seulement le cas documente `git mv crew/TODO/x.md crew/CURRENT_TASKS/x.md`
    (avec eventuels flags avant les deux chemins). Essaie TOUTES les
    occurrences de `mv` dans la commande (pas seulement la premiere) : une
    commande composee peut avoir un `mv` sans rapport avant le vrai `git mv`
    a surveiller."""
    todo_name, current_name = DIRS["TODO"].name, DIRS["CURRENT_TASKS"].name
    if "mv" not in command or todo_name not in command or current_name not in command:
        return None
    norm = _tokenize_command(command)
    for mv_i, tok in enumerate(norm):
        if tok != "mv":
            continue
        args = [t for t in norm[mv_i + 1:] if not t.startswith("-")]
        if len(args) < 2:
            continue
        src, dst = args[0], args[1]
        if f"{todo_name}/" not in src or f"{current_name}/" not in dst:
            continue
        if not src.endswith(".md"):
            continue
        return src.rsplit("/", 1)[-1]
    return None


def _extract_resume_claim(command):
    """Reconnait le marqueur no-op `: "crew-resume:<slug>.md"` qu'un
    `/crew-start` (Cas A : reprise d'une tache DEJA en CURRENT_TASKS, pas de
    `git mv` donc rien pour `_extract_git_mv_task` a intercepter) doit executer
    avant de reprendre le travail. `:` est le no-op Bash (aucun effet de bord)
    — seul le texte de la commande transporte l'intention jusqu'au hook.
    Retourne le slug si trouve, sinon None."""
    m = re.search(r"crew-resume:([\w\-.]+\.md)", command)
    return m.group(1) if m else None


def _claim_lock(slug, session_id, action_verb, sections=None, extra_check=None, on_success=None):
    """Primitive partagee par `_claim_resume_lock` et `_claim_git_mv_lock` :
    sous mutex, reload + purge + verifie qu'aucune AUTRE session ne detient
    deja ce slug exact (TOCTOU-safe vis-a-vis de toute lecture de `locks`
    faite par l'appelant AVANT le mutex), puis un `extra_check(locks) ->
    reason|None` optionnel (ex. `check_batch_collisions` pour les voisines de
    batch), enregistre le verrou (`_register_task_lock`) et sauvegarde.
    Bloque (exit 2 + stderr) sur toute collision — `action_verb` ('reprendre'/
    'demarrer') humanise le message. `on_success(locks)` optionnel s'execute
    juste apres `save_locks`, toujours sous mutex (ex. regen_batch_locks_md)."""
    with LocksMutex():
        locks = load_locks()
        now_dt = datetime.datetime.now()
        purge_stale_locks(locks, now_dt)
        other_session = _slug_session_map(locks).get(slug)
        if other_session and other_session != session_id:
            since = locks.get("sessions", {}).get(other_session, {}).get("since", "?")
            sys.stderr.write(
                f"Verrou live — `{slug}` est deja repris par une autre session "
                f"(depuis {since}). Attendre la fin de cette session avant de {action_verb} la meme tache "
                "(ou choisir une autre tache).\n"
            )
            sys.exit(2)
        if extra_check is not None:
            reason = extra_check(locks)
            if reason:
                sys.stderr.write(reason + "\n")
                sys.exit(2)
        _register_task_lock(slug, session_id, locks, now_dt, sections)
        save_locks(locks)
        if on_success is not None:
            on_success(locks)


def _claim_resume_lock(slug, session_id):
    """Reclame (ou rafraichit) le verrou live pour une tache DEJA presente en
    CURRENT_TASKS qu'une session reprend (`/crew-start` Cas A). Ferme le trou
    du mecanisme historique : le verrou n'etait pose qu'au moment du `git mv`
    TODO->CURRENT_TASKS (cf. `_extract_git_mv_task`/`started` dans `main()`),
    donc deux sessions qui reprenaient independamment la MEME tache deja
    presente en CURRENT_TASKS (aucun `git mv`, donc aucun `started`) ne
    declenchaient jamais aucune verification — ni verrou, ni collision.
    Preventif (avant que la session commence a editer la tache), pas
    retroactif comme le controle Stop. Cf. `_claim_lock` pour le detail."""
    _claim_lock(slug, session_id, "reprendre")


def _claim_git_mv_lock(slug, session_id, sections):
    """Enregistre le verrou live pour une tache demarree via `git mv`
    TODO->CURRENT_TASKS (gate_pretooluse), AVANT que le mv ne s'execute reellement
    — ferme le trou worktree (le hook Stop est ROOT-anchored, il ne voit jamais
    un `git mv` fait depuis `../<repo>-batch-<slug>/`, cf. tache
    fix-worktree-gitmv-lock-registration-gap). Ajoute a `_claim_lock` la
    verification des voisines de batch (`check_batch_collisions`, fraiche sous
    mutex — ferme le TOCTOU avec la lecture `locks` deja faite plus haut dans
    gate_pretooluse pour le scan generique de la meme invocation) et la
    regeneration de BATCH_LOCKS.md : sinon la doc humaine resterait en retard
    sur crew_lock.json jusqu'au prochain tour Stop. `active` calcule HORS
    mutex (I/O disque sans rapport avec crew_lock.json, meme raisonnement que
    dans `main()`)."""
    active = active_task_slugs()
    _claim_lock(
        slug, session_id, "demarrer", sections=sections,
        extra_check=lambda locks: check_batch_collisions({slug}, sections, locks, session_id),
        on_success=lambda locks: regen_batch_locks_md(sections, locks, active),
    )


def _locked_zones_by_others(sections, locks, session_id):
    """Retourne [(zone_path, section_header, other_session_id, since), ...]
    pour chaque `Zone:` d'un batch ACTIF (>=1 tache verrouillee) par une
    session != session_id — la liste que le gate hardened doit bloquer."""
    out = []
    sessions = locks.get("sessions", {})
    slug_sessions = _slug_session_map(locks)
    for section in sections:
        others = sorted(_section_lock_sessions(section, locks, slug_sessions) - {session_id})
        if not others:
            continue
        other = others[0]
        since = sessions.get(other, {}).get("since", "?")
        for zp in section["zone_paths"]:
            out.append((zp, section["header"], other, since))
    return out


def _repo_relative_path(path, locks=None):
    """Normalise `path` (absolu ou relatif, separateurs Windows ou POSIX) en
    chemin relatif POSIX au depot logique, pour comparaison avec les `Zone:`
    de CLAUDE_BATCH.md (toujours exprimees relatives a la racine du depot).
    `Edit`/`Write`/`MultiEdit` fournissent toujours un `file_path` ABSOLU :
    sans cette normalisation la comparaison directe avec une Zone: relative
    ne matche jamais (bug releve en code review de worktree-batch-isolation).
    Un chemin sous le worktree d'un batch connu (crew_lock.json) est ramene
    au meme chemin relatif logique que sous ROOT, puisqu'un `git worktree`
    mirrore la structure du depot principal. Fail-open sur echec de
    resolution (retombe sur un simple nettoyage de separateurs)."""
    try:
        p = pathlib.Path(str(path))
    except Exception:
        return str(path).replace("\\", "/").lstrip("./")
    if not p.is_absolute():
        return str(p).replace("\\", "/").lstrip("./")
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        pass
    locks = locks if locks is not None else load_locks()
    for info in locks.get("sessions", {}).values():
        wt = info.get("worktree")
        if not wt:
            continue
        try:
            wt_root = (ROOT / wt).resolve()
            return p.resolve().relative_to(wt_root).as_posix()
        except Exception:
            continue
    return str(p).replace("\\", "/").lstrip("./")


def _path_matches_zone(norm, zdir):
    """`norm` (chemin relatif POSIX, cf. _repo_relative_path) tombe-t-il sous
    la zone `zdir` (un membre deja expanse par _expand_brace_glob) ? Gere le
    cas prefixe simple (`crew/`) ET le cas glob `*` (ex. `.claude/skills/
    crew-*`, utilise tel quel par ce depot dans CLAUDE_BATCH.md) via fnmatch
    — best-effort, pas un moteur de glob complet."""
    zdir = zdir.rstrip("/")
    if any(ch in zdir for ch in "*?["):
        return fnmatch.fnmatchcase(norm, zdir) or fnmatch.fnmatchcase(norm, zdir + "/*")
    return norm == zdir or norm.startswith(zdir + "/")


def _path_locked_by_other(path, zones, locks=None):
    """`path` (chemin brut, absolu ou relatif, Windows ou POSIX) tombe-t-il
    sous l'une des zones de `zones` (sortie de _locked_zones_by_others) ?
    Renvoie (header, other_session, since) si oui, sinon None."""
    norm = _repo_relative_path(path, locks)
    for zp, header, other, since in zones:
        for expanded in _expand_brace_glob(zp):
            if _path_matches_zone(norm, expanded):
                return header, other, since
    return None


def _gate_check_path(path, session_id, locks=None, sections=None):
    """Bloque (exit 2) si `path` tombe sous une `Zone:` de batch verrouillee
    par une AUTRE session. Fail-open (retourne silencieusement) si aucune
    zone active n'est verrouillee par quelqu'un d'autre, ou si le chemin n'en
    croise aucune — coherent avec le contrat 'ne casse jamais le tour sur
    ambiguite' du reste du hook (Layer 2 = filet, pas la seule defense).
    `locks`/`sections` optionnels : un appelant qui scanne plusieurs chemins
    dans la meme invocation (ex. `gate_pretooluse` sur une commande Bash a
    plusieurs candidats) les charge une seule fois et les passe ici plutot
    que de relire/re-parser crew_lock.json/CLAUDE_BATCH.md a chaque chemin."""
    if not path:
        return
    locks = locks if locks is not None else load_locks()
    sections = sections if sections is not None else load_sections()
    zones = _locked_zones_by_others(sections, locks, session_id)
    if not zones:
        return
    hit = _path_locked_by_other(path, zones, locks)
    if not hit:
        return
    header, other, since = hit
    sys.stderr.write(
        f"[worktree-gate] `{path}` est sous la Zone: du batch « {header} », deja "
        f"verrouillee par une autre session (depuis {since}). Collision potentielle — "
        "travaille depuis le worktree de ton propre batch (cf. /crew-start), ou attends "
        "la fin de l'autre session.\n"
    )
    sys.exit(2)


def _extract_candidate_paths(command):
    """Scan best-effort (pas un parseur shell complet, meme esprit que
    `_extract_git_mv_task`) : repere les tokens qui ressemblent a un chemin de
    fichier apres `rm`/`mv`/`cp`, plus toute cible de redirection `>`/`>>`,
    dans une commande Bash potentiellement composee. Fail-open sur le reste —
    Layer 2 est un filet, pas la seule ligne de defense (cf. spec § Error
    handling > 'Gate false positive')."""
    norm = _tokenize_command(command)
    paths = []
    mutating = {"rm", "mv", "cp"}
    for i, tok in enumerate(norm):
        if tok.rsplit("/", 1)[-1] not in mutating:
            continue
        for arg in norm[i + 1:]:
            if arg.startswith("-"):
                continue
            if "/" in arg or "." in arg:
                paths.append(arg)
    for m in re.finditer(r">>?\s*([^\s|&;><]+)", command):
        paths.append(m.group(1).replace("\\", "/"))
    return paths


def gate_pretooluse(payload):
    """Hook PreToolUse (matcher Bash|Edit|Write|MultiEdit) : Layer 2 du design
    worktree-batch-isolation (cf. docs/superpowers/specs/2026-08-22-worktree-
    batch-isolation-design.md) — filet de securite pour tout ce qui contourne
    l'isolation physique par worktree (Layer 1, portee par /crew-start).

    - `Edit`/`Write`/`MultiEdit` : bloque avant ecriture si `tool_input.file_path`
      tombe sous une `Zone:` verrouillee par une AUTRE session (`_gate_check_path`).
    - `Bash` :
        1. marqueur de reprise `crew-resume:<slug>` (Cas A de `/crew-start`,
           cf. `_claim_resume_lock`) ;
        2. `git mv` TODO->CURRENT_TASKS : bloque si la tache n'est categorisee
           dans aucun batch, ou si une voisine de son batch est deja
           verrouillee par une AUTRE session (meme regle que
           check_batch_collisions au Stop) ;
        3. scan generique best-effort (`_extract_candidate_paths`) contre les
           memes zones verrouillees, pour `rm`/`mv`/`cp`/redirection.

    Preventif plutot que retroactif : contrairement au controle Stop (qui se
    declenche apres que les edits du tour ont deja eu lieu), celui-ci empeche
    l'action de s'executer. Bloque via exit(2) + stderr (protocole hook
    standard). Les chemins `crew-resume:` ET `git mv` TODO->CURRENT_TASKS
    ecrivent tous deux dans `crew_lock.json` (sous mutex, cf. `_claim_resume_lock`/
    `_claim_git_mv_lock`) — necessaire pour le `git mv` car depuis un worktree de
    batch le hook Stop (ROOT-anchored) ne voit jamais ce deplacement (cf. tache
    fix-worktree-gitmv-lock-registration-gap) ; seul le scan generique
    (`rm`/`mv`/`cp`/redirection) reste lecture seule."""
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    session_id = payload.get("session_id")

    if tool_name in ("Edit", "Write", "MultiEdit"):
        _gate_check_path(tool_input.get("file_path"), session_id)
        return

    if tool_name != "Bash":
        return

    command = str(tool_input.get("command") or "")

    resume_slug = _extract_resume_claim(command)
    if resume_slug is not None:
        _claim_resume_lock(resume_slug, session_id)
        return

    # Charges une seule fois pour tout le reste de la commande (git mv +
    # scan generique ci-dessous) plutot que relus/re-parses par candidat —
    # une commande composee peut produire plusieurs chemins a verifier.
    sections = load_sections()
    locks = load_locks()

    slug = _extract_git_mv_task(command)
    if slug:
        section = find_section_for(slug, sections)
        if section is None:
            sys.stderr.write(
                f"[batch] `{slug}` n'est categorisee dans aucun batch de CLAUDE_BATCH.md. "
                "Ajoute-la a un batch (avec sa Zone :) avant de la demarrer — voir CLAUDE.md § Batching, "
                "ou dispatch le persona manager (/crew-start) qui le fait pour toi.\n"
            )
            sys.exit(2)
        reason = check_batch_collisions({slug}, sections, locks, session_id)
        if reason:
            sys.stderr.write(reason + "\n")
            sys.exit(2)
        if session_id:
            _claim_git_mv_lock(slug, session_id, sections)

    for p in _extract_candidate_paths(command):
        _gate_check_path(p, session_id, locks, sections)


def active_task_slugs():
    """Slugs (fichiers .md) actuellement en crew/TODO/ ou crew/CURRENT_TASKS/."""
    active = set()
    for d in (DIRS["TODO"], DIRS["CURRENT_TASKS"]):
        if d.exists():
            active |= {f.name for f in d.glob("*.md")
                       if f.name not in ("INDEX.md", "README.md") and not f.name.startswith("_")}
    return active


def _expand_brace_glob(path):
    """Expanse tous les segments `{a,b,c}` d'un chemin en chemins concrets
    (produit cartesien des membres). Sans brace-glob, retourne [path] inchange."""
    m = re.search(r"\{([^{}]+)\}", path)
    if not m:
        return [path]
    expanded = [path[:m.start()] + member + path[m.end():] for member in m.group(1).split(",")]
    return [p for e in expanded for p in _expand_brace_glob(e)]


def _path_overlaps(a, b):
    """Deux chemins se chevauchent si l'un est prefixe (par segment) de l'autre,
    apres expansion des brace-globs (`{a,b,c}/`) de chaque cote en chemins concrets."""
    for pa in _expand_brace_glob(a):
        sa = pa.rstrip("/").split("/")
        for pb in _expand_brace_glob(b):
            sb = pb.rstrip("/").split("/")
            n = min(len(sa), len(sb))
            if sa[:n] == sb[:n]:
                return True
    return False


def _section_lock_sessions(section, locks, slug_sessions=None):
    """Sessions ayant actuellement un verrou live sur au moins une tache de la
    section (derive de sessions[*].tasks via _slug_session_map, alimente par
    la boucle `for f in started` de main()). `slug_sessions` optionnel : un
    appelant qui boucle sur plusieurs sections (check_zone_overlaps,
    _locked_zones_by_others) le calcule une fois et le passe ici plutot que
    de reconstruire la map complete a chaque section."""
    slug_sessions = slug_sessions if slug_sessions is not None else _slug_session_map(locks)
    return {slug_sessions[s] for s in section["slugs"] if s in slug_sessions}


def check_zone_overlaps(sections, active, locks):
    """Detecte les chevauchements de `Zone :` entre deux batchs ACTIFS (>=1 tache
    en TODO/CURRENT_TASKS). Devient bloquant (liste `blocking`) uniquement quand
    les deux batchs en collision sont verrouilles par des session_id
    differentes — memes regles que check_batch_collisions, pour ne PAS bloquer
    une session solo qui travaille sequentiellement sur deux batchs a zones
    voisines (aucun des deux n'est alors verrouille par une AUTRE session).
    Sinon reste un avertissement non bloquant : garde-fou automatise
    complementaire a la verification manuelle du manager avant de demarrer."""
    warnings = []
    blocking = []
    slug_sessions = _slug_session_map(locks)
    active_sections = [s for s in sections if s["slugs"] & active and s["zone_paths"]]
    for i, sec_a in enumerate(active_sections):
        sessions_a = _section_lock_sessions(sec_a, locks, slug_sessions)
        for sec_b in active_sections[i + 1:]:
            sessions_b = _section_lock_sessions(sec_b, locks, slug_sessions)
            cross_session = bool(sessions_a) and bool(sessions_b) and sessions_a != sessions_b
            for pa in sec_a["zone_paths"]:
                for pb in sec_b["zone_paths"]:
                    if not _path_overlaps(pa, pb):
                        continue
                    base = (f"[zone] Chevauchement detecte entre batchs actifs « {sec_a['header']} » "
                            f"et « {sec_b['header']} » : `{pa}` vs `{pb}`.")
                    if cross_session:
                        blocking.append(base + " Verrouilles par des sessions differentes — "
                                         "attendre la fin de l'une avant de continuer l'autre.")
                    else:
                        warnings.append(base + " Verifier CLAUDE_BATCH.md avant de demarrer une "
                                         "tache de l'un ou l'autre (risque de collision fichiers).")
    return warnings, blocking


def regen_batch_locks_md(sections, locks, active):
    """Regenere crew/CLAUDE_CONTEXT/BATCH_LOCKS.md : une entree par section de
    batch ayant au moins une tache actuellement en TODO/ ou CURRENT_TASKS/.
    Colonne `worktree` affichee quand l'entree session en porte une."""
    lines = ["# Verrous batch (temps reel)\n\n",
              "> Regenere automatiquement par `crew/crew_hook.py` a chaque tour. "
              "Ne pas editer a la main.\n\n"]
    slug_sessions = _slug_session_map(locks)
    sessions = locks.get("sessions", {})
    any_section = False
    for section in sections:
        relevant = sorted(section["slugs"] & active)
        if not relevant:
            continue
        any_section = True
        lines.append(f"## {section['header']}\n\n")
        for slug in relevant:
            sid = slug_sessions.get(slug)
            if sid:
                info = sessions.get(sid, {})
                try:
                    since_fmt = datetime.datetime.fromisoformat(info.get("since", "")).strftime("%H:%M")
                except Exception:
                    since_fmt = info.get("since", "?")
                worktree = info.get("worktree")
                suffix = f", worktree `{worktree}`" if worktree else ""
                lines.append(f"- 🔒 `{slug}` — verrouille (session `{sid}`, depuis {since_fmt}{suffix})\n")
            else:
                lines.append(f"- 🔓 `{slug}` — libre\n")
        lines.append("\n")
    if not any_section:
        lines.append("_Aucun batch actif avec tache en TODO/CURRENT_TASKS pour le moment._\n")
    BATCH_LOCKS_MD.write_text("".join(lines), encoding="utf-8")


def _git_tracked(rel):
    r = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel],
                        cwd=str(ROOT), capture_output=True, text=True)
    return r.returncode == 0


def _git_ignored(rel):
    r = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=str(ROOT))
    return r.returncode == 0


def _closure_commit_scope(slug):
    """Chemins crew/ (relatifs a ROOT, POSIX) a inclure dans le commit auto
    de cloture pour `slug` (sans extension `.md`) : le fichier CURRENT_TASKS
    disparu, HISTORIQUE.md, les tests sortis (IA/DEV, s'ils existent), et
    tous les INDEX.md + CLAUDE_BATCH.md + BATCH_LOCKS.md + CHANGELOG_TACHES.md
    regeneres par le hook dans la meme passe. Ne renvoie que des chemins que
    `git add` acceptera reellement :
    - deja suivi par git -> inclus systematiquement (couvre une suppression
      a stager, meme si le fichier n'existe plus sur disque) ;
    - jamais suivi mais absent -> exclu (un `git add` dessus echouerait avec
      'did not match any files') ;
    - jamais suivi, present sur disque, mais gitignore (ex.
      `crew/CLAUDE_CONTEXT/BATCH_LOCKS.md`, regenere a chaque tour mais
      jamais destine a etre commite — un `git add` explicite dessus est
      refuse par git) -> exclu."""
    candidates = [
        DIRS["CURRENT_TASKS"] / f"{slug}.md",
        CTX / "HISTORIQUE.md",
        DIRS["TESTS/IA"] / f"{slug}.md",
        DIRS["TESTS/DEV"] / f"{slug}.md",
        BATCH_FILE,
        CHANGELOG,
        BATCH_LOCKS_MD,
    ]
    for d in DIRS.values():
        candidates.append(d / "INDEX.md")
    paths = []
    for p in candidates:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if _git_tracked(rel):
            paths.append(rel)
            continue
        if not p.exists():
            continue
        if _git_ignored(rel):
            continue
        paths.append(rel)
    return sorted(set(paths))


def auto_commit_closure(finished, now_dt):
    """Commit git LOCAL UNIQUEMENT (jamais de push) scope a crew/, declenche
    par slug reellement cloture : un slug de `finished` (disparu de
    CURRENT_TASKS/ ce tour) n'est retenu QUE s'il a une entree correspondante
    dans le diff (non commit) de HISTORIQUE.md — pas juste "le fichier a
    bouge quelque part" (couvre le cas ou 2 taches finissent le meme tour
    mais une seule a une vraie entree, et le cas ou `finished` est non vide
    sans historisation reelle, ex. suppression manuelle du fichier).
    Idempotent par construction : rien de NOUVEAU sur le scope calcule ->
    aucun commit (verifie via `git diff --cached` restreint au scope, pas
    l'index entier). Commit SCOPE au
    pathspec (`git commit -- <paths>`) plutot qu'un `git commit` nu : ne
    touche jamais un changement de l'utilisateur deja stage ailleurs dans le
    depot au moment du hook, meme si `git add` l'a laisse dans l'index avant
    ce commit-ci — c'est exactement l'incident (ProjetA) que cette tache
    corrige. Ne casse jamais le tour : toute erreur (git absent, hook
    pre-commit qui rejette, etc.) est loggee sur stderr et avalee, jamais
    levee — meme contrat que le reste du hook."""
    if not finished:
        return
    paths = []
    try:
        histo_rel = str((CTX / "HISTORIQUE.md").relative_to(ROOT)).replace("\\", "/")
        diff_text = (
            subprocess.run(["git", "diff", "--", histo_rel], cwd=str(ROOT),
                            capture_output=True, text=True).stdout
            + subprocess.run(["git", "diff", "--cached", "--", histo_rel], cwd=str(ROOT),
                              capture_output=True, text=True).stdout
        )
        all_slugs = sorted(f[:-3] if f.endswith(".md") else f for f in finished)
        # Ne retient que les slugs ayant reellement une entree correspondante
        # dans le diff HISTORIQUE.md (pas juste "le fichier a bouge quelque
        # part") : si 2 taches finissent le meme tour et qu'une seule a une
        # vraie entree, l'autre n'est pas incluse dans ce commit.
        slugs = [s for s in all_slugs if s in diff_text]
        if not slugs:
            return  # aucun slug fini n'a d'entree correspondante dans HISTORIQUE.md
        paths = sorted({p for slug in slugs for p in _closure_commit_scope(slug)})
        if not paths:
            return
        subprocess.run(["git", "add", "--"] + paths, cwd=str(ROOT), check=True,
                        capture_output=True, text=True)
        if subprocess.run(["git", "diff", "--cached", "--quiet", "--"] + paths,
                           cwd=str(ROOT)).returncode == 0:
            return  # rien de reellement nouveau sur CE scope -> deja commit (idempotence)
        msg = "chore(crew): cloture tache " + ", ".join(slugs)
        subprocess.run(["git", "commit", "-m", msg, "--"] + paths, cwd=str(ROOT),
                        check=True, capture_output=True, text=True)
    except Exception as e:
        sys.stderr.write(f"[auto-commit] commit de cloture non effectue (non bloquant) : {e}\n")
        # Best-effort : si `git add` a partiellement reussi avant l'echec
        # (ex. un chemin du scope invalide plus loin dans la liste), ne pas
        # laisser ces chemins staged pour l'utilisateur — desstage uniquement
        # NOTRE scope, jamais le reste de l'index (memes garanties que le
        # commit lui-meme).
        if paths:
            try:
                subprocess.run(["git", "reset", "--"] + paths, cwd=str(ROOT), capture_output=True)
            except Exception:
                pass


def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}
    session_id = payload.get("session_id")
    hook_event = payload.get("hook_event_name")

    if hook_event == "PreToolUse":
        # Garde preventive uniquement (git mv TODO->CURRENT_TASKS) : pas de sync
        # d'index/journal/verrous ici, ça reste le travail du hook Stop.
        gate_pretooluse(payload)
        return

    rotate_graphify_snapshots()
    now_dt = datetime.datetime.now()

    state = {name: regen_index(name, d) for name, d in DIRS.items()}

    prev = {}
    if SNAP.exists():
        try:
            prev = json.loads(SNAP.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    cur_c, prev_c = set(state["CURRENT_TASKS"]), set(prev.get("CURRENT_TASKS", []))
    cur_t, prev_t = set(state["TODO"]), set(prev.get("TODO", []))
    started = cur_c - prev_c
    finished = prev_c - cur_c
    added = (cur_t - prev_t) - started

    now = now_dt.date().isoformat()
    entries = []
    for f in sorted(started):
        entries.append(f"- {now} ▶️ **démarrée** : `{f}`")
    for f in sorted(finished):
        entries.append(f"- {now} ✅ **terminée** : `{f}`")
    for f in sorted(added):
        entries.append(f"- {now} ➕ **ajoutée au backlog** : `{f}`")

    if finished:  # rappel non bloquant tracé au changelog
        entries.append(f"  ↳ ⚠️ vérifier : entrée dans `HISTORIQUE.md` + checklist `crew/TESTS/<chantier>.md` "
                       "pour " + ", ".join(sorted(finished)))

    completed_tests = process_completed_tests()
    for f in sorted(completed_tests):
        entries.append(f"- {now} 🧪 **tests validés** : `{f}` (déplacé vers `TESTS_DONE/`)")
        # Forcer la regénération de l'index IA puisqu'on a déplacé un fichier
        state["TESTS/IA"] = regen_index("TESTS/IA", DIRS["TESTS/IA"])

    # Verrous live par batch (anti-collision multi-Claude). Seule la section
    # read-modify-write de crew_lock.json (load -> mutate -> save) est
    # protégée par le mutex fichier (LocksMutex), pour éviter qu'une écriture
    # concurrente (deux sessions qui finissent leur tour à la même seconde)
    # n'en écrase une autre en silence, sans retenir le mutex plus longtemps
    # que nécessaire (check_zone_overlaps est du calcul pur, pas de la
    # section critique — il tourne après la libération, sur `locks` déjà à jour).
    sections = load_sections()
    active = active_task_slugs()
    collision_reason = None

    with LocksMutex():
        locks = load_locks()
        for sid in purge_stale_locks(locks, now_dt):
            entries.append(f"- {now} ⚠️ **verrou expiré (>6h) purgé (session `{sid}`)**")

        # Tache finie : sort des `tasks` de TOUTES les sessions qui la tenaient
        # (normalement une seule). L'entree session elle-meme n'est PAS purgee
        # ici meme si elle se retrouve sans aucune tache — elle peut enchainer
        # sur une autre tache du meme batch/worktree ; seule purge_stale_locks
        # (TTL) ou /crew-close-task retire une entree session entiere.
        if finished:
            for info in locks.get("sessions", {}).values():
                info["tasks"] = [t for t in info.get("tasks", []) if t not in finished]

        if hook_event == "SessionEnd":
            if session_id:
                locks.get("sessions", {}).pop(session_id, None)
        else:
            if session_id:
                # Fallback conserve deliberement (pas redondant) : couvre le
                # `git mv` fait directement dans le checkout principal SANS passer
                # par gate_pretooluse (ex. hook PreToolUse desactive/bypass, ou
                # mutex non acquis en best-effort). Pour le flux worktree normal,
                # `_claim_git_mv_lock` a deja enregistre le verrou en amont —
                # `_register_task_lock` est idempotent (slug pas duplique, batch/
                # worktree/branch deja poses pas ecrases), donc ce replay ne fait
                # que rafraichir `since` sans effet de bord problematique.
                for f in started:
                    _register_task_lock(f, session_id, locks, now_dt, sections)
                # Rafraichit aussi le verrou deja detenu par CETTE session si elle
                # a encore des taches actives (Cas A resume via _claim_resume_lock,
                # ou simplement une session longue) : sans ca, purge_stale_locks
                # finirait par liberer le verrou d'une session encore au travail.
                info = locks.get("sessions", {}).get(session_id)
                if info and any(f in cur_c for f in info.get("tasks", [])):
                    info["since"] = now_dt.isoformat()
            collision_reason = check_batch_collisions(started, sections, locks, session_id)

        save_locks(locks)
        regen_batch_locks_md(sections, locks, active)

    zone_warnings, zone_blocking = check_zone_overlaps(sections, active, locks)

    if entries and prev:  # ne pas journaliser le premier snapshot de référence
        head = ""
        if not CHANGELOG.exists():
            head = ("# Changelog des tâches\n\n"
                    "> Alimenté automatiquement par le hook Stop (`crew/crew_hook.py`).\n\n")
        with CHANGELOG.open("a", encoding="utf-8") as fh:
            fh.write(head + "\n".join(entries) + "\n")

    auto_commit_closure(finished, now_dt)

    SNAP.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    # Batching : avertissements non bloquants (stderr) — n'interfère pas avec le
    # JSON de décision émis sur stdout.
    for w in check_batches():
        sys.stderr.write(w + "\n")
    for w in zone_warnings:
        sys.stderr.write(w + "\n")

    # Invariants bloquants (combinés en une seule décision si plusieurs se déclenchent)
    reasons = []

    dup = {f[:-3] for f in cur_t} & {f[:-3] for f in cur_c}
    if dup:
        reasons.append("Incohérence cycle de vie : tâche(s) présente(s) à la fois dans "
                        "crew/TODO/ et crew/CURRENT_TASKS/ : " + ", ".join(sorted(dup)) +
                        ". Retire-les de crew/TODO/ (une tâche commencée ne reste pas dans le backlog).")

    if collision_reason:
        reasons.append(collision_reason)

    if zone_blocking:
        reasons.append("Verrou live zone — chevauchement entre batchs actifs verrouillés par des "
                        "sessions différentes : " + " ; ".join(zone_blocking) +
                        " Attendre la fin de l'autre session avant de continuer.")

    if reasons:
        print(json.dumps({"decision": "block", "reason": "\n\n".join(reasons)}))
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
