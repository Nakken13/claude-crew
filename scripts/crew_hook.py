# -*- coding: utf-8 -*-
"""Hook Stop — gestion des tâches du projet.
À chaque fin de tour :
  1. régénère crew/<dir>/INDEX.md (titres + liens),
  2. journalise les transitions (démarrée / terminée / ajoutée) dans
     crew/CLAUDE_CONTEXT/CHANGELOG_TACHES.md,
  3. bloque la fin de tour si une tâche est à la fois dans TODO/ et CURRENT_TASKS/,
  4. rappelle d'historiser + sortir les tests quand une tâche vient d'être terminée.
Ne casse jamais le tour : toute erreur interne -> exit 0 silencieux.
"""
import json, os, re, sys, datetime, pathlib, shutil

ROOT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or pathlib.Path(__file__).resolve().parent.parent)  # racine du projet
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
    entre backticks (`slug.md`) → les placeholders `<...>.md` sont ignorés."""
    warnings = []
    if not BATCH_FILE.exists():
        return warnings
    referenced = set(re.findall(r"`([\w\-.]+\.md)`", BATCH_FILE.read_text(encoding="utf-8")))
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


def slugs_by_batch_section(text):
    """Parse CLAUDE_BATCH.md : decoupe sur les en-tetes '## Batch'/'### Batch',
    extrait pour chaque section les slugs `xxx.md` references entre backticks,
    et les chemins declares sur sa ligne `Zone : ...` (pour la detection de
    chevauchement inter-batchs, cf. check_zone_overlaps)."""
    sections = []
    headers = list(re.finditer(r"^#{2,3}\s*Batch\b.*$", text, re.MULTILINE))
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end]
        slugs = set(re.findall(r"`([\w\-.]+\.md)`", body))
        zone_match = re.search(r"^\*{0,2}Zone\b[^:\n]*:\*{0,2}\s*(.+)$", body, re.MULTILINE)
        zone_paths = set(re.findall(r"`([^`]+)`", zone_match.group(1))) if zone_match else set()
        sections.append({"header": m.group().lstrip("#").strip(), "slugs": slugs, "zone_paths": zone_paths})
    return sections


def active_task_slugs():
    """Slugs (fichiers .md) actuellement en crew/TODO/ ou crew/CURRENT_TASKS/."""
    active = set()
    for d in (DIRS["TODO"], DIRS["CURRENT_TASKS"]):
        if d.exists():
            active |= {f.name for f in d.glob("*.md")
                       if f.name not in ("INDEX.md", "README.md") and not f.name.startswith("_")}
    return active


def _path_overlaps(a, b):
    """Deux chemins se chevauchent si l'un est prefixe (par segment) de l'autre."""
    sa = a.rstrip("/").split("/")
    sb = b.rstrip("/").split("/")
    n = min(len(sa), len(sb))
    return sa[:n] == sb[:n]


def check_zone_overlaps(sections, active):
    """Avertit (non bloquant) si deux batchs ACTIFS (>=1 tache en TODO/CURRENT_TASKS)
    declarent des `Zone :` qui se chevauchent. Garde-fou automatise complementaire a
    la verification manuelle que le manager doit faire avant de demarrer une tache."""
    warnings = []
    active_sections = [s for s in sections if s["slugs"] & active and s["zone_paths"]]
    for i, sec_a in enumerate(active_sections):
        for sec_b in active_sections[i + 1:]:
            for pa in sec_a["zone_paths"]:
                for pb in sec_b["zone_paths"]:
                    if _path_overlaps(pa, pb):
                        warnings.append(
                            f"[zone] Chevauchement detecte entre batchs actifs « {sec_a['header']} » "
                            f"et « {sec_b['header']} » : `{pa}` vs `{pb}`. Verifier CLAUDE_BATCH.md "
                            "avant de demarrer une tache de l'un ou l'autre (risque de collision fichiers)."
                        )
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


DEBUG_HOOK_DUMP = CTX / ".hook_debug_dump.json"


def dump_hook_payload_for_spike(raw):
    """Instrumentation temporaire (spike batch-live-locks, cf.
    docs/superpowers/specs/2026-08-01-batch-live-locks-design.md dans le repo
    voyageo d'origine) : journalise le JSON stdin brut de chaque appel de hook
    pour vérifier la présence/stabilité de `session_id` sur toute la durée
    d'une session, prérequis à un futur mécanisme de verrouillage de batch
    anti-collision multi-Claude. PAS ENCORE IMPLÉMENTÉ au-delà de ce spike —
    à retirer (ou à remplacer par la vraie logique de verrous) une fois le
    spike conclu. Ne pas construire de feature dessus tant que l'hypothèse
    `session_id` stable n'est pas confirmée."""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {"_raw_unparsed": raw}
    history = []
    if DEBUG_HOOK_DUMP.exists():
        try:
            history = json.loads(DEBUG_HOOK_DUMP.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.append({
        "seen_at": datetime.datetime.now().isoformat(),
        "session_id": payload.get("session_id"),
        "hook_event_name": payload.get("hook_event_name"),
        "keys": sorted(payload.keys()) if isinstance(payload, dict) else None,
    })
    DEBUG_HOOK_DUMP.write_text(json.dumps(history[-20:], ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    rotate_graphify_snapshots()

    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    dump_hook_payload_for_spike(raw)

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

    now = datetime.date.today().isoformat()
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
    sections = slugs_by_batch_section(BATCH_FILE.read_text(encoding="utf-8")) if BATCH_FILE.exists() else []
    for w in check_zone_overlaps(sections, active_task_slugs()):
        sys.stderr.write(w + "\n")

    # Invariant bloquant : pas de tâche dans TODO/ ET CURRENT_TASKS/
    dup = {f[:-3] for f in cur_t} & {f[:-3] for f in cur_c}
    if dup:
        reason = ("Incohérence cycle de vie : tâche(s) présente(s) à la fois dans "
                  "crew/TODO/ et crew/CURRENT_TASKS/ : " + ", ".join(sorted(dup)) +
                  ". Retire-les de crew/TODO/ (une tâche commencée ne reste pas dans le backlog).")
        print(json.dumps({"decision": "block", "reason": reason}))
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
