# -*- coding: utf-8 -*-
"""LE PALIER DE SOUMISSION — une carto ne part à l'examen que complète.

« Sur une carto de cent activités, si on dépose une demande dès qu'on met un
truc, on va faire des centaines de demandes pour remplir la carto. »

Ce que ces cas tiennent, dans l'ordre d'importance :

1. **la simulation n'écrit RIEN** — elle rejoue les vraies routes pour savoir
   ce que le brouillon donnerait ; une ligne laissée derrière elle serait une
   écriture que personne n'a demandée ;
2. **le brouillon COMPTE** — sur une carto commune tout ce que le champion
   écrit est détourné et n'atteint jamais la base : mesuré sur la base seule,
   le palier ne se franchirait JAMAIS ;
3. le périmètre (un résultat, une activité d'une autre carto ne bloquent pas),
   sans quoi le palier serait inatteignable ;
4. les trois exigences, chacune seule ;
5. le refus d'`/envoyer`, qui a le dernier mot.

⚠️ Ce fichier se donne SA PROPRE carto, avec un `owner_id`. C'est la règle du
14/11 : une entité de test sans propriétaire est lisible par TOUT LE MONDE et
devient le repli des fichiers suivants, et écrire dans la carto du décor
commun fait échouer un fichier qui ne parle pas du même sujet.
"""
import io
import json
import os
import re

import pytest
from sqlalchemy import event

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "activite_propositions.js")
CSS = os.path.join(RACINE, "static", "activite_propositions.css")
GABARIT = os.path.join(RACINE, "Code", "routes", "templates",
                       "activite_propositions.html")

_N = [0]


def _lire(p):
    return io.open(p, encoding="utf-8").read()


def _corps(js, ancre):
    """Le corps d'une fonction, borné sur sa propre accolade fermante.

    ⚠️ Jamais une longueur fixe : des cliquets de ce dépôt ont déjà rougi
    pour avoir découpé n signes après une ancre, simplement parce qu'un
    commentaire s'était glissé dedans."""
    i = js.index(ancre)
    j = js.index("{", i)
    niveau, k = 0, j
    while k < len(js):
        if js[k] == "{":
            niveau += 1
        elif js[k] == "}":
            niveau -= 1
            if niveau == 0:
                return js[j:k + 1]
        k += 1
    raise AssertionError("corps non borné pour %r" % ancre)


@pytest.fixture
def carto(app):
    """Un coordinateur, un champion, une carto COMMUNE, une activité nue."""
    from Code.models.models import Activities, Entity, User
    from Code.security import hash_password

    _N[0] += 1
    n = _N[0]
    with app.app_context():
        faire = lambda r, s: User(
            first_name=r.capitalize(), last_name="S%d" % n,
            email="%s%d@socle.test" % (r, n), password=hash_password("x"),
            status=s)
        coord, champ = faire("coord", "coordinateur"), faire("champ", "champion")
        db.session.add_all([coord, champ])
        db.session.commit()

        ent = Entity(name="Socle carto %d" % n, owner_id=coord.id, is_shared=True)
        db.session.add(ent)
        db.session.commit()
        act = Activities(name="Socle activité %d" % n, entity_id=ent.id,
                         is_result=False)
        db.session.add(act)
        db.session.commit()
        d = {"coord": coord.id, "champ": champ.id, "ent": ent.id,
             "act": act.id, "n": n}
    yield d
    _ranger(app, d)


def _ranger(app, d):
    with app.app_context():
        from Code.models.models import (ActivityChangeRequest, Activities,
                                        Entity, Role, Task, Tool, User,
                                        activity_roles, task_tools)
        ids_a = [a.id for a in Activities.query.filter_by(entity_id=d["ent"])]
        ids_t = [t.id for t in Task.query.filter(Task.activity_id.in_(ids_a))] \
            if ids_a else []
        if ids_t:
            db.session.execute(
                task_tools.delete().where(task_tools.c.task_id.in_(ids_t)))
            Task.query.filter(Task.activity_id.in_(ids_a)).delete(
                synchronize_session=False)
        if ids_a:
            db.session.execute(activity_roles.delete().where(
                activity_roles.c.activity_id.in_(ids_a)))
        ActivityChangeRequest.query.filter_by(entity_id=d["ent"]).delete()
        Tool.query.filter_by(entity_id=d["ent"]).delete()
        Role.query.filter_by(entity_id=d["ent"]).delete()
        Activities.query.filter_by(entity_id=d["ent"]).delete()
        Entity.query.filter_by(id=d["ent"]).delete()
        User.query.filter(User.id.in_([d["coord"], d["champ"]])).delete(
            synchronize_session=False)
        db.session.commit()


def _comme(app, uid, entity_id):
    """Un client PROPRE. ⚠️ `client` et `auth_client` sont le MÊME objet en
    portée session : s'en servir ici déconnecterait les fichiers suivants."""
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["active_entity_id"] = entity_id
    return c


def _etat(app, carto, qui="champ"):
    from Code.models.models import Entity, User
    from Code.socle_activites import etat
    with app.test_request_context():
        from flask import session
        session["user_id"] = carto[qui]
        session["active_entity_id"] = carto["ent"]
        return etat(db.session.get(User, carto[qui]),
                    db.session.get(Entity, carto["ent"]))


def _garant(app, carto, activity_id=None):
    from Code.models.models import Role, activity_roles
    with app.app_context():
        r = Role(name="Garant %d" % carto["n"], entity_id=carto["ent"])
        db.session.add(r)
        db.session.flush()
        db.session.execute(activity_roles.insert().values(
            activity_id=activity_id or carto["act"], role_id=r.id,
            status="Garant"))
        db.session.commit()


def _tache(app, carto, avec_outil=True, activity_id=None):
    from Code.models.models import Task, Tool
    with app.app_context():
        t = Task(name="Tâche %d" % carto["n"],
                 activity_id=activity_id or carto["act"])
        if avec_outil:
            o = Tool(name="Outil %d" % carto["n"], entity_id=carto["ent"])
            db.session.add(o)
            db.session.flush()
            t.tools.append(o)
        db.session.add(t)
        db.session.commit()


def _complete(app, carto, activity_id=None):
    _garant(app, carto, activity_id)
    _tache(app, carto, True, activity_id)


# ══════════════════════════════════════════════════════════════════════════
class TestLaSimulationNEcritRien:
    """⚠️⚠️ Le point le plus grave de tout le module. La mesure REJOUE les
    vraies routes — c'est la seule façon de n'avoir qu'une idée de ce
    qu'« ajouter une tâche » veut dire. Mais une simulation qui laisse une
    ligne derrière elle a écrit sans qu'on le lui demande, et le brouillon
    serait appliqué deux fois à l'arrivée."""

    def test_lire_le_socle_n_ecrit_AUCUNE_ligne(self, app, carto):
        from Code.models.models import Task
        c = _comme(app, carto["champ"], carto["ent"])
        # Détourné : la tâche part au brouillon, pas en base.
        assert c.post("/tasks/add", json={"activity_id": carto["act"],
                                          "name": "Proposée"}).status_code == 202
        with app.app_context():
            avant = Task.query.filter_by(activity_id=carto["act"]).count()
        assert avant == 0, "la porte doit détourner, pas écrire"

        # On lit le socle deux fois : si la simulation validait, la seconde
        # lecture compterait la tâche de la première.
        _etat(app, carto)
        _etat(app, carto)
        with app.app_context():
            assert Task.query.filter_by(activity_id=carto["act"]).count() == 0

    def test_et_la_session_reste_UTILISABLE_apres(self, app, carto):
        """⚠️ Une vue qui lève laisse la session en attente d'annulation :
        toute requête suivante échouerait. L'annulation est dans un
        `finally`, et on le vérifie en relisant juste après."""
        from Code.models.models import Task
        c = _comme(app, carto["champ"], carto["ent"])
        c.post("/tasks/add", json={"activity_id": carto["act"], "name": "X"})
        _etat(app, carto)
        with app.app_context():
            assert Task.query.filter_by(activity_id=carto["act"]).count() == 0


# ══════════════════════════════════════════════════════════════════════════
class TestLeBrouillonCompte:
    """⚠️ Sur une carto COMMUNE, tout ce que le champion écrit est détourné
    (`ecriture.porte` → 202) et n'atteint jamais la base. Mesuré sur la base
    seule, le palier annoncerait « 0 activité complète » quel que soit le
    travail fourni — il ne se franchirait jamais, et la fonction serait un
    mur."""

    def test_la_base_seule_dirait_TOUJOURS_incomplet(self, app, carto):
        assert _etat(app, carto)["complet"] is False

    def test_le_brouillon_FRANCHIT_le_palier(self, app, carto):
        c = _comme(app, carto["champ"], carto["ent"])
        r = c.post("/roles/garant/activity/%d" % carto["act"],
                   json={"role_name": "Métrologie"})
        assert r.status_code == 202, r.get_data(as_text=True)
        t = c.post("/tasks/add", json={"activity_id": carto["act"],
                                       "name": "Peser"})
        assert t.status_code == 202

        # ⚠️ L'outil se rattache à une TÂCHE, et la tâche n'existe pas encore
        # en base : son identifiant ne sera connu qu'au rejeu. On outille donc
        # la tâche du SOCLE — celle que le champion verra dans sa fiche — en
        # créant d'abord la tâche en base… ce qui n'est PAS le cas réel.
        # Le cas réel est couvert par `test_outiller_une_tache_se_propose`.
        etat = _etat(app, carto)
        assert etat["manque"]["garant"] == 0, etat
        assert etat["manque"]["tache"] == 0, etat
        assert etat["manque"]["outil"] == 1, "la tâche proposée n'a pas d'outil"

    def test_outiller_une_tache_se_propose(self, app, carto):
        """⚠️⚠️ `POST /tools/add` RATTACHE un outil à une tâche, et il
        manquait à `_SEGMENTS` : le champion se le faisait refuser avec
        `lecture_seule`, le motif réservé à `user`. Même famille que l'oubli
        du garant — et bloquant depuis le palier, qui exige un outil."""
        from Code.models.models import Task, Tool
        _garant(app, carto)
        _tache(app, carto, avec_outil=False)
        with app.app_context():
            tid = Task.query.filter_by(activity_id=carto["act"]).first().id
            o = Tool(name="Balance %d" % carto["n"], entity_id=carto["ent"])
            db.session.add(o)
            db.session.commit()
            oid = o.id

        assert _etat(app, carto)["manque"]["outil"] == 1

        c = _comme(app, carto["champ"], carto["ent"])
        r = c.post("/tools/add", json={"task_id": tid, "existing_tool_ids": [oid]})
        assert r.status_code == 202, r.get_data(as_text=True)
        assert r.get_json()["code"] == "proposition"

        etat = _etat(app, carto)
        assert etat["complet"] is True, etat

    def test_le_geste_d_outillage_se_LIT_sous_son_activite(self, app, carto):
        """Un outil du CATALOGUE n'appartient à aucune activité — mais celui
        qu'on rattache à une tâche concerne bien sa fiche, et c'est là qu'on
        vient le relire. Et le verbe suit le CHEMIN : `POST /tools/delete`
        détache, il ne se lit pas « Ajouter »."""
        from Code.models.models import Task
        _tache(app, carto, avec_outil=False)
        with app.app_context():
            tid = Task.query.filter_by(activity_id=carto["act"]).first().id
        c = _comme(app, carto["champ"], carto["ent"])
        c.post("/tools/add", json={"task_id": tid, "new_tools": ["Clé", "Pige"]})
        j = c.get("/api/propositions/brouillon").get_json()
        g = j["brouillon"]["gestes"][0]
        assert g["op"] == "tool.add"
        assert g["activity_id"] == carto["act"], g
        assert g["objet"].startswith("Clé"), g["objet"]
        assert "+1" in g["objet"], "les deux outils sont nommés, pas comptés"

        c.post("/tools/delete", json={"task_id": tid, "tool_id": 1})
        j = c.get("/api/propositions/brouillon").get_json()
        assert j["brouillon"]["gestes"][-1]["op"] == "tool.delete"


# ══════════════════════════════════════════════════════════════════════════
class TestLesTroisExigences:

    @pytest.mark.parametrize("absent", ["garant", "tache", "outil"])
    def test_chacune_seule_suffit_a_bloquer(self, app, carto, absent):
        if absent != "garant":
            _garant(app, carto)
        if absent == "outil":
            _tache(app, carto, avec_outil=False)
        elif absent != "tache":
            _tache(app, carto, avec_outil=True)
        etat = _etat(app, carto, qui="coord")
        assert etat["complet"] is False
        assert etat["manque"][absent] == 1, etat

    def test_les_trois_ensemble_donnent_complet(self, app, carto):
        _complete(app, carto)
        etat = _etat(app, carto, qui="coord")
        assert etat["complet"] is True
        assert etat["pretes"] == etat["total"] == 1
        assert etat["activites"] == []

    def test_un_outil_se_compte_PAR_LA_TACHE(self, app, carto):
        """Un outil n'appartient pas à une activité : c'est le catalogue de la
        carto, et il se rattache à une tâche. « Au moins un outil » veut donc
        dire : au moins une tâche de cette activité est outillée. Un outil posé
        dans le catalogue et rattaché à RIEN ne compte pas."""
        from Code.models.models import Tool
        _garant(app, carto)
        _tache(app, carto, avec_outil=False)
        with app.app_context():
            db.session.add(Tool(name="Orphelin", entity_id=carto["ent"]))
            db.session.commit()
        assert _etat(app, carto, qui="coord")["manque"]["outil"] == 1

    def test_l_activite_incomplete_est_NOMMEE(self, app, carto):
        """Un compteur ne dit pas où aller. « Il manque un garant sur 39 »
        sans les noms laisse chercher dans la liste."""
        etat = _etat(app, carto, qui="coord")
        noms = [a["nom"] for a in etat["activites"]]
        assert noms == ["Socle activité %d" % carto["n"]]
        assert set(etat["activites"][0]["manque"]) == {"garant", "tache", "outil"}


# ══════════════════════════════════════════════════════════════════════════
class TestLePerimetre:
    """⚠️ « Chaque activité » veut dire chaque activité que la carto TIENT.
    Exiger les trois d'un RÉSULTAT ou d'une activité d'une AUTRE carto rendrait
    le palier inatteignable — donc inutile."""

    def test_un_RESULTAT_ne_bloque_pas(self, app, carto):
        from Code.models.models import Activities
        _complete(app, carto)
        with app.app_context():
            db.session.add(Activities(name="Dossier complet",
                                      entity_id=carto["ent"], is_result=True))
            db.session.commit()
        etat = _etat(app, carto, qui="coord")
        assert etat["complet"] is True, etat
        assert etat["total"] == 1, "le résultat n'est pas compté"

    @pytest.mark.parametrize("sous_type", ["external", "extco"])
    def test_une_activite_d_une_AUTRE_carto_ne_bloque_pas(self, app, carto,
                                                          sous_type):
        """La règle n'est pas inventée ici : `activities_map` écarte déjà ces
        deux sous-types quand il cherche « la vraie activité »."""
        from Code.models.models import Activities
        _complete(app, carto)
        with app.app_context():
            db.session.add(Activities(name="Chez le voisin",
                                      entity_id=carto["ent"], is_result=False,
                                      shape_subtype=sous_type))
            db.session.commit()
        etat = _etat(app, carto, qui="coord")
        assert etat["complet"] is True, etat
        assert etat["total"] == 1

    def test_une_activite_NORMALE_de_plus_bloque(self, app, carto):
        """Le garde-fou du garde-fou : si le périmètre écartait tout, les deux
        cas ci-dessus passeraient au vert sans rien prouver."""
        from Code.models.models import Activities
        _complete(app, carto)
        with app.app_context():
            db.session.add(Activities(name="Deuxième vraie",
                                      entity_id=carto["ent"], is_result=False,
                                      shape_subtype="normal"))
            db.session.commit()
        etat = _etat(app, carto, qui="coord")
        assert etat["complet"] is False
        assert etat["total"] == 2 and etat["pretes"] == 1


# ══════════════════════════════════════════════════════════════════════════
class TestLEnvoi:

    def _brouillon(self, app, carto):
        c = _comme(app, carto["champ"], carto["ent"])
        c.post("/tasks/add", json={"activity_id": carto["act"], "name": "Z"})
        return c

    def test_envoyer_est_REFUSE_avec_l_etat(self, app, carto):
        c = self._brouillon(app, carto)
        r = c.post("/api/propositions/envoyer", json={})
        assert r.status_code == 409
        j = r.get_json()
        assert j["code"] == "socle"
        # ⚠️ Le refus PORTE l'état : « erreur » n'apprend rien, « il manque un
        # garant » dit quoi faire.
        assert j["socle"]["complet"] is False
        assert j["socle"]["manque"]["garant"] == 1

    def test_et_la_proposition_RESTE_un_brouillon(self, app, carto):
        from Code.models.models import ActivityChangeRequest
        c = self._brouillon(app, carto)
        c.post("/api/propositions/envoyer", json={})
        with app.app_context():
            cr = ActivityChangeRequest.query.filter_by(entity_id=carto["ent"]).first()
            assert cr.status == "draft", "refusé n'est pas envoyé"
            assert cr.submitted_at is None

    def test_une_fois_complete_l_envoi_PASSE(self, app, carto):
        """Le palier se libère tout seul : il n'y a pas de « première
        version » à marquer, le contrôle est « la carto est complète »."""
        _complete(app, carto)
        c = _comme(app, carto["champ"], carto["ent"])
        c.post("/tasks/add", json={"activity_id": carto["act"], "name": "Z"})
        r = c.post("/api/propositions/envoyer", json={})
        assert r.status_code == 201, r.get_data(as_text=True)

    def test_le_socle_se_lit_par_sa_route(self, app, carto):
        c = _comme(app, carto["champ"], carto["ent"])
        j = c.get("/api/propositions/socle").get_json()
        assert j["total"] == 1 and j["complet"] is False

    def test_sans_connexion_401(self, app):
        """⚠️ Un client PROPRE : `client` arrive connecté dès qu'un fichier
        précédent s'est authentifié, et ce cas ne passerait qu'en premier."""
        c = app.test_client()
        assert c.get("/api/propositions/socle").status_code == 401


# ══════════════════════════════════════════════════════════════════════════
class TestUnGesteQuiNeSAppliquePlus:

    def test_il_bloque_et_le_DIT(self, app, carto):
        """Mesurer « ce que les gestes d'avant donnent » laisserait croire à un
        envoi possible que `rejouer` refuserait de toute façon."""
        from Code.models.models import ActivityChangeRequest
        _complete(app, carto)
        c = _comme(app, carto["champ"], carto["ent"])
        c.post("/tasks/add", json={"activity_id": carto["act"], "name": "Z"})
        with app.app_context():
            cr = ActivityChangeRequest.query.filter_by(entity_id=carto["ent"]).first()
            liste = json.loads(cr.actions)
            liste.append({"op": "task.update", "chemin": "/tasks/999999",
                          "methode": "PUT", "corps": {"name": "fantôme"},
                          "activity_id": carto["act"], "activite": None,
                          "objet": "fantôme"})
            cr.actions = json.dumps(liste, ensure_ascii=False)
            db.session.commit()
        etat = _etat(app, carto)
        assert etat["complet"] is False
        assert etat["rejeu"] and etat["rejeu"]["rang"] == 2
        r = c.post("/api/propositions/envoyer", json={})
        assert r.status_code == 409 and r.get_json()["code"] == "socle"


# ══════════════════════════════════════════════════════════════════════════
class TestLeCout:
    """⚠️ Quatre requêtes, et pas une liste d'identifiants en paramètre : une
    carto du pilote porte 601 activités. C'est le défaut qui mettait le
    tableau global de la page RH à deux minutes et demie."""

    def test_le_cout_ne_grandit_pas_avec_la_carto(self, app, carto):
        from Code.models.models import Activities, Entity
        from Code.socle_activites import manques

        def compter():
            n = [0]

            def top(conn, cur, sql, params, ctx, many):
                n[0] += 1

            with app.app_context():
                ent = db.session.get(Entity, carto["ent"])
                event.listen(db.engine, "before_cursor_execute", top)
                try:
                    manques(ent)
                finally:
                    event.remove(db.engine, "before_cursor_execute", top)
            return n[0]

        avant = compter()
        with app.app_context():
            for i in range(12):
                db.session.add(Activities(name="Renfort %d-%d" % (carto["n"], i),
                                          entity_id=carto["ent"], is_result=False))
            db.session.commit()
        assert compter() == avant, "le coût suit la carto, pas une constante"
        assert avant <= 6, avant

    def test_aucune_liste_d_identifiants_en_parametre(self, app, carto):
        """Un `IN (…)` de six cents identifiants grandit avec la carto — et
        SQLite borne le nombre de paramètres d'une requête.

        ⚠️ On regarde le SQL RÉELLEMENT envoyé, pas le source : un cliquet qui
        relit un `.py` rougit dans l'arbre d'image, compilé en bytecode — le
        piège s'est présenté sept fois dans ce dépôt. Réécrit sur le
        comportement, il garde en plus les `IN` qu'un ORM poserait tout seul.
        """
        from Code.models.models import Activities, Entity
        from Code.socle_activites import manques

        def parametres():
            vus = []

            def top(conn, cur, sql, params, ctx, many):
                vus.append(len(params or ()))

            with app.app_context():
                ent = db.session.get(Entity, carto["ent"])
                event.listen(db.engine, "before_cursor_execute", top)
                try:
                    manques(ent)
                finally:
                    event.remove(db.engine, "before_cursor_execute", top)
            return vus

        avant = parametres()
        assert avant, "aucune requête observée"
        with app.app_context():
            for i in range(30):
                db.session.add(Activities(name="Masse %d-%d" % (carto["n"], i),
                                          entity_id=carto["ent"], is_result=False))
            db.session.commit()
        # ℹ️ Un `NOT IN (?, ?)` subsiste — les deux sous-types hors carto. Ce
        # n'est pas une liste d'identifiants : elle ne bouge pas d'un pouce.
        assert parametres() == avant, "le nombre de paramètres suit la carto"
        assert max(avant) <= 4, avant


# ══════════════════════════════════════════════════════════════════════════
class TestLEcran:

    def test_le_panneau_et_le_pied_SORTENT_du_defilement(self):
        """⚠️ Le panneau décide si l'envoi est possible et le pied le déclenche :
        les deux doivent rester sous les yeux. Mesuré avant correctif sur un
        portable 1366×768 — 3191 px de contenu pour 544 px visibles, et le
        bouton « Envoyer » tout en bas du défilement."""
        gab = _lire(GABARIT)
        # Trois zones sœurs du corps, pas trois blocs écrits DANS le corps.
        for ident in ('id="acp-socle-z"', 'id="acp-filtres"',
                      'id="acp-corps"', 'id="acp-pied-z"'):
            assert ident in gab, ident
        assert gab.index('id="acp-socle-z"') < gab.index('id="acp-corps"')
        assert gab.index('id="acp-corps"') < gab.index('id="acp-pied-z"')

        js = _lire(JS)
        # Le socle et le pied écrivent dans LEUR zone, jamais dans le corps.
        assert "getElementById('acp-socle-z')" in js
        assert "getElementById('acp-pied-z')" in js
        corps = _corps(js, "function rendreListe()")
        assert "data-envoyer" not in corps and "acp-msg" not in corps

        css = _lire(CSS)
        # Seul le corps défile ; les trois autres zones ne se laissent pas
        # écraser (`flex: none`).
        for cls in (".acp-socle-z", ".acp-filtres", ".acp-pied-z"):
            i = css.index(cls + " {")
            assert "flex: none" in css[i:css.index("}", i)], cls

    def test_la_fenetre_ne_se_borne_PAS_en_vh(self):
        """⚠️⚠️ `body.pg` porte `zoom: .8`, et les unités de fenêtre passent
        par ce zoom : `max-height: 88vh` bornait la fenêtre à 676 des 960 px
        CSS disponibles. On se mesure sur le VOILE, dont le `inset: 0` couvre
        bien l'écran. Même piège que la fenêtre de bienvenue."""
        css = _lire(CSS)
        i = css.index(".acp-boite {")
        boite = css[i:css.index("}", i)]
        assert "vh" not in boite, boite
        assert "max-height: 100%" in boite

    def test_le_bouton_est_eteint_mais_le_SERVEUR_tranche(self, app, carto):
        """⚠️ Le masquage n'est jamais une sécurité. Le bouton s'éteint ici, et
        `/envoyer` refuse de son côté — on le VÉRIFIE en appelant la route,
        pas en relisant son source : un cliquet qui lit un `.py` rougit dans
        l'arbre d'image, compilé en bytecode."""
        assert "disabled aria-disabled" in _lire(JS)
        c = _comme(app, carto["champ"], carto["ent"])
        c.post("/tasks/add", json={"activity_id": carto["act"], "name": "Z"})
        r = c.post("/api/propositions/envoyer", json={})
        assert r.status_code == 409 and r.get_json()["code"] == "socle"

    def test_le_refus_du_serveur_REMPLACE_le_message_d_erreur(self):
        """« Erreur » n'apprend rien. Le 409 porte l'état, et c'est lui qu'on
        affiche là où l'on vient de cliquer."""
        js = _lire(JS)
        assert "j.code === 'socle'" in js
        assert "S.socle = j.socle" in js

    def test_le_panneau_dit_que_RIEN_N_EST_PERDU(self):
        """La demande est explicite : le champion doit savoir que sa saisie est
        gardée d'une visite à l'autre, et qu'elle n'est pas pour autant une
        proposition déposée."""
        js = _lire(JS)
        assert "socle_garde" in js
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            assert TRANSLATIONS[lg]["acp.socle_garde"].strip()

    def test_le_socle_n_est_PAS_relu_a_chaque_geste(self):
        """Il coûte un rejeu simulé : le recalculer au rendu de chaque page —
        ou à chaque geste détourné — paierait un rejeu par frappe."""
        # ⚠️ Le corps de la fonction, borné sur sa propre accolade : le
        # découpage « 900 signes après l'ancre » avalait `ouvrir()`, qui
        # appelle légitimement `chargerSocle` — le cliquet rougissait sur du
        # code juste. C'est le piège documenté, et il a remordu ici.
        assert "chargerSocle" not in _corps(_lire(JS), "async function charger(")

    @pytest.mark.parametrize("cle", [
        "socle_titre", "socle_pourquoi", "socle_exige", "socle_barre",
        "socle_manque", "socle_liste", "socle_ok", "socle_garde",
        "socle_rejeu", "socle_c_garant", "socle_c_tache", "socle_c_outil",
        "socle_vide"])
    def test_chaque_cle_existe_dans_les_DEUX_langues(self, cle):
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            v = TRANSLATIONS[lg].get("acp." + cle)
            assert v and v.strip(), (lg, cle)

    @pytest.mark.parametrize("cle", [
        "socle_titre", "socle_pourquoi", "socle_exige", "socle_barre",
        "socle_manque", "socle_liste", "socle_ok", "socle_garde",
        "socle_rejeu", "socle_c_garant", "socle_c_tache", "socle_c_outil",
        "socle_vide"])
    def test_chaque_cle_est_INJECTEE(self, cle):
        """⚠️ `T()` rend la CLÉ quand elle manque, sans rien lever : une clé
        oubliée s'afficherait telle quelle. Et trois d'entre elles sont
        CONSTRUITES (`socle_c_` + code) — une analyse qui ne lit que les
        littéraux ne les verrait pas."""
        assert cle + ":" in _lire(GABARIT), cle

    def test_aucune_phrase_n_accorde_un_adjectif_sur_un_nombre(self):
        """« 1 activité prête sur 42 » et « 3 activités prêtes » demanderaient
        deux clés par langue, et l'anglais n'accorde pas au même seuil.
        « Prêtes : n sur t » se lit pareil à tous les comptes."""
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            v = TRANSLATIONS[lg]["acp.socle_barre"]
            assert "[[n]]" in v and "[[t]]" in v, (lg, v)
            assert "(s)" not in v

    def test_le_panneau_a_sa_feuille_de_style(self):
        css = _lire(CSS)
        for regle in (".acp-sb", ".acp-sb--ok", ".acp-ex", ".acp-sa",
                      ".acp-ok[disabled]"):
            assert regle in css, regle

    def test_le_chiffre_de_tete_compte_des_ACTIVITES(self):
        """⚠️⚠️ Le défaut relevé à l'usage : « ça me dit 1 truc manquant alors
        que j'ai rempli 30 % des activités ». Le serveur rendait le bon compte
        — mesuré `{garant: 0, outil: 26, tache: 26}` sur 36 activités — mais
        l'écran n'affichait qu'une pastille PAR FAMILLE. Quand une famille est
        complète partout (le garant vient de l'import carto), il n'en restait
        qu'UNE : on lisait « une chose manque » pour 26 activités."""
        js = _lire(JS)
        corps = _corps(js, "function rendreSocle()")
        # Le gros chiffre vient de (total − prêtes), pas d'un compte de familles.
        assert "nf('socle_restent', reste)" in corps
        assert "(s.total || 0) - (s.pretes || 0)" in corps
        # Les familles passent DANS le détail replié, pas en tête.
        assert "detailManque" in corps
        assert corps.index("socle_restent") < corps.index("detailManque")

        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            for cle in ("acp.socle_restent_1", "acp.socle_restent_n"):
                v = TRANSLATIONS[lg][cle]
                assert "[[n]]" in v, (lg, cle)
            assert TRANSLATIONS["en"][cle] != TRANSLATIONS["fr"][cle]

    def test_chaque_activite_a_completer_S_OUVRE(self):
        """Sans cela la liste est un rapport : elle dit ce qui manque et ne
        permet pas d'aller le remplir."""
        js = _lire(JS)
        assert "data-aller=" in _corps(js, "function rendreSocle()")
        aller = _corps(js, "function allerA(activityId)")
        assert "data-acp-act" in aller and "scrollIntoView" in aller
        assert "fermer()" in aller

    def test_aucune_regle_neuve_ne_lit_l_accent_doux_de_la_RACINE(self):
        """⚠️ `--pg-accent-soft` et ses trois frères sont déclarés sur `:root`,
        où `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS.
        Les mélanges s'écrivent sur place."""
        css = _lire(CSS)
        # Les commentaires d'abord : celui qui explique la règle la cite.
        nu = []
        reste = css
        while "/*" in reste:
            avant, _, suite = reste.partition("/*")
            nu.append(avant)
            _, _, reste = suite.partition("*/")
        nu.append(reste)
        propre = "".join(nu)
        for jeton in ("--pg-accent-soft", "--pg-accent-softer",
                      "--pg-accent-border", "--pg-accent-glow"):
            assert jeton not in propre, jeton


# ══════════════════════════════════════════════════════════════════════════
class TestLaFenetreSeParcourt:
    """« La première section ne fait aucun distingo visuel, ne propose aucun
    filtre, donc comme tout a la même tronche c'est pas très agréable d'aller
    chercher là-dedans. »

    Mesuré avant correctif, portable 1366×768, brouillon de 27 gestes :
    27 lignes identiques de 86 px, 2361 px de liste pour 544 px visibles."""

    def test_les_gestes_sont_GROUPES_par_famille(self):
        js = _lire(JS)
        corps = _corps(js, "function rendreListe()")
        assert "paquets" in corps and "famDe(e.g)" in corps
        assert "rangFam" in corps, "l'ordre des familles est celui du remplissage"
        assert 'class="acp-grp"' in corps and 'class="acp-gh"' in corps

    def test_chaque_famille_a_son_pictogramme_et_sa_couleur(self):
        """La couleur est celle de la PAGE où la donnée vit — Activités
        violet, Outils orange, Rôles vert — comme la fenêtre d'import. Ce
        n'est pas un arc-en-ciel décoratif."""
        js = _lire(JS)
        fam = _corps(js, "var FAM = ")
        for code in ("task", "tool", "savoir", "savoirfaire", "hsc",
                     "contrainte", "garant"):
            assert code + ":" in fam, code
        assert "#7c3aed" in fam and "#ea580c" in fam and "#059669" in fam

    def test_le_filtre_existe_et_ne_RE_REND_que_la_liste(self):
        """⚠️ Réécrire la barre à chaque frappe ferait perdre le curseur du
        champ qu'on tape — le piège déjà payé sur les cartes du plan de
        formation et sur l'autre sens de l'import."""
        js = _lire(JS)
        filtres = _corps(js, "function rendreFiltres()")
        assert "data-fam=" in filtres and "acp-rech" in filtres
        # `input`, jamais `change` : sur `change` le filtre n'agirait qu'à la
        # perte du focus, sans la moindre erreur pour le dire.
        assert "addEventListener('input'" in filtres
        # ⚠️ Les commentaires d'abord : celui qui explique la règle CITE le mot
        # interdit, et le cliquet se prenait lui-même. Septième occurrence de
        # ce piège dans ce dépôt.
        nu = re.sub(r"/\*.*?\*/", "", filtres, flags=re.S)
        nu = re.sub(r"(?m)^\s*//.*$", "", nu)
        assert "change" not in nu
        assert "rendreListe()" in nu and "rendreFiltres()" not in nu

    def test_le_filtre_retient_sur_l_objet_ET_l_activite(self):
        corps = _corps(_lire(JS), "function retenus()")
        assert "e.g.objet" in corps and "e.g.activite" in corps
        assert "toLowerCase()" in corps, "une recherche ne doit pas tenir à la casse"

    def test_les_familles_se_nomment_au_PLURIEL_sans_article(self):
        """⚠️ Les `f_*` portent leur article : ils se composent en « Ajouter
        la tâche ». Un en-tête de groupe qui les reprend affiche « LA TÂCHE 8 »,
        qui se lit comme un compte de la même tâche."""
        from Code.translations import TRANSLATIONS
        js = _lire(JS)
        assert "T('f_' + f)" not in js, "un en-tête de famille lit `g_`, pas `f_`"
        assert js.count("T('g_' + f)") >= 3
        for code in ("task", "tool", "savoir", "savoirfaire", "hsc",
                     "contrainte", "garant", "skill", "aptitude", "donnee"):
            cle = "acp.g_" + code
            assert cle in TRANSLATIONS["fr"] and cle in TRANSLATIONS["en"], cle
            fr, en = TRANSLATIONS["fr"][cle], TRANSLATIONS["en"][cle]
            for v in (fr, en):
                assert not v.lower().startswith(("la ", "le ", "l'", "the ")), v

    def test_les_libelles_neufs_sont_INJECTES(self):
        """`T()` rend la CLÉ quand elle manque : une clé oubliée s'afficherait
        telle quelle, sans la moindre erreur."""
        gab = _lire(GABARIT)
        js = _lire(JS)
        lues = set(re.findall(r"T\('((?:socle_|filtre_|g_)[a-z_0-9]+)'\)", js))
        lues |= set(re.findall(r"nf\('(socle_[a-z_]+)'", js))
        assert lues
        for cle in lues:
            if cle.endswith("_"):          # une clé construite : voir ci-dessous
                continue
            if cle.startswith("socle_restent"):
                cle = cle + "_1"
            assert re.search(r"\b%s:" % cle, gab), cle

    def test_le_pluriel_suit_la_LANGUE(self):
        """⚠️ Le singulier ne couvre pas les mêmes nombres : « 0 activité » en
        français, « 0 activities » en anglais."""
        corps = _corps(_lire(JS), "function nf(cle, n)")
        assert "L.lang === 'en'" in corps
        assert "(n === 1)" in corps and "(n < 2)" in corps

    def test_la_ligne_s_est_RESSERREE(self):
        """86 px par geste pour un verbe, un objet et une activité : la liste
        faisait 2361 px. Le verbe passe en méta à côté de l'activité."""
        js = _lire(JS)
        corps = _corps(js, "function rendreListe()")
        assert 'class="acp-verbe"' not in corps, "le verbe n'a plus sa ligne"
        css = _lire(CSS)
        i = css.index(".acp-grp .acp-l {")
        assert "padding: 6px 0" in css[i:css.index("}", i)]

    def test_le_nom_de_l_activite_n_est_pas_un_noeud_de_TEXTE_NU(self):
        """⚠️ Le `gap` d'une boîte flex ne s'applique qu'entre ÉLÉMENTS :
        relevé à l'écran, « AddManage Commercial Offer » collé."""
        corps = _corps(_lire(JS), "function rendreListe()")
        i = corps.index('class="acp-ou"')
        assert "<span>' + ou + '</span>" in corps[i:i + 220], corps[i:i + 220]
