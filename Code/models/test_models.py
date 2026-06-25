from datetime import datetime
from Code.extensions import db


class TestPage(db.Model):
    __tablename__ = 'test_pages'
    id          = db.Column(db.Integer, primary_key=True)
    slug        = db.Column(db.String(60), unique=True, nullable=False)
    title       = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    file_name   = db.Column(db.String(120))
    marker      = db.Column(db.String(60))
    cases       = db.relationship(
        'TestCase', backref='page', lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='TestCase.class_name, TestCase.name',
    )


class TestCase(db.Model):
    __tablename__ = 'test_cases'
    id           = db.Column(db.Integer, primary_key=True)
    page_id      = db.Column(db.Integer, db.ForeignKey('test_pages.id'), nullable=False)
    node_id      = db.Column(db.String(400), unique=True, nullable=False)
    class_name   = db.Column(db.String(120))
    name         = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(200))
    description  = db.Column(db.Text)
    last_status  = db.Column(db.String(20))
    last_ran_at  = db.Column(db.DateTime)
    results      = db.relationship(
        'TestResult', backref='case', lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='TestResult.ran_at',
    )


class TestRun(db.Model):
    __tablename__ = 'test_runs'
    id          = db.Column(db.Integer, primary_key=True)
    started_at  = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)
    scope       = db.Column(db.String(200))
    status      = db.Column(db.String(20), default='running')
    results     = db.relationship(
        'TestResult', backref='run', lazy='dynamic',
        cascade='all, delete-orphan',
    )


class TestResult(db.Model):
    __tablename__ = 'test_results'
    id       = db.Column(db.Integer, primary_key=True)
    run_id   = db.Column(db.Integer, db.ForeignKey('test_runs.id'), nullable=False)
    case_id  = db.Column(db.Integer, db.ForeignKey('test_cases.id'), nullable=False)
    status   = db.Column(db.String(20), nullable=False)
    duration = db.Column(db.Float)
    message  = db.Column(db.Text)
    ran_at   = db.Column(db.DateTime, default=datetime.utcnow)


class TestPatch(db.Model):
    """
    Trace d'un correctif appliqué suite à l'échec d'un ou plusieurs tests.

    Source de vérité : le fichier versionné ``tests/patches.json`` (synchronisé
    vers cette table à chaque consultation du panel, comme ``sync_tests_to_db``).
    Permet à Claude — et à la routine de tests — de documenter chaque fix :
    pourquoi le test échouait, s'il y avait une vraie erreur applicative, quelle
    était l'erreur, quand et comment elle a été corrigée.
    """
    __tablename__ = 'test_patches'
    id              = db.Column(db.Integer, primary_key=True)
    patch_uid       = db.Column(db.String(80), unique=True, nullable=False)
    title           = db.Column(db.String(200))      # résumé court du patch
    node_ids        = db.Column(db.Text)             # JSON : node_ids des tests corrigés
    page_slug       = db.Column(db.String(60))       # page principale concernée
    failure_reason  = db.Column(db.Text)             # raison de l'échec du test
    was_real_bug    = db.Column(db.Boolean, default=True)   # y avait-il une vraie erreur ?
    root_cause      = db.Column(db.String(40))       # app_bug | test_isolation | test_quality
    error           = db.Column(db.Text)             # ce qu'était l'erreur (diagnostic)
    fix_description = db.Column(db.Text)             # comment cela a été corrigé
    files_changed   = db.Column(db.Text)             # JSON : fichiers modifiés
    author          = db.Column(db.String(40), default='routine')  # claude | routine
    commit          = db.Column(db.String(60))       # sha du commit (optionnel)
    fixed_at        = db.Column(db.DateTime)         # quand cela a été corrigé
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def node_id_list(self):
        import json
        try:
            return json.loads(self.node_ids or '[]')
        except Exception:
            return []

    @property
    def files_list(self):
        import json
        try:
            return json.loads(self.files_changed or '[]')
        except Exception:
            return []
