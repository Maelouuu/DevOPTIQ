# tests/test_62_task_tool_files.py
# Deux pièces jointes DISTINCTES : celle de la TÂCHE (mode opératoire) et celle
# de l'OUTIL (notice). Avant, seul l'outil pouvait en porter une, et uniquement
# au moment de sa création : un outil déjà enregistré ne pouvait plus recevoir
# de fichier, et le dépôt du panneau « + outil » laissait croire qu'il valait
# pour la tâche.
import pytest
from Code.extensions import db
from Code.models.models import Entity, Activities, Task, Tool


@pytest.fixture()
def bureau(app):
    """Entité dédiée : une activité, une tâche, un outil sans fichier."""
    with app.app_context():
        # get_active est STRICT sur owner_id : sans propriétaire, /tools/all ne
        # verrait aucun outil (l'entité ne serait "active" pour personne).
        ent = Entity(name="PiecesJointesEnt", owner_id=1)
        db.session.add(ent); db.session.flush()
        act = Activities(entity_id=ent.id, name="Préparer la commande", shape_id="pj_s1")
        db.session.add(act); db.session.flush()
        tache = Task(name="Éditer le bon", activity_id=act.id, order=1)
        outil = Tool(name="ERP Commandes", entity_id=ent.id)
        db.session.add_all([tache, outil]); db.session.commit()
        ids = {"entity_id": ent.id, "activity_id": act.id,
               "task_id": tache.id, "tool_id": outil.id}
    yield ids
    with app.app_context():
        t = Task.query.get(ids["task_id"])
        if t:
            t.tools = []
            db.session.delete(t)
        Task.query.filter_by(activity_id=ids["activity_id"]).delete()
        Tool.query.filter_by(entity_id=ids["entity_id"]).delete()
        Activities.query.filter_by(id=ids["activity_id"]).delete()
        Entity.query.filter_by(id=ids["entity_id"]).delete()
        db.session.commit()


def _sess(client, ids):
    with client.session_transaction() as s:
        s["active_entity_id"] = ids["entity_id"]
        s["user_id"] = 1
        s["lang"] = "fr"


# ── Pièce jointe de la tâche ──────────────────────────────────────────────

def test_task_created_with_file(client, bureau, app):
    _sess(client, bureau)
    r = client.post('/tasks/add', json={
        "activity_id": bureau["activity_id"], "name": "Vérifier le stock",
        "file_path": "uploads/mode_operatoire.pdf"})
    assert r.status_code == 201
    assert r.get_json()["file_path"] == "uploads/mode_operatoire.pdf"
    with app.app_context():
        t = Task.query.filter_by(activity_id=bureau["activity_id"],
                                 name="Vérifier le stock").first()
        assert t.file_path == "uploads/mode_operatoire.pdf"


def test_task_file_added_afterwards(client, bureau, app):
    _sess(client, bureau)
    r = client.put(f'/tasks/{bureau["task_id"]}',
                   json={"file_path": "uploads/procedure.docx"})
    assert r.status_code == 200
    assert r.get_json()["file_path"] == "uploads/procedure.docx"
    with app.app_context():
        assert Task.query.get(bureau["task_id"]).file_path == "uploads/procedure.docx"


def test_task_file_cleared_by_empty_string(client, bureau, app):
    _sess(client, bureau)
    client.put(f'/tasks/{bureau["task_id"]}', json={"file_path": "uploads/x.pdf"})
    client.put(f'/tasks/{bureau["task_id"]}', json={"file_path": ""})
    with app.app_context():
        assert Task.query.get(bureau["task_id"]).file_path is None


def test_task_rename_keeps_its_file(client, bureau, app):
    """Renommer une tâche ne doit pas décrocher sa pièce jointe."""
    _sess(client, bureau)
    client.put(f'/tasks/{bureau["task_id"]}', json={"file_path": "uploads/a.pdf"})
    client.put(f'/tasks/{bureau["task_id"]}', json={"name": "Éditer le bon (v2)"})
    with app.app_context():
        t = Task.query.get(bureau["task_id"])
        assert t.name == "Éditer le bon (v2)"
        assert t.file_path == "uploads/a.pdf"


# ── Pièce jointe de l'outil, ajoutée APRÈS sa création ───────────────────

def test_tool_file_added_after_creation(client, bureau, app):
    _sess(client, bureau)
    r = client.put(f'/gestion_outils/api/tools/{bureau["tool_id"]}',
                   json={"file_path": "uploads/notice_erp.pdf"})
    assert r.status_code == 200
    assert r.get_json()["file_path"] == "uploads/notice_erp.pdf"
    with app.app_context():
        assert Tool.query.get(bureau["tool_id"]).file_path == "uploads/notice_erp.pdf"


def test_tool_sheet_can_edit_name_and_description(client, bureau, app):
    _sess(client, bureau)
    r = client.put(f'/gestion_outils/api/tools/{bureau["tool_id"]}',
                   json={"name": "ERP Commandes v2", "description": "Poste achats",
                         "file_path": "uploads/notice.pdf"})
    assert r.status_code == 200
    with app.app_context():
        o = Tool.query.get(bureau["tool_id"])
        assert (o.name, o.description, o.file_path) == (
            "ERP Commandes v2", "Poste achats", "uploads/notice.pdf")


def test_tools_all_exposes_description_and_file(client, bureau, app):
    """La fiche outil se remplit depuis /tools/all : sans description, elle
    ouvrait un champ toujours vide."""
    _sess(client, bureau)
    client.put(f'/gestion_outils/api/tools/{bureau["tool_id"]}',
               json={"description": "Poste achats", "file_path": "uploads/n.pdf"})
    ligne = next(o for o in client.get('/tools/all').get_json()
                 if o["id"] == bureau["tool_id"])
    assert ligne["description"] == "Poste achats"
    assert ligne["file_path"] == "uploads/n.pdf"


def test_task_and_tool_files_are_independent(client, bureau, app):
    """Le fichier de la tâche et celui de l'outil ne se recouvrent jamais."""
    _sess(client, bureau)
    client.put(f'/tasks/{bureau["task_id"]}', json={"file_path": "uploads/tache.pdf"})
    client.put(f'/gestion_outils/api/tools/{bureau["tool_id"]}',
               json={"file_path": "uploads/outil.pdf"})
    with app.app_context():
        assert Task.query.get(bureau["task_id"]).file_path == "uploads/tache.pdf"
        assert Tool.query.get(bureau["tool_id"]).file_path == "uploads/outil.pdf"
    # retirer celui de l'outil laisse celui de la tâche
    client.put(f'/gestion_outils/api/tools/{bureau["tool_id"]}', json={"file_path": ""})
    with app.app_context():
        assert Task.query.get(bureau["task_id"]).file_path == "uploads/tache.pdf"
        assert Tool.query.get(bureau["tool_id"]).file_path is None
