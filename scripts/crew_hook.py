# -*- coding: utf-8 -*-
"""Hook Stop/SessionEnd/PreToolUse — gestion des tâches du projet.
À chaque fin de tour (Stop) :
  1. régénère crew/<dir>/INDEX.md (titres + liens),
  2. journalise les transitions (démarrée / terminée / ajoutée) dans
     crew/CLAUDE_CONTEXT/CHANGELOG_TACHES.md,
  3. bloque la fin de tour si une tâche est à la fois dans TODO/ et CURRENT_TASKS/,
  4. rappelle d'historiser + sortir les tests quand une tâche vient d'être terminée,
  5. maintient des verrous live par batch (anti-collision multi-Claude, écriture
     protégée par LocksMutex) et bloque le tour si une tâche démarrée a une
     voisine de batch déjà verrouillée par une autre session, ou si deux batchs
     actifs à zones chevauchantes sont verrouillés par des sessions différentes
     (cf. crew/CLAUDE_CONTEXT/BATCH_LOCKS.md, régénéré à chaque tour).
En PreToolUse (matcher Bash, cf. gate_pretooluse) : contrôle préventif avant
exécution d'un `git mv` TODO->CURRENT_TASKS (tâche catégorisée + pas de
collision), en complément — pas en remplacement — du contrôle Stop rétroactif.
Ne casse jamais le tour : toute erreur interne -> exit 0 silencieux (sauf le
blocage volontaire exit(2) de gate_pretooluse).
"""
import json, os, re, sys, shlex, time, datetime, pathlib, shutil

ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parent.parent)  # racine du projet cible
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
LOCKS_FILE = CTX / ".batch_locks.json"
LOCKS_MUTEX = CTX / ".batch_locks.mutex"
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
    section critique read-modify-write de .batch_locks.json. Implemente via
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
    if LOCKS_FILE.exists():
        try:
            return json.loads(LOCKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_locks(locks):
    """Ecriture atomique (temp file + os.replace) : evite un .batch_locks.json
    tronque si le process est tue en cours d'ecriture."""
    tmp = LOCKS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(locks, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(LOCKS_FILE))


def purge_stale_locks(locks, now_dt):
    """Retire les verrous plus vieux que LOCK_TTL (session probablement crashee).
    Retourne la liste triee des slugs purges."""
    stale = []
    for slug, info in list(locks.items()):
        since_raw = info.get("since") if isinstance(info, dict) else None
        try:
            since = datetime.datetime.fromisoformat(since_raw)
            expired = now_dt - since > LOCK_TTL
        except Exception:
            expired = True  # entree corrompue -> on la degage aussi
        if expired:
            stale.append(slug)
            del locks[slug]
    return sorted(stale)


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
    reasons = []
    for f in sorted(started):
        section = find_section_for(f, sections)
        if not section:
            continue
        for neighbor in sorted(section["slugs"] - {f}):
            info = locks.get(neighbor)
            if not info:
                continue
            other_session = info.get("session_id")
            if other_session and other_session != session_id:
                since = info.get("since", "?")
                reasons.append(
                    f"batch « {section['header']} » : `{f}` demarre alors que `{neighbor}` "
                    f"est deja verrouille par une autre session (depuis {since})"
                )
    if not reasons:
        return None
    return ("Verrou live batch — collision detectee : " + " ; ".join(reasons) +
            ". Attendre la fin de l'autre session ou choisir une tache d'un autre batch.")


def _extract_git_mv_task(command):
    """Si `command` (une commande Bash, potentiellement composee : `a; b && c`)
    contient un `git mv` deplacant un fichier depuis crew/TODO/ vers
    crew/CURRENT_TASKS/, retourne son slug (nom de fichier). Sinon None.
    Best-effort : ne parse pas un shell complexe, couvre seulement le cas
    documente `git mv crew/TODO/x.md crew/CURRENT_TASKS/x.md` (avec eventuels
    flags avant les deux chemins). Essaie TOUTES les occurrences de `mv` dans
    la commande (pas seulement la premiere) : une commande composee peut avoir
    un `mv` sans rapport avant le vrai `git mv` a surveiller. `posix=True` est
    fige (pas `sys.platform`-dependant) : le tool Bash execute toujours du
    shell POSIX (Git Bash), quel que soit l'OS hote — sinon les guillemets
    autour d'un chemin restent dans le token sur Windows et le slug echoue
    silencieusement le test `.endswith(".md")`."""
    todo_name, current_name = DIRS["TODO"].name, DIRS["CURRENT_TASKS"].name
    if "mv" not in command or todo_name not in command or current_name not in command:
        return None
    try:
        tokens = shlex.split(command, posix=True)
    except Exception:
        tokens = command.split()
    norm = [t.replace("\\", "/") for t in tokens]
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


def _claim_resume_lock(slug, session_id):
    """Reclame (ou rafraichit) le verrou live pour une tache DEJA presente en
    CURRENT_TASKS qu'une session reprend (`/crew-start` Cas A). Ferme le trou
    du mecanisme historique : le verrou n'etait pose qu'au moment du `git mv`
    TODO->CURRENT_TASKS (cf. `_extract_git_mv_task`/`started` dans `main()`),
    donc deux sessions qui reprenaient independamment la MEME tache deja
    presente en CURRENT_TASKS (aucun `git mv`, donc aucun `started`) ne
    declenchaient jamais aucune verification — ni verrou, ni collision. Bloque
    (exit 2) si un AUTRE session_id detient deja le verrou ; sinon le
    pose/rafraichit pour cette session. Preventif (avant que la session
    commence a editer la tache), pas retroactif comme le controle Stop."""
    with LocksMutex():
        locks = load_locks()
        purge_stale_locks(locks, datetime.datetime.now())
        info = locks.get(slug)
        other_session = info.get("session_id") if info else None
        if other_session and other_session != session_id:
            since = info.get("since", "?")
            sys.stderr.write(
                f"Verrou live — `{slug}` est deja repris par une autre session "
                f"(depuis {since}). Attendre la fin de cette session avant de reprendre la meme tache "
                "(ou choisir une autre tache).\n"
            )
            sys.exit(2)
        locks[slug] = {"session_id": session_id, "since": datetime.datetime.now().isoformat()}
        save_locks(locks)


def gate_pretooluse(payload):
    """Hook PreToolUse (matcher Bash) : bloque *avant* execution un `git mv`
    TODO->CURRENT_TASKS si la tache n'est categorisee dans aucun batch de
    CLAUDE_BATCH.md, ou si une voisine de son batch est deja verrouillee par
    une AUTRE session (meme regle que check_batch_collisions au Stop). Gere
    aussi le marqueur de reprise `crew-resume:<slug>` (cf. `_claim_resume_lock`)
    pour le Cas A de `/crew-start` (tache deja en CURRENT_TASKS, pas de `git mv`
    a intercepter). Preventif plutot que retroactif : contrairement au controle
    Stop (qui se declenche apres que les edits du tour ont deja eu lieu),
    celui-ci empeche l'action de s'executer. Bloque via exit(2) + stderr
    (protocole hook standard). Seul le chemin `crew-resume:` ecrit dans
    `.batch_locks.json` (sous mutex) ; le chemin `git mv` n'ecrit rien — la
    mise a jour de ses verrous reste au Stop."""
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or "")
    session_id = payload.get("session_id")

    resume_slug = _extract_resume_claim(command)
    if resume_slug is not None:
        _claim_resume_lock(resume_slug, session_id)
        return

    slug = _extract_git_mv_task(command)
    if not slug:
        return
    sections = load_sections()
    section = find_section_for(slug, sections)
    if section is None:
        sys.stderr.write(
            f"[batch] `{slug}` n'est categorisee dans aucun batch de CLAUDE_BATCH.md. "
            "Ajoute-la a un batch (avec sa Zone :) avant de la demarrer — voir CLAUDE.md § Batching, "
            "ou dispatch le persona manager (/crew-start) qui le fait pour toi.\n"
        )
        sys.exit(2)
    locks = load_locks()
    reason = check_batch_collisions({slug}, sections, locks, session_id)
    if reason:
        sys.stderr.write(reason + "\n")
        sys.exit(2)


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


def _section_lock_sessions(section, locks):
    """Sessions ayant actuellement un verrou live sur au moins une tache de la
    section (cf. locks, alimente par le boucle `for f in started` de main())."""
    return {locks[s]["session_id"] for s in section["slugs"]
            if s in locks and locks[s].get("session_id")}


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
    active_sections = [s for s in sections if s["slugs"] & active and s["zone_paths"]]
    for i, sec_a in enumerate(active_sections):
        sessions_a = _section_lock_sessions(sec_a, locks)
        for sec_b in active_sections[i + 1:]:
            sessions_b = _section_lock_sessions(sec_b, locks)
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
    batch ayant au moins une tache actuellement en TODO/ ou CURRENT_TASKS/."""
    lines = ["# Verrous batch (temps reel)\n\n",
              "> Regenere automatiquement par `crew/crew_hook.py` a chaque tour. "
              "Ne pas editer a la main.\n\n"]
    any_section = False
    for section in sections:
        relevant = sorted(section["slugs"] & active)
        if not relevant:
            continue
        any_section = True
        lines.append(f"## {section['header']}\n\n")
        for slug in relevant:
            info = locks.get(slug)
            if info:
                try:
                    since_fmt = datetime.datetime.fromisoformat(info.get("since", "")).strftime("%H:%M")
                except Exception:
                    since_fmt = info.get("since", "?")
                lines.append(f"- 🔒 `{slug}` — verrouille (session `{info.get('session_id')}`, depuis {since_fmt})\n")
            else:
                lines.append(f"- 🔓 `{slug}` — libre\n")
        lines.append("\n")
    if not any_section:
        lines.append("_Aucun batch actif avec tache en TODO/CURRENT_TASKS pour le moment._\n")
    BATCH_LOCKS_MD.write_text("".join(lines), encoding="utf-8")


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
    # read-modify-write de .batch_locks.json (load -> mutate -> save) est
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
        for slug in purge_stale_locks(locks, now_dt):
            entries.append(f"- {now} ⚠️ **verrou expiré (>6h) purgé** : `{slug}`")

        for f in finished:
            locks.pop(f, None)

        if hook_event == "SessionEnd":
            if session_id:
                for slug in [s for s, info in locks.items() if info.get("session_id") == session_id]:
                    del locks[slug]
        else:
            for f in started:
                locks[f] = {"session_id": session_id, "since": now_dt.isoformat()}
            # Rafraichit aussi les verrous deja detenus par CETTE session sur des
            # taches encore actives (Cas A resume via _claim_resume_lock, ou
            # simplement une session longue) : sans ca, purge_stale_locks finirait
            # par liberer le verrou d'une session encore en train de travailler.
            if session_id:
                for f in cur_c:
                    if f in locks and locks[f].get("session_id") == session_id:
                        locks[f]["since"] = now_dt.isoformat()
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
