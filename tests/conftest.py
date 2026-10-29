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

# ⚠️ AUCUNE clé IA pendant la suite, quelle que soit la machine.
#
# Des dizaines de tests vérifient le comportement SANS clé (repli, 500 explicite,
# champ `source` de secours) ; ils s'appuyaient sur le fait qu'un poste de
# développement n'en a pas. Depuis que le panel rejoue la suite SUR l'instance,
# elle tourne là où les clés SONT présentes dans l'environnement : quinze de ces
# tests viraient au rouge, sur cinq fichiers, pour une raison qui n'a rien à voir
# avec le code — et faussaient le taux de fiabilité que le panel existe pour
# montrer. Certains fichiers faisaient déjà ce `delenv` chacun de leur côté ; on
# le fait une fois pour toutes, ici, avant la création de l'application.
#
# Les tests qui vérifient le chemin AVEC clé ne passent pas par l'environnement :
# ils remplacent `get_openai_key` par une valeur factice.
for _cle_ia in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_KEY"):
    os.environ.pop(_cle_ia, None)


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
            "pool_pre_ping": True,
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

    # owner_id must be set so Entity.get_active() finds the entity for the test user
    entity.owner_id = user.id
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


@pytest.fixture(scope="session", autouse=True)
def sessions_de_test_sans_empreinte(app):
    """⚠️ TRENTE fichiers de tests posent `session['user_id']` à la main, et
    une douzaine de helpers y REMPLACENT `user_id` sans toucher à l'empreinte
    `pwd_at` qu'un vrai login a laissée — la session se retrouve alors avec
    deux moitiés qui ne parlent pas du même compte.

    La porte des sessions périmées les met dehors, et le symptôme ne désigne
    jamais sa cause : on lit un 302 vers /login, ou un 403 parce que
    `_current_user()` est devenu None, ou un `KeyError` sur une réponse JSON
    qui n'en est plus une — dans un fichier qui ne parle pas de mots de passe.
    Mesuré : huit tests rouges sur cinq fichiers au premier passage, un
    neuvième au second, tous sans rapport avec le sujet.

    **La concession vit donc DANS LE DÉCOR, jamais dans l'application.** La
    porte ne mord que là où un test la met à l'épreuve, en posant
    `PWD_SESSION_STRICTE` (fixture `porte_stricte` de `test_117`). Partout
    ailleurs elle laisse passer.

    ⚠️ Ce n'est PAS « la garde n'est pas contrôlée » : `test_117` l'éprouve au
    niveau HTTP avec le levier posé, et la règle elle-même est vérifiée dans
    les deux sens directement sur `regle_session_perimee`, que ce
    remplacement ne touche pas.
    """
    from flask import current_app, has_app_context
    from Code import mot_de_passe as mdp
    vraie = mdp.session_perimee

    def sous_levier(user, valeur_en_session):
        if has_app_context() and current_app.config.get("PWD_SESSION_STRICTE"):
            return vraie(user, valeur_en_session)
        return False

    mdp.session_perimee = sous_levier
    yield
    mdp.session_perimee = vraie


# ⚠️ Depuis la révocation des sessions au changement de mot de passe, une
# session authentifiée porte aussi `pwd_at` (l'empreinte du dernier
# changement). Sans elle, un test qui change le mot de passe du compte de test
# verrait sa propre session fermée au milieu — ce qui est le comportement
# voulu en production, mais pas une façon d'écrire un décor de test.
@pytest.fixture
def auth_client(app, client):
    """Client avec session authentifiée (bypasse le formulaire de login).

    ⚠️ Portée FONCTION, et volontairement : `auth_client` et `client` sont le
    MÊME objet, et plus d'une dizaine de fichiers de tests remettent la session
    à zéro (`sess.clear()`) pour éprouver un accès anonyme. En portée session,
    la connexion n'était posée qu'UNE fois : le premier fichier qui nettoyait
    déconnectait tous les suivants, et leurs tests passaient ou tombaient selon
    l'ORDRE d'exécution. Invisible tant que les routes concernées ne regardaient
    pas la session — dix tests de `test_57_mastery` sont devenus rouges le jour
    où `/mastery/evaluate` a enfin contrôlé qui note qui.

    On ne fait qu'AJOUTER les trois clés d'identité : rien n'est effacé, donc un
    test qui a posé `lang` ou une entité active garde son réglage.
    """
    from Code.models.models import User, Entity

    from Code.extensions import db as _db
    from Code import mot_de_passe as _mdp

    with app.app_context():
        user = User.query.filter_by(email="test@devoptiq.com").first()
        entity = Entity.query.filter_by(name="Entité Test").first()
        # ⚠️ On EXPIRE l'objet avant de lire son horodatage. La session SQLAlchemy
        # des tests est partagée (`scope=session`) : sa carte d'identité peut
        # porter un `password_changed_at` périmé, écrit par un test précédent
        # dans une autre session. L'empreinte posée ici ne correspondrait alors
        # plus à ce que la porte relit en base, et le test se ferait
        # déconnecter pour une raison qui n'est pas la sienne — constaté à
        # l'arbre d'image, où l'ordre d'exécution diffère.
        _db.session.expire(user)
        empreinte = _mdp.empreinte_session(user)

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_email"] = user.email
        sess["pwd_at"] = empreinte
        sess.setdefault("active_entity_id", entity.id)

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
