# tests/test_117_mot_de_passe.py
"""Les GARANTIES du mécanisme de mot de passe, pas l'enchaînement des écrans
(celui-là est dans `test_35_password_reset.py`).

Chaque classe répond à un défaut relevé le 28/10/2026 sur le système
d'origine, et chacun a été vérifié ROUGE en remettant le code d'avant :

  1. le jeton n'était pas à usage unique — sa charge était l'adresse e-mail,
     et rien n'était stocké : le lien restait valable une heure MÊME APRÈS le
     changement de mot de passe. ⚠️ C'est l'EMPREINTE du mot de passe courant
     qui le ferme, et elle seule : le banc de cliquets a montré qu'en retirant
     la vérification de la ligne en base, aucun test de rejeu ne rougissait —
     chaque écriture re-sale le hash, donc l'empreinte change de toute façon.
     La ligne, elle, exige qu'une demande ait été enregistrée, et porte le
     débit et l'audit ;
  2. aucune limitation de débit, ni sur la demande ni sur la connexion ;
  3. le message neutre était annulé par le message d'erreur d'envoi, qui ne
     pouvait apparaître que pour un compte existant ;
  4. aucune session n'était fermée : réinitialiser changeait la clé du compte
     sans en reprendre le contrôle ;
  5. la politique vivait à cinq endroits, avec deux valeurs ;
  6. tout était en dur, en français, sur un pilote anglophone.
"""
import pytest

pytestmark = pytest.mark.password_reset

COMPTE = "test@devoptiq.com"
MDP_TEST = "TestPass123!"


@pytest.fixture(autouse=True)
def demandes_propres(app):
    """⚠️ La limitation de débit compte des lignes EN BASE, et la base est
    partagée entre les fichiers : sans remise à zéro, l'ordre d'exécution
    décide si un test reçoit « trop de demandes »."""
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


@pytest.fixture
def porte_stricte(app):
    """Met la porte des sessions périmées en service pour ce test.

    ⚠️ Elle est désarmée par défaut dans les tests (voir
    `conftest.sessions_de_test_sans_empreinte`) : une trentaine de fichiers
    bricolent leur session à la main. Les cas ci-dessous sont les seuls à la
    mettre à l'épreuve, et ils doivent donc l'armer eux-mêmes.
    """
    avant = app.config.get("PWD_SESSION_STRICTE")
    app.config["PWD_SESSION_STRICTE"] = True
    yield
    app.config["PWD_SESSION_STRICTE"] = avant


def _jeton(app, email=COMPTE):
    from Code import mot_de_passe as mdp
    from Code.models.models import User
    with app.app_context():
        user = User.query.filter(User.email == email).first()
        return mdp.fabriquer_jeton(user, email)


def _msg(app, cle, lang="en"):
    from Code.translations import t
    with app.app_context():
        return t(cle, lang)


# ══════════════════════════════════════════════════════════════════════════
#  1 · Le jeton ne sert qu'UNE fois
# ══════════════════════════════════════════════════════════════════════════

class TestLeJetonNeSertQuUneFois:

    def test_un_lien_deja_utilise_ne_resert_pas(self, client, app):
        jeton = _jeton(app)
        corps = {"password": "Premier1234!", "confirm_password": "Premier1234!"}
        assert client.post("/reset_password/%s" % jeton, data=corps).status_code == 302

        r = client.post("/reset_password/%s" % jeton,
                        data={"password": "Second12345!",
                              "confirm_password": "Second12345!"},
                        follow_redirects=True)
        assert _msg(app, "pwd.lien_utilise") in r.get_data(as_text=True)

        from Code.models.models import User
        from Code.security import verify_password
        with app.app_context():
            u = User.query.filter_by(email=COMPTE).first()
            assert verify_password(u.password, "Premier1234!")
            assert not verify_password(u.password, "Second12345!")

    def test_le_lien_meurt_quand_le_mot_de_passe_change_AILLEURS(
            self, client, app):
        """⚠️ Le cas qui comptait le plus. Quelqu'un reçoit un lien, un
        administrateur repose le mot de passe entre-temps : le lien d'avant
        devait mourir. Il vivait une heure."""
        from Code import mot_de_passe as mdp
        from Code.models.models import User

        jeton = _jeton(app)
        with app.app_context():
            u = User.query.filter_by(email=COMPTE).first()
            mdp.poser(u, "PoseParLAdmin1!")

        r = client.post("/reset_password/%s" % jeton,
                        data={"password": "AvecLeVieuxLien1!",
                              "confirm_password": "AvecLeVieuxLien1!"},
                        follow_redirects=True)
        assert _msg(app, "pwd.lien_utilise") in r.get_data(as_text=True)

    def test_deux_liens_demandes_le_premier_meurt_avec_le_second(
            self, client, app):
        """Deux demandes de suite : se servir du second tue le premier."""
        premier = _jeton(app)
        second = _jeton(app)
        assert client.post("/reset_password/%s" % second,
                           data={"password": "ParLeSecond1!",
                                 "confirm_password": "ParLeSecond1!"}).status_code == 302
        r = client.post("/reset_password/%s" % premier,
                        data={"password": "ParLePremier1!",
                              "confirm_password": "ParLePremier1!"},
                        follow_redirects=True)
        assert _msg(app, "pwd.lien_utilise") in r.get_data(as_text=True)

    def test_un_jeton_de_l_ancien_format_est_refuse(self, app):
        """La charge d'origine était l'adresse e-mail, en clair. Un tel jeton
        n'est plus accepté — voulu, et sans conséquence : l'envoi d'e-mail n'a
        jamais été configuré, personne n'en détient."""
        from itsdangerous import URLSafeTimedSerializer
        from Code import mot_de_passe as mdp
        with app.app_context():
            vieux = URLSafeTimedSerializer(app.config["SECRET_KEY"]).dumps(
                COMPTE, salt=mdp.SEL)
            user, code = mdp.lire_jeton(vieux)
        assert user is None
        assert code == "pwd_lien_invalide"

    def test_un_jeton_signe_SANS_demande_enregistree_est_refuse(self, app):
        """⚠️ Ce que la ligne en base garantit VRAIMENT — et ce n'est pas le
        rejeu, que l'empreinte couvre déjà. Un jeton bien signé doit
        correspondre à une demande réellement enregistrée : sans cela, un
        jeton ressorti après la purge des vieilles demandes, ou fabriqué par
        un autre chemin de code, passerait."""
        from Code import mot_de_passe as mdp
        from Code.extensions import db
        from Code.models.models import PasswordReset, User
        with app.app_context():
            u = User.query.filter_by(email=COMPTE).first()
            jeton = mdp.fabriquer_jeton(u, COMPTE)
            PasswordReset.query.filter_by(jeton_hash=mdp._sha(jeton)).delete()
            db.session.commit()
            user, code = mdp.lire_jeton(jeton)
        assert user is None
        assert code == "pwd_lien_invalide"

    def test_rien_d_exploitable_n_est_stocke(self, app):
        """⚠️ Une lecture de la base ne doit rendre NI un lien utilisable, NI
        la liste des adresses que quelqu'un a essayées."""
        from Code import mot_de_passe as mdp
        from Code.models.models import PasswordReset, User
        with app.app_context():
            user = User.query.filter_by(email=COMPTE).first()
            jeton = mdp.fabriquer_jeton(user, COMPTE, ip="203.0.113.7")
            ligne = PasswordReset.query.order_by(PasswordReset.id.desc()).first()

            assert ligne.jeton_hash != jeton
            assert jeton not in (ligne.jeton_hash or "")
            assert ligne.email_hash != COMPTE
            assert COMPTE not in (ligne.email_hash or "")
            assert ligne.ip_hash != "203.0.113.7"
            for empreinte in (ligne.email_hash, ligne.jeton_hash, ligne.ip_hash):
                assert empreinte is not None and len(empreinte) == 64

            # Et le modèle ne porte AUCUNE colonne en clair où les ranger.
            colonnes = {c.name for c in PasswordReset.__table__.columns}
            assert not (colonnes & {"email", "jeton", "token", "ip", "adresse"})

    def test_une_demande_consommee_est_tracee(self, client, app):
        """La trace d'audit : qui a demandé, quand, et l'a-t-il utilisée."""
        from Code.models.models import PasswordReset
        jeton = _jeton(app)
        with app.app_context():
            assert PasswordReset.query.filter(
                PasswordReset.utilise_le.isnot(None)).count() == 0
        client.post("/reset_password/%s" % jeton,
                    data={"password": "Consomme123!",
                          "confirm_password": "Consomme123!"})
        with app.app_context():
            ligne = PasswordReset.query.order_by(PasswordReset.id.desc()).first()
            assert ligne.utilise_le is not None
            assert ligne.user_id is not None


# ══════════════════════════════════════════════════════════════════════════
#  2 · La limitation de débit
# ══════════════════════════════════════════════════════════════════════════

class TestLeDebit:

    def test_au_dela_de_la_limite_la_demande_est_refusee(self, client, app):
        from Code import mot_de_passe as mdp
        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            from Code.extensions import mail
            with mail.record_messages():
                for _ in range(mdp.MAX_PAR_ADRESSE):
                    r = client.post("/forgot_password", data={"email": COMPTE},
                                    follow_redirects=True)
                    assert _msg(app, "pwd.sent") in r.get_data(as_text=True)
                r = client.post("/forgot_password", data={"email": COMPTE},
                                follow_redirects=True)
                assert _msg(app, "pwd.too_many") in r.get_data(as_text=True)
        finally:
            app.config["MAIL_CONFIGURED"] = False

    def test_une_adresse_INCONNUE_compte_aussi(self, client, app):
        """⚠️ Ne compter que les envois réels dirait, par le simple fait de ne
        pas ralentir, que l'adresse est inconnue."""
        from Code import mot_de_passe as mdp
        from Code.models.models import PasswordReset
        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            for _ in range(mdp.MAX_PAR_ADRESSE):
                client.post("/forgot_password",
                            data={"email": "personne@nowhere.test"},
                            follow_redirects=False)
            with app.app_context():
                assert PasswordReset.query.count() == mdp.MAX_PAR_ADRESSE
            r = client.post("/forgot_password",
                            data={"email": "personne@nowhere.test"},
                            follow_redirects=True)
            assert _msg(app, "pwd.too_many") in r.get_data(as_text=True)
        finally:
            app.config["MAIL_CONFIGURED"] = False

    def test_une_AUTRE_adresse_n_est_pas_bloquee(self, client, app):
        """La limite par adresse ne doit pas verrouiller tout le monde."""
        from Code import mot_de_passe as mdp
        with app.app_context():
            for _ in range(mdp.MAX_PAR_ADRESSE + 2):
                mdp.tracer_demande("premiere@nowhere.test")
            assert mdp.debit_depasse("premiere@nowhere.test")
            assert not mdp.debit_depasse("seconde@nowhere.test")

    def test_l_ip_du_client_vient_de_X_Forwarded_For(self, app):
        """⚠️ Le piège Cloud Run. `request.remote_addr` y est l'IP du frontend
        Google : la prendre ferait compter TOUTES les demandes de tout le monde
        sur une seule adresse, et la limite par IP verrouillerait l'instance
        entière au dixième essai."""
        import Code.routes.routes_password as rp
        with app.test_request_context(
                "/forgot_password",
                headers={"X-Forwarded-For": "203.0.113.7, 130.211.0.1"},
                environ_base={"REMOTE_ADDR": "169.254.8.129"}):
            assert rp._ip_client() == "203.0.113.7"
        with app.test_request_context("/forgot_password",
                                      environ_base={"REMOTE_ADDR": "10.0.0.5"}):
            assert rp._ip_client() == "10.0.0.5"

    def test_la_limite_par_ip_existe(self, app):
        from Code import mot_de_passe as mdp
        with app.app_context():
            for i in range(mdp.MAX_PAR_IP):
                mdp.tracer_demande("adresse%d@nowhere.test" % i, ip="198.51.100.9")
            # Chaque adresse n'a qu'une demande : seule la limite par IP peut mordre.
            assert mdp.debit_depasse("encore@nowhere.test", ip="198.51.100.9")
            assert not mdp.debit_depasse("encore@nowhere.test", ip="198.51.100.10")


# ══════════════════════════════════════════════════════════════════════════
#  3 · L'énumération
# ══════════════════════════════════════════════════════════════════════════

class TestOnNeDitPasQuiAUnCompte:

    def test_connu_et_inconnu_rendent_le_MEME_message(self, client, app):
        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            from Code.extensions import mail
            with mail.record_messages():
                a = client.post("/forgot_password", data={"email": COMPTE},
                                follow_redirects=True).get_data(as_text=True)
            b = client.post("/forgot_password", data={"email": "nul@nowhere.test"},
                            follow_redirects=True).get_data(as_text=True)
            attendu = _msg(app, "pwd.sent")
            assert attendu in a and attendu in b
        finally:
            app.config["MAIL_CONFIGURED"] = False

    def test_le_login_ne_dit_pas_LAQUELLE_des_deux_moities_est_fausse(self, app):
        """⚠️ « Compte introuvable. » d'un côté et « Mot de passe incorrect. »
        de l'autre suffisaient à dresser la liste du personnel en essayant des
        adresses."""
        c = app.test_client()
        inconnu = c.post("/login", data={"email": "nul@nowhere.test",
                                         "password": "Quelconque1!"},
                         follow_redirects=True).get_data(as_text=True)
        connu = c.post("/login", data={"email": COMPTE,
                                       "password": "MauvaisMotDePasse1!"},
                       follow_redirects=True).get_data(as_text=True)
        attendu = _msg(app, "login.bad_credentials")
        assert attendu in inconnu and attendu in connu


# ══════════════════════════════════════════════════════════════════════════
#  4 · Les sessions se ferment
# ══════════════════════════════════════════════════════════════════════════

class TestLesSessionsSeFerment:

    def test_un_changement_de_mot_de_passe_ferme_les_sessions_ouvertes(
            self, auth_client, app, porte_stricte):
        """⚠️ Sans cela, une réinitialisation change la clé du compte sans en
        reprendre le CONTRÔLE : l'intrus déjà connecté y reste."""
        from Code import mot_de_passe as mdp
        from Code.models.models import User

        assert auth_client.get("/auth/current_user_info").status_code == 200

        with app.app_context():
            u = User.query.filter_by(email=COMPTE).first()
            mdp.poser(u, "ApresReset123!")

        r = auth_client.get("/auth/current_user_info", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
        with auth_client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_une_session_perimee_laisse_PASSER_le_lien_de_reinitialisation(
            self, app, porte_stricte):
        """⚠️ Trouvé en écrivant ce test, pas à l'usage. Détourner vers /login
        depuis /reset_password enverrait dans le mur la personne qui vient
        justement de cliquer son lien : sa session est périmée PARCE QUE son
        mot de passe a changé."""
        from Code import mot_de_passe as mdp
        from Code.models.models import User

        c = app.test_client()
        with app.app_context():
            u = User.query.filter_by(email=COMPTE).first()
            mdp.poser(u, "Intermediaire1!")
            uid, mail_u = u.id, u.email
            jeton = mdp.fabriquer_jeton(u, mail_u)
        with c.session_transaction() as sess:
            sess["user_id"] = uid
            sess["user_email"] = mail_u
            sess["pwd_at"] = "une-empreinte-perimee"

        r = c.get("/reset_password/%s" % jeton)
        assert r.status_code == 200          # le formulaire, pas /login

    def test_la_REGLE_rejette_une_session_sans_empreinte_apres_un_changement(self, app):
        """⚠️ Au niveau de la RÈGLE, pas de la route : le décor de tests tolère
        l'absence d'empreinte (`conftest.sessions_de_test_sans_empreinte`),
        donc ce cas-là ne peut se vérifier qu'ici — et il DOIT l'être, c'est
        le cœur de la révocation."""
        from Code import mot_de_passe as mdp
        from Code.models.models import User
        with app.app_context():
            u = User.query.filter_by(email=COMPTE).first()
            mdp.poser(u, "PourLaRegle1!")
            assert u.password_changed_at is not None
            assert mdp.regle_session_perimee(u, None) is True
            assert mdp.regle_session_perimee(u, "autre-chose") is True
            assert mdp.regle_session_perimee(u, mdp.empreinte_session(u)) is False
            mdp.poser(u, MDP_TEST)

    def test_une_session_sans_empreinte_passe_tant_que_rien_n_a_change(
            self, app, porte_stricte):
        """⚠️ Sinon la mise en service déconnecterait tout le monde d'un coup.
        L'absence ne devient une péremption qu'au premier changement."""
        from Code import mot_de_passe as mdp
        from Code.extensions import db
        from Code.models.models import User
        from Code.security import hash_password

        with app.app_context():
            jetable = User(first_name="T117", last_name="Jamais",
                           email="t117.jamais@devoptiq.com",
                           password=hash_password("Motdepasse123!"), status="user")
            db.session.add(jetable)
            db.session.commit()
            uid, mail_u = jetable.id, jetable.email
            assert jetable.password_changed_at is None
            assert not mdp.regle_session_perimee(jetable, None)
        try:
            c = app.test_client()
            with c.session_transaction() as sess:
                sess["user_id"] = uid
                sess["user_email"] = mail_u
            assert c.get("/auth/current_user_info").status_code == 200
        finally:
            with app.app_context():
                User.query.filter_by(id=uid).delete()
                db.session.commit()

    def test_le_re_hachage_du_login_ne_ferme_PAS_la_session(self, app):
        """Le login re-hache les formats historiques : l'horodatage ne doit PAS
        bouger, sinon chacun se déconnecterait à sa propre connexion."""
        from Code.extensions import db
        from Code.models.models import User
        from werkzeug.security import generate_password_hash

        with app.app_context():
            u = User(first_name="T117", last_name="Vieux",
                     email="t117.vieux@devoptiq.com",
                     password=generate_password_hash("Motdepasse123!",
                                                     method="pbkdf2:sha256:1000"),
                     status="user")
            db.session.add(u)
            db.session.commit()
            uid = u.id
        try:
            c = app.test_client()
            r = c.post("/login", data={"email": "t117.vieux@devoptiq.com",
                                       "password": "Motdepasse123!"},
                       follow_redirects=False)
            assert r.status_code == 302
            with app.app_context():
                u = db.session.get(User, uid)
                from Code.security import needs_rehash
                assert not needs_rehash(u.password)      # il a bien été migré
                assert u.password_changed_at is None     # mais rien n'a « changé »
            assert c.get("/auth/current_user_info").status_code == 200
        finally:
            with app.app_context():
                User.query.filter_by(id=uid).delete()
                db.session.commit()


# ══════════════════════════════════════════════════════════════════════════
#  5 · La politique, à UN seul endroit
# ══════════════════════════════════════════════════════════════════════════

class TestLaPolitiqueEstUnique:

    def test_la_borne_est_celle_du_module(self, app):
        from Code import mot_de_passe as mdp
        assert mdp.MIN_LONGUEUR == 8
        assert mdp.valider("a" * (mdp.MIN_LONGUEUR - 1)) == "pwd_trop_court"
        assert mdp.valider("a" * mdp.MIN_LONGUEUR) is None
        assert mdp.valider("") == "pwd_trop_court"
        assert mdp.valider(None) == "pwd_trop_court"

    def test_les_quatre_portes_refusent_sept_caracteres(self, auth_client, app, ids):
        """⚠️ Le reset, la création, la modification et la pose par un
        administrateur : quatre écrans, une seule règle. Trois exigeaient six
        caractères, l'assistant d'installation huit."""
        court = "Court1!"            # sept caractères
        assert len(court) == 7

        # 1. poser le mot de passe de quelqu'un
        r = auth_client.post("/comptes/set_password/%d" % ids["user_id"],
                             json={"password": court})
        assert r.status_code == 400

        # 2. créer un compte
        r = auth_client.post("/comptes/create",
                             data={"first_name": "T117", "last_name": "Court",
                                   "email": "t117.court@devoptiq.com",
                                   "password": court, "statut": "user"},
                             headers={"Accept": "application/json"})
        assert r.status_code >= 400

        # 3. modifier un compte
        r = auth_client.post("/comptes/update/%d" % ids["user_id"],
                             data={"first_name": "Test", "last_name": "User",
                                   "email": COMPTE, "password": court},
                             headers={"Accept": "application/json"})
        assert r.status_code >= 400

        # 4. le reset
        r = auth_client.post("/reset_password/%s" % _jeton(app),
                             data={"password": court, "confirm_password": court})
        assert r.status_code == 200
        assert _msg(app, "reset_pwd.err_too_short") in r.get_data(as_text=True)

    def test_l_assistant_d_installation_partage_la_regle(self):
        """Il portait la seule valeur correcte (8) — et en dur.

        ⚠️ Relit une SOURCE : saute dans l'arbre d'image, qui est
        bytecode-only. Sans la garde, ce cas rougirait à chaque exécution de
        la suite sur l'instance — et un contrôle qui rougit toujours n'est
        plus lu.
        """
        import inspect
        import Code.routes.setup_wizard as sw
        try:
            source = inspect.getsource(sw)
        except (OSError, TypeError):
            pytest.skip("source absente (arbre bytecode) — contrôle de source")
        assert "mdp.valider(admin_password)" in source
        assert "len(admin_password) < 8" not in source


# ══════════════════════════════════════════════════════════════════════════
#  6 · La langue
# ══════════════════════════════════════════════════════════════════════════

class TestLeMailSuitLaLangueDuDestinataire:

    def test_le_corps_est_dans_la_langue_DU_COMPTE(self, client, app):
        """⚠️ Pas celle de la session : la demande part d'un écran de
        connexion, où personne n'est identifié. Le pilote est anglophone, et
        le mail d'origine était en français en dur."""
        from Code.extensions import db, mail
        from Code.models.models import User
        from Code.security import hash_password

        with app.app_context():
            u = User(first_name="T117", last_name="Anglais",
                     email="t117.en@devoptiq.com",
                     password=hash_password("Motdepasse123!"),
                     status="user", lang="en")
            db.session.add(u)
            db.session.commit()
            uid = u.id
        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            with client.session_transaction() as sess:
                sess["lang"] = "fr"          # la session, elle, est en français
            with mail.record_messages() as outbox:
                client.post("/forgot_password",
                            data={"email": "t117.en@devoptiq.com"})
            assert len(outbox) == 1
            assert outbox[0].subject == _msg(app, "pwd.mail_subject", "en")
            assert "Hello" in outbox[0].body
            assert "Bonjour" not in outbox[0].body
            assert "[[lien]]" not in outbox[0].body    # le marqueur est remplacé
            assert "/reset_password/" in outbox[0].body
        finally:
            app.config["MAIL_CONFIGURED"] = False
            with app.app_context():
                User.query.filter_by(id=uid).delete()
                db.session.commit()

    def test_aucun_libelle_du_parcours_n_est_ecrit_en_dur(self):
        """⚠️ Les six messages de la route et le corps du mail étaient en dur,
        en français. Le cliquet vise les PHRASES, pas les mots : un commentaire
        français reste légitime."""
        import io
        import os
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for rel in ("Code/routes/routes_password.py",
                    "Code/routes/connexion_routes.py"):
            chemin = os.path.join(racine, rel)
            # ⚠️ Arbre d'image : bytecode-only, les .py n'y sont plus.
            if not os.path.exists(chemin):
                pytest.skip("sources absentes (arbre bytecode) — contrôle de source")
            lignes = io.open(chemin, encoding="utf-8").read().split("\n")
            for n, ligne in enumerate(lignes, 1):
                nu = ligne.strip()
                if nu.startswith("#") or "flash(" not in nu:
                    continue
                assert "t(" in nu, "%s:%d — libellé en dur dans un flash : %s" % (
                    rel, n, nu)

    def test_les_cles_du_parcours_existent_dans_LES_DEUX_langues(self):
        from Code.translations import TRANSLATIONS
        cles = ["pwd.need_email", "pwd.mail_off", "pwd.sent", "pwd.too_many",
                "pwd.lien_expire", "pwd.lien_invalide", "pwd.lien_utilise",
                "pwd.done", "pwd.err_server", "pwd.err_not_saved",
                "pwd.mail_subject", "pwd.mail_body",
                "login.bad_credentials", "reset_pwd.account"]
        for cle in cles:
            for lang in ("fr", "en"):
                assert cle in TRANSLATIONS[lang], "%s absente en %s" % (cle, lang)
            assert TRANSLATIONS["fr"][cle] != TRANSLATIONS["en"][cle], cle

    def test_une_langue_INCONNUE_vaut_l_anglais_jamais_le_francais(self):
        """⚠️ `users.lang` est du TEXTE LIBRE (VARCHAR(5)) : les réglages, le
        login et l'import de comptes n'y mettent que `fr` ou `en`, mais rien
        n'empêche une correction en SQL ou une restauration depuis un vieux
        dump. Mesuré avant correctif : « EN », « en-US », « de », « hi »
        rendaient tous un corps de mail **FRANÇAIS** — c'est le repli de
        `t()`, et c'est exactement le courrier qu'on ne veut pas envoyer au
        pilote anglophone."""
        from Code.translations import langue_destinataire
        for brut in (None, "", "   ", "EN", "en-US", "en_GB", "de", "hi",
                     "xx", "zz-ZZ", 0):
            assert langue_destinataire(brut) == "en", repr(brut)
        for brut in ("fr", "FR", "fr-CA", " fr "):
            assert langue_destinataire(brut) == "fr", repr(brut)
        assert langue_destinataire("en") == "en"

    def test_le_defaut_du_mail_est_celui_DU_PRODUIT(self):
        """⚠️ Deux sources de vérité ne doivent pas dériver en silence.
        `translations` ne peut pas importer `models` (le sens de dépendance
        s'inverserait, et translations n'importe aujourd'hui que flask) : la
        valeur est donc redite, et tenue ici."""
        from Code.translations import LANGUE_PAR_DEFAUT
        from Code.models.models import DEFAULT_LANG
        assert LANGUE_PAR_DEFAUT == DEFAULT_LANG

    def test_le_corps_suit_users_lang_BOUT_EN_BOUT(self, client, app):
        """Le parcours complet, pour chaque valeur que la colonne peut porter.

        ⚠️ Une IP distincte par cas : la limite par IP (10 / quart d'heure)
        ne doit pas décider du résultat d'un test sur la LANGUE.
        """
        from Code.extensions import db, mail
        from Code.models.models import User
        from Code.security import hash_password

        CAS = [("en", "Hello"), ("fr", "Bonjour"), (None, "Hello"),
               ("", "Hello"), ("EN", "Hello"), ("en-US", "Hello"),
               ("fr-CA", "Bonjour"), ("hi", "Hello")]

        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            for i, (stocke, attendu) in enumerate(CAS):
                adresse = "t117.lang%d@devoptiq.com" % i
                with app.app_context():
                    u = User(first_name="T117", last_name="Lang",
                             email=adresse,
                             password=hash_password("Motdepasse123!"),
                             status="user", lang=stocke)
                    db.session.add(u)
                    db.session.commit()
                    uid = u.id
                try:
                    with mail.record_messages() as outbox:
                        client.post("/forgot_password", data={"email": adresse},
                                    headers={"X-Forwarded-For": "203.0.113.%d" % (i + 1)})
                    assert len(outbox) == 1, "users.lang=%r : aucun mail" % (stocke,)
                    premier = outbox[0].body.split(",")[0]
                    assert premier == attendu, (
                        "users.lang=%r → corps en %r, attendu %r"
                        % (stocke, premier, attendu))
                    assert "[[lien]]" not in outbox[0].body
                finally:
                    with app.app_context():
                        User.query.filter_by(id=uid).delete()
                        db.session.commit()
        finally:
            app.config["MAIL_CONFIGURED"] = False


class TestUneVariableVideNEstPasUneVariableAbsente:
    """⚠️ Le défaut qui aurait fait échouer la mise en service.

    `--set-env-vars` CRÉE la variable sur Cloud Run même quand le secret
    GitHub n'existe pas : elle arrive PRÉSENTE et VIDE. `getenv(cle, defaut)`
    ne regarde alors JAMAIS son défaut — une variable vide est une valeur.
    Relevé sur la console avant d'avoir posé le moindre secret : les trois
    MAIL_* y étaient déjà, toutes les trois vides.
    """

    def test_un_expediteur_vide_retombe_sur_le_compte_d_envoi(self):
        from Code.app import config_mail
        c = config_mail({"MAIL_USERNAME": "afdec@gmail.com",
                         "MAIL_PASSWORD": "x",
                         "MAIL_DEFAULT_SENDER": ""})
        assert c["MAIL_DEFAULT_SENDER"] == "afdec@gmail.com"

    def test_un_expediteur_vide_ferait_echouer_TOUT_envoi(self, app):
        """La CONSÉQUENCE, mesurée — ce n'est pas un détail de confort.
        flask_mail refuse un message sans expéditeur : on aurait posé les
        deux secrets, et rien ne serait jamais parti, avec à l'écran le même
        message neutre qu'avant le correctif. Introuvable sans les journaux.
        """
        from flask_mail import Message
        from Code.extensions import mail

        ext = app.extensions["mail"]
        ancien, ancienne_garde = ext.default_sender, ext.suppress
        ext.default_sender, ext.suppress = "", True   # jamais de vrai SMTP ici
        try:
            with app.app_context():
                with pytest.raises(AssertionError):
                    mail.send(Message(subject="Reset",
                                      recipients=["qui@exemple.fr"],
                                      body="lien"))
        finally:
            ext.default_sender, ext.suppress = ancien, ancienne_garde

    def test_un_port_vide_ne_fait_pas_tomber_le_DEMARRAGE(self):
        """⚠️ `int("")` lève une ValueError, et ce bloc s'exécute dans
        `create_app` : le conteneur ne démarrerait plus du tout. C'est la
        panne « failed to start and listen on the port » déjà vécue le
        26/09, pour une variable qu'on aurait seulement laissée vide."""
        from Code.app import config_mail
        assert config_mail({"MAIL_PORT": ""})["MAIL_PORT"] == 587
        assert config_mail({"MAIL_SERVER": ""})["MAIL_SERVER"] == "smtp.gmail.com"

    def test_des_identifiants_vides_valent_PAS_CONFIGURE(self):
        """Le repli d'origine doit survivre : sans compte d'envoi, l'écran
        dit proprement que l'envoi n'est pas configuré."""
        from Code.app import config_mail
        for env in ({}, {"MAIL_USERNAME": "", "MAIL_PASSWORD": ""},
                    {"MAIL_USERNAME": "afdec@gmail.com", "MAIL_PASSWORD": ""},
                    {"MAIL_USERNAME": "", "MAIL_PASSWORD": "x"}):
            assert config_mail(env)["MAIL_CONFIGURED"] is False, env
        # ⚠️ Sans compte d'envoi il n'y a aucun expéditeur à retomber dessus —
        # mais un compte SANS mot de passe en garde un : c'est « configuré »
        # qui est faux là, pas l'expéditeur.
        assert config_mail({})["MAIL_DEFAULT_SENDER"] is None
        assert config_mail({"MAIL_USERNAME": "", "MAIL_DEFAULT_SENDER": ""}
                           )["MAIL_DEFAULT_SENDER"] is None
