# tests/test_51_stream_sse.py
"""
Route : GET /testpanel/stream/<run_id>  (test_panel.py)
Fonctionnalité : endpoint Server-Sent Events (SSE) qui diffuse la sortie
d'un run pytest en temps réel via le dict en mémoire `_runs`.

Stratégie de test :
  On injecte directement des données dans `_runs` (dict module-level) avant
  chaque requête, ce qui permet de tester le comportement du générateur sans
  attendre le timeout de 5 min (3000 × 0.1 s) que la branche "run_id absent"
  déclencherait.
"""
import json
import threading
import pytest

pytestmark = pytest.mark.stream_sse

# ID fictif utilisé comme clé dans _runs — assez grand pour ne pas collisionner
# avec des run_id créés par les autres tests.
FAKE_RUN_ID = 987654


def _inject(run_id, lines, done=True):
    """Injecte des données dans le dict `_runs` du module test_panel."""
    from Code.routes.test_panel import _runs, _runs_lock
    with _runs_lock:
        _runs[run_id] = {"lines": lines, "done": done}


def _cleanup(run_id):
    """Supprime l'entrée de `_runs` après le test."""
    from Code.routes.test_panel import _runs, _runs_lock
    with _runs_lock:
        _runs.pop(run_id, None)


def _parse_sse(data: bytes) -> list:
    """
    Extrait les valeurs JSON des lignes 'data: ...' d'une réponse SSE brute.
    Retourne la liste des valeurs décodées.
    """
    events = []
    for line in data.decode("utf-8").splitlines():
        if line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                events.append(payload)  # garder brut si invalide
    return events


# ===========================================================================
# 1. Content-Type et en-têtes HTTP
# ===========================================================================

class TestStreamHeaders:

    def setup_method(self):
        _inject(FAKE_RUN_ID, [], done=True)

    def teardown_method(self):
        _cleanup(FAKE_RUN_ID)

    def test_content_type_is_event_stream(self, auth_client):
        """Content-Type retourné est text/event-stream."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        assert "text/event-stream" in r.content_type

    def test_cache_control_no_cache(self, auth_client):
        """En-tête Cache-Control vaut no-cache."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        assert r.headers.get("Cache-Control") == "no-cache"

    def test_x_accel_buffering_no(self, auth_client):
        """En-tête X-Accel-Buffering vaut no (désactive le buffering Nginx)."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        assert r.headers.get("X-Accel-Buffering") == "no"

    def test_status_code_200(self, auth_client):
        """La route retourne 200."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        assert r.status_code == 200


# ===========================================================================
# 2. Run vide terminé — seul [DONE] émis
# ===========================================================================

class TestStreamEmptyDone:

    def setup_method(self):
        _inject(FAKE_RUN_ID, [], done=True)

    def teardown_method(self):
        _cleanup(FAKE_RUN_ID)

    def test_empty_run_emits_done(self, auth_client):
        """Un run sans lignes mais terminé émet uniquement [DONE]."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert "[DONE]" in events

    def test_empty_run_last_event_is_done(self, auth_client):
        """Le dernier événement SSE est toujours [DONE]."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert events[-1] == "[DONE]"

    def test_empty_run_exactly_one_event(self, auth_client):
        """Un run vide émet exactement 1 événement ([DONE])."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert len(events) == 1

    def test_response_body_not_empty(self, auth_client):
        """Le corps de la réponse n'est pas vide."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        assert len(r.data) > 0


# ===========================================================================
# 3. Run avec lignes de sortie
# ===========================================================================

class TestStreamWithLines:

    LINES = ["PASSED test_one\n", "FAILED test_two\n", "ERROR test_three\n"]

    def setup_method(self):
        _inject(FAKE_RUN_ID, self.LINES, done=True)

    def teardown_method(self):
        _cleanup(FAKE_RUN_ID)

    def test_all_lines_emitted(self, auth_client):
        """Toutes les lignes injectées sont émises avant [DONE]."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        for line in self.LINES:
            stripped = line.rstrip("\n")
            assert stripped in events

    def test_last_event_is_done(self, auth_client):
        """[DONE] est toujours le dernier événement, même avec des lignes."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert events[-1] == "[DONE]"

    def test_event_count_equals_lines_plus_done(self, auth_client):
        """Nombre d'événements = nombre de lignes + 1 ([DONE])."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert len(events) == len(self.LINES) + 1

    def test_lines_order_preserved(self, auth_client):
        """Les lignes sont émises dans l'ordre d'injection."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        content_events = events[:-1]  # exclure [DONE]
        expected = [line.rstrip("\n") for line in self.LINES]
        assert content_events == expected

    def test_trailing_newline_stripped(self, auth_client):
        """Les sauts de ligne finaux sont retirés de chaque événement."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        for ev in events:
            if ev != "[DONE]":
                assert not ev.endswith("\n")


# ===========================================================================
# 4. Format SSE — structure des lignes
# ===========================================================================

class TestStreamSseFormat:

    def setup_method(self):
        _inject(FAKE_RUN_ID, ["hello\n"], done=True)

    def teardown_method(self):
        _cleanup(FAKE_RUN_ID)

    def test_each_event_starts_with_data_prefix(self, auth_client):
        """Chaque événement SSE commence par 'data: '."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        raw = r.data.decode("utf-8")
        for line in raw.splitlines():
            if line.strip():
                assert line.startswith("data: "), f"Ligne sans préfixe: {line!r}"

    def test_events_separated_by_double_newline(self, auth_client):
        """Les événements SSE sont séparés par \\n\\n."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        raw = r.data.decode("utf-8")
        assert "\n\n" in raw

    def test_each_payload_is_valid_json(self, auth_client):
        """Chaque payload SSE est du JSON valide."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        raw = r.data.decode("utf-8")
        for line in raw.splitlines():
            if line.startswith("data: "):
                payload = line[len("data: "):]
                try:
                    json.loads(payload)
                except json.JSONDecodeError as exc:
                    pytest.fail(f"Payload JSON invalide: {payload!r} — {exc}")

    def test_payload_types_are_string(self, auth_client):
        """Chaque payload SSE est une chaîne JSON (pas un objet ou un nombre)."""
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        for ev in events:
            assert isinstance(ev, str), f"Type inattendu pour {ev!r}"


# ===========================================================================
# 5. Contenu d'un run réel avec ligne multi-formats
# ===========================================================================

class TestStreamVariousLines:

    def teardown_method(self):
        _cleanup(FAKE_RUN_ID)

    def test_unicode_line_preserved(self, auth_client):
        """Une ligne contenant des caractères Unicode est transmise correctement."""
        _inject(FAKE_RUN_ID, ["résultat — Réussi ✓\n"], done=True)
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert "résultat — Réussi ✓" in events

    def test_empty_line_between_others_handled(self, auth_client):
        """Une ligne vide au milieu de la liste est transmise (chaîne vide)."""
        _inject(FAKE_RUN_ID, ["line1\n", "\n", "line3\n"], done=True)
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert "line1" in events
        assert "" in events
        assert "line3" in events
        assert events[-1] == "[DONE]"

    def test_single_line_run(self, auth_client):
        """Run avec une seule ligne → 2 événements (la ligne + [DONE])."""
        _inject(FAKE_RUN_ID, ["unique\n"], done=True)
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert len(events) == 2
        assert events[0] == "unique"
        assert events[1] == "[DONE]"

    def test_many_lines_all_emitted(self, auth_client):
        """Run avec 50 lignes → 51 événements (50 lignes + [DONE])."""
        lines = [f"line {i}\n" for i in range(50)]
        _inject(FAKE_RUN_ID, lines, done=True)
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert len(events) == 51
        assert events[-1] == "[DONE]"

    def test_line_without_newline_not_stripped_wrongly(self, auth_client):
        """Ligne sans '\\n' de fin : le contenu est transmis tel quel."""
        _inject(FAKE_RUN_ID, ["no-newline"], done=True)
        r = auth_client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert "no-newline" in events


# ===========================================================================
# 6. Accès sans authentification (la route n'a pas de garde login_required)
# ===========================================================================

class TestStreamNoAuth:

    def setup_method(self):
        _inject(FAKE_RUN_ID, ["output\n"], done=True)

    def teardown_method(self):
        _cleanup(FAKE_RUN_ID)

    def test_stream_accessible_without_auth(self, client):
        """Le stream est accessible même sans session — pas de redirection 302."""
        r = client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        assert r.status_code == 200

    def test_stream_no_auth_content_type(self, client):
        """Sans auth, le Content-Type est bien text/event-stream."""
        r = client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        assert "text/event-stream" in r.content_type

    def test_stream_no_auth_done_event(self, client):
        """Sans auth, [DONE] apparaît dans les événements."""
        r = client.get(f"/testpanel/stream/{FAKE_RUN_ID}")
        events = _parse_sse(r.data)
        assert "[DONE]" in events


# ===========================================================================
# 7. Route invalide — run_id non entier
# ===========================================================================

class TestStreamInvalidId:

    def test_string_run_id_returns_404(self, auth_client):
        """Un run_id non entier ('abc') → 404 (Flask ne matche pas la route)."""
        r = auth_client.get("/testpanel/stream/abc")
        assert r.status_code == 404

    def test_float_run_id_returns_404(self, auth_client):
        """Un run_id flottant ('1.5') → 404 (Flask ne matche pas la route)."""
        r = auth_client.get("/testpanel/stream/1.5")
        assert r.status_code == 404
