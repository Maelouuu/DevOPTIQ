# tests/test_143_carto_sharing_residuel.py
"""
Page : Partage de cartos — couverture résiduelle de Code/routes/carto_sharing.py.

Ce que les fichiers 51/66/68/119 ne jouaient pas :
  * la comparaison AVANT / APRÈS d'une proposition servie avec succès
    (`/api/changes/<id>/diagramme/<quel>` et `/changes/<id>/apercu/<quel>`) ;
  * les corps invalides (rôles, cases de la matrice, titulaires) ;
  * le cycle d'une proposition hors du chemin heureux : cible inconnue,
    diagramme absent ou illisible, synchronisation qui échoue, déjà tranchée ;
  * les accès anonymes des routes restantes.

Isolation : un décor DÉDIÉ (carto commune, quatre comptes) créé pour le module
et entièrement supprimé à la fin ; chaque test ouvre son PROPRE client Flask —
aucune session partagée avec le reste de la suite.
"""
import json

import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.carto_sharing

AVANT = {
    "shapes": [{"id": "a1", "type": "process", "label": "T143 Avant",
                "x": 0, "y": 0, "w": 100, "h": 50}],
    "bands": [{"id": "b1", "label": "Bande T143", "height": 200}],
    "connections": [],
}
APRES = {
    "shapes": [{"id": "a1", "type": "process", "label": "T143 Après",
                "x": 0, "y": 0, "w": 100, "h": 50},
               {"id": "a2", "type": "process", "label": "T143 Nouvelle",
                "x": 300, "y": 0, "w": 100, "h": 50}],
    "bands": [{"id": "b1", "label": "Bande T143", "height": 200}],
    "connections": [{"fromId": "a1", "toId": "a2"}],
}

COMPTES = {
    "coord": "coordinateur",
    "champ": "champion",
    "lecteur": "user",
}


@pytest.fixture(scope="module")
def decor(app):
    from Code.extensions import db
    from Code.models.models import (CartoChangeRequest, Entity, EntityRoleAccess,
                                    Role, User, UserRole)

    with app.app_context():
        ids = {}
        for cle, statut in COMPTES.items():
            email = f"t143.{cle}@devoptiq.com"
            u = User.query.filter_by(email=email).first()
            if u is None:
                u = User(first_name="T143", last_name=cle, email=email,
                         password=generate_password_hash("Test1234!"), status=statut)
                db.session.add(u)
            u.status = statut
            db.session.commit()
            ids[cle] = u.id

        ent = Entity(name="Carto commune T143", owner_id=ids["coord"],
                     is_shared=True,
                     optiqcarto_data=json.dumps(AVANT, ensure_ascii=False))
        db.session.add(ent)
        db.session.commit()
        privee = Entity(name="Carto privée T143", owner_id=ids["coord"],
                        is_shared=False)
        db.session.add(privee)
        role = Role(entity_id=ent.id, name="T143 Rôle")
        db.session.add(role)
        db.session.commit()
        ids.update(entity_id=ent.id, privee_id=privee.id, role_id=role.id)

    yield ids

    with app.app_context():
        CartoChangeRequest.query.filter(
            CartoChangeRequest.entity_id.in_([ids["entity_id"], ids["privee_id"]])
        ).delete(synchronize_session=False)
        UserRole.query.filter_by(role_id=ids["role_id"]).delete()
        EntityRoleAccess.query.filter(
            EntityRoleAccess.entity_id.in_([ids["entity_id"], ids["privee_id"]])
        ).delete(synchronize_session=False)
        r = db.session.get(Role, ids["role_id"])
        if r is not None:
            db.session.delete(r)
        db.session.commit()
        for cle in ("entity_id", "privee_id"):
            e = db.session.get(Entity, ids[cle])
            if e is not None:
                e.is_shared = False
                db.session.delete(e)
        db.session.commit()
        for cle in COMPTES:
            u = db.session.get(User, ids[cle])
            if u is not None:
                db.session.delete(u)
        db.session.commit()


def _client(app, user_id=None, entity_id=None):
    """Un client Flask NEUF, connecté (ou non) au compte demandé."""
    c = app.test_client()
    if user_id is not None:
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            email = db.session.get(User, user_id).email
        with c.session_transaction() as s:
            s["user_id"] = user_id
            s["user_email"] = email
            if entity_id is not None:
                s["active_entity_id"] = entity_id
    return c


def _admin(app, ids):
    return _client(app, ids["user_id"], ids["entity_id"])


def _post(c, url, payload):
    return c.post(url, data=json.dumps(payload), content_type="application/json")


def _proposition(app, decor, *, diagram=APRES, base=AVANT, status="pending",
                 author="champ"):
    """Dépose une proposition directement en base ; rend son id."""
    from Code.extensions import db
    from Code.models.models import CartoChangeRequest
    with app.app_context():
        cr = CartoChangeRequest(
            entity_id=decor["entity_id"], author_id=decor[author],
            title="T143",
            diagram=diagram if isinstance(diagram, str) else json.dumps(diagram),
            base_diagram=(None if base is None else
                          base if isinstance(base, str) else json.dumps(base)),
            status=status,
        )
        db.session.add(cr)
        db.session.commit()
        return cr.id


def _statut(app, cr_id):
    from Code.extensions import db
    from Code.models.models import CartoChangeRequest
    with app.app_context():
        cr = db.session.get(CartoChangeRequest, cr_id)
        return cr.status if cr else None


# ══════════════════════════════════════════════════════════════════════════
#  Accès anonymes — toutes les routes restantes refusent en 401
# ══════════════════════════════════════════════════════════════════════════

class TestCartoSharingAnonyme:

    @pytest.mark.parametrize("url", [
        "/cartography/api/access/previews",
        "/cartography/api/access/1/roles",
        "/cartography/api/changes",
        "/cartography/api/changes/1",
        "/cartography/api/changes/a_examiner",
        "/cartography/api/changes/decisions",
        "/cartography/api/changes/1/diagramme/apres",
    ])
    def test_get_anonyme_refuse_401(self, app, url):
        assert app.test_client().get(url).status_code == 401

    @pytest.mark.parametrize("url", [
        "/cartography/api/access/1/roles/1/holders",
        "/cartography/api/changes",
        "/cartography/api/changes/decisions/vues",
        "/cartography/api/changes/1/approve",
        "/cartography/api/changes/1/reject",
    ])
    def test_post_anonyme_refuse_401(self, app, url):
        assert _post(app.test_client(), url, {}).status_code == 401

    def test_retrait_anonyme_refuse_401(self, app):
        assert app.test_client().delete("/cartography/api/changes/1").status_code == 401

    def test_apercu_anonyme_refuse_401(self, app):
        assert app.test_client().get("/cartography/changes/1/apercu/avant").status_code == 401


# ══════════════════════════════════════════════════════════════════════════
#  Réglage de l'accès — corps invalides
# ══════════════════════════════════════════════════════════════════════════

class TestCartoSharingCorpsInvalides:

    def test_post_access_role_ids_non_numeriques_400(self, app, ids, decor):
        r = _post(_admin(app, ids), f"/cartography/api/access/{decor['entity_id']}",
                  {"is_shared": True, "role_ids": ["abc"]})
        assert r.status_code == 400
        assert "invalide" in r.get_json()["error"]

    def test_post_matrice_sans_aucune_liste_400(self, app, ids, decor):
        r = _post(_admin(app, ids), "/cartography/api/access/matrice",
                  {"cases": "pas une liste"})
        assert r.status_code == 400

    def test_post_matrice_cases_malformees_ignorees_sans_effet(self, app, ids, decor):
        from Code.models.models import EntityRoleAccess
        r = _post(_admin(app, ids), "/cartography/api/access/matrice", {"cases": [
            "pas un dict",
            {"entity_id": "x", "role_id": 1, "on": True},
            {"entity_id": 999999, "role_id": decor["role_id"], "on": True},
            {"entity_id": decor["entity_id"], "role_id": 999999, "on": True},
        ]})
        assert r.status_code == 200
        assert r.get_json()["rendues_communes"] == []
        with app.app_context():
            assert EntityRoleAccess.query.filter_by(
                entity_id=decor["entity_id"]).count() == 0

    def test_post_matrice_cases_statut_malformees_ignorees(self, app, ids, decor):
        from Code.extensions import db
        from Code.models.models import Entity
        r = _post(_admin(app, ids), "/cartography/api/access/matrice", {"cases_statut": [
            42,
            {"entity_id": None, "statut": "user", "on": True},
            {"entity_id": 999999, "statut": "user", "on": True},
            {"entity_id": decor["privee_id"], "statut": "user", "on": False},
        ]})
        assert r.status_code == 200
        assert r.get_json()["rendues_communes"] == []
        with app.app_context():
            assert db.session.get(Entity, decor["privee_id"]).is_shared is False

    def test_get_roles_entite_inconnue_404(self, app, ids):
        assert _admin(app, ids).get(
            "/cartography/api/access/999999/roles").status_code == 404

    def test_post_holders_entite_inconnue_404(self, app, ids, decor):
        r = _post(_admin(app, ids),
                  f"/cartography/api/access/999999/roles/{decor['role_id']}/holders",
                  {"add": []})
        assert r.status_code == 404

    def test_post_holders_liste_non_numerique_400(self, app, ids, decor):
        r = _post(_admin(app, ids),
                  f"/cartography/api/access/{decor['entity_id']}/roles/{decor['role_id']}/holders",
                  {"add": ["pas-un-id"]})
        assert r.status_code == 400

    def test_post_holders_compte_inconnu_ignore(self, app, ids, decor):
        r = _post(_admin(app, ids),
                  f"/cartography/api/access/{decor['entity_id']}/roles/{decor['role_id']}/holders",
                  {"add": [999999, decor["lecteur"]]})
        assert r.status_code == 200
        titulaires = {h["id"] for h in r.get_json()["holders"]}
        assert titulaires == {decor["lecteur"]}
        # Ménage : le titulaire posé ne doit pas survivre au test.
        r = _post(_admin(app, ids),
                  f"/cartography/api/access/{decor['entity_id']}/roles/{decor['role_id']}/holders",
                  {"remove": [decor["lecteur"]]})
        assert r.get_json()["holders"] == []


# ══════════════════════════════════════════════════════════════════════════
#  Comparaison AVANT / APRÈS d'une proposition
# ══════════════════════════════════════════════════════════════════════════

class TestCartoSharingComparaison:

    def test_l_auteur_recoit_le_diagramme_apres_tel_quel(self, app, decor):
        cr = _proposition(app, decor)
        r = _client(app, decor["champ"]).get(
            f"/cartography/api/changes/{cr}/diagramme/apres")
        assert r.status_code == 200
        assert [s["label"] for s in r.get_json()["shapes"]] == ["T143 Après", "T143 Nouvelle"]

    def test_l_arbitre_recoit_le_diagramme_avant(self, app, decor):
        cr = _proposition(app, decor)
        r = _client(app, decor["coord"]).get(
            f"/cartography/api/changes/{cr}/diagramme/avant")
        assert r.status_code == 200
        assert r.get_json()["shapes"][0]["label"] == "T143 Avant"

    def test_un_tiers_sans_droit_d_examen_recoit_404(self, app, decor):
        cr = _proposition(app, decor)
        r = _client(app, decor["lecteur"]).get(
            f"/cartography/api/changes/{cr}/diagramme/apres")
        assert r.status_code == 404

    def test_sans_base_l_avant_est_introuvable(self, app, decor):
        cr = _proposition(app, decor, base=None)
        r = _client(app, decor["champ"]).get(
            f"/cartography/api/changes/{cr}/diagramme/avant")
        assert r.status_code == 404

    def test_l_apercu_ouvre_le_viewer_sur_le_bon_diagramme(self, app, decor):
        cr = _proposition(app, decor)
        r = _client(app, decor["coord"]).get(f"/cartography/changes/{cr}/apercu/apres")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert f"/cartography/api/changes/{cr}/diagramme/apres" in html
        assert "Carto commune T143" in html


# ══════════════════════════════════════════════════════════════════════════
#  Lecture des propositions
# ══════════════════════════════════════════════════════════════════════════

class TestCartoSharingLectureDesPropositions:

    def test_filtre_par_statut(self, app, decor):
        attente = _proposition(app, decor)
        tranchee = _proposition(app, decor, status="rejected")
        r = _client(app, decor["coord"]).get(
            f"/cartography/api/changes?entity_id={decor['entity_id']}&status=rejected")
        vus = {p["id"] for p in r.get_json()["requests"]}
        assert tranchee in vus and attente not in vus

    def test_detail_inconnu_404(self, app, decor):
        assert _client(app, decor["coord"]).get(
            "/cartography/api/changes/999999").status_code == 404

    def test_sans_base_le_resume_compare_a_la_carto_actuelle(self, app, decor):
        cr = _proposition(app, decor, base=None)
        d = _client(app, decor["coord"]).get(f"/cartography/api/changes/{cr}").get_json()
        # La carto actuelle porte AVANT : une forme ajoutée, une renommée.
        assert d["summary"]["added"] == ["T143 Nouvelle"]
        assert d["summary"]["renamed"] == [{"from": "T143 Avant", "to": "T143 Après"}]
        # Sans base, rien ne permet de dire ce qui a bougé depuis le dépôt.
        assert d["since"] is None


# ══════════════════════════════════════════════════════════════════════════
#  Dépôt d'une proposition
# ══════════════════════════════════════════════════════════════════════════

class TestCartoSharingDepot:

    def test_sans_entity_id_la_proposition_vise_la_carto_active(self, app, decor):
        c = _client(app, decor["champ"], decor["entity_id"])
        r = _post(c, "/cartography/api/changes", {"diagram": APRES})
        assert r.status_code == 201
        assert r.get_json()["request"]["entity_id"] == decor["entity_id"]

    def test_sans_diagramme_400(self, app, decor):
        c = _client(app, decor["champ"], decor["entity_id"])
        r = _post(c, "/cartography/api/changes",
                  {"entity_id": decor["entity_id"], "diagram": "pas un objet"})
        assert r.status_code == 400

    def test_entity_id_inconnu_404_sans_repli_sur_la_carto_active(self, app, decor):
        """Une cible EXPLICITE introuvable ne doit pas déposer la proposition
        sur la carto active : l'auteur viserait une carto et en toucherait une
        autre."""
        from Code.models.models import CartoChangeRequest
        with app.app_context():
            avant = CartoChangeRequest.query.filter_by(author_id=decor["champ"]).count()
        c = _client(app, decor["champ"], decor["entity_id"])
        r = _post(c, "/cartography/api/changes",
                  {"entity_id": 999999, "diagram": APRES})
        assert r.status_code == 404
        with app.app_context():
            assert CartoChangeRequest.query.filter_by(
                author_id=decor["champ"]).count() == avant

    def test_entity_id_non_numerique_404_et_non_500(self, app, decor):
        c = _client(app, decor["champ"], decor["entity_id"])
        r = _post(c, "/cartography/api/changes",
                  {"entity_id": "abc", "diagram": APRES})
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
#  Application, refus, retrait
# ══════════════════════════════════════════════════════════════════════════

class TestCartoSharingArbitrage:

    def test_appliquer_une_proposition_inconnue_404(self, app, decor):
        r = _post(_client(app, decor["coord"]), "/cartography/api/changes/999999/approve", {})
        assert r.status_code == 404

    def test_appliquer_un_diagramme_illisible_400_et_carto_intacte(self, app, decor):
        from Code.extensions import db
        from Code.models.models import Entity
        cr = _proposition(app, decor, diagram="{pas du json")
        r = _post(_client(app, decor["coord"]), f"/cartography/api/changes/{cr}/approve", {})
        assert r.status_code == 400
        assert _statut(app, cr) == "pending"
        with app.app_context():
            assert json.loads(db.session.get(Entity, decor["entity_id"]).optiqcarto_data) == AVANT

    def test_echec_de_synchronisation_signale_mais_proposition_appliquee(
            self, app, decor, monkeypatch):
        from Code.extensions import db
        from Code.models.models import Entity
        import Code.routes.cartography_editor as editeur

        def casse(entity, diagram):
            raise RuntimeError("dérivation T143 en panne")

        monkeypatch.setattr(editeur, "_sync_carto_to_db", casse)
        cr = _proposition(app, decor)
        try:
            r = _post(_client(app, decor["coord"]),
                      f"/cartography/api/changes/{cr}/approve", {"comment": "ok"})
            assert r.status_code == 200
            assert r.get_json()["sync_warning"] == "dérivation T143 en panne"
            assert _statut(app, cr) == "approved"
        finally:
            with app.app_context():
                e = db.session.get(Entity, decor["entity_id"])
                e.optiqcarto_data = json.dumps(AVANT, ensure_ascii=False)
                db.session.commit()

    def test_refuser_une_proposition_inconnue_404(self, app, decor):
        r = _post(_client(app, decor["coord"]), "/cartography/api/changes/999999/reject", {})
        assert r.status_code == 404

    def test_un_champion_ne_refuse_pas_403(self, app, decor):
        cr = _proposition(app, decor, author="lecteur")
        r = _post(_client(app, decor["champ"]), f"/cartography/api/changes/{cr}/reject", {})
        assert r.status_code == 403
        assert _statut(app, cr) == "pending"

    def test_refuser_deux_fois_409(self, app, decor):
        cr = _proposition(app, decor, status="approved")
        r = _post(_client(app, decor["coord"]), f"/cartography/api/changes/{cr}/reject", {})
        assert r.status_code == 409
        assert _statut(app, cr) == "approved"

    def test_l_auteur_ne_retire_pas_une_proposition_tranchee_409(self, app, decor):
        cr = _proposition(app, decor, status="rejected")
        r = _client(app, decor["champ"]).delete(f"/cartography/api/changes/{cr}")
        assert r.status_code == 409
        assert _statut(app, cr) == "rejected"
