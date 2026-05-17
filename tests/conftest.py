# tests/conftest.py
"""
Fixtures partagées pour la suite de tests DevOPTIQ.
Crée une application Flask de test avec une base SQLite en mémoire.
"""
import pytest
import tempfile
import os
from werkzeug.security import generate_password_hash

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="session")
def app():
    """Instance Flask configurée pour les tests (SQLite fichier temporaire)."""
    from Code.app import create_app
    from Code.extensions import db as _db

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    test_app = create_app(test_config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
        "MAIL_SUPPRESS_SEND": True,
        "PROPAGATE_EXCEPTIONS": False,
        "SQLALCHEMY_ENGINE_OPTIONS": {
            "connect_args": {"check_same_thread": False},
        },
    })

    with test_app.app_context():
        _db.drop_all()
        _db.create_all()
        _seed_db(_db)
        yield test_app
        _db.session.remove()
        _db.drop_all()

    os.unlink(db_path)


def _seed_db(db):
    """Crée les données de base nécessaires aux tests."""
    from Code.models.models import Entity, User, Activities, Task, Link, Data

    entity = Entity(name="Entité Test", description="Entité de test automatisée")
    db.session.add(entity)
    db.session.flush()

    user = User(
        entity_id=entity.id,
        first_name="Test",
        last_name="User",
        email="test@devoptiq.com",
        password=generate_password_hash("TestPass123!"),
        status="admin",
    )
    db.session.add(user)
    db.session.flush()

    activity = Activities(
        entity_id=entity.id,
        name="Activité Test",
        description="Description de test",
    )
    db.session.add(activity)
    db.session.flush()

    task = Task(
        name="Tâche Test",
        description="Description tâche",
        activity_id=activity.id,
        order=1,
    )
    db.session.add(task)

    # Donnée et lien pour les tests DnD
    data_obj = Data(entity_id=entity.id, name="Donnée Test", type="nourrissante")
    db.session.add(data_obj)
    db.session.flush()

    link = Link(
        entity_id=entity.id,
        source_data_id=data_obj.id,
        target_activity_id=activity.id,
        type="nourrissante",
    )
    db.session.add(link)

    db.session.commit()


@pytest.fixture(scope="session")
def client(app):
    """Client HTTP de test Flask."""
    return app.test_client()


@pytest.fixture(scope="session")
def auth_client(app, client):
    """Client avec session authentifiée (bypasse le formulaire de login)."""
    from Code.models.models import User, Entity

    with app.app_context():
        user = User.query.filter_by(email="test@devoptiq.com").first()
        entity = Entity.query.filter_by(name="Entité Test").first()

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_email"] = user.email
        sess["active_entity_id"] = entity.id

    return client


@pytest.fixture(scope="session")
def ids(app):
    """IDs des objets créés au seed — accessibles depuis tous les tests."""
    from Code.models.models import Entity, User, Activities, Task, Link

    with app.app_context():
        entity = Entity.query.filter_by(name="Entité Test").first()
        user = User.query.filter_by(email="test@devoptiq.com").first()
        activity = Activities.query.filter_by(name="Activité Test").first()
        task = Task.query.filter_by(name="Tâche Test").first()
        link = Link.query.first()

    return {
        "entity_id": entity.id,
        "user_id": user.id,
        "activity_id": activity.id,
        "task_id": task.id,
        "link_id": link.id if link else None,
    }
