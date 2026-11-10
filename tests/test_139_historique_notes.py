# -*- coding: utf-8 -*-
"""L'HISTORIQUE DES NOTES — une courbe par sortie, plus celle de l'activité.

Ce que ce fichier garde, et pourquoi :

  • le niveau d'une date se RECALCULE depuis la mesure du palier (un palier
    ne stocke pas de niveau) ;
  • une sortie JUGÉE À LA MAIN n'a qu'UN point, parce que `/mastery/evaluate`
    écrase la note précédente — l'écran doit le dire au lieu de laisser
    croire à une progression qu'on n'a pas gardée ;
  • la courbe GLOBALE n'existe QUE là où toutes les sorties portent une note
    (le MINIMUM, et NULL tant qu'il en manque une), et elle REPORTE le
    dernier niveau connu de chacune — sans ce report, la colonne du jour ne
    porterait que la sortie qu'on vient de noter ;
  • la route se lit avec la même porte que `/mastery/activity` : elle porte
    les niveaux d'une personne et jusqu'aux mesures relevées en séance.
"""
import json
from datetime import date, datetime, timedelta

import pytest

from Code.extensions import db

_N = [0]


@pytest.fixture
def deux_sorties(app, ids):
    """Une activité, deux sorties : une MESURÉE, une jugée à la main.

    ⚠️ Le décor est recréé ici, avec un compteur dans les noms : la base est
    commune à toute la suite et les rôles sont COMMUNS à l'entreprise — un
    nom fixe fait collision dès que deux cas tournent.
    """
    from Code.models.models import (Activities, Data, Link, Role, User, UserRole,
                                    activity_roles)
    from Code.security import hash_password
    _N[0] += 1
    n = _N[0]
    with app.app_context():
        dev = User(first_name="Dev", last_name="T139", email="dev.t139.%d@test" % n,
                   password=hash_password("Test1234!"), status="user")
        bob = User(first_name="Bob", last_name="T139", email="bob.t139.%d@test" % n,
                   password=hash_password("Test1234!"), status="user")
        db.session.add_all([dev, bob])
        db.session.commit()

        role = Role(name="T139 Rédacteur %d" % n, entity_id=ids["entity_id"])
        db.session.add(role)
        db.session.commit()
        db.session.add(UserRole(user_id=bob.id, role_id=role.id, manager_id=dev.id))

        act = Activities(name="T139 Documenter %d" % n, entity_id=ids["entity_id"])
        av1 = Activities(name="T139 Aval A %d" % n, entity_id=ids["entity_id"])
        av2 = Activities(name="T139 Aval B %d" % n, entity_id=ids["entity_id"])
        db.session.add_all([act, av1, av2])
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant",
            required_mastery_level=2))
        db.session.add_all([
            Link(entity_id=ids["entity_id"], source_activity_id=act.id,
                 target_activity_id=av1.id, description="Dossier T139 %d" % n, type="flux"),
            Link(entity_id=ids["entity_id"], source_activity_id=act.id,
                 target_activity_id=av2.id, description="Prototype T139 %d" % n, type="flux"),
        ])
        db.session.commit()

        from Code.routes.qualify_outputs import get_activity_outputs
        sorties = get_activity_outputs(act.id)
        mes, main = sorties[0], sorties[1]
        mes.norme_valeur, mes.norme_unite, mes.norme_sens = 48.0, "h", "moins"
        db.session.commit()
        info = {"dev_id": dev.id, "bob_id": bob.id, "role_id": role.id,
                "activity_id": act.id, "mes_id": mes.id, "main_id": main.id}
    yield info
    with app.app_context():
        from Code.models.models import (CompetencyEvaluation, NoteEvaluation,
                                        PalierPerformance)
        # ⚠️ Objet par objet, jamais `delete(synchronize_session=False)` : la
        # session est partagée, et des objets morts ressortent trois fichiers
        # plus loin sur le commit d'une route sans rapport.
        for m in (PalierPerformance, CompetencyEvaluation, NoteEvaluation):
            for x in m.query.filter_by(user_id=info["bob_id"]).all():
                db.session.delete(x)
        db.session.commit()


@pytest.fixture
def comme_dev(auth_client, deux_sorties):
    """On agit en développeur de compétences — et on rend la session telle
    qu'on l'a trouvée : `auth_client` est partagé en portée session."""
    with auth_client.session_transaction() as sess:
        avant = sess.get("user_id")
        sess["user_id"] = deux_sorties["dev_id"]
    yield
    with auth_client.session_transaction() as sess:
        if avant is None:
            sess.pop("user_id", None)
        else:
            sess["user_id"] = avant


def _palier(app, d, cible, mesure, jours, rang):
    """Un palier déjà tranché, daté dans le passé."""
    from Code.models.models import PalierPerformance
    with app.app_context():
        p = PalierPerformance(
            user_id=d["bob_id"], activity_id=d["activity_id"], data_id=d["mes_id"],
            role_id=d["role_id"], rang=rang, cible_valeur=cible,
            echeance=date.today() - timedelta(days=jours),
            statut="atteint", mesure_valeur=mesure,
            evalue_le=date.today() - timedelta(days=jours))
        db.session.add(p)
        db.session.commit()


def _note_main(app, d, niveau, jours=0):
    """La note à la main de la sortie sans norme, par un Garant."""
    from Code.models.models import CompetencyEvaluation
    with app.app_context():
        ev = CompetencyEvaluation(
            user_id=d["bob_id"], activity_id=d["activity_id"],
            item_type="activity_results", item_id=d["main_id"],
            eval_number="1", note="", mastery_level=niveau,
            evaluated_at=datetime.utcnow() - timedelta(days=jours))
        db.session.add(ev)
        db.session.commit()


def _registre(app, d, data_id, niveau, jours=0, source="main"):
    """Un événement du REGISTRE, daté — ce que `/mastery/evaluate` ajoute."""
    from Code.models.models import NoteEvaluation
    with app.app_context():
        db.session.add(NoteEvaluation(
            user_id=d["bob_id"], activity_id=d["activity_id"], data_id=data_id,
            role_id=d["role_id"], eval_number="1", niveau=niveau,
            posee_le=datetime.utcnow() - timedelta(days=jours), source=source))
        db.session.commit()


def _poster(client, d, data_id, niveau, preuve=None):
    """La vraie route : c'est elle qui doit alimenter le registre."""
    corps = {"user_id": d["bob_id"], "activity_id": d["activity_id"],
             "data_id": data_id, "role_id": d["role_id"], "evaluator": "1",
             "mastery_level": niveau}
    if preuve is not None:
        corps["evidence"] = preuve
    return client.post("/mastery/evaluate", json=corps)


def _histo(app, d):
    from Code.historique_notes import historique_activite
    with app.app_context():
        return historique_activite(d["bob_id"], d["activity_id"], d["role_id"])


class TestUneCourbeParSortie:

    def test_le_niveau_de_chaque_date_se_recalcule_depuis_la_mesure(self, app, deux_sorties):
        _palier(app, deux_sorties, 96.0, 90.0, 60, 1)
        _palier(app, deux_sorties, 72.0, 70.0, 30, 2)
        _palier(app, deux_sorties, 48.0, 46.0, 10, 3)
        h = _histo(app, deux_sorties)
        mes = [s for s in h["sorties"] if s["data_id"] == deux_sorties["mes_id"]][0]
        # 90 h : au-dessus de la première marche, rien n'est démontré → 1 ;
        # 46 h : la norme est tenue → 2.
        assert [p["niveau"] for p in mes["points"]] == [1, 1, 2]
        assert mes["tracable"] is True
        assert len(h["dates"]) == 3

    def test_les_dates_sont_l_union_ordonnee(self, app, deux_sorties):
        _palier(app, deux_sorties, 96.0, 90.0, 60, 1)
        _registre(app, deux_sorties, deux_sorties["main_id"], 3, jours=20)
        h = _histo(app, deux_sorties)
        assert h["dates"] == sorted(h["dates"])
        tous = [p["t"] for s in h["sorties"] for p in s["points"]]
        assert set(tous) == {0, 1}

    def test_une_sortie_jugee_a_la_main_GARDE_son_historique(self, app, deux_sorties):
        """⚠️ C'était le trou : `/mastery/evaluate` fait un upsert, la note
        précédente disparaissait, et la courbe se réduisait à un point. Le
        REGISTRE (`notes_evaluation`) garde un événement par écriture."""
        _registre(app, deux_sorties, deux_sorties["main_id"], 1, jours=40)
        _registre(app, deux_sorties, deux_sorties["main_id"], 2, jours=20)
        _registre(app, deux_sorties, deux_sorties["main_id"], 3, jours=5)
        h = _histo(app, deux_sorties)
        main = [s for s in h["sorties"] if s["data_id"] == deux_sorties["main_id"]][0]
        assert [p["niveau"] for p in main["points"]] == [1, 2, 3]
        assert main["tracable"] is True

    def test_la_route_ALIMENTE_le_registre(self, auth_client, app, deux_sorties, comme_dev):
        """L'état courant et l'événement s'écrivent ensemble : un état sans son
        événement serait un trou dans l'historique."""
        from Code.models.models import NoteEvaluation
        assert _poster(auth_client, deux_sorties, deux_sorties["main_id"], 1).status_code == 200
        assert _poster(auth_client, deux_sorties, deux_sorties["main_id"], 3).status_code == 200
        with app.app_context():
            evts = NoteEvaluation.query.filter_by(
                user_id=deux_sorties["bob_id"], data_id=deux_sorties["main_id"]).all()
            assert sorted(e.niveau for e in evts) == [1, 3]
            assert {e.source for e in evts} == {"main"}

    def test_deux_ecritures_le_MEME_jour_ne_font_qu_un_point(self, app, deux_sorties):
        """Sinon la courbe rebrousse chemin sur une abscisse unique. C'est
        l'état du jour qui compte, donc la dernière écriture."""
        _registre(app, deux_sorties, deux_sorties["main_id"], 1, jours=3)
        _registre(app, deux_sorties, deux_sorties["main_id"], 4, jours=3)
        h = _histo(app, deux_sorties)
        main = [s for s in h["sorties"] if s["data_id"] == deux_sorties["main_id"]][0]
        assert [p["niveau"] for p in main["points"]] == [4]

    def test_une_note_EFFACEE_arrete_le_report(self, app, deux_sorties):
        """⚠️ Un effacement est un vrai événement : il ne se dessine pas, mais
        il date la fin du report. Sans lui, une note retirée continuerait de
        peser sur le niveau de l'activité."""
        _palier(app, deux_sorties, 48.0, 46.0, 30, 1)          # J-30 : mesurée = 2
        _registre(app, deux_sorties, deux_sorties["main_id"], 3, jours=30)
        _registre(app, deux_sorties, deux_sorties["main_id"], None, jours=10)
        h = _histo(app, deux_sorties)
        main = [s for s in h["sorties"] if s["data_id"] == deux_sorties["main_id"]][0]
        assert [p["niveau"] for p in main["points"]] == [3], "l'effacement ne se dessine pas"
        assert h["complet"] is False, "la sortie n'a plus de note"
        assert [g["t"] for g in h["global"]] == [0], "la globale s'arrête à l'effacement"

    def test_une_sortie_jamais_notee_est_nommee(self, app, deux_sorties):
        _palier(app, deux_sorties, 96.0, 90.0, 60, 1)
        h = _histo(app, deux_sorties)
        main = [s for s in h["sorties"] if s["data_id"] == deux_sorties["main_id"]][0]
        assert main["points"] == []
        assert main["nom"] in h["sans_note"]

    def test_l_expertise_posee_a_la_main_termine_la_courbe(self, app, deux_sorties):
        """La déduction plafonne à 3 : un 4 ne peut venir que de la main, et
        l'historique mentirait s'il s'arrêtait à la dernière mesure. Les deux
        sources d'une sortie mesurée se réunissent dans UNE chronologie."""
        _palier(app, deux_sorties, 48.0, 46.0, 30, 1)
        _registre(app, deux_sorties, deux_sorties["mes_id"], 4, jours=2)
        h = _histo(app, deux_sorties)
        mes = [s for s in h["sorties"] if s["data_id"] == deux_sorties["mes_id"]][0]
        assert [p["niveau"] for p in mes["points"]] == [2, 4]


class TestLaCourbeGlobale:

    def test_elle_n_existe_pas_tant_qu_une_sortie_n_est_pas_notee(self, app, deux_sorties):
        """⚠️ C'est la règle du module : NULL tant qu'il en manque une, et le
        grand chiffre de l'écran dit « — » au même moment."""
        _palier(app, deux_sorties, 96.0, 90.0, 60, 1)
        h = _histo(app, deux_sorties)
        assert h["global"] == []
        assert h["complet"] is False

    def test_elle_est_le_MINIMUM_des_sorties(self, app, deux_sorties):
        _palier(app, deux_sorties, 48.0, 46.0, 30, 1)     # mesurée → 2
        _registre(app, deux_sorties, deux_sorties["main_id"], 4, jours=30)        # à la main → 4
        h = _histo(app, deux_sorties)
        assert h["complet"] is True
        assert [g["niveau"] for g in h["global"]] == [2]

    def test_elle_REPORTE_le_dernier_niveau_connu(self, app, deux_sorties):
        """⚠️ Sans report, la colonne du jour ne porterait que la sortie qu'on
        vient de noter : la globale sauterait à SA valeur — elle annonçait 4
        pour une activité qui vaut 2."""
        _palier(app, deux_sorties, 96.0, 90.0, 60, 1)     # J-60 : mesurée = 1
        _registre(app, deux_sorties, deux_sorties["main_id"], 4, jours=30)        # J-30 : à la main = 4
        _palier(app, deux_sorties, 48.0, 46.0, 10, 2)     # J-10 : mesurée = 2
        h = _histo(app, deux_sorties)
        # J-60 : il manque la sortie à la main → pas de globale.
        # J-30 : min(1, 4) = 1.  J-10 : min(2, 4) = 2.
        assert [(g["t"], g["niveau"]) for g in h["global"]] == [(1, 1), (2, 2)]


class TestLaPorte:

    def test_la_route_rend_l_historique(self, auth_client, deux_sorties, comme_dev, app):
        _palier(app, deux_sorties, 48.0, 46.0, 10, 1)
        r = auth_client.get("/mastery/historique/%d/%d?role_id=%d" % (
            deux_sorties["bob_id"], deux_sorties["activity_id"], deux_sorties["role_id"]))
        assert r.status_code == 200, r.data
        j = json.loads(r.data)
        assert len(j["sorties"]) == 2
        assert j["dates"]

    def test_un_tiers_ne_lit_pas_l_historique(self, app, auth_client, deux_sorties):
        """⚠️ Une route d'historique laissée ouverte rouvrirait par la bande
        ce que `/mastery/activity` vient de fermer."""
        from Code.models.models import User
        from Code.security import hash_password
        with app.app_context():
            tiers = User(first_name="Tiers", last_name="T139",
                         email="tiers.t139.%d@test" % _N[0],
                         password=hash_password("Test1234!"), status="user")
            db.session.add(tiers)
            db.session.commit()
            tid = tiers.id
        with auth_client.session_transaction() as sess:
            avant = sess.get("user_id")
            sess["user_id"] = tid
        try:
            r = auth_client.get("/mastery/historique/%d/%d?role_id=%d" % (
                deux_sorties["bob_id"], deux_sorties["activity_id"],
                deux_sorties["role_id"]))
            assert r.status_code == 403, r.data
        finally:
            with auth_client.session_transaction() as sess:
                if avant is None:
                    sess.pop("user_id", None)
                else:
                    sess["user_id"] = avant

    def test_activite_inconnue(self, auth_client, deux_sorties, comme_dev):
        r = auth_client.get("/mastery/historique/%d/999999" % deux_sorties["bob_id"])
        assert r.status_code == 404


class TestLeNiveauDuPalierEstFIGE:
    """⚠️ Il se DÉDUISAIT de la mesure à chaque lecture, avec les seuils
    d'aujourd'hui : poser plus tard une marche au-delà de la norme relisait
    tout le passé avec la nouvelle frontière, et l'historique changeait
    rétroactivement sans que personne n'ait rien touché."""

    def test_trancher_enregistre_le_niveau_du_jour(self, app, deux_sorties):
        from Code.models.models import PalierPerformance
        from Code.paliers import trancher
        with app.app_context():
            p = PalierPerformance(
                user_id=deux_sorties["bob_id"], activity_id=deux_sorties["activity_id"],
                data_id=deux_sorties["mes_id"], role_id=deux_sorties["role_id"],
                rang=1, cible_valeur=96.0, statut="en_cours")
            db.session.add(p)
            db.session.commit()
            trancher(p, 90.0)
            db.session.commit()
            assert p.niveau_atteint == 1

    def test_une_marche_posee_APRES_ne_bouge_plus_le_passe(self, app, deux_sorties):
        """96 → 72 → 48 (la norme) : une mesure de 30 h vaut 2, la norme est
        tenue. Poser ensuite une marche à 36 h déplace la frontière de
        l'« au-delà » — et la DÉDUCTION relirait alors ce 30 h comme un 3."""
        from Code.models.models import PalierPerformance
        from Code.paliers import niveau_depuis_mesure, pas_de_progression, seuil_au_dela
        _palier(app, deux_sorties, 96.0, 90.0, 60, 1)
        _palier(app, deux_sorties, 72.0, 70.0, 40, 2)
        _palier(app, deux_sorties, 48.0, 30.0, 20, 3)
        with app.app_context():
            p3 = PalierPerformance.query.filter_by(
                user_id=deux_sorties["bob_id"], rang=3).first()
            p3.niveau_atteint = 2          # ce qui avait été tranché ce jour-là
            db.session.add(PalierPerformance(
                user_id=deux_sorties["bob_id"], activity_id=deux_sorties["activity_id"],
                data_id=deux_sorties["mes_id"], role_id=deux_sorties["role_id"],
                rang=4, cible_valeur=36.0, statut="en_cours"))
            db.session.commit()
            # la déduction, elle, aurait changé d'avis
            cibles = [96.0, 72.0, 48.0, 36.0]
            marge = pas_de_progression(cibles, 48.0, "moins")
            assert niveau_depuis_mesure(30.0, 48.0, "moins", 96.0, marge,
                                        seuil_au_dela(cibles, 48.0, "moins", marge)) == 3
        h = _histo(app, deux_sorties)
        mes = [s for s in h["sorties"] if s["data_id"] == deux_sorties["mes_id"]][0]
        assert mes["points"][-1]["niveau"] == 2, "le verdict du jour ne se relit pas"

    def test_une_ligne_d_AVANT_retombe_sur_la_deduction(self, app, deux_sorties):
        """Sans ce repli, tout l'historique déjà en base tomberait d'un coup."""
        from Code.models.models import PalierPerformance
        _palier(app, deux_sorties, 48.0, 46.0, 10, 1)
        with app.app_context():
            p = PalierPerformance.query.filter_by(user_id=deux_sorties["bob_id"]).first()
            p.niveau_atteint = None
            db.session.commit()
        h = _histo(app, deux_sorties)
        mes = [s for s in h["sorties"] if s["data_id"] == deux_sorties["mes_id"]][0]
        assert mes["points"][-1]["niveau"] == 2


class TestLaPreuveNeSEffacePlusToute_seule:
    """⚠️ La route faisait `(evidence or "").strip() or None` sur une clé
    ABSENTE : poser un niveau depuis la piste de l'axe — où il n'y a pas de
    champ de preuve — effaçait ce que quelqu'un avait écrit."""

    def test_une_note_SANS_la_cle_laisse_la_preuve(self, auth_client, app,
                                                   deux_sorties, comme_dev):
        from Code.models.models import CompetencyEvaluation
        _poster(auth_client, deux_sorties, deux_sorties["main_id"], 2, preuve="CTR-114")
        _poster(auth_client, deux_sorties, deux_sorties["main_id"], 3)
        with app.app_context():
            ev = CompetencyEvaluation.query.filter_by(
                user_id=deux_sorties["bob_id"], item_id=deux_sorties["main_id"],
                eval_number="1").first()
            assert ev.mastery_level == 3
            assert ev.evidence == "CTR-114"

    def test_une_note_AVEC_la_cle_la_remplace(self, auth_client, app,
                                              deux_sorties, comme_dev):
        from Code.models.models import CompetencyEvaluation
        _poster(auth_client, deux_sorties, deux_sorties["main_id"], 2, preuve="CTR-114")
        _poster(auth_client, deux_sorties, deux_sorties["main_id"], 2, preuve="CTR-220")
        with app.app_context():
            ev = CompetencyEvaluation.query.filter_by(
                user_id=deux_sorties["bob_id"], item_id=deux_sorties["main_id"],
                eval_number="1").first()
            assert ev.evidence == "CTR-220"


class TestLaReprise:
    """Les notes déjà en base n'ont aucun événement : sans reprise, la frise
    perdrait le seul point qu'elle savait montrer."""

    def test_elle_recopie_l_etat_courant_et_le_MARQUE(self, app, deux_sorties):
        from Code.historique_notes import reprendre_notes_existantes
        from Code.models.models import NoteEvaluation
        _note_main(app, deux_sorties, 3, jours=12)
        with app.app_context():
            reprendre_notes_existantes(force=True)
            e = NoteEvaluation.query.filter_by(
                user_id=deux_sorties["bob_id"], data_id=deux_sorties["main_id"]).all()
            assert [x.niveau for x in e] == [3]
            assert e[0].source == "reprise", "une recopie n'est pas une note posée"

    def test_elle_ne_double_PAS_si_on_la_rejoue(self, app, deux_sorties):
        """⚠️ Le marqueur vit en base ; `force=True` la rejoue, et elle doit
        rester idempotente — sinon chaque démarrage ajouterait un point."""
        from Code.historique_notes import reprendre_notes_existantes
        from Code.models.models import NoteEvaluation
        _note_main(app, deux_sorties, 3, jours=12)
        with app.app_context():
            reprendre_notes_existantes(force=True)
            reprendre_notes_existantes(force=True)
            n = NoteEvaluation.query.filter_by(
                user_id=deux_sorties["bob_id"], data_id=deux_sorties["main_id"]).count()
            assert n == 1

    def test_l_ecran_dit_d_ou_part_l_historique(self, app, deux_sorties):
        """Une sortie dont TOUT l'historique vient de la reprise n'a pas été
        notée une seule fois : c'est le registre qui commence là."""
        from Code.historique_notes import reprendre_notes_existantes
        _note_main(app, deux_sorties, 3, jours=12)
        with app.app_context():
            reprendre_notes_existantes(force=True)
        h = _histo(app, deux_sorties)
        main = [s for s in h["sorties"] if s["data_id"] == deux_sorties["main_id"]][0]
        assert main["nom"] in h["avant_registre"]
        _registre(app, deux_sorties, deux_sorties["main_id"], 4, jours=1)
        h2 = _histo(app, deux_sorties)
        assert h2["avant_registre"] == [], "une note posée depuis lève la mention"
