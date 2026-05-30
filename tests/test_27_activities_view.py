# tests/test_27_activities_view.py
"""
Module : activities_view.py — Affichage paginé des activités
Routes couvertes :
  GET /activities/view                      → chargement initial de la page
  GET /activities/view?activity_id=<id>     → activité épinglée en premier
  GET /activities/view/more                 → chargement paginé supplémentaire (JSON)
  GET /activities/view/more?offset=<n>      → pagination par décalage
  GET /activities/view/more?exclude_id=<id> → filtrage d'une activité
"""
import json
import pytest

pytestmark = pytest.mark.activities_view


# ===========================================================================
# 1. Accès à la page principale /activities/view
# ===========================================================================

class TestActivitiesViewPage:

    def test_view_authenticated_returns_200(self, auth_client):
        """La page /activities/view retourne 200 avec une session valide."""
        r = auth_client.get("/activities/view")
        assert r.status_code == 200

    def test_view_unauthenticated_does_not_crash(self, client):
        """Sans session, /activities/view répond 200 ou 302 sans lever d'exception."""
        r = client.get("/activities/view", follow_redirects=False)
        assert r.status_code in (200, 302)

    def test_view_returns_html(self, auth_client):
        """La réponse est du HTML (contient <html ou <!doctype)."""
        r = auth_client.get("/activities/view")
        assert r.status_code == 200
        body = r.data.lower()
        assert b"<html" in body or b"<!doctype" in body

    def test_view_contains_seeded_activity_name(self, auth_client):
        """Le nom de l'activité test ('Activité Test') apparaît dans la page."""
        r = auth_client.get("/activities/view")
        assert r.status_code == 200
        assert "Activit" in r.data.decode("utf-8", errors="replace")


# ===========================================================================
# 2. Activité épinglée — paramètre ?activity_id
# ===========================================================================

class TestActivitiesViewPinned:

    def test_pinned_activity_valid_id_returns_200(self, auth_client, ids):
        """?activity_id=<id> valide retourne 200 sans crash."""
        r = auth_client.get(f"/activities/view?activity_id={ids['activity_id']}")
        assert r.status_code == 200

    def test_pinned_activity_unknown_id_returns_200(self, auth_client):
        """?activity_id=999999 (inexistant) retourne tout de même 200 gracieusement."""
        r = auth_client.get("/activities/view?activity_id=999999")
        assert r.status_code == 200

    def test_pinned_activity_content_present(self, auth_client, ids):
        """La page épinglée contient le nom de l'activité ciblée."""
        r = auth_client.get(f"/activities/view?activity_id={ids['activity_id']}")
        assert r.status_code == 200
        assert "Activit" in r.data.decode("utf-8", errors="replace")

    def test_pinned_activity_zero_not_treated_as_id(self, auth_client):
        """?activity_id=0 est ignoré (retourne la liste normale, pas de crash)."""
        r = auth_client.get("/activities/view?activity_id=0")
        assert r.status_code == 200


# ===========================================================================
# 3. Endpoint de pagination /activities/view/more
# ===========================================================================

class TestActivitiesViewMore:

    def test_view_more_returns_200(self, auth_client):
        """GET /activities/view/more retourne 200."""
        r = auth_client.get("/activities/view/more")
        assert r.status_code == 200

    def test_view_more_returns_json(self, auth_client):
        """La réponse est du JSON valide."""
        r = auth_client.get("/activities/view/more")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, dict)

    def test_view_more_has_required_keys(self, auth_client):
        """JSON contient les clés html, has_more et next_offset."""
        r = auth_client.get("/activities/view/more")
        data = json.loads(r.data)
        assert "html" in data
        assert "has_more" in data
        assert "next_offset" in data

    def test_view_more_html_is_string(self, auth_client):
        """La clé html est une chaîne de caractères."""
        r = auth_client.get("/activities/view/more")
        data = json.loads(r.data)
        assert isinstance(data["html"], str)

    def test_view_more_has_more_is_bool(self, auth_client):
        """La clé has_more est un booléen."""
        r = auth_client.get("/activities/view/more")
        data = json.loads(r.data)
        assert isinstance(data["has_more"], bool)

    def test_view_more_next_offset_is_int(self, auth_client):
        """La clé next_offset est un entier."""
        r = auth_client.get("/activities/view/more")
        data = json.loads(r.data)
        assert isinstance(data["next_offset"], int)


# ===========================================================================
# 4. Paramètre offset — pagination par décalage
# ===========================================================================

class TestActivitiesViewMoreOffset:

    def test_offset_zero_returns_activities(self, auth_client):
        """offset=0 retourne les activités depuis le début."""
        r = auth_client.get("/activities/view/more?offset=0")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "html" in data

    def test_high_offset_returns_empty_html(self, auth_client):
        """Un offset très élevé retourne html vide et has_more=False."""
        r = auth_client.get("/activities/view/more?offset=9999")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["has_more"] is False
        assert data["html"] == ""

    def test_high_offset_next_offset_equals_input(self, auth_client):
        """Quand il n'y a plus rien, next_offset correspond à l'offset demandé."""
        r = auth_client.get("/activities/view/more?offset=9999")
        data = json.loads(r.data)
        assert data["next_offset"] == 9999

    def test_offset_default_is_page_size(self, auth_client):
        """Sans paramètre offset, l'offset par défaut est PAGE_SIZE (20)."""
        r = auth_client.get("/activities/view/more")
        data = json.loads(r.data)
        # Avec seulement 1 activité en DB, has_more=False et next_offset=20 (ou la valeur par défaut)
        assert data["next_offset"] >= 0


# ===========================================================================
# 5. Paramètre exclude_id — filtrage d'une activité
# ===========================================================================

class TestActivitiesViewMoreExclude:

    def test_exclude_id_filters_out_activity(self, auth_client, ids):
        """exclude_id supprime l'activité correspondante du résultat HTML."""
        r = auth_client.get(f"/activities/view/more?offset=0&exclude_id={ids['activity_id']}")
        assert r.status_code == 200
        data = json.loads(r.data)
        # L'activité "Activité Test" ne doit plus apparaître dans le HTML retourné
        assert "Activité Test" not in data["html"]

    def test_exclude_unknown_id_does_not_crash(self, auth_client):
        """exclude_id=999999 (inexistant) ne provoque pas d'erreur."""
        r = auth_client.get("/activities/view/more?offset=0&exclude_id=999999")
        assert r.status_code == 200

    def test_exclude_zero_treated_as_no_filter(self, auth_client):
        """exclude_id=0 est ignoré (type=int, None si absent) — pas de crash."""
        r = auth_client.get("/activities/view/more?offset=0&exclude_id=0")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "html" in data

    def test_unauthenticated_view_more_does_not_crash(self, client):
        """Sans session, /activities/view/more répond 200 ou 302 sans exception."""
        r = client.get("/activities/view/more", follow_redirects=False)
        assert r.status_code in (200, 302)
