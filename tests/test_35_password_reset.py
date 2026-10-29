# tests/test_35_password_reset.py
"""Les deux routes du parcours « mot de passe oublié ».

  - POST /forgot_password            (routes_password.py)
  - GET  /reset_password/<token>     (routes_password.py)
  - POST /reset_password/<token>     (routes_password.py)

Les GARANTIES du mécanisme (usage unique, débit, révocation des sessions,
politique) sont éprouvées dans `test_117_mot_de_passe.py` ; ici on vérifie
l'enchaînement et les messages.

⚠️ **Les messages se comparent au CATALOGUE, jamais à une phrase recopiée.**
La session de test part en anglais (`DEFAULT_LANG`), et toutes ces routes
passent désormais par `t()` : une phrase française écrite en dur dans un test
le ferait échouer pour une raison qui n'a rien à voir avec ce qu'il contrôle.

⚠️ **La limitation de débit vaut aussi dans les tests** (3 demandes par
adresse et par quart d'heure) : sans la remise à zéro de `demandes_propres`,
le quatrième test qui demande une réinitialisation pour la même adresse
recevrait « trop de demandes » et personne ne comprendrait pourquoi.
"""
import pytest

pytestmark = pytest.mark.password_reset

COMPTE = "test@devoptiq.com"


@pytest.fixture(autouse=True)
def demandes_propres(app):
    """La table des demandes est à l'échelle de l'instance, et la base est
    partagée entre les fichiers de tests."""
    from Code.extensions import db
    from Code.models.models import PasswordReset

    def vider():
        with app.app_context():
            db.session.rollback()
            PasswordReset.query.delete()
            db.session.commit()

    vider()
    yield
    vider()


@pytest.fixture(autouse=True)
def compte_partage_rendu_intact(app):
    """Rend `test@devoptiq.com` EXACTEMENT comme il a été trouvé.

    ⚠️ Le mot de passe **ET** `password_changed_at`. Ce compte est partagé par
    toute la suite, et l'horodatage décide désormais de la validité des
    sessions : le laisser bougé fait sortir les fichiers suivants de leur
    session, sans qu'aucun d'eux ne parle de mots de passe. Mesuré : trois
    échecs instables sur trois fichiers sans rapport, qui changeaient d'un
    passage à l'autre.

    ⚠️ Lecture et écriture en SQL BRUT, puis `expire_all()` : la session
    SQLAlchemy des tests est partagée, et sa carte d'identité garderait
    l'ancienne valeur même après l'UPDATE.
    """
    from sqlalchemy import text as _text
    from Code.extensions import db

    SEL = "SELECT password, password_changed_at FROM users WHERE email = :e"
    UPD = ("UPDATE users SET password = :p, password_changed_at = :t "
           "WHERE email = :e")

    with app.app_context():
        db.session.rollback()
        avant = db.session.execute(_text(SEL), {"e": COMPTE}).first()
    yield
    with app.app_context():
        db.session.rollback()
        db.session.execute(_text(UPD),
                           {"p": avant[0], "t": avant[1], "e": COMPTE})
        db.session.commit()
        db.session.expire_all()


@pytest.fixture(autouse=True)
def langue_anglaise(client):
    """Épingle la langue de la session, et la rend telle qu'elle était.

    ⚠️ `client` est partagé : un fichier précédent peut l'avoir laissé en
    français, et les messages comparés ici ne seraient plus les bons.
    """
    with client.session_transaction() as sess:
        avant = sess.get("lang")
        sess["lang"] = "en"
    yield
    with client.session_transaction() as sess:
        if avant is None:
            sess.pop("lang", None)
        else:
            sess["lang"] = avant


def _msg(app, cle):
    """Le libellé attendu, dans la langue de la session de test."""
    from Code.translations import t
    with app.app_context():
        return t(cle, "en")


def _jeton(app, email=COMPTE):
    """Un VRAI jeton : signé, et avec sa ligne en base."""
    from Code import mot_de_passe as mdp
    from Code.models.models import User
    with app.app_context():
        user = User.query.filter(User.email == email).first()
        assert user is not None, email
        return mdp.fabriquer_jeton(user, email)


# ===========================================================================
# 1. POST /forgot_password
# ===========================================================================

class TestForgotPassword:

    def test_sans_email_redirige_vers_login(self, client):
        r = client.post("/forgot_password", data={}, follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_email_connu_redirige_avec_message_discret(self, client, app):
        r = client.post("/forgot_password", data={"email": COMPTE},
                        follow_redirects=True)
        assert r.status_code == 200

    def test_email_inconnu_meme_comportement(self, client):
        r = client.post("/forgot_password", data={"email": "inconnu@nowhere.com"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_email_en_minuscules(self, client):
        r = client.post("/forgot_password", data={"email": "TEST@DEVOPTIQ.COM"},
                        follow_redirects=False)
        assert r.status_code == 302

    def test_mail_non_configure_message_specifique(self, client, app):
        """MAIL_CONFIGURED=False (le cas par défaut des tests) → message dédié."""
        assert not app.config.get("MAIL_CONFIGURED")
        r = client.post("/forgot_password", data={"email": COMPTE},
                        follow_redirects=True)
        assert r.status_code == 200
        assert _msg(app, "pwd.mail_off") in r.get_data(as_text=True)

    def test_email_connu_envoie_un_email_avec_lien_reset(self, client, app):
        from Code.extensions import mail

        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            with mail.record_messages() as outbox:
                r = client.post("/forgot_password", data={"email": COMPTE},
                                follow_redirects=False)
                assert r.status_code == 302
                assert "/login" in r.headers["Location"]
                assert len(outbox) == 1
                assert outbox[0].recipients == [COMPTE]
                assert "/reset_password/" in outbox[0].body
        finally:
            app.config["MAIL_CONFIGURED"] = False

    def test_email_inconnu_mais_mail_configure_ne_cree_pas_de_message(self, client, app):
        from Code.extensions import mail

        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            with mail.record_messages() as outbox:
                r = client.post("/forgot_password",
                                data={"email": "personne@nowhere.com"},
                                follow_redirects=False)
                assert r.status_code == 302
                assert len(outbox) == 0
        finally:
            app.config["MAIL_CONFIGURED"] = False

    def test_recherche_insensible_a_la_casse(self, app):
        import Code.routes.routes_password as routes_password_module
        with app.app_context():
            found = routes_password_module._find_user_by_email("TEST@DEVOPTIQ.COM")
            assert found is not None
            assert found.email == COMPTE

    def test_une_erreur_d_envoi_rend_le_MEME_message_que_le_succes(
            self, client, app, monkeypatch):
        """⚠️ Le cœur de l'anti-énumération, et l'inverse de ce que faisait la
        version d'avant.

        Elle affichait « Erreur lors de l'envoi de l'email » — un message que
        le `try/except`, posé À L'INTÉRIEUR du `if user:`, ne pouvait rendre
        QUE pour un compte existant. Le message neutre était donc annulé par
        son voisin : il suffisait d'essayer des adresses et de regarder
        laquelle produisait l'erreur.
        """
        from Code.extensions import mail

        def envoi_casse(msg):
            raise RuntimeError("SMTP down")

        monkeypatch.setattr(mail, "send", envoi_casse)
        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            r = client.post("/forgot_password", data={"email": COMPTE},
                            follow_redirects=True)
            assert r.status_code == 200
            page = r.get_data(as_text=True)
            assert _msg(app, "pwd.sent") in page
            assert "SMTP" not in page
        finally:
            app.config["MAIL_CONFIGURED"] = False


# ===========================================================================
# 2. GET /reset_password/<token>
# ===========================================================================

class TestResetPasswordGet:

    def test_token_invalide_redirige_login(self, client):
        r = client.get("/reset_password/token-invalide", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_token_valide_retourne_formulaire(self, client, app):
        r = client.get("/reset_password/%s" % _jeton(app))
        assert r.status_code == 200

    def test_token_valide_contient_champ_password(self, client, app):
        r = client.get("/reset_password/%s" % _jeton(app))
        assert b"password" in r.data.lower()

    def test_un_GET_ne_consomme_PAS_le_lien(self, client, app):
        """Ouvrir la page ne doit pas brûler le lien : on y arrive, on réfléchit,
        on revient."""
        jeton = _jeton(app)
        assert client.get("/reset_password/%s" % jeton).status_code == 200
        assert client.get("/reset_password/%s" % jeton).status_code == 200

    def test_token_expire_redirige_login(self, client, monkeypatch):
        """⚠️ On remplace la classe dans le namespace de `mot_de_passe`, pas
        globalement : `URLSafeTimedSerializer` signe aussi les cookies de
        session Flask, et la patcher partout couperait l'authentification des
        autres tests qui partagent ce client."""
        import Code.mot_de_passe as module_mdp
        from itsdangerous import SignatureExpired

        class SerialiseurExpire:
            def __init__(self, *a, **kw):
                pass

            def loads(self, *a, **kw):
                raise SignatureExpired("expired")

        monkeypatch.setattr(module_mdp, "URLSafeTimedSerializer", SerialiseurExpire)
        r = client.get("/reset_password/un-token-quelconque", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]


# ===========================================================================
# 3. POST /reset_password/<token>
# ===========================================================================

class TestResetPasswordPost:

    def test_mot_de_passe_trop_court(self, client, app):
        r = client.post("/reset_password/%s" % _jeton(app),
                        data={"password": "abc", "confirm_password": "abc"})
        assert r.status_code == 200
        assert _msg(app, "reset_pwd.err_too_short") in r.get_data(as_text=True)

    def test_mots_de_passe_non_identiques(self, client, app):
        r = client.post("/reset_password/%s" % _jeton(app),
                        data={"password": "NouveauPass1!",
                              "confirm_password": "AutrePass2!"})
        assert r.status_code == 200
        assert _msg(app, "reset_pwd.err_mismatch") in r.get_data(as_text=True)

    def test_token_invalide_sur_post_redirige(self, client):
        r = client.post("/reset_password/mauvais-token",
                        data={"password": "NewPass123!",
                              "confirm_password": "NewPass123!"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_reset_valide_redirige_vers_login(self, client, app):
        from Code.extensions import db
        from Code.models.models import User
        from Code.security import hash_password

        jeton = _jeton(app)
        r = client.post("/reset_password/%s" % jeton,
                        data={"password": "NouveauPass123!",
                              "confirm_password": "NouveauPass123!"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
        with app.app_context():
            u = User.query.filter_by(email=COMPTE).first()
            u.password = hash_password("TestPass123!")
            db.session.commit()

    def test_jeton_d_un_compte_supprime(self, client, app):
        """Un lien dont le compte a disparu entre-temps ne passe pas.

        ⚠️ La charge du jeton porte désormais l'IDENTIFIANT du compte, pas son
        adresse : « un jeton valide pour une adresse inconnue » n'existe plus,
        le cas réel est le compte supprimé après l'envoi.
        """
        from Code.extensions import db
        from Code.models.models import User
        from Code.security import hash_password

        with app.app_context():
            jetable = User(first_name="T35", last_name="Jetable",
                           email="t35.jetable@devoptiq.com",
                           password=hash_password("Motdepasse123!"), status="user")
            db.session.add(jetable)
            db.session.commit()
        jeton = _jeton(app, "t35.jetable@devoptiq.com")
        with app.app_context():
            User.query.filter_by(email="t35.jetable@devoptiq.com").delete()
            db.session.commit()

        r = client.post("/reset_password/%s" % jeton,
                        data={"password": "NouveauPass123!",
                              "confirm_password": "NouveauPass123!"},
                        follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_erreur_commit_annule_et_affiche_erreur(self, client, app, monkeypatch):
        from sqlalchemy.orm import Session as SqlaSession
        from Code.models.models import User

        jeton = _jeton(app)
        with app.app_context():
            hash_origine = User.query.filter_by(email=COMPTE).first().password

        def commit_casse(self):
            raise RuntimeError("DB down")

        monkeypatch.setattr(SqlaSession, "commit", commit_casse)
        r = client.post("/reset_password/%s" % jeton,
                        data={"password": "TentativePass123!",
                              "confirm_password": "TentativePass123!"})
        assert r.status_code == 200
        assert _msg(app, "pwd.err_server") in r.get_data(as_text=True)

        monkeypatch.undo()
        with app.app_context():
            assert User.query.filter_by(email=COMPTE).first().password == hash_origine

    def test_hash_non_persiste_affiche_erreur_dediee(self, client, app, monkeypatch):
        """Le commit réussit, la relecture ne correspond pas → message dédié."""
        import Code.mot_de_passe as module_mdp
        from Code.extensions import db
        from Code.models.models import User
        from Code.security import hash_password

        jeton = _jeton(app)
        monkeypatch.setattr(module_mdp, "verify_password", lambda stocke, clair: False)
        try:
            r = client.post("/reset_password/%s" % jeton,
                            data={"password": "AutreTentative123!",
                                  "confirm_password": "AutreTentative123!"})
            assert r.status_code == 200
            assert _msg(app, "pwd.err_not_saved") in r.get_data(as_text=True)
        finally:
            with app.app_context():
                u = User.query.filter_by(email=COMPTE).first()
                u.password = hash_password("TestPass123!")
                db.session.commit()

    def test_reset_valide_modifie_le_mot_de_passe(self, client, app):
        from Code.extensions import db
        from Code.models.models import User
        from Code.security import hash_password, verify_password

        jeton = _jeton(app)
        nouveau = "ResetPass456!"
        client.post("/reset_password/%s" % jeton,
                    data={"password": nouveau, "confirm_password": nouveau})

        with app.app_context():
            u = User.query.filter_by(email=COMPTE).first()
            assert verify_password(u.password, nouveau)
            u.password = hash_password("TestPass123!")
            db.session.commit()
