# -*- coding: utf-8 -*-
"""Couverture résiduelle des modules utilitaires transverses.

Page : Modules utilitaires (console, IA, prompts, accès, porte, paliers)

- `Code/logstream.py` : la console serveur ne doit jamais casser l'app —
  sortie d'origine en panne, fichier impossible à ouvrir, troncature.
- `Code/ai_client.py` / `Code/ai_key.py` : choix du fournisseur IA, du
  modèle, construction du client, masquage et effacement de la clé.
- `Code/prompts/__init__.py` : catalogue clair absent → bundle chiffré,
  avec ou sans clé, clé fausse, prompt manquant.
- `Code/security.py` / `Code/extensions.py` : replis silencieux.
- `Code/competences_acces.py` : garde-fous sur acteur/cible absents.
- `Code/ecriture.py` : redirection d'une navigation anonyme, carto active
  illisible, geste non rejouable, trace des refus.
- `Code/mot_de_passe.py` : lien déjà utilisé / expiré, purge.
- `Code/roles_permanents.py` : diagramme illisible, reprise en erreur.
- `Code/paliers.py` : bornes des calculs et liste des sessions.

Chaque test est autonome : données dédiées nettoyées, monkeypatch restauré
par pytest, fichiers dans `tmp_path`.
"""
import io
import json
import logging
import sqlite3
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from Code.extensions import db


class _Casse:
    """Un « modèle » dont toute requête lève : simule une table absente."""

    class _Q:
        def __getattr__(self, _nom):
            raise RuntimeError("table absente")

    query = _Q()


# ══════════════════════════════════════════════════════════════════════════
#  logstream.py
# ══════════════════════════════════════════════════════════════════════════

class _SortieEnPanne:
    def write(self, _d):
        raise IOError("stdout fermé")

    def flush(self):
        raise IOError("stdout fermé")

    encoding = "utf-8"


class TestLogstream:

    @pytest.fixture
    def journal(self, tmp_path, monkeypatch):
        from Code import logstream
        chemin = tmp_path / "serveur.log"
        monkeypatch.setattr(logstream, "LOG_PATH", str(chemin))
        return chemin

    def test_tee_ecrit_au_journal_meme_si_la_sortie_d_origine_casse(self, journal):
        from Code.logstream import _Tee
        tee = _Tee(_SortieEnPanne())
        tee.write("ligne malgré tout\n")
        assert journal.read_text(encoding="utf-8") == "ligne malgré tout\n"

    def test_tee_flush_avale_l_erreur_de_la_sortie_d_origine(self, journal):
        from Code.logstream import _Tee
        _Tee(_SortieEnPanne()).flush()   # ne lève pas

    def test_tee_relaie_les_attributs_de_la_sortie_d_origine(self):
        from Code.logstream import _Tee
        assert _Tee(_SortieEnPanne()).encoding == "utf-8"

    def test_tee_n_ecrit_rien_pour_une_chaine_vide(self, journal):
        from Code.logstream import _Tee
        _Tee(io.StringIO()).write("")
        assert not journal.exists()

    def test_append_decode_les_octets(self, journal):
        from Code.logstream import _append
        _append("é\n".encode("utf-8"))
        assert journal.read_text(encoding="utf-8") == "é\n"

    def test_fichier_trop_gros_est_tronque_en_gardant_la_fin(self, journal, monkeypatch):
        from Code import logstream
        monkeypatch.setattr(logstream, "MAX_BYTES", 20)
        monkeypatch.setattr(logstream, "KEEP_BYTES", 8)
        logstream._append("A" * 15)
        logstream._append("B" * 10)
        assert journal.read_bytes() == b"BBBBBBBB"

    def test_chemin_inutilisable_n_empeche_pas_d_ecrire(self, tmp_path, monkeypatch):
        from Code import logstream
        monkeypatch.setattr(logstream, "LOG_PATH", str(tmp_path))   # un dossier
        logstream._append("perdu mais sans lever\n")

    def test_handler_dont_le_format_casse_ne_leve_pas(self, journal):
        from Code.logstream import _FileHandler

        class _Fmt(logging.Formatter):
            def format(self, record):
                raise ValueError("format cassé")

        h = _FileHandler()
        h.setFormatter(_Fmt())
        h.emit(logging.makeLogRecord({"msg": "x"}))
        assert not journal.exists()

    def test_handler_ecrit_la_ligne_formatee(self, journal):
        from Code.logstream import _FileHandler
        h = _FileHandler()
        h.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        h.emit(logging.makeLogRecord({"msg": "bonjour", "levelname": "INFO"}))
        assert journal.read_text(encoding="utf-8") == "INFO bonjour\n"

    def test_init_est_idempotent(self, monkeypatch):
        from Code import logstream
        monkeypatch.setattr(logstream, "_initialized", True)
        avant = sys.stdout
        logstream.init_logstream()
        assert sys.stdout is avant

    def test_init_branche_stdout_stderr_et_le_logging(self, journal, monkeypatch):
        from Code import logstream
        monkeypatch.setattr(logstream, "_initialized", False)
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        monkeypatch.setattr(sys, "stderr", io.StringIO())
        racine = logging.getLogger()
        avant = list(racine.handlers)
        try:
            logstream.init_logstream()
            assert isinstance(sys.stdout, logstream._Tee)
            assert isinstance(sys.stderr, logstream._Tee)
            nouveaux = [h for h in racine.handlers if h not in avant]
            assert len(nouveaux) == 1 and isinstance(nouveaux[0], logstream._FileHandler)
        finally:
            for h in list(racine.handlers):
                if h not in avant:
                    racine.removeHandler(h)

    def test_tail_fichier_absent(self, journal):
        from Code.logstream import tail
        assert tail() == ("", 0, 0)

    def test_tail_offset_au_dela_de_la_taille_repart_du_debut(self, journal):
        from Code.logstream import tail
        journal.write_text("abcdef", encoding="utf-8")
        texte, offset, taille = tail(offset=999)
        assert (texte, offset, taille) == ("abcdef", 6, 6)

    def test_tail_depuis_un_offset_rend_la_suite(self, journal):
        from Code.logstream import tail
        journal.write_text("abcdef", encoding="utf-8")
        assert tail(offset=4) == ("ef", 6, 6)

    def test_tail_sans_offset_borne_la_lecture_a_la_fin(self, journal):
        from Code.logstream import tail
        journal.write_text("0123456789", encoding="utf-8")
        assert tail(offset=0, max_bytes=3) == ("789", 10, 10)

    def test_tail_lecture_impossible_rend_vide_sans_bouger(self, tmp_path, monkeypatch):
        from Code import logstream
        monkeypatch.setattr(logstream, "LOG_PATH", str(tmp_path))   # un dossier
        texte, offset, _taille = logstream.tail(offset=0)
        assert texte == "" and offset == 0


# ══════════════════════════════════════════════════════════════════════════
#  ai_client.py
# ══════════════════════════════════════════════════════════════════════════

class TestAiClient:

    @pytest.fixture
    def cles(self, monkeypatch):
        from Code import ai_client
        etat = {"anthropic": None, "openai": None}
        monkeypatch.setattr(ai_client, "get_anthropic_key", lambda: etat["anthropic"])
        monkeypatch.setattr(ai_client, "get_openai_key", lambda: etat["openai"])
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        monkeypatch.delenv("AI_MODEL", raising=False)
        return etat

    def test_fournisseur_force_anthropic(self, cles, monkeypatch):
        from Code.ai_client import resolve_provider
        cles["anthropic"], cles["openai"] = "sk-ant", "sk-oai"
        monkeypatch.setenv("AI_PROVIDER", " Anthropic ")
        assert resolve_provider() == ("anthropic", "sk-ant")

    def test_fournisseur_force_openai_meme_avec_une_cle_claude(self, cles, monkeypatch):
        from Code.ai_client import resolve_provider
        cles["anthropic"], cles["openai"] = "sk-ant", "sk-oai"
        monkeypatch.setenv("AI_PROVIDER", "openai")
        assert resolve_provider() == ("openai", "sk-oai")

    def test_auto_prefere_claude_des_qu_une_cle_existe(self, cles):
        from Code.ai_client import resolve_provider
        cles["anthropic"], cles["openai"] = "sk-ant", "sk-oai"
        assert resolve_provider() == ("anthropic", "sk-ant")

    def test_auto_retombe_sur_openai_sans_cle_claude(self, cles):
        from Code.ai_client import resolve_provider
        cles["openai"] = "sk-oai"
        assert resolve_provider() == ("openai", "sk-oai")

    def test_modele_force_par_l_environnement(self, cles, monkeypatch):
        from Code.ai_client import ai_model
        monkeypatch.setenv("AI_MODEL", "  mon-modele  ")
        assert ai_model("openai") == "mon-modele"

    def test_modele_deduit_du_fournisseur_resolu(self, cles):
        from Code.ai_client import DEFAULT_MODELS, ai_model
        cles["anthropic"] = "sk-ant"
        assert ai_model() == DEFAULT_MODELS["anthropic"]

    def test_fournisseur_inconnu_prend_le_modele_openai(self, cles):
        from Code.ai_client import DEFAULT_MODELS, ai_model
        assert ai_model("mistral") == DEFAULT_MODELS["openai"]

    def test_sans_cle_aucun_client(self, cles):
        from Code.ai_client import NO_KEY_MSG, make_ai_client
        assert make_ai_client() == (None, None, NO_KEY_MSG)

    def test_client_claude_pointe_sur_le_point_d_acces_anthropic(self, cles, monkeypatch):
        import openai
        from Code.ai_client import ANTHROPIC_OPENAI_BASE, DEFAULT_MODELS, make_ai_client
        vus = {}

        class _Faux:
            def __init__(self, **kw):
                vus.update(kw)

        monkeypatch.setattr(openai, "OpenAI", _Faux)
        cles["anthropic"] = "sk-ant"
        client, modele, err = make_ai_client(timeout=12)
        assert isinstance(client, _Faux) and err is None
        assert modele == DEFAULT_MODELS["anthropic"]
        assert vus == {"api_key": "sk-ant", "base_url": ANTHROPIC_OPENAI_BASE, "timeout": 12}

    def test_client_openai_sans_base_url_ni_timeout(self, cles, monkeypatch):
        import openai
        from Code.ai_client import make_ai_client
        vus = {}

        class _Faux:
            def __init__(self, **kw):
                vus.update(kw)

        monkeypatch.setattr(openai, "OpenAI", _Faux)
        cles["openai"] = "sk-oai"
        _c, modele, err = make_ai_client()
        assert err is None and modele == "gpt-4o-mini"
        assert vus == {"api_key": "sk-oai"}

    def test_echec_de_construction_rend_le_message(self, cles, monkeypatch):
        import openai
        from Code.ai_client import make_ai_client

        def _boum(**_kw):
            raise RuntimeError("clé malformée")

        monkeypatch.setattr(openai, "OpenAI", _boum)
        cles["openai"] = "sk-oai"
        assert make_ai_client() == (None, None, "clé malformée")


# ══════════════════════════════════════════════════════════════════════════
#  ai_key.py
# ══════════════════════════════════════════════════════════════════════════

class TestAiKey:

    def test_table_des_reglages_illisible_on_retombe_sur_l_environnement(
            self, app, monkeypatch):
        from Code import ai_key
        from Code.models import models
        monkeypatch.setattr(models, "AppSetting", _Casse)
        monkeypatch.setenv("OPENAI_API_KEY", "  sk-env  ")
        with app.app_context():
            assert ai_key._setting(ai_key._SETTING_KEY) is None
            assert ai_key.get_openai_key() == "sk-env"

    def test_cle_anthropic_par_l_ancien_nom_de_variable(self, monkeypatch):
        from Code import ai_key
        monkeypatch.setattr(ai_key, "_setting", lambda _k: None)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_KEY", "sk-ancien")
        assert ai_key.get_anthropic_key() == "sk-ancien"

    def test_effacer_la_cle_supprime_la_ligne(self, app, monkeypatch):
        from Code import ai_key
        from Code.models.models import AppSetting
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with app.app_context():
            ligne = db.session.get(AppSetting, ai_key._SETTING_KEY)
            avant = ligne.value if ligne else None
            try:
                ai_key.set_openai_key("sk-t142-premiere")
                ai_key.set_openai_key("sk-t142-seconde")
                assert ai_key.get_openai_key() == "sk-t142-seconde"
                ai_key.set_openai_key("   ")
                assert db.session.get(AppSetting, ai_key._SETTING_KEY) is None
                assert ai_key.get_openai_key() is None
            finally:
                if avant is not None:
                    ai_key.set_openai_key(avant)

    def test_effacer_une_cle_absente_ne_leve_pas(self, app):
        from Code import ai_key
        from Code.models.models import AppSetting
        with app.app_context():
            ligne = db.session.get(AppSetting, ai_key._SETTING_KEY)
            avant = ligne.value if ligne else None
            try:
                ai_key.set_openai_key("")
                ai_key.set_openai_key("")
                assert db.session.get(AppSetting, ai_key._SETTING_KEY) is None
            finally:
                if avant is not None:
                    ai_key.set_openai_key(avant)

    @pytest.mark.parametrize("cle, attendu", [
        (None, None),
        ("", None),
        ("sk-123", "sk" + "•" * 8),
        ("sk-proj-abcdefghij1234", "sk-proj" + "•" * 12 + "1234"),
    ])
    def test_masquage(self, cle, attendu):
        from Code.ai_key import mask_key
        assert mask_key(cle) == attendu


# ══════════════════════════════════════════════════════════════════════════
#  prompts/__init__.py
# ══════════════════════════════════════════════════════════════════════════

class TestPromptsBundle:

    @pytest.fixture
    def sans_catalogue(self, monkeypatch, tmp_path):
        """Simule l'image client : catalog.py absent, bundle dans tmp_path."""
        from Code import prompts
        monkeypatch.setitem(sys.modules, "Code.prompts.catalog", None)
        monkeypatch.setattr(prompts, "_store", None)
        monkeypatch.setattr(prompts, "_ENC_PATH", str(tmp_path / "prompts.enc"))
        monkeypatch.delenv("PROMPTS_KEY", raising=False)
        return tmp_path / "prompts.enc"

    def _chiffrer(self, chemin, contenu):
        from cryptography.fernet import Fernet
        cle = Fernet.generate_key()
        chemin.write_bytes(Fernet(cle).encrypt(json.dumps(contenu).encode()))
        return cle.decode()

    def test_catalogue_clair_charge_en_dev(self, monkeypatch):
        from Code import prompts
        monkeypatch.setattr(prompts, "_store", None)
        assert prompts.prompts_available() is True

    def test_ni_catalogue_ni_bundle(self, sans_catalogue):
        from Code import prompts
        assert prompts._try_load() is None
        assert prompts.prompts_available() is False
        assert prompts.get_prompt("quoi") is None

    def test_bundle_sans_cle(self, sans_catalogue):
        from Code import prompts
        sans_catalogue.write_bytes(b"chiffre")
        assert prompts._try_load() is None

    def test_bundle_dechiffre_avec_la_cle_d_environnement(self, sans_catalogue, monkeypatch):
        from Code import prompts
        cle = self._chiffrer(sans_catalogue, {"salut": "Bonjour [[nom]] {json}"})
        monkeypatch.setenv("PROMPTS_KEY", cle)
        assert prompts.get_prompt("salut", nom="Ada") == "Bonjour Ada {json}"

    def test_bundle_avec_une_mauvaise_cle(self, sans_catalogue, monkeypatch):
        from cryptography.fernet import Fernet
        from Code import prompts
        self._chiffrer(sans_catalogue, {"x": "y"})
        monkeypatch.setenv("PROMPTS_KEY", Fernet.generate_key().decode())
        assert prompts._try_load() is None

    def test_cle_portee_par_la_licence(self, app, sans_catalogue, monkeypatch):
        from Code import prompts
        cle = self._chiffrer(sans_catalogue, {"x": "depuis la licence"})
        monkeypatch.setitem(app.config, "LICENSE_STATE", {"info": {"prompts_key": cle}})
        with app.app_context():
            assert prompts._license_prompts_key() == cle
            assert prompts.get_prompt("x") == "depuis la licence"

    def test_licence_sans_info(self, app, monkeypatch):
        from Code import prompts
        monkeypatch.setitem(app.config, "LICENSE_STATE", None)
        with app.app_context():
            assert prompts._license_prompts_key() is None

    def test_etat_de_licence_malforme_pas_de_cle(self, app, monkeypatch):
        from Code import prompts
        monkeypatch.setitem(app.config, "LICENSE_STATE", "pas un dict")
        with app.app_context():
            assert prompts._license_prompts_key() is None

    def test_un_echec_n_est_pas_memorise(self, sans_catalogue, monkeypatch):
        from Code import prompts
        assert prompts.get_prompt("x") is None
        cle = self._chiffrer(sans_catalogue, {"x": "arrivé après coup"})
        monkeypatch.setenv("PROMPTS_KEY", cle)
        assert prompts.get_prompt("x") == "arrivé après coup"

    def test_prompt_manquant(self, monkeypatch, capsys):
        from Code import prompts
        monkeypatch.setattr(prompts, "_store", {"a": "b"})
        assert prompts.get_prompt("absent") is None
        assert "Prompt manquant : absent" in capsys.readouterr().out

    def test_magasin_vide_vaut_indisponible(self, monkeypatch):
        from Code import prompts
        monkeypatch.setattr(prompts, "_store", {})
        assert prompts.prompts_available() is False


# ══════════════════════════════════════════════════════════════════════════
#  security.py + extensions.py
# ══════════════════════════════════════════════════════════════════════════

class TestReplisSilencieux:

    def test_verification_qui_leve_rend_faux(self, monkeypatch):
        from Code import security

        def _boum(*_a):
            raise ValueError("hash illisible")

        monkeypatch.setattr(security, "check_password_hash", _boum)
        assert security.verify_password("x$y$z", "secret") is False

    def test_hash_ou_mot_de_passe_vide(self):
        from Code.security import verify_password
        assert verify_password("", "a") is False
        assert verify_password("h", "") is False

    def test_pragmas_sqlite_qui_echouent_ne_levent_pas(self):
        from Code.extensions import set_sqlite_pragmas
        executes = []

        class _Curseur:
            def execute(self, sql):
                executes.append(sql)
                raise sqlite3.OperationalError("verrouillée")

            def close(self):
                executes.append("close")

        class _Cnx(sqlite3.Connection):
            def cursor(self, *_a, **_k):
                return _Curseur()

        cnx = sqlite3.connect(":memory:", factory=_Cnx)
        try:
            set_sqlite_pragmas(cnx, None)
        finally:
            cnx.close()
        assert executes == ["PRAGMA journal_mode=WAL;", "PRAGMA busy_timeout = 5000;", "close"]

    def test_pragmas_ignores_hors_sqlite(self):
        from Code.extensions import set_sqlite_pragmas
        set_sqlite_pragmas(object(), None)   # ne touche à rien, ne lève pas


# ══════════════════════════════════════════════════════════════════════════
#  competences_acces.py
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def binome(app):
    """Un développeur et son collaborateur rattaché globalement."""
    from Code.models.models import User
    from Code.security import hash_password
    with app.app_context():
        dev = User(first_name="Dev", last_name="T142", email="dev.t142@test",
                   password=hash_password("Test1234!"), status="user")
        db.session.add(dev)
        db.session.commit()
        col = User(first_name="Col", last_name="T142", email="col.t142@test",
                   password=hash_password("Test1234!"), status="user",
                   manager_id=dev.id)
        db.session.add(col)
        db.session.commit()
        info = {"dev": dev.id, "col": col.id}
    yield info
    with app.app_context():
        User.query.filter(User.email.like("%.t142@test")).delete(synchronize_session=False)
        db.session.commit()


class TestCompetencesAcces:

    def test_aucun_acteur_n_est_eleve(self):
        from Code.competences_acces import _statut_eleve
        assert _statut_eleve(None) is False

    @pytest.mark.parametrize("dev, col", [(None, 1), (1, None)])
    def test_encadre_sans_identifiant(self, dev, col):
        from Code.competences_acces import encadre
        assert encadre(dev, col) is False

    @pytest.mark.parametrize("dev, col, role", [(None, 1, 1), (1, None, 1), (1, 1, None)])
    def test_encadre_pour_role_sans_identifiant(self, dev, col, role):
        from Code.competences_acces import encadre_pour_role
        assert encadre_pour_role(dev, col, role) is False

    def test_roles_suivis_sans_acteur_est_une_liste_vide(self):
        from Code.competences_acces import roles_suivis
        assert roles_suivis(None, 1) == []

    def test_evaluateur_inconnu_refuse(self):
        from Code.competences_acces import peut_noter
        acteur = SimpleNamespace(id=1, status="admin")
        assert peut_noter(acteur, 2, "9") == (False, "unknown_evaluator")

    def test_lien_global_suffit_pour_noter_sans_role(self, app, binome):
        from Code.competences_acces import peut_noter
        with app.app_context():
            acteur = SimpleNamespace(id=binome["dev"], status="user")
            assert peut_noter(acteur, binome["col"], 2) == (True, "ok")

    def test_sans_aucun_lien_on_ne_note_pas(self, app, binome):
        from Code.competences_acces import peut_noter
        with app.app_context():
            acteur = SimpleNamespace(id=binome["col"], status="user")
            assert peut_noter(acteur, binome["dev"], "1") == (False, "not_the_developer")

    def test_lecture_bornee_au_role(self, app, binome):
        from Code.competences_acces import peut_lire
        with app.app_context():
            etranger = SimpleNamespace(id=binome["col"], status="user")
            assert peut_lire(etranger, binome["dev"], role_id=999999) is False
            dev = SimpleNamespace(id=binome["dev"], status="user")
            assert peut_lire(dev, binome["col"], role_id=999999) is True


# ══════════════════════════════════════════════════════════════════════════
#  ecriture.py
# ══════════════════════════════════════════════════════════════════════════

class TestPorteEcritureBranchesRares:

    def test_navigation_anonyme_est_renvoyee_a_la_connexion(self, app):
        from Code.ecriture import _refus
        with app.test_request_context("/tasks/add", method="POST",
                                      headers={"Accept": "text/html"}):
            r = _refus("non_connecte")
            assert r.status_code == 302 and r.location.endswith("/login")

    def test_fetch_anonyme_recoit_le_motif_en_json(self, app):
        from Code.ecriture import _refus
        with app.test_request_context("/tasks/add", method="POST", json={}):
            corps, statut = _refus("non_connecte")
            assert statut == 401 and corps.get_json()["code"] == "non_connecte"

    def test_carto_active_illisible_retombe_sur_le_droit_de_statut(self, app, monkeypatch):
        from Code import ecriture
        from Code.models.models import Entity

        def _boum():
            raise RuntimeError("base injoignable")

        monkeypatch.setattr(Entity, "get_active", staticmethod(_boum))
        monkeypatch.setattr(ecriture, "a_le_droit", lambda droit: droit == ecriture.DROIT_ECRITURE)
        with app.test_request_context("/"):
            assert ecriture._peut_ecrire() is True

    def test_proposition_impossible_si_la_carto_active_est_illisible(self, app, monkeypatch):
        from Code import ecriture, propositions_activite
        from Code.models.models import Entity

        def _boum():
            raise RuntimeError("base injoignable")

        monkeypatch.setattr(propositions_activite, "chemin_propasable", lambda _c: True)
        monkeypatch.setattr(propositions_activite, "route_existe", lambda _c, _m: True)
        monkeypatch.setattr(Entity, "get_active", staticmethod(_boum))
        with app.test_request_context("/"):
            assert ecriture._peut_proposer("/tasks/add", "POST") is False

    def test_geste_non_rejouable_est_refuse_en_lecture_seule(self, app, monkeypatch):
        from Code import ecriture, propositions_activite
        monkeypatch.setattr(propositions_activite, "lire_geste", lambda *_a: None)
        with app.test_request_context("/tasks/add", method="POST", json={"x": 1}):
            corps, statut = ecriture._detourner()
            assert statut == 403 and corps.get_json()["code"] == "lecture_seule"

    def test_un_refus_est_trace_quand_on_le_demande(self, auth_client, monkeypatch, tmp_path):
        from Code import ecriture
        trace = tmp_path / "porte.tsv"
        vraie_porte = ecriture.porte

        def _porte(chemin, methode, en_test=False):
            if chemin == "/t142/sonde":
                return "lecture_seule"
            return vraie_porte(chemin, methode, en_test=en_test)

        monkeypatch.setattr(ecriture, "porte", _porte)
        monkeypatch.setenv("OPTIQ_TRACE_PORTE", str(trace))
        r = auth_client.post("/t142/sonde", json={})
        assert r.status_code == 403
        champs = trace.read_text().strip().split("\t")
        assert champs[:3] == ["lecture_seule", "POST", "/t142/sonde"]

    def test_un_refus_sans_trace_demandee_n_ecrit_rien(self, auth_client, monkeypatch, tmp_path):
        from Code import ecriture
        vraie_porte = ecriture.porte
        monkeypatch.setattr(ecriture, "porte", lambda c, m, en_test=False: (
            "lecture_seule" if c == "/t142/sonde" else vraie_porte(c, m, en_test=en_test)))
        monkeypatch.delenv("OPTIQ_TRACE_PORTE", raising=False)
        r = auth_client.post("/t142/sonde", json={})
        assert r.status_code == 403 and r.get_json()["code"] == "lecture_seule"


# ══════════════════════════════════════════════════════════════════════════
#  mot_de_passe.py
# ══════════════════════════════════════════════════════════════════════════

class TestMotDePasseVerrouBase:

    @pytest.fixture
    def compte(self, app):
        from Code.models.models import PasswordReset, User
        from Code.security import hash_password
        with app.app_context():
            u = User(first_name="Mdp", last_name="T142", email="mdp.t142@test",
                     password=hash_password("Test1234!"), status="user")
            db.session.add(u)
            db.session.commit()
            uid = u.id
        yield uid
        with app.app_context():
            PasswordReset.query.filter_by(user_id=uid).delete()
            User.query.filter_by(id=uid).delete()
            db.session.commit()

    def _jeton_et_ligne(self, uid):
        from Code import mot_de_passe as mdp
        from Code.models.models import PasswordReset, User
        u = db.session.get(User, uid)
        jeton = mdp.fabriquer_jeton(u, u.email)
        ligne = PasswordReset.query.filter_by(jeton_hash=mdp._sha(jeton)).first()
        return jeton, ligne

    def test_ligne_deja_utilisee(self, app, compte):
        from Code import mot_de_passe as mdp
        with app.app_context():
            jeton, ligne = self._jeton_et_ligne(compte)
            mdp.consommer(ligne)
            assert mdp.lire_jeton(jeton) == (None, "pwd_lien_utilise")

    def test_ligne_expiree_en_base(self, app, compte):
        from Code import mot_de_passe as mdp
        with app.app_context():
            jeton, ligne = self._jeton_et_ligne(compte)
            ligne.expire_le = datetime.utcnow() - timedelta(minutes=1)
            db.session.commit()
            assert mdp.lire_jeton(jeton) == (None, "pwd_lien_expire")

    def test_purge_retire_les_demandes_anciennes_seulement(self, app, compte):
        from Code import mot_de_passe as mdp
        from Code.models.models import PasswordReset
        with app.app_context():
            vieille = PasswordReset(user_id=compte, email_hash="v" * 64,
                                    cree_le=datetime.utcnow() - timedelta(days=400))
            recente = PasswordReset(user_id=compte, email_hash="r" * 64)
            db.session.add_all([vieille, recente])
            db.session.commit()
            rid = recente.id
            assert mdp.purger(jours=365) >= 1
            restants = PasswordReset.query.filter_by(user_id=compte).all()
            assert [p.id for p in restants] == [rid]

    def test_purge_en_erreur_rend_zero(self, app, monkeypatch):
        from Code import mot_de_passe as mdp
        from Code.models import models
        monkeypatch.setattr(models, "PasswordReset", _Casse)
        with app.app_context():
            assert mdp.purger() == 0

    def test_purge_en_erreur_meme_au_rollback_rend_zero(self, app, monkeypatch):
        from Code import mot_de_passe as mdp
        from Code.models import models
        monkeypatch.setattr(models, "PasswordReset", _Casse)

        def _boum():
            raise RuntimeError("connexion perdue")

        with app.app_context():
            monkeypatch.setattr(db.session, "rollback", _boum)
            assert mdp.purger() == 0


# ══════════════════════════════════════════════════════════════════════════
#  roles_permanents.py
# ══════════════════════════════════════════════════════════════════════════

class TestRolesPermanents:

    def test_sans_candidat_ni_creation_rien(self, monkeypatch):
        from Code import roles_permanents as rp
        monkeypatch.setattr(rp, "Role", SimpleNamespace(query=SimpleNamespace(all=lambda: [])))
        assert rp.role_dev_competences(creer=False) is None

    @pytest.mark.parametrize("brut", [None, "", "{pas du json", "[1, 2]", "42"])
    def test_diagramme_illisible(self, brut):
        from Code.roles_permanents import _bandes
        assert _bandes(SimpleNamespace(optiqcarto_data=brut)) is None

    def test_format_entite_enveloppe(self):
        from Code.roles_permanents import _bandes
        brut = json.dumps({"format": "optiqcarto/entity",
                           "diagram": {"bands": [{"label": " Niveau 1 "}, "x", {"label": None}]}})
        assert _bandes(SimpleNamespace(optiqcarto_data=brut)) == {"Niveau 1", ""}

    def test_format_entite_sans_diagramme(self):
        from Code.roles_permanents import _bandes
        brut = json.dumps({"format": "optiqcarto/entity", "diagram": None})
        assert _bandes(SimpleNamespace(optiqcarto_data=brut)) is None

    def test_reprise_dont_le_marqueur_est_illisible(self, app, monkeypatch):
        from Code import roles_permanents as rp
        from Code.models import models
        monkeypatch.setattr(models, "AppSetting", _Casse)
        with app.app_context():
            assert rp.reprendre_roles_hors_carte() == 0

    def test_reprise_ignore_une_carto_illisible(self, app):
        from Code import roles_permanents as rp
        from Code.models.models import Entity, Role
        with app.app_context():
            e = Entity(name="T142 carto illisible", optiqcarto_data="{cassé")
            db.session.add(e)
            db.session.commit()
            r = Role(name="T142 rôle orphelin", entity_id=e.id)
            db.session.add(r)
            db.session.commit()
            eid, rid = e.id, r.id
        try:
            with app.app_context():
                assert rp.reprendre_roles_hors_carte(force=True, entity_ids=[eid]) == 0
                assert not db.session.get(Role, rid).hors_carte
        finally:
            with app.app_context():
                Role.query.filter_by(id=rid).delete()
                Entity.query.filter_by(id=eid).delete()
                db.session.commit()


# ══════════════════════════════════════════════════════════════════════════
#  paliers.py
# ══════════════════════════════════════════════════════════════════════════

class TestPaliersBornes:

    def test_atteint_sans_mesure_ou_sans_cible(self):
        from Code.paliers import MOINS, atteint
        assert atteint(None, 10, MOINS) is False
        assert atteint(10, None, MOINS) is False

    def test_mieux_que_sans_valeur(self):
        from Code.paliers import PLUS, _mieux_que
        assert _mieux_que(None, 1, PLUS) is False
        assert _mieux_que(1, None, PLUS) is False

    @pytest.mark.parametrize("valeur, sens", [(None, "moins"), (48, "ailleurs")])
    def test_pas_de_progression_sans_norme_valide(self, valeur, sens):
        from Code.paliers import pas_de_progression
        assert pas_de_progression([96, 72], valeur, sens) is None

    @pytest.mark.parametrize("valeur, sens", [(None, "moins"), (48, "ailleurs")])
    def test_seuil_au_dela_sans_norme_valide(self, valeur, sens):
        from Code.paliers import seuil_au_dela
        assert seuil_au_dela([96, 72, 24], valeur, sens) is None

    def test_proposer_cible_sur_une_sortie_non_mesurable(self):
        from Code.paliers import proposer_cible
        assert proposer_cible(None, 1) is None
        assert proposer_cible(SimpleNamespace(norme_valeur=None, norme_sens="moins"), 1) is None

    def test_proposer_cible_quand_le_dernier_palier_atteint_la_norme(self, monkeypatch):
        from Code import paliers
        d = SimpleNamespace(id=1, norme_valeur=48.0, norme_sens=paliers.MOINS)
        dernier = SimpleNamespace(mesure_valeur=40.0, cible_valeur=48.0)
        monkeypatch.setattr(paliers, "paliers_de", lambda *_a: [dernier])
        assert paliers.proposer_cible(d, 1) == 48.0

    def test_proposer_cible_sans_mesure_part_de_la_cible(self, monkeypatch):
        from Code import paliers
        d = SimpleNamespace(id=1, norme_valeur=48.0, norme_sens=paliers.MOINS)
        dernier = SimpleNamespace(mesure_valeur=None, cible_valeur=96.0)
        monkeypatch.setattr(paliers, "paliers_de", lambda *_a: [dernier])
        assert paliers.proposer_cible(d, 1) == 72.0

    def test_niveau_du_jour_sans_sortie_ou_sans_norme(self):
        from Code.paliers import _niveau_du_jour
        p = SimpleNamespace(user_id=1, data_id=1, role_id=None, cible_valeur=1,
                            mesure_valeur=1)
        assert _niveau_du_jour(p, None) is None
        assert _niveau_du_jour(p, SimpleNamespace(norme_valeur=None)) is None


class TestSessionsDe:

    @pytest.fixture
    def agenda(self, app, binome):
        from Code.models.models import Role, SessionEvaluation
        with app.app_context():
            role = Role(name="T142 rôle agenda")
            db.session.add(role)
            db.session.commit()
            uid = binome["col"]
            aujourd_hui = date.today()
            lignes = [
                SessionEvaluation(user_id=uid, role_id=role.id, statut="prevue",
                                  date_prevue=aujourd_hui + timedelta(days=5), objet="futur"),
                SessionEvaluation(user_id=uid, role_id=role.id, statut="prevue",
                                  date_prevue=aujourd_hui - timedelta(days=5), objet="passe"),
                SessionEvaluation(user_id=uid, role_id=role.id, statut="tenue",
                                  date_prevue=aujourd_hui + timedelta(days=1), objet="tenue"),
                SessionEvaluation(user_id=uid, role_id=None, statut="prevue",
                                  date_prevue=aujourd_hui + timedelta(days=2), objet="sans role"),
            ]
            db.session.add_all(lignes)
            db.session.commit()
            info = {"uid": uid, "role_id": role.id}
        yield info
        with app.app_context():
            SessionEvaluation.query.filter_by(user_id=info["uid"]).delete()
            Role.query.filter_by(id=info["role_id"]).delete()
            db.session.commit()

    def test_toutes_les_sessions_triees_par_date(self, app, agenda):
        from Code.paliers import sessions_de
        with app.app_context():
            objets = [s.objet for s in sessions_de(agenda["uid"])]
            assert objets == ["passe", "tenue", "sans role", "futur"]

    def test_filtre_par_role(self, app, agenda):
        from Code.paliers import sessions_de
        with app.app_context():
            objets = [s.objet for s in sessions_de(agenda["uid"], role_id=agenda["role_id"])]
            assert objets == ["passe", "tenue", "futur"]

    def test_a_venir_seulement(self, app, agenda):
        from Code.paliers import sessions_de
        with app.app_context():
            objets = [s.objet for s in sessions_de(agenda["uid"], a_venir_seulement=True)]
            assert objets == ["sans role", "futur"]
