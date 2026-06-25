#!/usr/bin/env python3
"""
tests/record_patch.py — Enregistre un patch dans le registre versionné
``tests/patches.json`` (source de vérité du panel de tests).

Le panel (Code/routes/test_panel.py → sync_patches_to_db) synchronise ce
fichier vers la table ``test_patches`` à chaque consultation. Ajouter une
entrée ici suffit donc à faire apparaître le patch dans le panel — aucun accès
à la base de prod n'est requis (la routine tourne en local et pousse le code).

Usage CLI (JSON via --json ou via stdin) :
    python tests/record_patch.py --json '{"patch_uid": "2026-06-25-x", ...}'
    echo '{ ... }' | python tests/record_patch.py

Usage import :
    from tests.record_patch import record_patch
    record_patch(patch_uid="2026-06-25-x", title="...", node_ids=[...], ...)

Champs d'une entrée :
    patch_uid       (str, requis, unique)  identifiant stable du patch
    title           (str)                  résumé court du correctif
    node_ids        (list[str])            node_ids pytest des tests corrigés,
                                           ex: "tests/test_11_tools.py::TestX::test_y"
    page_slug       (str)                  slug de la page (ex: "tools")
    failure_reason  (str)                  pourquoi le test échouait
    was_real_bug    (bool)                 y avait-il une vraie erreur applicative ?
    root_cause      (str)                  app_bug | test_isolation | test_quality
    error           (str)                  description de l'erreur (diagnostic)
    fix_description (str)                  comment cela a été corrigé
    files_changed   (list[str])            fichiers modifiés
    author          (str)                  "claude" | "routine"
    commit          (str)                  sha du commit (optionnel)
    fixed_at        (str ISO)              horodatage (auto-rempli si absent)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PATCHES_FILE = Path(__file__).parent / 'patches.json'

FIELDS = ["patch_uid", "title", "node_ids", "page_slug", "failure_reason",
          "was_real_bug", "root_cause", "error", "fix_description",
          "files_changed", "author", "commit", "fixed_at"]


def _load():
    if not PATCHES_FILE.exists():
        return []
    try:
        data = json.loads(PATCHES_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record_patch(**entry):
    """Upsert d'un patch dans tests/patches.json (clé : patch_uid)."""
    uid = (entry.get('patch_uid') or '').strip()
    if not uid:
        raise ValueError("patch_uid est requis")
    entry.setdefault('fixed_at', datetime.utcnow().isoformat(timespec='seconds'))
    entry.setdefault('author', 'routine')
    entry.setdefault('was_real_bug', True)
    entry.setdefault('node_ids', [])
    entry.setdefault('files_changed', [])
    clean = {k: entry.get(k) for k in FIELDS if k in entry}

    patches = _load()
    for i, p in enumerate(patches):
        if p.get('patch_uid') == uid:
            patches[i] = {**p, **clean}
            break
    else:
        patches.append(clean)

    PATCHES_FILE.write_text(
        json.dumps(patches, ensure_ascii=False, indent=2) + "\n",
        encoding='utf-8',
    )
    return clean


def _main(argv):
    raw = None
    if '--json' in argv:
        try:
            raw = argv[argv.index('--json') + 1]
        except IndexError:
            raw = None
    elif not sys.stdin.isatty():
        raw = sys.stdin.read()

    if not raw:
        print(__doc__)
        return 1

    entry = json.loads(raw)
    rec = record_patch(**entry)
    print(f"✓ Patch enregistré : {rec['patch_uid']}")
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
