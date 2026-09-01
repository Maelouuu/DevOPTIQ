# tests/test_50_accounts_permissions_lang.py
"""
Page Comptes : droits d'accès + langue par défaut.

Règles couvertes :
  - seul un administrateur modifie ou supprime le compte d'un autre ;
  - chacun peut modifier le sien ;
  - créer un compte (formulaire ou import Excel) demande le statut
    administrateur ou gestionnaire de compétences ;
  - la page s'ouvre sur la liste des utilisateurs ;
  - un compte naît en anglais, sauf ceux de DEFAULT_FRENCH_ACCOUNTS.
"""
import json

import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.gestion_compte


# Le client de test est partagé par TOUTE la suite (fixture de portée session).
# Ces tests changent de compte connecté : sans restauration, les modules
# suivants héritent d'une session non-admin et échouent.
@pytest.fixture(scope='module', autouse=True)
def _restaurer_la_session(app, client, ids):
    yield
    with app.app_context():
        from Code.models.models import User
        seed = User.query.filter_by(email='test@devoptiq.com').first()
        uid, umail = seed.id, seed.email
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['user_email'] = umail
        sess['active_entity_id'] = ids['entity_id']


def _mk_user(app, email, status, lang=None):
    from Code.models.models import User
    from Code.extensions import db
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(first_name="T", last_name=email.split("@")[0],
                        email=email, password=generate_password_hash("Test1234!"),
                        status=status)
            db.session.add(user)
        user.status = status
        if lang is not None:
            user.lang = lang
        db.session.commit()
        return user.id


def _as(client, user_id, email):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_email"] = email


@pytest.fixture(scope="module")
def actors(app):
    return {
        "admin": _mk_user(app, "perm.admin@devoptiq.com", "administrateur"),
        "gest":  _mk_user(app, "perm.gest@devoptiq.com", "Gestionnaire de compétences"),
        "rh":    _mk_user(app, "perm.rh@devoptiq.com", "rh"),
        "user":  _mk_user(app, "perm.user@devoptiq.com", "user"),
        "other": _mk_user(app, "perm.other@devoptiq.com", "user"),
    }


# ── Modification d'un compte ──────────────────────────────────────────────────

def test_un_utilisateur_peut_ouvrir_son_propre_compte(app, client, actors):
    _as(client, actors["user"], "perm.user@devoptiq.com")
    res = client.get(f"/comptes/update/{actors['user']}")
    assert res.status_code == 200


def test_un_utilisateur_ne_peut_pas_ouvrir_le_compte_d_un_autre(app, client, actors):
    _as(client, actors["user"], "perm.user@devoptiq.com")
    res = client.get(f"/comptes/update/{actors['other']}")
    assert res.status_code == 302
    assert "error_forbidden_edit" in res.headers["Location"]


def test_un_utilisateur_ne_peut_pas_modifier_le_compte_d_un_autre(app, client, actors):
    _as(client, actors["user"], "perm.user@devoptiq.com")
    res = client.post(f"/comptes/update/{actors['other']}", data={
        "first_name": "Pirate", "last_name": "X", "email": "perm.other@devoptiq.com",
        "status": "administrateur", "role_id": "1",
    })
    assert res.status_code == 302
    assert "error_forbidden_edit" in res.headers["Location"]
    with app.app_context():
        from Code.models.models import User
        assert User.query.get(actors["other"]).first_name != "Pirate"


def test_un_admin_peut_modifier_un_autre_compte(app, client, actors):
    _as(client, actors["admin"], "perm.admin@devoptiq.com")
    res = client.get(f"/comptes/update/{actors['other']}")
    assert res.status_code == 200


def test_un_non_admin_ne_peut_pas_s_auto_promouvoir(app, client, actors):
    """Éditer son propre compte ne doit pas permettre de changer son statut."""
    _as(client, actors["user"], "perm.user@devoptiq.com")
    client.post(f"/comptes/update/{actors['user']}", data={
        "first_name": "T", "last_name": "user", "email": "perm.user@devoptiq.com",
        "status": "administrateur", "role_id": "1",
    })
    with app.app_context():
        from Code.models.models import User
        assert User.query.get(actors["user"]).status == "user"


# ── Suppression ───────────────────────────────────────────────────────────────

def test_seul_un_admin_supprime_un_compte(app, client, actors):
    _as(client, actors["gest"], "perm.gest@devoptiq.com")
    cible = _mk_user(app, "perm.cible@devoptiq.com", "user")
    res = client.post(f"/comptes/delete/{cible}")
    assert res.status_code == 302
    assert "error_forbidden_edit" in res.headers["Location"]
    with app.app_context():
        from Code.models.models import User
        assert User.query.get(cible) is not None


# ── Création de comptes ───────────────────────────────────────────────────────

def _create_payload(email):
    return {"first_name": "N", "last_name": "N", "email": email,
            "password": "Test1234!", "role_id": "1", "status": "user"}


@pytest.mark.parametrize("who,autorise", [("admin", True), ("gest", True),
                                          ("rh", False), ("user", False)])
def test_creation_reservee_admin_et_gestionnaire(app, client, actors, who, autorise):
    _as(client, actors[who], f"perm.{who}@devoptiq.com")
    email = f"nouveau.{who}@devoptiq.com"
    res = client.post("/comptes/create", data=_create_payload(email))
    assert res.status_code == 302
    with app.app_context():
        from Code.models.models import User
        cree = User.query.filter_by(email=email).first() is not None
    assert cree is autorise
    if not autorise:
        assert "error_forbidden_create" in res.headers["Location"]


def test_import_excel_refuse_sans_le_droit(app, client, actors):
    _as(client, actors["user"], "perm.user@devoptiq.com")
    res = client.post("/comptes/import_excel", json={"users": []})
    assert res.status_code == 403


# ── Page d'accueil de la section ──────────────────────────────────────────────

def test_la_page_s_ouvre_sur_la_liste_des_utilisateurs(app, client, actors):
    _as(client, actors["admin"], "perm.admin@devoptiq.com")
    html = client.get("/comptes/").data.decode("utf-8")
    assert '<div id="list-tab" class="tab-pane active">' in html
    assert '<div id="create-tab" class="tab-pane">' in html


def test_les_onglets_de_creation_sont_masques_sans_le_droit(app, client, actors):
    _as(client, actors["user"], "perm.user@devoptiq.com")
    html = client.get("/comptes/").data.decode("utf-8")
    assert 'data-tab="create-tab"' not in html
    assert 'data-tab="import-tab"' not in html
    assert 'data-tab="list-tab"' in html


# ── Langue ────────────────────────────────────────────────────────────────────

def test_un_nouveau_compte_nait_en_anglais(app, client, actors):
    _as(client, actors["admin"], "perm.admin@devoptiq.com")
    client.post("/comptes/create", data=_create_payload("lang.neuf@devoptiq.com"))
    with app.app_context():
        from Code.models.models import User
        assert User.query.filter_by(email="lang.neuf@devoptiq.com").first().lang == "en"


def test_le_compte_afdec_nait_en_francais(app, client, actors):
    from Code.models.models import default_lang_for, DEFAULT_FRENCH_ACCOUNTS
    assert default_lang_for("afdec.enterprise.services@gmail.com") == "fr"
    assert default_lang_for("AFDEC.Enterprise.Services@Gmail.com") == "fr"
    assert default_lang_for("quelqun@araymond.com") == "en"
    assert "afdec.enterprise.services@gmail.com" in DEFAULT_FRENCH_ACCOUNTS


def test_la_connexion_applique_la_langue_du_compte(app, client):
    _mk_user(app, "lang.en@devoptiq.com", "user", lang="en")
    _mk_user(app, "lang.fr@devoptiq.com", "user", lang="fr")
    for email, attendu in (("lang.en@devoptiq.com", "en"), ("lang.fr@devoptiq.com", "fr")):
        client.post("/login", data={"email": email, "password": "Test1234!"})
        with client.session_transaction() as sess:
            assert sess.get("lang") == attendu


def test_le_choix_de_langue_est_persiste_sur_le_compte(app, client, actors):
    _as(client, actors["user"], "perm.user@devoptiq.com")
    res = client.post("/parametres/set_language", json={"lang": "fr"})
    assert res.get_json()["ok"] is True
    with app.app_context():
        from Code.models.models import User
        assert User.query.get(actors["user"]).lang == "fr"
    # remise en anglais pour ne pas polluer les tests suivants
    client.post("/parametres/set_language", json={"lang": "en"})


def test_session_sans_langue_retombe_sur_l_anglais(app, client):
    with client.session_transaction() as sess:
        sess.clear()
    client.get("/login")
    with client.session_transaction() as sess:
        assert sess.get("lang") == "en"


# ── Reconnaissance du statut « gestionnaire de compétences » ──────────────────
# La colonne users.status est un VARCHAR(20) : le libellé complet y arrive
# tronqué. Et selon l'instance il est saisi en français ou en anglais.

@pytest.mark.parametrize("valeur", [
    "manager",                      # valeur canonique des listes déroulantes
    "Gestionnaire de compétences",  # libellé complet
    "gestionnaire de comp",         # tronqué par VARCHAR(20)
    "GESTIONNAIRE",
    "gestionnaire-competences",
    "Competency Manager",
    "competency_manager",
    "skills manager",
])
def test_variantes_reconnues_comme_gestionnaire(valeur):
    from Code.permissions import can_create_accounts_status, is_competency_manager_status
    assert is_competency_manager_status(valeur), valeur
    assert can_create_accounts_status(valeur), valeur


@pytest.mark.parametrize("valeur", ["user", "rh", "", None, "viewer"])
def test_valeurs_qui_ne_donnent_pas_le_droit_de_creer(valeur):
    from Code.permissions import can_create_accounts_status
    assert not can_create_accounts_status(valeur), valeur


@pytest.mark.parametrize("valeur", ["admin", "administrateur", "Administrator", "ADMIN"])
def test_variantes_administrateur(valeur):
    from Code.permissions import is_admin_status, can_create_accounts_status
    assert is_admin_status(valeur), valeur
    assert can_create_accounts_status(valeur), valeur


def test_le_statut_canonique_tient_dans_la_colonne():
    """users.status est un VARCHAR(20) : la valeur proposée doit y entrer."""
    from Code.permissions import COMPETENCY_MANAGER_STATUS
    assert len(COMPETENCY_MANAGER_STATUS) <= 20


def test_un_gestionnaire_voit_les_onglets_de_creation(app, client):
    """Régression : le statut canonique doit ouvrir Créer et Import Excel."""
    uid = _mk_user(app, "perm.gest2@devoptiq.com", "manager")
    _as(client, uid, "perm.gest2@devoptiq.com")
    html = client.get("/comptes/").data.decode("utf-8")
    assert 'data-tab="create-tab"' in html
    assert 'data-tab="import-tab"' in html


# ── Modification d'un compte : robustesse du formulaire ──────────────────────
# Un « âge » vide partait tel quel ('') dans une colonne entière : PostgreSQL
# refusait, et TOUTE modification (même un nom de famille) tombait en 500.

def test_modifier_un_compte_sans_age(app, client, actors):
    _as(client, actors["admin"], "perm.admin@devoptiq.com")
    res = client.post(f"/comptes/update/{actors['other']}", data={
        "first_name": "Jean", "last_name": "Nouveau",
        "email": "perm.other@devoptiq.com", "age": "",
        "status": "user", "role_id": "",
    })
    assert res.status_code == 302
    assert "msg=updated" in res.headers["Location"]
    with app.app_context():
        from Code.models.models import User
        u = User.query.get(actors["other"])
        assert u.last_name == "Nouveau"
        assert u.age is None          # et surtout PAS la chaîne vide


def test_modifier_le_statut_d_un_compte(app, client, actors):
    _as(client, actors["admin"], "perm.admin@devoptiq.com")
    res = client.post(f"/comptes/update/{actors['other']}", data={
        "first_name": "Jean", "last_name": "Nouveau",
        "email": "perm.other@devoptiq.com", "age": "",
        "status": "manager", "role_id": "",
    })
    assert res.status_code == 302
    with app.app_context():
        from Code.models.models import User
        assert User.query.get(actors["other"]).status == "manager"


def test_un_age_non_numerique_est_refuse_proprement(app, client, actors):
    _as(client, actors["admin"], "perm.admin@devoptiq.com")
    res = client.post(f"/comptes/update/{actors['other']}", data={
        "first_name": "Jean", "last_name": "Nouveau",
        "email": "perm.other@devoptiq.com", "age": "trente",
        "status": "user", "role_id": "",
    })
    assert res.status_code == 302
    assert "error_invalid_age" in res.headers["Location"]


def test_un_email_deja_pris_est_refuse(app, client, actors):
    _as(client, actors["admin"], "perm.admin@devoptiq.com")
    res = client.post(f"/comptes/update/{actors['other']}", data={
        "first_name": "Jean", "last_name": "Nouveau",
        "email": "perm.admin@devoptiq.com", "age": "",
        "status": "user", "role_id": "",
    })
    assert res.status_code == 302
    assert "error_email_exists" in res.headers["Location"]
    with app.app_context():
        from Code.models.models import User
        assert User.query.get(actors["other"]).email == "perm.other@devoptiq.com"


def test_le_role_est_facultatif_a_la_modification(app, client, actors):
    """Sans rôle sélectionné, l'affectation existante est retirée — pas de 500."""
    from Code.models.models import UserRole, Role
    from Code.extensions import db
    with app.app_context():
        from Code.models.models import User
        role = Role.query.filter_by(name="Role edition compte").first()
        if role is None:
            role = Role(name="Role edition compte",
                        entity_id=User.query.get(actors["other"]).entity_id)
            db.session.add(role)
            db.session.commit()
        if not UserRole.query.filter_by(user_id=actors["other"]).first():
            db.session.add(UserRole(user_id=actors["other"], role_id=role.id))
            db.session.commit()

    _as(client, actors["admin"], "perm.admin@devoptiq.com")
    res = client.post(f"/comptes/update/{actors['other']}", data={
        "first_name": "Jean", "last_name": "Nouveau",
        "email": "perm.other@devoptiq.com", "age": "42",
        "status": "user", "role_id": "",
    })
    assert res.status_code == 302
    assert "msg=updated" in res.headers["Location"]
    with app.app_context():
        from Code.models.models import User, UserRole as UR
        assert UR.query.filter_by(user_id=actors["other"]).first() is None
        assert User.query.get(actors["other"]).age == 42
