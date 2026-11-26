# -*- coding: utf-8 -*-
"""LE BROUILLON SE VOIT, ET IL S'OUTILLE — plus de saisie à l'aveugle.

« On crée une tâche dans une activité, une fois créée elle ne s'affiche pas
dedans mais se rajoute à la proposition… on ne peut donc pas consulter ce que
l'on a fait qu'à partir du truc en haut de page, si on a 150 activités cela
va être trop chiant. De plus, comment j'associe un outil à une tâche si elle
n'apparaît pas dans l'interface car est à l'état de proposition ? »

Deux défauts, et le second était BLOQUANT :

1. ce qu'un champion écrit part dans son brouillon et n'atteint jamais la
   base — la fiche restait donc muette ;
2. **le palier du 22/11 était infranchissable** sur toute activité vierge :
   il exige un outil par activité, un outil se rattache à une TÂCHE, et la
   tâche en attente n'a aucun identifiant à viser.

D'où les références locales (`b:0` = « ce que crée le geste 0 »), résolues au
rejeu par ce qu'il vient réellement d'écrire — jamais par l'identifiant d'une
simulation, qui est annulée aussitôt.

Ce fichier couvre aussi les trois autres points du même retour : le 403 qui
faisait revenir la fenêtre de bienvenue à chaque page, le chatbot refusé en
français sur un écran anglais, et les formulaires de la page Temps qui
présélectionnaient la première activité venue.

⚠️ Ce fichier se donne SA PROPRE carto, avec un `owner_id` : une entité de
test sans propriétaire est lisible par TOUT LE MONDE et devient le repli des
fichiers suivants.
"""
import io
import os
import re

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_ACP = os.path.join(RACINE, "static", "js", "activite_propositions.js")
CSS_ACP = os.path.join(RACINE, "static", "activite_propositions.css")
JS_CHAT = os.path.join(RACINE, "static", "js", "chatbot.js")
CSS_CHAT = os.path.join(RACINE, "static", "chatbot.css")
JS_TIME = os.path.join(RACINE, "static", "js", "time.js")
JS_COMP = os.path.join(RACINE, "static", "js", "competences_v2.js")
CSS_COMP = os.path.join(RACINE, "static", "competences.css")
GAB = os.path.join(RACINE, "Code", "routes", "templates")

_N = [0]


def _lire(p):
    return io.open(p, encoding="utf-8").read()


def _sans_commentaires_css(css):
    """⚠️ Sixième occurrence du piège : un cliquet qui cherche une chaîne doit
    retirer les commentaires d'abord, sinon il s'attrape sur l'explication
    qu'on vient d'écrire au-dessus de la règle."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _sans_commentaires_js(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", js)


def _bloc_media(css, entete, marqueur):
    """Le corps de l'at-règle `entete` QUI PORTE `marqueur`.

    ⚠️ `@media (max-width: 1100px)` ouvre CINQ blocs dans `competences.css` :
    chercher « le premier », ou « le premier après telle position », fait lire
    un bloc qui ne parle pas du sujet. Mesuré — un cas est tombé là-dessus."""
    for part in css.split(entete)[1:]:
        corps = part.split("\n}", 1)[0]
        if marqueur in corps:
            return corps
    raise AssertionError(entete + " ne porte nulle part " + marqueur)


def _corps(js, ancre):
    """Le corps d'une fonction, borné sur sa propre accolade fermante.

    ⚠️ Pas une longueur fixe : deux cliquets ont rougi dans ce dépôt pour
    avoir découpé 600 ou 900 signes après une ancre, simplement parce qu'un
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
            first_name=r.capitalize(), last_name="V%d" % n,
            email="%s%d@visible.test" % (r, n), password=hash_password("x"),
            status=s)
        coord, champ = faire("coord", "coordinateur"), faire("champ", "champion")
        lect = faire("lect", "user")
        db.session.add_all([coord, champ, lect])
        db.session.commit()
        # Socle VALIDE : ce fichier eprouve le regime « une modification,
        # une demande ». Au defaut (saisie), le champion ecrirait
        # directement et rien ne partirait au brouillon.
        ent = Entity(name="Visible carto %d" % n, owner_id=coord.id,
                     is_shared=True, socle_etat="valide")
        db.session.add(ent)
        db.session.commit()
        act = Activities(name="Visible activité %d" % n, entity_id=ent.id,
                         is_result=False)
        db.session.add(act)
        db.session.commit()
        d = {"coord": coord.id, "champ": champ.id, "lect": lect.id,
             "ent": ent.id, "act": act.id, "n": n}
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
        User.query.filter(User.id.in_([d["coord"], d["champ"], d["lect"]])) \
            .delete(synchronize_session=False)
        db.session.commit()


def _comme(app, uid, entity_id):
    """Un client PROPRE. ⚠️ `client` et `auth_client` sont le MÊME objet en
    portée session : s'en servir ici déconnecterait les fichiers suivants."""
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["active_entity_id"] = entity_id
    return c


def _ranger_gestes(app, carto, *gestes_bruts):
    """Dépose les gestes dans le brouillon du champion, dans l'ordre."""
    from Code.models.models import Entity, User
    from Code.propositions_activite import ajouter_geste, brouillon, gestes, \
        lire_geste
    with app.test_request_context():
        from flask import session
        session["user_id"] = carto["champ"]
        session["active_entity_id"] = carto["ent"]
        u = db.session.get(User, carto["champ"])
        e = db.session.get(Entity, carto["ent"])
        cr = None
        for chemin, methode, corps in gestes_bruts:
            deja = gestes(cr) if cr is not None else None
            g = lire_geste(chemin, methode, corps, deja=deja)
            assert g is not None, "geste non proposable : %s" % chemin
            cr, _ = ajouter_geste(u, e, g)
        return brouillon(u, e).id


# ══════════════════════════════════════════════════════════════════════════
class TestLesReferencesLocales:
    """⚠️⚠️ Sans elles, le palier est INFRANCHISSABLE sur une activité vierge :
    il exige un outil, un outil se rattache à une tâche, et la tâche en
    attente n'a aucun identifiant."""

    def test_une_reference_se_lit_et_s_ecrit(self):
        from Code.propositions_activite import rang_de_la_ref, ref_vers
        assert rang_de_la_ref("b:3") == 3
        assert rang_de_la_ref(ref_vers(7)) == 7
        for pas_une in ("12", "", None, 4, "b:", "ab:1", "b:x"):
            assert rang_de_la_ref(pas_une) is None

    def test_les_references_se_trouvent_jusque_dans_les_listes(self):
        from Code.propositions_activite import refs_du_corps
        assert refs_du_corps({"task_id": "b:0",
                              "existing_tool_ids": [4, "b:2"],
                              "n": 1}) == {0, 2}
        assert refs_du_corps(None) == set()

    def test_outiller_une_tache_en_attente_se_range_SOUS_son_activite(self, app, carto):
        """Sinon le geste part « hors activité » — là où le champion ne le
        retrouve pas, et c'est tout le reproche."""
        _ranger_gestes(
            app, carto,
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "Peser"}),
            ("/tools/add", "POST", {"task_id": "b:0", "new_tools": ["Balance"]}))
        j = _comme(app, carto["champ"], carto["ent"]) \
            .get("/api/propositions/brouillon").get_json()
        g = j["brouillon"]["gestes"]
        assert g[1]["activity_id"] == carto["act"]
        assert g[1]["objet"] == "Balance"
        assert g[1]["vise"] == [0]

    def test_le_REJEU_resout_la_reference_et_outille_la_tache(self, app, carto):
        """La tache naît au rejeu, et l'outil doit tomber SUR ELLE.

        ⚠️ Éprouvé par le REJEU, et non plus par une simulation : celle-ci
        mesurait ce que le brouillon donnerait, pour un palier qui lisait le
        brouillon. Le premier remplissage s'écrivant désormais directement en
        base (`Code/socle_activites.py`), il n'y a plus rien à simuler et
        `simuler` est partie avec son dernier appelant. La référence `b:0`,
        elle, sert toujours — c'est elle qui permet d'outiller une tâche qui
        n'existe pas encore quand le coordinateur approuve."""
        from Code.models.models import ActivityChangeRequest, Task, User
        from Code.propositions_activite import rejouer
        rid = _ranger_gestes(
            app, carto,
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "Peser"}),
            ("/tools/add", "POST", {"task_id": "b:0", "new_tools": ["Balance"]}))
        with app.test_request_context():
            from flask import session
            session["user_id"] = carto["coord"]
            session["active_entity_id"] = carto["ent"]
            cr = db.session.get(ActivityChangeRequest, rid)
            assert rejouer(cr, db.session.get(User, carto["coord"])) == 2
        with app.app_context():
            t = Task.query.filter_by(activity_id=carto["act"]).first()
            assert t is not None and t.name == "Peser"
            assert [o.name for o in t.tools] == ["Balance"]

    def test_le_rejeu_resout_la_reference_par_ce_qu_il_vient_d_ecrire(self, app, carto):
        from Code.models.models import ActivityChangeRequest, Task, User
        from Code.propositions_activite import rejouer
        rid = _ranger_gestes(
            app, carto,
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "Peser"}),
            ("/tools/add", "POST", {"task_id": "b:0", "new_tools": ["Balance"]}))
        with app.test_request_context():
            from flask import session
            session["user_id"] = carto["coord"]
            session["active_entity_id"] = carto["ent"]
            rejouer(db.session.get(ActivityChangeRequest, rid),
                    db.session.get(User, carto["coord"]))
        with app.app_context():
            t = Task.query.filter_by(activity_id=carto["act"]).one()
            assert t.name == "Peser"
            assert [o.name for o in t.tools] == ["Balance"]

    def test_une_reference_vers_rien_ARRETE_le_rejeu_sans_rien_ecrire(self, app, carto):
        """⚠️ Laisser passer la chaîne « b:9 » la ferait arriver jusqu'à
        `int()` dans la route visée : le rejeu s'arrêterait sur une pile
        Python au lieu d'un motif lisible."""
        from Code.models.models import ActivityChangeRequest, Task, User
        from Code.propositions_activite import EchecDeRejeu, rejouer
        rid = _ranger_gestes(
            app, carto,
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "Peser"}),
            ("/tools/add", "POST", {"task_id": "b:9", "new_tools": ["Balance"]}))
        with app.test_request_context():
            from flask import session
            session["user_id"] = carto["coord"]
            session["active_entity_id"] = carto["ent"]
            with pytest.raises(EchecDeRejeu) as exc:
                rejouer(db.session.get(ActivityChangeRequest, rid),
                        db.session.get(User, carto["coord"]))
            assert exc.value.rang == 1 and "b:9" in exc.value.raison
        with app.app_context():
            assert Task.query.filter_by(activity_id=carto["act"]).count() == 0

    def test_retirer_une_tache_emporte_ce_qui_la_visait(self, app, carto):
        from Code.models.models import ActivityChangeRequest
        from Code.propositions_activite import gestes, retirer_geste
        rid = _ranger_gestes(
            app, carto,
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "A"}),
            ("/tools/add", "POST", {"task_id": "b:0", "new_tools": ["O1"]}),
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "B"}))
        with app.app_context():
            cr = db.session.get(ActivityChangeRequest, rid)
            assert retirer_geste(cr, 0)
            restants = gestes(db.session.get(ActivityChangeRequest, rid))
            assert [g["corps"].get("name") for g in restants] == ["B"]

    def test_le_retrait_RENUMEROTE_les_references_qui_restent(self, app, carto):
        """Sans cela, « outiller la tâche du geste 2 » se mettrait à désigner
        le geste 1, c'est-à-dire n'importe quoi."""
        from Code.models.models import ActivityChangeRequest
        from Code.propositions_activite import gestes, retirer_geste
        rid = _ranger_gestes(
            app, carto,
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "A"}),
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "B"}),
            ("/tools/add", "POST", {"task_id": "b:1", "new_tools": ["O"]}))
        with app.app_context():
            cr = db.session.get(ActivityChangeRequest, rid)
            assert retirer_geste(cr, 0)
            restants = gestes(db.session.get(ActivityChangeRequest, rid))
            assert len(restants) == 2
            assert restants[1]["corps"]["task_id"] == "b:0"

    def test_le_brouillon_vide_par_cascade_disparait(self, app, carto):
        from Code.models.models import ActivityChangeRequest
        from Code.propositions_activite import retirer_geste
        rid = _ranger_gestes(
            app, carto,
            ("/tasks/add", "POST", {"activity_id": carto["act"], "name": "A"}),
            ("/tools/add", "POST", {"task_id": "b:0", "new_tools": ["O"]}))
        with app.app_context():
            assert retirer_geste(db.session.get(ActivityChangeRequest, rid), 0)
            assert db.session.get(ActivityChangeRequest, rid) is None


# ══════════════════════════════════════════════════════════════════════════
class TestLeBrouillonSePoseDansSaFiche:

    def test_le_gabarit_des_taches_porte_l_ancre(self):
        g = _lire(os.path.join(GAB, "tasks_partial.html"))
        assert 'data-acp-act="{{ activity.id }}"' in g

    def test_l_ancre_est_sur_le_conteneur_et_PAS_sur_la_liste(self):
        """⚠️ `#tasks-list-<id>` n'est rendu QUE si l'activité porte déjà une
        tâche — c'est-à-dire jamais dans le cas qui nous occupe."""
        g = _lire(os.path.join(GAB, "tasks_partial.html"))
        # ⚠️ On lit la BALISE qui porte l'attribut, pas une fenêtre de n
        # signes avant lui : le commentaire qui l'explique s'est glissé entre
        # les deux, et le cliquet est tombé sur sa propre explication.
        balise = re.search(r"<[^>]*data-acp-act[^>]*>", g).group(0)
        assert "tasks-section-modern" in balise
        assert "tasks-list-" not in balise

    def test_le_js_pose_les_cartes_dans_la_fiche(self):
        js = _sans_commentaires_js(_lire(JS_ACP))
        corps = _corps(js, "function placer()")
        assert ".tasks-section-modern[data-acp-act=" in corps

    def test_placer_repart_de_zero(self):
        """Un geste retiré doit disparaître de la fiche : sans ce nettoyage,
        les cartes s'empileraient à chaque rechargement du brouillon."""
        corps = _corps(_sans_commentaires_js(_lire(JS_ACP)), "function placer()")
        assert "[data-acp-pose]" in corps and ".remove()" in corps

    def test_charger_replace_les_cartes(self):
        corps = _corps(_sans_commentaires_js(_lire(JS_ACP)),
                       "async function charger()")
        assert "placer()" in corps

    def test_les_fiches_arrivees_PLUS_TARD_recoivent_leurs_gestes(self):
        """La liste des activités arrive par lots de 20."""
        js = _sans_commentaires_js(_lire(JS_ACP))
        corps = _corps(js, "function observer()")
        assert "main-activities-list" in corps
        assert "MutationObserver" in corps and "placer" in corps

    def test_un_geste_hors_activite_ne_se_pose_nulle_part(self):
        """Un outil du CATALOGUE n'appartient à aucune fiche : lui en
        inventer une le ferait paraître sous une activité qui ne le porte
        pas."""
        corps = _corps(_sans_commentaires_js(_lire(JS_ACP)),
                       "function groupeParActivite()")
        assert "if (!g.activity_id) return;" in corps

    def test_une_tache_en_attente_s_OUTILLE(self):
        """Le point bloquant : sans ce bouton, le palier est infranchissable
        sur toute activité vierge."""
        js = _sans_commentaires_js(_lire(JS_ACP))
        corps = _corps(js, "function carteGeste(")
        assert "data-outiller" in corps
        assert "task.add" in corps, \
            "seule une tâche AJOUTÉE s'outille — pas une suppression"

    def test_l_outillage_part_en_UN_SEUL_geste(self):
        """⚠️ Passer d'abord par `/gestion_outils/api/tools` pour créer
        l'outil — ce que fait le formulaire des tâches existantes — donnerait
        un second geste détourné dont on ne pourrait pas lire l'identifiant.
        `new_tools` crée-ou-rattache par nom, en un appel."""
        corps = _corps(_sans_commentaires_js(_lire(JS_ACP)),
                       "async function validerOutils(")
        assert "'/tools/add'" in corps
        assert "/gestion_outils/api/tools" not in corps
        assert "new_tools" in corps and "'b:' + rang" in corps

    def test_les_libelles_sont_dans_les_DEUX_langues(self):
        from Code.translations import TRANSLATIONS
        cles = [c for c in TRANSLATIONS["fr"] if c.startswith("acp.pose_")]
        assert len(cles) >= 9
        for c in cles:
            assert c in TRANSLATIONS["en"], c
            assert TRANSLATIONS["en"][c] != TRANSLATIONS["fr"][c], c

    def test_les_libelles_sont_INJECTES_dans_le_gabarit(self):
        """`T()` rend la CLÉ quand elle manque : une clé oubliée s'afficherait
        telle quelle, sans la moindre erreur."""
        gab = _lire(os.path.join(GAB, "activite_propositions.html"))
        js = _sans_commentaires_js(_lire(JS_ACP))
        lues = set(re.findall(r"T\('(pose_[a-z_]+)'\)", js))
        assert lues
        for cle in lues:
            assert re.search(r"\b%s:" % cle, gab), cle

    def test_la_couleur_des_cartes_est_celle_de_la_GOUVERNANCE(self):
        """Ambre comme le bandeau et la fenêtre, pas le violet de la page :
        ces lignes parlent de ce qui ARRIVE à ce qu'on écrit."""
        css = _sans_commentaires_css(_lire(CSS_ACP))
        i = css.index(".acp-pose {")
        bloc = css[i:css.index("}", i)]
        assert "--acp-or" in bloc and "dashed" in bloc

    def test_aucune_regle_neuve_ne_lit_l_accent_doux_de_la_racine(self):
        """⚠️ `--pg-accent-soft` et ses trois frères sont déclarés sur
        `:root`, où `--pg-accent` vaut encore le gris par défaut."""
        css = _sans_commentaires_css(_lire(CSS_ACP))
        bloc = css[css.index(".acp-pose {"):]
        for jeton in ("--pg-accent-soft", "--pg-accent-softer",
                      "--pg-accent-border", "--pg-accent-glow"):
            assert jeton not in bloc, jeton


# ══════════════════════════════════════════════════════════════════════════
class TestLaFenetreDeBienvenueNeRevientPlus:
    """⚠️ `POST /api/bienvenue/vue` tombait en 403 pour tout compte sans droit
    d'écriture : la signature n'était jamais écrite, et la fenêtre revenait à
    CHAQUE page. C'est le défaut signalé sur staging, console à l'appui."""

    def test_la_porte_laisse_passer_le_marquage(self):
        from Code.ecriture import porte
        assert porte("/api/bienvenue/vue", "POST") is None

    def test_un_compte_en_lecture_seule_peut_marquer_la_fenetre_vue(self, app, carto):
        c = _comme(app, carto["lect"], carto["ent"])
        r = c.post("/api/bienvenue/vue")
        assert r.status_code == 200 and r.get_json()["ok"] is True

    def test_et_la_fenetre_ne_revient_pas(self, app, carto):
        from Code.bienvenue import etat
        c = _comme(app, carto["lect"], carto["ent"])
        c.post("/api/bienvenue/vue")
        with app.test_request_context():
            from flask import session
            session["user_id"] = carto["lect"]
            assert etat()["montrer"] is False


# ══════════════════════════════════════════════════════════════════════════
class TestLeChatbot:

    def test_converser_n_est_pas_ecrire(self):
        """`/chat` n'écrit pas une ligne : il est en POST parce qu'il porte un
        historique. Refusé, il répondait « lecture seule » à un champion qui a
        pourtant le droit de proposer des tâches."""
        from Code.ecriture import porte
        assert porte("/api/chatbot/chat", "POST") is None

    def test_mais_injecter_reste_sous_la_porte(self):
        from Code.ecriture import TOUT_COMPTE
        assert not "/api/chatbot/inject".startswith(TOUT_COMPTE)

    def test_injecter_SE_PROPOSE(self, app, carto):
        """Sinon le champion est refusé avec `lecture_seule` — le motif
        réservé à `user` — pour un geste qu'il peut faire à la main."""
        from Code.propositions_activite import chemin_propasable, lire_geste
        assert chemin_propasable("/api/chatbot/inject")
        g = lire_geste("/api/chatbot/inject", "POST",
                       {"activity_id": carto["act"],
                        "tasks": [{"label": "Peser"}, {"label": "Trier"}]})
        assert g["op"] == "task.add"
        assert g["activity_id"] == carto["act"]
        assert g["objet"] == "Peser +1"

    def test_le_refus_de_la_porte_passe_par_le_CATALOGUE(self):
        """Il partait tel quel dans la réponse, et le chatbot l'affiche sans
        le relire : « lecture seule » s'écrivait en plein milieu d'une
        interface anglaise."""
        from Code.ecriture import MOTIF
        from Code.translations import TRANSLATIONS
        for code, (cle, _statut) in MOTIF.items():
            assert cle.startswith("porte."), code
            assert cle in TRANSLATIONS["fr"] and cle in TRANSLATIONS["en"]
            assert TRANSLATIONS["en"][cle] != TRANSLATIONS["fr"][cle]

    def test_le_refus_suit_la_langue_de_la_session(self, app):
        from Code.ecriture import _refus
        with app.test_request_context("/tasks/add", method="POST"):
            from flask import session
            session["lang"] = "en"
            corps, statut = _refus("lecture_seule")
            assert statut == 403
            assert corps.get_json()["error"] == "read-only"
            assert corps.get_json()["code"] == "lecture_seule"

    def test_plus_une_phrase_francaise_en_dur_dans_le_js(self):
        """⚠️ `_clearDraft()` RÉÉCRIVAIT le bouton du gabarit, pourtant
        traduit : c'est là que le français revenait, dès l'ouverture."""
        js = _sans_commentaires_js(_lire(JS_CHAT))
        for phrase in ("Injection en cours", "tâche(s) ajoutée(s)",
                       "En attente de la conversation",
                       "tâche(s) dans l'activité",
                       "Les tâches validées seront ajoutées"):
            assert phrase not in js, phrase

    def test_le_bouton_garde_l_id_que_le_compteur_reecrit(self):
        """Sans lui, le bouton reste à « 0 tâche » quoi que l'IA propose."""
        corps = _corps(_sans_commentaires_js(_lire(JS_CHAT)),
                       "function _clearDraft()")
        assert "chatbot-inject-label" in corps

    def test_le_sous_titre_dit_le_REGIME_d_ecriture(self):
        """On ne promet pas un ajout immédiat à qui va déposer une
        proposition."""
        gab = _lire(os.path.join(GAB, "chatbot_widget.html"))
        assert "chat.inject_sub_prop" in gab and "propose_activites" in gab
        corps = _corps(_sans_commentaires_js(_lire(JS_CHAT)),
                       "function _clearDraft()")
        assert "CHAT_PROPOSE" in corps

    def test_une_injection_DETOURNEE_ne_recharge_pas_la_fiche(self):
        """Annoncer « n tâches ajoutées » puis recharger montrerait une liste
        inchangée — on croirait avoir perdu sa saisie."""
        js = _sans_commentaires_js(_lire(JS_CHAT))
        corps = _corps(js, "window.injectTasks = function ()")
        assert "'proposition'" in corps
        assert "else if (!propose)" in corps

    def test_la_peau_est_VIOLETTE_et_jamais_ambre(self):
        """« On garde le violet, je veux pas de orange. »"""
        # ⚠️ `rindex` : la règle d'origine porte le MÊME sélecteur plus haut
        # dans la feuille, et c'est la dernière déclarée qui gagne. Un
        # cliquet qui cherche une chaîne doit borner sa zone.
        css = _sans_commentaires_css(_lire(CSS_CHAT))
        i = css.rindex("#chatbot-inject-btn {")
        bouton = css[i:css.index("}", i)]
        assert "--cb-vif" in bouton and "--cb-prof" in bouton
        assert "#22c55e" not in bouton and "#16a34a" not in bouton

    def test_l_en_tete_est_un_fond_de_NUIT(self):
        """C'est le CONTRASTE qui désigne le sujet, pas un aplat de plus."""
        css = _sans_commentaires_css(_lire(CSS_CHAT))
        i = css.rindex("#chatbot-header {")
        bloc = css[i:css.index("}", i)]
        assert "--cb-nuit" in bloc and "radial-gradient" in bloc

    def test_les_taches_proposees_portent_un_RAIL_numerote(self):
        js = _sans_commentaires_js(_lire(JS_CHAT))
        assert 'class="cb-task-n"' in js
        assert "T${i + 1}." not in js, \
            "le numéro a sa pastille — collé au libellé, il se lisait " \
            "comme un bout du texte"


# ══════════════════════════════════════════════════════════════════════════
class TestLaPageTempsNePRESELECTIONNEPlus:
    """« Cela présélectionne la première activité de la liste. » On
    enregistrait une charge sur une activité que personne n'avait désignée,
    et l'écran annonçait « enregistré »."""

    def test_les_trois_listes_ouvrent_sur_un_choix_VIDE(self):
        gab = _lire(os.path.join(GAB, "time_dashboard.html"))
        for ident, cle in (("act-activity", "time.choisir_activite"),
                           ("fw-activity", "time.choisir_activite"),
                           ("role-select", "time.choisir_role")):
            i = gab.index('id="%s"' % ident)
            suite = gab[i:i + 320]
            assert '<option value="">' in suite, ident
            assert cle in suite, ident

    def test_le_serveur_refuse_une_analyse_sans_sujet(self, app, carto):
        c = _comme(app, carto["coord"], carto["ent"])
        for url, charge, code in (
                ("/temps/api/activity_workload", {"duration": 10}, "sans_activite"),
                ("/temps/api/weakness", {"mode": "activity"}, "sans_activite"),
                ("/temps/api/role_analysis", {"lines": [{"activity_id": 1}]},
                 "sans_role")):
            r = c.post(url, json=charge)
            assert r.status_code == 400, url
            assert r.get_json()["code"] == code, url

    def test_une_ligne_de_projet_sans_activite_est_refusee(self, app, carto):
        c = _comme(app, carto["coord"], carto["ent"])
        r = c.post("/temps/api/project",
                   json={"name": "P", "lines": [{"activity_id": "",
                                                 "duration": 3}]})
        assert r.status_code == 400
        assert r.get_json()["code"] == "ligne_sans_activite"

    def test_une_chaine_vide_ne_tombe_pas_en_500(self):
        """⚠️ La valeur arrivait jusqu'à `int('')` : un refus se dit, il ne
        tombe pas."""
        from Code.routes.time_view import sujet_choisi
        for rien in ("", "   ", None, "abc", 0, "0", -3):
            assert sujet_choisi(rien) is None, repr(rien)
        assert sujet_choisi("7") == 7 and sujet_choisi(7) == 7

    def test_vider_la_saisie_remet_les_listes_a_vide(self):
        """Un `<select>` garde le choix précédent d'une page à l'autre."""
        corps = _corps(_sans_commentaires_js(_lire(JS_TIME)),
                       "function viderSaisie(type)")
        for ident in ("#act-activity", "#role-select", "#fw-activity"):
            assert ident in corps, ident

    def test_l_ecran_refuse_AVANT_d_envoyer(self):
        js = _sans_commentaires_js(_lire(JS_TIME))
        assert "err_sans_activite" in js and "err_sans_role" in js
        assert "err_ligne_sans_activite" in js

    def test_les_messages_existent_dans_les_deux_langues(self):
        from Code.translations import TRANSLATIONS
        for cle in ("time.choisir_activite", "time.choisir_role",
                    "time.err_sans_activite", "time.err_sans_role",
                    "time.err_ligne_sans_activite"):
            assert cle in TRANSLATIONS["fr"] and cle in TRANSLATIONS["en"], cle
            assert TRANSLATIONS["en"][cle] != TRANSLATIONS["fr"][cle], cle

    def test_les_messages_sont_INJECTES(self):
        gab = _lire(os.path.join(GAB, "time_dashboard.html"))
        for cle in ("err_sans_activite", "err_sans_role",
                    "err_ligne_sans_activite"):
            assert re.search(r"\b%s:" % cle, gab), cle

    def test_aucun_appel_de_defauts_avec_un_identifiant_VIDE(self):
        """`/activity_defaults/` sans identifiant rend une 404 que personne ne
        lit."""
        js = _sans_commentaires_js(_lire(JS_TIME))
        for ancre in ("async function prefillDefaults()",
                      "async function refreshActivityDefaults()",
                      "async function loadRoleActivities(roleId)"):
            corps = _corps(js, ancre)
            assert "return" in corps.split("\n")[1] or "if (!" in corps, ancre


# ══════════════════════════════════════════════════════════════════════════
class TestLeLienEntreLActiviteEtCeQuElleProduit:
    """« Rien ne fait le lien entre les deux. » On cliquait une barre à gauche,
    un panneau changeait à droite sous un titre (« SES marches ») dont le
    « ses » ne désignait rien."""

    def test_le_panneau_NOMME_l_activite_qu_il_decrit(self):
        js = _sans_commentaires_js(_lire(JS_COMP))
        corps = _corps(js, "function marches(ap)")
        assert "vo-sujet" in corps and "a.activity_name" in corps

    def test_la_teinte_est_posee_sur_le_DUO(self):
        """La barre choisie et le panneau doivent lire la MÊME, et elles
        vivent dans deux colonnes sœurs."""
        corps = _corps(_sans_commentaires_js(_lire(JS_COMP)),
                       "function marches(ap)")
        assert "'--vo-c'" in corps and ".vo-duo" in corps

    def test_la_gouttiere_porte_un_TRACE_et_plus_une_pointe(self):
        """⚠️ RÉÉCRIT le 24/11. La gouttière portait une POINTE SEULE, posée à
        un `top` fixe : rien n'en partait, donc rien ne bougeait quand on
        changeait d'activité. Elle est devenue une COLONNE de la grille, et
        le lien s'y trace — c'est le traitement retenu sur la maquette
        « L'entre-deux », dont seule la pointe avait été livrée."""
        css = _sans_commentaires_css(_lire(CSS_COMP))
        i = css.index(".vo-duo {")
        assert "minmax(0, 1fr) 56px 420px" in css[i:css.index("}", i)]
        j = css.index(".ln-tete {")
        assert "var(--vo-c)" in css[j:css.index("}", j)]
        assert '<div class="vo-lane" id="vo-lane"' in _lire(JS_COMP)

    def test_la_barre_choisie_marque_son_NIVEAU(self):
        """⚠️ RÉÉCRIT le 24/11. Sa pointe partait de son BAS, qui ne dit rien,
        et le lien part de son HAUT — de son NIVEAU, qui est tout le propos de
        cette colonne. Deux pointes à 160 px l'une de l'autre, toutes deux
        « vers le panneau », ne désignaient plus rien : c'est la pastille du
        lien qui marque désormais le départ."""
        css = _sans_commentaires_css(_lire(CSS_COMP))
        assert ".esc .st.on::after" not in css
        i = css.index(".ln-src {")
        assert "var(--vo-c)" in css[i:css.index("}", i)]
        g = _corps(_sans_commentaires_js(_lire(JS_COMP)), "function geoLien()")
        assert "'#vo-esc .st.on .bar'" in g and "b.top" in g

    def test_le_panneau_porte_le_lisere_de_la_teinte(self):
        css = _sans_commentaires_css(_lire(CSS_COMP))
        i = css.index(".vo-mp .mpan {")
        assert "var(--vo-c)" in css[i:css.index("}", i)]

    def test_en_colonne_la_fleche_regarde_vers_le_BAS(self):
        """Sous 1100 px réels les deux blocs s'empilent : une flèche qui
        pointe à droite ne désigne plus rien."""
        css = _sans_commentaires_css(_lire(CSS_COMP))
        # ⚠️ L'ancre d'avant partait de la position de `.vo-duo .vo-mp::before`
        # et prenait le PREMIER média de 1100 px rencontré ensuite — il y en a
        # cinq dans cette feuille, et depuis que la pointe a rejoint le repli
        # c'est le SUIVANT qui tombait sous la lecture. On borne sur le bloc
        # qui porte le marqueur.
        bloc = _bloc_media(css, "@media (max-width: 1100px) {", ".vo-lane")
        assert ".vo-mp::before" in bloc and "transform: translateX(-50%)" in bloc
        assert ".vo-lane { display: none; }" in bloc, \
            "un trait tiré de gauche à droite ne relie plus rien, empilé"

    def test_le_libelle_existe_dans_les_deux_langues(self):
        js = _lire(JS_COMP)
        assert js.count("vo_produit:") == 2
        fr = re.search(r"vo_produit: '([^']+)'", js).group(1)
        assert "produit" in fr.lower()
