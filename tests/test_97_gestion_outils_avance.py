# tests/test_97_gestion_outils_avance.py
"""
Gestion des outils (/gestion_outils) — cas non couverts par test_11 :
chemin de fichier, usages dans la liste, remplacement ciblé / sans doublon,
détachement partiel, isolation par entité, ordre des usages.
Chaque test crée ses propres outils/tâches et les nettoie.
"""
import json
import pytest

pytestmark = pytest.mark.tools

BASE = "/gestion_outils/api/tools"


def _mk_tool(app, ids, name, entity_id="__default__"):
    from Code.models.models import Tool
    from Code.extensions import db
    with app.app_context():
        t = Tool(name=name, entity_id=ids["entity_id"] if entity_id == "__default__" else entity_id)
        db.session.add(t)
        db.session.commit()
        return t.id


def _mk_task(app, ids, name):
    from Code.models.models import Task
    from Code.extensions import db
    with app.app_context():
        t = Task(name=name, activity_id=ids["activity_id"])
        db.session.add(t)
        db.session.commit()
        return t.id


def _link(app, task_id, tool_id):
    from Code.models.models import task_tools
    from Code.extensions import db
    with app.app_context():
        db.session.execute(task_tools.insert(), [{"task_id": task_id, "tool_id": tool_id}])
        db.session.commit()


def _tools_of(app, tool_id):
    from Code.models.models import task_tools
    from Code.extensions import db
    with app.app_context():
        return {r[0] for r in db.session.query(task_tools.c.task_id)
                .filter(task_tools.c.tool_id == tool_id).all()}


def _cleanup(app, tool_ids=(), task_ids=()):
    from Code.models.models import Tool, Task, task_tools
    from Code.extensions import db
    with app.app_context():
        for tid in tool_ids:
            db.session.execute(task_tools.delete().where(task_tools.c.tool_id == tid))
        for tid in task_ids:
            db.session.execute(task_tools.delete().where(task_tools.c.task_id == tid))
        for tid in tool_ids:
            t = db.session.get(Tool, tid)
            if t:
                db.session.delete(t)
        for tid in task_ids:
            t = db.session.get(Task, tid)
            if t:
                db.session.delete(t)
        db.session.commit()


def _json(auth_client, method, url, body=None):
    return getattr(auth_client, method)(
        url, data=json.dumps(body if body is not None else {}), content_type="application/json")


class TestFilePath:

    def test_create_stocke_et_nettoie_le_chemin(self, auth_client, app):
        r = _json(auth_client, "post", BASE, {"name": "Outil Chemin 97", "file_path": "  /docs/notice.pdf  "})
        assert r.status_code == 201
        tid = r.get_json()["id"]
        try:
            rows = {t["id"]: t for t in auth_client.get(BASE).get_json()}
            assert rows[tid]["file_path"] == "/docs/notice.pdf"
        finally:
            _cleanup(app, [tid])

    def test_create_sans_chemin_renvoie_chaine_vide_dans_la_liste(self, auth_client, app):
        tid = _json(auth_client, "post", BASE, {"name": "Outil Sans Chemin 97"}).get_json()["id"]
        try:
            rows = {t["id"]: t for t in auth_client.get(BASE).get_json()}
            assert rows[tid]["file_path"] == ""
            assert rows[tid]["description"] == ""
        finally:
            _cleanup(app, [tid])

    def test_update_chemin_puis_effacement(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil MajChemin 97")
        try:
            r = _json(auth_client, "put", f"{BASE}/{tid}", {"file_path": " a/b.docx "})
            assert r.status_code == 200
            assert r.get_json()["file_path"] == "a/b.docx"
            r = _json(auth_client, "put", f"{BASE}/{tid}", {"file_path": "   "})
            assert r.get_json()["file_path"] is None
        finally:
            _cleanup(app, [tid])

    def test_update_sans_champ_ne_change_rien(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil Intact 97")
        try:
            _json(auth_client, "put", f"{BASE}/{tid}", {"description": "desc"})
            r = _json(auth_client, "put", f"{BASE}/{tid}", {})
            assert r.status_code == 200
            rows = {t["id"]: t for t in auth_client.get(BASE).get_json()}
            assert rows[tid]["name"] == "Outil Intact 97"
            assert rows[tid]["description"] == "desc"
        finally:
            _cleanup(app, [tid])

    def test_update_description_blanche_efface(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil DescVide 97")
        try:
            _json(auth_client, "put", f"{BASE}/{tid}", {"description": "x"})
            _json(auth_client, "put", f"{BASE}/{tid}", {"description": "  "})
            rows = {t["id"]: t for t in auth_client.get(BASE).get_json()}
            assert rows[tid]["description"] == ""
        finally:
            _cleanup(app, [tid])

    def test_update_garde_son_propre_nom_en_changeant_la_casse(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "outil casse 97")
        try:
            r = _json(auth_client, "put", f"{BASE}/{tid}", {"name": "OUTIL CASSE 97"})
            assert r.status_code == 200
        finally:
            _cleanup(app, [tid])


class TestListeEtUsages:

    def test_liste_contient_les_usages_avec_activite(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil Usage Liste 97")
        task = _mk_task(app, ids, "Tâche Liste 97")
        _link(app, task, tid)
        try:
            rows = {t["id"]: t for t in auth_client.get(BASE).get_json()}
            usages = rows[tid]["usages"]
            assert len(usages) == 1
            assert usages[0]["task_id"] == task
            assert usages[0]["task_name"] == "Tâche Liste 97"
            assert usages[0]["activity_id"] == ids["activity_id"]
            assert usages[0]["activity_name"]
        finally:
            _cleanup(app, [tid], [task])

    def test_liste_triee_sans_tenir_compte_de_la_casse(self, auth_client, app, ids):
        a = _mk_tool(app, ids, "zz97 beta")
        b = _mk_tool(app, ids, "ZZ97 Alpha")
        try:
            noms = [t["name"] for t in auth_client.get(BASE).get_json() if t["name"].lower().startswith("zz97")]
            assert noms == ["ZZ97 Alpha", "zz97 beta"]
        finally:
            _cleanup(app, [a, b])

    def test_usages_tries_par_nom_de_tache(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil Tri Usages 97")
        t2 = _mk_task(app, ids, "b-tache 97")
        t1 = _mk_task(app, ids, "A-tache 97")
        _link(app, t2, tid)
        _link(app, t1, tid)
        try:
            data = auth_client.get(f"{BASE}/{tid}/usages").get_json()
            assert data["tool"] == {"id": tid, "name": "Outil Tri Usages 97"}
            assert [u["task_name"] for u in data["usages"]] == ["A-tache 97", "b-tache 97"]
        finally:
            _cleanup(app, [tid], [t1, t2])

    def test_liste_exclut_les_outils_d_une_autre_entite(self, auth_client, app, ids):
        from Code.models.models import Entity
        from Code.extensions import db
        with app.app_context():
            e = Entity(name="Entité Outils Autre 97", description="")
            db.session.add(e)
            db.session.commit()
            other = e.id
        tid = _mk_tool(app, ids, "Outil Autre Entité 97", entity_id=other)
        try:
            noms = [t["name"] for t in auth_client.get(BASE).get_json()]
            assert "Outil Autre Entité 97" not in noms
        finally:
            _cleanup(app, [tid])
            with app.app_context():
                e = db.session.get(Entity, other)
                if e:
                    db.session.delete(e)
                    db.session.commit()

    def test_meme_nom_autorise_dans_une_autre_entite(self, auth_client, app, ids):
        from Code.models.models import Entity
        from Code.extensions import db
        with app.app_context():
            e = Entity(name="Entité Outils Doublon 97", description="")
            db.session.add(e)
            db.session.commit()
            other = e.id
        tid = _mk_tool(app, ids, "Outil Doublon Inter 97", entity_id=other)
        r = _json(auth_client, "post", BASE, {"name": "Outil Doublon Inter 97"})
        try:
            assert r.status_code == 201
        finally:
            _cleanup(app, [tid, r.get_json().get("id")] if r.status_code == 201 else [tid])
            with app.app_context():
                e = db.session.get(Entity, other)
                if e:
                    db.session.delete(e)
                    db.session.commit()


class TestRemplacementAvance:

    def test_remplacement_filtre_par_task_ids(self, auth_client, app, ids):
        src = _mk_tool(app, ids, "Src Filtre 97")
        dst = _mk_tool(app, ids, "Dst Filtre 97")
        t1 = _mk_task(app, ids, "T1 filtre 97")
        t2 = _mk_task(app, ids, "T2 filtre 97")
        _link(app, t1, src)
        _link(app, t2, src)
        try:
            r = _json(auth_client, "post", f"{BASE}/{src}/replace",
                      {"replacement_id": dst, "task_ids": [t1]})
            assert r.status_code == 200
            assert r.get_json()["replaced_count"] == 1
            assert _tools_of(app, dst) == {t1}
            assert _tools_of(app, src) == {t2}
        finally:
            _cleanup(app, [src, dst], [t1, t2])

    def test_remplacement_ne_cree_pas_de_doublon(self, auth_client, app, ids):
        src = _mk_tool(app, ids, "Src Doublon 97")
        dst = _mk_tool(app, ids, "Dst Doublon 97")
        t1 = _mk_task(app, ids, "T1 doublon 97")
        _link(app, t1, src)
        _link(app, t1, dst)
        try:
            r = _json(auth_client, "post", f"{BASE}/{src}/replace", {"replacement_id": dst})
            assert r.status_code == 200
            assert _tools_of(app, dst) == {t1}
            assert _tools_of(app, src) == set()
        finally:
            _cleanup(app, [src, dst], [t1])

    def test_remplacement_sans_usage_compte_zero(self, auth_client, app, ids):
        src = _mk_tool(app, ids, "Src Vide 97")
        dst = _mk_tool(app, ids, "Dst Vide 97")
        try:
            r = _json(auth_client, "post", f"{BASE}/{src}/replace", {"replacement_id": dst})
            assert r.status_code == 200
            assert r.get_json()["replaced_count"] == 0
        finally:
            _cleanup(app, [src, dst])

    def test_remplacement_task_ids_hors_usages_ignore(self, auth_client, app, ids):
        src = _mk_tool(app, ids, "Src Hors 97")
        dst = _mk_tool(app, ids, "Dst Hors 97")
        t1 = _mk_task(app, ids, "T1 hors 97")
        _link(app, t1, src)
        try:
            r = _json(auth_client, "post", f"{BASE}/{src}/replace",
                      {"replacement_id": dst, "task_ids": [999999]})
            assert r.get_json()["replaced_count"] == 0
            assert _tools_of(app, src) == {t1}
        finally:
            _cleanup(app, [src, dst], [t1])


class TestSuppressionAvancee:

    def test_detachement_partiel_laisse_l_outil_si_usages_restants(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil Partiel Reste 97")
        t1 = _mk_task(app, ids, "T1 reste 97")
        t2 = _mk_task(app, ids, "T2 reste 97")
        _link(app, t1, tid)
        _link(app, t2, tid)
        try:
            r = _json(auth_client, "delete", f"{BASE}/{tid}", {"task_ids": [t1]})
            assert r.status_code == 200
            body = r.get_json()
            assert body["deleted"] is False
            assert body["remaining"] == 1
            assert _tools_of(app, tid) == {t2}
        finally:
            _cleanup(app, [tid], [t1, t2])

    def test_detachement_partiel_total_supprime_l_outil(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil Partiel Total 97")
        t1 = _mk_task(app, ids, "T1 total 97")
        _link(app, t1, tid)
        try:
            r = _json(auth_client, "delete", f"{BASE}/{tid}", {"task_ids": [t1]})
            assert r.get_json()["deleted"] is True
            noms = [t["name"] for t in auth_client.get(BASE).get_json()]
            assert "Outil Partiel Total 97" not in noms
        finally:
            _cleanup(app, [tid], [t1])

    def test_conflit_409_indique_le_nombre_d_usages(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil Conflit 97")
        t1 = _mk_task(app, ids, "T1 conflit 97")
        t2 = _mk_task(app, ids, "T2 conflit 97")
        _link(app, t1, tid)
        _link(app, t2, tid)
        try:
            r = auth_client.delete(f"{BASE}/{tid}")
            assert r.status_code == 409
            assert r.get_json()["usages_count"] == 2
        finally:
            _cleanup(app, [tid], [t1, t2])

    def test_force_detach_false_explicite_refuse(self, auth_client, app, ids):
        tid = _mk_tool(app, ids, "Outil Force Faux 97")
        t1 = _mk_task(app, ids, "T1 force 97")
        _link(app, t1, tid)
        try:
            assert auth_client.delete(f"{BASE}/{tid}?force_detach=false").status_code == 409
            assert auth_client.delete(f"{BASE}/{tid}?force_detach=TRUE").status_code == 200
        finally:
            _cleanup(app, [tid], [t1])

    def test_suppression_force_garde_les_taches(self, auth_client, app, ids):
        from Code.models.models import Task
        from Code.extensions import db
        tid = _mk_tool(app, ids, "Outil Force Taches 97")
        t1 = _mk_task(app, ids, "T1 garde 97")
        _link(app, t1, tid)
        try:
            assert auth_client.delete(f"{BASE}/{tid}?force_detach=true").status_code == 200
            with app.app_context():
                assert db.session.get(Task, t1) is not None
        finally:
            _cleanup(app, [tid], [t1])
