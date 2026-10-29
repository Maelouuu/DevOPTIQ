# tests/test_48_set_password_admin.py
"""
Route : POST /comptes/set_password/<user_id>  (gestion_compte.py)
Permet à un administrateur de définir ou réinitialiser le mot de passe
d'un utilisateur sans passer par le flux de réinitialisation par email.

Comportements testés :
  - 404 si l'utilisateur n'existe pas
  - 400 si le mot de passe est absent, None, vide ou trop court (< 6 car.)
  - 200 + ok=True si le mot de passe est valide (≥ 6 car.)
  - Persistance : le nouveau mot de passe est bien enregistré en base
  - Le nouveau mot de passe permet bien de se connecter ensuite
  - La réponse est toujours du JSON
  - Le message d'erreur de validation correspond exactement à la constante
"""
import json
import pytest
from werkzeug.security import check_password_hash

pytestmark = pytest.mark.set_password_admin

URL = "/comptes/set_password/{user_id}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(app, ids, email="pwdtest@devoptiq.com", password="InitialPass1!"):
    """Crée un utilisateur de test et retourne son id."""
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        from werkzeug.security import generate_password_hash
        u = User(
            entity_id=ids["entity_id"],
            first_name="PwdTest",
            last_name="User",
            email=email,
            password=generate_password_hash(password),
            status="viewer",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _delete_user(app, user_id):
    """Supprime l'utilisateur de test."""
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        u = User.query.get(user_id)
        if u:
            db.session.delete(u)
            db.session.commit()


def _get_password_hash(app, user_id):
    """Lit le hash de mot de passe actuellement stocké en base."""
    with app.app_context():
        from Code.models.models import User
        u = User.query.get(user_id)
        return u.password if u else None


# ===========================================================================
# 1. Utilisateur introuvable
# ===========================================================================

class TestSetPasswordUserNotFound:

    def test_unknown_user_id_returns_404(self, auth_client):
        """POST /comptes/set_password/999999 → 404 (utilisateur inexistant)."""
        r = auth_client.post(
            URL.format(user_id=999999),
            json={"password": "ValidPass1!"},
        )
        assert r.status_code == 404

    def test_zero_user_id_returns_404(self, auth_client):
        """user_id=0 : l'ORM ne trouve aucun utilisateur → 404."""
        r = auth_client.post(
            URL.format(user_id=0),
            json={"password": "ValidPass1!"},
        )
        assert r.status_code == 404


# ===========================================================================
# 2. Validation du mot de passe
# ===========================================================================

class TestSetPasswordValidation:

    def test_empty_password_returns_400(self, auth_client, ids):
        """Mot de passe vide ("") → 400."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": ""},
        )
        assert r.status_code == 400

    def test_none_password_returns_400(self, auth_client, ids):
        """password=null (None) → interprété comme vide → 400."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": None},
        )
        assert r.status_code == 400

    def test_whitespace_only_password_returns_400(self, auth_client, ids):
        """Mot de passe composé uniquement d'espaces → strip() → vide → 400."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": "     "},
        )
        assert r.status_code == 400

    def test_missing_password_field_returns_400(self, auth_client, ids):
        """Corps JSON sans champ 'password' → 400."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"other_field": "value"},
        )
        assert r.status_code == 400

    def test_empty_json_body_returns_400(self, auth_client, ids):
        """Corps JSON vide {} → 400."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={},
        )
        assert r.status_code == 400

    def test_5_chars_password_returns_400(self, auth_client, ids):
        """Mot de passe de 5 caractères (< 6) → 400 (borne inférieure)."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": "12345"},
        )
        assert r.status_code == 400

    def test_7_chars_password_returns_400(self, auth_client, ids):
        """⚠️ Sept caractères : juste SOUS la borne, refusé.

        La politique est passée de six à huit caractères, et elle vit
        désormais à UN seul endroit (`Code/mot_de_passe.MIN_LONGUEUR`) — elle
        était écrite ici, deux fois de plus dans la page Comptes, dans le
        reset, et à huit dans l'assistant d'installation.
        """
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": "1234567"},
        )
        assert r.status_code == 400

    def test_8_chars_password_returns_200(self, auth_client, ids, app):
        """Huit caractères (la borne exacte) → 200."""
        old_hash = _get_password_hash(app, ids["user_id"])
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": "12345678"},
        )
        assert r.status_code == 200
        # Remettre le mot de passe original pour ne pas casser les autres tests
        with app.app_context():
            from Code.models.models import User
            from Code.extensions import db
            from sqlalchemy.orm.attributes import flag_modified
            u = User.query.get(ids["user_id"])
            u.password = old_hash
            flag_modified(u, "password")
            db.session.commit()

    def test_validation_error_contains_ok_false(self, auth_client, ids):
        """La réponse 400 contient ok=False."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": ""},
        )
        body = r.get_json()
        assert body.get("ok") is False

    def test_validation_error_contains_error_message(self, auth_client, ids):
        """La réponse 400 contient un champ 'error' avec le message exact."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": "abc"},
        )
        body = r.get_json()
        assert "error" in body
        from Code.mot_de_passe import MIN_LONGUEUR
        assert str(MIN_LONGUEUR) in body["error"]  # mentionne la longueur minimale

    def test_exact_error_message_wording(self, auth_client, ids, app):
        """Le message vient du CATALOGUE, pas d'une phrase écrite dans la route.

        ⚠️ Il était en dur, en français, dans la route : un administrateur du
        pilote anglophone lisait donc du français au milieu de son écran.
        """
        from Code.translations import t
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": ""},
        )
        body = r.get_json()
        with app.app_context():
            assert body["error"] in (t("reset_pwd.err_too_short", "fr"),
                                     t("reset_pwd.err_too_short", "en"))


# ===========================================================================
# 3. Succès
# ===========================================================================

class TestSetPasswordSuccess:

    def test_valid_password_returns_200(self, auth_client, app, ids):
        """Mot de passe valide → 200."""
        uid = _create_user(app, ids, email="success_test@devoptiq.com")
        try:
            r = auth_client.post(
                URL.format(user_id=uid),
                json={"password": "NouveauMdp42!"},
            )
            assert r.status_code == 200
        finally:
            _delete_user(app, uid)

    def test_valid_password_response_ok_true(self, auth_client, app, ids):
        """La réponse 200 contient ok=True."""
        uid = _create_user(app, ids, email="ok_true@devoptiq.com")
        try:
            r = auth_client.post(
                URL.format(user_id=uid),
                json={"password": "NouveauMdp42!"},
            )
            body = r.get_json()
            assert body.get("ok") is True
        finally:
            _delete_user(app, uid)

    def test_valid_password_response_no_error_field(self, auth_client, app, ids):
        """La réponse 200 ne contient pas de champ 'error'."""
        uid = _create_user(app, ids, email="no_error@devoptiq.com")
        try:
            r = auth_client.post(
                URL.format(user_id=uid),
                json={"password": "NouveauMdp42!"},
            )
            body = r.get_json()
            assert "error" not in body
        finally:
            _delete_user(app, uid)

    def test_response_is_json(self, auth_client, ids):
        """La réponse (succès ou erreur) est toujours du JSON."""
        r = auth_client.post(
            URL.format(user_id=ids["user_id"]),
            json={"password": ""},
        )
        assert r.content_type.startswith("application/json")


# ===========================================================================
# 4. Persistance en base
# ===========================================================================

class TestSetPasswordPersistence:

    def test_new_password_is_stored_in_db(self, auth_client, app, ids):
        """Après set_password, le hash stocké en base est celui du nouveau mot de passe."""
        new_pwd = "NouveauMdp_Persistance!"
        uid = _create_user(app, ids, email="persist@devoptiq.com", password="AncienMdp!")
        try:
            auth_client.post(
                URL.format(user_id=uid),
                json={"password": new_pwd},
            )
            stored_hash = _get_password_hash(app, uid)
            assert stored_hash is not None
            assert check_password_hash(stored_hash, new_pwd)
        finally:
            _delete_user(app, uid)

    def test_old_password_no_longer_valid(self, auth_client, app, ids):
        """Après set_password, l'ancien mot de passe n'est plus valide en base."""
        old_pwd = "AncienMdp!"
        new_pwd = "NouveauMdp_Old!"
        uid = _create_user(app, ids, email="old_invalid@devoptiq.com", password=old_pwd)
        try:
            auth_client.post(
                URL.format(user_id=uid),
                json={"password": new_pwd},
            )
            stored_hash = _get_password_hash(app, uid)
            assert not check_password_hash(stored_hash, old_pwd)
        finally:
            _delete_user(app, uid)

    def test_new_password_allows_login(self, auth_client, app, ids):
        """Après set_password, l'utilisateur peut se connecter avec son nouveau mot de passe.

        ⚠️ La connexion se fait sur un client NEUF, pas sur `client`. Les deux
        fixtures `client` et `auth_client` sont le MÊME objet en portée
        session : se connecter dessus avec un autre compte en remplace
        l'identité pour tous les tests suivants, et depuis la révocation des
        sessions au changement de mot de passe, cela rendait ce cas instable —
        vert seul, rouge une fois sur deux dans la suite complète. Un test qui
        se connecte pour de vrai prend son propre client.
        """
        new_pwd = "NewLogin_Mdp42!"
        uid = _create_user(app, ids, email="newlogin@devoptiq.com", password="OldLogin!")
        try:
            r0 = auth_client.post(
                URL.format(user_id=uid),
                json={"password": new_pwd},
            )
            assert r0.status_code == 200, r0.get_data(as_text=True)[:200]
            # Tentative de connexion avec le nouveau mot de passe
            r = app.test_client().post(
                "/login",
                data={"email": "newlogin@devoptiq.com", "password": new_pwd},
                follow_redirects=False,
            )
            # Flask redirige (302) vers la page d'accueil si la connexion réussit
            assert r.status_code in (200, 302)
            # S'il y a une redirection, elle ne va pas vers /login (pas d'erreur)
            if r.status_code == 302:
                assert "/login" not in r.headers.get("Location", "")
        finally:
            _delete_user(app, uid)

    def test_set_password_twice_keeps_latest(self, auth_client, app, ids):
        """Deux appels successifs à set_password conservent uniquement le dernier mot de passe."""
        first_pwd = "PremierMdp1!"
        second_pwd = "SecondMdp2@"
        uid = _create_user(app, ids, email="twicepwd@devoptiq.com")
        try:
            auth_client.post(URL.format(user_id=uid), json={"password": first_pwd})
            auth_client.post(URL.format(user_id=uid), json={"password": second_pwd})
            stored_hash = _get_password_hash(app, uid)
            assert check_password_hash(stored_hash, second_pwd)
            assert not check_password_hash(stored_hash, first_pwd)
        finally:
            _delete_user(app, uid)

    def test_password_is_hashed_not_plain(self, auth_client, app, ids):
        """Le mot de passe stocké est hashé, jamais en clair."""
        pwd = "PlainTextCheck!"
        uid = _create_user(app, ids, email="hashed@devoptiq.com")
        try:
            auth_client.post(URL.format(user_id=uid), json={"password": pwd})
            stored_hash = _get_password_hash(app, uid)
            # Le hash ne doit pas être égal au mot de passe en clair
            assert stored_hash != pwd
            # Mais check_password_hash doit valider le mot de passe original
            assert check_password_hash(stored_hash, pwd)
        finally:
            _delete_user(app, uid)
