# tests/test_103_upload_vsdx_connexions.py
"""
Couvre la branche VSDX de POST /activities/upload-cartography
(activities_map.py) : import des connexions, dédoublonnage, création de Data,
clear_connections, keep_vsdx, erreur interne.
Isolation : entité jetable, dossier d'entités redirigé vers tmp_path,
parseur VSDX simulé.
"""
import io

import pytest

pytestmark = pytest.mark.activities_map


def _conn(src, tgt, dname=None, dtype=None):
    return {"source_name": src, "target_name": tgt,
            "data_name": dname, "data_type": dtype}


@pytest.fixture
def carto(app, ids, tmp_path, monkeypatch):
    from Code.extensions import db
    from Code.models.models import Entity, Activities, Link, Data
    import Code.routes.activities_map as am

    monkeypatch.setattr(am, "ENTITIES_DIR", str(tmp_path))
    with app.app_context():
        e = Entity(name="Entité VSDX 103", description="", owner_id=ids["user_id"])
        db.session.add(e)
        db.session.commit()
        eid = e.id
        a = Activities(entity_id=eid, name="Alpha103", description="")
        b = Activities(entity_id=eid, name="Beta103", description="")
        db.session.add_all([a, b])
        db.session.commit()
        aid, bid = a.id, b.id
    yield {"eid": eid, "aid": aid, "bid": bid, "am": am, "tmp": tmp_path}
    with app.app_context():
        Link.query.filter_by(entity_id=eid).delete()
        Data.query.filter_by(entity_id=eid).delete()
        Activities.query.filter_by(entity_id=eid).delete()
        ent = db.session.get(Entity, eid)
        if ent:
            db.session.delete(ent)
        db.session.commit()


def _post(client, eid, **extra):
    data = {"entity_id": eid, "mode": "update",
            "vsdx_file": (io.BytesIO(b"x"), "flux.vsdx")}
    data.update(extra)
    return client.post("/activities/upload-cartography", data=data,
                       content_type="multipart/form-data")


def _links(app, eid):
    from Code.models.models import Link
    with app.app_context():
        return [(l.source_activity_id, l.target_activity_id, l.type,
                 l.description, l.source_data_id)
                for l in Link.query.filter_by(entity_id=eid).all()]


class TestUploadVsdxConnexions:

    def test_importe_connexion_valide_et_cree_data(self, auth_client, app, carto, monkeypatch):
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections",
                            lambda p: ([_conn("Alpha103", "Beta103", "Commande", "déclenchante")], []))
        r = _post(auth_client, carto["eid"])
        assert r.status_code == 200
        stats = r.get_json()["stats"]
        assert stats["connections"] == 1
        assert stats["vsdx_updated"] is True
        assert stats["invalid_connections"] == 0
        links = _links(app, carto["eid"])
        assert len(links) == 1
        src, tgt, typ, desc, data_id = links[0]
        assert (src, tgt, desc) == (carto["aid"], carto["bid"], "Commande")
        assert typ == "déclenchante"
        assert data_id is not None

    def test_nom_original_du_vsdx_enregistre(self, auth_client, app, carto, monkeypatch):
        from Code.models.models import Entity
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections", lambda p: ([], []))
        r = _post(auth_client, carto["eid"])
        assert r.status_code == 200
        with app.app_context():
            assert Entity.query.get(carto["eid"]).vsdx_filename == "flux.vsdx"

    def test_connexion_sans_nom_de_donnee_n_a_pas_de_data(self, auth_client, app, carto, monkeypatch):
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections",
                            lambda p: ([_conn("Alpha103", "Beta103")], []))
        r = _post(auth_client, carto["eid"])
        assert r.status_code == 200
        (src, tgt, typ, desc, data_id), = _links(app, carto["eid"])
        assert typ == "nourrissante"
        assert desc is None and data_id is None

    def test_connexion_deja_existante_non_dupliquee(self, auth_client, app, carto, monkeypatch):
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections",
                            lambda p: ([_conn("Alpha103", "Beta103")], []))
        assert _post(auth_client, carto["eid"]).status_code == 200
        r = _post(auth_client, carto["eid"])
        assert r.get_json()["stats"]["connections"] == 1  # recomptage final
        assert len(_links(app, carto["eid"])) == 1

    def test_data_existante_reutilisee(self, auth_client, app, carto, monkeypatch):
        from Code.models.models import Data
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections",
                            lambda p: ([_conn("Alpha103", "Beta103", "Flux")], []))
        _post(auth_client, carto["eid"])
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections",
                            lambda p: ([_conn("Beta103", "Alpha103", "Flux")], []))
        _post(auth_client, carto["eid"])
        with app.app_context():
            assert Data.query.filter_by(entity_id=carto["eid"], name="Flux").count() == 1

    def test_activites_inconnues_comptees_invalides(self, auth_client, carto, monkeypatch):
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections",
                            lambda p: ([_conn("Alpha103", "Fantome103")], []))
        r = _post(auth_client, carto["eid"])
        stats = r.get_json()["stats"]
        assert stats["invalid_connections"] == 1
        assert stats["missing_activities"] == ["Fantome103"]
        assert stats["connections"] == 0

    def test_clear_connections_supprime_les_anciens_liens(self, auth_client, app, carto, monkeypatch):
        from Code.extensions import db
        from Code.models.models import Link
        with app.app_context():
            db.session.add(Link(entity_id=carto["eid"], source_activity_id=carto["bid"],
                                target_activity_id=carto["aid"], type="nourrissante"))
            db.session.commit()
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections",
                            lambda p: ([_conn("Alpha103", "Beta103")], []))
        _post(auth_client, carto["eid"], clear_connections="true")
        links = _links(app, carto["eid"])
        assert [(l[0], l[1]) for l in links] == [(carto["aid"], carto["bid"])]

    def test_sans_clear_les_anciens_liens_sont_conserves(self, auth_client, app, carto, monkeypatch):
        from Code.extensions import db
        from Code.models.models import Link
        with app.app_context():
            db.session.add(Link(entity_id=carto["eid"], source_activity_id=carto["bid"],
                                target_activity_id=carto["aid"], type="nourrissante"))
            db.session.commit()
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections",
                            lambda p: ([_conn("Alpha103", "Beta103")], []))
        _post(auth_client, carto["eid"])
        assert len(_links(app, carto["eid"])) == 2

    def test_keep_vsdx_avec_fichier_present(self, auth_client, carto):
        import os
        d = carto["tmp"] / f"entity_{carto['eid']}"
        d.mkdir()
        (d / "connections.vsdx").write_bytes(b"x")
        r = auth_client.post("/activities/upload-cartography",
                             data={"entity_id": carto["eid"], "mode": "update",
                                   "keep_vsdx": "true"},
                             content_type="multipart/form-data")
        assert r.status_code == 200
        assert r.get_json()["stats"]["vsdx_kept"] is True

    def test_keep_vsdx_sans_fichier_n_est_pas_marque_conserve(self, auth_client, carto):
        r = auth_client.post("/activities/upload-cartography",
                             data={"entity_id": carto["eid"], "mode": "update",
                                   "keep_vsdx": "true"},
                             content_type="multipart/form-data")
        assert r.status_code == 200
        assert r.get_json()["stats"]["vsdx_kept"] is False

    def test_erreur_du_parseur_renvoie_500(self, auth_client, carto, monkeypatch):
        def boom(p):
            raise RuntimeError("parseur cassé")
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections", boom)
        r = _post(auth_client, carto["eid"])
        assert r.status_code == 500
        assert "parseur cassé" in r.get_json()["error"]

    def test_entite_d_un_autre_utilisateur_refusee(self, auth_client, app, carto, monkeypatch):
        from Code.extensions import db
        from Code.models.models import Entity
        with app.app_context():
            e = db.session.get(Entity, carto["eid"])
            e.owner_id = 987654
            db.session.commit()
        monkeypatch.setattr(carto["am"], "parse_vsdx_connections", lambda p: ([], []))
        assert _post(auth_client, carto["eid"]).status_code == 404
