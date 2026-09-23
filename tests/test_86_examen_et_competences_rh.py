# tests/test_86_examen_et_competences_rh.py
"""
Trois sujets livrés ensemble, parce qu'ils se tiennent :

1. **Les propositions s'examinent depuis la page Carte**, toutes cartos
   confondues. Elles vivaient dans la page RH, cadrées par la carto active :
   celui qui valide ne les voyait qu'en activant la carto visée — donc souvent
   jamais. Le détail dit en plus si la carto a bougé depuis le dépôt : appliquer
   REMPLACE la carto par la version proposée.
2. **Le tableau global des compétences** (page RH) : chaque personne × chacun
   de ses rôles, sur toutes les cartos. Il compte avec les fonctions de la page
   Compétences — ses chiffres doivent être ceux de `/mastery/synthese`, et son
   coût ne doit pas grandir avec l'effectif.
3. **Deux droits qui ne suivaient plus leurs règles** :
   - `competences_acces._statut_eleve` disait « champion ou admin ». Depuis les
     quatre paliers, le champion est le palier qui PROPOSE : il pouvait lire et
     noter tout le monde, et le coordinateur plus personne ;
   - les lignes « valider » et « enregistrer directement » du tableau des droits
     ne décidaient de rien : `can_review` / `can_edit` lisaient le statut brut.
"""
import json

import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.carto_sharing

DIAG = {
    "shapes": [
        {"id": "a", "type": "process", "label": "T86 Amont", "x": 100, "y": 0, "w": 120, "h": 60},
        {"id": "b", "type": "process", "label": "T86 Aval", "x": 400, "y": 0, "w": 120, "h": 60},
    ],
    "bands": [{"id": "b1", "label": "Bande T86", "height": 200}],
    "connections": [{"fromId": "a", "toId": "b", "label": "flux"}],
}


def _propose(diag):
    d = json.loads(json.dumps(diag))
    d["shapes"][0]["label"] = "T86 Amont renommée"
    return d


# Le client de test est partagé par toute la suite : on rend la session d'origine.
@pytest.fixture(scope="module", autouse=True)
def _restaurer_la_session(app, client, ids):
    yield
    with app.app_context():
        from Code.models.models import User
        seed = User.query.filter_by(email="test@devoptiq.com").first()
        uid, umail = seed.id, seed.email
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["user_email"] = umail
        sess["active_entity_id"] = ids["entity_id"]
        sess["lang"] = "fr"


def _mk_user(email, status, prenom="T86"):
    from Code.extensions import db
    from Code.models.models import User
    u = User.query.filter_by(email=email).first()
    if u is None:
        u = User(first_name=prenom, last_name=email.split("@")[0], email=email,
                 password=generate_password_hash("Test1234!"), status=status)
        db.session.add(u)
    u.status = status
    db.session.commit()
    return u.id


def _as(client, user_id, email, entity_id=None):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user_id
        sess["user_email"] = email
        sess["lang"] = "fr"
        if entity_id is not None:
            sess["active_entity_id"] = entity_id


@pytest.fixture(scope="module")
def monde(app, ids):
    """Deux cartos communes, une privée, des propositions dans tous les états."""
    from Code.extensions import db
    from Code.models.models import CartoChangeRequest, Entity

    with app.app_context():
        coord = _mk_user("t86.coord@devoptiq.com", "coordinateur")
        champion = _mk_user("t86.champion@devoptiq.com", "champion")
        auteur = _mk_user("t86.auteur@devoptiq.com", "champion")
        simple = _mk_user("t86.user@devoptiq.com", "user")

        def carto(nom, commune):
            e = Entity.query.filter_by(name=nom).first()
            if e is None:
                e = Entity(name=nom, owner_id=coord)
                db.session.add(e)
            e.owner_id = coord
            e.is_shared = commune
            e.optiqcarto_data = json.dumps(DIAG, ensure_ascii=False)
            db.session.commit()
            return e.id

        ea = carto("T86 Carto A", True)
        eb = carto("T86 Carto B", True)
        ep = carto("T86 Carto privée", False)

        def proposition(entity_id, author, status="pending"):
            cr = CartoChangeRequest(
                entity_id=entity_id, author_id=author, status=status,
                title=f"T86 prop {entity_id} {status}",
                diagram=json.dumps(_propose(DIAG), ensure_ascii=False),
                base_diagram=json.dumps(DIAG, ensure_ascii=False))
            db.session.add(cr)
            db.session.commit()
            return cr.id

        m = {
            "coord": coord, "champion": champion, "auteur": auteur, "simple": simple,
            "ea": ea, "eb": eb, "ep": ep,
            "p_a": proposition(ea, auteur),
            "p_b": proposition(eb, auteur),
            "p_privee": proposition(ep, auteur),
            "p_mienne": proposition(ea, coord),
            "p_close": proposition(ea, auteur, status="approved"),
        }
    yield m

    with app.app_context():
        from Code.models.models import CartoChangeRequest, Entity
        CartoChangeRequest.query.filter(
            CartoChangeRequest.entity_id.in_([m["ea"], m["eb"], m["ep"]])).delete(
            synchronize_session=False)
        for eid in (m["ea"], m["eb"], m["ep"]):
            e = db.session.get(Entity, eid)
            if e:
                # Une carto de test laissée COMMUNE devient le repli des fichiers
                # suivants : on la rend privée avant de l'effacer.
                e.is_shared = False
                db.session.delete(e)
        db.session.commit()


def _ids(rep):
    return {r["id"] for r in rep.get_json()["requests"]}


@pytest.fixture
def droits_d_origine(app):
    """Le tableau des droits tel qu'on l'a trouvé, rendu à la fin du test."""
    from Code.extensions import db
    from Code.models.models import AppSetting
    from Code.permissions import CLE_DROITS
    with app.app_context():
        row = db.session.get(AppSetting, CLE_DROITS)
        avant = row.value if row else None
    yield
    with app.app_context():
        row = db.session.get(AppSetting, CLE_DROITS)
        if avant is None:
            if row is not None:
                db.session.delete(row)
        else:
            row.value = avant
        db.session.commit()


# ══════════════════════════════════════════════════════════════════════
#  1 · Examiner depuis la page Carte, toutes cartos confondues
# ══════════════════════════════════════════════════════════════════════
class TestAExaminer:

    def test_le_coordinateur_voit_les_propositions_de_toutes_les_cartos(self, client, monde, ids):
        # ⚠️ Carto active = une TROISIÈME carto : c'est précisément le cas qui
        # échappait (on ne voyait que la carto active).
        _as(client, monde["coord"], "t86.coord@devoptiq.com", entity_id=ids["entity_id"])
        rep = client.get("/cartography/api/changes/a_examiner")
        assert rep.status_code == 200
        vus = _ids(rep)
        assert {monde["p_a"], monde["p_b"]} <= vus
        corps = rep.get_json()
        assert corps["n"] == len(corps["requests"])
        assert corps["cartos"] >= 2

    def test_ni_les_siennes_ni_les_closes_ni_une_carto_privee(self, client, monde):
        _as(client, monde["coord"], "t86.coord@devoptiq.com")
        vus = _ids(client.get("/cartography/api/changes/a_examiner"))
        assert monde["p_mienne"] not in vus          # on ne s'alerte pas soi-même
        assert monde["p_close"] not in vus           # déjà tranchée
        assert monde["p_privee"] not in vus          # une carto privée ne s'arbitre pas

    @pytest.mark.parametrize("qui", ["champion", "simple"])
    def test_qui_ne_valide_pas_n_a_rien_a_examiner(self, client, monde, qui):
        mail = {"champion": "t86.champion@devoptiq.com", "simple": "t86.user@devoptiq.com"}[qui]
        _as(client, monde[qui], mail)
        corps = client.get("/cartography/api/changes/a_examiner").get_json()
        assert corps["n"] == 0 and corps["requests"] == []

    def test_le_bandeau_de_la_page_carte_pour_qui_valide(self, client, monde):
        _as(client, monde["coord"], "t86.coord@devoptiq.com", entity_id=monde["ea"])
        html = client.get("/activities/map").get_data(as_text=True)
        assert 'id="cex-bandeau"' in html
        assert 'id="cex"' in html                     # la fenêtre d'examen
        assert "carto_examen.js" in html

    def test_pas_de_bandeau_pour_qui_ne_valide_pas(self, client, monde):
        _as(client, monde["champion"], "t86.champion@devoptiq.com", entity_id=monde["ea"])
        html = client.get("/activities/map").get_data(as_text=True)
        assert 'id="cex-bandeau"' not in html
        assert "carto_examen.js" not in html

    def test_pas_de_bandeau_quand_rien_n_attend(self, client, monde, monkeypatch):
        # Un bandeau d'alerte qui s'affiche à vide cesse d'être lu.
        import Code.routes.carto_sharing as cs
        monkeypatch.setattr(cs, "propositions_a_examiner", lambda user: [])
        _as(client, monde["coord"], "t86.coord@devoptiq.com", entity_id=monde["ea"])
        html = client.get("/activities/map").get_data(as_text=True)
        assert 'id="cex-bandeau"' not in html

    def test_le_detail_dit_si_la_carto_a_bouge_depuis_le_depot(self, app, client, monde):
        from Code.extensions import db
        from Code.models.models import Entity
        _as(client, monde["coord"], "t86.coord@devoptiq.com")
        assert client.get(f"/cartography/api/changes/{monde['p_b']}").get_json()["since"] is None

        with app.app_context():
            e = db.session.get(Entity, monde["eb"])
            d = json.loads(e.optiqcarto_data)
            d["shapes"][1]["x"] += 300           # quelqu'un a déplacé une activité
            e.optiqcarto_data = json.dumps(d)
            db.session.commit()
        try:
            since = client.get(f"/cartography/api/changes/{monde['p_b']}").get_json()["since"]
            assert since is not None and since["moved"] == ["T86 Aval"]
        finally:
            with app.app_context():
                e = db.session.get(Entity, monde["eb"])
                e.optiqcarto_data = json.dumps(DIAG, ensure_ascii=False)
                db.session.commit()

    def test_un_simple_reenregistrement_n_alerte_pas(self, app, client, monde):
        # Le texte du JSON change (ordre des clés, espaces), la carto non.
        from Code.extensions import db
        from Code.models.models import Entity
        with app.app_context():
            e = db.session.get(Entity, monde["eb"])
            e.optiqcarto_data = json.dumps(json.loads(e.optiqcarto_data), indent=2, sort_keys=True)
            db.session.commit()
        _as(client, monde["coord"], "t86.coord@devoptiq.com")
        assert client.get(f"/cartography/api/changes/{monde['p_b']}").get_json()["since"] is None

    def test_les_propositions_ont_quitte_la_page_rh(self, client, monde):
        _as(client, monde["coord"], "t86.coord@devoptiq.com", entity_id=monde["ea"])
        html = client.get("/gestion_rh/").get_data(as_text=True)
        assert "bloc-propositions" not in html
        assert "propositions" not in client.get("/gestion_rh/api/tableau").get_json()


class TestLeTableauDesDroitsDecide:
    """Les lignes « valider » et « enregistrer directement » ne décidaient de rien."""

    def test_confier_l_examen_au_champion_lui_ouvre_le_bandeau(self, app, client, monde,
                                                                droits_d_origine):
        from Code.permissions import droits_effectifs, enregistrer_droits
        with app.app_context():
            table = droits_effectifs()
            table["review_carto"]["champion"] = True
            enregistrer_droits(table)
        _as(client, monde["champion"], "t86.champion@devoptiq.com")
        vus = _ids(client.get("/cartography/api/changes/a_examiner"))
        assert {monde["p_a"], monde["p_b"]} <= vus

    def test_retirer_l_examen_au_coordinateur_le_lui_retire(self, app, client, monde,
                                                             droits_d_origine):
        from Code.permissions import droits_effectifs, enregistrer_droits
        with app.app_context():
            table = droits_effectifs()
            table["review_carto"]["coordinateur"] = False
            enregistrer_droits(table)
        _as(client, monde["coord"], "t86.coord@devoptiq.com")
        assert client.get("/cartography/api/changes/a_examiner").get_json()["n"] == 0
        rep = client.post(f"/cartography/api/changes/{monde['p_a']}/approve", json={})
        assert rep.status_code == 403

    def test_retirer_l_enregistrement_direct_fait_proposer_le_coordinateur(
            self, app, monde, droits_d_origine):
        from Code.carto_access import can_edit, must_propose
        from Code.extensions import db
        from Code.models.models import Entity, User
        from Code.permissions import droits_effectifs, enregistrer_droits
        with app.app_context():
            coord = db.session.get(User, monde["coord"])
            ent = db.session.get(Entity, monde["ea"])
            assert can_edit(ent, coord) is True
            table = droits_effectifs()
            table["edit_carto"]["coordinateur"] = False
            enregistrer_droits(table)
            assert can_edit(ent, coord) is False
            assert must_propose(ent, coord) is True


# ══════════════════════════════════════════════════════════════════════
#  2 · Le tableau global des compétences (page RH)
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def equipe(app, monde):
    """Deux cartos communes, trois rôles, deux personnes, des notes de tout
    genre — dont une auto-évaluation qui ne doit JAMAIS compter."""
    from datetime import datetime, timedelta

    from Code.extensions import db
    from Code.models.models import (Activities, CompetencyEvaluation, Data, Link, Role,
                                    UserRole, activity_roles)

    with app.app_context():
        u1 = _mk_user("t86.u1@devoptiq.com", "user", prenom="Alix")
        u2 = _mk_user("t86.u2@devoptiq.com", "user", prenom="Basile")
        ea, eb = monde["ea"], monde["eb"]

        def role(nom, eid):
            r = Role(name=nom, entity_id=eid)
            db.session.add(r)
            db.session.commit()
            return r.id

        ra1, ra_vide, ra_sans = role("T86 Méthodes", ea), role("T86 Sans activité", ea), role("T86 Sans titulaire", ea)
        rb1 = role("T86 Qualité", eb)

        def activite(nom, eid):
            a = Activities(name=nom, entity_id=eid)
            db.session.add(a)
            db.session.commit()
            return a.id

        a1, a2, a3 = activite("T86 Chiffrer", ea), activite("T86 Préparer", ea), activite("T86 Contrôler", eb)
        for act, rid, req in ((a1, ra1, 3), (a2, ra1, None), (a3, rb1, 2), (a1, ra_sans, 2)):
            db.session.execute(activity_roles.insert().values(
                activity_id=act, role_id=rid, status="Garant", required_mastery_level=req))

        d1 = Data(entity_id=ea, name="T86 Offre", type="flux", producer_activity_id=a1, semantic_nature="RESULT")
        d2 = Data(entity_id=ea, name="T86 Planning", type="flux", producer_activity_id=a1, semantic_nature="RESULT")
        # Un résultat « hérité » : visé par un lien sortant, sans producteur.
        d3 = Data(entity_id=eb, name="T86 Rapport", type="flux", semantic_nature="RESULT")
        db.session.add_all([d1, d2, d3])
        db.session.commit()
        db.session.add(Link(entity_id=eb, source_activity_id=a3, target_data_id=d3.id, type="flux"))

        for uid, rid in ((u1, ra1), (u1, rb1), (u2, ra1)):
            db.session.add(UserRole(user_id=uid, role_id=rid))

        t0 = datetime(2026, 9, 1)

        def note(uid, act, did, lvl, qui="2", quand=t0):
            db.session.add(CompetencyEvaluation(
                user_id=uid, activity_id=act, item_type="activity_results", item_id=did,
                eval_number=qui, note="", mastery_level=lvl, evaluated_at=quand))

        note(u1, a1, d1.id, 3)
        note(u1, a1, d2.id, 2)                    # a1 : min(3, 2) = 2 < requis 3 → écart
        note(u1, a1, d1.id, 4, qui="0")           # auto-évaluation : ne compte JAMAIS
        note(u1, a3, d3.id, 2)                    # a3 : tenu
        note(u2, a1, d1.id, 1, quand=t0)          # la plus ANCIENNE…
        note(u2, a1, d1.id, 3, qui="1", quand=t0 + timedelta(days=3))   # …la récente fait foi
        db.session.commit()                       # u2 : d2 non évalué → à évaluer

        e = {"u1": u1, "u2": u2, "ra1": ra1, "ra_vide": ra_vide, "ra_sans": ra_sans,
             "rb1": rb1, "a1": a1, "a2": a2, "a3": a3, "d": [d1.id, d2.id, d3.id]}
    yield e

    with app.app_context():
        acts = [e["a1"], e["a2"], e["a3"]]
        CompetencyEvaluation.query.filter(CompetencyEvaluation.activity_id.in_(acts)).delete(
            synchronize_session=False)
        Link.query.filter(Link.source_activity_id.in_(acts)).delete(synchronize_session=False)
        # ⚠️ Et les sorties que `/mastery/synthese` a MATÉRIALISÉES en passant
        # (`get_activity_outputs` écrit) : elles pointent sur nos activités.
        Data.query.filter(db.or_(Data.id.in_(e["d"]),
                                 Data.producer_activity_id.in_(acts))).delete(
            synchronize_session=False)
        roles = [e["ra1"], e["ra_vide"], e["ra_sans"], e["rb1"]]
        UserRole.query.filter(UserRole.role_id.in_(roles)).delete(synchronize_session=False)
        db.session.execute(activity_roles.delete().where(activity_roles.c.activity_id.in_(acts)))
        Activities.query.filter(Activities.id.in_(acts)).delete(synchronize_session=False)
        Role.query.filter(Role.id.in_(roles)).delete(synchronize_session=False)
        db.session.commit()


def _tableau(client, monde, **params):
    _as(client, monde["coord"], "t86.coord@devoptiq.com")
    q = "&".join(f"{k}={v}" for k, v in params.items())
    rep = client.get("/gestion_rh/api/competences" + (f"?{q}" if q else ""))
    assert rep.status_code == 200, rep.get_data(as_text=True)
    return rep.get_json()


def _personne(t, uid):
    return next((p for p in t["personnes"] if p["id"] == uid), None)


class TestTableauGlobal:

    def test_memes_chiffres_que_la_page_competences(self, client, monde, equipe):
        """⚠️ LE contrôle : deux écrans qui comptent avec deux codes finissent
        par afficher deux chiffres. Rôle par rôle, champ par champ."""
        t = _tableau(client, monde)
        for uid in (equipe["u1"], equipe["u2"]):
            synth = client.get(f"/mastery/synthese/{uid}").get_json()
            ligne = _personne(t, uid)
            assert ligne is not None
            for r in synth["roles"]:
                if not r["n_activities"]:
                    continue
                g = ligne["roles"][str(r["role_id"])]
                for champ in ("level", "required_level", "color", "counts", "n_activities",
                              "n_evaluated", "n_gap", "couverture", "gap"):
                    assert g[champ] == r[champ], (uid, r["role_name"], champ)
            assert ligne["couverture"] == synth["couverture"]

    def test_ce_que_dit_chaque_case(self, client, monde, equipe):
        t = _tableau(client, monde)
        u1, u2 = _personne(t, equipe["u1"]), _personne(t, equipe["u2"])
        meth = u1["roles"][str(equipe["ra1"])]
        # a1 à 2 (sous le requis 3) et a2 sans résultat : le rôle n'a de niveau
        # que si TOUT ce qui s'évalue l'est — ici oui, donc min = 2.
        assert meth["level"] == 2 and meth["color"] == "orange"
        assert meth["counts"] == {"held": 0, "gap": 1, "todo": 0, "setup": 1}
        # L'auto-évaluation à 4 n'a rien changé, et la note la plus RÉCENTE fait foi.
        assert u1["roles"][str(equipe["rb1"])]["color"] == "green"
        assert u2["roles"][str(equipe["ra1"])]["counts"]["todo"] == 1
        assert u2["roles"][str(equipe["ra1"])]["level"] is None       # NULL ≠ 0

    def test_les_colonnes_sont_les_roles_de_l_entreprise(self, client, monde, equipe):
        """Sans filtre de carto, une colonne par rôle tenu — les rôles ne se
        rangent plus par carto, ils sont communs."""
        t = _tableau(client, monde)
        tous = {r["id"] for g in t["colonnes"] for r in g["roles"]}
        assert equipe["ra1"] in tous and equipe["rb1"] in tous
        assert equipe["ra_vide"] not in tous       # rien à évaluer
        assert equipe["ra_sans"] not in tous       # personne ne le tient

    def test_le_filtre_par_carto(self, client, monde, equipe):
        t = _tableau(client, monde, entity_id=monde["eb"])
        assert t["entity_id"] == monde["eb"]
        assert [g["carto_id"] for g in t["colonnes"]] == [monde["eb"]]
        assert _personne(t, equipe["u2"]) is None          # ne tient rien sur B
        assert set(_personne(t, equipe["u1"])["roles"]) == {str(equipe["rb1"])}

    def test_une_carto_hors_de_portee_est_ignoree(self, client, monde, equipe):
        from Code.extensions import db
        from Code.models.models import Entity
        # Une carto privée d'un AUTRE compte : l'identifiant vient du navigateur.
        with client.application.app_context():
            autre = Entity(name="T86 Hors portée", owner_id=monde["simple"], is_shared=False)
            db.session.add(autre)
            db.session.commit()
            autre_id = autre.id
        try:
            t = _tableau(client, monde, entity_id=autre_id)
            assert t["entity_id"] is None
            assert autre_id not in {c["id"] for c in t["cartos"]}
        finally:
            with client.application.app_context():
                db.session.delete(db.session.get(Entity, autre_id))
                db.session.commit()

    def test_reserve_a_qui_ouvre_la_page_rh(self, client, monde, equipe):
        _as(client, monde["simple"], "t86.user@devoptiq.com")
        assert client.get("/gestion_rh/api/competences").status_code == 403

    def test_le_cout_ne_grandit_pas_avec_l_effectif(self, app, monde, equipe):
        """Soixante personnes ne doivent pas coûter soixante fois plus qu'une.
        On compte des REQUÊTES : sur SQLite tout est dans le processus, le
        défaut serait invisible au chronomètre."""
        from sqlalchemy import event

        from Code.competences_globales import tableau_global
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation, User, UserRole

        def compter():
            n = [0]

            def top(*_a, **_k):
                n[0] += 1
            with app.test_request_context():
                from flask import session
                session["user_id"] = monde["coord"]
                session["lang"] = "fr"
                moi = db.session.get(User, monde["coord"])
                event.listen(db.engine, "before_cursor_execute", top)
                try:
                    tableau_global(moi)
                finally:
                    event.remove(db.engine, "before_cursor_execute", top)
            return n[0]

        avant = compter()
        with app.app_context():
            nouveaux = []
            for i in range(6):
                uid = _mk_user(f"t86.renfort{i}@devoptiq.com", "user")
                nouveaux.append(uid)
                db.session.add(UserRole(user_id=uid, role_id=equipe["ra1"]))
                db.session.add(CompetencyEvaluation(
                    user_id=uid, activity_id=equipe["a1"], item_type="activity_results",
                    item_id=equipe["d"][0], eval_number="2", note="", mastery_level=2))
            db.session.commit()
        try:
            assert compter() == avant
        finally:
            with app.app_context():
                CompetencyEvaluation.query.filter(
                    CompetencyEvaluation.user_id.in_(nouveaux)).delete(synchronize_session=False)
                UserRole.query.filter(UserRole.user_id.in_(nouveaux)).delete(
                    synchronize_session=False)
                User.query.filter(User.id.in_(nouveaux)).delete(synchronize_session=False)
                db.session.commit()

    def test_le_bloc_est_dans_la_page_rh(self, client, monde, equipe):
        _as(client, monde["coord"], "t86.coord@devoptiq.com", entity_id=monde["ea"])
        html = client.get("/gestion_rh/").get_data(as_text=True)
        assert 'id="bloc-competences"' in html
        assert "rh_competences.js" in html


# ══════════════════════════════════════════════════════════════════════
#  3 · Qui lit et note les compétences de tout le monde
# ══════════════════════════════════════════════════════════════════════
class TestQuiArbitreLesCompetences:
    """Le coordinateur, pas le champion : depuis les quatre paliers, le champion
    est celui qui PROPOSE sans valider."""

    def test_un_champion_ne_note_pas_quelqu_un_qu_il_n_encadre_pas(self, app, monde, equipe):
        from Code.competences_acces import peut_lire, peut_noter
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            champion = db.session.get(User, monde["champion"])
            assert peut_noter(champion, equipe["u1"], "2") == (False, "not_the_developer")
            assert peut_lire(champion, equipe["u1"]) is False

    def test_ni_ne_se_decerne_le_niveau_qui_fait_foi(self, app, monde):
        from Code.competences_acces import peut_noter
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            champion = db.session.get(User, monde["champion"])
            assert peut_noter(champion, champion.id, "2")[0] is False

    def test_le_coordinateur_lit_et_note_tout_le_monde(self, app, monde, equipe):
        from Code.competences_acces import peut_lire, peut_noter
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            coord = db.session.get(User, monde["coord"])
            assert peut_noter(coord, equipe["u1"], "2") == (True, "ok")
            assert peut_lire(coord, equipe["u1"]) is True

    def test_par_la_route_aussi(self, client, monde, equipe):
        _as(client, monde["champion"], "t86.champion@devoptiq.com")
        rep = client.post("/mastery/evaluate", json={
            "user_id": equipe["u1"], "activity_id": equipe["a1"], "data_id": equipe["d"][0],
            "evaluator": "2", "mastery_level": 4})
        assert rep.status_code == 403
        _as(client, monde["coord"], "t86.coord@devoptiq.com")
        assert client.get(f"/mastery/synthese/{equipe['u1']}").status_code == 200
