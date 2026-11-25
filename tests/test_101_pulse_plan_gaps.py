"""
Compléments de couverture : pulse_track.py (télémétrie « jamais bloquante »).
Chaque test nettoie ce qu'il crée.

⚠️ Ce fichier couvrait aussi `plan_storage.py` (échec de commit, contenu
corrompu). Ce blueprint était MORT — aucun écran n'y menait — et il a été
retiré : les deux cas sont partis avec leur sujet. Un cas qui appelle une
route supprimée ne garde plus rien, et le supprimer ne garde rien non plus,
d'où la mention ici plutôt qu'un silence.
"""
import pytest

from Code.extensions import db


def _purge_pulse(app):
    from Code.models.models import UsageBeat, UsageEvent
    with app.app_context():
        UsageEvent.query.delete()
        UsageBeat.query.delete()
        db.session.commit()


@pytest.fixture
def pulse_on(app):
    app.config["PULSE_FORCE"] = True
    yield
    app.config["PULSE_FORCE"] = False
    _purge_pulse(app)


class TestPulseTrackResilience:

    def test_write_returns_false_on_invalid_values(self, app):
        from Code.models.models import UsageEvent
        from Code.routes.pulse_track import _write
        with app.app_context():
            assert _write(UsageEvent.__table__, {"colonne_inconnue": 1}) is False

    def test_write_returns_true_on_valid_values(self, app, pulse_on):
        from datetime import datetime
        from Code.models.models import UsageBeat
        from Code.routes.pulse_track import _write
        with app.app_context():
            ok = _write(UsageBeat.__table__, {"ts": datetime.utcnow(),
                                              "user_id": 1,
                                              "session_key": "k",
                                              "path": "/x"})
            assert ok is True

    def test_enabled_false_under_testing_without_force(self, app):
        from Code.routes.pulse_track import _enabled
        with app.test_request_context("/"):
            assert _enabled() is False

    def test_enabled_true_with_force(self, app, pulse_on):
        from Code.routes.pulse_track import _enabled
        with app.test_request_context("/"):
            assert _enabled() is True

    def test_session_key_none_for_anonymous(self, app):
        from Code.routes.pulse_track import _session_key
        with app.test_request_context("/"):
            assert _session_key() is None

    def test_session_key_is_reused_once_set(self, app):
        from flask import session
        from Code.routes.pulse_track import _session_key
        with app.test_request_context("/"):
            session["user_id"] = 1
            first = _session_key()
            assert first and len(first) == 32
            assert _session_key() == first

    def test_session_key_existing_value_kept_without_user(self, app):
        from flask import session
        from Code.routes.pulse_track import _session_key
        with app.test_request_context("/"):
            session["pulse_sid"] = "abc"
            assert _session_key() == "abc"

    def test_page_still_served_when_event_write_explodes(
            self, app, auth_client, pulse_on, monkeypatch):
        from Code.routes import pulse_track

        def boom(*a, **k):
            raise RuntimeError("base indisponible")

        monkeypatch.setattr(pulse_track, "_write", boom)
        r = auth_client.get("/activities/view")
        assert r.status_code == 200

    def test_beat_returns_204_when_write_explodes(
            self, app, auth_client, pulse_on, monkeypatch):
        from Code.routes import pulse_track

        def boom(*a, **k):
            raise RuntimeError("base indisponible")

        monkeypatch.setattr(pulse_track, "_write", boom)
        r = auth_client.post("/pulse/beat", json={"path": "/x"})
        assert r.status_code == 204
        assert r.data == b""

    def test_beat_without_json_body_stores_null_path(
            self, app, auth_client, pulse_on):
        from Code.models.models import UsageBeat
        r = auth_client.post("/pulse/beat", data="pas du json",
                             content_type="text/plain")
        assert r.status_code == 204
        with app.app_context():
            b = UsageBeat.query.order_by(UsageBeat.id.desc()).first()
            assert b is not None
            assert b.path is None

    def test_beat_path_truncated_to_300_chars(self, app, auth_client, pulse_on):
        from Code.models.models import UsageBeat
        auth_client.post("/pulse/beat", json={"path": "/" + "a" * 500})
        with app.app_context():
            b = UsageBeat.query.order_by(UsageBeat.id.desc()).first()
            assert len(b.path) == 300

    def test_anonymous_post_is_logged_without_user(self, app, pulse_on):
        from Code.models.models import UsageEvent
        app.test_client().post("/introuvable-pulse-xyz")
        with app.app_context():
            ev = (UsageEvent.query.filter_by(path="/introuvable-pulse-xyz")
                  .order_by(UsageEvent.id.desc()).first())
            assert ev is not None
            assert ev.user_id is None
            assert ev.kind == "action"

    def test_error_get_is_not_logged_as_view(self, app, auth_client, pulse_on):
        from Code.models.models import UsageEvent
        r = auth_client.get("/introuvable-pulse-get")
        assert r.status_code == 404
        with app.app_context():
            assert UsageEvent.query.filter_by(
                path="/introuvable-pulse-get").count() == 0
