# tests/test_126_rh_settings_gaps.py
"""
Page : Gestion RH — paramètres d'entreprise (`update_single_setting`,
`_parse_setting_value`, `_get_settings_row`).

Chaque test travaille sur une entité jetable rendue active par
`session_transaction`, puis la supprime : la base est partagée (scope=session).
"""
import pytest

import Code.routes.gestion_rh as _rh
from Code.extensions import db
from Code.models.models import Entity, EntrepriseSettings

pytestmark = pytest.mark.gestion_rh


@pytest.fixture
def entite_126(app, auth_client):
    with app.app_context():
        ent = Entity(name="Entité 126 settings")
        db.session.add(ent)
        db.session.commit()
        eid = ent.id
    with auth_client.session_transaction() as sess:
        ancienne = sess.get("active_entity_id")
        sess["active_entity_id"] = eid
    yield eid
    with auth_client.session_transaction() as sess:
        if ancienne is None:
            sess.pop("active_entity_id", None)
        else:
            sess["active_entity_id"] = ancienne
    with app.app_context():
        EntrepriseSettings.query.filter_by(entity_id=eid).delete()
        Entity.query.filter_by(id=eid).delete()
        db.session.commit()


class TestParseSettingValue:

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_vide_donne_none(self, raw):
        assert _rh._parse_setting_value(raw) is None

    def test_virgule_decimale_acceptee(self):
        assert _rh._parse_setting_value("7,5") == 7.5

    def test_texte_non_numerique_donne_none(self):
        assert _rh._parse_setting_value("abc") is None


class TestUpdateSingleSetting:

    def test_cle_inconnue_refusee(self, auth_client, entite_126):
        r = auth_client.post("/gestion_rh/update_single_setting",
                             data={"key": "nope", "value": "3"})
        assert r.status_code == 400
        assert r.get_json()["success"] is False

    def test_valeur_virgule_persistee(self, auth_client, entite_126):
        r = auth_client.post("/gestion_rh/update_single_setting",
                             data={"key": "work_hours_per_day", "value": "7,5"})
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert body["value"] == 7.5

    def test_valeur_vide_efface_le_parametre(self, auth_client, entite_126):
        auth_client.post("/gestion_rh/update_single_setting",
                         data={"key": "work_days_per_week", "value": "5"})
        r = auth_client.post("/gestion_rh/update_single_setting",
                             data={"key": "work_days_per_week", "value": ""})
        assert r.status_code == 200
        assert r.get_json()["value"] is None

    def test_deux_appels_reutilisent_la_meme_ligne(self, app, auth_client, entite_126):
        for v in ("5", "4"):
            auth_client.post("/gestion_rh/update_single_setting",
                             data={"key": "work_days_per_week", "value": v})
        with app.app_context():
            n = EntrepriseSettings.query.filter_by(entity_id=entite_126).count()
        assert n == 1


class TestGetSettingsRow:

    def test_absente_sans_create_renvoie_none(self, app, entite_126):
        with app.app_context():
            assert _rh._get_settings_row(entite_126) is None

    def test_create_ajoute_la_ligne_a_la_session(self, app, entite_126):
        with app.app_context():
            row = _rh._get_settings_row(entite_126, create=True)
            assert row.entity_id == entite_126
            db.session.rollback()

    def test_page_rh_affiche_sans_erreur_avec_parametres(self, auth_client, entite_126):
        auth_client.post("/gestion_rh/update_single_setting",
                         data={"key": "work_hours_per_day", "value": "8"})
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 200
