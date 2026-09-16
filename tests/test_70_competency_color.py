# tests/test_70_competency_color.py
"""
Page : Couleur de synthèse des compétences (Code/competency_color.py)

Utilisé pour colorer un utilisateur selon ses évaluations (page Rôles, page
Gestion RH). Aucun test direct n'existait : la fonction n'est exercée
qu'indirectement, en creux, par des pages qui ne vérifient pas sa valeur de
retour. Ce fichier crée ses propres évaluations (activité et utilisateur
dédiés) et les nettoie à la fin de chaque test pour ne pas fausser les
moyennes d'un autre test partageant la même base (scope=session).
"""
import pytest

from Code.competency_color import (COLOR_HEX, user_competency_color,
                                   user_competency_hex)
from Code.extensions import db
from Code.models.models import Activities, CompetencyEvaluation, Entity, User

pytestmark = pytest.mark.competences


@pytest.fixture
def couleur_ctx(app, ids):
    """Un utilisateur et deux activités dédiés, nettoyés après le test."""
    with app.app_context():
        entity = db.session.get(Entity, ids["entity_id"])
        user = User(entity_id=entity.id, first_name="Couleur", last_name="Test",
                    email="couleur.test.70@devoptiq.com", password="x", status="user")
        db.session.add(user)
        act1 = Activities(entity_id=entity.id, name="Activité Couleur 1")
        act2 = Activities(entity_id=entity.id, name="Activité Couleur 2")
        db.session.add_all([act1, act2])
        db.session.commit()
        ctx = {"user_id": user.id, "act1": act1.id, "act2": act2.id}
        yield ctx
        CompetencyEvaluation.query.filter_by(user_id=user.id).delete()
        db.session.delete(act1)
        db.session.delete(act2)
        db.session.delete(user)
        db.session.commit()


class TestUserCompetencyColor:

    def test_aucune_evaluation_retourne_none(self, app, couleur_ctx):
        with app.app_context():
            assert user_competency_color(couleur_ctx["user_id"]) is None

    def test_une_seule_note_verte_retourne_green(self, app, couleur_ctx):
        with app.app_context():
            db.session.add(CompetencyEvaluation(
                user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act1"],
                eval_number="manager", note="green"))
            db.session.commit()
            assert user_competency_color(couleur_ctx["user_id"]) == "green"

    def test_moyenne_rouge_et_vert_arrondit_vers_orange(self, app, couleur_ctx):
        with app.app_context():
            db.session.add_all([
                CompetencyEvaluation(user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act1"],
                                     eval_number="manager", note="red"),
                CompetencyEvaluation(user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act2"],
                                     eval_number="manager", note="green"),
            ])
            db.session.commit()
            # (1 + 3) / 2 = 2.0 -> round(2.0) = 2 -> orange
            assert user_competency_color(couleur_ctx["user_id"]) == "orange"

    def test_notes_hors_categories_connues_sont_ignorees(self, app, couleur_ctx):
        with app.app_context():
            db.session.add_all([
                CompetencyEvaluation(user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act1"],
                                     eval_number="manager", note="garant"),
                CompetencyEvaluation(user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act2"],
                                     eval_number="manager", note="green"),
            ])
            db.session.commit()
            # 'garant' n'est pas une couleur : seule 'green' compte.
            assert user_competency_color(couleur_ctx["user_id"]) == "green"

    def test_evaluator_differe_est_ignore(self, app, couleur_ctx):
        with app.app_context():
            db.session.add(CompetencyEvaluation(
                user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act1"],
                eval_number="rh", note="green"))
            db.session.commit()
            # Par défaut on regarde 'manager' : la note 'rh' ne compte pas.
            assert user_competency_color(couleur_ctx["user_id"]) is None
            assert user_competency_color(couleur_ctx["user_id"], evaluator="rh") == "green"

    def test_activity_ids_vide_retourne_none_sans_requeter_tout(self, app, couleur_ctx):
        with app.app_context():
            db.session.add(CompetencyEvaluation(
                user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act1"],
                eval_number="manager", note="green"))
            db.session.commit()
            assert user_competency_color(couleur_ctx["user_id"], activity_ids=[]) is None

    def test_activity_ids_restreint_le_calcul(self, app, couleur_ctx):
        with app.app_context():
            db.session.add_all([
                CompetencyEvaluation(user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act1"],
                                     eval_number="manager", note="red"),
                CompetencyEvaluation(user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act2"],
                                     eval_number="manager", note="green"),
            ])
            db.session.commit()
            only_act2 = user_competency_color(
                couleur_ctx["user_id"], activity_ids=[couleur_ctx["act2"]])
            assert only_act2 == "green"


class TestUserCompetencyHex:

    def test_sans_note_retourne_none(self, app, couleur_ctx):
        with app.app_context():
            assert user_competency_hex(couleur_ctx["user_id"]) is None

    def test_avec_note_retourne_le_code_hex_correspondant(self, app, couleur_ctx):
        with app.app_context():
            db.session.add(CompetencyEvaluation(
                user_id=couleur_ctx["user_id"], activity_id=couleur_ctx["act1"],
                eval_number="manager", note="orange"))
            db.session.commit()
            assert user_competency_hex(couleur_ctx["user_id"]) == COLOR_HEX["orange"]
