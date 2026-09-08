# tests/test_68_share_page.py
"""
Page Partage (/share) — tout le processus au même endroit.

Régler l'accès se faisait sur la carte, mais dire QUI tient un rôle se faisait
sur la page Rôles : deux moitiés de la même décision, à deux endroits. La page
Partage porte les deux, plus la file des modifications proposées.

⚠️ Le piège que ces tests gardent : les endpoints de la page RH remplacent TOUS
les rôles d'une personne (delete puis insert). Les appeler depuis cet écran
retirerait à quelqu'un ses rôles sur les AUTRES cartos. On ne touche donc qu'au
couple (compte, rôle) visé.
"""
import json

import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.share_page


DIAGRAM = {
    "shapes": [{"id": "a1", "type": "process", "label": "T68 Activité",
                "x": 100, "y": 0, "w": 120, "h": 60}],
    "bands": [{"id": "b1", "label": "T68 Bande", "height": 200}],
    "connections": [],
}


@pytest.fixture(scope="module", autouse=True)
def _restaurer_la_session(app, client, ids):
    yield
    with app.app_context():
        from Code.models.models import User
        seed = User.query.filter_by(email="test@devoptiq.com").first()
        uid, umail = seed.id, seed.email
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_email"] = umail
        sess["active_entity_id"] = ids["entity_id"]


def _mk_user(app, email, status):
    from Code.extensions import db
    from Code.models.models import User
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(first_name="T68", last_name=email.split("@")[0], email=email,
                     password=generate_password_hash("Test1234!"), status=status)
            db.session.add(u)
        u.status = status
        db.session.commit()
        return u.id


def _as(client, user_id, email):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_email"] = email


@pytest.fixture(scope="module")
def scene(app):
    """Deux cartos du même champion : une commune, une autre pour vérifier
    qu'on ne déborde pas dessus."""
    from Code.extensions import db
    from Code.models.models import Entity, EntityRoleAccess, Role, UserRole

    champion = _mk_user(app, "t68.champion@devoptiq.com", "champion")
    simple = _mk_user(app, "t68.simple@devoptiq.com", "user")

    with app.app_context():
        ids = {}
        for cle, nom in (("a", "T68 Carto A"), ("b", "T68 Carto B")):
            ent = Entity.query.filter_by(name=nom).first()
            if ent is None:
                ent = Entity(name=nom, owner_id=champion)
                db.session.add(ent)
            ent.owner_id = champion
            ent.optiqcarto_data = json.dumps(DIAGRAM, ensure_ascii=False)
            ent.is_shared = True
            db.session.commit()
            ids[cle] = ent.id

        roles = {}
        for cle, (eid, nom) in {"a1": (ids["a"], "T68 Rôle A"),
                                "b1": (ids["b"], "T68 Rôle B")}.items():
            r = Role.query.filter_by(entity_id=eid, name=nom).first()
            if r is None:
                r = Role(entity_id=eid, name=nom)
                db.session.add(r)
                db.session.commit()
            roles[cle] = r.id

        # `simple` tient le rôle de la carto B — il ne doit pas le perdre en
        # étant ajouté au rôle de la carto A.
        UserRole.query.filter_by(user_id=simple).delete()
        db.session.add(UserRole(user_id=simple, role_id=roles["b1"]))
        EntityRoleAccess.query.filter(
            EntityRoleAccess.entity_id.in_([ids["a"], ids["b"]])).delete(
            synchronize_session=False)
        db.session.commit()

    return {"champion": champion, "simple": simple,
            "entity_a": ids["a"], "entity_b": ids["b"],
            "role_a": roles["a1"], "role_b": roles["b1"]}


# ══════════════════════════════════════════════════════════════════════════
# 1. La page
# ══════════════════════════════════════════════════════════════════════════

class TestPage:

    def test_la_page_s_ouvre_pour_un_compte_connecte(self, client, scene):
        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        res = client.get("/share/")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "share-entity" in html          # sélecteur de carto
        assert "share-roles" in html           # rôles et titulaires
        assert "share-changes" in html         # file d'examen

    def test_un_visiteur_est_renvoye_a_la_connexion(self, client):
        with client.session_transaction() as sess:
            sess.clear()
        res = client.get("/share/")
        assert res.status_code in (302, 401)

    def test_l_entite_de_l_url_est_celle_qui_s_affiche(self, client, scene):
        """On arrive depuis la fiche d'une entité : c'est celle-là qu'on veut voir."""
        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        html = client.get(f"/share/?entity_id={scene['entity_b']}").get_data(as_text=True)
        assert f'value="{scene["entity_b"]}" selected' in html

    def test_une_entite_hors_perimetre_est_ignoree(self, app, client, scene):
        """Un id d'entité au hasard dans l'URL ne doit rien ouvrir de plus."""
        from Code.extensions import db
        from Code.models.models import Entity
        etranger = _mk_user(app, "t68.etranger@devoptiq.com", "user")
        with app.app_context():
            priv = Entity.query.filter_by(name="T68 Privée étrangère").first()
            if priv is None:
                priv = Entity(name="T68 Privée étrangère", owner_id=etranger)
                db.session.add(priv)
                db.session.commit()
            priv_id = priv.id

        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        html = client.get(f"/share/?entity_id={priv_id}").get_data(as_text=True)
        assert f'value="{priv_id}"' not in html


# ══════════════════════════════════════════════════════════════════════════
# 2. Rôles et titulaires
# ══════════════════════════════════════════════════════════════════════════

class TestTitulaires:

    def test_l_ecran_donne_les_roles_avec_leurs_titulaires(self, client, scene):
        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        data = client.get(f"/cartography/api/access/{scene['entity_b']}/roles").get_json()
        role = next(r for r in data["roles"] if r["id"] == scene["role_b"])
        assert [h["id"] for h in role["holders"]] == [scene["simple"]]
        assert any(a["id"] == scene["simple"] for a in data["accounts"])

    def test_ajouter_un_titulaire_ne_touche_pas_ses_autres_roles(self, app, client, scene):
        """Le piège des endpoints RH : ils remplacent TOUS les rôles d'un compte."""
        from Code.models.models import UserRole
        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        res = client.post(
            f"/cartography/api/access/{scene['entity_a']}/roles/{scene['role_a']}/holders",
            json={"add": [scene["simple"]]})
        assert res.status_code == 200
        assert scene["simple"] in [h["id"] for h in res.get_json()["holders"]]

        with app.app_context():
            portes = {ur.role_id for ur in
                      UserRole.query.filter_by(user_id=scene["simple"]).all()}
        assert scene["role_b"] in portes, "le rôle de l'autre carto a été perdu"
        assert scene["role_a"] in portes

    def test_ajouter_deux_fois_ne_duplique_pas(self, app, client, scene):
        from Code.models.models import UserRole
        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        for _ in range(2):
            client.post(
                f"/cartography/api/access/{scene['entity_a']}/roles/{scene['role_a']}/holders",
                json={"add": [scene["simple"]]})
        with app.app_context():
            n = UserRole.query.filter_by(user_id=scene["simple"],
                                         role_id=scene["role_a"]).count()
        assert n == 1

    def test_retirer_un_titulaire(self, app, client, scene):
        from Code.models.models import UserRole
        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        client.post(
            f"/cartography/api/access/{scene['entity_a']}/roles/{scene['role_a']}/holders",
            json={"add": [scene["simple"]]})
        res = client.post(
            f"/cartography/api/access/{scene['entity_a']}/roles/{scene['role_a']}/holders",
            json={"remove": [scene["simple"]]})
        assert res.status_code == 200
        assert scene["simple"] not in [h["id"] for h in res.get_json()["holders"]]
        with app.app_context():
            assert UserRole.query.filter_by(user_id=scene["simple"],
                                            role_id=scene["role_b"]).count() == 1

    def test_un_compte_ordinaire_ne_nomme_personne(self, client, scene):
        _as(client, scene["simple"], "t68.simple@devoptiq.com")
        res = client.post(
            f"/cartography/api/access/{scene['entity_a']}/roles/{scene['role_a']}/holders",
            json={"add": [scene["simple"]]})
        assert res.status_code == 403
        assert res.get_json()["code"] == "forbidden"

    def test_un_role_d_une_autre_carto_est_refuse(self, client, scene):
        """L'id du rôle doit appartenir à la carto de l'URL."""
        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        res = client.post(
            f"/cartography/api/access/{scene['entity_a']}/roles/{scene['role_b']}/holders",
            json={"add": [scene["simple"]]})
        assert res.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# 3. Qui ouvre la carto
# ══════════════════════════════════════════════════════════════════════════

class TestPortee:

    def test_sans_role_coche_tout_le_monde_est_dans_la_portee(self, app, client, scene):
        from Code.carto_access import set_access
        from Code.extensions import db
        from Code.models.models import Entity, User
        with app.app_context():
            set_access(db.session.get(Entity, scene["entity_a"]), True, [])
            db.session.commit()
            total = User.query.count()

        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        data = client.get(f"/cartography/api/access/{scene['entity_a']}/roles").get_json()
        assert len(data["reach"]) == total
        assert {u["reason"] for u in data["reach"]} <= {"owner", "admin", "champion", "all"}

    def test_un_role_coche_dit_par_quel_role_chacun_entre(self, app, client, scene):
        from Code.carto_access import set_access
        from Code.extensions import db
        from Code.models.models import Entity
        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        client.post(
            f"/cartography/api/access/{scene['entity_a']}/roles/{scene['role_a']}/holders",
            json={"add": [scene["simple"]]})
        with app.app_context():
            set_access(db.session.get(Entity, scene["entity_a"]), True, [scene["role_a"]])
            db.session.commit()

        data = client.get(f"/cartography/api/access/{scene['entity_a']}/roles").get_json()
        ligne = next(u for u in data["reach"] if u["id"] == scene["simple"])
        assert ligne["reason"] == "role"
        assert "T68 Rôle A" in ligne["roles"]

    def test_un_compte_sans_le_role_sort_de_la_portee(self, app, client, scene):
        from Code.carto_access import set_access
        from Code.extensions import db
        from Code.models.models import Entity
        dehors = _mk_user(app, "t68.dehors@devoptiq.com", "user")
        with app.app_context():
            from Code.models.models import UserRole
            UserRole.query.filter_by(user_id=dehors).delete()
            set_access(db.session.get(Entity, scene["entity_a"]), True, [scene["role_a"]])
            db.session.commit()

        _as(client, scene["champion"], "t68.champion@devoptiq.com")
        data = client.get(f"/cartography/api/access/{scene['entity_a']}/roles").get_json()
        assert all(u["id"] != dehors for u in data["reach"])


# ══════════════════════════════════════════════════════════════════════════
# 4. Un seul écran pour le processus
# ══════════════════════════════════════════════════════════════════════════

class TestPlusDeDoublon:
    """La carte réglait le même accès dans une modale, en moins complet."""

    def test_la_carte_ne_porte_plus_le_reglage_d_acces(self):
        import io, os
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html = io.open(os.path.join(racine, "Code", "routes", "templates",
                                    "activities_map.html"), encoding="utf-8").read()
        js = io.open(os.path.join(racine, "static", "js", "activities_map.js"),
                     encoding="utf-8").read()
        assert "carto-access-modal" not in html
        assert "openAccessModal" not in js
        assert "/share/" in js, "le bouton doit mener à la page Partage"
