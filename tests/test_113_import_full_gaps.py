# tests/test_113_import_full_gaps.py
"""
Import global Excel : branches restées sans test — enrichissement IA des
activités non appariées, refus d'écriture, erreur serveur à l'injection.

L'IA est toujours simulée (aucun appel réseau) et chaque test crée ses propres
fichiers : la base et la session sont partagées par toute la suite.
"""
import io

import openpyxl
import pytest

pytestmark = pytest.mark.import_full

NOM_INCONNU = "Zorglub Quantique 9000"


def _excel(lignes, entetes=("Department", "Activity", "Guarantor", "Task", "Tool", "Doer", "Approver", "Skills")):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(entetes))
    for ligne in lignes:
        ws.append(list(ligne))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _entite_active(client, entity_id):
    with client.session_transaction() as sess:
        sess["active_entity_id"] = entity_id


def _analyser(client, contenu):
    return client.post(
        "/api/import-full/analyze",
        data={"file": (io.BytesIO(contenu), "import.xlsx")},
        content_type="multipart/form-data",
    )


@pytest.fixture
def fichier_inconnu():
    return _excel([("Dept", NOM_INCONNU, "Chef", "Tâche inconnue", "", "", "", "")])


class TestEnrichissementIA:
    def test_suggestion_sure_ia_passe_dans_mappe(self, auth_client, ids, fichier_inconnu, monkeypatch):
        import Code.routes.import_full as imp
        _entite_active(auth_client, ids["entity_id"])
        monkeypatch.setattr(imp, "_try_openai_enrich", lambda groupes, acts: {
            "resolved": [{
                "activity_name_excel": NOM_INCONNU,
                "activity_id": ids["activity_id"],
                "activity_name_db": "Activité Test",
                "confidence": "high",
                "match_reason": "synonyme",
            }]})
        data = _analyser(auth_client, fichier_inconnu).get_json()
        mappes = data["analysis"]["matched_groups"]
        groupe = next(g for g in mappes if g["activity_name_excel"] == NOM_INCONNU)
        assert groupe["activity_id"] == ids["activity_id"]
        assert groupe["confidence"] == "high"
        assert groupe["match_reason"] == "synonyme"
        assert not any(g["activity_name_excel"] == NOM_INCONNU
                       for g in data["analysis"]["unmatched_groups"])
        assert data["stats"]["unmatched_activities"] == 0

    def test_suggestion_incertaine_reste_a_resoudre_en_tete(self, auth_client, ids, fichier_inconnu, monkeypatch):
        import Code.routes.import_full as imp
        _entite_active(auth_client, ids["entity_id"])
        monkeypatch.setattr(imp, "_try_openai_enrich", lambda groupes, acts: {
            "resolved": [{
                "activity_name_excel": NOM_INCONNU,
                "activity_id": ids["activity_id"],
                "activity_name_db": "Activité Test",
                "confidence": "medium",
                "match_reason": "peut-être",
            }]})
        data = _analyser(auth_client, fichier_inconnu).get_json()
        assert not any(g["activity_name_excel"] == NOM_INCONNU
                       for g in data["analysis"]["matched_groups"])
        groupe = next(g for g in data["analysis"]["unmatched_groups"]
                      if g["activity_name_excel"] == NOM_INCONNU)
        candidats = {p["activity_id"] for p in groupe["possible_matches"]}
        assert ids["activity_id"] in candidats
        assert "medium" in groupe["reason"]
        assert "peut-être" in groupe["reason"]

    def test_suggestion_incertaine_ne_duplique_pas_un_candidat_deja_present(
            self, auth_client, ids, monkeypatch):
        import Code.routes.import_full as imp
        _entite_active(auth_client, ids["entity_id"])
        # Nom proche de l'activité seedée : l'algorithme la propose déjà
        nom = "Activité Tes"
        contenu = _excel([("Dept", nom, "Chef", "T", "", "", "", "")])
        monkeypatch.setattr(imp, "_try_openai_enrich", lambda groupes, acts: {
            "resolved": [{
                "activity_name_excel": g["activity_name_excel"],
                "activity_id": ids["activity_id"],
                "activity_name_db": "Activité Test",
                "confidence": "low",
            } for g in groupes]})
        data = _analyser(auth_client, contenu).get_json()
        for g in data["analysis"]["unmatched_groups"]:
            id_candidats = [p["activity_id"] for p in g["possible_matches"]]
            assert len(id_candidats) == len(set(id_candidats))

    def test_groupe_ignore_par_ia_reste_non_mappe(self, auth_client, ids, fichier_inconnu, monkeypatch):
        import Code.routes.import_full as imp
        _entite_active(auth_client, ids["entity_id"])
        monkeypatch.setattr(imp, "_try_openai_enrich", lambda groupes, acts: {"resolved": []})
        data = _analyser(auth_client, fichier_inconnu).get_json()
        assert any(g["activity_name_excel"] == NOM_INCONNU
                   for g in data["analysis"]["unmatched_groups"])
        assert data["stats"]["unmatched_activities"] >= 1

    def test_ia_indisponible_laisse_l_analyse_algorithmique(self, auth_client, ids, fichier_inconnu, monkeypatch):
        import Code.routes.import_full as imp
        _entite_active(auth_client, ids["entity_id"])
        monkeypatch.setattr(imp, "_try_openai_enrich", lambda groupes, acts: None)
        resp = _analyser(auth_client, fichier_inconnu)
        assert resp.status_code == 200
        assert any(g["activity_name_excel"] == NOM_INCONNU
                   for g in resp.get_json()["analysis"]["unmatched_groups"])


class TestTryOpenaiEnrich:
    GROUPES = [{"activity_name_excel": NOM_INCONNU}]
    ACTIVITES = [{"id": 1, "name": "Activité Test"}]

    def test_sans_cle_retourne_none(self, monkeypatch):
        import Code.routes.import_full as imp
        monkeypatch.setattr(imp, "get_openai_key", lambda: "")
        assert imp._try_openai_enrich(self.GROUPES, self.ACTIVITES) is None

    def test_sans_groupe_non_mappe_retourne_none(self, monkeypatch):
        import Code.routes.import_full as imp
        monkeypatch.setattr(imp, "get_openai_key", lambda: "cle")
        assert imp._try_openai_enrich([], self.ACTIVITES) is None

    def test_sans_prompt_retourne_none(self, monkeypatch):
        import Code.routes.import_full as imp
        monkeypatch.setattr(imp, "get_openai_key", lambda: "cle")
        monkeypatch.setattr(imp, "get_prompt", lambda nom: None)
        assert imp._try_openai_enrich(self.GROUPES, self.ACTIVITES) is None

    def test_reponse_json_est_decodee(self, monkeypatch):
        import Code.ai_client
        import Code.routes.import_full as imp
        vus = {}

        class _Completions:
            def create(self, **kw):
                vus.update(kw)
                msg = type("M", (), {"content": '{"resolved": [], "still_unmatched": []}'})()
                return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

        client = type("Cl", (), {"chat": type("Ch", (), {"completions": _Completions()})()})()
        monkeypatch.setattr(imp, "get_openai_key", lambda: "cle")
        monkeypatch.setattr(imp, "get_prompt", lambda nom: "prompt")
        monkeypatch.setattr(Code.ai_client, "make_ai_client", lambda: (client, "modele-x", None))
        monkeypatch.delenv("OPENAI_CHATBOT_MODEL", raising=False)
        out = imp._try_openai_enrich(self.GROUPES, self.ACTIVITES)
        assert out == {"resolved": [], "still_unmatched": []}
        assert vus["model"] == "modele-x"
        assert NOM_INCONNU in vus["messages"][1]["content"]

    def test_erreur_client_est_avalee(self, monkeypatch):
        import Code.ai_client
        import Code.routes.import_full as imp
        monkeypatch.setattr(imp, "get_openai_key", lambda: "cle")
        monkeypatch.setattr(imp, "get_prompt", lambda nom: "prompt")

        def _boom():
            raise RuntimeError("quota dépassé")

        monkeypatch.setattr(Code.ai_client, "make_ai_client", _boom)
        assert imp._try_openai_enrich(self.GROUPES, self.ACTIVITES) is None


class TestAnalyseRefus:
    def test_aucune_activite_dans_la_carto_donne_400(self, auth_client, app, monkeypatch):
        from Code.extensions import db
        from Code.models.models import Entity
        with app.app_context():
            ent = Entity(name="T113 vide")
            db.session.add(ent)
            db.session.commit()
            eid = ent.id
        try:
            _entite_active(auth_client, eid)
            resp = _analyser(auth_client, _excel([("D", "Act", "G", "T", "", "", "", "")]))
            assert resp.status_code == 400
        finally:
            with app.app_context():
                db.session.delete(db.session.get(Entity, eid))
                db.session.commit()

    def test_fichier_sans_ligne_utile_donne_400(self, auth_client, ids):
        _entite_active(auth_client, ids["entity_id"])
        resp = _analyser(auth_client, _excel([]))
        assert resp.status_code == 400
        assert resp.get_json()["error"]

    def test_fichier_illisible_donne_400(self, auth_client, ids):
        _entite_active(auth_client, ids["entity_id"])
        resp = _analyser(auth_client, b"ceci n'est pas un classeur")
        assert resp.status_code == 400


class TestParseExcelCellules:
    def test_ligne_plus_courte_que_les_entetes_donne_valeur_vide(self):
        from Code.routes.import_full import _parse_excel_bytes
        contenu = _excel([("Dept", "Activité A", "Chef", "Tâche 1")])
        groupes = _parse_excel_bytes(contenu)
        assert [g["activity_name"] for g in groupes] == ["Activité A"]
        tache = groupes[0]["tasks"][0]
        assert tache["name"] == "Tâche 1"
        assert tache["tools"] == [] and tache["doer"] == "" and tache["skills"] == []

    def test_garant_vide_reprend_celui_de_la_ligne_precedente(self):
        from Code.routes.import_full import _parse_excel_bytes
        contenu = _excel([
            ("Dept", "Activité A", "Chef A", "Tâche 1", "", "", "", ""),
            ("Dept", "Activité B", "", "Tâche 2", "", "", "", ""),
        ])
        par_nom = {g["activity_name"]: g for g in _parse_excel_bytes(contenu)}
        assert par_nom["Activité A"]["guarantor"] == "Chef A"
        assert par_nom["Activité B"]["guarantor"] == "Chef A"


class TestInjectionRefus:
    CORPS = {"groups": [{"activity_id": 1, "tasks": []}]}

    def test_droit_d_ecriture_refuse_donne_403(self, auth_client, ids, monkeypatch):
        import Code.carto_access
        _entite_active(auth_client, ids["entity_id"])
        monkeypatch.setattr(Code.carto_access, "can_edit", lambda entity, user=None: False)
        resp = auth_client.post("/api/import-full/inject", json=self.CORPS)
        assert resp.status_code == 403
        assert resp.get_json()["error"]

    def test_erreur_interne_donne_500_et_annule(self, auth_client, ids, monkeypatch):
        import Code.routes.import_full as imp
        _entite_active(auth_client, ids["entity_id"])

        def _boom(groupes, entity_id):
            raise RuntimeError("base indisponible")

        monkeypatch.setattr(imp, "injecter_groupes", _boom)
        resp = auth_client.post("/api/import-full/inject", json=self.CORPS)
        assert resp.status_code == 500
        assert "base indisponible" in resp.get_json()["error"]

    def test_groupe_sans_activity_id_est_ignore(self, auth_client, ids):
        _entite_active(auth_client, ids["entity_id"])
        resp = auth_client.post("/api/import-full/inject",
                                json={"groups": [{"tasks": [{"name": "Fantôme"}]}]})
        assert resp.status_code == 201
        assert resp.get_json()["stats"]["tasks_created"] == 0
