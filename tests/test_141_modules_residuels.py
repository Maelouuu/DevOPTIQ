# -*- coding: utf-8 -*-
"""Couverture résiduelle de trois modules transverses.

- `Code/bienvenue.py` : la fenêtre de bienvenue doit se dégrader sans jamais
  casser la page — fichier de nouveautés absent ou illisible, file de
  propositions en erreur, table absente sur une base ancienne.
- `Code/propositions_activite.py` : lecture d'un geste proposé (famille,
  verbe, activité et nom de l'objet retrouvés en base) et rejeu tout-ou-rien.
- `Code/role_i18n.py` : traduction des noms de rôles, avec et sans IA.

Chaque test est autonome : objets factices ou données dédiées nettoyées,
monkeypatch restauré par pytest.
"""
import json
from types import SimpleNamespace

import pytest


class _Casse:
    """Un « modèle » dont toute requête lève : simule une table absente."""

    class _Q:
        def __getattr__(self, _nom):
            raise RuntimeError("table absente")

    query = _Q()


def _fausse_prop(genre="carto", author_id=None, entity_id=1, quand=None):
    return SimpleNamespace(author_id=author_id, entity=None, entity_id=entity_id,
                           submitted_at=quand if genre == "fiche" else None,
                           created_at=quand if genre == "carto" else None,
                           actions="[]")


# ══════════════════════════════════════════════════════════════════════════
#  bienvenue.py
# ══════════════════════════════════════════════════════════════════════════

class TestBienvenueSignature:

    def _pointer(self, monkeypatch, chemin):
        from Code import bienvenue
        monkeypatch.setattr(bienvenue, "_fichier_cure", lambda: str(chemin))

    def test_fichier_absent_donne_signature_vide(self, tmp_path, monkeypatch):
        from Code import bienvenue
        self._pointer(monkeypatch, tmp_path / "absent.json")
        assert bienvenue._items_bruts() == []
        assert bienvenue.signature_nouveautes() == ""

    def test_fichier_illisible_donne_signature_vide(self, tmp_path, monkeypatch):
        from Code import bienvenue
        f = tmp_path / "casse.json"
        f.write_text("{ pas du json", encoding="utf-8")
        self._pointer(monkeypatch, f)
        assert bienvenue._items_bruts() == []
        assert bienvenue.signature_nouveautes() == ""

    def test_fichier_qui_n_est_pas_une_liste_est_ignore(self, tmp_path, monkeypatch):
        from Code import bienvenue
        f = tmp_path / "objet.json"
        f.write_text('{"id": "x"}', encoding="utf-8")
        self._pointer(monkeypatch, f)
        assert bienvenue._items_bruts() == []

    def test_seules_des_entrees_non_dict_donnent_signature_vide(
            self, tmp_path, monkeypatch):
        from Code import bienvenue
        f = tmp_path / "scalaires.json"
        f.write_text('["a", 3, null]', encoding="utf-8")
        self._pointer(monkeypatch, f)
        assert bienvenue.signature_nouveautes() == ""

    def test_entree_sans_id_prend_l_empreinte_de_ses_champs(
            self, tmp_path, monkeypatch):
        import hashlib
        from Code import bienvenue
        f = tmp_path / "sans_id.json"
        f.write_text(json.dumps([{"title": "Titre", "desc": "Texte"}, "bruit",
                                 {"id": "  stable  "}]), encoding="utf-8")
        self._pointer(monkeypatch, f)
        attendu = hashlib.sha1("Titre\x1fTexte".encode("utf-8")).hexdigest()[:10]
        assert bienvenue.signature_nouveautes() == (
            bienvenue.VERSION_SIGNATURE + ":" + attendu + "|stable")


class TestBienvenueSansCompte:
    """Sans session, chaque fonction rend sa valeur neutre."""

    def test_portes_sans_compte(self, app):
        from Code import bienvenue
        with app.test_request_context("/"):
            assert bienvenue.portes_ouvertes() == []

    def test_deux_files_sans_compte(self, app):
        from Code import bienvenue
        with app.app_context():
            assert bienvenue._deux_files(None) == ([], [])

    def test_propositions_sans_compte(self, app):
        from Code import bienvenue
        with app.test_request_context("/"):
            assert bienvenue.propositions_recues()["n"] == 0
            assert bienvenue.propositions_recues()["lignes"] == []

    def test_attentes_sans_compte(self, app):
        from Code import bienvenue
        with app.test_request_context("/"):
            assert bienvenue.attentes() == []

    def test_signature_vue_sans_compte(self, app):
        from Code import bienvenue
        with app.test_request_context("/"):
            assert bienvenue.signature_vue() is None

    def test_marquer_vue_sans_compte(self, app):
        from Code import bienvenue
        with app.test_request_context("/"):
            assert bienvenue.marquer_vue() is False


class TestBienvenueDegradee:
    """Une source en erreur ne casse jamais la fenêtre."""

    def test_files_de_propositions_en_erreur_sont_vides(self, app, monkeypatch):
        from Code import bienvenue
        from Code.routes import activite_propositions, carto_sharing

        def _boum(_u):
            raise RuntimeError("file indisponible")

        monkeypatch.setattr(carto_sharing, "propositions_a_examiner", _boum)
        monkeypatch.setattr(activite_propositions, "propositions_a_examiner", _boum)
        with app.app_context():
            assert bienvenue._deux_files(SimpleNamespace(id=1)) == ([], [])

    def test_auteurs_illisibles_deviennent_anonymes(self, app, monkeypatch):
        from Code import bienvenue
        from Code.models import models
        monkeypatch.setattr(bienvenue, "_deux_files",
                            lambda _u: ([_fausse_prop("carto", author_id=999)], []))
        monkeypatch.setattr(models, "User", _Casse)
        with app.app_context():
            r = bienvenue.propositions_recues(SimpleNamespace(id=1), "fr")
        assert r["n"] == 1
        assert r["lignes"][0]["auteur"] == "Un collaborateur"
        assert r["lignes"][0]["quoi"] == "la cartographie"

    def test_gestes_illisibles_comptent_zero(self, app, monkeypatch):
        from Code import bienvenue, propositions_activite

        def _boum(_cr):
            raise ValueError("actions illisibles")

        monkeypatch.setattr(bienvenue, "_deux_files",
                            lambda _u: ([], [_fausse_prop("fiche")]))
        monkeypatch.setattr(propositions_activite, "gestes", _boum)
        with app.app_context():
            r = bienvenue.propositions_recues(SimpleNamespace(id=1), "fr")
        assert r["lignes"][0]["genre"] == "fiche"
        assert r["lignes"][0]["quoi"] == "0 modification(s) de fiche"

    def test_attentes_tables_absentes_rendent_liste_vide(self, app, monkeypatch):
        from Code import bienvenue
        from Code.models import models
        monkeypatch.setattr(models, "ActivityChangeRequest", _Casse)
        monkeypatch.setattr(models, "CartoChangeRequest", _Casse)
        monkeypatch.setattr(models, "SessionEvaluation", _Casse)
        with app.app_context():
            assert bienvenue.attentes(SimpleNamespace(id=1), "fr") == []

    def test_modeles_absents_sont_ignores(self, app, monkeypatch):
        from Code import bienvenue
        from Code.models import models
        monkeypatch.delattr(models, "CartoChangeRequest")
        noms = [m.__name__ for m in bienvenue._modeles_propositions()]
        assert noms == ["ActivityChangeRequest"]

    def test_signature_vue_table_absente_rend_none(self, app, monkeypatch, ids):
        from Code import bienvenue
        from Code.models import models
        monkeypatch.setattr(models, "WelcomeSeen", _Casse)
        with app.app_context():
            assert bienvenue.signature_vue(SimpleNamespace(id=ids["user_id"])) is None

    def test_marquer_vue_table_absente_rend_false(self, app, monkeypatch, ids):
        from Code import bienvenue
        from Code.models import models
        monkeypatch.setattr(models, "WelcomeSeen", _Casse)
        with app.app_context():
            assert bienvenue.marquer_vue(SimpleNamespace(id=ids["user_id"]),
                                         "sig") is False

    def test_nouveautes_changelog_en_erreur_rend_liste_vide(self, app, monkeypatch):
        from Code import bienvenue
        from Code.routes import changelog

        def _boum():
            raise RuntimeError("changelog cassé")

        monkeypatch.setattr(changelog, "_read_curated", _boum)
        assert bienvenue.nouveautes("fr") == []


class TestBienvenueMarquerVue:

    @pytest.fixture
    def compte(self, app):
        from werkzeug.security import generate_password_hash
        from Code.extensions import db
        from Code.models.models import User, WelcomeSeen
        with app.app_context():
            u = User(first_name="Marque", last_name="Vue",
                     email="t141-marquer-vue@devoptiq.com",
                     password=generate_password_hash("Test1234!"), status="user")
            db.session.add(u)
            db.session.commit()
            uid = u.id
        yield uid
        with app.app_context():
            ligne = db.session.get(WelcomeSeen, uid)
            if ligne:
                db.session.delete(ligne)
            u = db.session.get(User, uid)
            if u:
                db.session.delete(u)
            db.session.commit()

    def test_signature_par_defaut_est_celle_du_serveur(self, app, compte):
        from Code import bienvenue
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            u = db.session.get(User, compte)
            assert bienvenue.marquer_vue(u) is True
            assert bienvenue.signature_vue(u) == bienvenue.signature_nouveautes()

    def test_marquer_vue_ecrase_la_signature_precedente(self, app, compte):
        from Code import bienvenue
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            u = db.session.get(User, compte)
            bienvenue.marquer_vue(u, "ancienne")
            bienvenue.marquer_vue(u, "nouvelle")
            assert bienvenue.signature_vue(u) == "nouvelle"


# ══════════════════════════════════════════════════════════════════════════
#  propositions_activite.py
# ══════════════════════════════════════════════════════════════════════════

class TestPropositionsCheminEtGeste:

    def test_chemin_vide_n_est_pas_proposable(self):
        from Code.propositions_activite import chemin_propasable
        assert chemin_propasable("") is False
        assert chemin_propasable(None) is False

    def test_chemin_racine_n_est_pas_proposable(self):
        from Code.propositions_activite import chemin_propasable
        assert chemin_propasable("/") is False
        assert chemin_propasable("///") is False

    def test_hors_liste_rend_none(self, app):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            assert lire_geste("/comptes/delete/3", "POST", {}) is None

    def test_contrainte_sous_activities(self, app):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            g = lire_geste("/activities/constraints/add", "POST",
                           {"description": "Délai légal"})
        assert g["op"] == "contrainte.add"
        assert g["objet"] == "Délai légal"

    def test_role_de_tache_retire(self, app, ids):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            g = lire_geste("/tasks/%s/roles/9" % ids["task_id"], "DELETE", {})
        assert g["op"] == "task.role_del"
        assert g["activity_id"] == ids["activity_id"]

    def test_role_de_tache_ajoute_retrouve_l_activite_par_la_tache(self, app, ids):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            g = lire_geste("/tasks/%s/roles" % ids["task_id"], "POST", {})
        assert g["op"] == "task.role_add"
        assert g["activity_id"] == ids["activity_id"]
        assert g["activite"] == "Activité Test"

    def test_tache_inconnue_n_a_pas_d_activite(self, app):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            g = lire_geste("/tasks/987654", "PUT", {})
        assert g["activity_id"] is None
        assert g["objet"] is None

    def test_outil_remplace_et_jamais_rattache_a_une_activite(self, app, ids):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            g = lire_geste("/gestion_outils/5/replace", "POST",
                           {"activity_id": ids["activity_id"]})
        assert g["op"] == "tool.replace"
        assert g["activity_id"] is None

    def test_savoir_retrouve_l_activite_dans_l_url(self, app, ids):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            g = lire_geste("/savoirs/%s/42" % ids["activity_id"], "PUT", {})
        assert g["op"] == "savoir.update"
        assert g["activity_id"] == ids["activity_id"]

    def test_methode_inconnue_vaut_modification(self, app):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            g = lire_geste("/aptitudes/add", "OPTIONS", {"name": "x"})
        assert g["op"] == "aptitude.update"

    def test_corps_non_dict_est_ignore(self, app):
        from Code.propositions_activite import lire_geste
        with app.app_context():
            g = lire_geste("/skills/add", "POST", ["pas", "un", "dict"])
        assert g["corps"] == {}


class TestPropositionsNomEnBase:

    def test_nom_de_la_tache_lu_en_base(self, app, ids):
        from Code.propositions_activite import _nom_objet
        with app.app_context():
            nom = _nom_objet("task", ["tasks", str(ids["task_id"])], {})
        assert nom == "Tâche Test"

    def test_nom_vide_dans_le_corps_retombe_sur_la_base(self, app, ids):
        from Code.propositions_activite import _nom_objet
        with app.app_context():
            nom = _nom_objet("task", ["tasks", str(ids["task_id"])],
                             {"name": "   ", "description": 12})
        assert nom == "Tâche Test"

    def test_nom_tronque_a_200(self, app):
        from Code.propositions_activite import _nom_objet
        with app.app_context():
            assert len(_nom_objet("task", ["tasks"], {"name": "x" * 500})) == 200

    def test_famille_sans_modele_rend_none(self, app):
        from Code.propositions_activite import _nom_en_base
        with app.app_context():
            assert _nom_en_base("contrainte", ["constraints", "1"]) is None

    def test_identifiants_absents_rendent_none(self, app):
        from Code.propositions_activite import _nom_en_base
        with app.app_context():
            assert _nom_en_base("tool", ["gestion_outils", "987654", "edit"]) is None

    def test_dernier_identifiant_existant_est_retenu(self, app, ids):
        from Code.propositions_activite import _nom_en_base
        with app.app_context():
            nom = _nom_en_base("task", ["tasks", str(ids["task_id"]), "987654"])
        assert nom == "Tâche Test"

    def test_garant_role_inconnu_rend_none(self, app):
        from Code.propositions_activite import _nom_objet
        with app.app_context():
            assert _nom_objet("garant", ["roles", "garant", "activity", "1"],
                              {"role_id": 987654}) is None


class TestPropositionsBrouillon:

    def test_brouillon_sans_compte_ou_sans_carto(self, app, ids):
        from Code.propositions_activite import brouillon
        with app.app_context():
            assert brouillon(None, SimpleNamespace(id=ids["entity_id"])) is None
            assert brouillon(SimpleNamespace(id=ids["user_id"]), None) is None

    def test_gestes_illisibles_rendent_liste_vide(self):
        from Code.propositions_activite import gestes
        assert gestes(SimpleNamespace(actions="{pas du json")) == []
        assert gestes(SimpleNamespace(actions=12)) == []

    def test_gestes_qui_ne_sont_pas_une_liste(self):
        from Code.propositions_activite import gestes
        assert gestes(SimpleNamespace(actions='{"a": 1}')) == []

    def test_retirer_un_rang_hors_limites(self):
        from Code.propositions_activite import retirer_geste
        cr = SimpleNamespace(actions='[{"chemin": "/tasks/add"}]')
        assert retirer_geste(cr, -1) is False
        assert retirer_geste(cr, 1) is False


class TestPropositionsRejeu:

    CHEMIN = "/tasks/add"

    def _cr(self, gestes):
        return SimpleNamespace(actions=json.dumps(gestes))

    def test_rien_a_rejouer(self, app):
        from Code.propositions_activite import rejouer
        with app.test_request_context("/"):
            assert rejouer(self._cr([]), None) == 0

    def test_route_introuvable_leve_echec(self, app):
        from Code.extensions import db
        from Code.propositions_activite import EchecDeRejeu, rejouer
        vrai = db.session.commit
        with app.test_request_context("/"):
            with pytest.raises(EchecDeRejeu) as e:
                rejouer(self._cr([{"chemin": "/nulle/part/xyz", "methode": "post"}]),
                        None)
        assert e.value.rang == 0
        assert e.value.raison.startswith("route:")
        assert db.session.commit == vrai

    def _point(self, app):
        point, _args = app.url_map.bind("localhost").match(self.CHEMIN,
                                                            method="POST")
        return point

    def test_vue_absente_leve_echec(self, app, monkeypatch):
        from Code.propositions_activite import EchecDeRejeu, rejouer
        monkeypatch.delitem(app.view_functions, self._point(app))
        with app.test_request_context("/"):
            with pytest.raises(EchecDeRejeu) as e:
                rejouer(self._cr([{"chemin": self.CHEMIN}]), None)
        assert e.value.raison == "route inconnue"

    def test_vue_qui_leve_est_rapportee_avec_son_rang(self, app, monkeypatch):
        from Code.extensions import db
        from Code.propositions_activite import EchecDeRejeu, rejouer

        def _boum(**_kw):
            raise RuntimeError("écriture refusée")

        monkeypatch.setitem(app.view_functions, self._point(app), _boum)
        vrai = db.session.commit
        with app.test_request_context("/"):
            with pytest.raises(EchecDeRejeu) as e:
                rejouer(self._cr([{"chemin": self.CHEMIN, "corps": "pas un dict"}]),
                        None)
        assert e.value.raison == "écriture refusée"
        assert e.value.geste["chemin"] == self.CHEMIN
        assert db.session.commit == vrai

    def test_vue_en_erreur_http_leve_echec(self, app, monkeypatch):
        from Code.propositions_activite import EchecDeRejeu, rejouer
        monkeypatch.setitem(app.view_functions, self._point(app),
                            lambda **_kw: ("refus", 403))
        with app.test_request_context("/"):
            with pytest.raises(EchecDeRejeu) as e:
                rejouer(self._cr([{"chemin": self.CHEMIN}]), None)
        assert e.value.raison == "HTTP 403"

    def test_tous_les_gestes_reussis_sont_comptes(self, app, monkeypatch):
        from Code.extensions import db
        from Code.propositions_activite import rejouer
        vus = []

        def _ok(**_kw):
            from flask import session
            vus.append(session.get("marqueur"))
            return "ok"

        monkeypatch.setitem(app.view_functions, self._point(app), _ok)
        vrai = db.session.commit
        with app.test_request_context("/"):
            from flask import session
            session["marqueur"] = "recopie"
            n = rejouer(self._cr([{"chemin": self.CHEMIN}] * 2), None)
        assert n == 2
        assert vus == ["recopie", "recopie"]
        assert db.session.commit == vrai

    def test_statut_d_un_tuple_sans_entier(self):
        from Code.propositions_activite import _statut
        assert _statut(("corps", {"X-Entete": "1"})) == 200
        assert _statut(("corps", {"X": "1"}, 409)) == 409
        assert _statut("texte brut") == 200


# ══════════════════════════════════════════════════════════════════════════
#  role_i18n.py
# ══════════════════════════════════════════════════════════════════════════

def _role(rid, name, fr=None, en=None):
    return SimpleNamespace(id=rid, name=name, name_fr=fr, name_en=en)


class _FauxClient:
    def __init__(self, contenu=None, erreur=None):
        self.contenu, self.erreur = contenu, erreur
        self.chat = SimpleNamespace(completions=self)
        self.appels = []

    def create(self, **kw):
        self.appels.append(kw)
        if self.erreur:
            raise self.erreur
        msg = SimpleNamespace(content=self.contenu)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class TestRoleI18n:

    def test_langue_hors_requete_vaut_francais(self, app):
        from Code.role_i18n import current_lang
        with app.app_context():
            assert current_lang() == "fr"

    def test_langue_non_supportee_vaut_francais(self, app):
        from Code.role_i18n import current_lang
        with app.test_request_context("/"):
            from flask import session
            session["lang"] = "de"
            assert current_lang() == "fr"

    def test_display_name_utilise_le_cache(self, app):
        from Code.role_i18n import display_name
        with app.app_context():
            assert display_name(_role(1, "Chef", en="Head"), "en") == "Head"

    def test_traduction_vide_retombe_sur_le_nom(self, app, monkeypatch):
        from Code import role_i18n
        monkeypatch.setattr(role_i18n, "_translate_batch",
                            lambda noms, lang: ["  ", None])
        r1, r2 = _role(1, "Chef"), _role(2, "Adjoint")
        with app.app_context():
            res = role_i18n.display_names([r1, r2], "en")
        assert res == {1: "Chef", 2: "Adjoint"}
        assert r1.name_en == "Chef"

    def test_echec_du_commit_est_annule_sans_casser(self, app, monkeypatch):
        from Code import role_i18n
        from Code.extensions import db
        monkeypatch.setattr(role_i18n, "_translate_batch",
                            lambda noms, lang: ["Head"])
        annule = []

        def _boum():
            raise RuntimeError("base en lecture seule")

        monkeypatch.setattr(db.session, "commit", _boum)
        monkeypatch.setattr(db.session, "rollback", lambda: annule.append(1))
        with app.app_context():
            res = role_i18n.display_names([_role(7, "Chef")], "en")
        assert res == {7: "Head"}
        assert annule == [1]

    def test_traduction_de_longueur_differente_garde_les_noms(self, app, monkeypatch):
        from Code import role_i18n
        monkeypatch.setattr(role_i18n, "_translate_batch",
                            lambda noms, lang: ["seul"])
        with app.app_context():
            res = role_i18n.display_names([_role(1, "A"), _role(2, "B")], "en")
        assert res == {1: "A", 2: "B"}

    def test_lot_vide_ne_sollicite_pas_l_ia(self):
        from Code.role_i18n import _translate_batch
        assert _translate_batch([], "en") == []

    def test_lot_sans_client_rend_none(self, monkeypatch):
        from Code import role_i18n
        from Code.routes import propose_common
        monkeypatch.setattr(propose_common, "openai_client_or_none",
                            lambda: (None, "pas de clé"))
        assert role_i18n._translate_batch(["Chef"], "en") is None

    def test_lot_traduit_par_l_ia(self, monkeypatch):
        from Code import role_i18n
        from Code.routes import propose_common
        client = _FauxClient(contenu='{"translations": ["Head", "Deputy"]}')
        monkeypatch.setattr(propose_common, "openai_client_or_none",
                            lambda: (client, None))
        assert role_i18n._translate_batch(["Chef", "Adjoint"], "en") == [
            "Head", "Deputy"]
        prompt = client.appels[0]["messages"][0]["content"]
        assert "vers le anglais" in prompt
        assert '["Chef", "Adjoint"]' in prompt

    def test_reponse_ia_de_mauvaise_longueur_rend_none(self, monkeypatch):
        from Code import role_i18n
        from Code.routes import propose_common
        client = _FauxClient(contenu='{"translations": ["Head"]}')
        monkeypatch.setattr(propose_common, "openai_client_or_none",
                            lambda: (client, None))
        assert role_i18n._translate_batch(["Chef", "Adjoint"], "en") is None

    def test_reponse_ia_illisible_rend_none(self, monkeypatch):
        from Code import role_i18n
        from Code.routes import propose_common
        client = _FauxClient(contenu="pas du json")
        monkeypatch.setattr(propose_common, "openai_client_or_none",
                            lambda: (client, None))
        assert role_i18n._translate_batch(["Chef"], "en") is None

    def test_erreur_de_l_ia_rend_none(self, monkeypatch):
        from Code import role_i18n
        from Code.routes import propose_common
        client = _FauxClient(erreur=TimeoutError("délai dépassé"))
        monkeypatch.setattr(propose_common, "openai_client_or_none",
                            lambda: (client, None))
        assert role_i18n._translate_batch(["Chef"], "fr") is None
