# tests/test_60_competency_color.py
"""
Tests unitaires pour Code/competency_color.py (pas de route HTTP) :
  user_competency_color, user_competency_hex
Couleur de synthèse d'un utilisateur à partir de ses CompetencyEvaluation.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_entity_user_activities(app, suffix, n_activities=2):
    """Crée une entité, un user et N activités dédiés, isolés du reste de la suite."""
    from Code.extensions import db
    from Code.models.models import Entity, User, Activities

    with app.app_context():
        entity = Entity(name=f"Entité T60-{suffix}", description="Test competency_color")
        db.session.add(entity)
        db.session.flush()

        user = User(
            entity_id=entity.id,
            first_name="T60",
            last_name="User",
            email=f"t60.{suffix}@devoptiq.com",
            password="unused",
            status="user",
        )
        db.session.add(user)
        db.session.flush()

        activities = []
        for i in range(n_activities):
            act = Activities(entity_id=entity.id, name=f"Activité T60-{suffix}-{i}")
            db.session.add(act)
            db.session.flush()
            activities.append(act.id)

        db.session.commit()
        return {"entity_id": entity.id, "user_id": user.id, "activity_ids": activities}


def _add_eval(app, user_id, activity_id, note, eval_number="manager"):
    from Code.extensions import db
    from Code.models.models import CompetencyEvaluation

    with app.app_context():
        ev = CompetencyEvaluation(
            user_id=user_id,
            activity_id=activity_id,
            eval_number=eval_number,
            note=note,
        )
        db.session.add(ev)
        db.session.commit()


def _cleanup(app, ctx):
    from Code.extensions import db
    from Code.models.models import Entity, User, Activities, CompetencyEvaluation

    with app.app_context():
        CompetencyEvaluation.query.filter_by(user_id=ctx["user_id"]).delete()
        Activities.query.filter(Activities.id.in_(ctx["activity_ids"])).delete(synchronize_session=False)
        User.query.filter_by(id=ctx["user_id"]).delete()
        Entity.query.filter_by(id=ctx["entity_id"]).delete()
        db.session.commit()


class TestUserCompetencyColor:

    def test_no_evaluations_returns_none(self, app):
        ctx = _make_entity_user_activities(app, "none")
        try:
            with app.app_context():
                from Code.competency_color import user_competency_color, user_competency_hex
                assert user_competency_color(ctx["user_id"]) is None
                assert user_competency_hex(ctx["user_id"]) is None
        finally:
            _cleanup(app, ctx)

    def test_single_green_note_returns_green(self, app):
        ctx = _make_entity_user_activities(app, "green", n_activities=1)
        try:
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], "green")
            with app.app_context():
                from Code.competency_color import user_competency_color, user_competency_hex
                assert user_competency_color(ctx["user_id"]) == "green"
                assert user_competency_hex(ctx["user_id"]) == "#22c55e"
        finally:
            _cleanup(app, ctx)

    def test_average_of_red_and_green_rounds_to_orange(self, app):
        ctx = _make_entity_user_activities(app, "avg", n_activities=2)
        try:
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], "red")
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][1], "green")
            with app.app_context():
                from Code.competency_color import user_competency_color
                # (1 + 3) / 2 = 2.0 -> orange
                assert user_competency_color(ctx["user_id"]) == "orange"
        finally:
            _cleanup(app, ctx)

    def test_half_point_average_rounds_to_even(self, app):
        ctx = _make_entity_user_activities(app, "half", n_activities=2)
        try:
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], "orange")
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][1], "green")
            with app.app_context():
                from Code.competency_color import user_competency_color
                # (2 + 3) / 2 = 2.5 -> round() Python (half-to-even) -> 2 -> orange
                assert user_competency_color(ctx["user_id"]) == "orange"
        finally:
            _cleanup(app, ctx)

    def test_evaluator_filter_restricts_to_matching_notes(self, app):
        ctx = _make_entity_user_activities(app, "evaluator", n_activities=1)
        try:
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], "green", eval_number="manager")
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], "red", eval_number="garant")
            with app.app_context():
                from Code.competency_color import user_competency_color
                assert user_competency_color(ctx["user_id"], evaluator="manager") == "green"
                assert user_competency_color(ctx["user_id"], evaluator="garant") == "red"
                assert user_competency_color(ctx["user_id"], evaluator="rh") is None
        finally:
            _cleanup(app, ctx)

    def test_activity_ids_filter_restricts_scope(self, app):
        ctx = _make_entity_user_activities(app, "scope", n_activities=2)
        try:
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], "red")
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][1], "green")
            with app.app_context():
                from Code.competency_color import user_competency_color
                only_first = user_competency_color(ctx["user_id"], activity_ids=[ctx["activity_ids"][0]])
                only_second = user_competency_color(ctx["user_id"], activity_ids=[ctx["activity_ids"][1]])
                both = user_competency_color(ctx["user_id"], activity_ids=ctx["activity_ids"])
                assert only_first == "red"
                assert only_second == "green"
                assert both == "orange"
        finally:
            _cleanup(app, ctx)

    def test_empty_activity_ids_list_returns_none(self, app):
        ctx = _make_entity_user_activities(app, "empty", n_activities=1)
        try:
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], "green")
            with app.app_context():
                from Code.competency_color import user_competency_color
                assert user_competency_color(ctx["user_id"], activity_ids=[]) is None
        finally:
            _cleanup(app, ctx)

    def test_unknown_note_values_are_ignored(self, app):
        ctx = _make_entity_user_activities(app, "unknown", n_activities=1)
        try:
            _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], "blue")
            with app.app_context():
                from Code.competency_color import user_competency_color
                assert user_competency_color(ctx["user_id"]) is None
        finally:
            _cleanup(app, ctx)

    def test_unknown_user_returns_none(self, app):
        with app.app_context():
            from Code.competency_color import user_competency_color, user_competency_hex
            assert user_competency_color(-1) is None
            assert user_competency_hex(-1) is None


class TestUserCompetencyHex:

    def test_hex_matches_each_color(self, app):
        ctx = _make_entity_user_activities(app, "hex", n_activities=1)
        try:
            for note, expected_hex in (("red", "#ef4444"), ("orange", "#f59e0b"), ("green", "#22c55e")):
                _add_eval(app, ctx["user_id"], ctx["activity_ids"][0], note, eval_number=f"ev_{note}")
                with app.app_context():
                    from Code.competency_color import user_competency_hex
                    assert user_competency_hex(ctx["user_id"], evaluator=f"ev_{note}") == expected_hex
        finally:
            _cleanup(app, ctx)
