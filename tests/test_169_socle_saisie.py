# -*- coding: utf-8 -*-
"""LE SOCLE — le premier remplissage d'une carto, et la bascule de régime.

« Un coordinateur crée une entité, lui importe une carto, la partage aux
champions ; l'un d'eux la remplit avec un import Excel. Au lieu d'une demande
par modification, le palier se met en place : il faut un garant, une tâche et
un outil par activité pour soumettre. Une fois validé, on rebascule dans
"une modification, une demande". »

Ce que ces cas tiennent, dans l'ordre d'importance :

1. **la saisie est DIRECTE pendant le premier remplissage** — sans quoi le
   découlement ne démarre même pas : l'import Excel ne vise que les cartos où
   le compte écrit, et `can_edit` rendait faux pour un champion ;
2. **et seulement là** : un `user` reste en lecture seule, le DIAGRAMME reste
   au coordinateur, et l'examen gèle la carto ;
3. la REPRISE, qui ne se joue qu'une fois — rejouée, elle validerait le socle
   de chaque carto qu'on est en train de remplir ;
4. les trois transitions et le refus de chacune ;
5. la bascule de régime, qui est le but de tout l'édifice.

⚠️ Ce fichier se donne SA PROPRE carto, avec un `owner_id`. Une entité de
test sans propriétaire est lisible par TOUT LE MONDE et devient le repli des
fichiers suivants.
"""
import io
import os
import re

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "socle_saisie.js")
CSS = os.path.join(RACINE, "static", "socle_saisie.css")
GABARIT = os.path.join(RACINE, "Code", "routes", "templates",
                       "socle_panneau.html")

_N = [0]


def _lire(p):
    return io.open(p, encoding="utf-8").read()


def _js_nu():
    """Le JS sans ses commentaires.

    ⚠️ À employer dans TOUT cliquet qui cherche une chaîne : le commentaire
    qui explique une règle la cite forcément, et le contrôle s'attrape alors
    sur sa propre explication. Ce piège a mordu DEUX fois dans ce seul
    fichier — une clé construite citée en commentaire, et le nom d'un
    observateur qu'on explique ne pas employer."""
    s = re.sub(r"/\*.*?\*/", "", _lire(JS), flags=re.S)
    return re.sub(r"^\s*//.*$", "", s, flags=re.M)


def _corps_js(js, ancre):
    """Le corps d'une fonction, borné sur sa propre accolade fermante.

    ⚠️ Jamais « jusqu'à la fonction suivante » : la DÉFINITION de ce qu'on
    cherche peut vivre entre les deux, et le cliquet lit alors son propre
    sujet. C'est ce qui lui a fait rater le défaut au premier essai."""
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
    raise AssertionError("accolade non refermee apres " + ancre)


def _sans_commentaires(css):
    """⚠️ Les commentaires d'abord : celui qui explique une règle la cite, et
    un cliquet qui cherche une chaîne s'attrape alors sur sa propre
    explication. Neuvième fois que ce piège se présente dans ce dépôt."""
    out, reste = [], css
    while "/*" in reste:
        avant, _, suite = reste.partition("/*")
        out.append(avant)
        _, _, reste = suite.partition("*/")
    out.append(reste)
    return "".join(out)


# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def carto(app):
    """Un coordinateur, un champion, un `user`, une carto COMMUNE en SAISIE."""
    from Code.models.models import Activities, Entity, Role, User, UserRole
    from Code.security import hash_password

    _N[0] += 1
    n = _N[0]
    with app.app_context():
        faire = lambda r, s: User(
            first_name=r.capitalize(), last_name="SQ%d" % n,
            email="%s%d@socleq.test" % (r, n), password=hash_password("x"),
            status=s)
        coord = faire("coord", "coordinateur")
        champ = faire("champ", "champion")
        simple = faire("simple", "user")
        db.session.add_all([coord, champ, simple])
        db.session.commit()

        ent = Entity(name="Saisie carto %d" % n, owner_id=coord.id,
                     is_shared=True, socle_etat="saisie")
        db.session.add(ent)
        db.session.commit()
        act = Activities(name="Saisie activité %d" % n, entity_id=ent.id,
                         is_result=False)
        db.session.add(act)
        db.session.commit()
        d = {"coord": coord.id, "champ": champ.id, "simple": simple.id,
             "ent": ent.id, "act": act.id, "n": n}
    yield d
    _ranger(app, d)


def _ranger(app, d):
    with app.app_context():
        from Code.models.models import (ActivityChangeRequest, Activities,
                                        Entity, Role, Task, Tool, User,
                                        UserRole, activity_roles, task_tools)
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
        roles = [r.id for r in Role.query.filter_by(entity_id=d["ent"])]
        if roles:
            UserRole.query.filter(UserRole.role_id.in_(roles)).delete(
                synchronize_session=False)
        Role.query.filter_by(entity_id=d["ent"]).delete()
        Activities.query.filter_by(entity_id=d["ent"]).delete()
        Entity.query.filter_by(id=d["ent"]).delete()
        User.query.filter(
            User.id.in_([d["coord"], d["champ"], d["simple"]])).delete(
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


def _poser(app, carto, etat, **champs):
    from Code.models.models import Entity
    with app.app_context():
        ent = db.session.get(Entity, carto["ent"])
        ent.socle_etat = etat
        for k, v in champs.items():
            setattr(ent, k, v)
        db.session.commit()


def _etat_en_base(app, carto):
    from Code.models.models import Entity
    with app.app_context():
        ent = db.session.get(Entity, carto["ent"])
        return (ent.socle_etat, ent.socle_retour, ent.socle_par_id)


def _completer(app, carto, activity_id=None):
    """Garant + tâche + outil : le palier est alors franchi."""
    from Code.models.models import Role, Task, Tool, activity_roles
    with app.app_context():
        r = Role(name="Garant SQ%d" % carto["n"], entity_id=carto["ent"])
        o = Tool(name="Outil SQ%d" % carto["n"], entity_id=carto["ent"])
        db.session.add_all([r, o])
        db.session.flush()
        db.session.execute(activity_roles.insert().values(
            activity_id=activity_id or carto["act"], role_id=r.id,
            status="Garant"))
        t = Task(name="Tâche SQ%d" % carto["n"],
                 activity_id=activity_id or carto["act"])
        t.tools.append(o)
        db.session.add(t)
        db.session.commit()


def _droit(app, carto, qui, fonction):
    from Code.carto_access import can_edit, can_fill, can_propose, can_review
    from Code.models.models import Entity, User
    table = {"fill": can_fill, "edit": can_edit, "propose": can_propose,
             "review": can_review}
    with app.test_request_context():
        from flask import session
        session["user_id"] = carto[qui]
        session["active_entity_id"] = carto["ent"]
        return bool(table[fonction](db.session.get(Entity, carto["ent"]),
                                    db.session.get(User, carto[qui])))


# ══════════════════════════════════════════════════════════════════════════
class TestLaSaisieEstDIRECTE:
    """⚠️⚠️ Le point qui fait tenir tout le reste. Sans lui le découlement ne
    démarre même pas : l'import Excel ne vise que les cartos où le compte a
    `can_edit` (`import_hub._cibles_possibles`), et `can_edit` rend faux pour
    un champion sur une carto commune — mesuré avant, la liste des cibles
    était VIDE."""

    def test_le_champion_ecrit_en_base_pendant_la_saisie(self, app, carto):
        from Code.models.models import Task
        c = _comme(app, carto["champ"], carto["ent"])
        r = c.post("/tasks/add", json={"activity_id": carto["act"],
                                       "name": "Écrite en direct"})
        assert r.status_code == 201, r.get_data(as_text=True)
        with app.app_context():
            assert Task.query.filter_by(activity_id=carto["act"]).count() == 1

    def test_et_RIEN_ne_part_au_brouillon(self, app, carto):
        """Un brouillon pendant la saisie serait une seconde pile : on écrit
        directement, il n'y a rien à accumuler."""
        c = _comme(app, carto["champ"], carto["ent"])
        c.post("/tasks/add", json={"activity_id": carto["act"], "name": "X"})
        j = c.get("/api/propositions/brouillon").get_json()
        assert j["n"] == 0 and j["brouillon"] is None

    def test_can_fill_suit_l_etat_du_socle(self, app, carto):
        assert _droit(app, carto, "champ", "fill") is True
        _poser(app, carto, "soumis")
        assert _droit(app, carto, "champ", "fill") is False, \
            "l'examen gèle la carto"
        _poser(app, carto, "valide")
        assert _droit(app, carto, "champ", "fill") is False, \
            "après validation, on propose"

    def test_le_DIAGRAMME_reste_au_coordinateur(self, app, carto):
        """⚠️⚠️ C'est pour cela que ce n'est PAS `can_edit` : celui-ci ouvre
        aussi `/cartography/api/save`, l'import Visio et le renommage de la
        carto. La carte vient du coordinateur, elle n'est pas à remplir."""
        assert _droit(app, carto, "champ", "fill") is True
        assert _droit(app, carto, "champ", "edit") is False
        assert _droit(app, carto, "champ", "propose") is True, \
            "le diagramme, lui, se propose toujours"

    def test_un_user_ordinaire_reste_en_LECTURE_SEULE(self, app, carto):
        """Ce régime ne change pas la grammaire du produit : `user` consulte
        et ne modifie rien."""
        assert _droit(app, carto, "simple", "fill") is False
        c = _comme(app, carto["simple"], carto["ent"])
        r = c.post("/tasks/add", json={"activity_id": carto["act"], "name": "N"})
        assert r.status_code == 403
        assert r.get_json()["code"] == "lecture_seule"

    def test_une_carto_PRIVEE_ne_connait_pas_ce_regime(self, app, carto):
        """Son propriétaire écrit de toute façon, et personne n'a rien à
        valider : le socle y dort."""
        from Code.models.models import Entity
        from Code.socle_activites import en_saisie
        with app.app_context():
            ent = db.session.get(Entity, carto["ent"])
            ent.is_shared = False
            db.session.commit()
            assert en_saisie(ent) is False
        assert _droit(app, carto, "champ", "fill") is False

    def test_l_import_excel_VISE_la_carto_en_saisie(self, app, carto):
        """⚠️ Le premier pas du découlement. Mesuré avant : `can_edit` rendait
        une liste de cibles VIDE pour un champion, donc « un champion remplit
        l'entité avec un import Excel » était impossible."""
        from Code.models.models import User
        from Code.routes.import_hub import _cibles_possibles
        with app.test_request_context():
            from flask import session
            session["user_id"] = carto["champ"]
            session["active_entity_id"] = carto["ent"]
            moi = db.session.get(User, carto["champ"])
            assert carto["ent"] in [e.id for e in _cibles_possibles(moi)]
        _poser(app, carto, "valide")
        with app.test_request_context():
            from flask import session
            session["user_id"] = carto["champ"]
            session["active_entity_id"] = carto["ent"]
            moi = db.session.get(User, carto["champ"])
            assert carto["ent"] not in [e.id for e in _cibles_possibles(moi)]


# ══════════════════════════════════════════════════════════════════════════
class TestLaPorteDitLEQUEL_DES_TROIS:
    """Trois régimes, trois réponses, et chacune dit QUOI FAIRE. Dire
    « lecture seule » à un champion qui remplissait la carto cinq minutes
    plus tôt l'enverrait chercher un droit qu'il a."""

    def test_saisie_201(self, app, carto):
        c = _comme(app, carto["champ"], carto["ent"])
        assert c.post("/tasks/add", json={"activity_id": carto["act"],
                                          "name": "A"}).status_code == 201

    def test_examen_409_avec_son_propre_motif(self, app, carto):
        _poser(app, carto, "soumis")
        c = _comme(app, carto["champ"], carto["ent"])
        r = c.post("/tasks/add", json={"activity_id": carto["act"], "name": "B"})
        assert r.status_code == 409
        assert r.get_json()["code"] == "socle_en_examen"

    def test_valide_202_proposition(self, app, carto):
        _poser(app, carto, "valide")
        c = _comme(app, carto["champ"], carto["ent"])
        r = c.post("/tasks/add", json={"activity_id": carto["act"], "name": "C"})
        assert r.status_code == 202
        assert r.get_json()["code"] == "proposition"

    def test_le_coordinateur_ecrit_dans_les_TROIS(self, app, carto):
        """⚠️ `_peut_ecrire` passe AVANT le refus d'examen : un coordinateur
        qui corrige pendant qu'il examine n'est pas gêné par sa propre file."""
        for etat in ("saisie", "soumis", "valide"):
            _poser(app, carto, etat)
            c = _comme(app, carto["coord"], carto["ent"])
            r = c.post("/tasks/add", json={"activity_id": carto["act"],
                                           "name": "Coord %s" % etat})
            assert r.status_code == 201, (etat, r.get_data(as_text=True))

    def test_le_motif_de_l_examen_est_une_CLE_dans_les_deux_langues(self):
        """⚠️ Le texte part tel quel dans la réponse, et plusieurs écrans
        l'affichent sans le relire — écrit en dur, il montrerait du français
        au milieu d'une interface anglaise."""
        from Code.ecriture import MOTIF
        from Code.translations import TRANSLATIONS
        cle, statut = MOTIF["socle_en_examen"]
        assert statut == 409
        for lg in ("fr", "en"):
            v = TRANSLATIONS[lg].get(cle)
            assert v and v.strip(), (lg, cle)
        assert TRANSLATIONS["fr"][cle] != TRANSLATIONS["en"][cle]


# ══════════════════════════════════════════════════════════════════════════
class TestLesTroisTransitions:

    def test_soumettre_exige_le_PALIER(self, app, carto):
        c = _comme(app, carto["champ"], carto["ent"])
        r = c.post("/api/propositions/socle/soumettre", json={"message": "fini"})
        assert r.status_code == 409 and r.get_json()["code"] == "palier"
        assert _etat_en_base(app, carto)[0] == "saisie"

    def test_soumettre_une_fois_COMPLET(self, app, carto):
        _completer(app, carto)
        c = _comme(app, carto["champ"], carto["ent"])
        r = c.post("/api/propositions/socle/soumettre", json={"message": "voilà"})
        assert r.status_code == 201, r.get_data(as_text=True)
        etat, _, par = _etat_en_base(app, carto)
        assert etat == "soumis" and par == carto["champ"]

    def test_un_user_ne_SOUMET_pas(self, app, carto):
        """Celui qui REMPLIT soumet : un compte qui n'a pas écrit une ligne
        n'a pas à déclarer le travail d'un autre terminé."""
        _completer(app, carto)
        c = _comme(app, carto["simple"], carto["ent"])
        r = c.post("/api/propositions/socle/soumettre", json={})
        assert r.status_code == 403 and r.get_json()["code"] == "forbidden"

    def test_valider_est_RESERVE_au_coordinateur(self, app, carto):
        _completer(app, carto)
        _poser(app, carto, "soumis")
        c = _comme(app, carto["champ"], carto["ent"])
        assert c.post("/api/propositions/socle/valider",
                      json={}).status_code == 403
        assert _etat_en_base(app, carto)[0] == "soumis"

    def test_valider_exige_aussi_le_palier(self, app, carto):
        """Ce qui devient officiel doit être complet — y compris quand le
        coordinateur valide sa propre carto sans passer par une soumission."""
        c = _comme(app, carto["coord"], carto["ent"])
        r = c.post("/api/propositions/socle/valider", json={})
        assert r.status_code == 409 and r.get_json()["code"] == "palier"

    def test_le_coordinateur_valide_DIRECTEMENT_depuis_la_saisie(self, app, carto):
        """⚠️ Voulu : il n'a personne à qui soumettre, et attendre une
        soumission qui ne viendra jamais le laisserait coincé en saisie."""
        _completer(app, carto)
        c = _comme(app, carto["coord"], carto["ent"])
        assert c.post("/api/propositions/socle/valider",
                      json={}).status_code == 200
        assert _etat_en_base(app, carto)[0] == "valide"

    def test_renvoyer_EXIGE_un_mot(self, app, carto):
        """⚠️ Sans lui, le champion ne sait pas ce qu'il doit reprendre : le
        mot est ce qui rend le renvoi utile."""
        _completer(app, carto)
        _poser(app, carto, "soumis")
        c = _comme(app, carto["coord"], carto["ent"])
        r = c.post("/api/propositions/socle/renvoyer", json={"commentaire": "  "})
        assert r.status_code == 409 and r.get_json()["code"] == "sans_mot"
        assert _etat_en_base(app, carto)[0] == "soumis"

    def test_renvoyer_rend_la_main_AVEC_le_mot(self, app, carto):
        _completer(app, carto)
        _poser(app, carto, "soumis")
        c = _comme(app, carto["coord"], carto["ent"])
        assert c.post("/api/propositions/socle/renvoyer",
                      json={"commentaire": "Il manque les outils."}
                      ).status_code == 200
        etat, retour, _ = _etat_en_base(app, carto)
        assert etat == "saisie" and retour == "Il manque les outils."

    def test_renvoyer_ne_part_que_de_SOUMIS(self, app, carto):
        c = _comme(app, carto["coord"], carto["ent"])
        r = c.post("/api/propositions/socle/renvoyer", json={"commentaire": "x"})
        assert r.status_code == 409 and r.get_json()["code"] == "pas_soumis"

    def test_resoumettre_efface_le_retour_precedent(self, app, carto):
        """Le mot du coordinateur portait sur un état qu'on vient de
        corriger."""
        _completer(app, carto)
        _poser(app, carto, "saisie", socle_retour="à reprendre")
        c = _comme(app, carto["champ"], carto["ent"])
        assert c.post("/api/propositions/socle/soumettre",
                      json={}).status_code == 201
        assert _etat_en_base(app, carto)[1] is None

    def test_une_carto_PRIVEE_ne_se_soumet_pas(self, app, carto):
        from Code.models.models import Entity
        _completer(app, carto)
        with app.app_context():
            db.session.get(Entity, carto["ent"]).is_shared = False
            db.session.commit()
        c = _comme(app, carto["coord"], carto["ent"])
        r = c.post("/api/propositions/socle/soumettre", json={})
        assert r.status_code in (403, 409)
        assert _etat_en_base(app, carto)[0] == "saisie"

    def test_sans_connexion_401(self, app, carto):
        c = app.test_client()
        for chemin in ("soumettre", "valider", "renvoyer"):
            assert c.post("/api/propositions/socle/" + chemin,
                          json={}).status_code == 401


# ══════════════════════════════════════════════════════════════════════════
class TestLaBasculeDeRegime:
    """Le but de tout l'édifice : une fois validé, une modification = une
    demande."""

    def test_avant_on_ECRIT_apres_on_PROPOSE(self, app, carto):
        from Code.models.models import Task
        _completer(app, carto)
        c = _comme(app, carto["champ"], carto["ent"])
        assert c.post("/tasks/add", json={"activity_id": carto["act"],
                                          "name": "Avant"}).status_code == 201

        _comme(app, carto["coord"], carto["ent"]).post(
            "/api/propositions/socle/valider", json={})

        r = c.post("/tasks/add", json={"activity_id": carto["act"],
                                       "name": "Après"})
        assert r.status_code == 202 and r.get_json()["code"] == "proposition"
        with app.app_context():
            noms = {t.name for t in Task.query.filter_by(
                activity_id=carto["act"])}
        assert "Avant" in noms and "Après" not in noms

    def test_le_panneau_s_EFFACE_une_fois_valide(self, app, carto):
        from Code.models.models import Entity, User
        from Code.socle_activites import etat
        _poser(app, carto, "valide")
        with app.test_request_context():
            from flask import session
            session["user_id"] = carto["champ"]
            session["active_entity_id"] = carto["ent"]
            e = etat(db.session.get(Entity, carto["ent"]),
                     db.session.get(User, carto["champ"]))
        assert e["actif"] is False
        # ⚠️ Et le palier n'est PAS calculé : quatre requêtes qu'on ne paie
        # pas pour un panneau qui ne s'affiche pas.
        assert e["palier"] is None

    def test_les_DEUX_ecrans_ne_cohabitent_jamais(self, app, carto):
        """⚠️ Vu au banc en basculant l'état à la main : le bandeau « vos
        modifications partent à l'examen » s'affichait à côté du panneau du
        socle, annonçant une SECONDE file là où il n'y en a qu'une."""
        c = _comme(app, carto["champ"], carto["ent"])
        for etat, panneau, bandeau in (("saisie", True, False),
                                       ("soumis", True, False),
                                       ("valide", False, True)):
            _poser(app, carto, etat)
            page = c.get("/activities/view").get_data(as_text=True)
            assert ('id="scl"' in page) is panneau, (etat, "panneau")
            assert ('id="acp-bandeau"' in page) is bandeau, (etat, "bandeau")


# ══════════════════════════════════════════════════════════════════════════
class TestLaReprise:
    """⚠️⚠️ Sans elle, cette livraison ouvrirait l'écriture DIRECTE à tout
    champion sur des données DÉJÀ officielles : le défaut de la colonne est
    'saisie', et toutes les lignes existantes l'héritent. C'est un recul du
    contrôle d'accès, pas une nouveauté."""

    def test_elle_passe_les_cartos_existantes_a_valide(self, app, carto):
        from Code.socle_activites import reprendre_cartos_existantes
        with app.app_context():
            reprendre_cartos_existantes(force=True)
        assert _etat_en_base(app, carto)[0] == "valide"

    def test_et_elle_ne_se_joue_QU_UNE_FOIS(self, app, carto):
        """⚠️ Rejouée à chaque démarrage, elle validerait le socle de chaque
        carto qu'on est en train de remplir : on ouvrirait la saisie le matin
        et le redéploiement du soir la refermerait. C'est exactement le défaut
        de `migrer_anciens_champions`, qui promouvait tout champion nommé
        APRÈS la reprise."""
        from Code.models.models import AppSetting
        from Code.socle_activites import CLE_REPRISE, reprendre_cartos_existantes
        with app.app_context():
            # Le marqueur est posé au démarrage de l'application de test.
            assert db.session.get(AppSetting, CLE_REPRISE) is not None
            assert reprendre_cartos_existantes() == 0
        assert _etat_en_base(app, carto)[0] == "saisie", \
            "une carto NEUVE ne doit pas être validée par la reprise"

    def test_le_marqueur_vit_en_BASE(self):
        """⚠️ Pas en mémoire : une instance qui redémarre, se duplique ou se
        redéploie doit lire la même réponse."""
        from Code.models.models import AppSetting
        from Code.socle_activites import CLE_REPRISE
        assert isinstance(CLE_REPRISE, str) and CLE_REPRISE
        assert hasattr(AppSetting, "key")


# ══════════════════════════════════════════════════════════════════════════
class TestLePalierSeMesureEnBase:

    def test_une_carto_SANS_activite_n_est_pas_complete(self, app, carto):
        """Sans ce cas, une carto vide passerait le palier et le coordinateur
        validerait du néant."""
        from Code.models.models import Activities, Entity
        from Code.socle_activites import palier
        with app.app_context():
            Activities.query.filter_by(entity_id=carto["ent"]).delete()
            db.session.commit()
            p = palier(db.session.get(Entity, carto["ent"]))
        assert p["total"] == 0 and p["complet"] is False

    def test_lire_le_socle_n_ecrit_AUCUNE_ligne(self, app, carto):
        """⚠️ Le palier a longtemps SIMULÉ le brouillon — il rejouait les
        vraies routes puis annulait. Il lit désormais la base, et une lecture
        qui écrirait serait une écriture que personne n'a demandée."""
        from Code.models.models import Activities, Entity, Task
        from Code.socle_activites import palier
        with app.app_context():
            avant = (Task.query.count(), Activities.query.count())
            ent = db.session.get(Entity, carto["ent"])
            palier(ent)
            palier(ent)
            assert (Task.query.count(), Activities.query.count()) == avant

    def test_le_cout_ne_grandit_PAS_avec_la_carto(self, app, carto):
        """⚠️ Le panneau est rendu à chaque ouverture de la page Activités :
        un coût qui suit le nombre d'activités serait payé à chaque visite."""
        from sqlalchemy import event
        from Code.models.models import Activities, Entity
        from Code.socle_activites import palier

        def compter():
            n = [0]

            def vu(*a, **k):
                n[0] += 1
            with app.app_context():
                ent = db.session.get(Entity, carto["ent"])
                event.listen(db.engine, "before_cursor_execute", vu)
                try:
                    palier(ent)
                finally:
                    event.remove(db.engine, "before_cursor_execute", vu)
            return n[0]

        avant = compter()
        with app.app_context():
            for i in range(25):
                db.session.add(Activities(name="SQ charge %d-%d" % (carto["n"], i),
                                          entity_id=carto["ent"], is_result=False))
            db.session.commit()
        assert compter() == avant, "le nombre de requêtes suit la carto"
        assert avant <= 4, avant


# ══════════════════════════════════════════════════════════════════════════
class TestSupprimerUnCompteQuiASoumis:
    """⚠️ `socle_par_id` est une clé étrangère vers `users` : PostgreSQL les
    applique quand SQLite les ignore. Oubliée dans `delete_user`, la
    suppression d'un compte tomberait en 500 **en production seulement** —
    c'est la famille de `password_resets.user_id`, qui a choisi l'autre bord
    (pas de FK du tout) pour exactement cette raison."""

    def test_la_route_DETACHE_la_reference(self, app, carto):
        """⚠️ Éprouvé en APPELANT la route, pas en relisant son source : un
        cliquet qui lit un `.py` rougit dans l'arbre d'image, compilé en
        bytecode. Huitième fois que ce piège se présente — et celui-ci a été
        écrit le jour même où la leçon était recopiée."""
        from Code.models.models import User
        from Code.security import hash_password
        _completer(app, carto)
        _comme(app, carto["champ"], carto["ent"]).post(
            "/api/propositions/socle/soumettre", json={})
        assert _etat_en_base(app, carto)[2] == carto["champ"]

        with app.app_context():
            adm = User(first_name="Adm", last_name="SQ%d" % carto["n"],
                       email="adm%d@socleq.test" % carto["n"],
                       password=hash_password("x"), status="admin")
            db.session.add(adm)
            db.session.commit()
            aid = adm.id
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = aid
        r = c.post("/comptes/delete/%d" % carto["champ"])
        assert r.status_code in (200, 302), r.status_code
        assert _etat_en_base(app, carto)[2] is None, \
            "la référence doit être détachée, pas laissée pendante"
        with app.app_context():
            assert db.session.get(User, carto["champ"]) is None
            User.query.filter_by(id=aid).delete()
            db.session.commit()


# ══════════════════════════════════════════════════════════════════════════
class TestLePanneau:

    CLES = ["sur", "etiq_saisie", "etiq_soumis", "i_titre", "i_texte",
            "sur_total", "pretes_1", "pretes_n", "x_garant", "x_tache",
            "x_outil", "pret", "vide", "voir_1", "voir_n", "cacher",
            "et_autres", "c_garant", "c_tache", "c_outil", "soumettre",
            "mot_ph", "confirmer", "annuler", "valider", "renvoyer",
            "retour_ph", "err_mot", "err", "introuvable", "rail", "a_valider",
            "soumis_par", "attente", "attente_d", "coord_attend", "renvoye"]

    @pytest.mark.parametrize("cle", CLES)
    def test_chaque_cle_existe_dans_les_DEUX_langues(self, cle):
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            v = TRANSLATIONS[lg].get("socle." + cle)
            assert v and str(v).strip(), (lg, cle)

    def test_chaque_cle_lue_par_le_JS_est_INJECTEE(self):
        """⚠️ `T()` rend la CLÉ quand elle manque, sans rien lever : une clé
        oubliée s'afficherait telle quelle à l'écran."""
        js = _js_nu()
        gab = _lire(GABARIT)
        lues = set(re.findall(r"T\('([a-z0-9_]+)'\)", js))
        lues |= set(re.findall(r"F\('([a-z0-9_]+)'", js))
        # ⚠️ `nf()` reçoit la BASE d'une paire singulier/pluriel.
        for base in re.findall(r"nf\('([a-z0-9_]+)'", js):
            lues |= {base + "_1", base + "_n"}
        # ⚠️ Les libellés de famille passent par une TABLE, jamais par une
        # clé construite : `T('x_' + code)` serait relevé par `test_78` comme
        # la clé « x_ ». On les lit donc dans la table — sans quoi une
        # injection oubliée passerait inaperçue, ce qui était le cas des
        # pastilles avant cette passe.
        for nom in ("CHIP", "LIB"):
            for bloc in re.findall(r"var " + nom + r" = \{([^}]*)\}", js):
                lues |= set(re.findall(r"'([a-z0-9_]+)'", bloc))
        assert len(lues) >= 20, lues
        absentes = [c for c in sorted(lues) if (c + ":") not in gab]
        assert not absentes, absentes

    def test_aucune_cle_n_est_CONSTRUITE_dans_le_gabarit(self):
        """⚠️ `t('socle.c_' + code)` est relevé par `test_78` comme la clé
        « socle.c_ », et le jour où une exigence s'ajoute sa pastille
        s'afficherait en clair. Les trois sont écrites en toutes lettres."""
        gab = _lire(GABARIT)
        assert "t('socle.c_' +" not in gab and 't("socle.c_" +' not in gab
        for c in ("c_garant", "c_tache", "c_outil"):
            assert "socle." + c in gab, c

    def test_le_pluriel_suit_la_LANGUE(self):
        """⚠️ Le singulier ne couvre pas les mêmes nombres d'une langue à
        l'autre : « 0 activité » en français, « 0 activities » en anglais."""
        js = _lire(JS)
        assert "L.lang === 'en'" in js and "(n === 1)" in js and "(n < 2)" in js

    def test_le_mot_du_champion_se_cite_avec_un_Q(self):
        """⚠️ « » est une convention FRANÇAISE, et le navigateur pose les
        guillemets de la langue du document. Relevé à l'écran : le message
        sortait avec ses chevrons au milieu d'une phrase anglaise."""
        js = _sans_commentaires(_lire(JS).replace("/*", "/*").replace("*/", "*/"))
        corps = re.sub(r"/\*.*?\*/", "", _lire(JS), flags=re.S)
        corps = re.sub(r"^\s*//.*$", "", corps, flags=re.M)
        assert "<q>" in corps
        assert "«" not in corps and "»" not in corps

    def test_la_carte_du_i_DIVISE_par_le_zoom_du_corps(self):
        """⚠️ `getBoundingClientRect()` rend DÉJÀ des pixels d'écran — le zoom
        du corps y est appliqué. Seules les coordonnées qu'on ÉCRIT repassent
        par lui. Septième fois que ce piège se présente dans l'application."""
        corps = re.sub(r"/\*.*?\*/", "", _lire(JS), flags=re.S)
        i = corps.index("function ouvrirInfo(")
        bloc = corps[i:corps.index("function majVisibiliteRail", i)]
        assert "zoomCorps()" in bloc
        assert "/ z" in bloc, "les coordonnées écrites se divisent par le zoom"

    def test_le_rail_ne_s_appuie_PAS_sur_un_observateur(self):
        """⚠️ Ni `IntersectionObserver` ni `requestAnimationFrame` ne tirent
        dans le volet de mise au point : un observateur neuf n'y rend rien,
        pas même l'appel initial que la spécification garantit. Un calcul au
        défilement se rejoue, lui, à la main.

        ⚠️ Commentaires retirés d'abord : celui qui explique la règle la
        cite, et ce cliquet s'est pris dessus au premier essai. Dixième
        occurrence de ce piège dans ce dépôt."""
        js = re.sub(r"/\*.*?\*/", "", _lire(JS), flags=re.S)
        js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
        assert "IntersectionObserver" not in js
        assert "window.__sclRail" in js, "exposé pour le banc"

    def test_chaque_classe_qui_pose_un_display_declare_son_hidden(self):
        """⚠️ `[hidden]` est une règle du NAVIGATEUR : une classe d'auteur qui
        pose un `display` l'emporte. Septième fois que ce piège mord ici."""
        css = _sans_commentaires(_lire(CSS))
        for cls in (".scl-liste", ".scl-rail", ".scl-voir"):
            assert cls + "[hidden]" in css, cls

    def test_aucune_regle_ne_lit_l_accent_doux_de_la_RACINE(self):
        """⚠️ Les quatre dérivés se redéclarent désormais sur les sélecteurs
        de page — mais ce panneau porte sa propre famille (l'ambre de la
        gouvernance), pas l'accent de la page Activités."""
        css = _sans_commentaires(_lire(CSS))
        for jeton in ("--pg-accent-soft", "--pg-accent-softer",
                      "--pg-accent-border", "--pg-accent-glow"):
            assert jeton not in css, jeton

    def test_la_liste_de_travail_se_rend_DANS_LE_JS(self):
        """⚠️⚠️ Le défaut relevé à l'usage : « l'écran n'indique pas ce qu'il
        manque est où ». La liste était rendue par le GABARIT, et `relire()`
        met à jour les chiffres après chaque écriture sans toucher au HTML du
        serveur : elle restait dans l'état du chargement de page. Le bouton
        annonçait « Masquer » au-dessus de RIEN.

        Une seule implantation, donc, et c'est le JS — les données arrivent
        par `SOCLE_ETAT`, donc sans aller-retour au premier rendu."""
        gab = _lire(GABARIT)
        i = gab.index('id="scl-liste"')
        j = gab.index("</div>", i)
        assert "{% for" not in gab[i:j], \
            "le gabarit ne doit plus rendre la liste"
        js = _js_nu()
        assert "function rendreListe(" in js
        assert "data-scl-act=" in js, "chaque nom doit OUVRIR son activité"

    def test_et_elle_suit_les_CHIFFRES(self):
        """Sans cet appel, la liste se fige au chargement : c'est exactement
        le défaut. Les deux se mettent à jour ensemble ou pas du tout."""
        corps = _corps_js(_js_nu(), "function majValeurs(")
        assert "rendreListe()" in corps, \
            "majValeurs doit re-rendre la liste"

    def test_la_barre_DROITE_est_devenue_un_COMPTEUR(self):
        """⚠️ « j'imaginais un truc un peu plus sympa avec une courbe pas
        juste droite mais en mode arrondie (compteur de vitesse) ». Et le
        reproche portait juste : une barre droite dit « 80 % », pas
        « 8 sur 10 » — il fallait aller lire le chiffre à côté."""
        css = _sans_commentaires(_lire(CSS))
        assert ".scl-barre" not in css
        assert "scl-barre" not in _lire(GABARIT)
        js = _js_nu()
        assert "function rendreJauge(" in js
        # Un ARC, pas une barre pliée : 240° du bas-gauche au bas-droit.
        assert "DEB = -120" in js and "SWEEP = 240" in js
        assert "' A '" in js, "le tracé doit être un arc SVG"

    def test_le_compteur_est_dessine_pour_le_ZOOM_du_corps(self):
        """⚠️ `body:has(.pg-root)` porte `zoom: .8` (ui-theme) : la maquette,
        écrite dans une page SANS ce zoom, arriverait 20 % plus petite.
        218 × 0,8 = 174, la taille éprouvée à l'écran."""
        t = int(re.search(r"TAILLE = (\d+)", _js_nu()).group(1))
        assert round(t * 0.8) == 174, t

    def test_la_hauteur_du_compteur_est_RESERVEE(self):
        """Le cadran se dessine dans le JS : sans hauteur réservée, le
        panneau sauterait entre le rendu du serveur et celui du script.

        ⚠️ Et la réserve suit la PROPORTION : changée d'un côté sans
        l'autre, elle ne réserverait plus la bonne place."""
        css = _sans_commentaires(_lire(CSS))
        i = css.index(".scl-jauge {")
        bloc = css[i:css.index("}", i)]
        js = _js_nu()
        t = int(re.search(r"TAILLE = (\d+)", js).group(1))
        h = int(re.search(r"min-height:\s*(\d+)px", bloc).group(1))
        prop = float(re.search(r"H = TAILLE \* ([0-9.]+)", js).group(1))
        assert abs(h - t * prop) <= 1, (h, t * prop)

    def test_la_lecture_passe_SOUS_le_moyeu_et_tient_dans_sa_boite(self):
        """⚠️ Les proportions sont MESURÉES, pas choisies au jugé : la
        lecture posée par-dessus en absolu retombait sur le moyeu de
        l'aiguille, qui occupe le centre. On rejoue ici la géométrie du SVG
        — c'est le seul contrôle qui porte sur ce qu'on publie, le volet de
        mise au point ne rendant pas la page.

        ⚠️ Les proportions sont LUES dans le JS, jamais recopiées : un
        cliquet qui porte sa propre copie de la formule ne garde rien."""
        import math
        js = _js_nu()
        t = int(re.search(r"TAILLE = (\d+)", js).group(1))
        k = t / 174.0
        C = t / 2.0
        R = t * float(re.search(r"R = TAILLE \* ([0-9.]+)", js).group(1))
        EP = t * float(re.search(r"EP = TAILLE \* ([0-9.]+)", js).group(1))
        H = t * float(re.search(r"H = TAILLE \* ([0-9.]+)", js).group(1))
        prop = [float(x) for x in re.findall(r"\(TAILLE \* ([0-9.]+)\)", js)]
        assert len(prop) == 4, prop
        n_y, n_t, d_y, d_t = prop

        def pt(r, deg):
            a = math.radians(deg - 90)
            return C + r * math.cos(a), C + r * math.sin(a)

        deb = float(re.search(r"DEB = (-?\d+)", js).group(1))
        bal = float(re.search(r"SWEEP = (\d+)", js).group(1))
        bas = max(pt(R, deb)[1], pt(R, deb + bal)[1]) + EP / 2
        haut = pt(R, 0)[1] - EP / 2
        gauche = pt(R, deb)[0] - EP / 2
        droite = pt(R, deb + bal)[0] + EP / 2
        assert haut >= 0 and bas <= H, ("l'arc sort de sa boîte", haut, bas, H)
        assert gauche >= 0 and droite <= t, (gauche, droite, t)
        # Le chiffre : sa hauteur de capitale passe SOUS le moyeu.
        capitale = t * n_y - t * n_t * 0.72
        assert capitale > C + 6.5 * k, ("le chiffre touche le moyeu", capitale)
        # La légende tient dans la boîte, jambage compris, et sous le chiffre.
        assert t * d_y + t * d_t * 0.25 <= H, "la légende sort par le bas"
        assert t * n_y < t * d_y - t * d_t * 0.8, "le chiffre touche la légende"

    def test_l_aiguille_n_entre_PAS_dans_le_chiffre(self):
        """⚠⚠ Un balayage de 240° fait pointer l'aiguille vers le BAS à ses
        deux extrêmes : elle y atteint C + r/2, c'est-à-dire la zone où vit
        la lecture. Mesuré à 36/36 avant correctif : dix pixels de
        recouvrement sur le coin haut-droit des chiffres, et comme le texte
        est peint par-dessus, la pointe paraissait s'arrêter dans le « 6 ».

        ⚠️ La maquette portait le même défaut et il n'a PAS été vu à l'œil :
        c'est la mesure qui le trouve. D'où ce cliquet."""
        import math
        js = _js_nu()
        t = int(re.search(r"TAILLE = (\d+)", js).group(1))
        k = t / 174.0
        C = t / 2.0
        R = t * float(re.search(r"R = TAILLE \* ([0-9.]+)", js).group(1))
        EP = t * float(re.search(r"EP = TAILLE \* ([0-9.]+)", js).group(1))
        lg = float(re.search(r"R - EP - ([0-9.]+) \* k", js).group(1))
        deb = float(re.search(r"DEB = (-?\d+)", js).group(1))
        bal = float(re.search(r"SWEEP = (\d+)", js).group(1))
        prop = [float(x) for x in re.findall(r"\(TAILLE \* ([0-9.]+)\)", js)]
        n_y, n_t = prop[0], prop[1]

        def y(r, deg):
            return C + r * math.sin(math.radians(deg - 90))

        r_aig = R - EP - lg * k
        bas = max(y(r_aig, deb), y(r_aig, deb + bal))
        capitale = t * n_y - t * n_t * 0.72
        assert capitale > bas + 4, \
            ("l'aiguille entre dans le chiffre", bas, capitale)

    def test_les_graduations_sont_PLAFONNEES(self):
        """Une carto du pilote porte six cents activités : six cents traits
        sur un arc de 354 px se lisent comme une hachure, pas comme une
        échelle. L'arc seul suffit alors."""
        js = _js_nu()
        assert "GRADS_MAX" in _corps_js(js, "function rendreJauge(")
        n = int(re.search(r"GRADS_MAX = (\d+)", js).group(1))
        assert 10 <= n <= 60, n

    def test_les_trois_exigences_montrent_ce_qui_est_ACQUIS(self):
        """⚠️ `manque[code]` compte les activités qui en MANQUENT. Une barre
        remplie avec ce nombre se VIDERAIT à mesure qu'on avance."""
        corps = _corps_js(_js_nu(), "function rendreExigences(")
        assert re.search(r"total\s*-\s*\(\(p\.manque", corps), corps

    def test_les_trois_libelles_ne_sont_pas_CONSTRUITS(self):
        """⚠️ `T('x_' + code)` est relevé par `test_78` comme la clé
        « x_ », et le jour où une exigence s'ajoute son libellé s'afficherait
        en clair."""
        js = _js_nu()
        assert "T('x_' +" not in js and 'T("x_" +' not in js
        for c in ("x_garant", "x_tache", "x_outil"):
            assert "'" + c + "'" in js, c

    def test_le_compteur_et_les_exigences_suivent_les_CHIFFRES(self):
        """Même règle que la liste : rendus ailleurs, ils se figeraient à
        l'état du chargement de page."""
        corps = _corps_js(_js_nu(), "function majValeurs(")
        for appel in ("rendreJauge()", "rendreExigences()"):
            assert appel in corps, appel

    def test_le_cadran_porte_son_etiquette_pour_un_LECTEUR_d_ecran(self):
        """`role="img"` masque le texte interne du SVG : sans `aria-label`,
        le compteur ne dit plus rien à un lecteur d'écran."""
        corps = _corps_js(_js_nu(), "function rendreJauge(")
        assert 'role="img"' in corps and "aria-label" in corps
        assert "nf('pretes'" in corps, "l'étiquette porte les DEUX nombres"
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            v = TRANSLATIONS[lg]["socle.pretes_n"]
            assert "[[n]]" in v and "[[t]]" in v, (lg, v)

    def test_les_deux_cas_de_bord_vivent_dans_la_zone_de_la_LISTE(self):
        """Carto vide, ou plus rien à compléter : la zone de la liste est le
        seul endroit de ce panneau qui parle des activités. Et elle ne doit
        pas se replier quand elle porte l'une des deux phrases."""
        corps = _corps_js(_js_nu(), "function rendreListe(")
        assert "T('vide')" in corps and "T('pret')" in corps
        assert "liste.hidden = false" in _corps_js(_js_nu(),
                                                   "function majValeurs(")
        assert ".scl-l-dit" in _sans_commentaires(_lire(CSS))

    def test_la_liste_s_ouvre_d_elle_meme_quand_il_reste_PEU(self):
        """C'est le moment où l'on chasse les dernières activités — et c'est
        précisément ce qu'on reprochait à l'écran. Au-delà elle reste pliée :
        vingt-huit lignes enterreraient les fiches qu'elles désignent.

        ⚠️ Posé UNE fois, à l'init : dans `majValeurs`, chaque écriture
        rouvrirait ce que l'on vient de replier."""
        js = _js_nu()
        assert "OUVRE_SI" in js, "la liste ne s'ouvre plus d'elle-même"
        n = int(re.search(r"OUVRE_SI = (\d+)", js).group(1))
        assert 2 <= n <= 12, n
        assert "OUVRE_SI" not in _corps_js(js, "function majValeurs(")

    def test_le_compte_du_bouton_vit_DANS_sa_cle(self):
        """⚠️ « Voir » + un nombre + « activités à compléter » découperait
        une phrase en trois, et l'ordre des mots n'est pas le même d'une
        langue à l'autre."""
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            assert "[[n]]" in TRANSLATIONS[lg]["socle.voir_n"]
            assert "[[n]]" not in TRANSLATIONS[lg]["socle.voir_1"]
        assert "nf('voir'" in _js_nu()

    def test_le_panneau_n_est_rendu_QUE_s_il_est_actif(self):
        """Une carto privée, ou un socle validé, ne paie pas les quatre
        requêtes du palier — et n'affiche rien."""
        gab = _lire(GABARIT)
        assert "{% if socle and socle.actif %}" in gab

    def test_la_borne_etroite_s_ecrit_en_px_REELS(self):
        """⚠️ `body.pg` porte `zoom: .8` et les requêtes média IGNORENT ce
        zoom : un seuil écrit en px de mise en page se déclencherait trop
        tard."""
        css = _lire(CSS)
        assert "px RÉELS" in css or "px REELS" in css
        assert "@media (max-width: 860px)" in css
