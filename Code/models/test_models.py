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
