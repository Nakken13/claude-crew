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
import re
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

USER_SETTINGS_PATH = pathlib.Path.home() / ".claude" / "settings.json"
PROJECT_SETTINGS_FILES = ("settings.json", "settings.local.json")
PLUGIN_NAME = "claude-crew"
LOCAL_HOOK_RE = re.compile(r"(^|[\s\"'/\\=])crew[/\\]crew_hook\.py")

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


def _write_json_atomic(path, data, **dumps_kw):
    """temp file + os.replace : jamais de JSON tronque si le process est tue."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, **dumps_kw) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def save_scaffold_version(project_root, data):
    """Ecriture atomique (temp file + os.replace), meme idiome que
    crew_hook.save_locks() : evite un SCAFFOLD_VERSION.json tronque si le
    process est tue en cours d'ecriture (il est relu a chaque /crew-update
    suivant pour decider apply vs conflict)."""
    p = pathlib.Path(project_root) / SCAFFOLD_VERSION_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(p, data, sort_keys=True)


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


def _read_settings(path):
    """JSON d'un settings.json, {} si absent/illisible/de forme inattendue."""
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _plugin_enabled(settings):
    plugins = settings.get("enabledPlugins")
    if not isinstance(plugins, dict):
        return False
    return any(k.split("@")[0] == PLUGIN_NAME and v is True for k, v in plugins.items())


def _is_local_crew_hook(hook):
    command = hook.get("command") if isinstance(hook, dict) else None
    return (isinstance(command, str) and "CLAUDE_PLUGIN_ROOT" not in command
            and LOCAL_HOOK_RE.search(command) is not None)


def _group_hooks(group):
    inner = group.get("hooks") if isinstance(group, dict) else None
    return inner if isinstance(inner, list) else []


def _hook_groups(settings):
    """(evenement, groupes) pour chaque evenement de `hooks` bien forme."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event, groups in hooks.items():
        if isinstance(groups, list):
            yield event, groups


def _iter_local_hook_commands(settings):
    for event, groups in _hook_groups(settings):
        for group in groups:
            for hook in _group_hooks(group):
                if _is_local_crew_hook(hook):
                    yield event, hook["command"]


def _strip_local_hooks(settings):
    """Retire de `settings` (en place) les hooks locaux crew ; ne supprime
    que les groupes/evenements vides *a cause* du retrait. True si modifie."""
    modified = False
    for event, groups in list(_hook_groups(settings)):
        kept = []
        for group in groups:
            inner = _group_hooks(group)
            remaining = [h for h in inner
                         if not _is_local_crew_hook(h)]
            if len(remaining) != len(inner):
                modified = True
                group["hooks"] = remaining
                if not remaining:
                    continue
            kept.append(group)
        if kept:
            settings["hooks"][event] = kept
        else:
            del settings["hooks"][event]
    if modified and not settings["hooks"]:
        del settings["hooks"]
    return modified


def detect_double_hook(project_root, user_settings_path=None):
    """{evenement: [commandes locales]} quand le plugin claude-crew est actif
    (`enabledPlugins` du projet ou de l'utilisateur) ET que les settings du
    projet appellent aussi la copie locale `crew/crew_hook.py` : deux hooks
    sur le meme crew_lock.json. {} sinon (legacy sans plugin = normal).
    Lecture seule."""
    claude_dir = pathlib.Path(project_root) / ".claude"
    project_settings = [_read_settings(claude_dir / name) for name in PROJECT_SETTINGS_FILES]
    found = {}
    for settings in project_settings:
        for event, cmd in _iter_local_hook_commands(settings):
            found.setdefault(event, []).append(cmd)
    if not found:
        return {}
    if not any(_plugin_enabled(s) for s in project_settings) and not _plugin_enabled(
            _read_settings(user_settings_path or USER_SETTINGS_PATH)):
        return {}
    return found


def remove_double_hook(project_root):
    """Retire des settings du projet les seules entrees hook locales
    `crew/crew_hook.py` (le reste du fichier est conserve, mais reformate en
    JSON indente). Ecrit : a n'appeler que sur confirmation explicite.
    Retourne les fichiers modifies."""
    changed = []
    claude_dir = pathlib.Path(project_root) / ".claude"
    for name in PROJECT_SETTINGS_FILES:
        path = claude_dir / name
        settings = _read_settings(path)
        if _strip_local_hooks(settings):
            _write_json_atomic(path, settings)
            changed.append(str(path))
    return changed


def _handle_double_hook(project_root, remove):
    """Avertit (et ne retire que si `remove`) un double hook plugin + local."""
    double = detect_double_hook(project_root)
    if double:
        print("ATTENTION : plugin claude-crew actif ET hooks locaux crew/crew_hook.py "
              "(deux hooks sur le meme crew_lock.json) :")
        for event, cmds in double.items():
            for cmd in cmds:
                print(f"  {event}: {cmd}")
        if remove:
            for f in remove_double_hook(project_root):
                print(f"Hooks locaux retires de {f}")
        else:
            print("Relancer avec --remove-double-hook pour les retirer (aucune modification faite).")
        print()
    elif remove:
        print("--remove-double-hook : aucun double hook detecte, rien a retirer.")


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
    parser.add_argument("--remove-double-hook", action="store_true",
                         help="retire des settings du projet les hooks locaux crew/crew_hook.py "
                              "quand le plugin claude-crew est aussi actif (sinon : avertissement seul)")
    args = parser.parse_args()

    _handle_double_hook(args.project, args.remove_double_hook)

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
