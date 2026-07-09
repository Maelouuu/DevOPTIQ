# tests/test_51_competency_color.py
"""
Module : Couleur de synthèse des compétences (Code/competency_color.py)
Couvre : user_competency_color / user_competency_hex — agrégation des notes
d'évaluation ('red'/'orange'/'green') en une couleur unique, filtrage par
evaluator et activity_ids, arrondi de la moyenne, cas sans note.
"""
import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.competency_color


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(app, entity_id, email):
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        u = User(
            entity_id=entity_id,
            first_name="Color",
            last_name="Test",
            email=email,
            password=generate_password_hash("Pass123!"),
            status="user",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _create_activity(app, entity_id, name):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, description="")
        db.session.add(a)
        db.session.commit()
        return a.id


def _add_eval(app, user_id, activity_id, note, evaluator="manager", item_id=None, item_type=None):
    with app.app_context():
        from Code.models.models import CompetencyEvaluation
        from Code.extensions import db
        e = CompetencyEvaluation(
            user_id=user_id,
            activity_id=activity_id,
            item_id=item_id,
            item_type=item_type,
            eval_number=evaluator,
            note=note,
        )
        db.session.add(e)
        db.session.commit()
        return e.id


def _cleanup(app, user_ids=None, activity_ids=None):
    with app.app_context():
        from Code.models.models import User, Activities, CompetencyEvaluation
        from Code.extensions import db
        for uid in (user_ids or []):
            CompetencyEvaluation.query.filter_by(user_id=uid).delete()
            u = User.query.get(uid)
            if u:
                db.session.delete(u)
        for aid in (activity_ids or []):
            a = Activities.query.get(aid)
            if a:
                db.session.delete(a)
        db.session.commit()


# ===========================================================================
# 1. Aucune évaluation
# ===========================================================================

class TestNoEvaluation:

    def test_no_evaluation_returns_none(self, app, ids):
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-none@devoptiq.com")
        with app.app_context():
            result = user_competency_color(uid)
        assert result is None
        _cleanup(app, user_ids=[uid])

    def test_no_evaluation_hex_returns_none(self, app, ids):
        from Code.competency_color import user_competency_hex
        uid = _create_user(app, ids["entity_id"], "color-none-hex@devoptiq.com")
        with app.app_context():
            result = user_competency_hex(uid)
        assert result is None
        _cleanup(app, user_ids=[uid])

    def test_empty_activity_ids_list_returns_none(self, app, ids):
        """Une liste vide d'activity_ids signifie 'rien à évaluer' → None."""
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-empty-list@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "green")
        with app.app_context():
            result = user_competency_color(uid, activity_ids=[])
        assert result is None
        _cleanup(app, user_ids=[uid])


# ===========================================================================
# 2. Une seule note
# ===========================================================================

class TestSingleNote:

    def test_single_red_note(self, app, ids):
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-red@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "red")
        with app.app_context():
            result = user_competency_color(uid)
        assert result == "red"
        _cleanup(app, user_ids=[uid])

    def test_single_orange_note(self, app, ids):
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-orange@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "orange")
        with app.app_context():
            result = user_competency_color(uid)
        assert result == "orange"
        _cleanup(app, user_ids=[uid])

    def test_single_green_note(self, app, ids):
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-green@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "green")
        with app.app_context():
            result = user_competency_color(uid)
        assert result == "green"
        _cleanup(app, user_ids=[uid])

    def test_single_note_hex_matches_color_hex(self, app, ids):
        from Code.competency_color import user_competency_hex, COLOR_HEX
        uid = _create_user(app, ids["entity_id"], "color-hex-green@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "green")
        with app.app_context():
            result = user_competency_hex(uid)
        assert result == COLOR_HEX["green"]
        _cleanup(app, user_ids=[uid])


# ===========================================================================
# 3. Moyenne de plusieurs notes (arrondi)
# ===========================================================================

class TestAverageRounding:

    def test_red_and_green_average_rounds_to_orange(self, app, ids):
        """(1 + 3) / 2 = 2.0 → round(2.0) = 2 → 'orange'."""
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-avg1@devoptiq.com")
        a1 = _create_activity(app, ids["entity_id"], "Activité couleur A1")
        a2 = _create_activity(app, ids["entity_id"], "Activité couleur A2")
        _add_eval(app, uid, a1, "red")
        _add_eval(app, uid, a2, "green")
        with app.app_context():
            result = user_competency_color(uid)
        assert result == "orange"
        _cleanup(app, user_ids=[uid], activity_ids=[a1, a2])

    def test_two_greens_and_one_red_rounds_to_orange(self, app, ids):
        """(3 + 3 + 1) / 3 = 2.33 → round(2.33) = 2 → 'orange'."""
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-avg2@devoptiq.com")
        a1 = _create_activity(app, ids["entity_id"], "Activité couleur A3")
        a2 = _create_activity(app, ids["entity_id"], "Activité couleur A4")
        a3 = _create_activity(app, ids["entity_id"], "Activité couleur A5")
        _add_eval(app, uid, a1, "green")
        _add_eval(app, uid, a2, "green")
        _add_eval(app, uid, a3, "red")
        with app.app_context():
            result = user_competency_color(uid)
        # avg = (3+3+1)/3 = 2.333... -> round -> 2 -> 'orange'
        assert result == "orange"
        _cleanup(app, user_ids=[uid], activity_ids=[a1, a2, a3])

    def test_all_green_stays_green(self, app, ids):
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-allgreen@devoptiq.com")
        a1 = _create_activity(app, ids["entity_id"], "Activité couleur A6")
        a2 = _create_activity(app, ids["entity_id"], "Activité couleur A7")
        _add_eval(app, uid, a1, "green")
        _add_eval(app, uid, a2, "green")
        with app.app_context():
            result = user_competency_color(uid)
        assert result == "green"
        _cleanup(app, user_ids=[uid], activity_ids=[a1, a2])


# ===========================================================================
# 4. Filtrage par evaluator
# ===========================================================================

class TestEvaluatorFilter:

    def test_default_evaluator_is_manager(self, app, ids):
        """Sans evaluator explicite, seules les notes 'manager' comptent."""
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-eval1@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "red", evaluator="garant")
        with app.app_context():
            result = user_competency_color(uid)
        assert result is None
        _cleanup(app, user_ids=[uid])

    def test_explicit_evaluator_garant_is_honored(self, app, ids):
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-eval2@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "red", evaluator="garant")
        with app.app_context():
            result = user_competency_color(uid, evaluator="garant")
        assert result == "red"
        _cleanup(app, user_ids=[uid])

    def test_different_evaluators_do_not_mix(self, app, ids):
        """Une note 'manager' et une note 'rh' différentes ne se mélangent pas."""
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-eval3@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "green", evaluator="manager")
        _add_eval(app, uid, ids["activity_id"], "red", evaluator="rh")
        with app.app_context():
            manager_result = user_competency_color(uid, evaluator="manager")
            rh_result = user_competency_color(uid, evaluator="rh")
        assert manager_result == "green"
        assert rh_result == "red"
        _cleanup(app, user_ids=[uid])


# ===========================================================================
# 5. Filtrage par activity_ids
# ===========================================================================

class TestActivityIdsFilter:

    def test_activity_ids_restricts_scope(self, app, ids):
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-scope1@devoptiq.com")
        a1 = _create_activity(app, ids["entity_id"], "Activité scope A1")
        a2 = _create_activity(app, ids["entity_id"], "Activité scope A2")
        _add_eval(app, uid, a1, "red")
        _add_eval(app, uid, a2, "green")
        with app.app_context():
            only_a1 = user_competency_color(uid, activity_ids=[a1])
            only_a2 = user_competency_color(uid, activity_ids=[a2])
            both = user_competency_color(uid, activity_ids=[a1, a2])
        assert only_a1 == "red"
        assert only_a2 == "green"
        assert both == "orange"
        _cleanup(app, user_ids=[uid], activity_ids=[a1, a2])

    def test_activity_ids_none_includes_all(self, app, ids):
        """activity_ids=None (défaut) inclut toutes les activités évaluées."""
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-scope2@devoptiq.com")
        a1 = _create_activity(app, ids["entity_id"], "Activité scope A3")
        _add_eval(app, uid, a1, "red")
        with app.app_context():
            result = user_competency_color(uid, activity_ids=None)
        assert result == "red"
        _cleanup(app, user_ids=[uid], activity_ids=[a1])

    def test_unrelated_activity_not_included(self, app, ids):
        """Une évaluation hors du filtre activity_ids ne doit pas influencer le résultat."""
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-scope3@devoptiq.com")
        a1 = _create_activity(app, ids["entity_id"], "Activité scope A4")
        a2 = _create_activity(app, ids["entity_id"], "Activité scope A5")
        _add_eval(app, uid, a1, "red")
        _add_eval(app, uid, a2, "green")
        with app.app_context():
            result = user_competency_color(uid, activity_ids=[a1])
        assert result == "red"
        _cleanup(app, user_ids=[uid], activity_ids=[a1, a2])


# ===========================================================================
# 6. Notes invalides ignorées
# ===========================================================================

class TestInvalidNotes:

    def test_note_not_in_note_value_is_ignored(self, app, ids):
        """Une note hors de {'red','orange','green'} (ex: 'garant') est ignorée dans la moyenne."""
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-invalid@devoptiq.com")
        _add_eval(app, uid, ids["activity_id"], "garant")
        with app.app_context():
            result = user_competency_color(uid)
        assert result is None
        _cleanup(app, user_ids=[uid])

    def test_valid_note_counted_when_mixed_with_invalid(self, app, ids):
        from Code.competency_color import user_competency_color
        uid = _create_user(app, ids["entity_id"], "color-mixed@devoptiq.com")
        a1 = _create_activity(app, ids["entity_id"], "Activité mixte A1")
        a2 = _create_activity(app, ids["entity_id"], "Activité mixte A2")
        _add_eval(app, uid, a1, "garant")
        _add_eval(app, uid, a2, "green")
        with app.app_context():
            result = user_competency_color(uid)
        assert result == "green"
        _cleanup(app, user_ids=[uid], activity_ids=[a1, a2])
