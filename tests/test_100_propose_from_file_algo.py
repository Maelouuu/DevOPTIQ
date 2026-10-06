# tests/test_100_propose_from_file_algo.py
"""
Couvre l'algorithme de proposition (_propose_from_job_map, _tokenize,
_parse_file) et les branches d'erreur d'upload/status de propose_from_file.py.
Tests unitaires purs + clients dédiés : aucun état partagé laissé derrière.
"""
import io
from collections import defaultdict

import pytest

pytestmark = pytest.mark.propose_from_file


def _job_map(spec):
    jm = {}
    for job, grps in spec.items():
        d = defaultdict(list)
        for g, comps in grps.items():
            d[g].extend(comps)
        jm[job] = d
    return jm


class TestTokenize:

    def test_retire_mots_vides_et_mots_courts(self):
        from Code.routes.propose_from_file import _tokenize
        assert _tokenize("Le Chief de gestion SQL, Python!") == {"sql", "python"}

    def test_chaine_vide_donne_ensemble_vide(self):
        from Code.routes.propose_from_file import _tokenize
        assert _tokenize("") == set()


class TestProposeFromJobMap:

    def test_poste_correspondant_classe_ses_competences(self):
        from Code.routes.propose_from_file import _propose_from_job_map
        jm = _job_map({"data analyst": {"Technical Skills": ["SQL", "Python"]},
                       "cuisinier": {"Technical Skills": ["Hachage"]}})
        res = _propose_from_job_map("analyse data reporting", jm, ["Technical Skills"])
        assert set(res) == {"SQL", "Python"}

    def test_bonus_nom_de_competence_place_en_tete(self):
        from Code.routes.propose_from_file import _propose_from_job_map
        jm = _job_map({"data analyst": {"Technical Skills": ["Excel", "Reporting data"]}})
        res = _propose_from_job_map("data analyst", jm, ["Technical Skills"])
        assert res[0] == "Reporting data"

    def test_score_partiel_sous_chaine(self):
        from Code.routes.propose_from_file import _propose_from_job_map
        jm = _job_map({"comptabilite": {"Technical Skills": ["Bilan"]}})
        assert _propose_from_job_map("comptabilites", jm, ["Technical Skills"]) == ["Bilan"]

    def test_fallback_score_direct_sur_nom_de_competence(self):
        from Code.routes.propose_from_file import _propose_from_job_map
        jm = _job_map({"zzz": {"Technical Skills": ["Soudure laser", "Peinture"]}})
        assert _propose_from_job_map("soudure", jm, ["Technical Skills"]) == ["Soudure laser"]

    def test_fallback_echantillonnage_quand_aucun_signal(self):
        from Code.routes.propose_from_file import _propose_from_job_map
        comps = [f"Comp{i:02d}" for i in range(40)]
        jm = _job_map({"zzz": {"Technical Skills": comps}})
        res = _propose_from_job_map("xxxx", jm, ["Technical Skills"], max_results=5)
        assert len(res) == 5
        assert set(res) <= set(comps)

    def test_groupe_absent_donne_liste_vide(self):
        from Code.routes.propose_from_file import _propose_from_job_map
        jm = _job_map({"data analyst": {"Technical Skills": ["SQL"]}})
        assert _propose_from_job_map("data", jm, ["Behavioural Competencies"]) == []

    def test_max_results_respecte(self):
        from Code.routes.propose_from_file import _propose_from_job_map
        jm = _job_map({"data analyst": {"Technical Skills": [f"C{i}" for i in range(30)]}})
        assert len(_propose_from_job_map("data", jm, ["Technical Skills"], max_results=4)) == 4


class TestParseFile:

    def test_ignore_lignes_incompletes_et_regroupe_par_poste(self):
        import openpyxl
        from Code.routes.propose_from_file import _parse_file, _parse_stats
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["a", "b", "JobText", "GrpName", "CompName"])
        ws.append([1, 1, "Dev", "Technical Skills", "Python"])
        ws.append([2, 1, "Dev", "Technical Skills", None])
        ws.append([3, 1, None, "Technical Skills", "Orphelin"])
        buf = io.BytesIO()
        wb.save(buf)
        jm = _parse_file(buf.getvalue())
        assert dict(jm["dev"]) == {"Technical Skills": ["Python"]}
        assert _parse_stats(buf.getvalue()) == {"Technical Skills": 1}


class TestUploadStatusFichierInvalide:

    def test_upload_fichier_illisible_renvoie_warning(self, app, ids):
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = 987654
        r = c.post("/propose_from_file/upload",
                   data={"file": (io.BytesIO(b"pas un xlsx"), "x.xlsx")},
                   content_type="multipart/form-data")
        try:
            j = r.get_json()
            assert r.status_code == 200
            assert j["ok"] is True and j["stats"] == {} and j["warning"]
        finally:
            c.delete("/propose_from_file/delete")

    def test_status_fichier_illisible_has_file_true_stats_vides(self, app, ids):
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = 987655
        c.post("/propose_from_file/upload",
               data={"file": (io.BytesIO(b"corrompu"), "x.xlsx")},
               content_type="multipart/form-data")
        try:
            j = c.get("/propose_from_file/status").get_json()
            assert j == {"has_file": True, "stats": {}}
        finally:
            c.delete("/propose_from_file/delete")
