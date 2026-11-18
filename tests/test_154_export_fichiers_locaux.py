# tests/test_154_export_fichiers_locaux.py
"""
Page : Export & fichiers joints — service des fichiers locaux, export HTML garni.

`/utils/serve-file?path=…` servait, SANS connexion, n'importe quel fichier
lisible par le processus (`/etc/passwd` répondait 200 ; sur Cloud Run,
`/proc/self/environ` aurait livré les secrets). Ces tests fixent la règle :
un fichier local n'est servi qu'à une session ouverte, hors Cloud Run, s'il est
un fichier ordinaire et s'il est exactement le chemin joint à une tâche, un
outil ou une contrainte.

Ils couvrent aussi l'export HTML d'une entité garnie (sections savoirs /
savoir-faire / HSC / compétences, carte du rôle avec ou sans mission), que
`test_21_export.py` n'exerçait que sur des listes vides.

Données dédiées, supprimées après chaque test (base partagée, scope=session).
"""
import uuid

import pytest

from Code.extensions import db
from Code.models.models import (Activities, Aptitude, Competency, Constraint,
                                Entity, Role, Savoir, SavoirFaire, Task, Tool,
                                activity_roles)

pytestmark = pytest.mark.export


def _servir(client, chemin):
    return client.get("/utils/serve-file", query_string={"path": chemin})


@pytest.fixture
def anonyme(app):
    return app.test_client()


@pytest.fixture
def fichier(tmp_path):
    f = tmp_path / f"piece_{uuid.uuid4().hex[:6]}.txt"
    f.write_text("contenu joint 154", encoding="utf-8")
    return str(f)


@pytest.fixture
def joindre(app, ids):
    """Joint un chemin à un objet (outil, tâche ou contrainte), retiré ensuite."""
    crees = []

    def _joindre(chemin, sorte="outil"):
        with app.app_context():
            if sorte == "outil":
                o = Tool(entity_id=ids["entity_id"], name="Outil 154 " + uuid.uuid4().hex[:6],
                         file_path=chemin)
            elif sorte == "tache":
                o = Task(name="Tâche 154", activity_id=ids["activity_id"], order=99,
                         file_path=chemin)
            else:
                o = Constraint(description="Contrainte 154", activity_id=ids["activity_id"],
                               file_path=chemin)
            db.session.add(o)
            db.session.commit()
            crees.append((type(o), o.id))

    yield _joindre
    with app.app_context():
        for model, oid in crees:
            o = db.session.get(model, oid)
            if o:
                db.session.delete(o)
        db.session.commit()


class TestServeFileLocal:

    def test_fichier_systeme_refuse_sans_connexion(self, anonyme):
        r = _servir(anonyme, "/etc/passwd")
        assert r.status_code == 404
        assert b"root:" not in r.data

    def test_fichier_systeme_refuse_meme_connecte(self, auth_client):
        r = _servir(auth_client, "/etc/passwd")
        assert r.status_code == 404
        assert b"root:" not in r.data

    def test_fichier_non_joint_refuse_meme_connecte(self, auth_client, fichier):
        assert _servir(auth_client, fichier).status_code == 404

    def test_fichier_joint_a_un_outil_est_servi(self, auth_client, fichier, joindre):
        joindre(fichier, "outil")
        r = _servir(auth_client, fichier)
        assert r.status_code == 200
        assert r.data == b"contenu joint 154"
        assert r.mimetype == "text/plain"

    def test_fichier_joint_a_une_tache_est_servi(self, auth_client, fichier, joindre):
        joindre(fichier, "tache")
        assert _servir(auth_client, fichier).status_code == 200

    def test_fichier_joint_a_une_contrainte_est_servi(self, auth_client, fichier, joindre):
        joindre(fichier, "contrainte")
        assert _servir(auth_client, fichier).status_code == 200

    def test_fichier_joint_refuse_sans_connexion(self, anonyme, fichier, joindre):
        joindre(fichier, "outil")
        assert _servir(anonyme, fichier).status_code == 404

    def test_fichier_joint_refuse_sur_cloud_run(self, auth_client, fichier, joindre, monkeypatch):
        joindre(fichier, "outil")
        monkeypatch.setenv("K_SERVICE", "devoptiq")
        assert _servir(auth_client, fichier).status_code == 404

    def test_pseudo_fichier_proc_refuse_meme_joint(self, auth_client, joindre):
        joindre("/proc/self/environ", "outil")
        r = _servir(auth_client, "/proc/self/environ")
        assert r.status_code == 404

    def test_dossier_joint_refuse(self, auth_client, tmp_path, joindre):
        joindre(str(tmp_path), "outil")
        assert _servir(auth_client, str(tmp_path)).status_code == 404

    def test_lien_symbolique_vers_proc_refuse(self, auth_client, tmp_path, joindre):
        lien = tmp_path / "env.txt"
        lien.symlink_to("/proc/self/environ")
        joindre(str(lien), "outil")
        assert _servir(auth_client, str(lien)).status_code == 404


# ---------------------------------------------------------------------------
# Export HTML d'une entité garnie
# ---------------------------------------------------------------------------

@pytest.fixture
def entite_garnie(app):
    with app.app_context():
        m = uuid.uuid4().hex[:6]
        ent = Entity(name=f"Entité export 154 {m}")
        db.session.add(ent)
        db.session.flush()
        act = Activities(entity_id=ent.id, name="Activité <export>")
        role = Role(name=f"Rôle export 154 {m}")
        role_sans = Role(name=f"Rôle sans mission 154 {m}")
        db.session.add_all([act, role, role_sans])
        db.session.flush()
        db.session.add_all([
            Savoir(description="Savoir & règle", activity_id=act.id),
            SavoirFaire(description="Savoir-faire 154", activity_id=act.id),
            Aptitude(description="Aptitude 154", activity_id=act.id),
            Competency(description="Compétence 154", activity_id=act.id),
        ])
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant"))
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role_sans.id, status="Garant"))
        role.mission_generale = "Mission <principale>"
        db.session.commit()
        ids = {"entity": ent.id, "act": act.id, "role": role.id, "role_sans": role_sans.id}
    yield ids
    with app.app_context():
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.activity_id == ids["act"]))
        act = db.session.get(Activities, ids["act"])
        if act:
            db.session.delete(act)
        for rid in (ids["role"], ids["role_sans"]):
            r = db.session.get(Role, rid)
            if r:
                db.session.delete(r)
        db.session.flush()
        db.session.delete(db.session.get(Entity, ids["entity"]))
        db.session.commit()


def _export_html(client, **params):
    r = client.get("/export/entity", query_string={"format": "html", **params})
    assert r.status_code == 200
    return r.get_data(as_text=True)


class TestExportHtmlGarni:

    def test_les_quatre_sections_listent_leurs_elements(self, auth_client, entite_garnie):
        html = _export_html(auth_client, entity_id=entite_garnie["entity"])
        for texte in ("Savoir &amp; règle", "Savoir-faire 154", "Aptitude 154", "Compétence 154"):
            assert texte in html

    def test_nom_d_activite_echappe_dans_les_tableaux(self, auth_client, entite_garnie):
        html = _export_html(auth_client, entity_id=entite_garnie["entity"])
        assert "Activité &lt;export&gt;" in html
        assert "Activité <export>" not in html

    def test_carte_du_role_affiche_la_mission_echappee(self, auth_client, entite_garnie):
        html = _export_html(auth_client, entity_id=entite_garnie["entity"],
                            role_id=entite_garnie["role"])
        assert "Mission &lt;principale&gt;" in html
        assert "Rôle exporté" in html

    def test_role_sans_mission_affiche_non_renseignee(self, auth_client, entite_garnie):
        html = _export_html(auth_client, entity_id=entite_garnie["entity"],
                            role_id=entite_garnie["role_sans"])
        assert "<em>Non renseignée</em>" in html

    def test_nom_de_fichier_porte_le_role(self, auth_client, entite_garnie, app):
        with app.app_context():
            nom = db.session.get(Role, entite_garnie["role"]).name.replace(" ", "_")
        r = auth_client.get("/export/entity", query_string={
            "format": "html", "entity_id": entite_garnie["entity"],
            "role_id": entite_garnie["role"]})
        assert nom in r.headers["Content-Disposition"]
