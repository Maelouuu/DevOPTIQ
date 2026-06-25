# tests/test_47_cartography_editor_avance.py
"""
Couverture des routes avancées de l'éditeur cartographique non encore testées :
  POST /cartography/api/architect             → repositionnement IA des formes
  GET  /cartography/api/liaisons              → liaisons cross-carto pour l'éditeur
  PATCH /cartography/api/liaisons/<id>        → mise à jour du libellé d'une liaison
  GET  /activities/map/api/activities         → liste des activités pour rafraîchissement calque
"""
import pytest
from Code.models.models import CrossCartoLiaison, Entity, Activities

pytestmark = pytest.mark.cartography_editor_avance


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_owner(app, ids):
    """S'assure que l'entité test appartient à l'utilisateur test."""
    with app.app_context():
        from Code.extensions import db
        e = Entity.query.get(ids["entity_id"])
        if e and e.owner_id != ids["user_id"]:
            e.owner_id = ids["user_id"]
            db.session.commit()


def _create_liaison(app, ids, display_label=None):
    """Insère une CrossCartoLiaison active pour l'entité test et retourne son id."""
    with app.app_context():
        from Code.extensions import db
        liaison = CrossCartoLiaison(
            extco_entity_id=ids["entity_id"],
            extco_activity_id=ids["activity_id"],
            origin_entity_id=ids["entity_id"],
            origin_activity_id=ids["activity_id"],
            is_active=True,
            display_label=display_label,
        )
        db.session.add(liaison)
        db.session.commit()
        return liaison.id


def _delete_liaison(app, liaison_id):
    """Supprime une liaison par ID."""
    with app.app_context():
        from Code.extensions import db
        l = CrossCartoLiaison.query.get(liaison_id)
        if l:
            db.session.delete(l)
            db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# 1. POST /cartography/api/architect
# ─────────────────────────────────────────────────────────────────────────────

class TestArchitectNoAuth:
    """Sans session, l'endpoint retourne 403."""

    @pytest.fixture
    def anon(self, app):
        return app.test_client()

    def test_architect_sans_auth_retourne_403(self, anon):
        """POST /cartography/api/architect sans session → 403."""
        r = anon.post("/cartography/api/architect", json={"state": {"shapes": []}})
        assert r.status_code == 403


class TestArchitectPayload:
    """Cas de validation du payload (avec auth)."""

    def test_corps_vide_retourne_400(self, auth_client):
        """Body vide → 400 (aucune forme à organiser)."""
        r = auth_client.post("/cartography/api/architect", json={})
        assert r.status_code == 400

    def test_shapes_absentes_retourne_400(self, auth_client):
        """Pas de clé shapes → 400."""
        r = auth_client.post("/cartography/api/architect", json={"state": {}})
        assert r.status_code == 400

    def test_shapes_vide_retourne_400(self, auth_client):
        """shapes=[] → 400."""
        r = auth_client.post(
            "/cartography/api/architect",
            json={"state": {"shapes": [], "bands": [], "connections": []}},
        )
        assert r.status_code == 400

    def test_erreur_400_contient_champ_error(self, auth_client):
        """La réponse 400 contient un champ 'error'."""
        r = auth_client.post("/cartography/api/architect", json={"state": {"shapes": []}})
        data = r.get_json()
        assert "error" in data

    def test_shapes_non_vides_sans_cle_ia_retourne_500(self, auth_client):
        """Avec shapes valides mais sans clé IA → 500 (aucune clé configurée)."""
        payload = {
            "state": {
                "shapes": [
                    {"id": 1, "label": "Activité A", "type": "process",
                     "x": 100, "y": 0, "w": 170, "h": 70},
                ],
                "bands": [{"id": 1, "label": "Bande 1", "height": 220}],
                "connections": [],
            }
        }
        r = auth_client.post("/cartography/api/architect", json=payload)
        assert r.status_code == 500

    def test_erreur_500_contient_champ_error(self, auth_client):
        """La réponse 500 (aucune clé IA) contient un champ 'error'."""
        payload = {
            "state": {
                "shapes": [{"id": 1, "label": "X", "type": "process",
                             "x": 0, "y": 0, "w": 170, "h": 70}],
                "bands": [],
                "connections": [],
            }
        }
        r = auth_client.post("/cartography/api/architect", json=payload)
        data = r.get_json()
        assert "error" in data

    def test_plusieurs_shapes_sans_cle_ia_reste_500(self, auth_client):
        """Plusieurs formes avec connexions mais sans clé IA → 500."""
        payload = {
            "state": {
                "shapes": [
                    {"id": 1, "label": "Entrée", "type": "process",
                     "x": 50, "y": 10, "w": 170, "h": 70},
                    {"id": 2, "label": "Sortie", "type": "process",
                     "x": 300, "y": 10, "w": 170, "h": 70},
                ],
                "bands": [{"id": 1, "label": "Bande Flux", "height": 220}],
                "connections": [{"fromId": 1, "toId": 2}],
            }
        }
        r = auth_client.post("/cartography/api/architect", json=payload)
        assert r.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /cartography/api/liaisons
# ─────────────────────────────────────────────────────────────────────────────

class TestGetLiaisonsNoAuth:
    """Sans session, l'endpoint retourne une liste vide (pas de 403)."""

    @pytest.fixture
    def anon(self, app):
        return app.test_client()

    def test_sans_auth_retourne_200(self, anon):
        """GET /cartography/api/liaisons sans session → 200."""
        r = anon.get("/cartography/api/liaisons")
        assert r.status_code == 200

    def test_sans_auth_retourne_liste_vide(self, anon):
        """Sans session → liste vide (pas de données exposées)."""
        r = anon.get("/cartography/api/liaisons")
        assert r.get_json() == []


class TestGetLiaisonsAuth:
    """Avec session valide."""

    def test_retourne_200(self, auth_client, ids, app):
        """GET /cartography/api/liaisons avec auth → 200."""
        _ensure_owner(app, ids)
        r = auth_client.get("/cartography/api/liaisons")
        assert r.status_code == 200

    def test_retourne_liste_json(self, auth_client, ids, app):
        """La réponse est un tableau JSON."""
        _ensure_owner(app, ids)
        r = auth_client.get("/cartography/api/liaisons")
        assert isinstance(r.get_json(), list)

    def test_sans_liaison_retourne_vide(self, auth_client, ids, app):
        """Sans liaison en DB → liste vide.

        On purge d'abord les CrossCartoLiaison de l'entité partagée : d'autres
        tests en créent et la base est partagée (scope=session).
        """
        _ensure_owner(app, ids)
        with app.app_context():
            from Code.extensions import db
            CrossCartoLiaison.query.filter(
                db.or_(CrossCartoLiaison.extco_entity_id == ids["entity_id"],
                       CrossCartoLiaison.origin_entity_id == ids["entity_id"])
            ).delete(synchronize_session=False)
            db.session.commit()
        r = auth_client.get("/cartography/api/liaisons")
        data = r.get_json()
        assert data == []

    def test_avec_liaison_retourne_un_element(self, auth_client, ids, app):
        """Avec une liaison active → la liste contient un élément."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids)
        try:
            r = auth_client.get("/cartography/api/liaisons")
            data = r.get_json()
            assert len(data) >= 1
        finally:
            _delete_liaison(app, lid)

    def test_liaison_contient_champ_id(self, auth_client, ids, app):
        """Chaque liaison retournée a un champ 'id'."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids)
        try:
            data = auth_client.get("/cartography/api/liaisons").get_json()
            assert any("id" in l for l in data)
        finally:
            _delete_liaison(app, lid)

    def test_liaison_contient_extco_activity_id(self, auth_client, ids, app):
        """Chaque liaison retournée a un champ 'extco_activity_id'."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids)
        try:
            data = auth_client.get("/cartography/api/liaisons").get_json()
            assert any("extco_activity_id" in l for l in data)
        finally:
            _delete_liaison(app, lid)

    def test_liaison_contient_origin_entity_id(self, auth_client, ids, app):
        """Chaque liaison a un champ 'origin_entity_id'."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids)
        try:
            data = auth_client.get("/cartography/api/liaisons").get_json()
            assert any("origin_entity_id" in l for l in data)
        finally:
            _delete_liaison(app, lid)

    def test_liaison_contient_display_label(self, auth_client, ids, app):
        """Chaque liaison a un champ 'display_label' (peut être null)."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids, display_label="Label test")
        try:
            data = auth_client.get("/cartography/api/liaisons").get_json()
            assert any("display_label" in l for l in data)
        finally:
            _delete_liaison(app, lid)

    def test_liaison_inactive_non_retournee(self, auth_client, ids, app):
        """Une liaison is_active=False n'apparaît pas dans la liste."""
        _ensure_owner(app, ids)
        with app.app_context():
            from Code.extensions import db
            liaison = CrossCartoLiaison(
                extco_entity_id=ids["entity_id"],
                extco_activity_id=ids["activity_id"],
                origin_entity_id=ids["entity_id"],
                origin_activity_id=ids["activity_id"],
                is_active=False,
            )
            db.session.add(liaison)
            db.session.commit()
            lid = liaison.id

        try:
            data = auth_client.get("/cartography/api/liaisons").get_json()
            ids_retournes = [l["id"] for l in data]
            assert lid not in ids_retournes
        finally:
            _delete_liaison(app, lid)

    def test_entity_id_param_differente_retourne_vide(self, auth_client, ids, app):
        """entity_id appartenant à un autre propriétaire → liste vide."""
        _ensure_owner(app, ids)
        r = auth_client.get("/cartography/api/liaisons?entity_id=999999")
        assert r.get_json() == []


# ─────────────────────────────────────────────────────────────────────────────
# 3. PATCH /cartography/api/liaisons/<id>
# ─────────────────────────────────────────────────────────────────────────────

class TestPatchLiaisonNoAuth:
    """Sans session → 403."""

    @pytest.fixture
    def anon(self, app):
        return app.test_client()

    def test_sans_auth_retourne_403(self, anon):
        """PATCH /cartography/api/liaisons/1 sans session → 403."""
        r = anon.patch("/cartography/api/liaisons/1", json={"display_label": "test"})
        assert r.status_code == 403

    def test_sans_auth_contient_champ_error(self, anon):
        """La réponse 403 contient un champ 'error'."""
        r = anon.patch("/cartography/api/liaisons/1", json={})
        data = r.get_json()
        assert "error" in data


class TestPatchLiaisonAuth:
    """Avec session valide."""

    def test_liaison_inexistante_retourne_404(self, auth_client, ids, app):
        """PATCH sur une liaison inexistante → 404."""
        _ensure_owner(app, ids)
        r = auth_client.patch(
            "/cartography/api/liaisons/999999",
            json={"display_label": "test"},
        )
        assert r.status_code == 404

    def test_404_contient_champ_error(self, auth_client, ids, app):
        """La réponse 404 contient un champ 'error'."""
        _ensure_owner(app, ids)
        r = auth_client.patch("/cartography/api/liaisons/999999", json={})
        data = r.get_json()
        assert "error" in data

    def test_mise_a_jour_label_retourne_ok_true(self, auth_client, ids, app):
        """PATCH valide → réponse avec ok=True."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids)
        try:
            r = auth_client.patch(
                f"/cartography/api/liaisons/{lid}",
                json={"display_label": "Nouveau libellé"},
            )
            assert r.status_code == 200
            assert r.get_json().get("ok") is True
        finally:
            _delete_liaison(app, lid)

    def test_mise_a_jour_label_retourne_valeur(self, auth_client, ids, app):
        """PATCH retourne la nouvelle valeur de display_label."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids)
        try:
            r = auth_client.patch(
                f"/cartography/api/liaisons/{lid}",
                json={"display_label": "Label mis à jour"},
            )
            data = r.get_json()
            assert data.get("display_label") == "Label mis à jour"
        finally:
            _delete_liaison(app, lid)

    def test_mise_a_jour_label_persiste_en_db(self, auth_client, ids, app):
        """Après PATCH, le display_label est bien mis à jour en base."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids)
        try:
            auth_client.patch(
                f"/cartography/api/liaisons/{lid}",
                json={"display_label": "Label persisté"},
            )
            with app.app_context():
                l = CrossCartoLiaison.query.get(lid)
                assert l.display_label == "Label persisté"
        finally:
            _delete_liaison(app, lid)

    def test_label_vide_efface_le_libelle(self, auth_client, ids, app):
        """Envoyer display_label='' efface le libellé (→ null en DB)."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids, display_label="Ancien label")
        try:
            r = auth_client.patch(
                f"/cartography/api/liaisons/{lid}",
                json={"display_label": ""},
            )
            assert r.status_code == 200
            with app.app_context():
                l = CrossCartoLiaison.query.get(lid)
                assert l.display_label is None
        finally:
            _delete_liaison(app, lid)

    def test_label_null_efface_le_libelle(self, auth_client, ids, app):
        """Envoyer display_label=null efface le libellé."""
        _ensure_owner(app, ids)
        lid = _create_liaison(app, ids, display_label="Label à effacer")
        try:
            r = auth_client.patch(
                f"/cartography/api/liaisons/{lid}",
                json={"display_label": None},
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data.get("display_label") is None
        finally:
            _delete_liaison(app, lid)

    def test_liaison_inactive_non_patchable(self, auth_client, ids, app):
        """Une liaison is_active=False ne peut pas être modifiée (→ 404)."""
        _ensure_owner(app, ids)
        with app.app_context():
            from Code.extensions import db
            liaison = CrossCartoLiaison(
                extco_entity_id=ids["entity_id"],
                extco_activity_id=ids["activity_id"],
                origin_entity_id=ids["entity_id"],
                origin_activity_id=ids["activity_id"],
                is_active=False,
            )
            db.session.add(liaison)
            db.session.commit()
            lid = liaison.id

        try:
            r = auth_client.patch(
                f"/cartography/api/liaisons/{lid}",
                json={"display_label": "test"},
            )
            assert r.status_code == 404
        finally:
            _delete_liaison(app, lid)


# ─────────────────────────────────────────────────────────────────────────────
# 4. GET /activities/map/api/activities
# ─────────────────────────────────────────────────────────────────────────────

class TestMapApiActivities:
    """Endpoint utilitaire pour rafraîchir la liste d'activités après un switch de calque."""

    @pytest.fixture
    def anon(self, app):
        return app.test_client()

    def test_sans_entite_active_retourne_vide(self, anon):
        """Sans entité active en session → liste vide []."""
        r = anon.get("/activities/map/api/activities")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_avec_auth_retourne_200(self, auth_client):
        """Avec session et entité active → 200."""
        r = auth_client.get("/activities/map/api/activities")
        assert r.status_code == 200

    def test_retourne_liste_json(self, auth_client):
        """La réponse est une liste JSON."""
        r = auth_client.get("/activities/map/api/activities")
        assert isinstance(r.get_json(), list)

    def test_liste_contient_activite_seedee(self, auth_client, ids):
        """L'activité créée au seed apparaît dans la liste."""
        data = auth_client.get("/activities/map/api/activities").get_json()
        ids_retournes = [item["id"] for item in data]
        assert ids["activity_id"] in ids_retournes

    def test_chaque_element_a_champ_id(self, auth_client):
        """Chaque élément de la liste a un champ 'id'."""
        data = auth_client.get("/activities/map/api/activities").get_json()
        assert all("id" in item for item in data)

    def test_chaque_element_a_champ_name(self, auth_client):
        """Chaque élément de la liste a un champ 'name'."""
        data = auth_client.get("/activities/map/api/activities").get_json()
        assert all("name" in item for item in data)

    def test_activite_creee_apparait(self, auth_client, ids, app):
        """Une activité ajoutée dynamiquement est visible via cet endpoint."""
        with app.app_context():
            from Code.extensions import db
            act = Activities(
                entity_id=ids["entity_id"],
                name="Activité MapAPI Test 47",
            )
            db.session.add(act)
            db.session.commit()
            new_id = act.id

        try:
            data = auth_client.get("/activities/map/api/activities").get_json()
            ids_retournes = [item["id"] for item in data]
            assert new_id in ids_retournes
        finally:
            with app.app_context():
                from Code.extensions import db
                a = Activities.query.get(new_id)
                if a:
                    db.session.delete(a)
                    db.session.commit()
