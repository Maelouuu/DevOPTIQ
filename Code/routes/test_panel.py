import ast
import json
import os
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from flask import (Blueprint, Response, jsonify, render_template, request,
                   stream_with_context, current_app, abort)

from Code.extensions import db
from Code.models.test_models import (TestCase, TestPage, TestPatch, TestResult,
                                     TestRun)

test_panel_bp = Blueprint('test_panel', __name__, url_prefix='/testpanel')

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TESTS_DIR    = _PROJECT_ROOT / 'tests'

# run_id → {'lines': [str], 'done': bool}
_runs: dict = {}
_runs_lock = threading.Lock()


# ── Sync test files → DB ──────────────────────────────────────────────────────

def _parse_test_file(fpath: Path) -> dict:
    src  = fpath.read_text(encoding='utf-8')
    tree = ast.parse(src)
    mod_doc = ast.get_docstring(tree) or ''
    title = ''
    for line in mod_doc.splitlines():
        s = line.strip()
        if s.startswith('Page :') or s.startswith('Pages :'):
            title = s.split(':', 1)[1].strip()
            break

    marker = ''
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'pytestmark':
                    v = node.value
                    if isinstance(v, ast.Attribute):
                        marker = v.attr
                    elif isinstance(v, ast.List) and v.elts:
                        if isinstance(v.elts[0], ast.Attribute):
                            marker = v.elts[0].attr

    cases = []

    def _ajouter(fonction, classe, doc_parent):
        doc = ast.get_docstring(fonction) or doc_parent
        # node_id pytest : avec la classe quand il y en a une, sans sinon.
        node_id = (f"tests/{fpath.name}::{classe}::{fonction.name}" if classe
                   else f"tests/{fpath.name}::{fonction.name}")
        cases.append({
            'node_id':      node_id,
            'class_name':   classe or '',
            'name':         fonction.name,
            'display_name': fonction.name[5:].replace('_', ' ').capitalize(),
            'description':  doc,
        })

    # ⚠️ Les tests écrits en fonctions de MODULE comptent autant que ceux
    # rangés dans une classe. Ne recenser que les classes laissait sept pages
    # entières (test_48, 49, 50, 51, 52, 62…) à zéro cas : elles affichaient
    # « jamais joué » même après une exécution complète, et leurs ~120 tests
    # ne pesaient dans aucun taux de fiabilité.
    _FONCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_doc = ast.get_docstring(node) or ''
            for item in node.body:
                if isinstance(item, _FONCTIONS) and item.name.startswith('test_'):
                    _ajouter(item, node.name, class_doc)
        elif isinstance(node, _FONCTIONS) and node.name.startswith('test_'):
            _ajouter(node, None, '')

    # slug: remove numeric prefix → e.g. test_01_auth → auth
    parts = fpath.stem.split('_')
    slug = '_'.join(p for p in parts if not p.isdigit() and p != 'test') or fpath.stem

    return dict(file_name=fpath.name, slug=slug, title=title or slug,
                description=mod_doc, marker=marker, cases=cases)


def sync_tests_to_db():
    for fpath in sorted(_TESTS_DIR.glob('test_*.py')):
        info = _parse_test_file(fpath)
        page = TestPage.query.filter_by(slug=info['slug']).first()
        if not page:
            page = TestPage(slug=info['slug'])
            db.session.add(page)
        page.title       = info['title']
        page.description = info['description']
        page.file_name   = info['file_name']
        page.marker      = info['marker']
        db.session.flush()

        existing = {c.node_id for c in page.cases}
        for c in info['cases']:
            if c['node_id'] in existing:
                case = TestCase.query.filter_by(node_id=c['node_id']).first()
                if case:
                    case.display_name = c['display_name']
                    case.description  = c['description']
            else:
                db.session.add(TestCase(page_id=page.id, **c))
    db.session.commit()


# ── Sync patch registry → DB ──────────────────────────────────────────────────

_PATCHES_FILE = _TESTS_DIR / 'patches.json'


def sync_patches_to_db():
    """
    Synchronise le registre versionné ``tests/patches.json`` vers la table
    ``test_patches``. Upsert par ``patch_uid`` : la routine (et Claude) n'ont
    qu'à ajouter une entrée au JSON et committer — aucun accès direct à la DB
    de prod n'est requis pour que le patch apparaisse dans le panel.
    """
    if not _PATCHES_FILE.exists():
        return
    try:
        entries = json.loads(_PATCHES_FILE.read_text(encoding='utf-8'))
    except Exception:
        return
    if not isinstance(entries, list):
        return

    for e in entries:
        uid = (e.get('patch_uid') or '').strip()
        if not uid:
            continue
        p = TestPatch.query.filter_by(patch_uid=uid).first()
        if not p:
            p = TestPatch(patch_uid=uid)
            db.session.add(p)
        p.title           = (e.get('title') or '')[:200]
        p.node_ids        = json.dumps(e.get('node_ids', []), ensure_ascii=False)
        p.page_slug       = e.get('page_slug')
        p.failure_reason  = e.get('failure_reason', '')
        p.was_real_bug    = bool(e.get('was_real_bug', True))
        p.root_cause      = (e.get('root_cause') or '')[:40]
        p.error           = e.get('error', '')
        p.fix_description = e.get('fix_description', '')
        p.files_changed   = json.dumps(e.get('files_changed', []), ensure_ascii=False)
        p.author          = (e.get('author') or 'routine')[:40]
        p.commit          = (e.get('commit') or '')[:60]
        fa = e.get('fixed_at')
        if fa:
            try:
                p.fixed_at = datetime.fromisoformat(str(fa).replace('Z', ''))
            except Exception:
                p.fixed_at = None
    db.session.commit()


def _patches_for_nodes(node_ids):
    """Retourne les patchs dont au moins un node_id corrigé est dans node_ids."""
    wanted = set(node_ids)
    out = []
    for p in TestPatch.query.order_by(TestPatch.created_at.desc()).all():
        if wanted & set(p.node_id_list):
            out.append(p)
    return out


def _patch_to_dict(p):
    return {
        'patch_uid':       p.patch_uid,
        'title':           p.title,
        'node_ids':        p.node_id_list,
        'page_slug':       p.page_slug,
        'failure_reason':  p.failure_reason,
        'was_real_bug':    p.was_real_bug,
        'root_cause':      p.root_cause,
        'error':           p.error,
        'fix_description': p.fix_description,
        'files_changed':   p.files_list,
        'author':          p.author,
        'commit':          p.commit,
        'fixed_at':        p.fixed_at.strftime('%d/%m/%y %H:%M') if p.fixed_at else '',
    }


# Catégories de cause racine connues (pour filtres + couleurs du panel)
PATCH_CATEGORIES = ('app_bug', 'test_isolation', 'test_quality')


def _patch_category_counts(patches):
    """Compte les patchs par catégorie de cause racine."""
    counts = {c: 0 for c in PATCH_CATEGORIES}
    counts['other'] = 0
    for p in patches:
        key = p.root_cause if p.root_cause in counts else 'other'
        counts[key] += 1
    return counts


def _recent_runs(limit=20):
    """Liste structurée des derniers runs terminés (pour dashboard + API)."""
    out = []
    q = (TestRun.query.filter(TestRun.status == 'done')
         .order_by(TestRun.finished_at.desc()).limit(limit).all())
    for r in q:
        res = list(r.results)
        total = len(res)
        passed = sum(1 for x in res if x.status == 'passed')
        dur = None
        if r.started_at and r.finished_at:
            dur = round((r.finished_at - r.started_at).total_seconds(), 1)
        out.append({
            'id':         r.id,
            'at':         r.finished_at.strftime('%d/%m/%y %H:%M') if r.finished_at else '—',
            'scope':      r.scope or 'all',
            'passed':     passed,
            'failed':     total - passed,
            'total':      total,
            'pct':        round(100 * passed / total) if total else 0,
            'duration_s': dur,
        })
    return out


# ── Run pytest ────────────────────────────────────────────────────────────────

def _build_args(scope: str, xml_path: str) -> list[str]:
    base = [sys.executable, '-m', 'pytest', '--tb=short', '-v',
            '--no-header', f'--junit-xml={xml_path}']
    if scope == 'all':
        base += [str(_TESTS_DIR)]
    elif scope.startswith('page:'):
        page = TestPage.query.filter_by(slug=scope[5:]).first()
        if page and page.file_name:
            base += [str(_TESTS_DIR / page.file_name)]
    elif scope.startswith('case:'):
        case = db.session.get(TestCase, int(scope[5:]))
        if case:
            # node_id tel qu'il a été recensé : un test écrit en fonction de
            # module n'a pas de classe, et « fichier::::nom » ne veut rien dire
            # pour pytest.
            base += [case.node_id]
    return base


def _save_results(db_url: str, run_id: int, xml_path: str, emit):
    """
    Parse le XML JUnit et persiste les résultats.
    SQLite → sqlite3 brut (évite tout problème de session/URL SQLAlchemy).
    PostgreSQL → SQLAlchemy avec engine dédié.
    """
    import traceback

    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        emit('\n[WARN] XML JUnit invalide ou vide\n')
        return

    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')

    # Construire la liste de résultats à partir du XML
    results = []
    for tc in root.findall('.//testcase'):
        classname = tc.get('classname', '')
        name      = tc.get('name', '')
        # JUnit donne « tests.test_50_x.TestY » pour un test de classe et
        # « tests.test_50_x » pour un test écrit en fonction de module. Prendre
        # parts[-1] comme classe faisait passer le NOM DU MODULE pour une
        # classe : le node_id ne correspondait à rien et le résultat était
        # perdu. La classe est ce qui SUIT le module, s'il y a quelque chose.
        parts     = classname.split('.')
        idx       = next((i for i, p in enumerate(parts) if p.startswith('test_')), None)
        if idx is None:
            continue
        file_mod  = parts[idx]
        class_nm  = '.'.join(parts[idx + 1:])
        node_id   = (f"tests/{file_mod}.py::{class_nm}::{name}" if class_nm
                     else f"tests/{file_mod}.py::{name}")
        failure = tc.find('failure')
        error   = tc.find('error')
        if failure is not None:
            status  = 'failed'
            message = ((failure.get('message') or '') + '\n' + (failure.text or ''))[:3000]
        elif error is not None:
            status  = 'error'
            message = ((error.get('message') or '') + '\n' + (error.text or ''))[:3000]
        else:
            status  = 'passed'
            message = ''
        duration = float(tc.get('time', 0) or 0)
        results.append((node_id, status, duration, message))

    if db_url.startswith('sqlite'):
        # ── SQLite : accès direct via sqlite3, pas d'ambiguïté de chemin ────────
        import sqlite3 as _sqlite3
        # Extraire le chemin du fichier depuis l'URL (strip sqlite:/// et ?params)
        raw_path = db_url[len('sqlite:///'):]
        raw_path = raw_path.split('?')[0]
        print(f'[test_panel] Sauvegarde run #{run_id} → {raw_path}', flush=True)
        try:
            conn = _sqlite3.connect(raw_path, timeout=30)
            conn.row_factory = _sqlite3.Row
            cur = conn.cursor()
            cur.execute("UPDATE test_runs SET status='done', finished_at=? WHERE id=?",
                        (now_str, run_id))
            saved = 0
            for node_id, status, duration, message in results:
                row = cur.execute(
                    "SELECT id FROM test_cases WHERE node_id=?", (node_id,)
                ).fetchone()
                if not row:
                    continue
                case_id = row[0]
                cur.execute(
                    "INSERT INTO test_results (run_id, case_id, status, duration, message, ran_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (run_id, case_id, status, duration, message, now_str)
                )
                cur.execute(
                    "UPDATE test_cases SET last_status=?, last_ran_at=? WHERE id=?",
                    (status, now_str, case_id)
                )
                saved += 1
            conn.commit()
            conn.close()
            msg = f'\n[OK] {saved}/{len(results)} résultats sauvegardés (run #{run_id})\n'
            emit(msg)
            print(f'[test_panel] {msg.strip()}', flush=True)
        except Exception:
            tb = traceback.format_exc()
            emit(f'\n[DB ERROR sqlite3]\n{tb}\n')
            print(f'[test_panel] DB ERROR run #{run_id}:\n{tb}', flush=True)

    else:
        # ── PostgreSQL : SQLAlchemy avec engine propre ────────────────────────
        from sqlalchemy import create_engine as _ce, text as _text
        _engine = _ce(db_url, pool_pre_ping=True, pool_size=1, max_overflow=0)
        try:
            with _engine.connect() as conn:
                conn.execute(_text(
                    "UPDATE test_runs SET status='done', finished_at=:ts WHERE id=:rid"
                ), {'ts': now_str, 'rid': run_id})
                for node_id, status, duration, message in results:
                    row = conn.execute(_text(
                        "SELECT id FROM test_cases WHERE node_id=:nid"
                    ), {'nid': node_id}).fetchone()
                    if not row:
                        continue
                    case_id = row[0]
                    conn.execute(_text(
                        "INSERT INTO test_results (run_id,case_id,status,duration,message,ran_at)"
                        " VALUES (:r,:c,:s,:d,:m,:ts)"
                    ), {'r': run_id, 'c': case_id, 's': status, 'd': duration,
                        'm': message, 'ts': now_str})
                    conn.execute(_text(
                        "UPDATE test_cases SET last_status=:s, last_ran_at=:ts WHERE id=:c"
                    ), {'s': status, 'ts': now_str, 'c': case_id})
                conn.commit()
            emit(f'\n[OK] {len(results)} résultats sauvegardés (run #{run_id})\n')
        except Exception:
            emit(f'\n[DB ERROR postgresql]\n{traceback.format_exc()}\n')
        finally:
            _engine.dispose()


# Le blueprint n'est protégé par AUCUNE authentification : qui connaît l'URL de
# l'instance peut demander une exécution. Tant que l'image n'embarquait pas la
# suite, pytest ne collectait rien et cela ne coûtait rien ; maintenant qu'elle
# est là et que Cloud Run tourne sans bridage CPU, chaque demande consomme deux
# minutes de deux vCPU. On borne donc les pytest simultanés SUR CETTE INSTANCE.
# Le garde vit dans le worker, pas dans la route : le contrat du panel (un run
# par demande, id distinct, portée exacte) reste intact, et une route qu'un
# test neutralise n'est jamais bridée. Ce n'est PAS une authentification :
# cela plafonne la casse.
_MAX_SIMULTANEES = 3
_actifs = 0
_actifs_lock = threading.Lock()


def _reserver_creneau():
    global _actifs
    with _actifs_lock:
        if _actifs >= _MAX_SIMULTANEES:
            return False
        _actifs += 1
        return True


def _liberer_creneau():
    global _actifs
    with _actifs_lock:
        _actifs = max(0, _actifs - 1)


def _run_thread(run_id: int, scope: str, app):
    def emit(line: str):
        with _runs_lock:
            if run_id in _runs:
                _runs[run_id]['lines'].append(line)

    if not _reserver_creneau():
        emit(f"[REFUSÉ] {_MAX_SIMULTANEES} exécutions déjà en cours sur cette "
             "instance — réessayez dans deux minutes.\n")
        with app.app_context():
            run = db.session.get(TestRun, run_id)
            if run:
                run.status = 'done'
                run.finished_at = datetime.utcnow()
                db.session.commit()
        with _runs_lock:
            if run_id in _runs:
                _runs[run_id]['done'] = True
        return

    try:
        _executer_run(run_id, scope, app, emit)
    finally:
        _liberer_creneau()


def _executer_run(run_id: int, scope: str, app, emit):
    with app.app_context():
        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        fd, xml_path = tempfile.mkstemp(suffix='.xml', prefix=f'trun_{run_id}_')
        os.close(fd)
        args = _build_args(scope, xml_path)
        # Fermer la session SQLAlchemy AVANT de lancer le subprocess
        # pour éviter que le lock SQLite bloque _save_results
        db.session.remove()

    emit(f"$ pytest {' '.join(args[3:])}\n")

    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                cwd=str(_PROJECT_ROOT), text=True, bufsize=1)
        for line in proc.stdout:
            emit(line)
        proc.wait()
    except Exception as e:
        emit(f'\n[ERROR lors du lancement] {e}\n')

    if os.path.exists(xml_path):
        _save_results(db_url, run_id, xml_path, emit)
        try:
            os.unlink(xml_path)
        except OSError:
            pass
    else:
        import sqlite3 as _sq3
        if db_url.startswith('sqlite'):
            raw = db_url[len('sqlite:///'):].split('?')[0]
            try:
                c = _sq3.connect(raw, timeout=30)
                c.execute("UPDATE test_runs SET status='done', finished_at=? WHERE id=?",
                          (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f'), run_id))
                c.commit(); c.close()
            except Exception:
                pass

    # Marquer done en dernier — le SSE generator détecte ce flag
    with _runs_lock:
        if run_id in _runs:
            _runs[run_id]['done'] = True


def _expire_stale_runs():
    """Mark runs still 'running' after 15 min as done (crash/restart recovery)."""
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    stale = TestRun.query.filter(
        TestRun.status == 'running',
        TestRun.started_at < cutoff
    ).all()
    for r in stale:
        r.status = 'done'
    if stale:
        db.session.commit()


def _start_run(scope: str) -> int:
    run = TestRun(scope=scope, status='running')
    db.session.add(run)
    db.session.commit()
    run_id = run.id
    # Initialiser AVANT de démarrer le thread pour éviter la race condition SSE
    with _runs_lock:
        _runs[run_id] = {'lines': [], 'done': False}
    app = current_app._get_current_object()
    threading.Thread(target=_run_thread, args=(run_id, scope, app), daemon=True).start()
    return run_id


# ── Routes ────────────────────────────────────────────────────────────────────

_VIEW_ENDPOINTS = {'test_panel.panel', 'test_panel.page_detail',
                   'test_panel.case_detail', 'test_panel.patches_page'}

@test_panel_bp.app_context_processor
def _inject_nav():
    """Données de la barre latérale (pages + % global), pour tous les écrans du panel."""
    if (request.blueprint or '') != 'test_panel':
        return {}
    try:
        from sqlalchemy import func
        pages = TestPage.query.order_by(TestPage.file_name).all()
        rows = (db.session.query(TestCase.page_id, TestCase.last_status, func.count())
                .group_by(TestCase.page_id, TestCase.last_status).all())
        agg = {}
        for pid, status, cnt in rows:
            a = agg.setdefault(pid, {'total': 0, 'passed': 0})
            a['total'] += cnt
            if status == 'passed':
                a['passed'] += cnt
        nav, gp_total, gp_pass = [], 0, 0
        for p in pages:
            a = agg.get(p.id, {'total': 0, 'passed': 0})
            gp_total += a['total']; gp_pass += a['passed']
            nav.append({'slug': p.slug, 'title': p.title, 'total': a['total'],
                        'pct': round(100 * a['passed'] / a['total']) if a['total'] else 0})
        return {'nav_pages': nav,
                'nav_global_pct': round(100 * gp_pass / gp_total) if gp_total else 0}
    except Exception:
        return {'nav_pages': [], 'nav_global_pct': 0}


@test_panel_bp.before_request
def _auto_sync():
    # Ne synchroniser les fichiers de test que sur les pages visuelles,
    # pas sur les routes API (run_status, stream, run_all…).
    if request.endpoint not in _VIEW_ENDPOINTS:
        return
    try:
        for model in (TestPage, TestCase, TestRun, TestResult, TestPatch):
            model.__table__.create(db.engine, checkfirst=True)
        sync_tests_to_db()
        sync_patches_to_db()
    except Exception:
        pass


@test_panel_bp.route('/')
def panel():
    pages = TestPage.query.order_by(TestPage.file_name).all()
    page_stats = []
    for page in pages:
        cases = list(page.cases)
        total = len(cases)
        case_ids = [c.id for c in cases]

        runs_done = (TestRun.query
                     .filter(TestRun.status == 'done')
                     .filter(db.or_(TestRun.scope == f'page:{page.slug}', TestRun.scope == 'all'))
                     .order_by(TestRun.finished_at.desc()).limit(30).all())

        run_history = []
        for r in reversed(runs_done):
            res = list(r.results.filter(TestResult.case_id.in_(case_ids)))
            if res:
                pct = round(100 * sum(1 for x in res if x.status == 'passed') / len(res))
                run_history.append({'run_id': r.id, 'pct': pct,
                                    'at': r.finished_at.strftime('%d/%m %H:%M') if r.finished_at else ''})

        passed   = sum(1 for c in cases if c.last_status == 'passed')
        failed   = sum(1 for c in cases if c.last_status in ('failed', 'error'))
        untested = sum(1 for c in cases if c.last_status is None)
        cur_pct  = round(100 * passed / total) if total else 0
        page_stats.append(dict(page=page, total=total, passed=passed, failed=failed,
                               untested=untested, cur_pct=cur_pct, run_history=run_history))

    all_cases = TestCase.query.all()
    total_all    = len(all_cases)
    passed_all   = sum(1 for c in all_cases if c.last_status == 'passed')
    failed_all   = sum(1 for c in all_cases if c.last_status in ('failed', 'error'))
    untested_all = sum(1 for c in all_cases if c.last_status is None)
    global_pct   = round(100 * passed_all / total_all) if total_all else 0

    # Patchs — synthèse + comptage par page + catégories
    all_patches = TestPatch.query.order_by(TestPatch.created_at.desc()).all()
    patches_by_slug = {}
    for p in all_patches:
        if p.page_slug:
            patches_by_slug[p.page_slug] = patches_by_slug.get(p.page_slug, 0) + 1
    for s in page_stats:
        s['n_patches'] = patches_by_slug.get(s['page'].slug, 0)
    patch_count    = len(all_patches)
    real_bug_count = sum(1 for p in all_patches if p.was_real_bug)
    patch_cats     = _patch_category_counts(all_patches)
    recent_patches = [_patch_to_dict(p) for p in all_patches[:6]]

    # Pages les plus fragiles (taux le plus bas, hors 100 %)
    weak_pages = sorted([s for s in page_stats if s['cur_pct'] < 100 and s['total']],
                        key=lambda s: s['cur_pct'])[:5]

    _expire_stale_runs()
    active_run  = TestRun.query.filter_by(status='running').order_by(TestRun.started_at.desc()).first()
    recent_runs = _recent_runs(6)

    return render_template('test_panel/panel.html',
                           page_stats=page_stats, total_all=total_all,
                           passed_all=passed_all, failed_all=failed_all,
                           untested_all=untested_all, global_pct=global_pct,
                           patch_count=patch_count, real_bug_count=real_bug_count,
                           patch_cats=patch_cats, recent_patches=recent_patches,
                           weak_pages=weak_pages, recent_runs=recent_runs,
                           active_run=active_run)


@test_panel_bp.route('/page/<slug>')
def page_detail(slug):
    page  = TestPage.query.filter_by(slug=slug).first_or_404()
    cases = list(page.cases)
    case_ids = [c.id for c in cases]

    runs_done = (TestRun.query
                 .filter(TestRun.status == 'done')
                 .filter(db.or_(TestRun.scope == f'page:{slug}', TestRun.scope == 'all'))
                 .order_by(TestRun.finished_at.desc()).limit(30).all())

    run_history = []
    for r in reversed(runs_done):
        res = list(r.results.filter(TestResult.case_id.in_(case_ids)))
        if res:
            pct = round(100 * sum(1 for x in res if x.status == 'passed') / len(res))
            run_history.append({'run_id': r.id, 'pct': pct,
                                'at': r.finished_at.strftime('%d/%m %H:%M') if r.finished_at else ''})

    case_history = {}
    for c in cases:
        rows = list(c.results.order_by(TestResult.ran_at.asc()).limit(30))
        case_history[c.id] = [{'status': r.status, 'run_id': r.run_id} for r in rows]

    classes = {}
    for c in cases:
        classes.setdefault(c.class_name or 'Tests', []).append(c)

    # Patchs concernant cette page (par node_id de ses cas OU par page_slug)
    page_node_ids = [c.node_id for c in cases]
    patches = _patches_for_nodes(page_node_ids)
    for p in TestPatch.query.filter_by(page_slug=slug).all():
        if p not in patches:
            patches.append(p)
    patched_nodes = set()
    for p in patches:
        patched_nodes |= set(p.node_id_list)

    total    = len(cases)
    passed   = sum(1 for c in cases if c.last_status == 'passed')
    failed   = sum(1 for c in cases if c.last_status in ('failed', 'error'))
    untested = sum(1 for c in cases if c.last_status is None)
    cur_pct  = round(100 * passed / total) if total else 0

    _expire_stale_runs()
    active_run = TestRun.query.filter_by(status='running').order_by(TestRun.started_at.desc()).first()
    return render_template('test_panel/page.html', page=page, classes=classes,
                           run_history=run_history, case_history=case_history,
                           patches=patches, patched_nodes=patched_nodes,
                           total=total, passed=passed, failed=failed,
                           untested=untested, cur_pct=cur_pct,
                           active_run=active_run)


@test_panel_bp.route('/case/<int:case_id>')
def case_detail(case_id):
    case    = db.session.get(TestCase, case_id)
    if not case:
        return 'Not found', 404
    results = list(case.results.order_by(TestResult.ran_at.asc()).limit(40))
    history = [{'status': r.status, 'duration': round(r.duration or 0, 3),
                'run_id': r.run_id,
                'at': r.ran_at.strftime('%d/%m %H:%M') if r.ran_at else ''}
               for r in results]
    last = results[-1] if results else None
    patches = _patches_for_nodes([case.node_id])
    return render_template('test_panel/case.html', case=case,
                           history=history, last_result=last, patches=patches)


@test_panel_bp.route('/patches')
def patches_page():
    """Page dédiée à tous les patchs (correctifs tracés)."""
    all_patches = TestPatch.query.order_by(TestPatch.fixed_at.desc(),
                                           TestPatch.created_at.desc()).all()
    slug_to_title = {p.slug: p.title for p in TestPage.query.all()}
    patches = []
    for p in all_patches:
        d = _patch_to_dict(p)
        d['page_title'] = slug_to_title.get(p.page_slug, p.page_slug or '—')
        d['n_tests'] = len(p.node_id_list)
        patches.append(d)
    cats = _patch_category_counts(all_patches)
    summary = {
        'total':     len(all_patches),
        'real_bugs': sum(1 for p in all_patches if p.was_real_bug),
        'test_only': sum(1 for p in all_patches if not p.was_real_bug),
        'tests_fixed': sum(len(p.node_id_list) for p in all_patches),
        'files':     len({f for p in all_patches for f in p.files_list}),
    }
    return render_template('test_panel/patches.html',
                           patches=patches, cats=cats, summary=summary)


_JOURNAL_FILE = _TESTS_DIR / 'journal.json'


def _load_journal():
    """Lit le carnet de bord versionné (tests/journal.json)."""
    data = {'plan': {}, 'entries': []}
    if not _JOURNAL_FILE.exists():
        return data
    try:
        loaded = json.loads(_JOURNAL_FILE.read_text(encoding='utf-8'))
        if isinstance(loaded, dict):
            data['plan'] = loaded.get('plan', {}) or {}
            data['entries'] = loaded.get('entries', []) or []
    except Exception:
        pass
    return data


@test_panel_bp.route('/journal')
def journal_page():
    """Carnet de bord de la routine : plan en cours + journal des exécutions."""
    data = _load_journal()
    plan = data['plan']
    steps = plan.get('steps', []) or []
    for s in steps:
        if s.get('status') == 'done':
            s['_pct'] = 100
        else:
            try:
                s['_pct'] = max(0, min(100, int(s.get('progress', 0) or 0)))
            except (TypeError, ValueError):
                s['_pct'] = 0
    plan_pct  = round(sum(s['_pct'] for s in steps) / len(steps)) if steps else 0
    steps_done = sum(1 for s in steps if s.get('status') == 'done')

    # Les entrées sont stockées les plus récentes en premier (le helper les
    # insère en tête) — on garde l'ordre du fichier.
    entries = data['entries']
    agg = {
        'runs':        len(entries),
        'new_tests':   sum(int(e.get('new_tests') or 0) for e in entries),
        'tests_fixed': sum(int(e.get('tests_fixed') or 0) for e in entries),
        'patches':     sum(int(e.get('patches') or 0) for e in entries),
    }
    return render_template('test_panel/journal.html', plan=plan, steps=steps,
                           plan_pct=plan_pct, steps_done=steps_done,
                           entries=entries, agg=agg)


@test_panel_bp.route('/run/all', methods=['POST'])
def run_all():
    return jsonify({'run_id': _start_run('all')})


@test_panel_bp.route('/run/page/<slug>', methods=['POST'])
def run_page(slug):
    TestPage.query.filter_by(slug=slug).first_or_404()
    return jsonify({'run_id': _start_run(f'page:{slug}')})


@test_panel_bp.route('/run/case/<int:case_id>', methods=['POST'])
def run_case(case_id):
    db.session.get(TestCase, case_id) or abort(404)
    return jsonify({'run_id': _start_run(f'case:{case_id}')})


@test_panel_bp.route('/stream/<int:run_id>')
def stream_output(run_id):
    import time, json as _json

    def _gen():
        sent = 0
        for _ in range(3000):          # max ~5 min
            with _runs_lock:
                data = _runs.get(run_id)
            if data is None:
                # Thread pas encore initialisé — attendre
                time.sleep(0.1)
                continue
            with _runs_lock:
                lines = list(data['lines'])
                done  = data['done']
            while sent < len(lines):
                yield f"data: {_json.dumps(lines[sent].rstrip(chr(10)))}\n\n"
                sent += 1
            if done and sent >= len(lines):
                yield f"data: {_json.dumps('[DONE]')}\n\n"
                return
            time.sleep(0.1)

    return Response(stream_with_context(_gen()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@test_panel_bp.route('/admin/reset-stale', methods=['POST'])
def reset_stale():
    """Force-expire all stale 'running' runs. Useful after a crash."""
    stale = TestRun.query.filter_by(status='running').all()
    for r in stale:
        r.status = 'done'
    db.session.commit()
    return jsonify({'expired': len(stale)})


# ── API JSON pour Optiq Hub ───────────────────────────────────────────────────
# Le hub affiche la fiabilité par page et le détail d'une page ; il lui faut du
# JSON, pas les gabarits du panel. Ces routes ne servent qu'à lire.

def _fiabilite(cases):
    """Part de cas au vert, sur ceux qui ont déjà tourné.

    Les cas jamais exécutés sont EXCLUS du calcul : les compter comme des
    échecs ferait chuter le score d'une page simplement parce qu'on ne l'a
    pas encore jouée, ce qui induirait en erreur.
    """
    joues = [c for c in cases if c.last_status in ('passed', 'failed', 'error')]
    if not joues:
        return None, 0, 0, 0
    verts = sum(1 for c in joues if c.last_status == 'passed')
    return round(100 * verts / len(joues)), verts, len(joues) - verts, len(joues)


@test_panel_bp.route('/api/pages')
def api_pages():
    sync_tests_to_db()
    pages = TestPage.query.order_by(TestPage.file_name).all()
    sortie = []
    for page in pages:
        cases = list(page.cases)
        pct, verts, rouges, joues = _fiabilite(cases)
        dernier = max((c.last_ran_at for c in cases if c.last_ran_at), default=None)
        sortie.append({
            'slug': page.slug,
            'titre': page.title,
            'description': page.description,
            'fichier': page.file_name,
            'marqueur': page.marker,
            'total': len(cases),
            'joues': joues,
            'verts': verts,
            'rouges': rouges,
            'fiabilite': pct,                     # None = jamais joué
            'dernier': dernier.isoformat() if dernier else None,
        })
    return jsonify({'pages': sortie, 'total_cas': sum(p['total'] for p in sortie)})


@test_panel_bp.route('/api/page/<slug>')
def api_page(slug):
    page = TestPage.query.filter_by(slug=slug).first_or_404()
    cases = list(page.cases)
    pct, verts, rouges, joues = _fiabilite(cases)
    return jsonify({
        'slug': page.slug,
        'titre': page.title,
        'description': page.description,
        'fichier': page.file_name,
        'marqueur': page.marker,
        'fiabilite': pct,
        'verts': verts,
        'rouges': rouges,
        'joues': joues,
        'total': len(cases),
        'cas': [{
            'id': c.id,
            'nom': c.display_name or c.name,
            'classe': c.class_name,
            'description': c.description,
            'statut': c.last_status,
            'quand': c.last_ran_at.isoformat() if c.last_ran_at else None,
        } for c in cases],
    })


@test_panel_bp.route('/api/etat')
def api_etat():
    """Ce que le hub doit savoir avant de proposer un lancement."""
    sync_tests_to_db()
    en_cours = TestRun.query.filter_by(status='running').order_by(
        TestRun.started_at.desc()).first()
    dernier = TestRun.query.filter_by(status='done').order_by(
        TestRun.finished_at.desc()).first()
    return jsonify({
        'suite_presente': _TESTS_DIR.exists() and any(_TESTS_DIR.glob('test_*.py')),
        'pages': TestPage.query.count(),
        'cas': TestCase.query.count(),
        'en_cours': ({'id': en_cours.id, 'scope': en_cours.scope,
                      'depuis': en_cours.started_at.isoformat() if en_cours.started_at else None}
                     if en_cours else None),
        'dernier': ({'id': dernier.id, 'scope': dernier.scope,
                     'fin': dernier.finished_at.isoformat() if dernier.finished_at else None}
                    if dernier else None),
    })


@test_panel_bp.route('/global/stats')
def global_stats():
    from collections import Counter
    period = request.args.get('period', 'day')
    now = datetime.utcnow()
    if period == 'hour':
        since = now - timedelta(hours=1)
        time_fmt = '%H:%M'
    elif period == 'month':
        since = now - timedelta(days=30)
        time_fmt = '%d/%m'
    else:
        since = now - timedelta(hours=24)
        time_fmt = '%H:%M'

    # Chart points: runs finished in the selected period
    period_runs = (TestRun.query
                   .filter(TestRun.status == 'done', TestRun.finished_at >= since)
                   .order_by(TestRun.finished_at.asc()).all())
    chart_points = []
    for r in period_runs:
        res_list = list(r.results)
        total = len(res_list)
        if not total:
            continue
        passed = sum(1 for x in res_list if x.status == 'passed')
        chart_points.append({
            't':      r.finished_at.strftime(time_fmt),
            'pct':    round(100 * passed / total),
            'run_id': r.id,
            'passed': passed,
            'total':  total,
        })

    # Recent runs (last 20, all time)
    recent_runs = _recent_runs(20)

    # Global summary stats
    total_runs  = TestRun.query.filter(TestRun.status == 'done').count()
    all_res     = TestResult.query.all()
    total_res   = len(all_res)
    passed_res  = sum(1 for x in all_res if x.status == 'passed')
    overall_pct = round(100 * passed_res / total_res) if total_res else 0

    dur_runs = TestRun.query.filter(
        TestRun.status == 'done',
        TestRun.started_at.isnot(None),
        TestRun.finished_at.isnot(None)
    ).all()
    durs    = [(r.finished_at - r.started_at).total_seconds() for r in dur_runs]
    avg_dur = round(sum(durs) / len(durs), 1) if durs else None

    fail_counts = Counter(
        x.case_id for x in TestResult.query.filter(TestResult.status.in_(['failed', 'error'])).all()
    )
    most_failing = None
    if fail_counts:
        top_cid, top_cnt = fail_counts.most_common(1)[0]
        tc = db.session.get(TestCase, top_cid)
        if tc:
            most_failing = {'name': tc.display_name or tc.name, 'fail_count': top_cnt}

    # Patchs récents (traçabilité des correctifs)
    all_patches    = TestPatch.query.order_by(TestPatch.created_at.desc()).all()
    recent_patches = [_patch_to_dict(p) for p in all_patches[:12]]
    patch_summary  = {
        'total':      len(all_patches),
        'real_bugs':  sum(1 for p in all_patches if p.was_real_bug),
        'test_only':  sum(1 for p in all_patches if not p.was_real_bug),
        'by_category': _patch_category_counts(all_patches),
    }

    return jsonify({
        'period':         period,
        'chart_points':   chart_points,
        'recent_runs':    recent_runs,
        'recent_patches': recent_patches,
        'patch_summary':  patch_summary,
        'summary': {
            'total_runs':     total_runs,
            'overall_pct':    overall_pct,
            'avg_duration_s': avg_dur,
            'most_failing':   most_failing,
        },
    })


@test_panel_bp.route('/run/<int:run_id>/status')
def run_status(run_id):
    # Lecture directe sqlite3 — évite tout problème de cache de session SQLAlchemy
    db_url = current_app.config['SQLALCHEMY_DATABASE_URI']
    if db_url.startswith('sqlite'):
        import sqlite3 as _sq
        raw = db_url[len('sqlite:///'):].split('?')[0]
        try:
            conn = _sq.connect(raw, timeout=10)
            run_row = conn.execute(
                "SELECT status, finished_at FROM test_runs WHERE id=?", (run_id,)
            ).fetchone()
            if not run_row:
                conn.close()
                return jsonify({'status': 'unknown'}), 404
            total  = conn.execute(
                "SELECT COUNT(*) FROM test_results WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            passed = conn.execute(
                "SELECT COUNT(*) FROM test_results WHERE run_id=? AND status='passed'", (run_id,)
            ).fetchone()[0]
            conn.close()
            return jsonify({
                'status':      run_row[0],
                'total':       total,
                'passed':      passed,
                'pct':         round(100 * passed / total) if total else 0,
                'finished_at': run_row[1],
            })
        except Exception as e:
            return jsonify({'status': 'error', 'detail': str(e)}), 500
    else:
        # PostgreSQL — SQLAlchemy normal
        run = db.session.get(TestRun, run_id)
        if not run:
            return jsonify({'status': 'unknown'}), 404
        results = list(run.results)
        total   = len(results)
        passed  = sum(1 for r in results if r.status == 'passed')
        return jsonify({
            'status':      run.status,
            'total':       total,
            'passed':      passed,
            'pct':         round(100 * passed / total) if total else 0,
            'finished_at': run.finished_at.isoformat() if run.finished_at else None,
        })


# ── One-shot admin: deep clone of an entity (all related data) ───────────────

@test_panel_bp.route('/admin/clone_entity', methods=['POST'])
def admin_clone_entity():
    from Code.models.models import (
        Entity, Activities, Role, Link, Task, Tool, Competency,
        Savoir, SavoirFaire, Aptitude, Softskill, Constraint, Data,
        Performance, activity_roles, task_roles, task_tools
    )
    from sqlalchemy import text

    data_req = request.get_json(silent=True) or {}
    source_id = int(data_req.get('source_id', 1))
    target_id = int(data_req.get('target_id'))

    try:
        source = Entity.query.get_or_404(source_id)
        target = Entity.query.get_or_404(target_id)

        # Clean any partial data already in target (from previous failed attempts)
        for act in Activities.query.filter_by(entity_id=target_id).all():
            db.session.delete(act)
        for r in Role.query.filter_by(entity_id=target_id).all():
            db.session.delete(r)
        for t in Tool.query.filter_by(entity_id=target_id).all():
            db.session.delete(t)
        for lk in Link.query.filter_by(entity_id=target_id).all():
            db.session.delete(lk)
        for d in Data.query.filter_by(entity_id=target_id).all():
            db.session.delete(d)
        db.session.flush()

        role_map     = {}
        tool_map     = {}
        activity_map = {}
        task_map     = {}
        data_map     = {}
        link_map     = {}

        # 1. Roles
        for r in Role.query.filter_by(entity_id=source_id).all():
            nr = Role(entity_id=target_id, name=r.name,
                      onboarding_plan=r.onboarding_plan,
                      mission_generale=r.mission_generale)
            db.session.add(nr)
            db.session.flush()
            role_map[r.id] = nr.id

        # 2. Tools
        for t in Tool.query.filter_by(entity_id=source_id).all():
            nt = Tool(entity_id=target_id, name=t.name)
            db.session.add(nt)
            db.session.flush()
            tool_map[t.id] = nt.id

        # 3. Activities + children
        for act in Activities.query.filter_by(entity_id=source_id).all():
            nact = Activities(
                entity_id=target_id, shape_id=act.shape_id,
                name=act.name, description=act.description,
                is_result=act.is_result, shape_subtype=act.shape_subtype,
                duration_minutes=act.duration_minutes, delay_minutes=act.delay_minutes,
            )
            db.session.add(nact)
            db.session.flush()
            activity_map[act.id] = nact.id

            for c in act.competencies:
                db.session.add(Competency(description=c.description, activity_id=nact.id))
            for s in act.savoirs:
                db.session.add(Savoir(description=s.description, activity_id=nact.id))
            for sf in act.savoir_faires:
                db.session.add(SavoirFaire(description=sf.description, activity_id=nact.id))
            for ap in act.aptitudes:
                db.session.add(Aptitude(description=ap.description, activity_id=nact.id))
            for sk in act.softskills:
                db.session.add(Softskill(habilete=sk.habilete, niveau=sk.niveau,
                                         justification=sk.justification, activity_id=nact.id))
            for cn in act.constraints:
                db.session.add(Constraint(description=cn.description, activity_id=nact.id))

            for tk in act.tasks:
                ntk = Task(name=tk.name, description=tk.description, order=tk.order,
                           activity_id=nact.id, duration_minutes=tk.duration_minutes,
                           delay_minutes=tk.delay_minutes)
                db.session.add(ntk)
                db.session.flush()
                task_map[tk.id] = ntk.id

        db.session.flush()

        # 4. activity_roles via raw SQL
        if activity_map:
            old_act_ids = list(activity_map.keys())
            rows = db.session.execute(
                text("SELECT activity_id, role_id, status FROM activity_roles WHERE activity_id = ANY(:ids)"),
                {'ids': old_act_ids}
            ).fetchall()
            for row in rows:
                new_act  = activity_map.get(row[0])
                new_role = role_map.get(row[1])
                if new_act and new_role:
                    db.session.execute(
                        text("INSERT INTO activity_roles (activity_id, role_id, status) VALUES (:a, :r, :s) ON CONFLICT DO NOTHING"),
                        {'a': new_act, 'r': new_role, 's': row[2]}
                    )

        # 5. task_roles via raw SQL
        if task_map:
            old_task_ids = list(task_map.keys())
            rows = db.session.execute(
                text("SELECT task_id, role_id, status FROM task_roles WHERE task_id = ANY(:ids)"),
                {'ids': old_task_ids}
            ).fetchall()
            for row in rows:
                new_task = task_map.get(row[0])
                new_role = role_map.get(row[1])
                if new_task and new_role:
                    db.session.execute(
                        text("INSERT INTO task_roles (task_id, role_id, status) VALUES (:t, :r, :s) ON CONFLICT DO NOTHING"),
                        {'t': new_task, 'r': new_role, 's': row[2]}
                    )

        # 6. task_tools via raw SQL
        if task_map:
            rows = db.session.execute(
                text("SELECT task_id, tool_id FROM task_tools WHERE task_id = ANY(:ids)"),
                {'ids': old_task_ids}
            ).fetchall()
            for row in rows:
                new_task = task_map.get(row[0])
                new_tool = tool_map.get(row[1])
                if new_task and new_tool:
                    db.session.execute(
                        text("INSERT INTO task_tools (task_id, tool_id) VALUES (:t, :tl) ON CONFLICT DO NOTHING"),
                        {'t': new_task, 'tl': new_tool}
                    )

        # 7. Data shapes
        for d in Data.query.filter_by(entity_id=source_id).all():
            nd = Data(
                entity_id=target_id,
                shape_id=f"{d.shape_id}_e{target_id}" if d.shape_id else None,
                name=d.name, type=d.type, description=d.description, layer=d.layer,
            )
            db.session.add(nd)
            db.session.flush()
            data_map[d.id] = nd.id

        # 8. Links
        for lk in Link.query.filter_by(entity_id=source_id).all():
            nlk = Link(
                entity_id=target_id,
                source_activity_id=activity_map.get(lk.source_activity_id) if lk.source_activity_id else None,
                source_data_id    =data_map.get(lk.source_data_id)         if lk.source_data_id     else None,
                target_activity_id=activity_map.get(lk.target_activity_id) if lk.target_activity_id else None,
                target_data_id    =data_map.get(lk.target_data_id)         if lk.target_data_id     else None,
                type=lk.type, description=lk.description,
                cross_carto_liaison_id=lk.cross_carto_liaison_id,
                cross_carto_label=lk.cross_carto_label,
                choice_label=lk.choice_label,
            )
            db.session.add(nlk)
            db.session.flush()
            link_map[lk.id] = nlk.id
            if lk.performance:
                db.session.add(Performance(name=lk.performance.name,
                                           description=lk.performance.description,
                                           link_id=nlk.id))

        db.session.commit()
        return jsonify({'ok': True, 'source': source.name, 'target': target.name,
                        'roles': len(role_map), 'tools': len(tool_map),
                        'activities': len(activity_map), 'tasks': len(task_map),
                        'data_shapes': len(data_map), 'links': len(link_map)})

    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


# ── One-shot admin: transfer null-owner entities + duplicate entité de base ──

@test_panel_bp.route('/admin/migrate_entities', methods=['GET', 'POST'])
def admin_migrate_entities():
    """
    GET  → dry-run: shows what would happen
    POST → executes the migration
    """
    from Code.models.models import Entity, User
    from datetime import datetime

    MAEL_EMAIL   = 'mael.pierre.girardin@icloud.com'
    HUBERT_EMAIL = 'h.grandjean@afdec.fr'

    mael   = User.query.filter_by(email=MAEL_EMAIL).first()
    hubert = User.query.filter_by(email=HUBERT_EMAIL).first()

    if not mael:
        return jsonify({'error': f'User not found: {MAEL_EMAIL}'}), 404
    if not hubert:
        return jsonify({'error': f'User not found: {HUBERT_EMAIL}'}), 404

    # Entités sans owner (anciennement "test test")
    orphan_entities = Entity.query.filter_by(owner_id=None).all()

    # Entité de base : chercher par nom
    base_entity = (
        Entity.query.filter(Entity.name.ilike('%entit%base%')).first()
        or Entity.query.filter(Entity.name.ilike('%base%')).first()
    )

    report = {
        'mael_id':        mael.id,
        'hubert_id':      hubert.id,
        'orphans':        [{'id': e.id, 'name': e.name} for e in orphan_entities],
        'base_entity':    {'id': base_entity.id, 'name': base_entity.name} if base_entity else None,
        'dry_run':        request.method == 'GET',
    }

    if request.method == 'POST':
        # 1. Rattacher les entités orphelines à Maël
        for e in orphan_entities:
            e.owner_id = mael.id

        # 2. Dupliquer l'entité de base pour Hubert
        new_entity = None
        if base_entity:
            new_entity = Entity(
                name            = base_entity.name + ' — Hubert',
                description     = base_entity.description,
                owner_id        = hubert.id,
                svg_filename    = base_entity.svg_filename,
                svg_content     = base_entity.svg_content,
                vsdx_filename   = base_entity.vsdx_filename,
                optiqcarto_data = base_entity.optiqcarto_data,
                is_active       = False,
                created_at      = datetime.utcnow(),
                updated_at      = datetime.utcnow(),
            )
            db.session.add(new_entity)

        db.session.commit()
        report['done']       = True
        report['new_entity_id'] = new_entity.id if new_entity else None

    return jsonify(report)
