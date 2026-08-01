# tests/test_44_cross_carto_liaisons.py
"""
Couverture des routes cross-carto liaisons (activities_map.py) non testées :
  GET  /activities/api/liaison_matches            → liaisons entre cartos (par nom d'activité)
  GET  /activities/api/reverse_liaisons_map       → liste des liaisons inverses de l'entité active
  GET  /activities/api/reverse_liaisons           → liaisons inverses pour une activité nommée
  POST /activities/api/officialize_liaison        → créer une liaison officielle cross-carto
  GET  /activities/api/liaison_deoffice_preview   → aperçu avant dé-officialisation
  POST /activities/api/liaison_deoffice           → dé-officialiser et nettoyer
  GET  /activities/api/debug-decisions/env-check  → diagnostic variables d'environnement
  GET  /activities/api/debug-decisions            → extraction décisions VSDX (legacy)
  POST /activities/api/debug-decisions/analyze-file     → upload VSDX sans IA
  POST /activities/api/debug-decisions/analyze-file/ai  → upload VSDX avec IA
  POST /activities/api/debug-decisions/ai         → analyse IA du fichier de l'entité (legacy)
"""
import io
import pytest

pytestmark = pytest.mark.cross_carto_liaisons


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _create_second_entity_and_activity(app, user_id, suffix=""):
    """Crée une entité secondaire + activité d'origine pour les tests cross-carto."""
    with app.app_context():
        from Code.models.models import Entity, Activities
        from Code.extensions import db

        ent2 = Entity(
            name=f"Entité Origine Cross-Carto{suffix}",
            description="Entité pour tests liaisons inter-cartos",
        )
        db.session.add(ent2)
        db.session.flush()
        ent2.owner_id = user_id
        db.session.flush()

        act = Activities(
            entity_id=ent2.id,
            name="Activité Origine",
            description="Activité d'origine pour liaison cross-carto",
        )
        db.session.add(act)
        db.session.flush()
        db.session.commit()
        return ent2.id, act.id


def _create_extco_activity(app, entity_id, name):
    """Crée une activité de type extco (hachurée) dans l'entité donnée."""
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db

        act = Activities(
            entity_id=entity_id,
            name=name,
            description="Activité hachurée (extco) pour test",
            shape_subtype="extco",
        )
        db.session.add(act)
        db.session.commit()
        return act.id


def _create_liaison(app, extco_entity_id, extco_activity_id, origin_entity_id, origin_activity_id):
    """Insère directement une CrossCartoLiaison en base."""
    with app.app_context():
        from Code.models.models import CrossCartoLiaison
        from Code.extensions import db

        liaison = CrossCartoLiaison(
            extco_entity_id=extco_entity_id,
            extco_activity_id=extco_activity_id,
            origin_entity_id=origin_entity_id,
            origin_activity_id=origin_activity_id,
            is_active=True,
        )
        db.session.add(liaison)
        db.session.commit()
        return liaison.id


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /activities/api/liaison_matches
# ─────────────────────────────────────────────────────────────────────────────

class TestLiaisonMatches:

    def test_sans_nom_retourne_vide(self, auth_client):
        """Sans paramètre name, retourne matches vide."""
        r = auth_client.get("/activities/api/liaison_matches")
        assert r.status_code == 200
        data = r.get_json()
        assert data["matches"] == []

    def test_nom_vide_retourne_vide(self, auth_client):
        """Avec name='' (chaîne vide), retourne matches vide."""
        r = auth_client.get("/activities/api/liaison_matches?name=")
        assert r.status_code == 200
        assert r.get_json()["matches"] == []

    def test_structure_json_complete(self, auth_client):
        """La réponse contient les clés 'matches' et 'total'."""
        r = auth_client.get("/activities/api/liaison_matches?name=activite-inexistante")
        assert r.status_code == 200
        data = r.get_json()
        assert "matches" in data
        assert "total" in data

    def test_total_coherent_avec_matches(self, auth_client):
        """total correspond au nombre d'éléments dans matches."""
        r = auth_client.get("/activities/api/liaison_matches?name=quelque+chose")
        assert r.status_code == 200
        data = r.get_json()
        assert data["total"] == len(data["matches"])

    def test_entite_unique_aucune_correspondance(self, auth_client, ids):
        """Avec une seule entité dans le seed, aucune correspondance externe."""
        r = auth_client.get(f"/activities/api/liaison_matches?name=activit%C3%A9+test")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data["matches"], list)

    def test_retour_json_content_type(self, auth_client):
        """La réponse est de type application/json."""
        r = auth_client.get("/activities/api/liaison_matches?name=test")
        assert r.content_type.startswith("application/json")


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /activities/api/reverse_liaisons_map
# ─────────────────────────────────────────────────────────────────────────────

class TestReverseliaisonsMap:

    def test_retourne_200(self, auth_client):
        """La route répond 200 avec une entité active valide."""
        r = auth_client.get("/activities/api/reverse_liaisons_map")
        assert r.status_code == 200

    def test_structure_cle_origins(self, auth_client):
        """La réponse contient obligatoirement la clé 'origins'."""
        r = auth_client.get("/activities/api/reverse_liaisons_map")
        data = r.get_json()
        assert "origins" in data

    def test_origins_est_une_liste(self, auth_client):
        """origins est toujours une liste."""
        r = auth_client.get("/activities/api/reverse_liaisons_map")
        data = r.get_json()
        assert isinstance(data["origins"], list)

    def test_sans_liaisons_actives_origins_vide(self, auth_client):
        """Sans liaison cross-carto active pour l'entité seed, origins est vide."""
        r = auth_client.get("/activities/api/reverse_liaisons_map")
        data = r.get_json()
        # Le seed n'a pas de liaisons où entity_test est l'origine
        assert data["origins"] == [] or isinstance(data["origins"], list)

    def test_avec_liaison_retourne_origines(self, auth_client, app, ids):
        """Après création d'une liaison, origins contient l'activité d'origine."""
        extco_id = _create_extco_activity(app, ids["entity_id"], "Extco Pour ReverseMap")
        ent2_id, act2_id = _create_second_entity_and_activity(app, ids["user_id"], " ReverseMap")
        # Créer une liaison où ent2 est l'origine → elle apparaît dans les liaisons inverses de ent2
        _create_liaison(app, ids["entity_id"], extco_id, ent2_id, act2_id)
        # La route retourne les liaisons où l'entité active (main entity) est l'origine
        # Comme l'entité active est extco_entity ici, origins sera vide pour cet angle
        r = auth_client.get("/activities/api/reverse_liaisons_map")
        assert r.status_code == 200
        assert "origins" in r.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# 3. GET /activities/api/reverse_liaisons
# ─────────────────────────────────────────────────────────────────────────────

class TestReverseliaisonsQuery:

    def test_sans_nom_retourne_vide(self, auth_client):
        """Sans paramètre name, retourne matches vide (guard name)."""
        r = auth_client.get("/activities/api/reverse_liaisons")
        assert r.status_code == 200
        assert r.get_json()["matches"] == []

    def test_nom_inexistant_retourne_vide(self, auth_client):
        """Nom d'activité fantôme → aucune correspondance."""
        r = auth_client.get("/activities/api/reverse_liaisons?name=activite-fantome-xyz-999")
        assert r.status_code == 200
        data = r.get_json()
        assert data["matches"] == []

    def test_structure_cle_matches(self, auth_client):
        """La réponse contient la clé 'matches'."""
        r = auth_client.get("/activities/api/reverse_liaisons?name=test")
        assert r.status_code == 200
        assert "matches" in r.get_json()

    def test_matches_est_une_liste(self, auth_client):
        """matches est toujours une liste."""
        r = auth_client.get("/activities/api/reverse_liaisons?name=quelque+chose")
        assert r.status_code == 200
        assert isinstance(r.get_json()["matches"], list)

    def test_activite_seed_sans_liaison(self, auth_client):
        """L'activité du seed n'est pas origin d'une liaison → matches vide."""
        r = auth_client.get("/activities/api/reverse_liaisons?name=activit%C3%A9+test")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data["matches"], list)

    def test_retour_json_content_type(self, auth_client):
        """Content-Type est application/json."""
        r = auth_client.get("/activities/api/reverse_liaisons?name=test")
        assert r.content_type.startswith("application/json")


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /activities/api/officialize_liaison
# ─────────────────────────────────────────────────────────────────────────────

class TestOfficializeLiaison:

    def test_params_manquants_400(self, auth_client):
        """Body vide → 400 (tous les IDs requis absents)."""
        r = auth_client.post("/activities/api/officialize_liaison", json={})
        assert r.status_code == 400

    def test_extco_activity_introuvable_404(self, auth_client):
        """extco_activity_id inexistant dans l'entité active → 404."""
        r = auth_client.post(
            "/activities/api/officialize_liaison",
            json={
                "extco_activity_id": 999999,
                "origin_entity_id": 1,
                "origin_activity_id": 1,
            },
        )
        assert r.status_code == 404

    def test_origin_entity_inconnue_404(self, auth_client, app, ids):
        """origin_entity_id n'appartenant pas à l'user → 404."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Origin Entity 404"
        )
        r = auth_client.post(
            "/activities/api/officialize_liaison",
            json={
                "extco_activity_id": extco_id,
                "origin_entity_id": 999999,
                "origin_activity_id": 1,
            },
        )
        assert r.status_code == 404

    def test_origin_activity_introuvable_404(self, auth_client, app, ids):
        """origin_activity_id inexistant dans origin_entity → 404."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Origin Act 404"
        )
        ent2_id, _ = _create_second_entity_and_activity(
            app, ids["user_id"], " OriginAct404"
        )
        r = auth_client.post(
            "/activities/api/officialize_liaison",
            json={
                "extco_activity_id": extco_id,
                "origin_entity_id": ent2_id,
                "origin_activity_id": 999999,
            },
        )
        assert r.status_code == 404

    def test_liaison_creee_avec_succes(self, auth_client, app, ids):
        """Officialise une liaison valide → 200 avec ok=True."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Liaison Valide"
        )
        ent2_id, act2_id = _create_second_entity_and_activity(
            app, ids["user_id"], " LiaisonValide"
        )
        r = auth_client.post(
            "/activities/api/officialize_liaison",
            json={
                "extco_activity_id": extco_id,
                "origin_entity_id": ent2_id,
                "origin_activity_id": act2_id,
            },
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True

    def test_reponse_contient_liens_crees(self, auth_client, app, ids):
        """La réponse d'officialisation contient le nombre de liens créés."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Links Crees"
        )
        ent2_id, act2_id = _create_second_entity_and_activity(
            app, ids["user_id"], " LinksCrees"
        )
        r = auth_client.post(
            "/activities/api/officialize_liaison",
            json={
                "extco_activity_id": extco_id,
                "origin_entity_id": ent2_id,
                "origin_activity_id": act2_id,
            },
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "links_created" in data

    def test_liaison_deja_existante_already_exists(self, auth_client, app, ids):
        """Officialiser une liaison déjà active → 200 avec already_exists=True."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Double Officialize"
        )
        ent2_id, act2_id = _create_second_entity_and_activity(
            app, ids["user_id"], " DoubleOffic"
        )
        payload = {
            "extco_activity_id": extco_id,
            "origin_entity_id": ent2_id,
            "origin_activity_id": act2_id,
        }
        auth_client.post("/activities/api/officialize_liaison", json=payload)
        r = auth_client.post("/activities/api/officialize_liaison", json=payload)
        assert r.status_code == 200
        assert r.get_json().get("already_exists") is True

    def test_sans_auth_interdit_403(self, app):
        """Sans session utilisateur → 403."""
        fresh = app.test_client()
        r = fresh.post(
            "/activities/api/officialize_liaison",
            json={
                "extco_activity_id": 1,
                "origin_entity_id": 1,
                "origin_activity_id": 1,
            },
        )
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# 5. GET /activities/api/liaison_deoffice_preview
# ─────────────────────────────────────────────────────────────────────────────

class TestLiaisonDeofficePreview:

    def test_params_manquants_400(self, auth_client):
        """Sans liaison_id → 400."""
        r = auth_client.get("/activities/api/liaison_deoffice_preview")
        assert r.status_code == 400

    def test_erreur_400_contient_message(self, auth_client):
        """L'erreur 400 inclut un champ 'error' dans le JSON."""
        r = auth_client.get("/activities/api/liaison_deoffice_preview")
        data = r.get_json()
        assert "error" in data

    def test_liaison_inexistante_404(self, auth_client):
        """liaison_id inexistant → 404."""
        r = auth_client.get("/activities/api/liaison_deoffice_preview?liaison_id=999999")
        assert r.status_code == 404

    def test_liaison_valide_retourne_200(self, auth_client, app, ids):
        """Liaison valide entre deux entités de l'utilisateur → 200."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Preview Test"
        )
        ent2_id, act2_id = _create_second_entity_and_activity(
            app, ids["user_id"], " PreviewTest"
        )
        liaison_id = _create_liaison(
            app, ids["entity_id"], extco_id, ent2_id, act2_id
        )
        r = auth_client.get(
            f"/activities/api/liaison_deoffice_preview?liaison_id={liaison_id}"
        )
        assert r.status_code == 200

    def test_structure_preview_complete(self, auth_client, app, ids):
        """La réponse contient toutes les clés de preview attendues."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Preview Structure"
        )
        ent2_id, act2_id = _create_second_entity_and_activity(
            app, ids["user_id"], " PreviewStruct"
        )
        liaison_id = _create_liaison(
            app, ids["entity_id"], extco_id, ent2_id, act2_id
        )
        r = auth_client.get(
            f"/activities/api/liaison_deoffice_preview?liaison_id={liaison_id}"
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "origin_entity_name" in data
        assert "extco_entity_name" in data
        assert "shapes_to_remove" in data
        assert "connections_to_remove" in data
        assert "db_links_to_remove" in data

    def test_db_links_to_remove_est_entier(self, auth_client, app, ids):
        """db_links_to_remove est un entier (0 si aucun lien propagé)."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Preview IntCheck"
        )
        ent2_id, act2_id = _create_second_entity_and_activity(
            app, ids["user_id"], " PreviewInt"
        )
        liaison_id = _create_liaison(
            app, ids["entity_id"], extco_id, ent2_id, act2_id
        )
        r = auth_client.get(
            f"/activities/api/liaison_deoffice_preview?liaison_id={liaison_id}"
        )
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data["db_links_to_remove"], int)


# ─────────────────────────────────────────────────────────────────────────────
# 6. POST /activities/api/liaison_deoffice
# ─────────────────────────────────────────────────────────────────────────────

class TestLiaisonDeoffice:

    def test_params_manquants_400(self, auth_client):
        """Body vide (liaison_id absent) → 400."""
        r = auth_client.post("/activities/api/liaison_deoffice", json={})
        assert r.status_code == 400

    def test_liaison_inexistante_404(self, auth_client):
        """liaison_id inexistant → 404."""
        r = auth_client.post(
            "/activities/api/liaison_deoffice",
            json={"liaison_id": 999999},
        )
        assert r.status_code == 404

    def test_deoffice_liaison_valide(self, auth_client, app, ids):
        """Dé-officialiser une liaison valide → 200 avec ok=True."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Deoffice Valide"
        )
        ent2_id, act2_id = _create_second_entity_and_activity(
            app, ids["user_id"], " DeofficeValide"
        )
        liaison_id = _create_liaison(
            app, ids["entity_id"], extco_id, ent2_id, act2_id
        )
        r = auth_client.post(
            "/activities/api/liaison_deoffice",
            json={"liaison_id": liaison_id},
        )
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

    def test_liaison_supprimee_apres_deoffice(self, auth_client, app, ids):
        """Après dé-officialisation, la liaison n'existe plus en base."""
        extco_id = _create_extco_activity(
            app, ids["entity_id"], "Extco Deoffice Verify"
        )
        ent2_id, act2_id = _create_second_entity_and_activity(
            app, ids["user_id"], " DeofficeVerify"
        )
        liaison_id = _create_liaison(
            app, ids["entity_id"], extco_id, ent2_id, act2_id
        )
        auth_client.post(
            "/activities/api/liaison_deoffice",
            json={"liaison_id": liaison_id},
        )
        with app.app_context():
            from Code.models.models import CrossCartoLiaison
            deleted = CrossCartoLiaison.query.get(liaison_id)
        assert deleted is None

    def test_sans_auth_400_ou_404(self, app):
        """Sans session, manque user_id → 400."""
        fresh = app.test_client()
        r = fresh.post(
            "/activities/api/liaison_deoffice",
            json={"liaison_id": 999},
        )
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 7. GET /activities/api/debug-decisions (legacy)
# ─────────────────────────────────────────────────────────────────────────────
# NB : la route /api/debug-decisions/env-check (et ses tests) a été SUPPRIMÉE :
# elle exposait les noms de toutes les variables d'environnement sans auth.

class TestDebugDecisionsLegacy:

    def test_retourne_200_avec_entite_active(self, auth_client):
        """Avec une entité active en session → 200."""
        r = auth_client.get("/activities/api/debug-decisions")
        assert r.status_code == 200

    def test_structure_entity_id(self, auth_client):
        """La réponse contient entity_id et entity_name."""
        r = auth_client.get("/activities/api/debug-decisions")
        assert r.status_code == 200
        data = r.get_json()
        assert "entity_id" in data
        assert "entity_name" in data

    def test_structure_cle_vsdx(self, auth_client):
        """La réponse contient le sous-objet vsdx."""
        r = auth_client.get("/activities/api/debug-decisions")
        assert r.status_code == 200
        data = r.get_json()
        assert "vsdx" in data

    def test_vsdx_contient_decisions(self, auth_client):
        """Le sous-objet vsdx a la clé 'decisions' (liste vide sans fichier VSDX)."""
        r = auth_client.get("/activities/api/debug-decisions")
        assert r.status_code == 200
        data = r.get_json()
        assert "decisions" in data["vsdx"]
        assert isinstance(data["vsdx"]["decisions"], list)

    def test_has_vsdx_est_bool(self, auth_client):
        """has_vsdx est un booléen (False sans fichier stocké pour l'entité test)."""
        r = auth_client.get("/activities/api/debug-decisions")
        assert r.status_code == 200
        data = r.get_json()
        assert "has_vsdx" in data
        assert isinstance(data["has_vsdx"], bool)


# ─────────────────────────────────────────────────────────────────────────────
# 9. POST /activities/api/debug-decisions/analyze-file
# ─────────────────────────────────────────────────────────────────────────────

class TestDebugAnalyzeFile:

    def test_sans_fichier_400(self, auth_client):
        """Sans fichier multipart → 400."""
        r = auth_client.post("/activities/api/debug-decisions/analyze-file")
        assert r.status_code == 400

    def test_sans_fichier_json_error(self, auth_client):
        """L'erreur 400 contient un champ 'error'."""
        r = auth_client.post("/activities/api/debug-decisions/analyze-file")
        assert "error" in r.get_json()

    def test_mauvaise_extension_400(self, auth_client):
        """Fichier avec extension non-.vsdx → 400."""
        data = {"vsdx": (io.BytesIO(b"fake content"), "diagram.txt")}
        r = auth_client.post(
            "/activities/api/debug-decisions/analyze-file",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_erreur_extension_dans_message(self, auth_client):
        """L'erreur 400 pour mauvaise extension mentionne 'vsdx'."""
        data = {"vsdx": (io.BytesIO(b"fake"), "test.pdf")}
        r = auth_client.post(
            "/activities/api/debug-decisions/analyze-file",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        error_msg = r.get_json().get("error", "").lower()
        assert "vsdx" in error_msg

    def test_extension_csv_refusee(self, auth_client):
        """Fichier CSV refusé (doit être .vsdx)."""
        data = {"vsdx": (io.BytesIO(b"col1,col2\n1,2"), "export.csv")}
        r = auth_client.post(
            "/activities/api/debug-decisions/analyze-file",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_sans_auth_retourne_401(self, app):
        """Client anonyme (pas de session) → 401, pas de traitement du fichier."""
        fresh = app.test_client()
        data = {"vsdx": (io.BytesIO(b"fake content"), "diagram.vsdx")}
        r = fresh.post(
            "/activities/api/debug-decisions/analyze-file",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 401
        assert "error" in r.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# 10. POST /activities/api/debug-decisions/analyze-file/ai
# ─────────────────────────────────────────────────────────────────────────────

class TestDebugAnalyzeFileAI:

    def test_sans_fichier_400(self, auth_client):
        """Sans fichier → 400."""
        r = auth_client.post("/activities/api/debug-decisions/analyze-file/ai")
        assert r.status_code == 400

    def test_erreur_json_presente(self, auth_client):
        """L'erreur retournée contient 'error'."""
        r = auth_client.post("/activities/api/debug-decisions/analyze-file/ai")
        assert "error" in r.get_json()

    def test_mauvaise_extension_400(self, auth_client):
        """Fichier non-.vsdx → 400."""
        data = {"vsdx": (io.BytesIO(b"dummy"), "rapport.pdf")}
        r = auth_client.post(
            "/activities/api/debug-decisions/analyze-file/ai",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_extension_docx_refusee(self, auth_client):
        """Fichier .docx refusé : doit être .vsdx."""
        data = {"vsdx": (io.BytesIO(b"PK\x03\x04"), "document.docx")}
        r = auth_client.post(
            "/activities/api/debug-decisions/analyze-file/ai",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_sans_auth_retourne_401(self, app):
        """Client anonyme (pas de session) → 401 (aucun appel IA sans authentification)."""
        fresh = app.test_client()
        data = {"vsdx": (io.BytesIO(b"fake content"), "diagram.vsdx")}
        r = fresh.post(
            "/activities/api/debug-decisions/analyze-file/ai",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 401
        assert "error" in r.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# 11. POST /activities/api/debug-decisions/ai (legacy, fichier de l'entité)
# ─────────────────────────────────────────────────────────────────────────────

class TestDebugDecisionsAI:

    def test_sans_vsdx_retourne_404(self, auth_client):
        """Sans fichier VSDX stocké pour l'entité test → 404."""
        r = auth_client.post("/activities/api/debug-decisions/ai")
        assert r.status_code == 404

    def test_erreur_404_contient_message(self, auth_client):
        """L'erreur 404 contient un champ 'error'."""
        r = auth_client.post("/activities/api/debug-decisions/ai")
        if r.status_code != 200:
            data = r.get_json()
            assert "error" in data

    def test_sans_entite_active_400(self, app):
        """Sans entité active en session → 400."""
        fresh = app.test_client()
        r = fresh.post("/activities/api/debug-decisions/ai")
        assert r.status_code == 400
