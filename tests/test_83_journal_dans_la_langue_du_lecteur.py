# -*- coding: utf-8 -*-
"""Le journal « Activité récente » se lit dans la langue de CELUI QUI LIT.

⚠️ Il était écrit dans la langue de la personne qui AGISSAIT : un anglophone
lisait « Rôle créé : Qualité » parce qu'un francophone avait créé le rôle, et
les champs d'un « avant → après » s'appelaient « Nom », « Mission ». Le libellé
est désormais rebâti à la lecture depuis le TYPE d'événement ; le libellé
stocké ne sert plus que de repli pour un type inconnu du catalogue.
"""
import json

import pytest

from Code.extensions import db


@pytest.fixture(autouse=True)
def _session_rendue(client):
    """Rend la session telle qu'on l'a trouvée : `client` est partagé par tous
    les fichiers, et une langue laissée à « en » changerait les messages que
    les fichiers suivants comparent."""
    with client.session_transaction() as s:
        avant = dict(s)
    yield
    with client.session_transaction() as s:
        s.clear()
        s.update(avant)


@pytest.fixture()
def evenements(app):
    from Code.models.models import RecentEvent
    ids = []
    with app.app_context():
        for ev in (
            RecentEvent(event_type="role_created", icon="fa-solid fa-user-tie",
                        label="Rôle créé : T83 Qualité",
                        detail=json.dumps({"name": "T83 Qualité"})),
            # ancien « modifié » : ni nom dans le détail, champ en français
            RecentEvent(event_type="role_updated", icon="fa-solid fa-pen",
                        label="Rôle modifié : T83 Logistique",
                        detail=json.dumps({"changes": [
                            {"field": "Nom", "before": "T83 Log", "after": "T83 Logistique"}]})),
            RecentEvent(event_type="t83_inconnu", icon="fa-solid fa-circle",
                        label="T83 libellé d'origine"),
        ):
            db.session.add(ev)
        db.session.commit()
        ids = [e.id for e in RecentEvent.query.filter(
            RecentEvent.label.like("%T83%")).all()]
    yield ids
    with app.app_context():
        RecentEvent.query.filter(RecentEvent.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()


def _lire(client, lang):
    with client.session_transaction() as s:
        s["lang"] = lang
    items = client.get("/api/recent-activity").get_json()["items"]
    return {i["type"]: i for i in items if "T83" in (i["label"] or "")
            or i["type"] == "t83_inconnu"}


class TestLeJournalSeLitDansLaLangueDuLecteur:

    def test_une_creation_ecrite_en_francais_se_lit_en_anglais(self, auth_client, evenements):
        """Vérifié ROUGE sur le code d'avant : « Rôle créé : T83 Qualité »."""
        en = _lire(auth_client, "en")
        assert en["role_created"]["label"] == "Role created: T83 Qualité"
        fr = _lire(auth_client, "fr")
        assert fr["role_created"]["label"] == "Rôle créé : T83 Qualité"

    def test_un_ancien_evenement_sans_nom_retrouve_le_sien_dans_son_libelle(
            self, auth_client, evenements):
        en = _lire(auth_client, "en")
        assert en["role_updated"]["label"] == "Role updated: T83 Logistique"

    def test_les_champs_d_un_avant_apres_se_traduisent(self, auth_client, evenements):
        en = _lire(auth_client, "en")
        assert en["role_updated"]["detail"]["changes"][0]["field"] == "Name"

    def test_un_type_inconnu_garde_son_libelle(self, auth_client, evenements):
        en = _lire(auth_client, "en")
        assert en["t83_inconnu"]["label"] == "T83 libellé d'origine"

    def test_une_modification_garde_desormais_le_nom_et_des_cles_de_champ(self, app):
        """À l'écriture : le nom de l'objet même dans « modifié », et des CLÉS
        de champ — plus de libellé français figé dans la base."""
        from Code.models.models import Entity, RecentEvent, Role
        with app.app_context():
            e = Entity(name="T83 Carto")
            db.session.add(e)
            db.session.flush()
            r = Role(name="T83 Avant", entity_id=e.id)
            db.session.add(r)
            db.session.commit()
            assert r.name == "T83 Avant"   # lu d'abord, comme dans une vraie route
            r.name = "T83 Après"
            db.session.commit()
            ev = (RecentEvent.query.filter_by(event_type="role_updated")
                  .order_by(RecentEvent.id.desc()).first())
            detail = json.loads(ev.detail)
            try:
                assert detail["name"] == "T83 Après"
                assert detail["changes"][0]["field"] == "name"
            finally:
                RecentEvent.query.filter(RecentEvent.label.like("%T83%")).delete(
                    synchronize_session=False)
                db.session.delete(r)
                db.session.delete(e)
                db.session.commit()


class TestLaPageDeConnexion:

    def test_le_titre_de_l_onglet_suit_la_langue(self, client):
        """Vérifié ROUGE sur le code d'avant : « OptiqFluent — Connexion »
        dans l'onglet, en anglais comme en français."""
        with client.session_transaction() as s:
            s.clear()
            s["lang"] = "en"
        html = client.get("/login").get_data(as_text=True)
        assert "<title>OptiqFluent — Sign in</title>" in html
