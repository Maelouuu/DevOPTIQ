# tests/test_105_roles_communs.py
"""
Couvre Code/roles_communs.py : recherche d'un rôle commun par nom, détection
d'usage et fusion des doublons. Chaque test crée ses rôles/utilisateurs
jetables (préfixe « RC105 ») et les supprime en fin de test.
"""
import uuid

import pytest

pytestmark = pytest.mark.roles_communs


@pytest.fixture
def ctx(app, ids):
    """Contexte d'appli + nettoyage de tout ce qui porte le préfixe RC105."""
    from Code.extensions import db
    from Code.models.models import (
        Role, User, UserRole, activity_roles, task_roles, Activities, Task,
        AppSetting, EntityRoleAccess,
    )

    with app.app_context():
        yield db
        db.session.rollback()
        roles = Role.query.filter(Role.name.like("RC105%")).all()
        rids = [r.id for r in roles]
        if rids:
            UserRole.query.filter(UserRole.role_id.in_(rids)).delete(synchronize_session=False)
            EntityRoleAccess.query.filter(EntityRoleAccess.role_id.in_(rids)).delete(
                synchronize_session=False)
            db.session.execute(activity_roles.delete().where(activity_roles.c.role_id.in_(rids)))
            db.session.execute(task_roles.delete().where(task_roles.c.role_id.in_(rids)))
            Role.query.filter(Role.id.in_(rids)).delete(synchronize_session=False)
        User.query.filter(User.email.like("rc105-%")).delete(synchronize_session=False)
        Task.query.filter(Task.name.like("RC105%")).delete(synchronize_session=False)
        Activities.query.filter(Activities.name.like("RC105%")).delete(synchronize_session=False)
        db.session.commit()


def _user(db):
    from Code.models.models import User
    u = User(first_name="RC", last_name="105", password="x", status="user",
             email=f"rc105-{uuid.uuid4().hex[:8]}@t.io")
    db.session.add(u)
    db.session.flush()
    return u


class TestNormalise:

    def test_retire_accents_casse_et_espaces(self):
        from Code.roles_communs import normalise
        assert normalise("  Développeur   DE  Compétences ") == "developpeur de competences"

    def test_valeur_vide_ou_none(self):
        from Code.roles_communs import normalise
        assert normalise(None) == ""
        assert normalise("") == ""


class TestRoleParNom:

    def test_nom_vide_renvoie_none(self, ctx):
        from Code.roles_communs import role_par_nom
        assert role_par_nom("   ") is None
        assert role_par_nom(None) is None

    def test_cree_le_role_absent(self, ctx, ids):
        from Code.roles_communs import role_par_nom
        r = role_par_nom("RC105 Créé", entity_id=ids["entity_id"])
        assert r.id is not None
        assert r.name == "RC105 Créé"
        assert r.hors_carte is False

    def test_creer_false_ne_cree_pas(self, ctx):
        from Code.models.models import Role
        from Code.roles_communs import role_par_nom
        assert role_par_nom("RC105 Fantôme", creer=False) is None
        assert Role.query.filter_by(name="RC105 Fantôme").first() is None

    def test_retrouve_malgre_casse_et_accents(self, ctx):
        from Code.roles_communs import role_par_nom
        r = role_par_nom("RC105 Résumé")
        trouve = role_par_nom("rc105 resume", creer=False)
        assert trouve is not None and trouve.id == r.id

    def test_retrouve_par_casse_seule(self, ctx):
        from Code.roles_communs import role_par_nom
        r = role_par_nom("RC105 Casse")
        assert role_par_nom("rc105 casse", creer=False).id == r.id

    def test_hors_carte_marque_un_role_existant(self, ctx):
        from Code.roles_communs import role_par_nom
        r = role_par_nom("RC105 Hors")
        assert r.hors_carte is False
        again = role_par_nom("RC105 Hors", hors_carte=True)
        assert again.id == r.id
        assert again.hors_carte is True

    def test_hors_carte_a_la_creation(self, ctx):
        from Code.roles_communs import role_par_nom
        assert role_par_nom("RC105 HorsNeuf", hors_carte=True).hors_carte is True

    def test_nom_tronque_a_100_caracteres(self, ctx):
        from Code.roles_communs import role_par_nom
        r = role_par_nom("RC105" + "x" * 150)
        assert len(r.name) == 100

    def test_index_est_utilise_et_tenu_a_jour(self, ctx):
        from Code.roles_communs import index_par_nom, role_par_nom
        index = index_par_nom()
        r = role_par_nom("RC105 Indexé", index=index)
        assert index["rc105 indexe"] is r
        assert role_par_nom("RC105 INDEXE", index=index) is r

    def test_index_sans_correspondance_et_creer_false(self, ctx):
        from Code.roles_communs import role_par_nom
        assert role_par_nom("RC105 Absent", creer=False, index={}) is None

    def test_index_par_nom_garde_le_premier_doublon(self, ctx):
        from Code.models.models import Role
        from Code.roles_communs import index_par_nom
        a = Role(name="RC105 Dup")
        b = Role(name="rc105 dup")
        ctx.session.add_all([a, b])
        ctx.session.flush()
        assert index_par_nom()["rc105 dup"].id == a.id


class TestEstUtilise:

    def test_none_et_role_non_persiste(self, ctx):
        from Code.models.models import Role
        from Code.roles_communs import est_utilise
        assert est_utilise(None) is False
        assert est_utilise(Role(name="RC105 Neuf")) is False

    def test_role_libre(self, ctx):
        from Code.roles_communs import est_utilise, role_par_nom
        assert est_utilise(role_par_nom("RC105 Libre")) is False

    def test_role_avec_titulaire(self, ctx):
        from Code.models.models import UserRole
        from Code.roles_communs import est_utilise, role_par_nom
        r = role_par_nom("RC105 Titulaire")
        u = _user(ctx)
        ctx.session.add(UserRole(user_id=u.id, role_id=r.id))
        ctx.session.flush()
        assert est_utilise(r) is True

    def test_role_avec_activite(self, ctx, ids):
        from Code.models.models import Activities, activity_roles
        from Code.roles_communs import est_utilise, role_par_nom
        r = role_par_nom("RC105 Activité")
        a = Activities(entity_id=ids["entity_id"], name="RC105 Act")
        ctx.session.add(a)
        ctx.session.flush()
        ctx.session.execute(activity_roles.insert().values(activity_id=a.id, role_id=r.id, status="x"))
        assert est_utilise(r) is True

    def test_role_avec_tache(self, ctx, ids):
        from Code.models.models import Activities, Task, task_roles
        from Code.roles_communs import est_utilise, role_par_nom
        r = role_par_nom("RC105 Tâche")
        a = Activities(entity_id=ids["entity_id"], name="RC105 ActT")
        ctx.session.add(a)
        ctx.session.flush()
        t = Task(name="RC105 T", activity_id=a.id, order=1)
        ctx.session.add(t)
        ctx.session.flush()
        ctx.session.execute(task_roles.insert().values(task_id=t.id, role_id=r.id, status="x"))
        assert est_utilise(r) is True


class TestFusionnerPaire:

    def _paire(self, ctx):
        from Code.roles_communs import role_par_nom
        return role_par_nom("RC105 Garde"), role_par_nom("RC105 Doublon")

    def test_titulaires_reportes_et_doublon_efface(self, ctx):
        from Code.models.models import Role, UserRole
        from Code.roles_communs import _fusionner_paire
        garde, dbl = self._paire(ctx)
        u = _user(ctx)
        ctx.session.add(UserRole(user_id=u.id, role_id=dbl.id))
        ctx.session.flush()
        did = dbl.id
        _fusionner_paire(garde, dbl)
        assert UserRole.query.filter_by(user_id=u.id, role_id=garde.id).count() == 1
        assert db_get(ctx, Role, did) is None

    def test_titulaire_commun_garde_le_manager_manquant(self, ctx):
        from Code.models.models import UserRole
        from Code.roles_communs import _fusionner_paire
        garde, dbl = self._paire(ctx)
        u, boss = _user(ctx), _user(ctx)
        ctx.session.add_all([UserRole(user_id=u.id, role_id=garde.id),
                             UserRole(user_id=u.id, role_id=dbl.id, manager_id=boss.id)])
        ctx.session.flush()
        _fusionner_paire(garde, dbl)
        lignes = UserRole.query.filter_by(user_id=u.id).all()
        assert len(lignes) == 1
        assert lignes[0].role_id == garde.id and lignes[0].manager_id == boss.id

    def test_titulaire_commun_ne_remplace_pas_un_manager_existant(self, ctx):
        from Code.models.models import UserRole
        from Code.roles_communs import _fusionner_paire
        garde, dbl = self._paire(ctx)
        u, b1, b2 = _user(ctx), _user(ctx), _user(ctx)
        ctx.session.add_all([UserRole(user_id=u.id, role_id=garde.id, manager_id=b1.id),
                             UserRole(user_id=u.id, role_id=dbl.id, manager_id=b2.id)])
        ctx.session.flush()
        _fusionner_paire(garde, dbl)
        assert UserRole.query.filter_by(user_id=u.id).one().manager_id == b1.id

    def test_activites_reportees_sans_doublon_de_paire(self, ctx, ids):
        from Code.models.models import Activities, activity_roles
        from Code.roles_communs import _fusionner_paire
        garde, dbl = self._paire(ctx)
        a1 = Activities(entity_id=ids["entity_id"], name="RC105 A1")
        a2 = Activities(entity_id=ids["entity_id"], name="RC105 A2")
        ctx.session.add_all([a1, a2])
        ctx.session.flush()
        ctx.session.execute(activity_roles.insert().values(
            [{"activity_id": a1.id, "role_id": garde.id, "status": "x"},
             {"activity_id": a1.id, "role_id": dbl.id, "status": "x"},
             {"activity_id": a2.id, "role_id": dbl.id, "status": "x"}]))
        _fusionner_paire(garde, dbl)
        rows = ctx.session.execute(
            ctx.select(activity_roles.c.activity_id).where(
                activity_roles.c.role_id == garde.id)).scalars().all()
        assert sorted(rows) == sorted([a1.id, a2.id])
        assert ctx.session.execute(
            ctx.select(ctx.func.count()).select_from(activity_roles).where(
                activity_roles.c.role_id == dbl.id)).scalar() == 0

    def test_acces_entite_en_double_est_jete(self, ctx, ids):
        from Code.models.models import EntityRoleAccess
        from Code.roles_communs import _fusionner_paire
        garde, dbl = self._paire(ctx)
        ctx.session.add_all([
            EntityRoleAccess(entity_id=ids["entity_id"], role_id=garde.id),
            EntityRoleAccess(entity_id=ids["entity_id"], role_id=dbl.id)])
        ctx.session.flush()
        _fusionner_paire(garde, dbl)
        assert EntityRoleAccess.query.filter_by(
            entity_id=ids["entity_id"], role_id=garde.id).count() == 1
        assert EntityRoleAccess.query.filter_by(role_id=dbl.id).count() == 0

    def test_acces_entite_unique_est_reporte(self, ctx, ids):
        from Code.models.models import EntityRoleAccess
        from Code.roles_communs import _fusionner_paire
        garde, dbl = self._paire(ctx)
        ctx.session.add(EntityRoleAccess(entity_id=ids["entity_id"], role_id=dbl.id))
        ctx.session.flush()
        _fusionner_paire(garde, dbl)
        assert EntityRoleAccess.query.filter_by(
            entity_id=ids["entity_id"], role_id=garde.id).count() == 1

    def test_champs_manquants_et_hors_carte_herites(self, ctx):
        from Code.roles_communs import _fusionner_paire
        garde, dbl = self._paire(ctx)
        garde.name_fr = "Déjà là"
        dbl.name_fr = "Ignoré"
        dbl.name_en = "English"
        dbl.mission_generale = "Mission"
        dbl.hors_carte = True
        ctx.session.flush()
        _fusionner_paire(garde, dbl)
        assert garde.name_fr == "Déjà là"
        assert garde.name_en == "English"
        assert garde.mission_generale == "Mission"
        assert garde.hors_carte is True


def db_get(ctx, model, pk):
    return ctx.session.get(model, pk)


class TestFusionnerDoublons:

    def test_deja_fait_ne_fait_rien(self, ctx):
        from Code.models.models import AppSetting
        from Code.roles_communs import CLE_FUSION, fusionner_doublons, role_par_nom
        cree = ctx.session.get(AppSetting, CLE_FUSION) is None
        if cree:
            ctx.session.add(AppSetting(key=CLE_FUSION, value="1"))
            ctx.session.commit()
        try:
            role_par_nom("RC105 Zéro")
            ctx.session.add(__import__("Code.models.models", fromlist=["Role"]).Role(name="rc105 zero"))
            ctx.session.commit()
            assert fusionner_doublons() == 0
        finally:
            if cree:
                ctx.session.delete(ctx.session.get(AppSetting, CLE_FUSION))
                ctx.session.commit()

    def test_force_garde_le_role_qui_a_le_plus_de_titulaires(self, ctx):
        from Code.models.models import AppSetting, Role, UserRole
        from Code.roles_communs import CLE_FUSION, fusionner_doublons
        a, b = Role(name="RC105 Fus"), Role(name="rc105 fus")
        ctx.session.add_all([a, b])
        ctx.session.flush()
        u1, u2 = _user(ctx), _user(ctx)
        ctx.session.add_all([UserRole(user_id=u1.id, role_id=b.id),
                             UserRole(user_id=u2.id, role_id=b.id)])
        ctx.session.commit()
        aid, bid = a.id, b.id
        cree = ctx.session.get(AppSetting, CLE_FUSION) is None
        try:
            assert fusionner_doublons(force=True) >= 1
            assert ctx.session.get(Role, aid) is None
            assert ctx.session.get(Role, bid) is not None
            assert UserRole.query.filter_by(role_id=bid).count() == 2
            assert ctx.session.get(AppSetting, CLE_FUSION) is not None
        finally:
            if cree:
                s = ctx.session.get(AppSetting, CLE_FUSION)
                if s:
                    ctx.session.delete(s)
                    ctx.session.commit()

    def test_a_egalite_le_plus_ancien_est_garde(self, ctx):
        from Code.models.models import AppSetting, Role
        from Code.roles_communs import CLE_FUSION, fusionner_doublons
        a, b = Role(name="RC105 Egal"), Role(name="rc105 egal")
        ctx.session.add_all([a, b])
        ctx.session.commit()
        aid, bid = a.id, b.id
        cree = ctx.session.get(AppSetting, CLE_FUSION) is None
        try:
            fusionner_doublons(force=True)
            assert ctx.session.get(Role, aid) is not None
            assert ctx.session.get(Role, bid) is None
        finally:
            if cree:
                s = ctx.session.get(AppSetting, CLE_FUSION)
                if s:
                    ctx.session.delete(s)
                    ctx.session.commit()
