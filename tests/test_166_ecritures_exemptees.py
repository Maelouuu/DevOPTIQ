# -*- coding: utf-8 -*-
"""Les routes que la porte d'écriture LAISSE PASSER — appelées pour de vrai.

`Code/ecriture.py` exempte 25 préfixes (`TOUT_COMPTE`) parce qu'ils « portent
déjà leur propre garde, plus fine ». L'audit avant livraison (25/11/2026) l'a
écrit noir sur blanc : c'est dans cette moitié-là qu'étaient tous les trous
trouvés jusqu'ici, et personne ne l'avait balayée — il fallait APPELER chaque
route avec un compte `user` et regarder si la base bougeait.

C'est ce que fait ce fichier. Premier passage : **douze routes écrivaient pour
un compte `user`** — dix sous `/gestion_rh` (supprimer un rôle de n'importe
quelle carto, réécrire les paramètres de temps, réaffecter rôles et
développeur de compétences), deux sous `/comptes` (se rattacher qui on veut,
donc devenir le développeur de compétences d'un collègue).

Le balayage est un CLIQUET : il lit la table des routes, il ne la recopie pas.
Une route d'écriture ajoutée demain sous un préfixe exempté y entre d'office.
"""
import hashlib
import os
import re
import shutil

import pytest
from sqlalchemy import text

from Code.ecriture import METHODES_ECRITURE, SANS_COMPTE, TOUT_COMPTE
from Code.extensions import db

PREFIXE = "t166."
MDP = "Motdepasse123!"


# ── Décor ────────────────────────────────────────────────────────────────

@pytest.fixture()
def decor(app):
    """Une carto COMMUNE d'un administrateur, ouverte à tous ; un compte `user`
    qui la consulte ; une victime `user` qui y tient un rôle ; un champion et un
    coordinateur pour les cas qui doivent, eux, passer ou non."""
    from Code.models.models import (Activities, Data, Entity, EntrepriseSettings,
                                    Role, User, UserRole)
    from Code.security import hash_password

    with app.app_context():
        comptes = {}
        for cle, statut in (("adm", "admin"), ("usr", "user"), ("vic", "user"),
                            ("cha", "champion"), ("coo", "coordinateur")):
            u = User(first_name="T166", last_name=cle, email=PREFIXE + cle + "@x.com",
                     password=hash_password(MDP), status=statut)
            db.session.add(u)
            comptes[cle] = u
        db.session.flush()
        e = Entity(name="T166 commune", owner_id=comptes["adm"].id, is_shared=True)
        db.session.add(e)
        db.session.flush()
        for cle in ("usr", "vic", "cha", "coo"):
            comptes[cle].entity_id = e.id
        act = Activities(entity_id=e.id, name="T166 activité")
        role = Role(entity_id=e.id, name="T166 rôle")
        jetable = Role(entity_id=e.id, name="T166 rôle jetable")
        d = Data(entity_id=e.id, name="T166 donnée", type="sortante")
        db.session.add_all([act, role, jetable, d])
        db.session.flush()
        db.session.add(UserRole(user_id=comptes["vic"].id, role_id=role.id))
        db.session.add(EntrepriseSettings(entity_id=e.id, work_hours_per_day=7.0))
        db.session.commit()
        ids = {k: u.id for k, u in comptes.items()}
        ids.update(entity_id=e.id, role_id=role.id, jetable_id=jetable.id,
                   activity_id=act.id, data_id=d.id)

    yield ids

    with app.app_context():
        from Code.models.models import WelcomeSeen
        uids = [ids[k] for k in ("adm", "usr", "vic", "cha", "coo")]
        db.session.rollback()
        perso = [x.id for x in Entity.query.filter(Entity.owner_id.in_(uids)).all()]
        eids = set(perso) | {ids["entity_id"]}
        WelcomeSeen.query.filter(WelcomeSeen.user_id.in_(uids)).delete(synchronize_session=False)
        UserRole.query.filter(UserRole.user_id.in_(uids)).delete(synchronize_session=False)
        EntrepriseSettings.query.filter(EntrepriseSettings.entity_id.in_(eids)).delete(synchronize_session=False)
        Data.query.filter(Data.entity_id.in_(eids)).delete(synchronize_session=False)
        Role.query.filter(Role.entity_id.in_(eids)).delete(synchronize_session=False)
        Activities.query.filter(Activities.entity_id.in_(eids)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(uids)).update({"entity_id": None, "manager_id": None},
                                                    synchronize_session=False)
        Entity.query.filter(Entity.id.in_(eids)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(uids)).delete(synchronize_session=False)
        db.session.commit()
        from Code.routes.activities_map import get_entity_dir
        for eid in perso:
            shutil.rmtree(get_entity_dir(eid), ignore_errors=True)


def _client(app, uid, entity_id):
    """Un client À SOI — jamais le client partagé de la suite."""
    c = app.test_client()
    if uid is not None:
        with c.session_transaction() as s:
            s["user_id"] = uid
            s["active_entity_id"] = entity_id
    return c


def _lire(app, fn):
    with app.app_context():
        db.session.expire_all()
        return fn()


# ── Les douze routes qui écrivaient pour un compte `user` ────────────────

def _cas_rh(ids):
    """(méthode, chemin, kwargs de requête) — le corps que l'écran envoie."""
    v, r = ids["vic"], ids["role_id"]
    return [
        ("/gestion_rh/delete_role/%d" % ids["jetable_id"], {}),
        ("/gestion_rh/role", {"data": {"id": str(r), "name": "Piraté"}}),
        ("/gestion_rh/update_single_setting",
         {"data": {"key": "work_hours_per_day", "value": "12"}}),
        ("/gestion_rh/update_settings", {"data": {"work_hours_per_day": "12"}}),
        ("/gestion_rh/assign_roles", {"data": {"user_id": str(v)}}),
        ("/gestion_rh/collaborateur_roles", {"data": {"user_id": str(v)}}),
        ("/gestion_rh/update_collaborator_name",
         {"json": {"user_id": v, "name": "Pirate Pirate"}}),
        ("/gestion_rh/assign_manager",
         {"json": {"manager_id": ids["usr"], "assignments": [{"user_id": v}]}}),
        ("/gestion_rh/assign_manager_simple",
         {"json": {"user_id": v, "manager_id": ids["usr"]}}),
    ]


def _etat_victime(app, ids):
    from Code.models.models import EntrepriseSettings, Role, User, UserRole

    def lire():
        v = db.session.get(User, ids["vic"])
        s = EntrepriseSettings.query.filter_by(entity_id=ids["entity_id"]).first()
        return {
            "jetable": db.session.get(Role, ids["jetable_id"]) is not None,
            "nom_role": db.session.get(Role, ids["role_id"]).name,
            "heures": s.work_hours_per_day,
            "roles_victime": sorted(x.role_id for x in UserRole.query.filter_by(user_id=v.id)),
            "nom_victime": (v.first_name, v.last_name),
            "manager_victime": v.manager_id,
        }
    return _lire(app, lire)


class TestGestionRhEcritureReservee:

    @pytest.mark.parametrize("rang", range(9))
    def test_un_compte_user_est_refuse_et_rien_ne_bouge(self, app, decor, rang):
        chemin, kw = _cas_rh(decor)[rang]
        avant = _etat_victime(app, decor)
        rv = _client(app, decor["usr"], decor["entity_id"]).post(chemin, **kw)
        assert rv.status_code == 403, (chemin, rv.status_code)
        assert rv.get_json()["code"] == "lecture_seule"
        assert _etat_victime(app, decor) == avant, chemin

    def test_un_champion_est_refuse_aussi(self, app, decor):
        """`acces_rh` est fermé au champion par défaut : il propose des tâches,
        il ne règle pas l'organisation."""
        rv = _client(app, decor["cha"], decor["entity_id"]).post(
            "/gestion_rh/delete_role/%d" % decor["jetable_id"])
        assert rv.status_code == 403
        assert _etat_victime(app, decor)["jetable"] is True

    def test_sans_compte_401_et_le_role_survit(self, app, decor):
        """⚠️ L'exemption tombait AVANT le contrôle du compte : en production,
        l'anonyme supprimait un rôle. Sous TESTING la porte centrale laisse
        passer l'anonyme — c'est donc bien la garde du blueprint qui répond."""
        rv = _client(app, None, None).post("/gestion_rh/delete_role/%d" % decor["jetable_id"])
        assert rv.status_code == 401
        assert rv.get_json()["code"] == "non_connecte"
        assert _etat_victime(app, decor)["jetable"] is True

    def test_import_roles_refuse_avant_de_lire_le_fichier(self, app, decor):
        import io
        from Code.models.models import Role
        rv = _client(app, decor["usr"], decor["entity_id"]).post(
            "/gestion_rh/import_roles", content_type="multipart/form-data",
            data={"role_file": (io.BytesIO("T166 importé\n".encode()), "t166.csv")})
        assert rv.status_code == 403
        assert _lire(app, lambda: Role.query.filter_by(name="T166 importé").count()) == 0

    def test_la_lecture_reste_ouverte(self, app, decor):
        """La garde ne porte que sur l'ÉCRITURE : les GET gardent leur règle."""
        rv = _client(app, decor["usr"], decor["entity_id"]).get("/gestion_rh/roles")
        assert rv.status_code == 200

    def test_le_coordinateur_supprime_toujours(self, app, decor):
        rv = _client(app, decor["coo"], decor["entity_id"]).post(
            "/gestion_rh/delete_role/%d" % decor["jetable_id"])
        assert rv.status_code == 200 and rv.get_json()["success"] is True
        assert _etat_victime(app, decor)["jetable"] is False

    def test_le_coordinateur_regle_toujours_les_heures(self, app, decor):
        rv = _client(app, decor["coo"], decor["entity_id"]).post(
            "/gestion_rh/update_single_setting",
            data={"key": "work_hours_per_day", "value": "8"})
        assert rv.status_code == 200 and rv.get_json()["value"] == 8.0

    def test_l_administrateur_renomme_toujours(self, app, decor):
        rv = _client(app, decor["adm"], decor["entity_id"]).post(
            "/gestion_rh/update_collaborator_name",
            json={"user_id": decor["vic"], "name": "Victime Renommée"})
        assert rv.status_code == 200
        assert _etat_victime(app, decor)["nom_victime"] == ("Victime", "Renommée")


class TestComptesRattachementReserve:

    def test_un_user_ne_se_rattache_personne(self, app, decor):
        """Se rattacher un collègue, c'est devenir son développeur de
        compétences — donc écrire son plan et ses évaluations."""
        rv = _client(app, decor["usr"], decor["entity_id"]).post(
            "/comptes/assign_manager",
            data={"manager_id": str(decor["usr"]), "user_id": str(decor["vic"])})
        assert rv.status_code in (302, 403)
        assert _etat_victime(app, decor)["manager_victime"] is None

    def test_un_user_ne_detache_personne(self, app, decor):
        from Code.models.models import User

        def poser():
            db.session.get(User, decor["vic"]).manager_id = decor["coo"]
            db.session.commit()
        _lire(app, poser)
        rv = _client(app, decor["usr"], decor["entity_id"]).post(
            "/comptes/remove_collaborator/%d" % decor["vic"])
        assert rv.status_code in (302, 403)
        assert _etat_victime(app, decor)["manager_victime"] == decor["coo"]

    def test_refus_en_json_pour_un_fetch(self, app, decor):
        rv = _client(app, decor["usr"], decor["entity_id"]).post(
            "/comptes/assign_manager", headers={"Accept": "application/json"},
            data={"manager_id": str(decor["usr"]), "user_id": str(decor["vic"])})
        assert rv.status_code == 403
        assert rv.get_json()["ok"] is False

    def test_le_coordinateur_rattache_toujours(self, app, decor):
        rv = _client(app, decor["coo"], decor["entity_id"]).post(
            "/comptes/assign_manager",
            data={"manager_id": str(decor["coo"]), "user_id": str(decor["vic"])})
        assert rv.status_code == 200
        assert [s["id"] for s in rv.get_json()["subordinates"]] == [decor["vic"]]


# ── Le balayage : toute route d'écriture exemptée, appelée par un `user` ──

# ⚠️ Ce qu'un `user` a LE DROIT d'écrire, et rien d'autre — chaque ligne nomme
# la table touchée et pourquoi c'est légitime.
ECRITURES_PERMISES = {
    ("POST", "/parametres/set_language"): {"users"},        # sa propre langue
    ("POST", "/api/bienvenue/vue"): {"welcome_seen"},       # « j'ai lu »
    # Sa PROPRE carto privée : il en est propriétaire, donc il y fait ce qu'il
    # veut (`carto_access.can_edit`). Créer, puis activer, désactive les autres.
    ("POST", "/activities/api/entities"): {"entities"},
    ("POST", "/activities/api/entities/<int:entity_id>/activate"): {"entities"},
}

# Hors balayage, et pourquoi :
NON_BALAYEES = (
    # Appellent l'IA et n'écrivent rien (un cliquet de test_164 le garde) ;
    # sans clé ils rendraient une erreur qui ne prouve rien.
    "/propose_", "/translate_softskills", "/api/chatbot/chat", "/skills/propose",
    "/diagnostic/plan", "/hsc/position",
    # Le panel lance pytest et n'a AUCUNE authentification — sujet déjà
    # inscrit à l'audit (§ 9, « à décider »), pas une régression à cacher ici.
    "/testpanel",
)


def _empreinte():
    out = {}
    for t in db.metadata.sorted_tables:
        try:
            rows = db.session.execute(text('SELECT * FROM "%s"' % t.name)).fetchall()
        except Exception:
            db.session.rollback()
            continue
        out[t.name] = hashlib.md5(repr(sorted(map(repr, rows))).encode()).hexdigest()
    return out


def _routes_exemptees(app):
    for r in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        ms = sorted((r.methods or set()) & METHODES_ECRITURE)
        if (ms and r.rule.startswith(TOUT_COMPTE) and not r.rule.startswith(SANS_COMPTE)
                and not r.rule.startswith(NON_BALAYEES)):
            for m in ms:
                yield m, r.rule


def _corps(ids):
    """Un corps qui porte TOUTES les clés que ces routes lisent : un refus pour
    champ manquant ne prouverait rien."""
    return dict(
        role_id=ids["role_id"], user_id=ids["vic"], activity_id=ids["activity_id"],
        data_id=ids["data_id"], entity_id=ids["entity_id"], name="T166 carto perso",
        manager_id=ids["usr"], assignments=[{"user_id": ids["vic"], "role_id": ids["role_id"]}],
        key="work_hours_per_day", value="12", action="accept", evaluator="0",
        mastery_level=2, required_mastery_level=2, role_ids=[ids["role_id"]],
        first_name="Pirate", last_name="P", email=PREFIXE + "nouveau@x.com",
        status="admin", password=MDP + "xx", id=ids["role_id"])


class TestBalayageCompteUser:

    def test_le_balayage_couvre_bien_les_routes(self, app):
        """Garde-fou de volume : un filtre qui ne retiendrait plus rien
        verdirait le balayage en n'appelant personne."""
        assert len(list(_routes_exemptees(app))) >= 70

    def test_un_user_n_ecrit_que_ce_qui_est_permis(self, app, decor):
        corps = _corps(decor)
        valeurs = {"entity_id": decor["entity_id"], "user_id": decor["vic"],
                   "role_id": decor["role_id"], "data_id": decor["data_id"]}

        def chemin_de(rule):
            def sub(m):
                nom = m.group(1).split(":")[-1]
                return str(valeurs.get(nom, 1)) if nom not in ("name", "slug") else "x"
            return re.sub(r"<([^>]+)>", sub, rule)

        c = _client(app, decor["usr"], decor["entity_id"])
        fautes = []
        for methode, rule in _routes_exemptees(app):
            permises = ECRITURES_PERMISES.get((methode, rule), set())
            for genre in ("json", "form"):
                kw = ({"json": corps} if genre == "json" else
                      {"data": {k: str(v[0] if isinstance(v, list) else v)
                                for k, v in corps.items()}})
                avant = _lire(app, _empreinte)
                rv = c.open(chemin_de(rule), method=methode, **kw)
                apres = _lire(app, _empreinte)
                touchees = {t for t in avant if avant[t] != apres.get(t)} - permises
                if touchees or rv.status_code >= 500:
                    fautes.append((genre, methode, rule, rv.status_code, sorted(touchees)))
        assert fautes == []
