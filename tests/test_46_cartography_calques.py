# tests/test_46_cartography_calques.py
"""
Couverture des routes Calques de l'éditeur OptiqCarto (/cartography/api/calques)
et de la resynchronisation forcée (/cartography/api/resync/<entity_id>).

Ces routes n'étaient pas testées dans test_14 (cartography_editor).

Routes couvertes :
  GET    /cartography/api/calques                     → liste des calques de l'entité active
  POST   /cartography/api/calques                     → créer un calque
  GET    /cartography/api/calques/<id>                → charger l'état JSON d'un calque
  PUT    /cartography/api/calques/<id>                → renommer / mettre à jour un calque
  DELETE /cartography/api/calques/<id>                → supprimer un calque
  POST   /cartography/api/calques/<id>/apply          → activer un calque (sync DB)
  POST   /cartography/api/calques/deactivate          → désactiver le calque actif
  POST   /cartography/api/resync/<entity_id>          → resync forcée depuis carto stockée
"""
import json
import pytest

pytestmark = pytest.mark.cartography_calques

# ── Diagramme de référence (utilisé comme état d'un calque) ──────────────────

SAMPLE_STATE = {
    "shapes": [
        {"id": "c1", "type": "process", "label": "Activité Calque",
         "x": 50, "y": 10, "w": 120, "h": 60},
    ],
    "bands": [{"id": "b1", "label": "Bande Calque", "height": 180}],
    "connections": [],
}

EMPTY_STATE = {"shapes": [], "bands": [], "connections": []}


# ── Helpers DB ────────────────────────────────────────────────────────────────

def _create_calque(app, entity_id, name="Calque Test", state=None):
    """Insère un calque en base et retourne son id."""
    with app.app_context():
        from Code.models.models import CartoCalque
        from Code.extensions import db
        s = json.dumps(state or SAMPLE_STATE, ensure_ascii=False)
        cal = CartoCalque(entity_id=entity_id, name=name, state_json=s)
        db.session.add(cal)
        db.session.commit()
        return cal.id


def _delete_calque(app, calque_id):
    """Supprime un calque en base (nettoyage)."""
    with app.app_context():
        from Code.models.models import CartoCalque
        from Code.extensions import db
        cal = CartoCalque.query.get(calque_id)
        if cal:
            db.session.delete(cal)
            db.session.commit()


def _calque_exists(app, calque_id):
    """Retourne True si le calque existe encore en base."""
    with app.app_context():
        from Code.models.models import CartoCalque
        return CartoCalque.query.get(calque_id) is not None


def _get_calque_name(app, calque_id):
    """Retourne le nom du calque en base."""
    with app.app_context():
        from Code.models.models import CartoCalque
        cal = CartoCalque.query.get(calque_id)
        return cal.name if cal else None


def _get_calque_state(app, calque_id):
    """Retourne l'état JSON parsé du calque en base."""
    with app.app_context():
        from Code.models.models import CartoCalque
        cal = CartoCalque.query.get(calque_id)
        return json.loads(cal.state_json) if cal else None


def _set_carto(app, ids, data):
    """Force optiqcarto_data sur l'entité de test (sans déclencher le sync)."""
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        entity = Entity.query.get(ids["entity_id"])
        entity.optiqcarto_data = json.dumps(data) if data is not None else None
        db.session.commit()


# ── Fixture de module : authentification + propriété de l'entité ──────────────

@pytest.fixture(scope="module", autouse=True)
def _setup_module(app, client, ids):
    """Ré-authentifie le client et garantit owner_id sur l'entité de test."""
    with app.app_context():
        from Code.models.models import User, Entity
        from Code.extensions import db
        user   = User.query.filter_by(email="test@devoptiq.com").first()
        entity = Entity.query.get(ids["entity_id"])
        entity.owner_id = ids["user_id"]
        db.session.commit()
        u_id   = user.id
        u_mail = user.email
        e_id   = entity.id

    with client.session_transaction() as sess:
        sess["user_id"]          = u_id
        sess["user_email"]       = u_mail
        sess["active_entity_id"] = e_id

    yield

    # Nettoyage : supprimer tous les calques du test et réinitialiser la carto
    with app.app_context():
        from Code.models.models import CartoCalque, Entity
        from Code.extensions import db
        CartoCalque.query.filter_by(entity_id=e_id).delete()
        entity = Entity.query.get(e_id)
        if entity:
            entity.optiqcarto_data = None
        db.session.commit()


# ── Fixture client anonyme ────────────────────────────────────────────────────

@pytest.fixture
def anon(app):
    """Client sans session (accès non-authentifié)."""
    return app.test_client()


# ===========================================================================
# 1. Accès sans authentification — toutes les routes renvoient 403
# ===========================================================================

class TestCalquesNoAuth:

    def test_list_calques_sans_auth_retourne_403(self, anon):
        r = anon.get("/cartography/api/calques")
        assert r.status_code == 403

    def test_create_calque_sans_auth_retourne_403(self, anon):
        r = anon.post("/cartography/api/calques", json={"name": "X", "state": EMPTY_STATE})
        assert r.status_code == 403

    def test_load_calque_sans_auth_retourne_403(self, anon):
        r = anon.get("/cartography/api/calques/1")
        assert r.status_code == 403

    def test_update_calque_sans_auth_retourne_403(self, anon):
        r = anon.put("/cartography/api/calques/1", json={"name": "Y"})
        assert r.status_code == 403

    def test_delete_calque_sans_auth_retourne_403(self, anon):
        r = anon.delete("/cartography/api/calques/1")
        assert r.status_code == 403

    def test_apply_calque_sans_auth_retourne_403(self, anon):
        r = anon.post("/cartography/api/calques/1/apply")
        assert r.status_code == 403

    def test_deactivate_sans_auth_retourne_403(self, anon):
        r = anon.post("/cartography/api/calques/deactivate")
        assert r.status_code == 403

    def test_resync_sans_auth_retourne_403(self, anon, ids):
        r = anon.post(f"/cartography/api/resync/{ids['entity_id']}")
        assert r.status_code == 403


# ===========================================================================
# 2. GET /cartography/api/calques — liste des calques
# ===========================================================================

class TestListCalques:

    def test_liste_vide_retourne_200(self, auth_client, app, ids):
        """Sans calques en base → 200 avec tableau vide."""
        # S'assurer qu'il n'y a pas de calques
        with app.app_context():
            from Code.models.models import CartoCalque
            from Code.extensions import db
            CartoCalque.query.filter_by(entity_id=ids["entity_id"]).delete()
            db.session.commit()
        r = auth_client.get("/cartography/api/calques")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_retourne_tableau_json(self, auth_client):
        """La réponse est toujours un tableau JSON."""
        r = auth_client.get("/cartography/api/calques")
        assert isinstance(r.get_json(), list)

    def test_calque_cree_apparait_dans_liste(self, auth_client, app, ids):
        """Un calque créé en base apparaît dans la liste."""
        cid = _create_calque(app, ids["entity_id"], "Calque Visible")
        try:
            r = auth_client.get("/cartography/api/calques")
            data = r.get_json()
            names = [c["name"] for c in data]
            assert "Calque Visible" in names
        finally:
            _delete_calque(app, cid)

    def test_liste_contient_id_et_name(self, auth_client, app, ids):
        """Chaque entrée expose les champs id et name."""
        cid = _create_calque(app, ids["entity_id"], "Calque Champs")
        try:
            r = auth_client.get("/cartography/api/calques")
            data = r.get_json()
            found = [c for c in data if c.get("id") == cid]
            assert len(found) == 1
            assert "id" in found[0]
            assert "name" in found[0]
        finally:
            _delete_calque(app, cid)

    def test_calque_supprime_absent_de_liste(self, auth_client, app, ids):
        """Après suppression en base, le calque disparaît de la liste."""
        cid = _create_calque(app, ids["entity_id"], "Calque À Supprimer Liste")
        _delete_calque(app, cid)
        r = auth_client.get("/cartography/api/calques")
        data = r.get_json()
        names = [c["name"] for c in data]
        assert "Calque À Supprimer Liste" not in names

    def test_content_type_json(self, auth_client):
        """Content-Type est application/json."""
        r = auth_client.get("/cartography/api/calques")
        assert r.content_type.startswith("application/json")


# ===========================================================================
# 3. POST /cartography/api/calques — créer un calque
# ===========================================================================

class TestCreateCalque:

    def test_creation_valide_retourne_200(self, auth_client):
        """Création avec name + state valides → 200."""
        r = auth_client.post("/cartography/api/calques", json={
            "name": "Calque Créé Test",
            "state": SAMPLE_STATE,
        })
        assert r.status_code == 200

    def test_creation_reponse_contient_ok_true(self, auth_client, app, ids):
        """La réponse contient ok=True."""
        r = auth_client.post("/cartography/api/calques", json={
            "name": "Calque OK Test",
            "state": EMPTY_STATE,
        })
        data = r.get_json()
        assert data.get("ok") is True
        _delete_calque(app, data.get("id"))

    def test_creation_reponse_contient_id(self, auth_client, app, ids):
        """La réponse contient le champ id du calque créé."""
        r = auth_client.post("/cartography/api/calques", json={
            "name": "Calque ID Test",
            "state": EMPTY_STATE,
        })
        data = r.get_json()
        assert "id" in data
        assert isinstance(data["id"], int)
        _delete_calque(app, data["id"])

    def test_creation_reponse_contient_name(self, auth_client, app, ids):
        """La réponse contient le name du calque."""
        r = auth_client.post("/cartography/api/calques", json={
            "name": "Calque Name Test",
            "state": EMPTY_STATE,
        })
        data = r.get_json()
        assert data.get("name") == "Calque Name Test"
        _delete_calque(app, data.get("id"))

    def test_creation_persiste_en_db(self, auth_client, app, ids):
        """Après création, le calque est bien en base."""
        r = auth_client.post("/cartography/api/calques", json={
            "name": "Calque DB Persist",
            "state": SAMPLE_STATE,
        })
        cid = r.get_json().get("id")
        assert _calque_exists(app, cid)
        _delete_calque(app, cid)

    def test_creation_sans_name_retourne_400(self, auth_client):
        """Sans name → 400."""
        r = auth_client.post("/cartography/api/calques", json={"state": EMPTY_STATE})
        assert r.status_code == 400

    def test_creation_name_vide_retourne_400(self, auth_client):
        """name vide → 400."""
        r = auth_client.post("/cartography/api/calques", json={
            "name": "   ",
            "state": EMPTY_STATE,
        })
        assert r.status_code == 400

    def test_creation_sans_state_retourne_400(self, auth_client):
        """Sans state → 400."""
        r = auth_client.post("/cartography/api/calques", json={"name": "Calque Sans État"})
        assert r.status_code == 400

    def test_creation_etat_vide_accepte(self, auth_client, app, ids):
        """Un état vide (shapes/bands/connections vides) est valide."""
        r = auth_client.post("/cartography/api/calques", json={
            "name": "Calque État Vide",
            "state": EMPTY_STATE,
        })
        assert r.status_code == 200
        _delete_calque(app, r.get_json().get("id"))


# ===========================================================================
# 4. GET /cartography/api/calques/<id> — charger un calque
# ===========================================================================

class TestLoadCalque:

    def test_chargement_valide_retourne_200(self, auth_client, app, ids):
        """Calque existant → 200."""
        cid = _create_calque(app, ids["entity_id"], "Calque Chargeable")
        try:
            r = auth_client.get(f"/cartography/api/calques/{cid}")
            assert r.status_code == 200
        finally:
            _delete_calque(app, cid)

    def test_chargement_retourne_etat_json(self, auth_client, app, ids):
        """La réponse est l'état JSON du calque."""
        cid = _create_calque(app, ids["entity_id"], "Calque État JSON", state=SAMPLE_STATE)
        try:
            r = auth_client.get(f"/cartography/api/calques/{cid}")
            assert r.status_code == 200
            data = r.get_json()
            assert "shapes" in data
            assert "bands" in data
            assert "connections" in data
        finally:
            _delete_calque(app, cid)

    def test_chargement_etat_correspond_au_cree(self, auth_client, app, ids):
        """L'état retourné correspond exactement à l'état stocké."""
        cid = _create_calque(app, ids["entity_id"], "Calque État Exact", state=SAMPLE_STATE)
        try:
            r = auth_client.get(f"/cartography/api/calques/{cid}")
            data = r.get_json()
            assert len(data["shapes"]) == 1
            assert data["shapes"][0]["label"] == "Activité Calque"
        finally:
            _delete_calque(app, cid)

    def test_chargement_inexistant_retourne_404(self, auth_client):
        """Calque inexistant → 404."""
        r = auth_client.get("/cartography/api/calques/999999")
        assert r.status_code == 404

    def test_chargement_content_type_json(self, auth_client, app, ids):
        """Content-Type est application/json."""
        cid = _create_calque(app, ids["entity_id"], "Calque CT JSON")
        try:
            r = auth_client.get(f"/cartography/api/calques/{cid}")
            assert r.content_type.startswith("application/json")
        finally:
            _delete_calque(app, cid)


# ===========================================================================
# 5. PUT /cartography/api/calques/<id> — mettre à jour un calque
# ===========================================================================

class TestUpdateCalque:

    def test_update_nom_succes_retourne_200(self, auth_client, app, ids):
        """Renommage valide → 200."""
        cid = _create_calque(app, ids["entity_id"], "Avant Renommage")
        try:
            r = auth_client.put(f"/cartography/api/calques/{cid}", json={"name": "Après Renommage"})
            assert r.status_code == 200
        finally:
            _delete_calque(app, cid)

    def test_update_ok_true_dans_reponse(self, auth_client, app, ids):
        """La réponse contient ok=True."""
        cid = _create_calque(app, ids["entity_id"], "Calque Update OK")
        try:
            r = auth_client.put(f"/cartography/api/calques/{cid}", json={"name": "Nouveau Nom OK"})
            assert r.get_json().get("ok") is True
        finally:
            _delete_calque(app, cid)

    def test_update_nom_persiste_en_db(self, auth_client, app, ids):
        """Après PUT, le nouveau nom est en base."""
        cid = _create_calque(app, ids["entity_id"], "Nom Avant Update")
        try:
            auth_client.put(f"/cartography/api/calques/{cid}", json={"name": "Nom Après Update"})
            assert _get_calque_name(app, cid) == "Nom Après Update"
        finally:
            _delete_calque(app, cid)

    def test_update_state_persiste_en_db(self, auth_client, app, ids):
        """Après PUT avec state, l'état est mis à jour en base."""
        cid = _create_calque(app, ids["entity_id"], "Calque State Update", state=EMPTY_STATE)
        try:
            auth_client.put(f"/cartography/api/calques/{cid}", json={
                "state": SAMPLE_STATE,
            })
            stored = _get_calque_state(app, cid)
            assert stored is not None
            assert len(stored["shapes"]) == 1
        finally:
            _delete_calque(app, cid)

    def test_update_nom_vide_ne_change_pas_le_nom(self, auth_client, app, ids):
        """Un nom vide (ou whitespace) dans PUT ne modifie pas le nom existant."""
        cid = _create_calque(app, ids["entity_id"], "Nom Stable")
        try:
            auth_client.put(f"/cartography/api/calques/{cid}", json={"name": ""})
            assert _get_calque_name(app, cid) == "Nom Stable"
        finally:
            _delete_calque(app, cid)

    def test_update_inexistant_retourne_404(self, auth_client):
        """PUT sur calque inexistant → 404."""
        r = auth_client.put("/cartography/api/calques/999999", json={"name": "Fantôme"})
        assert r.status_code == 404


# ===========================================================================
# 6. DELETE /cartography/api/calques/<id> — supprimer un calque
# ===========================================================================

class TestDeleteCalque:

    def test_delete_succes_retourne_200(self, auth_client, app, ids):
        """DELETE sur calque existant → 200."""
        cid = _create_calque(app, ids["entity_id"], "Calque À Supprimer")
        r = auth_client.delete(f"/cartography/api/calques/{cid}")
        assert r.status_code == 200

    def test_delete_ok_true_dans_reponse(self, auth_client, app, ids):
        """La réponse contient ok=True."""
        cid = _create_calque(app, ids["entity_id"], "Calque Delete OK")
        r = auth_client.delete(f"/cartography/api/calques/{cid}")
        assert r.get_json().get("ok") is True

    def test_delete_supprime_de_db(self, auth_client, app, ids):
        """Après DELETE, le calque n'existe plus en base."""
        cid = _create_calque(app, ids["entity_id"], "Calque Supprimé DB")
        auth_client.delete(f"/cartography/api/calques/{cid}")
        assert not _calque_exists(app, cid)

    def test_delete_inexistant_retourne_404(self, auth_client):
        """DELETE sur calque inexistant → 404."""
        r = auth_client.delete("/cartography/api/calques/999999")
        assert r.status_code == 404

    def test_double_delete_retourne_404(self, auth_client, app, ids):
        """Supprimer deux fois le même calque → 404 au second appel."""
        cid = _create_calque(app, ids["entity_id"], "Calque Double Delete")
        auth_client.delete(f"/cartography/api/calques/{cid}")
        r = auth_client.delete(f"/cartography/api/calques/{cid}")
        assert r.status_code == 404

    def test_delete_content_type_json(self, auth_client, app, ids):
        """La réponse DELETE est en JSON."""
        cid = _create_calque(app, ids["entity_id"], "Calque CT Delete")
        r = auth_client.delete(f"/cartography/api/calques/{cid}")
        assert r.content_type.startswith("application/json")


# ===========================================================================
# 7. POST /cartography/api/calques/<id>/apply — activer un calque
# ===========================================================================

class TestApplyCalque:

    def test_apply_succes_retourne_200(self, auth_client, app, ids):
        """Activation d'un calque valide → 200."""
        cid = _create_calque(app, ids["entity_id"], "Calque Apply Test", state=EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/calques/{cid}/apply")
            assert r.status_code == 200
        finally:
            _delete_calque(app, cid)

    def test_apply_reponse_ok_true(self, auth_client, app, ids):
        """La réponse contient ok=True."""
        cid = _create_calque(app, ids["entity_id"], "Calque Apply OK", state=EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/calques/{cid}/apply")
            assert r.get_json().get("ok") is True
        finally:
            _delete_calque(app, cid)

    def test_apply_inexistant_retourne_404(self, auth_client):
        """Activation d'un calque inexistant → 404."""
        r = auth_client.post("/cartography/api/calques/999999/apply")
        assert r.status_code == 404

    def test_apply_avec_state_non_vide(self, auth_client, app, ids):
        """Activation d'un calque avec shapes → 200 (sync DB exécutée)."""
        cid = _create_calque(app, ids["entity_id"], "Calque Apply Shapes", state=EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/calques/{cid}/apply")
            assert r.status_code == 200
        finally:
            _delete_calque(app, cid)

    def test_apply_content_type_json(self, auth_client, app, ids):
        """La réponse est en JSON."""
        cid = _create_calque(app, ids["entity_id"], "Calque Apply CT", state=EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/calques/{cid}/apply")
            assert r.content_type.startswith("application/json")
        finally:
            _delete_calque(app, cid)


# ===========================================================================
# 8. POST /cartography/api/calques/deactivate — désactiver le calque actif
# ===========================================================================

class TestDeactivateCalque:

    def test_deactivate_sans_carto_retourne_200(self, auth_client, app, ids):
        """Désactivation sans carto stockée → 200."""
        _set_carto(app, ids, None)
        r = auth_client.post("/cartography/api/calques/deactivate")
        assert r.status_code == 200

    def test_deactivate_reponse_ok_true(self, auth_client, app, ids):
        """La réponse contient ok=True."""
        _set_carto(app, ids, None)
        r = auth_client.post("/cartography/api/calques/deactivate")
        assert r.get_json().get("ok") is True

    def test_deactivate_avec_carto_stockee_retourne_200(self, auth_client, app, ids):
        """Désactivation avec carto stockée (resync depuis carto de base) → 200."""
        _set_carto(app, ids, EMPTY_STATE)
        try:
            r = auth_client.post("/cartography/api/calques/deactivate")
            assert r.status_code == 200
        finally:
            _set_carto(app, ids, None)

    def test_deactivate_supprime_calque_actif_de_session(self, auth_client, app, ids):
        """Après désactivation, active_calque_id n'est plus en session."""
        cid = _create_calque(app, ids["entity_id"], "Calque Session Deactivate", state=EMPTY_STATE)
        try:
            # Activer d'abord le calque
            auth_client.post(f"/cartography/api/calques/{cid}/apply")
            # Désactiver
            auth_client.post("/cartography/api/calques/deactivate")
            # Vérifier que la session ne contient plus l'id du calque actif
            with auth_client.session_transaction() as sess:
                assert "active_calque_id" not in sess
        finally:
            _delete_calque(app, cid)

    def test_deactivate_content_type_json(self, auth_client, app, ids):
        """La réponse est en JSON."""
        _set_carto(app, ids, None)
        r = auth_client.post("/cartography/api/calques/deactivate")
        assert r.content_type.startswith("application/json")


# ===========================================================================
# 9. POST /cartography/api/resync/<entity_id> — resynchronisation forcée
# ===========================================================================

class TestApiResync:

    def test_resync_sans_carto_retourne_400(self, auth_client, app, ids):
        """Entité sans carto stockée → 400."""
        _set_carto(app, ids, None)
        r = auth_client.post(f"/cartography/api/resync/{ids['entity_id']}")
        assert r.status_code == 400

    def test_resync_avec_carto_retourne_200(self, auth_client, app, ids):
        """Entité avec carto stockée → 200."""
        _set_carto(app, ids, EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/resync/{ids['entity_id']}")
            assert r.status_code == 200
        finally:
            _set_carto(app, ids, None)

    def test_resync_reponse_ok_true(self, auth_client, app, ids):
        """La réponse contient ok=True."""
        _set_carto(app, ids, EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/resync/{ids['entity_id']}")
            assert r.get_json().get("ok") is True
        finally:
            _set_carto(app, ids, None)

    def test_resync_reponse_contient_entity_name(self, auth_client, app, ids):
        """La réponse contient le nom de l'entité."""
        _set_carto(app, ids, EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/resync/{ids['entity_id']}")
            assert "entity" in r.get_json()
        finally:
            _set_carto(app, ids, None)

    def test_resync_entity_inconnue_retourne_404(self, auth_client):
        """Entité inexistante → 404."""
        r = auth_client.post("/cartography/api/resync/999999")
        assert r.status_code == 404

    def test_resync_avec_shapes_carto_retourne_200(self, auth_client, app, ids):
        """Resync avec une carto comportant une activité → 200 (sans erreur de sync)."""
        _set_carto(app, ids, EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/resync/{ids['entity_id']}")
            assert r.status_code == 200
        finally:
            _set_carto(app, ids, None)

    def test_resync_error_retourne_json(self, auth_client, app, ids):
        """La réponse d'une resync réussie est en JSON."""
        _set_carto(app, ids, EMPTY_STATE)
        try:
            r = auth_client.post(f"/cartography/api/resync/{ids['entity_id']}")
            assert r.content_type.startswith("application/json")
        finally:
            _set_carto(app, ids, None)
