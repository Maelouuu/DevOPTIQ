# -*- coding: utf-8 -*-
"""Socle — les dernières branches défensives encore jamais exécutées.

Chacune de ces lignes protège un cas que la suite ne provoquait pas : une
connexion SQLite qui refuse un PRAGMA, une clé IA ré-enregistrée, un niveau HSC
traduit hors requête, une carto illisible pendant la reprise des rôles, un lien
qui vise une donnée disparue… Les tests posent ce cas, isolément, et remettent
tout en place derrière eux (la base et la session sont partagées).
"""
import json
import sqlite3
import types

import pytest


def _entite(client, eid):
    with client.session_transaction() as s:
        s["active_entity_id"] = eid


# ── extensions.set_sqlite_pragmas ───────────────────────────────────────────

class _CurseurRetif:
    def __init__(self):
        self.ferme = False
        self.essais = []

    def execute(self, sql):
        self.essais.append(sql)
        raise sqlite3.OperationalError("database is locked")

    def close(self):
        self.ferme = True


class TestPragmasSqlite:

    def test_pragma_refuse_est_avale_et_le_curseur_ferme(self):
        from Code.extensions import set_sqlite_pragmas
        curseur = _CurseurRetif()

        class Connexion(sqlite3.Connection):
            def cursor(self, *a, **k):
                return curseur

        conn = sqlite3.connect(":memory:", factory=Connexion)
        try:
            set_sqlite_pragmas(conn, None)
        finally:
            conn.close()
        assert len(curseur.essais) == 2
        assert "journal_mode" in curseur.essais[0]
        assert "busy_timeout" in curseur.essais[1]
        assert curseur.ferme is True

    def test_connexion_non_sqlite_est_ignoree(self):
        from Code.extensions import set_sqlite_pragmas
        # Aucun appel : un objet quelconque n'a pas de curseur à ouvrir.
        set_sqlite_pragmas(object(), None)


# ── ai_key ──────────────────────────────────────────────────────────────────

class TestCleIa:

    def test_cle_reenregistree_remplace_la_valeur_en_base(self, app):
        from Code.ai_key import set_openai_key, _SETTING_KEY
        from Code.extensions import db
        from Code.models.models import AppSetting
        with app.app_context():
            avant = db.session.get(AppSetting, _SETTING_KEY)
            avant = avant.value if avant else None
            try:
                set_openai_key("sk-premiere-163")
                set_openai_key("sk-seconde-163")
                rows = AppSetting.query.filter_by(key=_SETTING_KEY).all()
                assert len(rows) == 1
                assert rows[0].value == "sk-seconde-163"
            finally:
                set_openai_key(avant or "")
            row = db.session.get(AppSetting, _SETTING_KEY)
            assert (row.value if row else None) == avant

    @pytest.mark.parametrize("cle, attendu", [
        ("sk-court", "sk" + "•" * 8),
        ("123456789012", "12" + "•" * 8),
    ])
    def test_cle_courte_masquee_apres_deux_caracteres(self, cle, attendu):
        from Code.ai_key import mask_key
        assert mask_key(cle) == attendu

    def test_cle_longue_garde_debut_et_fin(self):
        from Code.ai_key import mask_key
        assert mask_key("sk-ant-1234567890ABCD") == "sk-ant-" + "•" * 12 + "ABCD"


# ── translations.hsc_level_label ────────────────────────────────────────────

class TestNiveauHscHorsRequete:

    def test_valeur_absente_donne_chaine_vide(self):
        from Code.translations import hsc_level_label
        assert hsc_level_label(None) == ""
        assert hsc_level_label(None, "en") == ""

    def test_sans_requete_retombe_sur_la_langue_par_defaut(self, app):
        from Code.translations import hsc_level_label, _FALLBACK
        with app.app_context():
            # Hors requête, `session` lève RuntimeError : la langue de repli
            # s'applique au lieu de faire tomber l'appelant.
            assert hsc_level_label("3") == hsc_level_label("3", _FALLBACK)
            assert hsc_level_label("3") != ""


# ── prompts._license_prompts_key ────────────────────────────────────────────

class TestClePromptsLicence:

    def test_contexte_illisible_donne_none(self, monkeypatch):
        import flask
        from Code.prompts import _license_prompts_key
        monkeypatch.setattr(flask, "current_app", types.SimpleNamespace())
        assert _license_prompts_key() is None

    def test_cle_lue_dans_l_etat_de_licence(self, app, monkeypatch):
        from Code.prompts import _license_prompts_key
        with app.app_context():
            monkeypatch.setitem(app.config, "LICENSE_STATE",
                                {"info": {"prompts_key": "cle-163"}})
            assert _license_prompts_key() == "cle-163"


# ── licensing.verify_license_bytes ──────────────────────────────────────────

class TestLicenceMalformee:

    def test_license_error_du_decodage_est_relancee_telle_quelle(self, monkeypatch):
        import Code.licensing as lic
        erreur = lic.LicenseError("signature tronquée")

        def _boom(raw):
            raise erreur
        monkeypatch.setattr(lic, "json", types.SimpleNamespace(loads=_boom))
        with pytest.raises(lic.LicenseError) as exc:
            lic.verify_license_bytes(b"{}")
        # Relancée telle quelle : pas ré-emballée en « Fichier de licence malformé ».
        assert exc.value is erreur

    def test_contenu_non_json_est_malforme(self):
        import Code.licensing as lic
        with pytest.raises(lic.LicenseError, match="malformé"):
            lic.verify_license_bytes(b"pas du json")


# ── permissions.migrer_anciens_champions ────────────────────────────────────

class TestRepriseChampionsStatutVide:

    def test_compte_sans_statut_est_saute(self, app, monkeypatch):
        import Code.permissions as perm
        sans_statut = types.SimpleNamespace(status=None)
        vide = types.SimpleNamespace(status="   ")
        ancien = types.SimpleNamespace(status="champion")
        faux_user = types.SimpleNamespace(
            query=types.SimpleNamespace(all=lambda: [sans_statut, vide, ancien]))
        monkeypatch.setattr(perm, "User", faux_user)
        monkeypatch.setattr(perm, "_marquer_reprise", lambda: None)
        with app.app_context():
            assert perm.migrer_anciens_champions(force=True) == 1
        assert sans_statut.status is None
        assert vide.status == "   "
        assert ancien.status == perm.COORDINATOR_STATUS


# ── carto_access.can_propose / competences_acces.collaborateurs_de ──────────

class TestDroitsSansObjet:

    def test_pas_de_proposition_sur_une_carto_absente(self, app, ids):
        from Code.carto_access import can_propose
        from Code.models.models import User
        with app.app_context():
            user = User.query.get(ids["user_id"])
            assert can_propose(None, user) is False

    def test_pas_de_proposition_sur_une_carto_privee_d_un_autre(self, app, ids):
        from Code.carto_access import can_propose
        from Code.models.models import User
        with app.app_context():
            user = User.query.get(ids["user_id"])
            carto = types.SimpleNamespace(owner_id=user.id + 10_000, is_shared=False, id=-1)
            assert can_propose(carto, user) is False

    def test_aucun_acteur_aucun_collaborateur(self, app):
        from Code.competences_acces import collaborateurs_de
        with app.app_context():
            assert collaborateurs_de(None) == ([], False)


# ── roles_permanents.reprendre_roles_hors_carte ─────────────────────────────

@pytest.fixture()
def carto_illisible(app):
    from Code.extensions import db
    from Code.models.models import Entity, Role
    with app.app_context():
        e = Entity(name="Carto illisible 163", description="t163",
                   optiqcarto_data="{pas du json")
        db.session.add(e); db.session.flush()
        r = Role(name="Rôle orphelin 163", entity_id=e.id)
        db.session.add(r); db.session.commit()
        d = {"entity": e.id, "role": r.id}
    yield d
    with app.app_context():
        Role.query.filter_by(entity_id=d["entity"]).delete()
        Entity.query.filter_by(id=d["entity"]).delete()
        db.session.commit()


class TestRepriseHorsCarteCartoIllisible:

    def test_carto_illisible_est_laissee_telle_quelle(self, app, carto_illisible):
        from Code.extensions import db
        from Code.models.models import AppSetting, Role
        from Code.roles_permanents import reprendre_roles_hors_carte, CLE_REPRISE_HORS_CARTE
        with app.app_context():
            marque_avant = db.session.get(AppSetting, CLE_REPRISE_HORS_CARTE) is not None
            try:
                n = reprendre_roles_hors_carte(force=True,
                                               entity_ids=[carto_illisible["entity"]])
                assert n == 0
                # On ne devine pas : le rôle d'une carto illisible n'est pas marqué.
                assert not Role.query.get(carto_illisible["role"]).hors_carte
            finally:
                if not marque_avant:
                    AppSetting.query.filter_by(key=CLE_REPRISE_HORS_CARTE).delete()
                    db.session.commit()


# ── /cadence/consistency : lien vers une donnée disparue ────────────────────

@pytest.fixture()
def lien_fantome(app, ids):
    from Code.extensions import db
    from Code.models.models import Link
    with app.app_context():
        lk = Link(entity_id=ids["entity_id"], source_data_id=987_163,
                  target_activity_id=ids["activity_id"], type="input")
        db.session.add(lk); db.session.commit()
        lid = lk.id
    yield lid
    with app.app_context():
        Link.query.filter_by(id=lid).delete()
        db.session.commit()


class TestCadenceLienFantome:

    def test_lien_vers_donnee_absente_est_ignore(self, auth_client, ids, lien_fantome):
        _entite(auth_client, ids["entity_id"])
        r = auth_client.get("/cadence/consistency")
        assert r.status_code == 200
        body = r.get_json()
        assert all(w["source_data_id"] != 987_163 for w in body["warnings"])
        assert body["count"] == len(body["warnings"])


# ── pulse_track._enabled hors mode test ─────────────────────────────────────

class TestTelemetrieActivation:

    def test_hors_test_suit_la_variable_pulse_disabled(self, app, monkeypatch):
        from Code.routes.pulse_track import _enabled
        with app.app_context():
            monkeypatch.setitem(app.config, "TESTING", False)
            monkeypatch.setitem(app.config, "PULSE_FORCE", False)
            monkeypatch.setenv("PULSE_DISABLED", "1")
            assert _enabled() is False
            monkeypatch.setenv("PULSE_DISABLED", "0")
            assert _enabled() is True
            monkeypatch.delenv("PULSE_DISABLED")
            assert _enabled() is True

    def test_en_test_desactivee_sauf_forcage(self, app, monkeypatch):
        from Code.routes.pulse_track import _enabled
        with app.app_context():
            monkeypatch.setitem(app.config, "PULSE_FORCE", False)
            assert _enabled() is False
            monkeypatch.setitem(app.config, "PULSE_FORCE", True)
            assert _enabled() is True


# ── propose_common / propose_savoirs / propose_savoir_faires ────────────────

class TestProposeClientEtPromptsAbsents:

    def test_client_ia_disponible_est_rendu_sans_raison(self, monkeypatch):
        import Code.ai_client
        from Code.routes.propose_common import openai_client_or_none
        sentinelle = object()
        monkeypatch.setattr(Code.ai_client, "make_ai_client",
                            lambda: (sentinelle, "modele-163", None))
        assert openai_client_or_none() == (sentinelle, None)

    def test_client_ia_indisponible_rend_la_raison(self, monkeypatch):
        import Code.ai_client
        from Code.routes.propose_common import openai_client_or_none
        monkeypatch.setattr(Code.ai_client, "make_ai_client",
                            lambda: (None, None, "no-key"))
        assert openai_client_or_none() == (None, "no-key")

    @pytest.mark.parametrize("module, url, origine", [
        ("Code.routes.propose_savoirs", "/propose_savoirs/propose", "savoir"),
        ("Code.routes.propose_savoir_faires", "/propose_savoir_faires/propose", "savoir_faire"),
    ])
    def test_prompts_indisponibles_repli_sans_appel_ia(self, auth_client, monkeypatch,
                                                       module, url, origine):
        import importlib
        mod = importlib.import_module(module)

        class _ClientInterdit:
            @property
            def chat(self):
                raise AssertionError("aucun appel IA sans prompt")

        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (_ClientInterdit(), None))
        monkeypatch.setattr(mod, "get_prompt", lambda *a, **k: None)
        r = auth_client.post(url, data=json.dumps({"name": "Act 163",
                                                    "savoir_faires": ["Souder"]}),
                             content_type="application/json")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "prompts-unavailable"
        assert isinstance(body["proposals"], list) and body["proposals"]
