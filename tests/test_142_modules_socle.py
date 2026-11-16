# -*- coding: utf-8 -*-
"""Couverture des modules socle partagés par toute l'application.

- `Code/prompts/__init__.py` : catalogue clair, bundle chiffré (clé d'env ou
  de licence), dégradation propre sans clé, prompt manquant, interpolation.
- `Code/ai_client.py` : choix du fournisseur, modèle effectif, construction
  du client (base Anthropic, délai, échec du SDK).
- `Code/logstream.py` : duplication stdout/stderr, plafond du fichier
  tampon, lecture incrémentale et détection de troncature.
- `Code/paliers.py` : cas limites des fonctions pures et des sessions.
- `Code/mot_de_passe.py` : lien déjà utilisé, lien expiré, purge en erreur.
- `Code/ecriture.py` : refus en navigation, repli de droit, geste non
  rejouable, trace de la porte.
- `Code/roles_permanents.py` et `Code/carto_access.py` : branches rares.

Chaque test est autonome : monkeypatch restauré par pytest, fichiers dans
tmp_path, données dédiées nettoyées.
"""
import io
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest


# ══════════════════════════════════════════════════════════════════════════
#  prompts/__init__.py
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def prompts_sans_catalogue(monkeypatch, tmp_path):
    """Simule une image client : catalog.py absent, store vierge, bundle dans
    tmp_path. Rend (module, chemin_du_bundle)."""
    import Code.prompts as prompts
    monkeypatch.setitem(sys.modules, "Code.prompts.catalog", None)
    monkeypatch.setattr(prompts, "_store", None)
    enc = tmp_path / "prompts.enc"
    monkeypatch.setattr(prompts, "_ENC_PATH", str(enc))
    monkeypatch.delenv("PROMPTS_KEY", raising=False)
    return prompts, enc


def _bundle(enc, contenu):
    from cryptography.fernet import Fernet
    cle = Fernet.generate_key()
    enc.write_bytes(Fernet(cle).encrypt(json.dumps(contenu).encode()))
    return cle.decode()


class TestPromptsCatalogue:

    def test_catalogue_clair_est_charge_en_dict(self, monkeypatch):
        import Code.prompts as prompts
        from Code.prompts.catalog import PROMPTS
        monkeypatch.setattr(prompts, "_store", None)
        store = prompts._try_load()
        assert store == dict(PROMPTS)
        assert store is not PROMPTS

    def test_store_deja_charge_n_est_pas_relu(self, monkeypatch):
        import Code.prompts as prompts
        monkeypatch.setattr(prompts, "_store", {"k": "v"})
        monkeypatch.setattr(prompts, "_try_load",
                            lambda: pytest.fail("ne doit pas recharger"))
        assert prompts._get_store() == {"k": "v"}

    def test_store_vide_memorise_rend_none(self, monkeypatch):
        import Code.prompts as prompts
        monkeypatch.setattr(prompts, "_store", {})
        assert prompts._get_store() is None
        assert prompts.prompts_available() is False

    def test_interpolation_remplace_tous_les_placeholders(self, monkeypatch):
        import Code.prompts as prompts
        monkeypatch.setattr(prompts, "_store",
                            {"p": 'Bonjour [[nom]], {"json": [[n]]} [[nom]]'})
        assert prompts.get_prompt("p", nom="Ada", n=3) == \
            'Bonjour Ada, {"json": 3} Ada'

    def test_placeholder_non_fourni_reste_intact(self, monkeypatch):
        import Code.prompts as prompts
        monkeypatch.setattr(prompts, "_store", {"p": "[[a]] et [[b]]"})
        assert prompts.get_prompt("p", a="x") == "x et [[b]]"

    def test_prompt_manquant_rend_none_et_le_dit(self, monkeypatch, capsys):
        import Code.prompts as prompts
        monkeypatch.setattr(prompts, "_store", {"autre": "x"})
        assert prompts.get_prompt("inexistant") is None
        assert "Prompt manquant : inexistant" in capsys.readouterr().out

    def test_sans_store_get_prompt_rend_none(self, monkeypatch):
        import Code.prompts as prompts
        monkeypatch.setattr(prompts, "_store", None)
        monkeypatch.setattr(prompts, "_try_load", lambda: None)
        assert prompts.get_prompt("quoi_que_ce_soit") is None


class TestPromptsBundleChiffre:

    def test_ni_catalogue_ni_bundle_rend_none(self, prompts_sans_catalogue, capsys):
        prompts, _enc = prompts_sans_catalogue
        assert prompts._try_load() is None
        assert "Ni catalogue ni bundle" in capsys.readouterr().out

    def test_bundle_sans_cle_rend_none(self, prompts_sans_catalogue, capsys):
        prompts, enc = prompts_sans_catalogue
        _bundle(enc, {"a": "b"})
        assert prompts._try_load() is None
        assert "aucune clé" in capsys.readouterr().out

    def test_bundle_dechiffre_avec_la_cle_d_environnement(
            self, prompts_sans_catalogue, monkeypatch, capsys):
        prompts, enc = prompts_sans_catalogue
        cle = _bundle(enc, {"salut": "Bonjour [[qui]]"})
        monkeypatch.setenv("PROMPTS_KEY", cle)
        assert prompts._try_load() == {"salut": "Bonjour [[qui]]"}
        assert "Bundle chiffré chargé (1 prompts)" in capsys.readouterr().out

    def test_bundle_dechiffre_avec_la_cle_de_licence(
            self, app, prompts_sans_catalogue, monkeypatch):
        prompts, enc = prompts_sans_catalogue
        cle = _bundle(enc, {"x": "y"})
        monkeypatch.setitem(app.config, "LICENSE_STATE",
                            {"info": {"prompts_key": cle}})
        with app.app_context():
            assert prompts._try_load() == {"x": "y"}

    def test_mauvaise_cle_rend_none_sans_lever(
            self, prompts_sans_catalogue, monkeypatch, capsys):
        from cryptography.fernet import Fernet
        prompts, enc = prompts_sans_catalogue
        _bundle(enc, {"a": "b"})
        monkeypatch.setenv("PROMPTS_KEY", Fernet.generate_key().decode())
        assert prompts._try_load() is None
        assert "Déchiffrement du bundle impossible" in capsys.readouterr().out

    def test_echec_non_memorise_une_cle_tardive_est_prise(
            self, prompts_sans_catalogue, monkeypatch):
        prompts, enc = prompts_sans_catalogue
        cle = _bundle(enc, {"k": "v"})
        assert prompts._get_store() is None
        assert prompts._store is None
        monkeypatch.setenv("PROMPTS_KEY", cle)
        assert prompts.get_prompt("k") == "v"
        assert prompts.prompts_available() is True

    def test_cle_de_licence_hors_contexte_flask_rend_none(self):
        import Code.prompts as prompts
        assert prompts._license_prompts_key() is None

    def test_cle_de_licence_sans_etat_rend_none(self, app, monkeypatch):
        import Code.prompts as prompts
        monkeypatch.setitem(app.config, "LICENSE_STATE", None)
        with app.app_context():
            assert prompts._license_prompts_key() is None


# ══════════════════════════════════════════════════════════════════════════
#  ai_client.py
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def cles_ia(monkeypatch):
    """Pilote les clés vues par ai_client. Rend un dict modifiable."""
    import Code.ai_client as ai
    cles = {"anthropic": None, "openai": None}
    monkeypatch.setattr(ai, "get_anthropic_key", lambda: cles["anthropic"])
    monkeypatch.setattr(ai, "get_openai_key", lambda: cles["openai"])
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    return cles


class TestAiClientFournisseur:

    def test_auto_prefere_anthropic_quand_sa_cle_existe(self, cles_ia):
        from Code.ai_client import resolve_provider
        cles_ia.update(anthropic="sk-ant", openai="sk-oa")
        assert resolve_provider() == ("anthropic", "sk-ant")

    def test_auto_retombe_sur_openai_sans_cle_anthropic(self, cles_ia):
        from Code.ai_client import resolve_provider
        cles_ia.update(openai="sk-oa")
        assert resolve_provider() == ("openai", "sk-oa")

    def test_force_anthropic_meme_sans_cle(self, cles_ia, monkeypatch):
        from Code.ai_client import resolve_provider
        cles_ia.update(openai="sk-oa")
        monkeypatch.setenv("AI_PROVIDER", " Anthropic ")
        assert resolve_provider() == ("anthropic", None)

    def test_force_openai_ignore_la_cle_anthropic(self, cles_ia, monkeypatch):
        from Code.ai_client import resolve_provider
        cles_ia.update(anthropic="sk-ant", openai="sk-oa")
        monkeypatch.setenv("AI_PROVIDER", "openai")
        assert resolve_provider() == ("openai", "sk-oa")

    def test_valeur_inconnue_vaut_auto(self, cles_ia, monkeypatch):
        from Code.ai_client import resolve_provider
        cles_ia.update(anthropic="sk-ant")
        monkeypatch.setenv("AI_PROVIDER", "mistral")
        assert resolve_provider() == ("anthropic", "sk-ant")


class TestAiClientModele:

    def test_ai_model_env_prioritaire(self, cles_ia, monkeypatch):
        from Code.ai_client import ai_model
        monkeypatch.setenv("AI_MODEL", "  mon-modele ")
        assert ai_model("openai") == "mon-modele"

    def test_ai_model_defaut_du_fournisseur_resolu(self, cles_ia):
        from Code.ai_client import DEFAULT_MODELS, ai_model
        cles_ia.update(anthropic="sk-ant")
        assert ai_model() == DEFAULT_MODELS["anthropic"]

    def test_ai_model_fournisseur_inconnu_retombe_sur_openai(self, cles_ia):
        from Code.ai_client import DEFAULT_MODELS, ai_model
        assert ai_model("inconnu") == DEFAULT_MODELS["openai"]


class TestAiClientConstruction:

    def _faux_sdk(self, monkeypatch, recu, lever=None):
        import openai

        class _Faux:
            def __init__(self, **kwargs):
                if lever:
                    raise lever
                recu.update(kwargs)

        monkeypatch.setattr(openai, "OpenAI", _Faux)
        return _Faux

    def test_sans_cle_rend_le_message_utilisateur(self, cles_ia):
        from Code.ai_client import NO_KEY_MSG, make_ai_client
        assert make_ai_client() == (None, None, NO_KEY_MSG)

    def test_anthropic_pointe_sur_la_base_compatible(self, cles_ia, monkeypatch):
        from Code.ai_client import ANTHROPIC_OPENAI_BASE, DEFAULT_MODELS, make_ai_client
        cles_ia.update(anthropic="sk-ant")
        recu = {}
        faux = self._faux_sdk(monkeypatch, recu)
        client, modele, err = make_ai_client(timeout=12)
        assert isinstance(client, faux) and err is None
        assert modele == DEFAULT_MODELS["anthropic"]
        assert recu == {"api_key": "sk-ant", "base_url": ANTHROPIC_OPENAI_BASE,
                        "timeout": 12}

    def test_openai_sans_base_ni_timeout(self, cles_ia, monkeypatch):
        from Code.ai_client import make_ai_client
        cles_ia.update(openai="sk-oa")
        recu = {}
        self._faux_sdk(monkeypatch, recu)
        _client, modele, err = make_ai_client()
        assert err is None and modele == "gpt-4o-mini"
        assert recu == {"api_key": "sk-oa"}

    def test_echec_du_sdk_rend_le_message(self, cles_ia, monkeypatch):
        from Code.ai_client import make_ai_client
        cles_ia.update(openai="sk-oa")
        self._faux_sdk(monkeypatch, {}, lever=ValueError("clé malformée"))
        assert make_ai_client() == (None, None, "clé malformée")


# ══════════════════════════════════════════════════════════════════════════
#  logstream.py
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def journal(monkeypatch, tmp_path):
    import Code.logstream as ls
    chemin = tmp_path / "serveur.log"
    monkeypatch.setattr(ls, "LOG_PATH", str(chemin))
    return ls, chemin


class TestLogstreamTee:

    def test_write_duplique_vers_l_original_et_le_fichier(self, journal):
        ls, chemin = journal
        orig = io.StringIO()
        tee = ls._Tee(orig)
        tee.write("ligne 1\n")
        assert orig.getvalue() == "ligne 1\n"
        assert chemin.read_text(encoding="utf-8") == "ligne 1\n"

    def test_write_vide_n_ecrit_pas_le_fichier(self, journal):
        ls, chemin = journal
        ls._Tee(io.StringIO()).write("")
        assert not chemin.exists()

    def test_original_casse_n_empeche_pas_le_fichier(self, journal):
        ls, chemin = journal

        class _Casse:
            def write(self, _d):
                raise OSError("pipe fermé")

            def flush(self):
                raise OSError("pipe fermé")

        tee = ls._Tee(_Casse())
        tee.write("survit\n")
        tee.flush()
        assert chemin.read_text(encoding="utf-8") == "survit\n"

    def test_flush_et_attributs_deleguent_a_l_original(self, journal):
        ls, _ = journal
        orig = io.StringIO()
        tee = ls._Tee(orig)
        tee.flush()
        assert tee.getvalue is not None
        assert tee.closed is False

    def test_bytes_sont_decodes(self, journal):
        ls, chemin = journal
        ls._append("é".encode("utf-8") + b"\xff")
        assert chemin.read_text(encoding="utf-8") == "é�"


class TestLogstreamPlafond:

    def test_depassement_garde_la_fin(self, journal, monkeypatch):
        ls, chemin = journal
        monkeypatch.setattr(ls, "MAX_BYTES", 50)
        monkeypatch.setattr(ls, "KEEP_BYTES", 10)
        ls._append("A" * 45)
        ls._append("0123456789")
        assert chemin.read_bytes() == b"0123456789"

    def test_erreur_disque_avalee(self, journal, monkeypatch):
        ls, chemin = journal
        monkeypatch.setattr(ls, "LOG_PATH", str(chemin.parent / "absent" / "x.log"))
        ls._append("rien")


class TestLogstreamHandler:

    def test_handler_ecrit_le_message_formate(self, journal):
        ls, chemin = journal
        h = ls._FileHandler()
        h.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
        h.emit(logging.LogRecord("t", logging.WARNING, __file__, 1, "attention", None, None))
        assert chemin.read_text(encoding="utf-8") == "WARNING:attention\n"

    def test_handler_avale_une_erreur_de_formatage(self, journal):
        ls, chemin = journal
        h = ls._FileHandler()

        class _Casse(logging.Formatter):
            def format(self, record):
                raise RuntimeError("boum")

        h.setFormatter(_Casse())
        h.emit(logging.LogRecord("t", logging.INFO, __file__, 1, "x", None, None))
        assert not chemin.exists()


class TestLogstreamInit:

    def test_init_branche_puis_reste_idempotent(self, journal, monkeypatch):
        ls, chemin = journal
        monkeypatch.setattr(ls, "_initialized", False)
        out, err = io.StringIO(), io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)
        racine = logging.getLogger()
        avant = list(racine.handlers)
        try:
            ls.init_logstream()
            assert isinstance(sys.stdout, ls._Tee) and isinstance(sys.stderr, ls._Tee)
            ajoutes = [h for h in racine.handlers if h not in avant]
            assert len(ajoutes) == 1 and isinstance(ajoutes[0], ls._FileHandler)
            tee_out = sys.stdout
            ls.init_logstream()
            assert sys.stdout is tee_out
            assert len([h for h in racine.handlers if h not in avant]) == 1
            sys.stdout.write("capté\n")
            assert out.getvalue() == "capté\n"
            assert "capté" in chemin.read_text(encoding="utf-8")
        finally:
            for h in [h for h in racine.handlers if h not in avant]:
                racine.removeHandler(h)


class TestLogstreamTail:

    def test_fichier_absent(self, journal):
        ls, _ = journal
        assert ls.tail() == ("", 0, 0)

    def test_lecture_depuis_zero_puis_incrementale(self, journal):
        ls, chemin = journal
        chemin.write_text("abc", encoding="utf-8")
        texte, off, taille = ls.tail()
        assert (texte, off, taille) == ("abc", 3, 3)
        with open(chemin, "a", encoding="utf-8") as f:
            f.write("déf")
        texte, off2, taille2 = ls.tail(off)
        assert texte == "déf" and off2 == taille2 == 7

    def test_offset_zero_ne_lit_que_la_fin(self, journal):
        ls, chemin = journal
        chemin.write_text("0123456789", encoding="utf-8")
        texte, off, taille = ls.tail(0, max_bytes=4)
        assert texte == "6789" and off == 10 and taille == 10

    def test_offset_au_dela_de_la_taille_repart_de_zero(self, journal):
        ls, chemin = journal
        chemin.write_text("court", encoding="utf-8")
        texte, off, _ = ls.tail(999)
        assert texte == "court" and off == 5

    def test_erreur_de_lecture(self, journal, monkeypatch):
        import builtins
        ls, chemin = journal
        chemin.write_text("xyz", encoding="utf-8")
        vrai_open = builtins.open

        def _open(p, *a, **k):
            if str(p) == str(chemin):
                raise OSError("verrou")
            return vrai_open(p, *a, **k)

        monkeypatch.setattr(builtins, "open", _open)
        assert ls.tail(1) == ("", 1, 3)


# ══════════════════════════════════════════════════════════════════════════
#  paliers.py — fonctions pures et sessions
# ══════════════════════════════════════════════════════════════════════════

class TestPaliersFonctionsPures:

    def test_atteint_sans_mesure_ou_sans_cible(self):
        from Code.paliers import MOINS, atteint
        assert atteint(None, 48, MOINS) is False
        assert atteint(40, None, MOINS) is False

    def test_mieux_que_avec_none(self):
        from Code.paliers import PLUS, _mieux_que
        assert _mieux_que(None, 3, PLUS) is False
        assert _mieux_que(3, None, PLUS) is False

    def test_pas_de_progression_sans_norme_ou_sens_inconnu(self):
        from Code.paliers import MOINS, pas_de_progression
        assert pas_de_progression([96, 72], None, MOINS) is None
        assert pas_de_progression([96, 72], 48, "neutre") is None

    def test_pas_de_progression_sans_marche_en_deca(self):
        from Code.paliers import MOINS, pas_de_progression
        assert pas_de_progression([48, 40, None], 48, MOINS) is None

    def test_seuil_au_dela_sans_norme(self):
        from Code.paliers import PLUS, seuil_au_dela
        assert seuil_au_dela([80, 90], None, PLUS) is None

    def test_seuil_au_dela_deduit_du_pas_quand_aucune_marche_au_dela(self):
        from Code.paliers import MOINS, PLUS, seuil_au_dela
        assert seuil_au_dela([96, 72], 48, MOINS) == 24
        assert seuil_au_dela([80, 90], 95, PLUS) == 100

    def test_seuil_au_dela_sans_pas_rend_none(self):
        from Code.paliers import MOINS, seuil_au_dela
        assert seuil_au_dela([48], 48, MOINS) is None

    def test_norme_texte_vide_ou_sans_chiffre(self):
        from Code.paliers import norme_depuis_indicateur
        assert norme_depuis_indicateur("") is None
        assert norme_depuis_indicateur("Cahier des charges validé") is None

    @pytest.mark.parametrize("texte,attendu", [
        ("≤ 48 h", (48.0, "h", "moins")),
        ("95 % de conformité", (95.0, "%", "plus")),
        ("sous 5 jours", (5.0, "j", "moins")),
        ("au moins 3 semaines", (3.0, "sem", "plus")),
        ("2,5 hours max", (2.5, "h", "moins")),
        ("12 retouches", (12.0, "", "moins")),
    ])
    def test_norme_depuis_indicateur(self, texte, attendu):
        from Code.paliers import norme_depuis_indicateur
        r = norme_depuis_indicateur(texte)
        assert (r["valeur"], r["unite"], r["sens"]) == attendu

    def test_niveau_depuis_mesure_sans_premiere_cible_vaut_un(self):
        from Code.paliers import MOINS, niveau_depuis_mesure
        assert niveau_depuis_mesure(100, 48, MOINS) == 1

    def test_niveau_avance_deduit_de_la_marge(self):
        from Code.paliers import MOINS, NIVEAU_AVANCE, niveau_depuis_mesure
        assert niveau_depuis_mesure(20, 48, MOINS, 96, marge=24) == NIVEAU_AVANCE

    def test_mesurable(self):
        from Code.paliers import mesurable
        assert mesurable(None) is False
        assert mesurable(SimpleNamespace(norme_valeur=None, norme_sens="moins")) is False
        assert mesurable(SimpleNamespace(norme_valeur=4, norme_sens="x")) is False
        assert mesurable(SimpleNamespace(norme_valeur=4, norme_sens="plus")) is True

    def test_proposer_cible_non_mesurable(self):
        from Code.paliers import proposer_cible
        assert proposer_cible(SimpleNamespace(norme_valeur=None, norme_sens=None), 1) is None

    def test_niveau_du_jour_sans_donnee(self):
        from Code.paliers import _niveau_du_jour
        assert _niveau_du_jour(SimpleNamespace(), None) is None
        assert _niveau_du_jour(SimpleNamespace(), SimpleNamespace(norme_valeur=None)) is None


@pytest.fixture
def sortie_mesuree(app, ids):
    """Une sortie à norme ≤ 48 h, un compte et un rôle dédiés, nettoyés."""
    from werkzeug.security import generate_password_hash
    from Code.extensions import db
    from Code.models.models import (Activities, Data, PalierPerformance, Role,
                                    SessionEvaluation, User)
    with app.app_context():
        act = Activities(name="Act paliers socle 142", entity_id=ids["entity_id"])
        db.session.add(act)
        db.session.flush()
        d = Data(name="Doc socle 142", type="sortie", producer_activity_id=act.id,
                 norme_valeur=48, norme_sens="moins", norme_unite="h")
        u = User(entity_id=ids["entity_id"], first_name="Pal", last_name="Socle",
                 email="paliers.socle142@test.local",
                 password=generate_password_hash("x"), status="user")
        r = Role(entity_id=ids["entity_id"], name="Rôle socle 142")
        db.session.add_all([d, u, r])
        db.session.commit()
        out = SimpleNamespace(act=act.id, data=d.id, user=u.id, role=r.id)
    yield out
    with app.app_context():
        PalierPerformance.query.filter_by(user_id=out.user).delete()
        SessionEvaluation.query.filter_by(user_id=out.user).delete()
        for modele, pk in ((Data, out.data), (Role, out.role), (User, out.user),
                           (Activities, out.act)):
            obj = db.session.get(modele, pk)
            if obj is not None:
                db.session.delete(obj)
        db.session.commit()


class TestPaliersEnBase:

    def test_paliers_filtres_par_role(self, app, sortie_mesuree):
        from Code.extensions import db
        from Code.models.models import Data, PalierPerformance
        from Code.paliers import paliers_de
        s = sortie_mesuree
        with app.app_context():
            for rang, role in ((1, s.role), (2, None)):
                db.session.add(PalierPerformance(
                    user_id=s.user, activity_id=s.act, data_id=s.data,
                    role_id=role, rang=rang, cible_valeur=96, statut="en_cours"))
            db.session.commit()
            assert [p.rang for p in paliers_de(s.user, s.data)] == [1, 2]
            assert [p.rang for p in paliers_de(s.user, s.data, s.role)] == [1]

    def test_proposer_cible_atteinte_rend_la_norme(self, app, sortie_mesuree):
        from Code.extensions import db
        from Code.models.models import Data, PalierPerformance
        from Code.paliers import proposer_cible
        s = sortie_mesuree
        with app.app_context():
            db.session.add(PalierPerformance(
                user_id=s.user, activity_id=s.act, data_id=s.data, rang=1,
                cible_valeur=72, mesure_valeur=40, statut="atteint"))
            db.session.commit()
            assert proposer_cible(db.session.get(Data, s.data), s.user) == 48

    def test_proposer_cible_premier_palier_d_un_taux(self, app, sortie_mesuree):
        from Code.extensions import db
        from Code.models.models import Data
        from Code.paliers import proposer_cible
        s = sortie_mesuree
        with app.app_context():
            d = db.session.get(Data, s.data)
            d.norme_valeur, d.norme_sens = 90, "plus"
            db.session.commit()
            assert proposer_cible(d, s.user) == 45

    def test_sessions_a_venir_seulement(self, app, sortie_mesuree):
        from Code.extensions import db
        from Code.models.models import SessionEvaluation
        from Code.paliers import sessions_de
        s = sortie_mesuree
        with app.app_context():
            futur = SessionEvaluation(user_id=s.user, role_id=s.role, statut="prevue",
                                      date_prevue=date.today() + timedelta(days=5))
            passee = SessionEvaluation(user_id=s.user, role_id=s.role, statut="prevue",
                                       date_prevue=date.today() - timedelta(days=5))
            tenue = SessionEvaluation(user_id=s.user, role_id=s.role, statut="tenue",
                                      date_prevue=date.today() + timedelta(days=9))
            db.session.add_all([futur, passee, tenue])
            db.session.commit()
            tous = sessions_de(s.user, role_id=s.role)
            assert [x.id for x in tous] == [passee.id, futur.id, tenue.id]
            assert [x.id for x in sessions_de(s.user, s.role, a_venir_seulement=True)] \
                == [futur.id]


# ══════════════════════════════════════════════════════════════════════════
#  mot_de_passe.py
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def compte_reset(app, ids):
    from werkzeug.security import generate_password_hash
    from Code.extensions import db
    from Code.models.models import PasswordReset, User
    with app.app_context():
        u = User(entity_id=ids["entity_id"], first_name="Reset", last_name="Socle",
                 email="reset.socle142@test.local",
                 password=generate_password_hash("Ancien1!"), status="user")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield uid
    with app.app_context():
        PasswordReset.query.filter_by(user_id=uid).delete()
        u = db.session.get(User, uid)
        if u is not None:
            db.session.delete(u)
        db.session.commit()


class TestMotDePasseJeton:

    def _jeton(self, uid):
        from Code.extensions import db
        from Code.models.models import User
        from Code.mot_de_passe import _sha, fabriquer_jeton
        from Code.models.models import PasswordReset
        u = db.session.get(User, uid)
        jeton = fabriquer_jeton(u, u.email)
        ligne = PasswordReset.query.filter_by(jeton_hash=_sha(jeton)).one()
        return jeton, ligne

    def test_jeton_frais_est_accepte(self, app, compte_reset):
        from Code.mot_de_passe import lire_jeton
        with app.test_request_context():
            jeton, ligne = self._jeton(compte_reset)
            user, l2 = lire_jeton(jeton)
            assert user.id == compte_reset and l2.id == ligne.id

    def test_ligne_deja_utilisee_refuse(self, app, compte_reset):
        from Code.extensions import db
        from Code.mot_de_passe import consommer, lire_jeton
        with app.test_request_context():
            jeton, ligne = self._jeton(compte_reset)
            consommer(ligne)
            assert lire_jeton(jeton) == (None, "pwd_lien_utilise")

    def test_ligne_expiree_refuse(self, app, compte_reset):
        from Code.extensions import db
        from Code.mot_de_passe import lire_jeton
        with app.test_request_context():
            jeton, ligne = self._jeton(compte_reset)
            ligne.expire_le = datetime.utcnow() - timedelta(minutes=1)
            db.session.commit()
            assert lire_jeton(jeton) == (None, "pwd_lien_expire")

    def test_ligne_purgee_refuse(self, app, compte_reset):
        from Code.extensions import db
        from Code.mot_de_passe import lire_jeton
        with app.test_request_context():
            jeton, ligne = self._jeton(compte_reset)
            db.session.delete(ligne)
            db.session.commit()
            assert lire_jeton(jeton) == (None, "pwd_lien_invalide")


class TestMotDePassePurge:

    def test_purge_supprime_les_anciennes_seulement(self, app, compte_reset):
        from Code.extensions import db
        from Code.models.models import PasswordReset
        from Code.mot_de_passe import purger
        with app.app_context():
            vieille = PasswordReset(user_id=compte_reset, email_hash="h",
                                    cree_le=datetime.utcnow() - timedelta(days=200))
            recente = PasswordReset(user_id=compte_reset, email_hash="h")
            db.session.add_all([vieille, recente])
            db.session.commit()
            vid, rid = vieille.id, recente.id
            assert purger(jours=90) >= 1
            assert db.session.get(PasswordReset, vid) is None
            assert db.session.get(PasswordReset, rid) is not None

    def test_purge_en_erreur_rend_zero(self, app, monkeypatch):
        from Code.extensions import db
        from Code import mot_de_passe
        from Code.models.models import PasswordReset

        class _Q:
            def filter(self, *_a):
                raise RuntimeError("table absente")

        with app.app_context():
            monkeypatch.setattr(PasswordReset, "query", _Q())
            assert mot_de_passe.purger() == 0

    def test_purge_rollback_qui_echoue_aussi(self, app, monkeypatch):
        from Code.extensions import db
        from Code import mot_de_passe
        from Code.models.models import PasswordReset

        class _Q:
            def filter(self, *_a):
                raise RuntimeError("table absente")

        def _rollback():
            raise RuntimeError("connexion perdue")

        with app.app_context():
            monkeypatch.setattr(PasswordReset, "query", _Q())
            monkeypatch.setattr(db.session, "rollback", _rollback)
            assert mot_de_passe.purger() == 0


# ══════════════════════════════════════════════════════════════════════════
#  ecriture.py
# ══════════════════════════════════════════════════════════════════════════

class TestEcritureRefus:

    def test_non_connecte_en_navigation_redirige(self, app):
        from Code.ecriture import _refus
        with app.test_request_context("/tasks/add", method="POST",
                                      headers={"Accept": "text/html"}):
            r = _refus("non_connecte")
            assert r.status_code == 302 and r.location.endswith("/login")

    def test_non_connecte_en_api_rend_du_json(self, app):
        from Code.ecriture import _refus
        with app.test_request_context("/api/x", method="POST",
                                      headers={"Accept": "text/html"}):
            corps, statut = _refus("non_connecte")
            assert statut == 401 and corps.get_json()["code"] == "non_connecte"

    def test_non_connecte_en_xhr_rend_du_json(self, app):
        from Code.ecriture import _refus
        with app.test_request_context(
                "/tasks/add", method="POST",
                headers={"Accept": "text/html", "X-Requested-With": "XMLHttpRequest"}):
            _corps, statut = _refus("non_connecte")
            assert statut == 401

    def test_lecture_seule_jamais_redirigee(self, app):
        from Code.ecriture import _refus
        with app.test_request_context("/tasks/add", method="POST",
                                      headers={"Accept": "text/html"}):
            corps, statut = _refus("lecture_seule")
            assert statut == 403 and corps.get_json()["error"] == "lecture seule"


class TestEcritureDroits:

    def test_entite_active_en_erreur_retombe_sur_le_statut(self, app, monkeypatch):
        from Code import ecriture
        from Code.models.models import Entity

        def _casse():
            raise RuntimeError("base indisponible")

        monkeypatch.setattr(Entity, "get_active", staticmethod(_casse))
        monkeypatch.setattr(ecriture, "a_le_droit", lambda droit: droit == ecriture.DROIT_ECRITURE)
        with app.test_request_context():
            assert ecriture._peut_ecrire() is True
        monkeypatch.setattr(ecriture, "a_le_droit", lambda droit: False)
        with app.test_request_context():
            assert ecriture._peut_ecrire() is False

    def test_proposition_impossible_si_entite_active_en_erreur(self, app, monkeypatch):
        from Code import ecriture, propositions_activite
        from Code.models.models import Entity

        def _casse():
            raise RuntimeError("base indisponible")

        monkeypatch.setattr(propositions_activite, "chemin_propasable", lambda c: True)
        monkeypatch.setattr(propositions_activite, "route_existe", lambda c, m: True)
        monkeypatch.setattr(Entity, "get_active", staticmethod(_casse))
        with app.test_request_context():
            assert ecriture._peut_proposer("/tasks/add", "POST") is False

    def test_geste_non_rejouable_est_refuse(self, app, monkeypatch):
        from Code import ecriture, propositions_activite
        monkeypatch.setattr(propositions_activite, "lire_geste", lambda *a: None)
        with app.test_request_context("/tasks/add", method="POST", json={}):
            corps, statut = ecriture._detourner()
            assert statut == 403 and corps.get_json()["code"] == "lecture_seule"


class TestEcriturePorteTracee:

    def _porte(self, app):
        for f in app.before_request_funcs.get(None, []):
            if f.__name__ == "_porte_ecriture":
                return f
        pytest.fail("porte d'écriture non branchée")

    def test_refus_trace_dans_le_fichier_demande(self, app, monkeypatch, tmp_path):
        from Code import ecriture
        trace = tmp_path / "porte.tsv"
        monkeypatch.setenv("OPTIQ_TRACE_PORTE", str(trace))
        monkeypatch.setattr(ecriture, "porte", lambda *a, **k: "lecture_seule")
        monkeypatch.setattr(ecriture, "current_user",
                            lambda: SimpleNamespace(status="user"))
        with app.test_request_context("/tools/add", method="POST", json={}):
            _corps, statut = self._porte(app)()
        assert statut == 403
        assert trace.read_text() == "lecture_seule\tPOST\t/tools/add\tuser\n"

    def test_refus_anonyme_trace_un_tiret(self, app, monkeypatch, tmp_path):
        from Code import ecriture
        trace = tmp_path / "porte.tsv"
        monkeypatch.setenv("OPTIQ_TRACE_PORTE", str(trace))
        monkeypatch.setattr(ecriture, "porte", lambda *a, **k: "non_connecte")
        monkeypatch.setattr(ecriture, "current_user", lambda: None)
        with app.test_request_context("/api/x", method="DELETE"):
            _corps, statut = self._porte(app)()
        assert statut == 401
        assert trace.read_text() == "non_connecte\tDELETE\t/api/x\t-\n"

    def test_sans_variable_rien_n_est_trace(self, app, monkeypatch, tmp_path):
        from Code import ecriture
        monkeypatch.delenv("OPTIQ_TRACE_PORTE", raising=False)
        monkeypatch.setattr(ecriture, "porte", lambda *a, **k: "lecture_seule")
        with app.test_request_context("/tools/add", method="POST", json={}):
            _corps, statut = self._porte(app)()
        assert statut == 403
        assert list(tmp_path.iterdir()) == []


# ══════════════════════════════════════════════════════════════════════════
#  roles_permanents.py
# ══════════════════════════════════════════════════════════════════════════

class TestRolesPermanents:

    def test_sans_role_et_sans_creation_rend_none(self, app, monkeypatch):
        from Code import roles_permanents
        from Code.models.models import Role

        class _Q:
            def all(self):
                return []

        with app.app_context():
            monkeypatch.setattr(Role, "query", _Q())
            assert roles_permanents.role_dev_competences(creer=False) is None

    @pytest.mark.parametrize("brut", [None, "", "{pas du json", "[1, 2]", '"chaine"'])
    def test_bandes_illisibles_rendent_none(self, brut):
        from Code.roles_permanents import _bandes
        assert _bandes(SimpleNamespace(optiqcarto_data=brut)) is None

    def test_bandes_du_format_entite(self):
        from Code.roles_permanents import _bandes
        brut = json.dumps({"format": "optiqcarto/entity", "diagram": {
            "bands": [{"label": " Niveau 1 "}, {"label": None}, "pas un dict"]}})
        assert _bandes(SimpleNamespace(optiqcarto_data=brut)) == {"Niveau 1", ""}

    def test_bandes_format_entite_sans_diagramme(self):
        from Code.roles_permanents import _bandes
        brut = json.dumps({"format": "optiqcarto/entity", "diagram": None})
        assert _bandes(SimpleNamespace(optiqcarto_data=brut)) is None

    def test_reprise_deja_faite_ne_relit_rien(self, app, monkeypatch):
        from Code.extensions import db
        from Code import roles_permanents
        from Code.models.models import AppSetting
        with app.app_context():
            monkeypatch.setattr(db.session, "get",
                                lambda modele, cle: AppSetting(key=cle, value="1"))
            assert roles_permanents.reprendre_roles_hors_carte() == 0

    def test_reprise_base_illisible_rend_zero(self, app, monkeypatch):
        from Code.extensions import db
        from Code import roles_permanents

        def _casse(*_a):
            raise RuntimeError("table absente")

        appels = []
        with app.app_context():
            monkeypatch.setattr(db.session, "get", _casse)
            monkeypatch.setattr(db.session, "rollback", lambda: appels.append(1))
            assert roles_permanents.reprendre_roles_hors_carte() == 0
        assert appels == [1]


# ══════════════════════════════════════════════════════════════════════════
#  carto_access.py
# ══════════════════════════════════════════════════════════════════════════

class TestCartoAccesBranchesRares:

    def test_user_role_ids_sans_compte(self):
        from Code.carto_access import user_role_ids
        assert user_role_ids(None) == set()
        assert user_role_ids(0) == set()

    def test_entity_statuts_sans_entite(self):
        from Code.carto_access import entity_statuts
        assert entity_statuts(None) == set()

    def test_lecture_et_ecriture_sans_entite_ou_sans_compte(self, app):
        from Code.carto_access import can_edit, can_read
        e = SimpleNamespace(owner_id=None, is_shared=False, id=-1)
        with app.test_request_context():
            assert can_read(None) is False and can_edit(None) is False
            assert can_read(e) is False and can_edit(e) is False

    def test_readable_entities_et_entity_sans_compte(self, app):
        from Code.carto_access import readable_entities, readable_entity
        with app.test_request_context():
            assert readable_entities() == []
            assert readable_entity(None) is None
            assert readable_entity(0) is None

    def test_carto_commune_fermee_au_compte(self, app):
        from Code.carto_access import can_read
        e = SimpleNamespace(owner_id=-99, is_shared=False, id=-1)
        u = SimpleNamespace(id=12345, status="user")
        assert can_read(e, u) is False

    def test_review_et_gestion_sans_compte(self, app):
        from Code.carto_access import can_manage_access, can_review
        with app.test_request_context():
            assert can_review() is False
            assert can_manage_access() is False

    def test_set_statut_refuse_palier_inconnu_et_verrou(self):
        from Code.carto_access import STATUT_VERROU, set_statut
        e = SimpleNamespace(id=-1, statuts_regles=True)
        assert set_statut(e, "palier_inexistant", True) is False
        assert set_statut(e, STATUT_VERROU, False) is False
