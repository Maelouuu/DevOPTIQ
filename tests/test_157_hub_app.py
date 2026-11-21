# -*- coding: utf-8 -*-
"""Le hub en marche — `hub/app.py` servi par un client Flask.

`test_124` et `test_156` lisent les modules du hub (courrier, atelier) ; aucun
cas ne faisait encore TOURNER l'application du hub : connexion, verrou des
pages, limitation des tentatives, pont vers le panel, miroir de l'atelier,
sondes d'instances. Ce fichier le fait, sans réseau : chaque appel sortant
(`urlopen`, `panel_client`) est remplacé.

Isolation : un module NEUF par test (`_ATTEMPTS` et `_CACHE` sont des globaux
du module), et les noms nus que `app.py` importe (`atelier`, `courrier`,
`inventaire`…) sont retirés de `sys.modules` après chargement pour ne pas
contaminer d'autres fichiers.

⚠️ Sautés dans l'image bytecode-only, comme `test_124`/`test_156`.
"""
import importlib.util
import io
import json
import os
import socket
import sys
import urllib.error

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = os.path.join(RACINE, "hub")
SRC = os.path.join(HUB, "app.py")
NOMS_NUS = ("atelier", "atelier_modeles", "courrier", "inventaire", "panel_client")
MDP = "mot-de-passe-de-test"


def _charger():
    if not os.path.exists(SRC):
        pytest.skip("hub/ en bytecode — service séparé, sources absentes")
    avant = {n: sys.modules.get(n) for n in NOMS_NUS}
    sys.path.insert(0, HUB)
    try:
        spec = importlib.util.spec_from_file_location("hub_app_test", SRC)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(HUB)
        for n, m in avant.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m
    mod.app.config["TESTING"] = True
    return mod


@pytest.fixture
def hub(monkeypatch):
    monkeypatch.setenv("HUB_PASSWORD", MDP)
    monkeypatch.delenv("HUB_ATELIER_DB", raising=False)
    monkeypatch.delenv("PANEL_BASE", raising=False)
    mod = _charger()
    # Aucune sonde réseau pendant le rendu des pages.
    monkeypatch.setattr(mod, "etats_instances", lambda force=False: {})
    return mod


@pytest.fixture
def anon(hub):
    return hub.app.test_client()


@pytest.fixture
def connecte(hub):
    c = hub.app.test_client()
    with c.session_transaction() as s:
        s["auth"] = True
    return c


class _Reponse:
    def __init__(self, status=200, corps=b""):
        self.status = status
        self._corps = corps

    def read(self):
        return self._corps

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ── Connexion ─────────────────────────────────────────────────────────────
class TestHubConnexion:
    def test_login_get_affiche_le_formulaire(self, anon):
        r = anon.get("/login")
        assert r.status_code == 200
        assert b'name="suite"' in r.data

    def test_login_bons_identifiants_redirige_vers_suite(self, hub, anon):
        r = anon.post("/login", data={"username": hub.HUB_USER, "password": MDP,
                                      "suite": "/outils"})
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/outils")
        with anon.session_transaction() as s:
            assert s.get("auth") is True

    def test_login_suite_externe_ramenee_a_la_racine(self, hub, anon):
        r = anon.post("/login?suite=https://evil.example/x",
                      data={"username": hub.HUB_USER, "password": MDP})
        assert r.status_code == 302
        assert r.headers["Location"] in ("/", "http://localhost/")

    @pytest.mark.parametrize("suite", ["//evil.example/x", "/\\evil.example"])
    def test_login_suite_relative_au_protocole_refusee(self, hub, anon, suite):
        r = anon.post("/login", data={"username": hub.HUB_USER, "password": MDP,
                                      "suite": suite})
        assert r.status_code == 302
        assert r.headers["Location"] in ("/", "http://localhost/")

    def test_login_suite_interne_conservee_avec_requete(self, hub, anon):
        r = anon.post("/login", data={"username": hub.HUB_USER, "password": MDP,
                                      "suite": "/panel/tools?x=1"})
        assert r.headers["Location"].endswith("/panel/tools?x=1")

    def test_login_mauvais_mot_de_passe_reste_sur_la_page(self, hub, anon):
        r = anon.post("/login", data={"username": hub.HUB_USER, "password": "faux"})
        assert r.status_code == 200
        assert "Identifiants incorrects".encode() in r.data
        with anon.session_transaction() as s:
            assert not s.get("auth")

    def test_login_nom_inconnu_refuse(self, anon):
        r = anon.post("/login", data={"username": "inconnu", "password": MDP})
        assert "Identifiants incorrects".encode() in r.data

    def test_login_champs_absents_refuse_sans_erreur(self, anon):
        r = anon.post("/login", data={})
        assert r.status_code == 200
        assert "Identifiants incorrects".encode() in r.data

    def test_login_echec_enregistre_une_tentative(self, hub, anon):
        anon.post("/login", data={"username": "x", "password": "y"},
                  headers={"X-Forwarded-For": "10.0.0.7, 1.1.1.1"})
        assert len(hub._ATTEMPTS.get("10.0.0.7", [])) == 1

    def test_login_bloque_apres_trop_de_tentatives(self, hub, anon):
        ip = {"X-Forwarded-For": "10.9.9.9"}
        for _ in range(hub._MAX_TRIES):
            anon.post("/login", data={"username": "x", "password": "y"}, headers=ip)
        # Même les BONS identifiants sont refusés pendant le verrou.
        r = anon.post("/login", data={"username": hub.HUB_USER, "password": MDP},
                      headers=ip)
        assert r.status_code == 200
        assert "Trop de tentatives".encode() in r.data

    def test_verrou_ne_touche_pas_une_autre_ip(self, hub, anon):
        for _ in range(hub._MAX_TRIES):
            anon.post("/login", data={"username": "x", "password": "y"},
                      headers={"X-Forwarded-For": "10.1.1.1"})
        r = anon.post("/login", data={"username": hub.HUB_USER, "password": MDP},
                      headers={"X-Forwarded-For": "10.2.2.2"})
        assert r.status_code == 302

    def test_tentatives_anciennes_expirent(self, hub):
        hub._ATTEMPTS["ip"] = [0.0] * (hub._MAX_TRIES + 3)
        assert hub._rate_limited("ip") is False
        assert hub._ATTEMPTS["ip"] == []

    def test_logout_vide_la_session(self, connecte):
        r = connecte.get("/logout")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
        with connecte.session_transaction() as s:
            assert "auth" not in s


class TestHubIdentifiants:
    def test_mot_de_passe_en_clair_prioritaire(self, hub):
        assert hub._check_credentials(hub.HUB_USER, MDP) is True
        assert hub._check_credentials(hub.HUB_USER, MDP + "x") is False

    def test_sans_variable_le_hash_par_defaut_refuse_un_faux(self, hub, monkeypatch):
        monkeypatch.delenv("HUB_PASSWORD", raising=False)
        monkeypatch.delenv("HUB_PASSWORD_HASH", raising=False)
        assert hub._check_credentials(hub.HUB_USER, MDP) is False

    def test_hash_d_environnement_utilise(self, hub, monkeypatch):
        from werkzeug.security import generate_password_hash
        monkeypatch.delenv("HUB_PASSWORD", raising=False)
        monkeypatch.setenv("HUB_PASSWORD_HASH", generate_password_hash("h4sh"))
        assert hub._check_credentials(hub.HUB_USER, "h4sh") is True

    def test_second_compte_par_sa_variable(self, hub, monkeypatch):
        monkeypatch.setenv("HUB_PASSWORD_HG", "autre")
        assert hub._check_credentials("Hubert_Grandjean", "autre") is True
        # Le mot de passe d'un compte n'ouvre pas l'autre.
        assert hub._check_credentials("Hubert_Grandjean", MDP) is False

    def test_nom_et_mdp_none_ne_levent_pas(self, hub):
        assert hub._check_credentials(None, None) is False


# ── Verrou des pages ──────────────────────────────────────────────────────
PAGES_HTML = ["/", "/instances", "/infrastructure", "/documentation", "/outils",
              "/ci", "/courrier", "/atelier", "/panel"]


class TestHubVerrou:
    @pytest.mark.parametrize("chemin", PAGES_HTML)
    def test_page_sans_session_redirige_vers_login(self, anon, chemin):
        r = anon.get(chemin)
        assert r.status_code == 302
        assert "/login?suite=" in r.headers["Location"]

    @pytest.mark.parametrize("chemin", ["/api/etat", "/api/panel/pages",
                                        "/api/atelier/etat", "/api/courrier/boite"])
    def test_api_sans_session_repond_401(self, anon, chemin):
        assert anon.get(chemin).status_code == 401

    def test_lancer_sans_session_401(self, anon):
        assert anon.post("/api/panel/lancer", json={}).status_code == 401

    def test_health_public(self, anon):
        r = anon.get("/health")
        assert r.status_code == 200 and r.data == b"ok"

    def test_entetes_noindex_et_referrer(self, anon):
        r = anon.get("/health")
        assert r.headers["X-Robots-Tag"] == "noindex, nofollow"
        assert r.headers["Referrer-Policy"] == "no-referrer"


class TestHubPages:
    @pytest.mark.parametrize("chemin", PAGES_HTML)
    def test_page_connectee_rendue(self, connecte, chemin):
        r = connecte.get(chemin)
        assert r.status_code == 200
        assert b"<html" in r.data.lower()

    def test_documents_absents_404(self, connecte):
        # `_docs/` n'est copié qu'au build de l'image du hub.
        for chemin in ("/doc/refonte", "/assets/inexistant.png"):
            assert connecte.get(chemin).status_code == 404

    def test_doc_refonte_rend_le_markdown(self, hub, connecte, tmp_path, monkeypatch):
        (tmp_path / "refonte_competences_v1_1.md").write_text("# Titre refonte",
                                                               encoding="utf-8")
        monkeypatch.setattr(hub, "_DOCS", str(tmp_path))
        r = connecte.get("/doc/refonte")
        assert r.status_code == 200
        assert b"Titre refonte" in r.data

    def test_doc_et_guide_servis_depuis_docs(self, hub, connecte, tmp_path, monkeypatch):
        (tmp_path / "doc_technique.html").write_text("<p>tech</p>")
        (tmp_path / "guide.html").write_text("<p>guide</p>")
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "a.txt").write_text("media")
        monkeypatch.setattr(hub, "_DOCS", str(tmp_path))
        assert connecte.get("/doc").data == b"<p>tech</p>"
        assert connecte.get("/guide").data == b"<p>guide</p>"
        assert connecte.get("/assets/a.txt").data == b"media"

    def test_api_etat_transmet_force(self, hub, connecte, monkeypatch):
        vus = []
        monkeypatch.setattr(hub, "etats_instances",
                            lambda force=False: vus.append(force) or {"prod": {"etat": "en ligne"}})
        assert connecte.get("/api/etat?force=1").get_json() == {"prod": {"etat": "en ligne"}}
        connecte.get("/api/etat")
        assert vus == [True, False]


class TestHubToiles:
    def test_toiles_filtre_par_extension(self, hub, tmp_path, monkeypatch):
        for f in ("accueil.jpg", "ci.PNG", "LISEZ-MOI.txt", "outils.webp", "outils.png"):
            (tmp_path / f).write_bytes(b"")
        monkeypatch.setattr(hub, "_TOILES", str(tmp_path))
        t = hub.toiles_disponibles()
        assert t["accueil"] == "accueil.jpg"
        assert t["ci"] == "ci.PNG"
        assert "LISEZ-MOI" not in t
        assert t["outils"] in ("outils.webp", "outils.png")

    def test_toiles_dossier_absent_rend_vide(self, hub, tmp_path, monkeypatch):
        monkeypatch.setattr(hub, "_TOILES", str(tmp_path / "absent"))
        assert hub.toiles_disponibles() == {}


# ── Sondes d'instances ────────────────────────────────────────────────────
class TestHubSondes:
    INST = {"cle": "x", "url": "https://x.example/", "sonde": "/login"}

    def _urlopen(self, hub, monkeypatch, effet):
        def faux(req, timeout=None):
            if isinstance(effet, BaseException):
                raise effet
            return effet
        monkeypatch.setattr(hub.urllib.request, "urlopen", faux)

    @pytest.mark.parametrize("code,etat", [(200, "en ligne"), (302, "en ligne")])
    def test_sonde_reponse_ok(self, hub, monkeypatch, code, etat):
        self._urlopen(hub, monkeypatch, _Reponse(code))
        r = hub._sonder(self.INST)
        assert r["etat"] == etat and r["code"] == code and isinstance(r["ms"], int)

    @pytest.mark.parametrize("code,etat", [(404, "dégradé"), (503, "en erreur")])
    def test_sonde_http_error_classee(self, hub, monkeypatch, code, etat):
        self._urlopen(hub, monkeypatch,
                      urllib.error.HTTPError("u", code, "m", {}, io.BytesIO()))
        r = hub._sonder(self.INST)
        assert r["etat"] == etat and r["code"] == code

    def test_sonde_timeout_en_veille(self, hub, monkeypatch):
        self._urlopen(hub, monkeypatch, socket.timeout())
        assert hub._sonder(self.INST)["etat"] == "en veille"

    def test_sonde_urlerror_timeout_en_veille(self, hub, monkeypatch):
        self._urlopen(hub, monkeypatch, urllib.error.URLError(socket.timeout()))
        assert hub._sonder(self.INST)["etat"] == "en veille"

    def test_sonde_autre_erreur_injoignable(self, hub, monkeypatch):
        self._urlopen(hub, monkeypatch, urllib.error.URLError("dns"))
        assert hub._sonder(self.INST) == {"etat": "injoignable", "code": None, "ms": None}

    def test_sonde_construit_l_url(self, hub, monkeypatch):
        vues = []

        def faux(req, timeout=None):
            vues.append((req.full_url, timeout))
            return _Reponse(200)
        monkeypatch.setattr(hub.urllib.request, "urlopen", faux)
        hub._sonder(self.INST)
        assert vues == [("https://x.example/login", hub._DELAI_SONDE_S)]

    def _etats_reels(self):
        # La fixture `hub` neutralise `etats_instances` ; on reprend l'original.
        mod = _charger()
        return mod

    def test_etats_instances_sonde_chaque_instance_et_cache(self, monkeypatch):
        mod = self._etats_reels()
        appels = []
        monkeypatch.setattr(mod, "_sonder",
                            lambda i: appels.append(i["cle"]) or {"etat": "en ligne"})
        e1 = mod.etats_instances()
        assert set(e1) == {i["cle"] for i in mod.inventaire.INSTANCES}
        n = len(appels)
        mod.etats_instances()                 # dans le TTL : pas de nouvelle sonde
        assert len(appels) == n
        mod.etats_instances(force=True)
        assert len(appels) == 2 * n

    def test_etats_instances_sonde_qui_leve_injoignable(self, monkeypatch):
        mod = self._etats_reels()

        def boom(i):
            raise RuntimeError("x")
        monkeypatch.setattr(mod, "_sonder", boom)
        etats = mod.etats_instances(force=True)
        assert all(v["etat"] == "injoignable" for v in etats.values())


# ── Pont vers le panel ────────────────────────────────────────────────────
class TestHubPanelRoutes:
    PAGE = {"slug": "tools", "titre": "Outils", "fichier": "tests/test_11_tools.py",
            "fiabilite": 92, "description": "d", "verts": 2, "rouges": 1,
            "total": 3, "marqueur": "tools",
            "cas": [{"nom": "test_a", "classe": "T", "statut": "passed",
                     "quand": "2026-11-20T10:00:00"}]}

    def test_panel_page_rendue(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.panel_client, "page", lambda slug: dict(self.PAGE))
        r = connecte.get("/panel/tools")
        assert r.status_code == 200
        assert b"test_a" in r.data and b"92" in r.data

    def test_panel_page_instance_en_erreur_502(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.panel_client, "page", lambda slug: {"erreur": "injoignable"})
        assert connecte.get("/panel/tools").status_code == 502

    def test_api_pages_runs_etat_page_relayes(self, hub, connecte, monkeypatch):
        pc = hub.panel_client
        monkeypatch.setattr(pc, "pages", lambda: {"pages": [1]})
        monkeypatch.setattr(pc, "runs", lambda limite=20: {"limite": limite})
        monkeypatch.setattr(pc, "etat", lambda: {"en_cours": None})
        monkeypatch.setattr(pc, "page", lambda slug: {"slug": slug})
        assert connecte.get("/api/panel/pages").get_json() == {"pages": [1]}
        assert connecte.get("/api/panel/runs?limit=5").get_json() == {"limite": 5}
        assert connecte.get("/api/panel/runs").get_json() == {"limite": 20}
        assert connecte.get("/api/panel/etat").get_json() == {"en_cours": None}
        assert connecte.get("/api/panel/page/abc").get_json() == {"slug": "abc"}

    def test_api_lancer_ok(self, hub, connecte, monkeypatch):
        vues = []
        monkeypatch.setattr(hub.panel_client, "lancer",
                            lambda p: vues.append(p) or (True, {"run_id": 7}))
        r = connecte.post("/api/panel/lancer", json={"portee": "page:tools"})
        assert r.status_code == 200
        assert r.get_json() == {"run_id": 7, "ok": True}
        connecte.post("/api/panel/lancer")           # sans corps → 'all'
        assert vues == ["page:tools", "all"]

    def test_api_lancer_echec_502(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.panel_client, "lancer",
                            lambda p: (False, {"message": "non"}))
        r = connecte.post("/api/panel/lancer", json={})
        assert r.status_code == 502 and r.get_json()["ok"] is False

    def test_api_run_statut(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.panel_client, "statut", lambda i: {"id": i})
        assert connecte.get("/api/panel/run/12").get_json() == {"id": 12}
        assert connecte.get("/api/panel/run/abc").status_code == 404


class TestHubPanelClient:
    """`panel_client` : l'appel inter-services, sans réseau."""

    def _pc(self, hub, monkeypatch, effet, vus=None):
        pc = hub.panel_client

        def faux(req, timeout=None):
            if vus is not None:
                vus.append((req.full_url, req.get_method(), req.data, timeout))
            if isinstance(effet, BaseException):
                raise effet
            return effet
        monkeypatch.setattr(pc.urllib.request, "urlopen", faux)
        return pc

    def test_base_par_defaut_staging(self, hub):
        pc = hub.panel_client
        staging = [i for i in hub.inventaire.INSTANCES if i["cle"] == "staging"][0]
        assert pc._base() == staging["url"].rstrip("/")
        assert pc.url_panel() == staging["url"].rstrip("/") + "/testpanel/"

    def test_base_forcee_par_panel_base(self, hub, monkeypatch):
        monkeypatch.setenv("PANEL_BASE", " http://127.0.0.1:5000/ ")
        assert hub.panel_client._base() == "http://127.0.0.1:5000"

    def test_base_vide_sans_staging(self, hub, monkeypatch):
        monkeypatch.setattr(hub.panel_client.inventaire, "INSTANCES", [])
        assert hub.panel_client._base() == ""

    def test_appel_decode_le_json(self, hub, monkeypatch):
        vus = []
        pc = self._pc(hub, monkeypatch, _Reponse(200, b'{"a": 1}'), vus)
        assert pc.etat() == {"a": 1}
        url, methode, corps, delai = vus[0]
        assert url.endswith("/testpanel/api/etat") and methode == "GET"
        assert corps is None and delai == pc.DELAI

    def test_appel_corps_vide_rend_dict_vide(self, hub, monkeypatch):
        pc = self._pc(hub, monkeypatch, _Reponse(200, b""))
        assert pc.pages() == {}

    def test_appel_http_error(self, hub, monkeypatch):
        pc = self._pc(hub, monkeypatch,
                      urllib.error.HTTPError("u", 404, "m", {}, io.BytesIO()))
        assert pc.page("x") == {"erreur": "http_404"}

    def test_appel_injoignable(self, hub, monkeypatch):
        pc = self._pc(hub, monkeypatch, OSError("down"))
        assert pc.runs() == {"erreur": "injoignable"}

    def test_runs_et_statut_chemins(self, hub, monkeypatch):
        vus = []
        pc = self._pc(hub, monkeypatch, _Reponse(200, b"{}"), vus)
        pc.runs("7")
        pc.statut("42")
        assert vus[0][0].endswith("/testpanel/api/runs?limit=7")
        assert vus[1][0].endswith("/testpanel/run/42/status")

    def test_lancer_post_corps_vide_explicite(self, hub, monkeypatch):
        vus = []
        pc = self._pc(hub, monkeypatch, _Reponse(200, b'{"run_id": 3}'), vus)
        assert pc.lancer() == (True, {"run_id": 3})
        url, methode, corps, _ = vus[0]
        # Sans corps explicite, le frontend *.run.app renvoie 411.
        assert url.endswith("/testpanel/run/all") and methode == "POST" and corps == b""

    def test_lancer_une_page(self, hub, monkeypatch):
        vus = []
        pc = self._pc(hub, monkeypatch, _Reponse(200, b'{"run_id": 4}'), vus)
        assert pc.lancer("page:tools")[0] is True
        assert vus[0][0].endswith("/testpanel/run/page/tools")

    @pytest.mark.parametrize("effet,attendu", [
        (OSError("x"), "ne répond pas"),
        (urllib.error.HTTPError("u", 404, "m", {}, io.BytesIO()), "pas actif"),
        (urllib.error.HTTPError("u", 500, "m", {}, io.BytesIO()), "http_500"),
    ])
    def test_lancer_erreurs_message_lisible(self, hub, monkeypatch, effet, attendu):
        pc = self._pc(hub, monkeypatch, effet)
        ok, charge = pc.lancer()
        assert ok is False and attendu in charge["message"]

    def test_lancer_sans_run_id(self, hub, monkeypatch):
        pc = self._pc(hub, monkeypatch, _Reponse(200, b'{"autre": 1}'))
        ok, charge = pc.lancer()
        assert ok is False and "inattendue" in charge["message"]


# ── Courrier (routes) ─────────────────────────────────────────────────────
class TestHubCourrierRoutes:
    def test_reset_borne_les_jours_et_signale_configuration(self, hub, connecte, monkeypatch):
        c = hub.courrier
        vus = []
        monkeypatch.setattr(c, "load_sources", lambda: [])
        monkeypatch.setattr(c, "stats_reset", lambda b, j: vus.append(j) or [])
        monkeypatch.setattr(c, "cache", lambda cle, calc, force=False: calc())
        for q, j in (("", 30), ("?jours=0", 1), ("?jours=999", 180), ("?jours=45", 45)):
            d = connecte.get("/api/courrier/reset" + q).get_json()
            assert d["jours"] == j and d["configure"] is False
        assert vus == [30, 1, 180, 45]

    def test_reset_force_transmis_au_cache(self, hub, connecte, monkeypatch):
        c = hub.courrier
        forces = []
        monkeypatch.setattr(c, "load_sources", lambda: [{"nom": "a"}])
        monkeypatch.setattr(c, "cache",
                            lambda cle, calc, force=False: forces.append((cle, force)) or [])
        d = connecte.get("/api/courrier/reset?force=1").get_json()
        assert d["configure"] is True
        assert forces == [("reset", True)]

    def test_boite_relayee(self, hub, connecte, monkeypatch):
        c = hub.courrier
        monkeypatch.setattr(c, "cache",
                            lambda cle, calc, force=False: {"cle": cle, "force": force})
        assert connecte.get("/api/courrier/boite").get_json() == {"cle": "boite", "force": False}
        assert connecte.get("/api/courrier/boite?force=1").get_json()["force"] is True


# ── Atelier (routes) ──────────────────────────────────────────────────────
DATA_URL = "data:image/png;base64,iVBORw0KGgo="


class TestHubAtelierSansMiroir:
    """Sans `HUB_ATELIER_DB`, aucune route ne lève : la toile vit dans le navigateur."""

    def test_etat_sans_miroir(self, connecte):
        assert connecte.get("/api/atelier/etat").get_json()["miroir"] is False

    def test_toile_get(self, connecte):
        assert connecte.get("/api/atelier/toile/principale").status_code == 200

    @pytest.mark.parametrize("methode", ["put", "post"])
    def test_toile_ecriture_sans_miroir_200(self, connecte, methode):
        r = getattr(connecte, methode)("/api/atelier/toile/principale",
                                       json={"contenu": {"noeuds": []}})
        assert r.status_code == 200

    def test_modeles_catalogue(self, hub, connecte):
        assert connecte.get("/api/atelier/modeles").get_json() == \
            json.loads(json.dumps(hub.atelier_modeles.catalogue()))

    def test_modele_connu_et_inconnu(self, connecte):
        assert connecte.get("/api/atelier/modele/pages").get_json()["cle"] == "pages"
        assert connecte.get("/api/atelier/modele/inexistant").status_code == 404

    def test_pieces_connues_sans_miroir(self, connecte):
        d = connecte.post("/api/atelier/pieces", json={"ids": ["a", "b"]}).get_json()
        assert d["miroir"] is False and isinstance(d["connues"], list)

    def test_pieces_sans_corps(self, connecte):
        assert connecte.post("/api/atelier/pieces").status_code == 200

    def test_piece_absente_404(self, connecte):
        assert connecte.get("/api/atelier/piece/abc").status_code == 404

    def test_piece_data_url_invalide_400(self, connecte):
        r = connecte.put("/api/atelier/piece/abc", json={"mime": "image/png",
                                                         "donnees": "pas-une-data-url"})
        assert r.status_code == 400 and r.get_json()["ok"] is False

    def test_piece_valide_sans_miroir_200(self, connecte):
        r = connecte.put("/api/atelier/piece/abc", json={"mime": "image/png",
                                                         "donnees": DATA_URL})
        assert r.status_code == 200


class TestHubAtelierCodesRetour:
    """Les codes que la route choisit selon la réponse du module."""

    def test_conflit_409(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.atelier, "ecrire",
                            lambda cle, contenu, rev: {"ok": False, "conflit": True, "rev": 9})
        r = connecte.put("/api/atelier/toile/principale", json={"contenu": {}, "rev": 1})
        assert r.status_code == 409 and r.get_json()["rev"] == 9

    def test_echec_avec_miroir_502(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.atelier, "ecrire", lambda *a: {"ok": False})
        monkeypatch.setattr(hub.atelier, "disponible", lambda env=None: True)
        assert connecte.put("/api/atelier/toile/p", json={}).status_code == 502

    def test_ecriture_transmet_contenu_et_rev(self, hub, connecte, monkeypatch):
        vus = []
        monkeypatch.setattr(hub.atelier, "ecrire",
                            lambda cle, contenu, rev: vus.append((cle, contenu, rev)) or {"ok": True})
        connecte.post("/api/atelier/toile/t1", json={"contenu": {"a": 1}, "rev": 4})
        assert vus == [("t1", {"a": 1}, 4)]

    def test_piece_echec_avec_miroir_502(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.atelier, "piece_ecrire", lambda *a: {"ok": False})
        monkeypatch.setattr(hub.atelier, "disponible", lambda env=None: True)
        r = connecte.put("/api/atelier/piece/p1", json={"mime": "image/png",
                                                        "donnees": DATA_URL})
        assert r.status_code == 502

    def test_piece_lue_relayee(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.atelier, "piece_lire",
                            lambda i: {"id": i, "mime": "image/png", "donnees": DATA_URL})
        assert connecte.get("/api/atelier/piece/p9").get_json()["id"] == "p9"

    def test_pieces_connues_transmet_les_ids(self, hub, connecte, monkeypatch):
        monkeypatch.setattr(hub.atelier, "pieces_connues", lambda ids: [i for i in ids if i == "b"])
        monkeypatch.setattr(hub.atelier, "disponible", lambda env=None: True)
        d = connecte.post("/api/atelier/pieces", json={"ids": ["a", "b"]}).get_json()
        assert d == {"connues": ["b"], "miroir": True}
