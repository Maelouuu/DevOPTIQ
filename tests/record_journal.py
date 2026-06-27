#!/usr/bin/env python3
"""
tests/record_journal.py — Met à jour le carnet de bord (tests/journal.json).

Le panel lit ce fichier directement (page « Carnet de bord »). La routine
l'alimente à CHAQUE exécution : un bref compte rendu de ce qui a avancé, et
l'état du plan en cours (étapes + progression).

Usage import :
    from tests.record_journal import add_entry, set_step, set_plan
    add_entry(title="Couverture chatbot + 2 fixes",
              summary="…",
              new_tests=12, tests_fixed=2, patches=2, page="chatbot",
              highlights=["…", "…"], next="…")
    set_step("isolation", progress=85)
    set_step("optiqcarto", status="in_progress", progress=20)

Usage CLI :
    python tests/record_journal.py --entry '{"title":"…","summary":"…","new_tests":12}'
    python tests/record_journal.py --step  '{"id":"isolation","progress":85}'
    python tests/record_journal.py --plan  '{"objective":"…"}'

Entrée  : title, summary, new_tests, tests_fixed, patches, page,
          highlights (list[str]), next, author.  (at / date auto-remplis.)
Étape   : id (requis), title, status (done|in_progress|todo), progress (0-100), note.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

JOURNAL_FILE = Path(__file__).parent / 'journal.json'
ENTRY_FIELDS = ["id", "at", "date", "author", "title", "summary", "new_tests",
                "tests_fixed", "patches", "page", "highlights", "next"]
STEP_FIELDS = ["id", "title", "status", "progress", "note"]


def _load():
    if JOURNAL_FILE.exists():
        try:
            d = json.loads(JOURNAL_FILE.read_text(encoding='utf-8'))
            if isinstance(d, dict):
                d.setdefault('plan', {})
                d.setdefault('entries', [])
                d['plan'].setdefault('steps', [])
                return d
        except Exception:
            pass
    return {'plan': {'steps': []}, 'entries': []}


def _save(d):
    JOURNAL_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')


def add_entry(**e):
    """Ajoute une entrée de compte rendu (la plus récente en tête)."""
    d = _load()
    now = datetime.utcnow()
    e.setdefault('at', now.isoformat(timespec='seconds'))
    e.setdefault('date', now.strftime('%d/%m/%Y · %H:%M'))
    e.setdefault('author', 'routine')
    clean = {k: e[k] for k in ENTRY_FIELDS if k in e}
    d['entries'].insert(0, clean)
    _save(d)
    return clean


def set_step(step_id, **fields):
    """Crée ou met à jour une étape du plan."""
    d = _load()
    steps = d['plan'].setdefault('steps', [])
    for s in steps:
        if s.get('id') == step_id:
            s.update({k: fields[k] for k in STEP_FIELDS if k in fields})
            break
    else:
        s = {'id': step_id}
        s.update({k: fields[k] for k in STEP_FIELDS if k in fields})
        steps.append(s)
    d['plan']['updated_at'] = datetime.utcnow().strftime('%d/%m/%Y')
    _save(d)
    return d['plan']


def set_plan(**fields):
    """Met à jour le titre / l'objectif du plan."""
    d = _load()
    for k in ('title', 'objective'):
        if k in fields:
            d['plan'][k] = fields[k]
    d['plan']['updated_at'] = datetime.utcnow().strftime('%d/%m/%Y')
    _save(d)
    return d['plan']


def _arg(argv, flag):
    return json.loads(argv[argv.index(flag) + 1]) if flag in argv else None


def _main(argv):
    did = False
    o = _arg(argv, '--entry')
    if o is not None:
        add_entry(**o); print('✓ entrée ajoutée au carnet'); did = True
    o = _arg(argv, '--step')
    if o is not None:
        sid = o.pop('id'); set_step(sid, **o); print(f'✓ étape « {sid} » mise à jour'); did = True
    o = _arg(argv, '--plan')
    if o is not None:
        set_plan(**o); print('✓ plan mis à jour'); did = True
    if not did:
        print(__doc__); return 1
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
