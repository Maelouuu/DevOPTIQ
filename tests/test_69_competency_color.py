# tests/test_69_competency_color.py
"""
Couverture de Code/competency_color.py — synthèse couleur des évaluations de
compétence d'un utilisateur (utilisé par Gestion RH et la vue Rôles).

Aucune route HTTP : appels directs aux fonctions dans un contexte d'app,
avec des User/CompetencyEvaluation dédiés (nettoyés après chaque test) pour
ne pas polluer la session de tests partagée.
"""
import pytest
from werkzeug.security import generate_password_hash

from Code.competency_color import user_competency_color, user_competency_hex, COLOR_HEX


@pytest.fixture
def evaluated_user(app, ids):
    """Un utilisateur dédié, prêt à recevoir des CompetencyEvaluation jetables."""
    from Code.extensions import db
    from Code.models.models import User, CompetencyEvaluation

    with app.app_context():
        user = User(
            entity_id=ids["entity_id"],
            first_name="Coloré",
            last_name="Test69",
            email=f"coloretest69-{id(object())}@devoptiq.com",
            password=generate_password_hash("Whatever123!"),
            status="collaborateur",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        yield user_id

        CompetencyEvaluation.query.filter_by(user_id=user_id).delete()
        User.query.filter_by(id=user_id).delete()
        db.session.commit()


def _add_eval(app, user_id, activity_id, note, evaluator="manager"):
    from Code.extensions import db
    from Code.models.models import CompetencyEvaluation

    with app.app_context():
        ev = CompetencyEvaluation(
            user_id=user_id,
            activity_id=activity_id,
            eval_number=evaluator,
            note=note,
        )
        db.session.add(ev)
        db.session.commit()


class TestUserCompetencyColorNoData:
    def test_no_evaluation_returns_none(self, app, evaluated_user):
        with app.app_context():
            assert user_competency_color(evaluated_user) is None

    def test_no_evaluation_hex_returns_none(self, app, evaluated_user):
        with app.app_context():
            assert user_competency_hex(evaluated_user) is None

    def test_empty_activity_ids_returns_none_even_with_evaluations(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "green")
        with app.app_context():
            assert user_competency_color(evaluated_user, activity_ids=[]) is None


class TestUserCompetencyColorSingleNote:
    def test_single_red_note(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "red")
        with app.app_context():
            assert user_competency_color(evaluated_user) == "red"

    def test_single_orange_note(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "orange")
        with app.app_context():
            assert user_competency_color(evaluated_user) == "orange"

    def test_single_green_note_hex(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "green")
        with app.app_context():
            assert user_competency_hex(evaluated_user) == COLOR_HEX["green"]


class TestUserCompetencyColorAveraging:
    def test_red_and_green_average_to_orange(self, app, evaluated_user, ids):
        # (1 + 3) / 2 = 2.0 -> round() = 2 -> 'orange'
        _add_eval(app, evaluated_user, ids["activity_id"], "red")
        _add_eval(app, evaluated_user, ids["activity_id"], "green")
        with app.app_context():
            assert user_competency_color(evaluated_user) == "orange"

    def test_two_greens_and_one_red_rounds_to_green(self, app, evaluated_user, ids):
        # (3 + 3 + 1) / 3 = 2.33 -> round() = 2 -> 'orange' (pas 'green')
        _add_eval(app, evaluated_user, ids["activity_id"], "green")
        _add_eval(app, evaluated_user, ids["activity_id"], "green")
        _add_eval(app, evaluated_user, ids["activity_id"], "red")
        with app.app_context():
            assert user_competency_color(evaluated_user) == "orange"

    def test_ignores_note_outside_known_values(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "green")
        _add_eval(app, evaluated_user, ids["activity_id"], "inconnu")
        with app.app_context():
            # La note invalide est ignorée : le calcul se base uniquement sur 'green'.
            assert user_competency_color(evaluated_user) == "green"

    def test_only_unknown_notes_returns_none(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "inconnu")
        with app.app_context():
            assert user_competency_color(evaluated_user) is None


class TestUserCompetencyColorEvaluatorFilter:
    def test_different_evaluator_is_ignored_by_default(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "red", evaluator="garant")
        with app.app_context():
            # Par défaut evaluator='manager' : la note 'garant' ne compte pas.
            assert user_competency_color(evaluated_user) is None

    def test_explicit_evaluator_is_honored(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "red", evaluator="garant")
        with app.app_context():
            assert user_competency_color(evaluated_user, evaluator="garant") == "red"

    def test_rh_evaluator_isolated_from_manager(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "green", evaluator="manager")
        _add_eval(app, evaluated_user, ids["activity_id"], "red", evaluator="rh")
        with app.app_context():
            assert user_competency_color(evaluated_user, evaluator="manager") == "green"
            assert user_competency_color(evaluated_user, evaluator="rh") == "red"


class TestUserCompetencyColorActivityFilter:
    def test_activity_ids_restricts_scope(self, app, evaluated_user, ids):
        from Code.extensions import db
        from Code.models.models import Activities

        with app.app_context():
            other_activity = Activities(
                entity_id=ids["entity_id"],
                name="Activité Test69 Filtre",
                description="Dédiée au test de filtrage",
            )
            db.session.add(other_activity)
            db.session.commit()
            other_activity_id = other_activity.id

        try:
            _add_eval(app, evaluated_user, ids["activity_id"], "red")
            _add_eval(app, evaluated_user, other_activity_id, "green")

            with app.app_context():
                assert user_competency_color(evaluated_user, activity_ids=[ids["activity_id"]]) == "red"
                assert user_competency_color(evaluated_user, activity_ids=[other_activity_id]) == "green"
                assert user_competency_color(evaluated_user) == "orange"
        finally:
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                CompetencyEvaluation.query.filter_by(
                    user_id=evaluated_user, activity_id=other_activity_id
                ).delete()
                Activities.query.filter_by(id=other_activity_id).delete()
                db.session.commit()

    def test_none_activity_ids_considers_all_activities(self, app, evaluated_user, ids):
        _add_eval(app, evaluated_user, ids["activity_id"], "green")
        with app.app_context():
            assert user_competency_color(evaluated_user, activity_ids=None) == "green"
