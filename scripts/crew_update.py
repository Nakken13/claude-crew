# -*- coding: utf-8 -*-
"""Moteur de mise a jour du scaffold crew sur un projet deja bootstrape
(tache mecanisme-mise-a-jour-scaffold-multi-projets).

Compare, pour chaque fichier "moteur" d'une liste blanche, le contenu local
du projet cible a celui de la source du scaffold, en s'appuyant sur un hash
enregistre a la derniere ecriture (crew/CLAUDE_CONTEXT/SCAFFOLD_VERSION.json)
pour ne jamais ecraser silencieusement une personnalisation utilisateur.

N'ecrit jamais dans les dossiers de donnees utilisateur (crew/TODO,
crew/CURRENT_TASKS, crew/PROBLEMS, crew/ICEBOX, crew/TESTS,
crew/CLAUDE_CONTEXT/HISTORIQUE.md, ...) : seule la liste blanche explicite
passee par l'appelant est jamais touchee.

Usage CLI (dry-run par defaut, n'ecrit rien sans --apply) :
    python crew_update.py --project <dir> --source <dir> [--apply]
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCAFFOLD_VERSION_REL = pathlib.Path("crew") / "CLAUDE_CONTEXT" / "SCAFFOLD_VERSION.json"

# Fichiers moteur communs a tout projet bootstrape via crew-init, quel que
# soit le mode d'installation (plugin ou clone manuel).
ENGINE_FILES_COMMON = [
    "CLAUDE.md",
    "AGENTS.md",
    "PRODUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "check_placeholders.py",
]

# Fichiers moteur supplementaires, uniquement pour les projets bootstrapes
# avant le repackaging plugin (Option C / clone manuel) : skills, agents et
# hooks copies localement plutot que servis depuis ${CLAUDE_PLUGIN_ROOT}.
ENGINE_FILES_LEGACY = [
    "crew/crew_hook.py",
    "crew/spec_to_task_hook.py",
    ".claude/skills/crew-init/SKILL.md",
    ".claude/skills/crew-new-task/SKILL.md",
    ".claude/skills/crew-close-task/SKILL.md",
    ".claude/skills/crew-status/SKILL.md",
    ".claude/skills/crew-start/SKILL.md",
    ".claude/agents/ceo.md",
    ".claude/agents/manager.md",
    ".claude/agents/comms.md",
    ".claude/agents/architect.md",
    ".claude/agents/designer.md",
    ".claude/agents/legal.md",
]


def hash_file(path):
    """Hash sha256 du contenu, ou None si le fichier n'existe pas."""
    path = pathlib.Path(path)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(local_hash, recorded_hash, source_hash):
    """Decision pure pour un fichier moteur, sans aucun acces disque.

    - "absent"    : n'existe ni localement ni dans la source (rien a faire).
    - "new"       : absent localement, present dans la source -> a creer.
    - "removed"   : present localement, disparu de la source (deplace ou
                    supprime en amont) -> jamais applique automatiquement
                    (rien a copier), signale pour decision manuelle.
    - "up_to_date": local deja identique a la source -> no-op.
    - "apply"     : local inchange depuis notre derniere ecriture connue
                    (recorded_hash) mais la source a evolue -> safe a ecraser.
    - "conflict"  : local differe de la derniere ecriture connue -> une
                    personnalisation utilisateur est possible, ne jamais
                    ecraser silencieusement.
    """
    if local_hash is None:
        return "new" if source_hash is not None else "absent"
    if source_hash is None:
        return "removed"
    if local_hash == source_hash:
        return "up_to_date"
    if local_hash == recorded_hash:
        return "apply"
    return "conflict"


def load_scaffold_version(project_root):
    p = pathlib.Path(project_root) / SCAFFOLD_VERSION_REL
    if not p.is_file():
        return {"version": None, "files": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def save_scaffold_version(project_root, data):
    """Ecriture atomique (temp file + os.replace), meme idiome que
    crew_hook.save_locks() : evite un SCAFFOLD_VERSION.json tronque si le
    process est tue en cours d'ecriture (il est relu a chaque /crew-update
    suivant pour decider apply vs conflict)."""
    p = pathlib.Path(project_root) / SCAFFOLD_VERSION_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(p))


def plan(project_root, source_root, whitelist):
    """Decision par fichier de la liste blanche, sans rien ecrire."""
    project_root = pathlib.Path(project_root)
    source_root = pathlib.Path(source_root)
    recorded = load_scaffold_version(project_root).get("files", {})
    decisions = []
    for rel in whitelist:
        local_hash = hash_file(project_root / rel)
        source_hash = hash_file(source_root / rel)
        recorded_hash = recorded.get(rel)
        decisions.append({
            "path": rel,
            "status": classify(local_hash, recorded_hash, source_hash),
            "local_hash": local_hash,
            "source_hash": source_hash,
        })
    return decisions


def apply(project_root, source_root, decisions):
    """Ecrit uniquement les fichiers en statut 'apply'/'new'. Retourne la
    liste des chemins relatifs effectivement ecrits."""
    project_root = pathlib.Path(project_root)
    source_root = pathlib.Path(source_root)
    applied = []
    for d in decisions:
        if d["status"] not in ("apply", "new"):
            continue
        dst = project_root / d["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / d["path"], dst)
        applied.append(d["path"])
    return applied


def detect_mode(project_root):
    """"legacy" si le projet cible a une copie locale des skills/agents
    crew-* (bootstrape avant le repackaging plugin, cf. skills/crew-*),
    "plugin" sinon (skills/agents/hooks servis depuis
    ${CLAUDE_PLUGIN_ROOT}, rien a synchroniser pour eux)."""
    marker = pathlib.Path(project_root) / ".claude" / "skills" / "crew-init" / "SKILL.md"
    return "legacy" if marker.is_file() else "plugin"


def seed(project_root, whitelist, version, force=False):
    """Amorce SCAFFOLD_VERSION.json sur un projet legacy qui n'en a pas
    encore : accepte le contenu local actuel de chaque fichier present comme
    "notre derniere ecriture connue". Sans cet amorçage, le premier plan()
    d'un projet legacy classe tout fichier divergent en "conflict" (aucun
    recorded_hash pour prouver l'absence de personnalisation) et
    /crew-update n'applique rien automatiquement des le premier run.

    Refuse d'ecraser un historique deja enregistre sauf si force=True :
    contrairement a record_version() qui merge, seed() part d'une ardoise
    vierge et perdrait silencieusement les hashs existants sinon."""
    project_root = pathlib.Path(project_root)
    existing = load_scaffold_version(project_root)
    if not force and existing.get("files"):
        raise ValueError(
            "SCAFFOLD_VERSION.json existe deja avec des hashs enregistres — "
            "seed() les ecraserait. Utiliser plan()/apply()/record_version() "
            "pour une mise a jour normale, ou passer force=True pour "
            "reamorcer volontairement la baseline."
        )
    files = {}
    for rel in whitelist:
        h = hash_file(project_root / rel)
        if h is not None:
            files[rel] = h
    data = {"version": version, "files": files}
    save_scaffold_version(project_root, data)
    return data


def record_version(project_root, source_version, decisions):
    """Bump la version enregistree et le hash des fichiers effectivement
    appliques (les conflits gardent leur hash enregistre precedent)."""
    data = load_scaffold_version(project_root)
    files = data.setdefault("files", {})
    for d in decisions:
        if d["status"] in ("apply", "new"):
            files[d["path"]] = d["source_hash"]
    data["version"] = source_version
    save_scaffold_version(project_root, data)
    return data


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="racine du projet cible")
    parser.add_argument("--source", default=None, help="racine de la source du scaffold (inutile avec --seed)")
    parser.add_argument("--legacy", action="store_true",
                         help="force l'inclusion des fichiers moteur legacy (auto-detecte via detect_mode() sinon)")
    parser.add_argument("--apply", action="store_true",
                         help="ecrit reellement les fichiers 'apply'/'new' (sinon dry-run)")
    parser.add_argument("--source-version", default=None,
                         help="version a enregistrer apres application (ex. depuis .claude-plugin/plugin.json)")
    parser.add_argument("--seed", action="store_true",
                         help="amorce SCAFFOLD_VERSION.json sur un projet legacy sans historique "
                              "(accepte le contenu local actuel comme baseline), puis quitte sans comparer a la source")
    parser.add_argument("--force", action="store_true",
                         help="avec --seed, reamorce volontairement une baseline deja enregistree")
    args = parser.parse_args()

    whitelist = list(ENGINE_FILES_COMMON)
    if args.legacy or detect_mode(args.project) == "legacy":
        whitelist += ENGINE_FILES_LEGACY

    if args.seed:
        if not args.source_version:
            parser.error("--seed requiert --source-version")
        data = seed(args.project, whitelist, args.source_version, force=args.force)
        print(f"Amorce : {len(data['files'])} fichier(s) enregistre(s) comme baseline (version {data['version']}).")
        return

    if not args.source:
        parser.error("--source est requis hors mode --seed")

    decisions = plan(args.project, args.source, whitelist)
    for d in decisions:
        if d["status"] == "absent":
            continue
        print(f"{d['status']:>10}  {d['path']}")

    if args.apply:
        applied = apply(args.project, args.source, decisions)
        if args.source_version:
            record_version(args.project, args.source_version, decisions)
        print(f"\n{len(applied)} fichier(s) applique(s).")
    else:
        print("\nDry-run — relancer avec --apply pour ecrire.")


if __name__ == "__main__":
    _main()
