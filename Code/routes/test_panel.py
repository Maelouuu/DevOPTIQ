import ast
import os
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from flask import (Blueprint, Response, jsonify, render_template, request,
                   stream_with_context, current_app)

from Code.extensions import db
from Code.models.test_models import TestCase, TestPage, TestResult, TestRun

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
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        class_doc = ast.get_docstring(node) or ''
        for item in node.body:
            if not isinstance(item, ast.FunctionDef) or not item.name.startswith('test_'):
                continue
            doc = ast.get_docstring(item) or class_doc
            display = item.name[5:].replace('_', ' ').capitalize()
            cases.append({
                'node_id':      f"tests/{fpath.name}::{node.name}::{item.name}",
                'class_name':   node.name,
                'name':         item.name,
                'display_name': display,
                'description':  doc,
            })

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
            base += [f'tests/{case.page.file_name}::{case.class_name}::{case.name}']
    return base


def _parse_xml(xml_path: str, run_id: int):
    """Legacy: uses Flask's scoped session (kept for compatibility)."""
    _parse_xml_session(xml_path, run_id, db.session)
    db.session.flush()


def _parse_xml_session(xml_path: str, run_id: int, session):
    """Parse JUnit XML and write results using the provided SQLAlchemy session."""
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return
    now = datetime.utcnow()
    for tc in root.findall('.//testcase'):
        classname = tc.get('classname', '')
        name      = tc.get('name', '')
        parts     = classname.split('.')
        # reconstruct node_id: tests/test_01_auth.py::TestClass::test_name
        file_mod  = next((p for p in parts if p.startswith('test_')), '')
        class_nm  = parts[-1] if len(parts) > 1 else ''
        node_id   = f"tests/{file_mod}.py::{class_nm}::{name}" if file_mod else ''
        case      = session.query(TestCase).filter_by(node_id=node_id).first() if node_id else None

        failure = tc.find('failure')
        error   = tc.find('error')
        if failure is not None:
            status  = 'failed'
            message = (failure.get('message', '') + '\n' + (failure.text or ''))[:3000]
        elif error is not None:
            status  = 'error'
            message = (error.get('message', '') + '\n' + (error.text or ''))[:3000]
        else:
            status  = 'passed'
            message = ''

        duration = float(tc.get('time', 0) or 0)
        if case:
            session.add(TestResult(run_id=run_id, case_id=case.id,
                                   status=status, duration=duration,
                                   message=message, ran_at=now))
            case.last_status = status
            case.last_ran_at = now


def _run_thread(run_id: int, scope: str, app):
    import traceback

    def emit(line: str):
        with _runs_lock:
            if run_id in _runs:
                _runs[run_id]['lines'].append(line)

    with app.app_context():
        fd, xml_path = tempfile.mkstemp(suffix='.xml', prefix=f'trun_{run_id}_')
        os.close(fd)
        args = _build_args(scope, xml_path)
        emit(f"$ pytest {' '.join(args[3:])}\n")

        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    cwd=str(_PROJECT_ROOT), text=True, bufsize=1)
            for line in proc.stdout:
                emit(line)
            proc.wait()
        except Exception as e:
            emit(f'\n[ERROR lors du lancement] {e}\n')

        # Créer un engine dédié au thread, indépendant du pool Flask-SQLAlchemy
        from sqlalchemy import create_engine as _create_engine
        from sqlalchemy.orm import Session as _Session

        db_url = app.config['SQLALCHEMY_DATABASE_URI']
        connect_args = {}
        if db_url.startswith('sqlite'):
            connect_args = {'timeout': 30, 'check_same_thread': False}
        _engine = _create_engine(db_url, connect_args=connect_args)

        try:
            # S'assurer que les tables existent dans cette connexion
            from Code.models.test_models import TestPage as _TP, TestCase as _TC, TestRun as _TR, TestResult as _TRs
            for _m in (_TP, _TC, _TR, _TRs):
                _m.__table__.create(_engine, checkfirst=True)

            with _Session(_engine) as session:
                run = session.get(TestRun, run_id)
                if run:
                    run.finished_at = datetime.utcnow()
                    run.status = 'done'
                    if os.path.exists(xml_path):
                        _parse_xml_session(xml_path, run_id, session)
                        try:
                            os.unlink(xml_path)
                        except OSError:
                            pass
                    session.commit()
                    emit(f'\n[OK] Résultats sauvegardés en base (run #{run_id})\n')
        except Exception:
            tb = traceback.format_exc()
            emit(f'\n[DB ERROR] {tb}\n')
            print(f'[test_panel] DB error in run {run_id}:\n{tb}', file=sys.stderr)
        finally:
            _engine.dispose()

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

@test_panel_bp.before_request
def _auto_sync():
    try:
        # Recrée les tables si elles ont disparu (SQLite local, subprocess pytest, etc.)
        for model in (TestPage, TestCase, TestRun, TestResult):
            model.__table__.create(db.engine, checkfirst=True)
        sync_tests_to_db()
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
    total_all  = len(all_cases)
    passed_all = sum(1 for c in all_cases if c.last_status == 'passed')
    global_pct = round(100 * passed_all / total_all) if total_all else 0
    _expire_stale_runs()
    active_run = TestRun.query.filter_by(status='running').order_by(TestRun.started_at.desc()).first()

    return render_template('test_panel/panel.html',
                           page_stats=page_stats, total_all=total_all,
                           passed_all=passed_all, global_pct=global_pct,
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

    _expire_stale_runs()
    active_run = TestRun.query.filter_by(status='running').order_by(TestRun.started_at.desc()).first()
    return render_template('test_panel/page.html', page=page, classes=classes,
                           run_history=run_history, case_history=case_history,
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
    return render_template('test_panel/case.html', case=case,
                           history=history, last_result=last)


@test_panel_bp.route('/run/all', methods=['POST'])
def run_all():
    return jsonify({'run_id': _start_run('all')})


@test_panel_bp.route('/run/page/<slug>', methods=['POST'])
def run_page(slug):
    TestPage.query.filter_by(slug=slug).first_or_404()
    return jsonify({'run_id': _start_run(f'page:{slug}')})


@test_panel_bp.route('/run/case/<int:case_id>', methods=['POST'])
def run_case(case_id):
    db.session.get(TestCase, case_id) or (lambda: (_ for _ in ()).throw(Exception()))()
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


@test_panel_bp.route('/run/<int:run_id>/status')
def run_status(run_id):
    run     = db.session.get(TestRun, run_id)
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
