# -*- coding: utf-8 -*-
"""Proposer une modification sur une ACTIVITÉ — tâches, outils, compétences.

Le pendant de `test_66` pour l'autre moitié des données d'une carto. Ce que
ces cas tiennent, dans l'ordre d'importance :

1. un champion est DÉTOURNÉ vers une proposition, pas refusé — c'était le
   trou : il se voyait opposer `lecture_seule`, le motif réservé à `user` ;
2. un `user` reste refusé, et un coordinateur écrit toujours directement ;
3. une proposition s'applique en UNE transaction — tout ou rien.

⚠️ Chaque cas monte SON décor (ses comptes, sa carto, son activité) : la base
et la session sont partagées par toute la suite, et un décor commun dépendrait
de l'ordre des fichiers.
"""
import io
import json
import os

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_ECRAN = os.path.join(RACINE, "static", "js", "activite_propositions.js")
JS_EXAMEN = os.path.join(RACINE, "static", "js", "carto_examen.js")
GABARIT = os.path.join(RACINE, "Code", "routes", "templates",
                       "activite_propositions.html")


def _lire(p):
    return io.open(p, encoding="utf-8").read()


_N = [0]


@pytest.fixture
def decor(app):
    """Un coordinateur, un champion, un `user`, une carto COMMUNE, une activité."""
    from Code.models.models import Activities, Entity, User
    from Code.security import hash_password

    _N[0] += 1
    n = _N[0]
    with app.app_context():
        faire = lambda r, s: User(
            first_name=r.capitalize(), last_name="T%d" % n,
            email="%s%d@acp.test" % (r, n), password=hash_password("x"), status=s)
        coord = faire("coord", "coordinateur")
        champ = faire("champ", "champion")
        simple = faire("simple", "user")
        db.session.add_all([coord, champ, simple])
        db.session.commit()

        ent = Entity(name="ACP carto %d" % n, owner_id=coord.id, is_shared=True)
        db.session.add(ent)
        db.session.commit()
        act = Activities(name="ACP activité %d" % n, entity_id=ent.id)
        db.session.add(act)
        db.session.commit()

        d = {"coord": coord.id, "champ": champ.id, "simple": simple.id,
             "ent": ent.id, "act": act.id, "n": n}
    yield d
    with app.app_context():
        from Code.models.models import (ActivityChangeRequest, Competency,
                                        Savoir, Task, Tool)
        ActivityChangeRequest.query.filter_by(entity_id=d["ent"]).delete()
        Task.query.filter_by(activity_id=d["act"]).delete()
        Competency.query.filter_by(activity_id=d["act"]).delete()
        Savoir.query.filter_by(activity_id=d["act"]).delete()
        Tool.query.filter_by(entity_id=d["ent"]).delete()
        db.session.query(Activities).filter_by(id=d["act"]).delete()
        db.session.query(Entity).filter_by(id=d["ent"]).delete()
        User.query.filter(User.id.in_(
            [d["coord"], d["champ"], d["simple"]])).delete(synchronize_session=False)
        db.session.commit()


def _comme(app, uid, entity_id):
    """Un client PROPRE pour ce compte. ⚠️ `client` et `auth_client` sont le
    MÊME objet en portée session : s'en servir ici déconnecterait les
    fichiers suivants."""
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["active_entity_id"] = entity_id
    return c


# ══════════════════════════════════════════════════════════════════════════
class TestQuiEcritEtQuiPropose:
    """⚠️ Le défaut d'avant : `Code/ecriture.py` consulte `can_edit`, qui rend
    faux pour un champion sur une carto COMMUNE. Il se faisait donc refuser
    l'ajout d'une tâche avec `lecture_seule` — le motif de `user`. Il pouvait
    proposer une modification de la CARTE, et rien de ce qu'elle porte."""

    def test_le_champion_est_DETOURNE_pas_refuse(self, app, decor):
        from Code.models.models import Task
        c = _comme(app, decor["champ"], decor["ent"])
        r = c.post("/tasks/add", json={"activity_id": decor["act"], "name": "Peser"})
        assert r.status_code == 202, r.get_json()
        assert r.get_json()["code"] == "proposition"
        with app.app_context():
            assert Task.query.filter_by(activity_id=decor["act"]).count() == 0, \
                "rien ne doit être écrit avant la validation"

    def test_le_user_reste_refuse(self, app, decor):
        from Code.models.models import Task
        c = _comme(app, decor["simple"], decor["ent"])
        r = c.post("/tasks/add", json={"activity_id": decor["act"], "name": "Interdit"})
        assert r.status_code == 403
        assert r.get_json()["code"] == "lecture_seule"
        with app.app_context():
            assert Task.query.filter_by(activity_id=decor["act"]).count() == 0

    def test_le_coordinateur_ecrit_toujours_directement(self, app, decor):
        from Code.models.models import Task
        c = _comme(app, decor["coord"], decor["ent"])
        r = c.post("/tasks/add", json={"activity_id": decor["act"], "name": "Directe"})
        assert r.status_code == 201
        with app.app_context():
            assert Task.query.filter_by(activity_id=decor["act"]).count() == 1

    def test_sur_sa_carto_PRIVEE_le_champion_ecrit_directement(self, app, decor):
        """⚠️ `can_edit` rend la main au propriétaire d'une carto privée quel
        que soit son statut. Le détournement ne doit pas contredire cette
        règle — c'est le défaut relevé sur le pilote avant livraison."""
        from Code.models.models import Activities, Entity, Task
        with app.app_context():
            p = Entity(name="ACP privée %d" % decor["n"],
                       owner_id=decor["champ"], is_shared=False)
            db.session.add(p)
            db.session.commit()
            a = Activities(name="ACP privée act %d" % decor["n"], entity_id=p.id)
            db.session.add(a)
            db.session.commit()
            pid, aid = p.id, a.id
        c = _comme(app, decor["champ"], pid)
        r = c.post("/tasks/add", json={"activity_id": aid, "name": "Chez moi"})
        assert r.status_code == 201, r.get_json()
        with app.app_context():
            Task.query.filter_by(activity_id=aid).delete()
            Activities.query.filter_by(id=aid).delete()
            Entity.query.filter_by(id=pid).delete()
            db.session.commit()

    def test_ce_qui_n_ecrit_rien_passe_toujours(self, app, decor):
        """`/skills/propose` appelle l'IA et n'écrit pas : le champion doit
        pouvoir s'en servir pour PRÉPARER sa proposition."""
        from Code.propositions_activite import chemin_propasable
        assert chemin_propasable("/skills/propose") is False
        assert chemin_propasable("/utils/upload-file") is False
        assert chemin_propasable("/tasks/add") is True

    def test_on_ne_detourne_QUE_ce_qu_on_saura_rejouer(self, app, decor):
        """⚠️ Un POST vers une URL qui n'accepte que PUT devenait une
        proposition — acceptée, examinée, puis impossible à appliquer :
        `rejouer` ne retrouve aucune vue. La porte vérifie donc que la route
        se résout pour CETTE méthode avant de promettre un examen."""
        from Code.models.models import ActivityChangeRequest
        c = _comme(app, decor["champ"], decor["ent"])
        r = c.post("/tasks/999999", json={"name": "jamais"})
        assert r.status_code != 202, "un geste qu'on ne sait pas rejouer n'est pas déposé"
        with app.app_context():
            assert ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"]).count() == 0

    def test_un_chemin_hors_perimetre_reste_refuse(self, app, decor):
        """⚠️ Une liste EXPLICITE, pas un « tout sauf » : détourner une
        écriture qu'on ne sait pas rejouer, c'est promettre un examen pour un
        geste qui échouera."""
        from Code.propositions_activite import chemin_propasable
        for chemin in ("/temps/api/project", "/gestion_rh/role_dev",
                       "/paliers/norme/3", "/comptes/create"):
            assert chemin_propasable(chemin) is False, chemin


# ══════════════════════════════════════════════════════════════════════════
class TestLeBrouillonEstUnLOT:
    """⚠️ Un lot, pas un geste par proposition : corriger une fiche c'est cinq
    ou six clics, et six propositions demanderaient six décisions pour un
    seul travail."""

    def test_les_gestes_s_accumulent_dans_UNE_proposition(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        c = _comme(app, decor["champ"], decor["ent"])
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "A"})
        c.post("/savoirs/add", json={"activity_id": decor["act"], "description": "B"})
        c.post("/skills/add", json={"activity_id": decor["act"], "description": "C"})
        with app.app_context():
            lignes = ActivityChangeRequest.query.filter_by(entity_id=decor["ent"]).all()
            assert len(lignes) == 1, "une seule proposition, pas une par geste"
            assert lignes[0].status == "draft"
            assert len(json.loads(lignes[0].actions)) == 3

    def test_le_brouillon_se_relit_et_se_corrige(self, app, decor):
        c = _comme(app, decor["champ"], decor["ent"])
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "Gardée"})
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "Retirée"})
        j = c.get("/api/propositions/brouillon").get_json()
        assert j["n"] == 2
        assert [g["objet"] for g in j["brouillon"]["gestes"]] == ["Gardée", "Retirée"]
        assert c.delete("/api/propositions/brouillon/1").status_code == 200
        assert c.get("/api/propositions/brouillon").get_json()["n"] == 1

    def test_le_brouillon_vide_DISPARAIT(self, app, decor):
        """Une proposition sans geste n'a rien à dire : la garder la ferait
        paraître dans « mes propositions » sans contenu."""
        from Code.models.models import ActivityChangeRequest
        c = _comme(app, decor["champ"], decor["ent"])
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "Seule"})
        c.delete("/api/propositions/brouillon/0")
        with app.app_context():
            assert ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"]).count() == 0

    def test_un_BROUILLON_n_attend_la_decision_de_personne(self, app, decor):
        """⚠️ Tant qu'il n'est pas envoyé, il ne doit pas encombrer la file du
        coordinateur : on examine une intention, pas une saisie en cours."""
        c = _comme(app, decor["champ"], decor["ent"])
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "Pas fini"})
        vu = _comme(app, decor["coord"], decor["ent"])
        ids = [r["id"] for r in vu.get("/api/propositions/a_examiner").get_json()["requests"]]
        assert ids == []
        assert c.post("/api/propositions/envoyer", json={}).status_code == 201
        apres = vu.get("/api/propositions/a_examiner").get_json()
        assert len(apres["requests"]) == 1
        assert apres["requests"][0]["status"] == "pending"

    def test_envoyer_sans_rien_est_refuse(self, app, decor):
        c = _comme(app, decor["champ"], decor["ent"])
        r = c.post("/api/propositions/envoyer", json={})
        assert r.status_code == 400 and r.get_json()["code"] == "vide"


# ══════════════════════════════════════════════════════════════════════════
class TestAppliquerEstToutOuRien:

    def _deposer(self, app, decor, gestes=None):
        c = _comme(app, decor["champ"], decor["ent"])
        for url, corps in (gestes or [
            ("/tasks/add", {"activity_id": decor["act"], "name": "Peser"}),
            ("/skills/add", {"activity_id": decor["act"], "description": "Lire un plan"}),
        ]):
            c.post(url, json=corps)
        c.post("/api/propositions/envoyer", json={"message": "à relire"})
        from Code.models.models import ActivityChangeRequest
        with app.app_context():
            return ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"], status="pending").first().id

    def test_appliquer_ECRIT_tout_en_base(self, app, decor):
        from Code.models.models import Competency, Task
        rid = self._deposer(app, decor)
        vu = _comme(app, decor["coord"], decor["ent"])
        r = vu.post("/api/propositions/%d/approve" % rid, json={"comment": "ok"})
        assert r.status_code == 200 and r.get_json()["n"] == 2
        with app.app_context():
            assert Task.query.filter_by(activity_id=decor["act"]).count() == 1
            assert Competency.query.filter_by(activity_id=decor["act"]).count() == 1

    def test_un_geste_impossible_ANNULE_les_autres(self, app, decor):
        """⚠️ Chaque route appelée fait son propre `commit()`. Rejoués tels
        quels, cinq gestes donnent cinq transactions : si le troisième
        échoue, les deux premiers sont déjà écrits et personne ne peut dire
        où la proposition s'est arrêtée."""
        from Code.models.models import ActivityChangeRequest, Task
        rid = self._deposer(app, decor, gestes=[
            ("/tasks/add", {"activity_id": decor["act"], "name": "Première"}),
        ])
        # ⚠️ Le geste fantôme est INJECTÉ : il ne peut pas naître d'un clic,
        # puisque la porte ne détourne que ce qu'elle saura rejouer. C'est
        # pourtant le cas réel — l'objet visé a disparu entre le dépôt et
        # l'examen, et c'est tout l'intérêt de faire relire par quelqu'un.
        with app.app_context():
            cr = db.session.get(ActivityChangeRequest, rid)
            liste = json.loads(cr.actions)
            liste.append({"op": "task.update", "chemin": "/tasks/999999",
                          "methode": "PUT", "corps": {"name": "fantôme"},
                          "activity_id": decor["act"], "activite": None,
                          "objet": "fantôme"})
            cr.actions = json.dumps(liste, ensure_ascii=False)
            db.session.commit()

        vu = _comme(app, decor["coord"], decor["ent"])
        r = vu.post("/api/propositions/%d/approve" % rid, json={})
        assert r.status_code == 409
        corps = r.get_json()
        assert corps["code"] == "rejeu"
        assert corps["objet"] == "fantôme", "on dit LEQUEL a bloqué"
        with app.app_context():
            assert Task.query.filter_by(activity_id=decor["act"]).count() == 0, \
                "rien n'est écrit quand un geste échoue"
            assert db.session.get(ActivityChangeRequest, rid).status == "pending", \
                "la proposition reste examinable"

    def test_refuser_n_ecrit_rien(self, app, decor):
        from Code.models.models import ActivityChangeRequest, Task
        rid = self._deposer(app, decor)
        vu = _comme(app, decor["coord"], decor["ent"])
        assert vu.post("/api/propositions/%d/reject" % rid,
                       json={"comment": "non"}).status_code == 200
        with app.app_context():
            assert Task.query.filter_by(activity_id=decor["act"]).count() == 0
            cr = db.session.get(ActivityChangeRequest, rid)
            assert cr.status == "rejected" and cr.review_comment == "non"

    def test_une_proposition_deja_tranchee_ne_se_rejoue_pas(self, app, decor):
        rid = self._deposer(app, decor)
        vu = _comme(app, decor["coord"], decor["ent"])
        vu.post("/api/propositions/%d/approve" % rid, json={})
        r = vu.post("/api/propositions/%d/approve" % rid, json={})
        assert r.status_code == 409


# ══════════════════════════════════════════════════════════════════════════
class TestQuiTrancheEtQuiVoit:

    def _envoyee(self, app, decor):
        c = _comme(app, decor["champ"], decor["ent"])
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "X"})
        c.post("/api/propositions/envoyer", json={})
        from Code.models.models import ActivityChangeRequest
        with app.app_context():
            return ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"], status="pending").first().id

    def test_un_champion_ne_tranche_pas(self, app, decor):
        rid = self._envoyee(app, decor)
        c = _comme(app, decor["champ"], decor["ent"])
        assert c.post("/api/propositions/%d/approve" % rid, json={}).status_code == 403
        assert c.post("/api/propositions/%d/reject" % rid, json={}).status_code == 403

    def test_un_user_ne_voit_pas_la_file(self, app, decor):
        self._envoyee(app, decor)
        c = _comme(app, decor["simple"], decor["ent"])
        assert c.get("/api/propositions/a_examiner").get_json()["requests"] == []

    def test_on_ne_s_alerte_pas_SOI_MEME(self, app, decor):
        """Un coordinateur qui propose (sur une carto qu'il n'écrit pas) ne
        doit pas trouver sa propre proposition dans sa file."""
        from Code.models.models import ActivityChangeRequest
        with app.app_context():
            cr = ActivityChangeRequest(entity_id=decor["ent"], author_id=decor["coord"],
                                       status="pending", actions="[]")
            db.session.add(cr)
            db.session.commit()
        c = _comme(app, decor["coord"], decor["ent"])
        ids = [r["author_id"] for r in
               c.get("/api/propositions/a_examiner").get_json()["requests"]]
        assert decor["coord"] not in ids

    def test_l_auteur_retire_sa_proposition_tant_qu_elle_attend(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        rid = self._envoyee(app, decor)
        autre = _comme(app, decor["simple"], decor["ent"])
        assert autre.delete("/api/propositions/%d" % rid).status_code == 404
        c = _comme(app, decor["champ"], decor["ent"])
        assert c.delete("/api/propositions/%d" % rid).status_code == 200
        with app.app_context():
            assert db.session.get(ActivityChangeRequest, rid) is None

    def test_la_decision_est_annoncee_a_l_auteur(self, app, decor):
        rid = self._envoyee(app, decor)
        vu = _comme(app, decor["coord"], decor["ent"])
        vu.post("/api/propositions/%d/approve" % rid, json={"comment": "merci"})
        c = _comme(app, decor["champ"], decor["ent"])
        d = c.get("/api/propositions/decisions").get_json()["decisions"]
        assert len(d) == 1 and d[0]["review_comment"] == "merci"
        assert c.post("/api/propositions/decisions/vues",
                      json={"ids": [rid]}).get_json()["n"] == 1
        assert c.get("/api/propositions/decisions").get_json()["decisions"] == []

    def test_on_ne_marque_LU_que_ses_propres_propositions(self, app, decor):
        """⚠️ Les ids viennent du navigateur : ils ne suffisent jamais à
        écrire sur la ligne d'un autre."""
        rid = self._envoyee(app, decor)
        vu = _comme(app, decor["coord"], decor["ent"])
        vu.post("/api/propositions/%d/reject" % rid, json={})
        autre = _comme(app, decor["simple"], decor["ent"])
        assert autre.post("/api/propositions/decisions/vues",
                          json={"ids": [rid]}).get_json()["n"] == 0


# ══════════════════════════════════════════════════════════════════════════
class TestCeQuiSeLitAlEcran:

    def test_le_libelle_se_REBATIT_a_la_lecture(self, app, decor):
        """⚠️ Le champion propose dans SA langue, le coordinateur lit dans la
        SIENNE. Un libellé figé à l'écriture afficherait « Ajouter la tâche »
        à un anglophone — la leçon du journal d'activité récente."""
        c = _comme(app, decor["champ"], decor["ent"])
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "Peser"})
        g = c.get("/api/propositions/brouillon").get_json()["brouillon"]["gestes"][0]
        assert g["op"] == "task.add" and g["objet"] == "Peser"
        assert "Ajouter" not in json.dumps(g), "aucune phrase figée dans la donnée"
        # Et le chemin de la requête ne sort JAMAIS : il ne dit rien au lecteur.
        assert "chemin" not in g and "corps" not in g

    def test_un_OUTIL_n_est_rattache_a_aucune_activite(self, app, decor):
        """C'est le catalogue de la carto : lui inventer une activité ferait
        paraître le geste sous une fiche qui ne le porte pas."""
        c = _comme(app, decor["champ"], decor["ent"])
        # ⚠️ Le corps PORTE une activité (la création part du panneau d'une
        # tâche) : la retenir ferait paraître le geste sous une fiche qui ne
        # porte pas cet outil.
        r = c.post("/gestion_outils/api/tools",
                   json={"name": "Pied à coulisse", "activity_id": decor["act"]})
        assert r.status_code == 202
        g = c.get("/api/propositions/brouillon").get_json()["brouillon"]["gestes"][0]
        assert g["op"] == "tool.add"
        assert g["activity_id"] is None and not g["activite"]

    def test_les_deux_familles_se_distinguent_par_une_CLE(self, app):
        """⚠️ Les identifiants des deux tables se chevauchent : la proposition
        de carto n° 3 et celle d'activité n° 3 existent toutes les deux. La
        fenêtre d'examen ne travaille donc jamais sur `id` seul."""
        js = _lire(JS_EXAMEN)
        assert "cle: 'c' + r.id" in js and "cle: 'a' + r.id" in js
        assert "function retirer(cle)" in js
        assert ".map((x) => x.cle)" in js
        assert "choisir(item.dataset.id)" in js, "la clé, pas un entier"

    def test_l_ecran_enveloppe_fetch_plutot_que_huit_fichiers(self, app):
        """Les tâches, outils, compétences, savoirs, HSC et contraintes sont
        écrits par autant de scripts. Les reprendre un par un, c'est autant
        d'occasions d'en oublier un — et le neuvième écrit demain."""
        js = _lire(JS_ECRAN)
        assert "window.__acpFetch = window.fetch.bind(window)" in js
        assert "r.status !== 202" in js
        assert "r.clone().json()" in js, "un flux de réponse ne se lit qu'une fois"

    def test_le_geste_ajoute_est_un_TOAST_pas_une_modale(self, app):
        """Corriger une fiche c'est cinq ou six gestes : une fenêtre à fermer
        entre chacun transformerait la saisie en parcours d'obstacles."""
        js = _lire(JS_ECRAN)
        bloc = js.split("if (!j || j.code !== 'proposition') return r;", 1)[1] \
                 .split("return r;", 1)[0]
        assert "toast(" in bloc and "signaler(" not in bloc

    def test_le_bandeau_n_est_rendu_que_pour_qui_propose(self, app):
        g = _lire(GABARIT)
        assert "{% if propose_activites %}" in g
        assert g.count("{% endif %}") >= 1

    def test_les_libelles_sont_dans_les_deux_langues(self, app):
        from Code.translations import TRANSLATIONS as T
        fr = {k for k in T["fr"] if k.startswith(("acp.", "map.acces_ouvre"))}
        en = {k for k in T["en"] if k.startswith(("acp.", "map.acces_ouvre"))}
        assert fr == en and len(fr) > 40
        # Les clés lues par le gabarit sont toutes dans le catalogue.
        import re
        for cle in set(re.findall(r"t\('(acp\.[a-z_0-9]+)'\)", _lire(GABARIT))):
            assert cle in T["fr"] and cle in T["en"], cle

    def test_les_deux_conventions_de_substitution_ne_se_melangent_pas(self, app):
        """⚠️ `{n}` est lu par `carto_examen.js`, `[[n]]` par
        `activite_propositions.js`. Une clé qui prend la mauvaise affiche son
        marqueur TEL QUEL, et rien ne lève d'erreur — relevé à l'écran avec
        « [[N]] MODIFICATIONS PROPOSÉES »."""
        from Code.translations import TRANSLATIONS as T
        for langue in ("fr", "en"):
            for cle, valeur in T[langue].items():
                if not isinstance(valeur, str):
                    continue
                if cle.startswith("examen."):
                    assert "[[" not in valeur, "%s : lu avec la convention {n}" % cle
                if cle.startswith("acp.") and "{" in valeur:
                    assert "{n}" not in valeur, "%s : lu avec la convention [[n]]" % cle


# ══════════════════════════════════════════════════════════════════════════
class TestLeMenageEtLeBandeau:

    def test_supprimer_une_carto_efface_ses_propositions(self, app, decor):
        """⚠️ PostgreSQL applique les clés étrangères : sans ce ménage,
        effacer une carto qui en porte échouerait."""
        from Code.models.models import ActivityChangeRequest, Entity
        c = _comme(app, decor["champ"], decor["ent"])
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "X"})
        vu = _comme(app, decor["coord"], decor["ent"])
        r = vu.delete("/activities/api/entities/%d" % decor["ent"])
        assert r.status_code in (200, 204), r.get_data(as_text=True)[:200]
        with app.app_context():
            assert ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"]).count() == 0
            # L'entité est partie : la fixture n'aura plus rien à nettoyer.
            assert db.session.get(Entity, decor["ent"]) is None

    def test_le_bandeau_de_la_page_carte_compte_les_DEUX_files(self, app, decor):
        """Un coordinateur décide au même endroit. Un bandeau qui n'en
        compterait qu'une laisserait l'autre dormir — c'est ce qui faisait
        manquer les propositions quand elles vivaient dans la page RH."""
        from Code.models.models import CartoChangeRequest
        c = _comme(app, decor["champ"], decor["ent"])
        c.post("/tasks/add", json={"activity_id": decor["act"], "name": "X"})
        c.post("/api/propositions/envoyer", json={})
        with app.app_context():
            db.session.add(CartoChangeRequest(
                entity_id=decor["ent"], author_id=decor["champ"],
                status="pending", diagram="{}"))
            db.session.commit()

        vu = _comme(app, decor["coord"], decor["ent"])
        with vu.session_transaction():
            pass
        with app.test_request_context("/activities/map"):
            from flask import session as sess
            sess["user_id"] = decor["coord"]
            sess["active_entity_id"] = decor["ent"]
            from Code.routes.activities_map import _examen_en_attente
            etat = _examen_en_attente()
        assert etat and etat["n"] == 2, etat
        with app.app_context():
            CartoChangeRequest.query.filter_by(entity_id=decor["ent"]).delete()
            db.session.commit()

    def test_la_popup_acces_dit_ce_que_l_acces_OUVRE(self, app):
        """⚠️ Cet écran décide QUI entre, et ne disait nulle part ce qu'on y
        fait. Ouvrir une carto ouvre désormais aussi le droit de proposer sur
        ses tâches et ses outils."""
        js = _lire(os.path.join(RACINE, "static", "js", "carto_acces.js"))
        assert "function ceQueCaOuvre()" in js
        assert "${ceQueCaOuvre()}" in js
        # Il RENVOIE vers le seul écran qui le règle — il ne le règle pas lui-même.
        assert "acc-bloc-droits" in js
        from Code.translations import TRANSLATIONS as T
        assert "tâches, outils et compétences" in T["fr"]["map.acces_ouvre_champion"]
        assert "tasks, tools and competencies" in T["en"]["map.acces_ouvre_champion"]
