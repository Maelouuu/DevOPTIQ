# tests/test_52_competency_color.py
"""
Module : competency_color.py
Tests unitaires directs de user_competency_color() et user_competency_hex().

Logique : les notes 'red' < 'orange' < 'green' sont converties en 1/2/3,
moyennées, puis reconverties avec round(). Résultat : None si aucune note.
"""
import pytest

pytestmark = pytest.mark.competency_color


def _add_eval(app, db, user_id, activity_id, note, evaluator="manager", item_id=None, item_type=None):
    """Insère un CompetencyEvaluation et retourne son id."""
    from Code.models.models import CompetencyEvaluation
    ev = CompetencyEvaluation(
        user_id=user_id,
        activity_id=activity_id,
        eval_number=evaluator,
        note=note,
        item_id=item_id,
        item_type=item_type,
    )
    db.session.add(ev)
    db.session.flush()
    return ev.id


def _cleanup_evals(app, db, user_id):
    """Supprime toutes les évaluations du user de test."""
    from Code.models.models import CompetencyEvaluation
    CompetencyEvaluation.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    db.session.commit()


# ══════════════════════════════════════════════════════════════════════════════
# 1. user_competency_color
# ══════════════════════════════════════════════════════════════════════════════

class TestUserCompetencyColor:

    def test_no_evals_returns_none(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            _cleanup_evals(app, db, ids["user_id"])
            result = user_competency_color(ids["user_id"])
            assert result is None

    def test_single_red_returns_red(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "red")
            db.session.commit()
            result = user_competency_color(ids["user_id"])
            assert result == "red"
            _cleanup_evals(app, db, ids["user_id"])

    def test_single_orange_returns_orange(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "orange")
            db.session.commit()
            result = user_competency_color(ids["user_id"])
            assert result == "orange"
            _cleanup_evals(app, db, ids["user_id"])

    def test_single_green_returns_green(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "green")
            db.session.commit()
            result = user_competency_color(ids["user_id"])
            assert result == "green"
            _cleanup_evals(app, db, ids["user_id"])

    def test_red_and_green_average_is_orange(self, app, ids):
        """red=1, green=3 → average=2.0 → orange."""
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            from Code.models.models import Activities, Entity
            _cleanup_evals(app, db, ids["user_id"])
            # Create a second activity for the second eval (unique constraint is on user+activity+item+evalnum)
            entity = Entity.query.filter_by(name="Entité Test").first()
            act2 = Activities(entity_id=entity.id, name="Activité Color Test 2", description="")
            db.session.add(act2)
            db.session.flush()
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "red")
            _add_eval(app, db, ids["user_id"], act2.id, "green")
            db.session.commit()
            result = user_competency_color(ids["user_id"])
            assert result == "orange"
            _cleanup_evals(app, db, ids["user_id"])
            db.session.delete(act2)
            db.session.commit()

    def test_all_green_returns_green(self, app, ids):
        """Trois green → average=3 → green."""
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            from Code.models.models import Activities, Entity
            _cleanup_evals(app, db, ids["user_id"])
            entity = Entity.query.filter_by(name="Entité Test").first()
            acts = []
            for i in range(3):
                a = Activities(entity_id=entity.id, name=f"Activité Green {i}", description="")
                db.session.add(a)
                db.session.flush()
                acts.append(a)
            for a in acts:
                _add_eval(app, db, ids["user_id"], a.id, "green")
            db.session.commit()
            result = user_competency_color(ids["user_id"])
            assert result == "green"
            _cleanup_evals(app, db, ids["user_id"])
            for a in acts:
                db.session.delete(a)
            db.session.commit()

    def test_all_red_returns_red(self, app, ids):
        """Trois red → average=1 → red."""
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            from Code.models.models import Activities, Entity
            _cleanup_evals(app, db, ids["user_id"])
            entity = Entity.query.filter_by(name="Entité Test").first()
            acts = []
            for i in range(3):
                a = Activities(entity_id=entity.id, name=f"Activité Red {i}", description="")
                db.session.add(a)
                db.session.flush()
                acts.append(a)
            for a in acts:
                _add_eval(app, db, ids["user_id"], a.id, "red")
            db.session.commit()
            result = user_competency_color(ids["user_id"])
            assert result == "red"
            _cleanup_evals(app, db, ids["user_id"])
            for a in acts:
                db.session.delete(a)
            db.session.commit()

    def test_garant_evaluator_ignored_by_default(self, app, ids):
        """eval_number='garant' ignoré quand on filtre par 'manager' (default)."""
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "green", evaluator="garant")
            db.session.commit()
            result = user_competency_color(ids["user_id"])  # evaluator='manager' par défaut
            assert result is None
            _cleanup_evals(app, db, ids["user_id"])

    def test_custom_evaluator_rh(self, app, ids):
        """eval_number='rh' retourné quand evaluator='rh'."""
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "orange", evaluator="rh")
            db.session.commit()
            result = user_competency_color(ids["user_id"], evaluator="rh")
            assert result == "orange"
            _cleanup_evals(app, db, ids["user_id"])

    def test_activity_ids_filter_empty_list_returns_none(self, app, ids):
        """activity_ids=[] → None (rien à évaluer)."""
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "green")
            db.session.commit()
            result = user_competency_color(ids["user_id"], activity_ids=[])
            assert result is None
            _cleanup_evals(app, db, ids["user_id"])

    def test_activity_ids_filter_restricts_scope(self, app, ids):
        """activity_ids=[act_id] ne compte que les évals de cette activité."""
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            from Code.models.models import Activities, Entity
            _cleanup_evals(app, db, ids["user_id"])
            entity = Entity.query.filter_by(name="Entité Test").first()
            act2 = Activities(entity_id=entity.id, name="Activité Filter Scope", description="")
            db.session.add(act2)
            db.session.flush()
            # act1 = red, act2 = green
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "red")
            _add_eval(app, db, ids["user_id"], act2.id, "green")
            db.session.commit()
            # Filtrer sur act2 seul → green
            result = user_competency_color(ids["user_id"], activity_ids=[act2.id])
            assert result == "green"
            _cleanup_evals(app, db, ids["user_id"])
            db.session.delete(act2)
            db.session.commit()

    def test_result_is_string_or_none(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_color
            _cleanup_evals(app, db, ids["user_id"])
            result = user_competency_color(ids["user_id"])
            assert result is None or isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# 2. user_competency_hex
# ══════════════════════════════════════════════════════════════════════════════

class TestUserCompetencyHex:

    def test_no_evals_returns_none(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_hex
            _cleanup_evals(app, db, ids["user_id"])
            result = user_competency_hex(ids["user_id"])
            assert result is None

    def test_red_returns_hex_red(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_hex
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "red")
            db.session.commit()
            result = user_competency_hex(ids["user_id"])
            assert result == "#ef4444"
            _cleanup_evals(app, db, ids["user_id"])

    def test_orange_returns_hex_orange(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_hex
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "orange")
            db.session.commit()
            result = user_competency_hex(ids["user_id"])
            assert result == "#f59e0b"
            _cleanup_evals(app, db, ids["user_id"])

    def test_green_returns_hex_green(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_hex
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "green")
            db.session.commit()
            result = user_competency_hex(ids["user_id"])
            assert result == "#22c55e"
            _cleanup_evals(app, db, ids["user_id"])

    def test_hex_is_lowercase_hash_prefixed(self, app, ids):
        with app.app_context():
            from Code.extensions import db
            from Code.competency_color import user_competency_hex
            _cleanup_evals(app, db, ids["user_id"])
            _add_eval(app, db, ids["user_id"], ids["activity_id"], "green")
            db.session.commit()
            result = user_competency_hex(ids["user_id"])
            assert result is not None
            assert result.startswith("#")
            assert len(result) == 7
            _cleanup_evals(app, db, ids["user_id"])


# ══════════════════════════════════════════════════════════════════════════════
# 3. Tests des constantes du module
# ══════════════════════════════════════════════════════════════════════════════

class TestColorConstants:

    def test_note_value_mapping(self):
        from Code.competency_color import NOTE_VALUE
        assert NOTE_VALUE["red"] == 1
        assert NOTE_VALUE["orange"] == 2
        assert NOTE_VALUE["green"] == 3

    def test_color_hex_mapping(self):
        from Code.competency_color import COLOR_HEX
        assert COLOR_HEX["red"] == "#ef4444"
        assert COLOR_HEX["orange"] == "#f59e0b"
        assert COLOR_HEX["green"] == "#22c55e"

    def test_color_hex_all_valid_hex(self):
        from Code.competency_color import COLOR_HEX
        for color, hex_val in COLOR_HEX.items():
            assert hex_val.startswith("#"), f"{color}: {hex_val} ne commence pas par #"
            assert len(hex_val) == 7, f"{color}: {hex_val} n'a pas 7 chars"
