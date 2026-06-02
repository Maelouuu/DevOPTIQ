# tests/test_34_settings.py
"""
Couvre :
  - GET  /parametres/              (settings.py)
  - POST /parametres/set_language  (settings.py)
"""
import pytest

pytestmark = pytest.mark.settings


# ===========================================================================
# 1. Page des paramètres — GET /parametres/
# ===========================================================================

class TestSettingsPage:

    def test_page_accessible_avec_auth(self, auth_client):
        """Page /parametres/ accessible avec session authentifiée → 200."""
        r = auth_client.get("/parametres/")
        assert r.status_code == 200

    def test_page_renvoie_html(self, auth_client):
        """La réponse contient du HTML."""
        r = auth_client.get("/parametres/")
        assert b"<" in r.data

    def test_page_sans_auth(self, client):
        """Page accessible ou redirigée selon la politique de la route (pas de crash)."""
        r = client.get("/parametres/")
        assert r.status_code in (200, 302, 401)


# ===========================================================================
# 2. Changement de langue — POST /parametres/set_language
# ===========================================================================

class TestSetLanguage:

    def test_langue_fr_acceptee(self, auth_client):
        """POST {lang: 'fr'} → 200 avec {ok: true, lang: 'fr'}."""
        r = auth_client.post(
            "/parametres/set_language",
            json={"lang": "fr"},
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["lang"] == "fr"

    def test_langue_en_acceptee(self, auth_client):
        """POST {lang: 'en'} → 200 avec {ok: true, lang: 'en'}."""
        r = auth_client.post(
            "/parametres/set_language",
            json={"lang": "en"},
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["lang"] == "en"

    def test_langue_invalide_refusee(self, auth_client):
        """Langue inconnue → 400 avec {ok: false}."""
        r = auth_client.post(
            "/parametres/set_language",
            json={"lang": "zz"},
            content_type="application/json",
        )
        assert r.status_code == 400
        data = r.get_json()
        assert data["ok"] is False

    def test_langue_vide_refusee(self, auth_client):
        """Langue vide → 400 (non présente dans ALLOWED_LANGS)."""
        r = auth_client.post(
            "/parametres/set_language",
            json={"lang": ""},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_payload_vide_utilise_defaut_fr(self, auth_client):
        """Payload sans 'lang' → utilise 'fr' par défaut → 200."""
        r = auth_client.post(
            "/parametres/set_language",
            json={},
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["lang"] == "fr"

    def test_langue_stockee_en_session(self, auth_client):
        """Après POST lang=en, la session contient lang=en."""
        auth_client.post(
            "/parametres/set_language",
            json={"lang": "en"},
            content_type="application/json",
        )
        with auth_client.session_transaction() as sess:
            assert sess.get("lang") == "en"

        auth_client.post(
            "/parametres/set_language",
            json={"lang": "fr"},
            content_type="application/json",
        )

    def test_content_type_json(self, auth_client):
        """La réponse du set_language est bien du JSON."""
        r = auth_client.post(
            "/parametres/set_language",
            json={"lang": "fr"},
            content_type="application/json",
        )
        assert r.content_type.startswith("application/json")
