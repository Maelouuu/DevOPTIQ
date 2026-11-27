# -*- coding: utf-8 -*-
"""LE SOCLE, ce que l'écran ne montre pas : les refus de chaque transition
appelée en direct, la file d'examen du coordinateur, l'annonce dans la
fenêtre de bienvenue, et les replis qui empêchent un panneau illisible
d'emporter la page Activités.

⚠️ Ce fichier se donne SES cartos, toutes avec un `owner_id` : une entité de
test sans propriétaire est lisible par tout le monde et devient le repli des
fichiers suivants. Chaque test range ce qu'il a posé.
"""
from datetime import datetime, timedelta

import pytest

from Code.extensions import db

_N = [0]


# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def decor(app):
    """Un coordinateur, un champion, deux cartos COMMUNES et une PRIVÉE."""
    from Code.models.models import Entity, User
    from Code.security import hash_password

    _N[0] += 1
    n = _N[0]
    with app.app_context():
        faire = lambda r, s: User(
            first_name=r.capitalize(), last_name="SX%d" % n,
            email="%s%d@soclex.test" % (r, n), password=hash_password("x"),
            status=s)
        coord = faire("coord", "coordinateur")
        champ = faire("champ", "champion")
        db.session.add_all([coord, champ])
        db.session.commit()

        a = Entity(name="Socle X A %d" % n, owner_id=coord.id,
                   is_shared=True, socle_etat="saisie")
        b = Entity(name="Socle X B %d" % n, owner_id=coord.id,
                   is_shared=True, socle_etat="saisie")
        privee = Entity(name="Socle X P %d" % n, owner_id=coord.id,
                        is_shared=False, socle_etat="soumis")
        db.session.add_all([a, b, privee])
        db.session.commit()
        d = {"coord": coord.id, "champ": champ.id, "a": a.id, "b": b.id,
             "p": privee.id, "n": n}
    yield d
    with app.app_context():
        from Code.models.models import (Activities, EntityRoleAccess, Role,
                                        WelcomeSeen)
        ents = [d["a"], d["b"], d["p"]]
        EntityRoleAccess.query.filter(
            EntityRoleAccess.entity_id.in_(ents)).delete(
                synchronize_session=False)
        Role.query.filter(Role.entity_id.in_(ents)).delete(
            synchronize_session=False)
        Activities.query.filter(Activities.entity_id.in_(ents)).delete(
            synchronize_session=False)
        Entity.query.filter(Entity.id.in_(ents)).delete(
            synchronize_session=False)
        WelcomeSeen.query.filter(
            WelcomeSeen.user_id.in_([d["coord"], d["champ"]])).delete(
                synchronize_session=False)
        User.query.filter(User.id.in_([d["coord"], d["champ"]])).delete(
            synchronize_session=False)
        db.session.commit()


def _ent(eid):
    from Code.models.models import Entity
    return db.session.get(Entity, eid)


def _user(uid):
    from Code.models.models import User
    return db.session.get(User, uid)


def _poser(app, eid, **champs):
    with app.app_context():
        e = _ent(eid)
        for k, v in champs.items():
            setattr(e, k, v)
        db.session.commit()


# ══════════════════════════════════════════════════════════════════════════
class TestSocleTransitionsRefusees:
    """Les fonctions du socle, appelées sans passer par la route : le refus
    doit venir d'ELLES, pas seulement du contrôle d'accès en amont."""

    def test_soumettre_deux_fois_rend_deja_soumis(self, app, decor):
        from Code.socle_activites import soumettre
        _poser(app, decor["a"], socle_etat="soumis")
        with app.app_context():
            ok, code = soumettre(_ent(decor["a"]), _user(decor["champ"]))
            assert (ok, code) == (False, "deja_soumis")
            assert _ent(decor["a"]).socle_etat == "soumis"

    def test_soumettre_sans_entite_rend_pas_commune(self, app):
        from Code.socle_activites import soumettre
        with app.app_context():
            assert soumettre(None, None) == (False, "pas_commune")

    def test_valider_une_carto_privee_rend_pas_commune(self, app, decor):
        from Code.socle_activites import valider
        with app.app_context():
            ok, code = valider(_ent(decor["p"]), _user(decor["coord"]))
            assert (ok, code) == (False, "pas_commune")
            assert _ent(decor["p"]).socle_etat == "soumis"

    def test_valider_sans_entite_rend_pas_commune(self, app):
        from Code.socle_activites import valider
        with app.app_context():
            assert valider(None, None) == (False, "pas_commune")

    def test_valider_un_socle_deja_valide_rend_deja_valide(self, app, decor):
        from Code.socle_activites import valider
        _poser(app, decor["a"], socle_etat="valide", socle_retour="ancien")
        with app.app_context():
            ok, code = valider(_ent(decor["a"]), _user(decor["coord"]),
                               retour="nouveau")
            assert (ok, code) == (False, "deja_valide")
            # Le refus n'écrit rien : le mot de la validation reste l'ancien.
            assert _ent(decor["a"]).socle_retour == "ancien"

    def test_renvoyer_une_carto_privee_rend_pas_commune(self, app, decor):
        from Code.socle_activites import renvoyer
        with app.app_context():
            ok, code = renvoyer(_ent(decor["p"]), _user(decor["coord"]),
                                retour="à reprendre")
            assert (ok, code) == (False, "pas_commune")
            assert _ent(decor["p"]).socle_etat == "soumis"

    def test_renvoyer_sans_entite_rend_pas_commune(self, app):
        from Code.socle_activites import renvoyer
        with app.app_context():
            assert renvoyer(None, None, retour="x") == (False, "pas_commune")

    def test_etat_brut_inconnu_retombe_sur_saisie(self, app, decor):
        from Code.socle_activites import etat_brut
        with app.app_context():
            e = _ent(decor["a"])
            e.socle_etat = "farfelu"
            assert etat_brut(e) == "saisie"
            db.session.rollback()

    def test_etat_brut_sans_entite_est_valide(self):
        from Code.socle_activites import etat_brut
        assert etat_brut(None) == "valide"


# ══════════════════════════════════════════════════════════════════════════
class TestSocleFileDExamen:
    """`a_examiner` : les cartos dont le socle attend une décision."""

    def test_sans_compte_la_file_est_vide(self, app):
        from Code.socle_activites import a_examiner
        with app.app_context():
            assert a_examiner(None) == []

    def test_un_champion_n_examine_rien(self, app, decor):
        from Code.socle_activites import a_examiner
        _poser(app, decor["a"], socle_etat="soumis")
        with app.test_request_context():
            assert a_examiner(_user(decor["champ"])) == []

    def test_le_coordinateur_voit_ses_cartos_soumises_dans_l_ordre(self, app, decor):
        from Code.socle_activites import a_examiner
        maintenant = datetime.utcnow()
        _poser(app, decor["a"], socle_etat="soumis",
               socle_le=maintenant - timedelta(hours=1))
        _poser(app, decor["b"], socle_etat="soumis",
               socle_le=maintenant - timedelta(hours=3))
        with app.test_request_context():
            ids = [e.id for e in a_examiner(_user(decor["coord"]))]
        miens = [i for i in ids if i in (decor["a"], decor["b"], decor["p"])]
        # La plus ancienne soumission d'abord ; la privée n'y est jamais.
        assert miens == [decor["b"], decor["a"]]

    def test_une_carto_en_saisie_n_est_pas_dans_la_file(self, app, decor):
        from Code.socle_activites import a_examiner
        _poser(app, decor["a"], socle_etat="soumis", socle_le=datetime.utcnow())
        with app.test_request_context():
            ids = {e.id for e in a_examiner(_user(decor["coord"]))}
        assert decor["a"] in ids and decor["b"] not in ids


# ══════════════════════════════════════════════════════════════════════════
class TestBienvenueAnnonceLeSocle:
    """La fenêtre de bienvenue annonce au coordinateur les socles soumis."""

    def _attentes(self, app, uid):
        from Code import bienvenue
        with app.test_request_context():
            return {a["cle"]: a for a in bienvenue.attentes(_user(uid), "fr")}

    def test_le_coordinateur_voit_la_ligne_socle(self, app, decor):
        _poser(app, decor["a"], socle_etat="soumis", socle_le=datetime.utcnow())
        att = self._attentes(app, decor["coord"])
        assert "socle" in att
        assert att["socle"]["n"] >= 1
        assert att["socle"]["href"] == "/activities/view"
        assert att["socle"]["ton"] == "attention"

    def test_le_champion_ne_voit_pas_la_ligne_socle(self, app, decor):
        _poser(app, decor["a"], socle_etat="soumis", socle_le=datetime.utcnow())
        assert "socle" not in self._attentes(app, decor["champ"])

    def test_une_carto_privee_soumise_ne_compte_pas(self, app, decor):
        """La privée du décor est 'soumis' : elle ne doit pas gonfler le compte."""
        from Code.models.models import Entity
        with app.app_context():
            communes = (Entity.query
                        .filter(Entity.is_shared.is_(True),
                                Entity.socle_etat == "soumis").count())
        att = self._attentes(app, decor["coord"])
        assert att.get("socle", {"n": 0})["n"] == communes

    def test_signature_vue_table_illisible_rend_none(self, app, decor, monkeypatch):
        from Code import bienvenue
        from Code.extensions import db as _db

        def _casse(*a, **k):
            raise RuntimeError("table absente")

        with app.app_context():
            u = _user(decor["coord"])
            monkeypatch.setattr(_db.session, "get", _casse)
            monkeypatch.setattr(_db.session, "rollback", _casse)
            assert bienvenue.signature_vue(u) is None

    def test_marquer_vue_table_illisible_rend_false(self, app, decor, monkeypatch):
        from Code import bienvenue
        from Code.extensions import db as _db

        def _casse(*a, **k):
            raise RuntimeError("table absente")

        with app.app_context():
            u = _user(decor["coord"])
            monkeypatch.setattr(_db.session, "get", _casse)
            monkeypatch.setattr(_db.session, "rollback", _casse)
            assert bienvenue.marquer_vue(u, signature="sig") is False


# ══════════════════════════════════════════════════════════════════════════
class TestSocleDroitDeRemplir:

    def test_un_champion_qui_ne_LIT_pas_la_carto_ne_la_remplit_pas(self, app, decor):
        """Carto commune en saisie, mais réservée à un rôle que le champion
        n'a pas : il ne peut pas l'ouvrir, donc il n'y écrit pas."""
        from Code.carto_access import can_fill, can_read
        from Code.models.models import EntityRoleAccess, Role
        with app.app_context():
            r = Role(name="Rôle réservé SX%d" % decor["n"], entity_id=decor["a"])
            db.session.add(r)
            db.session.commit()
            db.session.add(EntityRoleAccess(entity_id=decor["a"], role_id=r.id))
            db.session.commit()
        with app.test_request_context():
            e, u = _ent(decor["a"]), _user(decor["champ"])
            assert can_read(e, u) is False
            assert can_fill(e, u) is False

    def test_sans_restriction_le_champion_remplit(self, app, decor):
        from Code.carto_access import can_fill
        with app.test_request_context():
            assert can_fill(_ent(decor["a"]), _user(decor["champ"])) is True


# ══════════════════════════════════════════════════════════════════════════
class TestPageActivitesReplis:
    """Le panneau du socle, les liaisons de tâches : ce qui tombe ne doit
    jamais emporter la page."""

    def _client(self, app, uid, eid):
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = uid
            s["active_entity_id"] = eid
        return c

    def test_socle_illisible_rend_none(self, app, decor, monkeypatch, capsys):
        import Code.socle_activites as socle
        from Code.routes.activities_view import _socle

        def _casse(*a, **k):
            raise RuntimeError("boum")

        monkeypatch.setattr(socle, "etat", _casse)
        with app.test_request_context():
            assert _socle() is None
        assert "[SOCLE]" in capsys.readouterr().out

    def test_la_page_s_ouvre_quand_le_socle_tombe(self, app, decor, monkeypatch):
        import Code.socle_activites as socle

        def _casse(*a, **k):
            raise RuntimeError("boum")

        monkeypatch.setattr(socle, "etat", _casse)
        c = self._client(app, decor["coord"], decor["a"])
        r = c.get("/activities/view")
        assert r.status_code == 200
        assert b'id="scl"' not in r.data

    def test_la_page_montre_le_panneau_quand_le_socle_se_lit(self, app, decor):
        """Témoin du test précédent : sans la panne, le panneau est là."""
        c = self._client(app, decor["coord"], decor["a"])
        r = c.get("/activities/view")
        assert r.status_code == 200
        assert b'id="scl"' in r.data

    def test_la_page_s_ouvre_quand_la_table_des_liaisons_tombe(self, app, ids,
                                                                monkeypatch):
        import Code.routes.task_link_assignments as tla

        def _casse():
            raise RuntimeError("table illisible")

        monkeypatch.setattr(tla, "ensure_table", _casse)
        c = self._client(app, ids["user_id"], ids["entity_id"])
        r = c.get("/activities/view")
        assert r.status_code == 200

    def test_liaisons_illisibles_la_fiche_reste_servie(self, app, ids, monkeypatch):
        """La lecture des liaisons tâche↔lien échoue : la fiche est rendue
        sans elles, et la session est remise d'aplomb (rollback)."""
        import Code.routes.activities_view as av
        vrai_text = av.text

        def _texte(sql):
            if "task_link_assignments" in sql:
                return vrai_text("SELECT * FROM table_qui_n_existe_pas_sx")
            return vrai_text(sql)

        monkeypatch.setattr(av, "text", _texte)
        c = self._client(app, ids["user_id"], ids["entity_id"])
        r = c.get("/activities/view?activity_id=%d" % ids["activity_id"])
        assert r.status_code == 200
        # La session doit rester utilisable après le rollback du repli.
        assert c.get("/activities/view").status_code == 200


# ══════════════════════════════════════════════════════════════════════════
class TestPorteEtPropositionsBranches:

    def test_socle_en_examen_carto_illisible_rend_false(self, app, monkeypatch):
        from Code import ecriture
        from Code.models.models import Entity

        def _casse(*a, **k):
            raise RuntimeError("boum")

        monkeypatch.setattr(Entity, "get_active", staticmethod(_casse))
        with app.test_request_context():
            assert ecriture._socle_en_examen() is False

    def test_socle_en_examen_suit_l_etat_soumis(self, app, decor):
        from Code import ecriture
        _poser(app, decor["a"], socle_etat="soumis")
        with app.test_request_context():
            from flask import session
            session["user_id"] = decor["coord"]
            session["active_entity_id"] = decor["a"]
            assert ecriture._socle_en_examen() is True

    def test_nom_d_un_auteur_absent_est_vide(self):
        from Code.routes.activite_propositions import _nom
        assert _nom(None) == ""

    def test_nom_retombe_sur_l_email(self, app, decor):
        from Code.routes.activite_propositions import _nom
        with app.app_context():
            u = _user(decor["coord"])
            u.first_name, u.last_name = "", None
            assert _nom(u) == u.email
            db.session.rollback()

    def test_reecrire_refs_laisse_un_corps_non_dict(self):
        from Code.propositions_activite import _reecrire_refs
        assert _reecrire_refs(["a", "b"], lambda r: r + 1) == ["a", "b"]
        assert _reecrire_refs(None, lambda r: r + 1) is None

    def test_nom_des_outils_par_tool_id(self, app, decor):
        from Code.models.models import Tool
        from Code.propositions_activite import _nom_des_outils
        with app.app_context():
            o = Tool(name="Outil seul SX%d" % decor["n"], entity_id=decor["a"])
            db.session.add(o)
            db.session.commit()
            try:
                assert _nom_des_outils({"tool_id": o.id}) == o.name
                assert _nom_des_outils({"tool_id": 987654321}) is None
            finally:
                db.session.delete(o)
                db.session.commit()

    def test_id_cree_reponse_illisible_rend_none(self):
        from Code.propositions_activite import _id_cree

        class _Illisible:
            def get_json(self, silent=True):
                raise ValueError("corps illisible")

        assert _id_cree(_Illisible()) is None
        assert _id_cree((_Illisible(), 201)) is None

    def test_id_cree_corps_non_dict_rend_none(self):
        from Code.propositions_activite import _id_cree

        class _Liste:
            def get_json(self, silent=True):
                return [1, 2]

        class _IdTexte:
            def get_json(self, silent=True):
                return {"id": "12"}

        assert _id_cree(_Liste()) is None
        assert _id_cree(_IdTexte()) is None
