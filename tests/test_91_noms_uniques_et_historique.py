# -*- coding: utf-8 -*-
"""Trois garanties livrées ensemble, toutes autour d'une carto :

* **deux cartos ne portent plus le même nom.** Le nom est ce qui la désigne
  partout — sélecteur d'entité active, galerie de la page Partage, colonnes de
  la matrice d'accès, tableau RH, file des propositions. Cinq « FluidClip »,
  ce que le dépôt de copies avait fabriqué sur le pilote, rendent ces écrans
  indéchiffrables. La comparaison est NORMALISÉE : « FLUIDCLIP » et
  « Fluid  Clip » désignent la même chose pour un lecteur humain ;
* **l'historique des imports** : « d'où vient cette tâche, et qui l'a mise
  là ? » n'avait aucune réponse ;
* **le filtre « sans tâches »** de la liste des activités : les activités nées
  de la carto qu'on n'a pas encore complétées.
"""
import json

import pytest

from Code.extensions import db

API = "/api/import"
MAP = "/activities/api/entities"


# ══════════════════════════════════════════════════════════════════════
#  Décor
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _session_rendue(client):
    """`client` est partagé : on rend la session telle qu'on l'a trouvée."""
    with client.session_transaction() as s:
        avant = dict(s)
    yield
    with client.session_transaction() as s:
        s.clear()
        s.update(avant)


@pytest.fixture()
def scene(app):
    from Code.models.models import Activities, Entity, Task, User
    from Code.security import hash_password
    with app.app_context():
        admin = User(first_name="T91", last_name="Admin", email="t91.admin@devoptiq.com",
                     password=hash_password("Motdepasse123!"), status="admin")
        autre = User(first_name="T91", last_name="Autre", email="t91.autre@devoptiq.com",
                     password=hash_password("Motdepasse123!"), status="user")
        db.session.add_all([admin, autre])
        db.session.flush()
        a = Entity(name="T91 Carto A", owner_id=admin.id)
        b = Entity(name="T91 Carto B", owner_id=admin.id)
        c = Entity(name="T91 Carto Privee", owner_id=autre.id)
        db.session.add_all([a, b, c])
        db.session.flush()
        # Deux activités dans A : une avec tâche, une sans.
        pleine = Activities(name="T91 Chiffrer l offre", entity_id=a.id, shape_id="t91_a1")
        vide = Activities(name="T91 Qualifier le besoin", entity_id=a.id, shape_id="t91_a2")
        db.session.add_all([pleine, vide])
        db.session.flush()
        db.session.add(Task(name="T91 relever les cotes", activity_id=pleine.id))
        db.session.commit()
        ids = {"admin": admin.id, "autre": autre.id, "a": a.id, "b": b.id, "c": c.id,
               "pleine": pleine.id, "vide": vide.id}
    yield ids
    with app.app_context():
        from Code.models.models import (Activities, Entity, ImportRecord, Role, Task,
                                        Tool, User, UserRole, activity_roles, task_roles)
        ents = [ids["a"], ids["b"], ids["c"]]
        # Les cartos créées PAR les tests portent le préfixe T91.
        ents += [e.id for e in Entity.query.filter(Entity.name.like("%T91%")).all()]
        ents = sorted(set(ents))
        acts = [x.id for x in Activities.query.filter(Activities.entity_id.in_(ents)).all()]
        taches = [x.id for x in Task.query.filter(Task.activity_id.in_(acts or [-1])).all()]
        roles = [x.id for x in Role.query.filter(Role.entity_id.in_(ents)).all()]
        db.session.execute(task_roles.delete().where(task_roles.c.task_id.in_(taches or [-1])))
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.activity_id.in_(acts or [-1])))
        Task.query.filter(Task.id.in_(taches or [-1])).delete(synchronize_session=False)
        Activities.query.filter(Activities.id.in_(acts or [-1])).delete(synchronize_session=False)
        Tool.query.filter(Tool.entity_id.in_(ents)).delete(synchronize_session=False)
        UserRole.query.filter(UserRole.role_id.in_(roles or [-1])).delete(synchronize_session=False)
        Role.query.filter(Role.id.in_(roles or [-1])).delete(synchronize_session=False)
        ImportRecord.query.filter(ImportRecord.entity_id.in_(ents)).delete(
            synchronize_session=False)
        Entity.query.filter(Entity.id.in_(ents)).delete(synchronize_session=False)
        User.query.filter(User.email.like("t91%")).delete(synchronize_session=False)
        db.session.commit()


def _connecte(client, app, uid, entity_id=None, lang="fr"):
    from Code.models.models import User
    with app.app_context():
        mail = db.session.get(User, uid).email
    with client.session_transaction() as s:
        s.clear()
        s["user_id"] = uid
        s["user_email"] = mail
        s["lang"] = lang
        if entity_id:
            s["active_entity_id"] = entity_id


# ══════════════════════════════════════════════════════════════════════
#  1 · Deux cartos ne portent plus le même nom
# ══════════════════════════════════════════════════════════════════════
class TestUnNomParCarto:

    def test_creer_avec_un_nom_deja_pris_est_refuse(self, app, client, scene):
        _connecte(client, app, scene["admin"])
        res = client.post(MAP, json={"name": "T91 Carto B"})
        assert res.status_code == 409
        body = res.get_json()
        assert body["code"] == "nom_pris"
        assert body["error"]
        with app.app_context():
            from Code.models.models import Entity
            assert Entity.query.filter_by(name="T91 Carto B").count() == 1

    def test_la_casse_et_les_espaces_ne_font_pas_un_nom_different(self, app, client, scene):
        """⚠️ « T91 CARTO B » se lit comme « T91 Carto B » : une contrainte UNIQUE
        en base laisserait passer les deux, c'est le lecteur qu'on protège."""
        _connecte(client, app, scene["admin"])
        for essai in ("T91 CARTO B", "t91  carto   b"):
            assert client.post(MAP, json={"name": essai}).status_code == 409

    def test_un_nom_libre_passe(self, app, client, scene):
        _connecte(client, app, scene["admin"])
        res = client.post(MAP, json={"name": "T91 Carto neuve"})
        assert res.status_code == 200
        assert res.get_json()["entity"]["name"] == "T91 Carto neuve"

    def test_renommer_vers_un_nom_pris_est_refuse(self, app, client, scene):
        _connecte(client, app, scene["admin"])
        res = client.patch(f"{MAP}/{scene['a']}", json={"name": "T91 Carto B"})
        assert res.status_code == 409
        with app.app_context():
            from Code.models.models import Entity
            assert db.session.get(Entity, scene["a"]).name == "T91 Carto A"

    def test_renommer_une_carto_en_son_PROPRE_nom_reste_permis(self, app, client, scene):
        """Sinon corriger une description obligerait à changer le nom."""
        _connecte(client, app, scene["admin"])
        res = client.patch(f"{MAP}/{scene['a']}", json={"name": "T91 Carto A"})
        assert res.status_code == 200

    def test_une_carto_d_un_AUTRE_compte_occupe_aussi_le_nom(self, app, client, scene):
        """L'unicité est celle de l'INSTANCE : c'est le dépôt de copies chez
        plusieurs comptes qui avait fabriqué les homonymes."""
        _connecte(client, app, scene["admin"])
        assert client.post(MAP, json={"name": "T91 Carto Privee"}).status_code == 409

    def test_une_copie_deposee_ne_prend_pas_le_nom_de_la_source(self, app, client, scene):
        _connecte(client, app, scene["admin"])
        res = client.post(f"{MAP}/{scene['a']}/share",
                          json={"user_ids": [scene["autre"]], "mode": "direct"})
        assert res.status_code == 200
        nom = res.get_json()["shared"][0]["entity_name"]
        assert nom.startswith("T91 Carto A") and nom != "T91 Carto A"


class TestLaRepriseDesHomonymes:
    """Les cartos déjà en base : la plus ANCIENNE prend le « 1 »."""

    @pytest.fixture()
    def jumelles(self, app):
        from datetime import datetime
        from Code.models.models import AppSetting, Entity
        with app.app_context():
            # Créées hors d'ordre exprès : c'est `created_at` qui tranche, pas l'id.
            e2 = Entity(name="T91 Jumelle", created_at=datetime(2026, 3, 2))
            e1 = Entity(name="t91 jumelle", created_at=datetime(2026, 1, 1))
            e3 = Entity(name="T91  JUMELLE", created_at=datetime(2026, 6, 9))
            seule = Entity(name="T91 Seule", created_at=datetime(2026, 2, 2))
            db.session.add_all([e2, e1, e3, seule])
            db.session.commit()
            ids = {"e1": e1.id, "e2": e2.id, "e3": e3.id, "seule": seule.id}
        yield ids
        with app.app_context():
            Entity.query.filter(Entity.id.in_(list(ids.values()))).delete(
                synchronize_session=False)
            AppSetting.query.filter_by(key="entites_nom_unique").delete(
                synchronize_session=False)
            db.session.commit()

    def test_les_homonymes_sont_numerotes_de_la_plus_ancienne_a_la_plus_recente(
            self, app, jumelles):
        from Code.entites_uniques import numeroter_doublons
        from Code.models.models import Entity
        with app.app_context():
            renommes = numeroter_doublons(force=True)
            # ⚠️ La base est PARTAGÉE : d'autres fichiers ont pu semer leurs
            # propres homonymes. On ne compte que les nôtres.
            miens = [r for r in renommes if r[0] in jumelles.values()]
            assert len(miens) == 3
            assert db.session.get(Entity, jumelles["e1"]).name.endswith(" 1")
            assert db.session.get(Entity, jumelles["e2"]).name.endswith(" 2")
            assert db.session.get(Entity, jumelles["e3"]).name.endswith(" 3")

    def test_chaque_carto_garde_son_ORTHOGRAPHE(self, app, jumelles):
        """On numérote pour distinguer, on ne réécrit pas ce que quelqu'un a saisi."""
        from Code.entites_uniques import numeroter_doublons
        from Code.models.models import Entity
        with app.app_context():
            numeroter_doublons(force=True)
            assert db.session.get(Entity, jumelles["e1"]).name == "t91 jumelle 1"
            assert db.session.get(Entity, jumelles["e3"]).name == "T91  JUMELLE 3"

    def test_une_carto_sans_homonyme_n_est_pas_touchee(self, app, jumelles):
        from Code.entites_uniques import numeroter_doublons
        from Code.models.models import Entity
        with app.app_context():
            numeroter_doublons(force=True)
            assert db.session.get(Entity, jumelles["seule"]).name == "T91 Seule"

    def test_la_reprise_ne_se_joue_qu_UNE_fois(self, app, jumelles):
        """⚠️ Rejouée à chaque démarrage, elle renommerait « X 1 » en « X 1 1 »
        au premier homonyme suivant — le marqueur vit en BASE, pas en mémoire."""
        from Code.entites_uniques import numeroter_doublons
        from Code.models.models import Entity
        with app.app_context():
            numeroter_doublons(force=True)
            apres = db.session.get(Entity, jumelles["e1"]).name
            assert numeroter_doublons() == []
            assert db.session.get(Entity, jumelles["e1"]).name == apres

    def test_apres_la_reprise_plus_aucun_homonyme(self, app, jumelles):
        from Code.entites_uniques import normalise, numeroter_doublons
        from Code.models.models import Entity
        with app.app_context():
            numeroter_doublons(force=True)
            cles = [normalise(e.name) for e in Entity.query.all() if e.name]
            assert len(cles) == len(set(cles))


# ══════════════════════════════════════════════════════════════════════
#  2 · L'historique des imports
# ══════════════════════════════════════════════════════════════════════
def _importer_roles(client, cibles, noms, fichier="roles.xlsx", feuille="Roles"):
    lignes = [{"nom": n, "mission": "", "_i": i, "statut": "nouveau"}
              for i, n in enumerate(noms)]
    return client.post(f"{API}/importer", data=json.dumps({
        "parts": [{"type": "roles", "id": "p1", "fichier": fichier,
                   "feuille": feuille, "lignes": lignes}],
        "cibles": cibles,
    }), content_type="application/json")


def _importer_outils(client, cibles, noms, fichier="outils.xlsx", feuille="Outils"):
    """Un outil appartient à SA carto : le même dépôt en crée un par carto visée."""
    lignes = [{"nom": n, "description": "", "_i": i, "statut": "nouveau"}
              for i, n in enumerate(noms)]
    return client.post(f"{API}/importer", data=json.dumps({
        "parts": [{"type": "outils", "id": "p1", "fichier": fichier,
                   "feuille": feuille, "lignes": lignes}],
        "cibles": cibles,
    }), content_type="application/json")


class TestHistoriqueDesImports:

    def test_un_import_laisse_sa_trace_avec_ce_qu_il_a_ajoute(self, app, client, scene):
        _connecte(client, app, scene["admin"], scene["a"])
        assert _importer_roles(client, [scene["a"]],
                               ["T91 Metrologie", "T91 Logistique"]).status_code == 200

        res = client.get(f"{API}/historique?entity_id={scene['a']}")
        assert res.status_code == 200
        body = res.get_json()
        assert body["entity"]["id"] == scene["a"]
        assert len(body["lignes"]) == 1
        l = body["lignes"][0]
        assert l["nature"] == "roles"
        assert l["ajoutes"] == 2
        assert set(l["detail"]) == {"T91 Metrologie", "T91 Logistique"}
        assert l["fichier"] == "roles.xlsx"
        assert l["feuille"] == "Roles"
        assert l["qui"] == "T91 Admin"
        assert l["quand"]

    def test_un_import_qui_n_ajoute_RIEN_ne_laisse_pas_de_ligne(self, app, client, scene):
        """Une trace vide ferait croire à un import ; et relire un fichier déjà
        importé est le geste le plus courant."""
        _connecte(client, app, scene["admin"], scene["a"])
        _importer_roles(client, [scene["a"]], ["T91 Metrologie"])
        _importer_roles(client, [scene["a"]], ["T91 Metrologie"])
        body = client.get(f"{API}/historique?entity_id={scene['a']}").get_json()
        assert len(body["lignes"]) == 1

    def test_un_depot_vers_DEUX_cartos_se_dit_de_chaque_cote(self, app, client, scene):
        """⚠️ C'est ce qui explique qu'un outil se retrouve ailleurs : on ne peut
        pas le deviner ligne par ligne."""
        _connecte(client, app, scene["admin"], scene["a"])
        assert _importer_outils(client, [scene["a"], scene["b"]],
                                ["T91 Pied a coulisse"]).status_code == 200
        for eid, autre in ((scene["a"], "T91 Carto B"), (scene["b"], "T91 Carto A")):
            l = client.get(f"{API}/historique?entity_id={eid}").get_json()["lignes"][0]
            assert l["nature"] == "outils"
            assert l["aussi"] == [autre]

    def test_un_ROLE_importe_dans_deux_cartos_ne_laisse_qu_UNE_trace(self, app, client, scene):
        """⚠️ Un rôle appartient à l'ENTREPRISE : créé pour une carto, il existe
        pour les autres. Deux traces diraient qu'il a été ajouté deux fois."""
        _connecte(client, app, scene["admin"], scene["a"])
        assert _importer_roles(client, [scene["a"], scene["b"]],
                               ["T91 Metrologie"]).status_code == 200
        n = sum(len(client.get(f"{API}/historique?entity_id={e}").get_json()["lignes"])
                for e in (scene["a"], scene["b"]))
        assert n == 1

    def test_l_historique_d_une_carto_qu_on_n_ouvre_pas_est_refuse(self, app, client, scene):
        _connecte(client, app, scene["admin"], scene["a"])
        _importer_roles(client, [scene["a"]], ["T91 Metrologie"])
        _connecte(client, app, scene["autre"], scene["c"])
        assert client.get(f"{API}/historique?entity_id={scene['a']}").status_code == 404

    def test_supprimer_la_carto_efface_son_historique(self, app, client, scene):
        """PostgreSQL applique les clés étrangères : sans ce ménage, effacer une
        carto importée échouerait."""
        _connecte(client, app, scene["admin"], scene["b"])
        _importer_roles(client, [scene["b"]], ["T91 Metrologie"])
        with app.app_context():
            from Code.models.models import ImportRecord
            assert ImportRecord.query.filter_by(entity_id=scene["b"]).count() == 1
        assert client.delete(f"{MAP}/{scene['b']}").status_code == 200
        with app.app_context():
            from Code.models.models import ImportRecord
            assert ImportRecord.query.filter_by(entity_id=scene["b"]).count() == 0

    def test_la_fiche_d_entite_porte_le_bouton(self, app, client, scene):
        _connecte(client, app, scene["admin"], scene["a"])
        page = client.get("/activities/map").get_data(as_text=True)
        assert 'id="wizard-history-btn"' in page
        assert 'id="import-history-modal"' in page


# ══════════════════════════════════════════════════════════════════════
#  3 · Le filtre « pas encore de tâches »
# ══════════════════════════════════════════════════════════════════════
class TestFiltreSansTaches:

    def test_sans_le_filtre_les_deux_activites_sont_la(self, app, client, scene):
        _connecte(client, app, scene["admin"], scene["a"])
        page = client.get("/activities/view").get_data(as_text=True)
        assert "T91 Chiffrer l offre" in page
        assert "T91 Qualifier le besoin" in page

    def test_avec_le_filtre_seule_celle_SANS_tache_reste(self, app, client, scene):
        _connecte(client, app, scene["admin"], scene["a"])
        page = client.get("/activities/view?sans_taches=1").get_data(as_text=True)
        assert "T91 Qualifier le besoin" in page
        assert "T91 Chiffrer l offre" not in page

    def test_le_compte_annonce_ce_qui_RESTE_a_faire_meme_sans_filtre(self, app, client, scene):
        """⚠️ Le compteur porte sur TOUTE la carto, pas sur le lot affiché : il
        dit ce qui reste, il ne doit pas bouger quand on filtre."""
        _connecte(client, app, scene["admin"], scene["a"])
        for url in ("/activities/view", "/activities/view?sans_taches=1"):
            page = client.get(url).get_data(as_text=True)
            assert "<b>1</b>" in page.replace(" ", "")

    def test_la_suite_de_la_liste_porte_le_filtre(self, app, client, scene):
        """⚠️ Le cadrage est SERVEUR : la liste arrive par lots, « charger plus »
        sans le filtre ramènerait les activités écartées."""
        _connecte(client, app, scene["admin"], scene["a"])
        html = client.get("/activities/view/more?offset=0&sans_taches=1").get_json()["html"]
        assert "T91 Qualifier le besoin" in html
        assert "T91 Chiffrer l offre" not in html

    def test_la_recherche_aussi(self, app, client, scene):
        _connecte(client, app, scene["admin"], scene["a"])
        res = client.get("/activities/view/search?q=T91&sans_taches=1").get_json()
        assert "T91 Qualifier le besoin" in res["html"]
        assert "T91 Chiffrer l offre" not in res["html"]

    def test_le_bouton_d_import_de_taches_n_existe_plus(self, app, client, scene):
        """L'import passe par la page Carte : deux portes pour un même geste
        finissent par donner deux comportements."""
        _connecte(client, app, scene["admin"], scene["a"])
        page = client.get("/activities/view").get_data(as_text=True)
        assert "btn-import-tasks" not in page
        assert "import_tasks" not in page
