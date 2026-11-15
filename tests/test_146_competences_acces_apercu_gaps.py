# -*- coding: utf-8 -*-
"""Compétences — les branches restées dans l'ombre : accès, aperçu, synthèse.

Mesuré au banc (couverture de lignes, 15/11/2026) : toute la suite passait,
mais une poignée de gardes n'étaient jamais franchies —

  • `competences_acces` : les identifiants absents (`None`), l'évaluateur
    inconnu, le refus « pas son développeur » sans rôle ;
  • `apercu_competences` : les lectures en bloc à vide, le collaborateur
    introuvable (404 et non 500), le collaborateur sans rôle ;
  • `competences_globales` : les références à vide, les comptes lisibles d'un
    simple utilisateur ;
  • `mastery` : la synthèse d'un compte inexistant, l'auto-évaluation qui
    remonte jusqu'au niveau du rôle, le niveau requis posé sans session.

Chaque cas pose son PROPRE décor et le retire : la base est commune à toute
la suite (portée session).
"""
import json
import uuid

import pytest

from Code.extensions import db

_N = [0]


def _mail(prefixe):
    _N[0] += 1
    return "%s.t146.%d@test" % (prefixe, _N[0])


@pytest.fixture
def comptes(app):
    """Trois comptes simples : un développeur, son collaborateur (lien GLOBAL),
    et un tiers qui n'encadre personne."""
    from Code.models.models import User
    from Code.security import hash_password
    with app.app_context():
        dev = User(first_name="Dev", last_name="T146", email=_mail("dev"),
                   password=hash_password("Test1234!"), status="user")
        db.session.add(dev)
        db.session.commit()
        col = User(first_name="Col", last_name="T146", email=_mail("col"),
                   password=hash_password("Test1234!"), status="user",
                   manager_id=dev.id)
        tiers = User(first_name="Tiers", last_name="T146", email=_mail("tiers"),
                     password=hash_password("Test1234!"), status="user")
        db.session.add_all([col, tiers])
        db.session.commit()
        info = {"dev": dev.id, "col": col.id, "tiers": tiers.id}
    yield info
    with app.app_context():
        from Code.models.models import UserRole
        for uid in (info["col"], info["tiers"], info["dev"]):
            UserRole.query.filter_by(user_id=uid).delete()
            u = User.query.get(uid)
            if u is not None:
                u.manager_id = None
        db.session.commit()
        for uid in (info["col"], info["tiers"], info["dev"]):
            u = User.query.get(uid)
            if u is not None:
                db.session.delete(u)
        db.session.commit()


@pytest.fixture
def connecte_comme(auth_client):
    """Change l'identité de la session, et la RESTAURE en sortant : le client
    est partagé par toute la suite."""
    with auth_client.session_transaction() as sess:
        avant = sess.get("user_id")

    def _poser(uid):
        with auth_client.session_transaction() as sess:
            sess["user_id"] = uid
        return auth_client

    yield _poser
    with auth_client.session_transaction() as sess:
        if avant is None:
            sess.pop("user_id", None)
        else:
            sess["user_id"] = avant


# ════════════════════════════════════════════════════════════════════════
#  competences_acces — les gardes sur les identifiants absents
# ════════════════════════════════════════════════════════════════════════

class TestReglesDAcces:

    def test_statut_eleve_refuse_un_acteur_absent(self, app):
        from Code.competences_acces import _statut_eleve
        with app.app_context():
            assert _statut_eleve(None) is False

    def test_encadre_refuse_un_identifiant_absent(self, app, comptes):
        from Code.competences_acces import encadre
        with app.app_context():
            assert encadre(None, comptes["col"]) is False
            assert encadre(comptes["dev"], None) is False
            # Contrôle : le lien global existe bien, c'est le None qui refuse.
            assert encadre(comptes["dev"], comptes["col"]) is True

    def test_encadre_pour_role_refuse_un_role_absent(self, app, comptes):
        from Code.competences_acces import encadre_pour_role
        with app.app_context():
            assert encadre_pour_role(comptes["dev"], comptes["col"], None) is False
            assert encadre_pour_role(None, comptes["col"], 1) is False

    def test_roles_suivis_sans_acteur_est_une_liste_VIDE_pas_None(self, app, comptes):
        """`None` voudrait dire « aucune restriction » : un anonyme n'en a
        surtout pas."""
        from Code.competences_acces import roles_suivis
        with app.app_context():
            assert roles_suivis(None, comptes["col"]) == []

    def test_peut_noter_refuse_un_evaluateur_inconnu(self, app, comptes):
        from Code.competences_acces import peut_noter
        from Code.models.models import User
        with app.app_context():
            dev = User.query.get(comptes["dev"])
            assert peut_noter(dev, comptes["col"], "3") == (False, "unknown_evaluator")

    def test_peut_noter_sans_role_refuse_qui_n_encadre_pas(self, app, comptes):
        from Code.competences_acces import peut_noter
        from Code.models.models import User
        with app.app_context():
            tiers = User.query.get(comptes["tiers"])
            assert peut_noter(tiers, comptes["col"], "2") == (False, "not_the_developer")

    def test_peut_noter_sans_role_accepte_le_lien_global(self, app, comptes):
        from Code.competences_acces import peut_noter
        from Code.models.models import User
        with app.app_context():
            dev = User.query.get(comptes["dev"])
            assert peut_noter(dev, comptes["col"], "2") == (True, "ok")


# ════════════════════════════════════════════════════════════════════════
#  competences_globales — les lectures en bloc
# ════════════════════════════════════════════════════════════════════════

class TestReferencesEtLisibles:

    def test_references_a_vide_ne_lit_rien(self, app, ids):
        from Code.competences_globales import _references
        with app.app_context():
            assert _references([], [ids["activity_id"]]) == {}
            assert _references([ids["user_id"]], []) == {}

    def test_un_simple_utilisateur_lit_lui_meme_et_ceux_qu_il_encadre(
            self, app, comptes, ids):
        from Code.competences_globales import _lisibles
        from Code.models.models import Role, User, UserRole
        with app.app_context():
            r = Role(name="T146 Lisibles %s" % uuid.uuid4().hex[:8], entity_id=ids["entity_id"])
            db.session.add(r)
            db.session.commit()
            # Le tiers devient développeur PAR RÔLE du collaborateur.
            db.session.add(UserRole(user_id=comptes["col"], role_id=r.id,
                                    manager_id=comptes["tiers"]))
            db.session.commit()
            try:
                dev = User.query.get(comptes["dev"])
                tiers = User.query.get(comptes["tiers"])
                assert _lisibles(dev) == {comptes["dev"], comptes["col"]}
                assert _lisibles(tiers) == {comptes["tiers"], comptes["col"]}
            finally:
                UserRole.query.filter_by(role_id=r.id).delete()
                db.session.delete(Role.query.get(r.id))
                db.session.commit()

    def test_un_administrateur_n_a_pas_de_restriction(self, app, ids):
        from Code.competences_globales import _lisibles
        from Code.models.models import User
        with app.app_context():
            assert _lisibles(User.query.get(ids["user_id"])) is None


# ════════════════════════════════════════════════════════════════════════
#  apercu_competences — vide, introuvable, sans rôle
# ════════════════════════════════════════════════════════════════════════

class TestApercuGaps:

    def test_les_lectures_en_bloc_a_vide_ne_font_aucune_requete(self, app, ids):
        from sqlalchemy import event
        from Code.apercu_competences import _paliers_en_bloc, _requis_en_bloc
        with app.app_context():
            n = [0]

            def compter(*a, **k):
                n[0] += 1
            event.listen(db.engine, "before_cursor_execute", compter)
            try:
                assert dict(_paliers_en_bloc(ids["user_id"], [])) == {}
                assert _requis_en_bloc([]) == {}
            finally:
                event.remove(db.engine, "before_cursor_execute", compter)
            assert n[0] == 0

    def test_apercu_d_un_compte_inexistant_rend_None(self, app, ids):
        from Code.apercu_competences import apercu
        from Code.models.models import User
        with app.app_context():
            assert apercu(User.query.get(ids["user_id"]), 99999999) is None

    def test_la_route_rend_404_pour_un_compte_inexistant(self, auth_client):
        """Le compte du seed est administrateur : il a le droit de lire, et
        c'est donc bien l'absence du compte qui doit répondre — pas un 500."""
        r = auth_client.get("/mastery/apercu/99999999")
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "user_not_found"

    def test_un_collaborateur_SANS_role_a_un_apercu_vide_et_sans_verdict(
            self, auth_client, comptes):
        r = auth_client.get("/mastery/apercu/%d" % comptes["tiers"])
        assert r.status_code == 200
        d = json.loads(r.data)
        assert d["n_roles"] == 0
        assert d["activites"] == []
        assert d["niveau"] is None and d["plus_bas"] is None
        assert d["compte"] == {"held": 0, "gap": 0, "todo": 0, "setup": 0}
        assert d["user_name"] == "Tiers T146"

    def test_un_tiers_ne_lit_pas_l_apercu_d_un_autre(self, connecte_comme, comptes):
        c = connecte_comme(comptes["tiers"])
        r = c.get("/mastery/apercu/%d" % comptes["col"])
        assert r.status_code == 403


# ════════════════════════════════════════════════════════════════════════
#  mastery — synthèse et niveau requis
# ════════════════════════════════════════════════════════════════════════

@pytest.fixture
def role_avec_sortie(app, ids, comptes):
    """Le collaborateur tient un rôle portant UNE activité à UNE sortie."""
    from Code.models.models import (Activities, CompetencyEvaluation, Link, Role,
                                    UserRole, activity_roles)
    with app.app_context():
        n = uuid.uuid4().hex[:8]
        r = Role(name="T146 Synthese %s" % n, entity_id=ids["entity_id"])
        a = Activities(name="T146 Agir %s" % n, entity_id=ids["entity_id"])
        aval = Activities(name="T146 Aval %s" % n, entity_id=ids["entity_id"])
        db.session.add_all([r, a, aval])
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=a.id, role_id=r.id, status="Garant",
            required_mastery_level=2))
        db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=a.id,
                            target_activity_id=aval.id, description="Livrable %s" % n,
                            type="flux"))
        db.session.add(UserRole(user_id=comptes["col"], role_id=r.id))
        db.session.commit()
        from Code.routes.qualify_outputs import get_activity_outputs
        sortie = get_activity_outputs(a.id)[0]
        info = {"role": r.id, "act": a.id, "aval": aval.id, "data": sortie.id}
    yield info
    with app.app_context():
        CompetencyEvaluation.query.filter_by(user_id=comptes["col"]).delete()
        UserRole.query.filter_by(role_id=info["role"]).delete()
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.role_id == info["role"]))
        Link.query.filter_by(source_activity_id=info["act"]).delete()
        db.session.commit()
        for modele, pk in ((Role, info["role"]), (Activities, info["act"]),
                           (Activities, info["aval"])):
            obj = modele.query.get(pk)
            if obj is not None:
                db.session.delete(obj)
        try:
            db.session.commit()
        except Exception:
            # Une sortie matérialisée peut encore tenir l'activité : le nom
            # aléatoire suffit alors à éviter toute collision.
            db.session.rollback()


class TestSyntheseEtRequisGaps:

    def test_synthese_d_un_compte_inexistant_rend_404(self, auth_client):
        r = auth_client.get("/mastery/synthese/99999999")
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "user_not_found"

    def test_self_level_sans_auto_evaluation_est_None(self, app, comptes, role_avec_sortie):
        from Code.routes.mastery import _self_level
        with app.app_context():
            assert _self_level(comptes["col"], role_avec_sortie["act"],
                               role_avec_sortie["data"]) is None

    def test_l_auto_evaluation_remonte_au_role_SANS_devenir_le_niveau(
            self, app, auth_client, comptes, role_avec_sortie):
        """Le repère du collaborateur s'affiche à côté ; le niveau qui fait foi
        reste NULL tant qu'aucun développeur n'a noté."""
        from Code.models.models import CompetencyEvaluation
        from Code.routes.mastery import _self_level
        with app.app_context():
            db.session.add(CompetencyEvaluation(
                user_id=comptes["col"], activity_id=role_avec_sortie["act"],
                item_type="activity_results", item_id=role_avec_sortie["data"],
                eval_number="0", note="", mastery_level=3))
            db.session.commit()
            assert _self_level(comptes["col"], role_avec_sortie["act"],
                               role_avec_sortie["data"]) == 3
        r = auth_client.get("/mastery/synthese/%d" % comptes["col"])
        assert r.status_code == 200
        d = json.loads(r.data)
        role = next(x for x in d["roles"] if x["role_id"] == role_avec_sortie["role"])
        assert role["self_level"] == 3
        assert role["level"] is None
        ligne = next(p for p in d["profil"] if p["activity_id"] == role_avec_sortie["act"])
        assert ligne["self_level"] == 3 and ligne["demonstrated_level"] is None

    def test_poser_le_requis_sans_session_est_refuse(self, app, role_avec_sortie):
        c = app.test_client()
        r = c.post("/mastery/required", json={
            "activity_id": role_avec_sortie["act"], "role_id": role_avec_sortie["role"],
            "required_mastery_level": 3})
        assert r.status_code in (302, 401, 403)
        from Code.models.models import activity_roles
        with app.app_context():
            ligne = db.session.execute(activity_roles.select().where(
                (activity_roles.c.activity_id == role_avec_sortie["act"])
                & (activity_roles.c.role_id == role_avec_sortie["role"]))).first()
            assert ligne.required_mastery_level == 2


# ════════════════════════════════════════════════════════════════════════
#  paliers_routes — la première mesure et les sessions introuvables
# ════════════════════════════════════════════════════════════════════════

class TestPremiereMesureGaps:
    """Le compte du seed est administrateur : il passe toutes les portes, et
    c'est donc la DONNÉE qui doit répondre dans chacun de ces cas."""

    def _post(self, client, **corps):
        return client.post("/paliers/premiere", json=corps)

    def test_une_sortie_inconnue_rend_404(self, auth_client, comptes, role_avec_sortie):
        r = self._post(auth_client, user_id=comptes["col"], data_id=99999999,
                       role_id=role_avec_sortie["role"], valeur=10, mesure=8)
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "unknown_output"

    def test_un_role_qui_ne_porte_pas_l_activite_rend_404(
            self, app, auth_client, ids, comptes, role_avec_sortie):
        from Code.models.models import Role
        with app.app_context():
            autre = Role(name="T146 Etranger %s" % uuid.uuid4().hex[:8],
                         entity_id=ids["entity_id"])
            db.session.add(autre)
            db.session.commit()
            autre_id = autre.id
        try:
            r = self._post(auth_client, user_id=comptes["col"],
                           data_id=role_avec_sortie["data"], role_id=autre_id,
                           valeur=10, mesure=8)
            assert r.status_code == 404
            assert json.loads(r.data)["error"] == "association_not_found"
        finally:
            with app.app_context():
                db.session.delete(Role.query.get(autre_id))
                db.session.commit()

    def test_une_norme_illisible_est_refusee_400(self, auth_client, comptes, role_avec_sortie):
        r = self._post(auth_client, user_id=comptes["col"],
                       data_id=role_avec_sortie["data"], role_id=role_avec_sortie["role"],
                       valeur="beaucoup", mesure=8)
        assert r.status_code == 400
        assert json.loads(r.data)["error"] == "invalid_value"

    def test_une_mesure_illisible_ne_laisse_PAS_la_norme_ecrite(
            self, app, auth_client, comptes, role_avec_sortie):
        """UNE transaction : une norme posée sans sa mesure ferait basculer la
        sortie en régime mesuré sans rien à y lire."""
        from Code.models.models import Data
        r = self._post(auth_client, user_id=comptes["col"],
                       data_id=role_avec_sortie["data"], role_id=role_avec_sortie["role"],
                       valeur=48, sens="moins", unite="h", mesure="vite")
        assert r.status_code == 400
        assert json.loads(r.data)["error"] == "invalid_measure"
        with app.app_context():
            d = Data.query.get(role_avec_sortie["data"])
            db.session.refresh(d)
            assert d.norme_valeur is None


class TestSessionsIntrouvables:

    def test_le_detail_d_une_session_inconnue_rend_404(self, auth_client):
        r = auth_client.get("/paliers/session/99999999/detail")
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "unknown"

    def test_cloturer_une_session_inconnue_rend_404(self, auth_client):
        r = auth_client.post("/paliers/session/99999999/cloturer", json={})
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "unknown"
