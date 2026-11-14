# -*- coding: utf-8 -*-
"""
Page : Import de données (`/api/import`) — branches résiduelles de
Code/routes/import_hub.py que `test_84` et `test_124` ne jouaient pas.

  * lecture de fichiers : trop gros, vide, csv sans séparateur devinable,
    classeur corrompu, plafond de lignes, fin de feuille vide ;
  * noms complets : colonne « nom » qui porte prénom ET nom, scission sans
    capitales, ordre imposé ;
  * l'IA : absente, en panne, réponse partielle (type implicite, en-tête non
    numérique, colonnes en texte) ;
  * la vérification : noms trop longs, doublons, groupes sans activité,
    rôle annoncé sans carto ;
  * les routes : type inconnu, droits, fichier manquant ou vide, IA muette,
    historique au détail corrompu.

Isolation : chaque test HTTP ouvre son PROPRE client ; les objets créés en base
(compte sans carto, ligne d'historique) sont supprimés par leur fixture.
"""
import io
import json
from types import SimpleNamespace

import openpyxl
import pytest
from werkzeug.datastructures import FileStorage

from Code.extensions import db

pytestmark = pytest.mark.import_hub

API = "/api/import"


# ══════════════════════════════════════════════════════════════════════
#  Décor
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture
def hub():
    import Code.routes.import_hub as module
    return module


@pytest.fixture
def ctx(app):
    """Un contexte de requête : `t()` lit la langue en session."""
    with app.test_request_context("/"):
        yield


def _client(app, uid, entity_id=None):
    from Code.models.models import User
    c = app.test_client()
    with app.app_context():
        mail = db.session.get(User, uid).email
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["user_email"] = mail
        s["lang"] = "fr"
        if entity_id is not None:
            s["active_entity_id"] = entity_id
    return c


@pytest.fixture
def admin(app, ids):
    return _client(app, ids["user_id"], ids["entity_id"])


@pytest.fixture
def sans_carto(app):
    """Un compte `user` qui n'écrit dans AUCUNE carto."""
    from Code.models.models import User
    from Code.security import hash_password
    with app.app_context():
        u = User(first_name="T144", last_name="SansCarto", email="t144.sanscarto@devoptiq.com",
                 password=hash_password("Motdepasse123!"), status="user")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield _client(app, uid)
    with app.app_context():
        u = db.session.get(User, uid)
        if u is not None:
            db.session.delete(u)
            db.session.commit()


def _fichier(nom, contenu):
    return FileStorage(stream=io.BytesIO(contenu), filename=nom)


def _xlsx(*feuilles):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nom, lignes in feuilles:
        ws = wb.create_sheet(nom)
        for l in lignes:
            ws.append(l)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════
#  Lecture d'un fichier
# ══════════════════════════════════════════════════════════════════════
class TestImportHubLectureFichier:

    def test_un_flottant_entier_s_ecrit_sans_virgule(self, hub):
        assert hub._txt(3.0) == "3"
        assert hub._txt(2.5) == "2.5"
        assert hub._txt(None) == ""

    def test_un_fichier_trop_gros_est_refuse(self, hub, ctx, monkeypatch):
        monkeypatch.setattr(hub, "MAX_OCTETS", 10)
        with pytest.raises(hub.FichierIllisible):
            hub._lire_feuilles(_fichier("gros.csv", b"x" * 50))

    def test_un_fichier_vide_est_refuse(self, hub, ctx):
        with pytest.raises(hub.FichierIllisible):
            hub._lire_feuilles(_fichier("vide.csv", b""))

    def test_un_classeur_corrompu_est_illisible(self, hub, ctx):
        with pytest.raises(hub.FichierIllisible):
            hub._lire_feuilles(_fichier("casse.xlsx", b"ceci n'est pas un zip"))

    def test_un_csv_sans_separateur_devinable_retombe_sur_la_virgule(self, hub, ctx):
        feuilles = hub._lire_feuilles(_fichier("roles.csv", "Rôle\nQualité\n".encode("utf-8")))
        assert feuilles == [("roles", [["Rôle"], ["Qualité"]])]

    def test_la_lecture_s_arrete_au_plafond_de_lignes(self, hub, ctx, monkeypatch):
        monkeypatch.setattr(hub, "MAX_LIGNES", 2)
        lignes = [["Nom"]] + [["Outil %d" % i] for i in range(100)]
        (_, lues), = hub._lire_feuilles(_fichier("o.xlsx", _xlsx(("Outils", lignes))))
        assert len(lues) == 2 + 50 + 1

    def test_les_lignes_vides_de_fin_sont_elaguees(self, hub):
        assert hub._elaguer([["a", ""], ["", ""], []]) == [["a"]]


# ══════════════════════════════════════════════════════════════════════
#  Noms complets
# ══════════════════════════════════════════════════════════════════════
class TestImportHubNomComplet:

    def test_une_colonne_nom_qui_porte_prenom_et_nom_devient_nom_complet(self, hub):
        donnees = [["Jean Dupont", "a@b.fr"], ["Marie Curie", "m@b.fr"], ["Ada", "x@b.fr"]]
        cor, nc = hub._nom_complet(["Nom", "Email"], {"nom": 0, "email": 1}, donnees)
        assert nc == 0 and cor == {"email": 1}

    def test_une_colonne_nom_de_noms_simples_reste_un_nom(self, hub):
        donnees = [["Dupont", "a@b.fr"], ["Curie", "m@b.fr"]]
        cor, nc = hub._nom_complet(["Nom", "Email"], {"nom": 0, "email": 1}, donnees)
        assert nc is None and cor == {"nom": 0, "email": 1}

    @pytest.mark.parametrize("texte, ordre, attendu", [
        ("", None, ("", "")),
        ("Cher", None, ("", "Cher")),
        ("jean pierre dupont", None, ("jean", "pierre dupont")),
        ("JEAN DUPONT", None, ("JEAN", "DUPONT")),
        ("Dupont Jean", "nom_prenom", ("Jean", "Dupont")),
        ("Jean Dupont", "prenom_nom", ("Jean", "Dupont")),
    ])
    def test_scinder(self, hub, texte, ordre, attendu):
        assert hub._scinder(texte, ordre) == attendu


# ══════════════════════════════════════════════════════════════════════
#  Extraction et analyse d'une feuille
# ══════════════════════════════════════════════════════════════════════
class TestImportHubExtraction:

    def test_une_ligne_d_outils_seule_rejoint_la_tache_du_dessus(self, hub, ctx):
        lignes = [{"activite": "A", "tache": "T1", "outils": "SAP"},
                  {"activite": "", "tache": "", "outils": "Excel"}]
        out = hub._propager_taches(lignes)
        assert len(out) == 1
        assert out[0]["outils"] == "SAP, Excel"

    def test_au_dela_du_plafond_la_part_signale_une_erreur(self, hub, ctx, monkeypatch):
        monkeypatch.setattr(hub, "MAX_LIGNES", 1)
        lignes = [["Nom"], ["O1"], ["O2"], ["O3"]]
        p = hub._part("0:x", "f.xlsx", "Outils", "outils", lignes, 0, {"nom": 0})
        assert p["reconnu"] is False
        assert "erreur" in p and p["lignes"] == []

    def test_une_feuille_sans_aucune_colonne_reconnue_garde_le_type_demande(self, hub, ctx):
        lignes = [["zzz", "qqq"], ["1", "2"]]
        p = hub._analyser_feuille("0:x", "f.xlsx", "Feuil1", lignes, ["outils"], force=True)
        assert p["type"] == "outils" and p["reconnu"] is False

    def test_plusieurs_natures_et_rien_de_reconnu_donne_un_type_vide(self, hub, ctx):
        lignes = [["zzz", "qqq"], ["1", "2"]]
        p = hub._analyser_feuille("0:x", "f.xlsx", "Feuil1", lignes, ["roles", "outils"],
                                  force=True)
        assert p["type"] is None


# ══════════════════════════════════════════════════════════════════════
#  L'IA
# ══════════════════════════════════════════════════════════════════════
class _ClientQuiCasse:
    class chat:
        class completions:
            @staticmethod
            def create(**kw):
                raise RuntimeError("fournisseur en panne")


class TestImportHubIA:

    def test_sans_fournisseur_l_appel_rend_none(self, hub, app, monkeypatch):
        import Code.routes.propose_common as pc
        monkeypatch.setattr(pc, "openai_client_or_none", lambda: (None, "pas de clé"))
        with app.app_context():
            assert hub._appeler_ia("sys", {}) is None

    def test_un_fournisseur_en_panne_rend_none(self, hub, app, monkeypatch):
        import Code.routes.propose_common as pc
        monkeypatch.setattr(pc, "openai_client_or_none", lambda: (_ClientQuiCasse(), None))
        with app.app_context():
            assert hub._appeler_ia("sys", {}) is None

    def test_sans_prompt_l_organisation_rend_none(self, hub, ctx, monkeypatch):
        import Code.prompts as prompts
        monkeypatch.setattr(prompts, "get_prompt", lambda nom: None)
        assert hub._organiser_ia("0:x", "f", "F", [["a"]], ["roles"]) is None

    def _organiser(self, hub, monkeypatch, reponse, types, lignes):
        import Code.prompts as prompts
        monkeypatch.setattr(prompts, "get_prompt", lambda nom: "systeme")
        monkeypatch.setattr(hub, "_appeler_ia", lambda s, c: reponse)
        return hub._organiser_ia("0:x", "f.xlsx", "Feuil1", lignes, types)

    def test_un_type_implicite_vaut_l_unique_nature_demandee(self, hub, ctx, monkeypatch):
        p = self._organiser(hub, monkeypatch,
                            {"type": None, "ligne_entete": "pas un nombre",
                             "colonnes": {"nom": "1"}},
                            ["outils"], [["x", "Outil"], ["", "Marteau"]])
        assert p["type"] == "outils" and p["source"] == "IA"
        # En-tête illisible → ligne 0 ; colonne donnée en TEXTE → acceptée.
        assert p["ligne_entete"] == 0
        assert p["correspondance"] == {"nom": 1}
        assert [l["nom"] for l in p["lignes"]] == ["Marteau"]

    def test_un_type_hors_demande_n_est_pas_retenu(self, hub, ctx, monkeypatch):
        p = self._organiser(hub, monkeypatch, {"type": "users", "remarque": "r"},
                            ["roles", "outils"], [["a"], ["b"]])
        assert p["type"] is None and p["confiance"] == "low"


# ══════════════════════════════════════════════════════════════════════
#  Portée et lignes venues du navigateur
# ══════════════════════════════════════════════════════════════════════
class TestImportHubPortee:

    def test_un_id_de_carto_non_numerique_est_ignore(self, hub, app, ids):
        from Code.models.models import User
        with app.test_request_context("/"):
            moi = db.session.get(User, ids["user_id"])
            cibles = hub._cibles_demandees(moi, ["abc", None, ids["entity_id"]])
        assert [e.id for e in cibles] == [ids["entity_id"]]

    def test_les_lignes_non_dict_sont_ecartees_et_l_index_repare(self, hub):
        out = hub._lignes("outils", ["texte", {"nom": "Scie", "_i": "x"}, {"nom": "Vis", "_i": 7}])
        assert [(l["nom"], l["_i"]) for l in out] == [("Scie", 0), ("Vis", 7)]

    def test_le_libelle_champion_est_reconnu(self, hub, ctx):
        assert hub._statut_compte("champion") == ("champion", True)


# ══════════════════════════════════════════════════════════════════════
#  Vérification
# ══════════════════════════════════════════════════════════════════════
class TestImportHubVerification:

    def test_un_nom_d_outil_trop_long_est_invalide(self, hub, ctx):
        res = hub._verifier_simple("outils", [{"nom": "x" * 300}], [])
        assert res["lignes"][0]["statut"] == "invalide"

    def test_les_comptes_invalides_le_disent(self, hub, app, ids, ctx):
        from Code.models.models import User
        moi = db.session.get(User, ids["user_id"])
        lignes = [
            {"prenom": "", "nom": "", "email": "a@b.fr"},
            {"prenom": "A", "nom": "B", "email": "t144.dup@x.fr"},
            {"prenom": "C", "nom": "D", "email": "t144.dup@x.fr"},
            {"prenom": "E" * 150, "nom": "F", "email": "t144.long@x.fr"},
        ]
        res = hub._verifier_users(lignes, moi, [], {})
        statuts = [l["statut"] for l in res["lignes"]]
        assert statuts == ["invalide", "nouveau", "invalide", "invalide"]

    def test_un_role_sans_carto_avertit_un_role_prevu_informe(self, hub, app, ids, ctx):
        from Code.models.models import Entity, User
        moi = db.session.get(User, ids["user_id"])
        carto = db.session.get(Entity, ids["entity_id"])
        sans = hub._verifier_users(
            [{"prenom": "G", "nom": "H", "email": "t144.r1@x.fr", "role": "T144 Rôle"}],
            moi, [], {})
        assert "avertissement" in sans["lignes"][0]
        prevu = hub._verifier_users(
            [{"prenom": "G", "nom": "H", "email": "t144.r2@x.fr", "role": "T144 Rôle"}],
            moi, [carto], {"roles_prevus": ["T144 Rôle"]})
        assert "info" in prevu["lignes"][0] and "avertissement" not in prevu["lignes"][0]

    def test_taches_sans_activite_doublons_et_trop_longues(self, hub, ctx):
        lignes = [
            {"activite": "", "tache": "Orpheline"},
            {"activite": "T144 Activité", "tache": "Même"},
            {"activite": "T144 Activité", "tache": "Même"},
            {"activite": "T144 Activité", "tache": "y" * 300},
        ]
        res = hub._verifier_taches(lignes, [], {})
        modes = {g["activite_fichier"]: g["mode"] for g in res["groupes"]}
        assert modes[""] == "sans_activite"
        assert [l["statut"] for l in res["lignes"]] == [
            "invalide", "a_rattacher", "invalide", "invalide"]


# ══════════════════════════════════════════════════════════════════════
#  Routes HTTP
# ══════════════════════════════════════════════════════════════════════
class TestImportHubRoutes:

    def test_modele_d_un_type_inconnu_404(self, admin):
        assert admin.get(API + "/modele/licornes").status_code == 404

    def test_lire_type_inconnu_404(self, admin):
        assert admin.post(API + "/lire", data={"type": "licornes"}).status_code == 404

    def test_lire_sans_fichier_400(self, admin):
        assert admin.post(API + "/lire", data={"type": "roles"}).status_code == 400

    def test_lire_feuille_demandee_absente_signale_une_erreur(self, admin):
        r = admin.post(API + "/lire", data={
            "type": "roles", "feuille": "Inexistante",
            "fichiers": (io.BytesIO(_xlsx(("Rôles", [["Rôle"], ["Qualité"]]))), "r.xlsx"),
        }, content_type="multipart/form-data")
        assert r.status_code == 200
        corps = r.get_json()
        assert corps["parts"] == [] and corps["erreurs"][0]["fichier"] == "r.xlsx"

    def test_organiser_type_inconnu_404(self, admin):
        assert admin.post(API + "/organiser", data={"type": "licornes"}).status_code == 404

    def test_organiser_sans_droit_403(self, sans_carto):
        assert sans_carto.post(API + "/organiser", data={"type": "roles"}).status_code == 403

    def test_organiser_sans_fichier_400(self, admin):
        assert admin.post(API + "/organiser", data={"type": "roles"}).status_code == 400

    def test_organiser_fichier_illisible_400(self, admin):
        r = admin.post(API + "/organiser", data={
            "type": "roles", "fichier": (io.BytesIO(b"x"), "r.pdf")},
            content_type="multipart/form-data")
        assert r.status_code == 400

    def test_organiser_classeur_sans_contenu_400(self, admin):
        r = admin.post(API + "/organiser", data={
            "type": "roles", "fichier": (io.BytesIO(_xlsx(("Vide", []))), "v.xlsx")},
            content_type="multipart/form-data")
        assert r.status_code == 400

    def test_verifier_type_inconnu_404(self, admin):
        r = admin.post(API + "/verifier", json={"type": "licornes"})
        assert r.status_code == 404

    def test_rapprocher_sans_droit_403(self, sans_carto):
        assert sans_carto.post(API + "/rapprocher", json={}).status_code == 403

    def test_rapprocher_sans_noms_ne_propose_rien(self, admin, ids):
        r = admin.post(API + "/rapprocher", json={"cibles": [ids["entity_id"]], "noms": []})
        assert r.status_code == 200 and r.get_json() == {"propositions": {}}

    def test_rapprocher_sans_ia_503(self, admin, ids, hub, monkeypatch):
        monkeypatch.setattr(hub, "_appeler_ia", lambda s, c: None)
        r = admin.post(API + "/rapprocher",
                       json={"cibles": [ids["entity_id"]], "noms": ["Quelque chose"]})
        assert r.status_code == 503

    def test_importer_des_roles_sans_carto_cible_400(self, admin):
        r = admin.post(API + "/importer",
                       json={"type": "roles", "lignes": [{"nom": "T144"}], "cibles": []})
        assert r.status_code == 400

    def test_historique_anonyme_403(self, app):
        assert app.test_client().get(API + "/historique").status_code == 403

    def test_historique_detail_corrompu_rendu_vide(self, app, admin, ids):
        from Code.models.models import ImportRecord
        with app.app_context():
            rec = ImportRecord(entity_id=ids["entity_id"], user_id=ids["user_id"],
                               nature="outils", fichier="t144.xlsx", ajoutes=1,
                               detail="{pas du json")
            db.session.add(rec)
            db.session.commit()
            rid = rec.id
        try:
            r = admin.get(API + "/historique?entity_id=%d" % ids["entity_id"])
            assert r.status_code == 200
            ligne = next(l for l in r.get_json()["lignes"] if l["id"] == rid)
            assert ligne["detail"] == [] and ligne["fichier"] == "t144.xlsx"
        finally:
            with app.app_context():
                db.session.delete(db.session.get(ImportRecord, rid))
                db.session.commit()
