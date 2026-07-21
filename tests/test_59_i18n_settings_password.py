# tests/test_59_i18n_settings_password.py
"""
Tests des correctifs Gestion RH / traduction / mot de passe :
1. Politique de hachage (Code/security.py) : PBKDF2-SHA256 600k, compat legacy.
2. Modification de mot de passe : set_password, reset par token, re-hash au login.
3. Paramètres entreprise : persistance réelle (modèle EntrepriseSettings),
   liste blanche des clés, relecture après enregistrement.
4. Traduction des rôles : caches name_fr/name_en, repli sans clé OpenAI.
5. Page Gestion RH : section DCP et textes JS traduits FR/EN.

Isolation : données dédiées (préfixe t59) + cleanup — DB partagée scope=session.
"""
import pytest


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_user(app, email, password="InitPass123!", legacy=False):
    from Code.extensions import db
    from Code.models.models import User
    from werkzeug.security import generate_password_hash
    from Code.security import hash_password
    with app.app_context():
        u = User(first_name="T59", last_name="User", email=email,
                 password=(generate_password_hash(password, method="scrypt")
                           if legacy else hash_password(password)),
                 status="user")
        db.session.add(u)
        db.session.commit()
        return u.id


def _delete_user(app, email):
    from Code.extensions import db
    from Code.models.models import User
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
            db.session.commit()


def _set_lang(client, lang):
    client.post("/parametres/set_language", json={"lang": lang})


def _restore_auth_session(app, client):
    """Restaure la session du user seed (le client est PARTAGÉ scope=session :
    un login dans un test remplace la session de auth_client pour toute la suite)."""
    from Code.models.models import User, Entity
    with app.app_context():
        user = User.query.filter_by(email="test@devoptiq.com").first()
        entity = Entity.query.filter_by(name="Entité Test").first()
    with client.session_transaction() as sess:
        if user:
            sess["user_id"] = user.id
            sess["user_email"] = user.email
        if entity:
            sess["active_entity_id"] = entity.id


# ═══════════════════════════════════════════════════════════════
# 1. Politique de hachage
# ═══════════════════════════════════════════════════════════════

class TestSecurityModule:

    def test_hash_is_pbkdf2_600k(self):
        from Code.security import hash_password, PASSWORD_HASH_METHOD
        h = hash_password("abcdef")
        assert h.startswith(PASSWORD_HASH_METHOD + "$")
        assert PASSWORD_HASH_METHOD == "pbkdf2:sha256:600000"

    def test_hash_fits_narrow_column(self):
        """Le hash doit tenir dans les colonnes historiques (< 128 caractères)."""
        from Code.security import hash_password
        assert len(hash_password("un mot de passe assez long !")) < 128

    def test_verify_roundtrip_and_reject(self):
        from Code.security import hash_password, verify_password
        h = hash_password("secret42")
        assert verify_password(h, "secret42")
        assert not verify_password(h, "mauvais")

    def test_verify_accepts_legacy_formats(self):
        from werkzeug.security import generate_password_hash
        from Code.security import verify_password, needs_rehash
        legacy = generate_password_hash("oldpass", method="scrypt")
        assert verify_password(legacy, "oldpass")
        assert needs_rehash(legacy)

    def test_verify_never_raises_on_garbage(self):
        from Code.security import verify_password
        assert not verify_password("pas-un-hash", "x")
        assert not verify_password(None, "x")
        assert not verify_password("", "")


# ═══════════════════════════════════════════════════════════════
# 2. Modification de mot de passe
# ═══════════════════════════════════════════════════════════════

class TestPasswordChange:

    EMAIL = "t59.pwd@devoptiq.com"

    def test_set_password_persists_and_login(self, app, client):
        uid = _make_user(app, self.EMAIL, "InitPass123!")
        try:
            r = client.post(f"/comptes/set_password/{uid}",
                            json={"password": "NouveauMdp1!"})
            assert r.status_code == 200 and r.get_json()["ok"] is True

            # le hash en base vérifie bien le nouveau mot de passe
            from Code.extensions import db
            from Code.models.models import User
            from Code.security import verify_password, PASSWORD_HASH_METHOD
            with app.app_context():
                u = db.session.get(User, uid)
                assert u.password.startswith(PASSWORD_HASH_METHOD + "$")
                assert verify_password(u.password, "NouveauMdp1!")
                assert not verify_password(u.password, "InitPass123!")

            # login : nouveau OK, ancien refusé
            r = client.post("/login", data={"email": self.EMAIL,
                                            "password": "NouveauMdp1!"})
            assert r.status_code == 302 and "/login" not in (r.headers.get("Location") or "")
            r = client.post("/login", data={"email": self.EMAIL,
                                            "password": "InitPass123!"})
            assert (r.headers.get("Location") or "").endswith("/login")
        finally:
            _restore_auth_session(app, client)
            _delete_user(app, self.EMAIL)

    def test_set_password_too_short_rejected(self, app, client):
        uid = _make_user(app, "t59.short@devoptiq.com")
        try:
            r = client.post(f"/comptes/set_password/{uid}", json={"password": "abc"})
            assert r.status_code == 400
        finally:
            _delete_user(app, "t59.short@devoptiq.com")

    def test_reset_password_by_token(self, app, client):
        email = "t59.reset@devoptiq.com"
        uid = _make_user(app, email, "AvantReset1!")
        try:
            from itsdangerous import URLSafeTimedSerializer
            with app.app_context():
                token = URLSafeTimedSerializer(app.config["SECRET_KEY"]).dumps(
                    email, salt="password-reset-salt")
            r = client.post(f"/reset_password/{token}",
                            data={"password": "ApresReset1!",
                                  "confirm_password": "ApresReset1!"})
            assert r.status_code == 302

            from Code.extensions import db
            from Code.models.models import User
            from Code.security import verify_password
            with app.app_context():
                u = db.session.get(User, uid)
                assert verify_password(u.password, "ApresReset1!")
        finally:
            _delete_user(app, email)

    def test_login_rehashes_legacy_scrypt(self, app, client):
        email = "t59.legacy@devoptiq.com"
        uid = _make_user(app, email, "LegacyPass1!", legacy=True)
        try:
            r = client.post("/login", data={"email": email, "password": "LegacyPass1!"})
            assert r.status_code == 302 and "/login" not in (r.headers.get("Location") or "")

            from Code.extensions import db
            from Code.models.models import User
            from Code.security import PASSWORD_HASH_METHOD, verify_password
            with app.app_context():
                u = db.session.get(User, uid)
                assert u.password.startswith(PASSWORD_HASH_METHOD + "$")
                assert verify_password(u.password, "LegacyPass1!")
        finally:
            _restore_auth_session(app, client)
            _delete_user(app, email)


# ═══════════════════════════════════════════════════════════════
# 3. Paramètres entreprise
# ═══════════════════════════════════════════════════════════════

class TestEntrepriseSettings:

    def _cleanup(self, app, entity_id):
        from Code.extensions import db
        from Code.models.models import EntrepriseSettings
        with app.app_context():
            EntrepriseSettings.query.filter_by(entity_id=entity_id).delete()
            db.session.commit()

    def test_single_setting_persists_after_reload(self, app, auth_client, ids):
        try:
            r = auth_client.post("/gestion_rh/update_single_setting",
                                 data={"key": "work_hours_per_day", "value": "7.5"})
            assert r.status_code == 200
            body = r.get_json()
            assert body["success"] is True and float(body["value"]) == 7.5

            # rechargement de la page : la valeur enregistrée est affichée
            r = auth_client.get("/gestion_rh/")
            assert r.status_code == 200
            assert "7.5" in r.data.decode()
        finally:
            self._cleanup(app, ids["entity_id"])

    def test_unknown_key_rejected(self, auth_client):
        r = auth_client.post("/gestion_rh/update_single_setting",
                             data={"key": "evil; DROP TABLE users", "value": "1"})
        assert r.status_code == 400

    def test_update_settings_form_persists(self, app, auth_client, ids):
        try:
            r = auth_client.post("/gestion_rh/update_settings",
                                 data={"work_hours_per_day": "8",
                                       "work_days_per_week": "5",
                                       "work_weeks_per_year": "47",
                                       "work_days_per_year": "220"})
            assert r.status_code == 302

            from Code.models.models import EntrepriseSettings
            with app.app_context():
                row = EntrepriseSettings.query.filter_by(
                    entity_id=ids["entity_id"]).first()
                assert row is not None
                assert row.work_hours_per_day == 8
                assert row.work_days_per_year == 220
        finally:
            self._cleanup(app, ids["entity_id"])

    def test_calendar_params_uses_settings(self, app, auth_client, ids):
        """Les paramètres RH alimentent les analyses de temps."""
        try:
            auth_client.post("/gestion_rh/update_settings",
                             data={"work_hours_per_day": "6",
                                   "work_days_per_week": "4",
                                   "work_weeks_per_year": "40",
                                   "work_days_per_year": "160"})
            r = auth_client.get("/temps/api/calendar_params")
            data = r.get_json()
            assert data["hours_per_day"] == 6.0
            assert data["days_per_week"] == 4
            assert data["weeks_per_year"] == 40
        finally:
            self._cleanup(app, ids["entity_id"])


# ═══════════════════════════════════════════════════════════════
# 4. Traduction des rôles
# ═══════════════════════════════════════════════════════════════

class TestRoleTranslation:

    def _delete_role(self, app, name):
        from Code.extensions import db
        from Code.models.models import Role
        with app.app_context():
            for r in Role.query.filter(Role.name == name).all():
                db.session.delete(r)
            db.session.commit()

    def test_create_role_caches_current_lang(self, app, auth_client):
        _set_lang(auth_client, "fr")
        try:
            r = auth_client.post("/gestion_rh/role", data={"name": "T59 Chef de projet"})
            assert r.status_code == 200

            from Code.models.models import Role
            with app.app_context():
                role = Role.query.filter_by(name="T59 Chef de projet").first()
                assert role is not None
                assert role.name_fr == "T59 Chef de projet"
                assert role.name_en is None  # traduit à la volée au 1er affichage EN
        finally:
            self._delete_role(app, "T59 Chef de projet")

    def test_rename_in_english_swaps_caches(self, app, auth_client):
        try:
            _set_lang(auth_client, "fr")
            auth_client.post("/gestion_rh/role", data={"name": "T59 Ancien"})
            from Code.models.models import Role
            with app.app_context():
                rid = Role.query.filter_by(name="T59 Ancien").first().id

            _set_lang(auth_client, "en")
            r = auth_client.put(f"/roles/{rid}", json={"name": "T59 New Name"})
            assert r.status_code == 200

            with app.app_context():
                role = Role.query.get(rid)
                assert role.name == "T59 New Name"
                assert role.name_en == "T59 New Name"
                assert role.name_fr is None  # invalidé : sera retraduit
        finally:
            _set_lang(auth_client, "fr")
            self._delete_role(app, "T59 New Name")
            self._delete_role(app, "T59 Ancien")

    def test_display_falls_back_without_openai(self, app, auth_client, monkeypatch):
        """Sans clé OpenAI, l'affichage retombe sur le nom d'origine (jamais inventé)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        try:
            _set_lang(auth_client, "fr")
            auth_client.post("/gestion_rh/role", data={"name": "T59 Comptable"})
            _set_lang(auth_client, "en")
            r = auth_client.get("/roles_view/")
            assert r.status_code == 200
            assert "T59 Comptable" in r.data.decode()
        finally:
            _set_lang(auth_client, "fr")
            self._delete_role(app, "T59 Comptable")

    def test_display_names_uses_ai_when_available(self, app, auth_client, monkeypatch):
        """Avec IA disponible (simulée), la traduction est affichée puis mise en cache."""
        import Code.role_i18n as ri
        monkeypatch.setattr(ri, "_translate_batch",
                            lambda names, lang: ["T59 Accountant" for _ in names])
        try:
            _set_lang(auth_client, "fr")
            auth_client.post("/gestion_rh/role", data={"name": "T59 Comptable"})
            _set_lang(auth_client, "en")
            r = auth_client.get("/roles_view/")
            assert "T59 Accountant" in r.data.decode()

            from Code.models.models import Role
            with app.app_context():
                role = Role.query.filter_by(name="T59 Comptable").first()
                assert role.name_en == "T59 Accountant"   # cache persisté
                assert role.name == "T59 Comptable"       # origine intacte

            # retour en FR : on retrouve exactement la saisie d'origine
            _set_lang(auth_client, "fr")
            r = auth_client.get("/roles_view/")
            assert "T59 Comptable" in r.data.decode()
        finally:
            _set_lang(auth_client, "fr")
            self._delete_role(app, "T59 Comptable")


# ═══════════════════════════════════════════════════════════════
# 5. Page Gestion RH traduite
# ═══════════════════════════════════════════════════════════════

class TestGestionRHTranslations:

    def test_dcp_section_english(self, auth_client):
        _set_lang(auth_client, "en")
        try:
            body = auth_client.get("/gestion_rh/").data.decode()
            assert "DCP reference file" in body
            assert "AI proposal mode" in body
            assert "Ce fichier Excel est utilis" not in body  # plus de FR en dur
        finally:
            _set_lang(auth_client, "fr")

    def test_dcp_section_french(self, auth_client):
        _set_lang(auth_client, "fr")
        body = auth_client.get("/gestion_rh/").data.decode()
        assert "Fichier de référence DCP" in body
        assert "Mode des propositions IA" in body

    def test_js_i18n_dictionaries_injected(self, auth_client):
        _set_lang(auth_client, "en")
        try:
            body = auth_client.get("/gestion_rh/").data.decode()
            assert "GRH_I18N" in body
            assert "PROPOSE_I18N" in body
            # quelques clés traduites côté JS
            assert '"Save roles"' in body
            assert '"DCP file loaded"' in body
        finally:
            _set_lang(auth_client, "fr")
