# tests/test_73_ui_routes.py
"""
Page : /ui/activities — vue minimale (Blueprint `ui_bp`), sans équivalent
dans les autres suites de tests malgré son enregistrement dans app.py.

Ne nécessite pas d'authentification (aucune garde dans la route) : elle
retombe simplement sur une liste vide si aucune entité active n'est
résolue. On vérifie donc le rendu dans les deux cas, l'isolation par
entité active, et le repli d'affichage sur un nom d'activité absent.
"""
import pytest

pytestmark = pytest.mark.activities


# Le client de test est partagé par toute la suite : on rend la session d'origine.
@pytest.fixture(autouse=True)
def _restaurer_la_session(app, client, ids):
    yield
    with client.session_transaction() as sess:
        sess["user_id"] = ids["user_id"]
        sess["user_email"] = "test@devoptiq.com"
        sess["active_entity_id"] = ids["entity_id"]


class TestUiActivitiesAnonyme:
    """Sans authentification : pas de garde, mais pas d'entité active non plus."""

    def test_get_sans_session_renvoie_200(self, client):
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/ui/activities")
        assert r.status_code == 200

    def test_get_sans_session_affiche_message_vide(self, client):
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/ui/activities")
        assert "Aucune activit".encode("utf-8") in r.data

    def test_get_sans_session_est_html(self, client):
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/ui/activities")
        assert "text/html" in (r.content_type or "")


class TestUiActivitiesAuthentifie:
    """Avec une entité active : la liste reflète les activités de CETTE entité."""

    def test_get_liste_active_entity(self, client, ids):
        with client.session_transaction() as sess:
            sess["user_id"] = ids["user_id"]
            sess["user_email"] = "test@devoptiq.com"
            sess["active_entity_id"] = ids["entity_id"]

        r = client.get("/ui/activities")
        assert r.status_code == 200
        assert f'data-activity-id="{ids["activity_id"]}"'.encode("utf-8") in r.data
        assert "Activité Test".encode("utf-8") in r.data

    def test_get_isole_par_entite_active(self, app, client, ids):
        """Une activité d'une AUTRE entité ne doit jamais apparaître ici."""
        from Code.extensions import db
        from Code.models.models import Entity, Activities

        with app.app_context():
            autre_entite = Entity(name="T73 Autre Entité", owner_id=ids["user_id"])
            db.session.add(autre_entite)
            db.session.flush()
            autre_activite = Activities(
                entity_id=autre_entite.id,
                name="T73 Activité Étrangère",
            )
            db.session.add(autre_activite)
            db.session.commit()
            autre_activite_id = autre_activite.id

        with client.session_transaction() as sess:
            sess["user_id"] = ids["user_id"]
            sess["user_email"] = "test@devoptiq.com"
            sess["active_entity_id"] = ids["entity_id"]

        r = client.get("/ui/activities")
        assert r.status_code == 200
        assert f'data-activity-id="{autre_activite_id}"'.encode("utf-8") not in r.data
        assert b"T73 Activit\xc3\xa9 \xc3\x89trang\xc3\xa8re" not in r.data

    def test_get_nom_absent_affiche_repli(self, app, client, ids):
        """Une activité sans nom (name vide) retombe sur le libellé de secours."""
        from Code.extensions import db
        from Code.models.models import Activities

        with app.app_context():
            sans_nom = Activities(entity_id=ids["entity_id"], name="")
            db.session.add(sans_nom)
            db.session.commit()
            sans_nom_id = sans_nom.id

        with client.session_transaction() as sess:
            sess["user_id"] = ids["user_id"]
            sess["user_email"] = "test@devoptiq.com"
            sess["active_entity_id"] = ids["entity_id"]

        r = client.get("/ui/activities")
        assert r.status_code == 200
        assert f'data-activity-id="{sans_nom_id}"'.encode("utf-8") in r.data
        assert "Activité sans nom".encode("utf-8") in r.data
