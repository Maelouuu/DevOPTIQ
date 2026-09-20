# tests/test_81_droits_reglables.py
"""
Ce que chaque palier OUVRE se règle — l'échelle, elle, ne bouge pas.

`user < champion < coordinateur < admin` est la grammaire du produit. Ce que
chacun ouvre dépend en revanche de l'entreprise : chez l'une tout le monde
propose, chez l'autre seul un coordinateur touche à la carto. La page RH porte
donc un tableau (droit × palier) que l'administrateur règle.

Trois garde-fous, et chacun répare une façon précise de se tirer une balle
dans le pied :

⚠️ **Le défaut EST le comportement d'hier.** Une instance qui n'a jamais rien
réglé ne change pas de comportement en prenant ce code. Sans cette règle, une
livraison redistribuerait silencieusement les droits de tout le monde.

⚠️ **La colonne `admin` est verrouillée à VRAI.** Se retirer les Paramètres,
c'est perdre l'écran depuis lequel on les remettrait : la porte se refermerait
de l'intérieur, sans poignée. Le serveur la reforce même si la requête demande
le contraire — le masquage côté écran ne serait pas une sécurité.

⚠️ **Seul un administrateur ÉCRIT.** Un coordinateur qui pourrait s'attribuer
les sections d'administration s'attribuerait la clé IA de l'entreprise. Il LIT
le tableau — savoir qui a quoi fait partie de son travail — sans le changer.

⚠️ Et on ne stocke que les ÉCARTS au défaut : enregistrer la table entière
figerait les valeurs d'origine, et le jour où le produit en change une, les
instances qui n'y avaient jamais touché garderaient l'ancienne sans le savoir.
"""
import pytest

pytestmark = pytest.mark.gestion_rh


@pytest.fixture
def table_propre(app):
    """⚠️ Ce réglage est à l'échelle de l'INSTANCE, et la base est partagée
    entre tous les fichiers de tests : laisser une ligne derrière soi
    changerait les droits de toute la suite."""
    from Code.extensions import db
    from Code.models.models import AppSetting
    from Code.permissions import CLE_DROITS

    def nettoyer():
        # ⚠️ On ÉCRIT un réglage vide au lieu de SUPPRIMER la ligne. Supprimer
        # paraissait plus propre et ne l'était pas : la session de test est
        # partagée (`scope=session` dans conftest), et entre sa carte
        # d'identité et celle de la session que Flask ouvre par requête, le
        # test et la requête ne voyaient pas la même chose — le réglage posé
        # par un test survivait au suivant, qui tombait alors sur des droits
        # qu'il n'avait pas posés. Une table d'écarts VIDE vaut exactement les
        # valeurs d'origine, et elle, on est sûr de l'avoir écrite.
        with app.app_context():
            db.session.rollback()
            row = db.session.get(AppSetting, CLE_DROITS)
            if row is None:
                row = AppSetting(key=CLE_DROITS)
                db.session.add(row)
            row.value = "{}"
            db.session.commit()

    nettoyer()
    yield
    nettoyer()


@pytest.fixture
def comptes(app):
    from Code.extensions import db
    from Code.models.models import User
    from Code.security import hash_password
    faits = {}
    with app.app_context():
        for statut in ("user", "champion", "coordinateur", "admin"):
            mail = "t81.%s@devoptiq.com" % statut
            u = User.query.filter_by(email=mail).first()
            if u is None:
                u = User(first_name="T81", last_name=statut.capitalize(),
                         email=mail, password=hash_password("Motdepasse123!"),
                         status=statut)
                db.session.add(u)
            u.status = statut
            db.session.commit()
            faits[statut] = u.id
    yield faits
    with app.app_context():
        for uid in faits.values():
            User.query.filter_by(id=uid).delete()
        db.session.commit()


def _en_tant_que(client, uid, mail):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["user_email"] = mail
        sess["lang"] = "fr"


# ══════════════════════════════════════════════════════════════════════
#  1 · Le défaut ne change RIEN
# ══════════════════════════════════════════════════════════════════════
class TestLeDefautEstLeComportementDHier:

    ATTENDU = {
        #                 propose  edit  review  rh    admin_settings
        "user":          (False, False, False, False, False),
        "champion":      (True,  False, False, False, False),
        "coordinateur":  (True,  True,  True,  True,  False),
        "admin":         (True,  True,  True,  True,  True),
    }

    def test_sans_reglage_chaque_palier_retrouve_ses_droits(
            self, app, table_propre, comptes):
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import (can_access_rh, can_edit_carto,
                                      can_propose_carto, can_review_carto,
                                      can_see_admin_settings)
        with app.app_context():
            for statut, (prop, edit, rev, rh, adm) in self.ATTENDU.items():
                u = db.session.get(User, comptes[statut])
                assert can_propose_carto(u) is prop, statut
                assert can_edit_carto(u) is edit, statut
                assert can_review_carto(u) is rev, statut
                assert can_access_rh(u) is rh, statut
                assert can_see_admin_settings(u) is adm, statut

    def test_un_reglage_illisible_retombe_sur_le_defaut(
            self, app, table_propre, comptes):
        """Un JSON abîmé ne doit pas verrouiller l'application : mieux vaut les
        valeurs d'origine qu'un refus général."""
        from Code.extensions import db
        from Code.models.models import AppSetting, User
        from Code.permissions import CLE_DROITS, can_edit_carto
        with app.app_context():
            row = db.session.get(AppSetting, CLE_DROITS)
            if row is None:
                row = AppSetting(key=CLE_DROITS)
                db.session.add(row)
            row.value = "{ceci n'est pas du JSON"
            db.session.commit()
        with app.app_context():
            coord = db.session.get(User, comptes["coordinateur"])
            assert can_edit_carto(coord) is True


# ══════════════════════════════════════════════════════════════════════
#  2 · Régler change vraiment ce que l'application autorise
# ══════════════════════════════════════════════════════════════════════
class TestReglerChangeLeComportement:

    def test_ouvrir_la_proposition_au_palier_user(self, app, table_propre, comptes):
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import (can_propose_carto, droits_effectifs,
                                      enregistrer_droits)
        with app.app_context():
            table = droits_effectifs()
            table["propose_carto"]["user"] = True
            enregistrer_droits(table)
        with app.app_context():
            assert can_propose_carto(db.session.get(User, comptes["user"])) is True

    def test_fermer_la_page_rh_au_coordinateur(self, app, table_propre, comptes):
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import (can_access_rh, droits_effectifs,
                                      enregistrer_droits)
        with app.app_context():
            table = droits_effectifs()
            table["acces_rh"]["coordinateur"] = False
            enregistrer_droits(table)
        with app.app_context():
            assert can_access_rh(db.session.get(User, comptes["coordinateur"])) is False
            # ⚠️ L'administrateur, lui, garde la page : c'est elle qui permet
            # de revenir en arrière.
            assert can_access_rh(db.session.get(User, comptes["admin"])) is True

    def test_l_editeur_suit_le_tableau(self, app, client, table_propre, comptes):
        """Bout en bout : le réglage décide de ce que l'ÉCRAN arme.

        Un `user` à qui on ouvre la proposition ne doit plus recevoir l'éditeur
        en lecture seule — sinon le réglage ne serait qu'un affichage.
        """
        from Code.carto_access import access_summary
        from Code.extensions import db
        from Code.models.models import Entity, User
        from Code.permissions import droits_effectifs, enregistrer_droits
        from Code.security import hash_password

        with app.app_context():
            proprio = User(first_name="T81", last_name="Proprio",
                           email="t81.proprio@devoptiq.com",
                           password=hash_password("Motdepasse123!"),
                           status="coordinateur")
            db.session.add(proprio)
            db.session.commit()
            ent = Entity(name="T81 Commune", owner_id=proprio.id, is_shared=True)
            db.session.add(ent)
            db.session.commit()
            eid, pid = ent.id, proprio.id
        try:
            with app.app_context():
                ent = db.session.get(Entity, eid)
                simple = db.session.get(User, comptes["user"])
                assert access_summary(ent, simple)["lecture_seule"] is True

                table = droits_effectifs()
                table["propose_carto"]["user"] = True
                enregistrer_droits(table)

            with app.app_context():
                ent = db.session.get(Entity, eid)
                simple = db.session.get(User, comptes["user"])
                vu = access_summary(ent, simple)
                assert vu["lecture_seule"] is False
                assert vu["must_propose"] is True
        finally:
            with app.app_context():
                Entity.query.filter_by(id=eid).delete()
                User.query.filter_by(id=pid).delete()
                db.session.commit()


# ══════════════════════════════════════════════════════════════════════
#  3 · Ce qu'on ne peut PAS faire
# ══════════════════════════════════════════════════════════════════════
class TestLesGardeFous:

    def test_l_administrateur_garde_tout_meme_si_on_demande_le_contraire(
            self, app, table_propre, comptes):
        """⚠️ Le masquage n'est pas une sécurité : la requête peut demander
        n'importe quoi, le serveur reforce la colonne."""
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import (can_see_admin_settings, droits_effectifs,
                                      enregistrer_droits)
        with app.app_context():
            table = droits_effectifs()
            for droit in table:
                table[droit]["admin"] = False
            enregistrer_droits(table)
        with app.app_context():
            admin = db.session.get(User, comptes["admin"])
            assert can_see_admin_settings(admin) is True
            assert droits_effectifs()["parametres_admin"]["admin"] is True

    def test_seul_l_administrateur_ecrit(self, app, client, table_propre, comptes):
        from Code.permissions import droits_effectifs
        with app.app_context():
            table = droits_effectifs()
        table["acces_rh"]["user"] = True

        _en_tant_que(client, comptes["coordinateur"], "t81.coordinateur@devoptiq.com")
        assert client.get("/comptes/droits").status_code == 200, (
            "un coordinateur doit POUVOIR lire le tableau")
        r = client.post("/comptes/droits", json={"droits": table})
        assert r.status_code == 403

        _en_tant_que(client, comptes["admin"], "t81.admin@devoptiq.com")
        assert client.post("/comptes/droits",
                           json={"droits": table}).status_code == 200

    def test_un_user_ne_lit_meme_pas_le_tableau(self, app, client, table_propre,
                                                comptes):
        _en_tant_que(client, comptes["user"], "t81.user@devoptiq.com")
        assert client.get("/comptes/droits").status_code == 403
        assert client.post("/comptes/droits", json={"droits": {}}).status_code == 403

    def test_on_ne_stocke_que_les_ECARTS(self, app, table_propre, comptes):
        """Enregistrer la table entière figerait les défauts : le jour où le
        produit change une valeur d'origine, les instances qui n'y avaient
        jamais touché garderaient l'ancienne sans le savoir."""
        import json
        from Code.extensions import db
        from Code.models.models import AppSetting
        from Code.permissions import (CLE_DROITS, droits_effectifs,
                                      enregistrer_droits)
        with app.app_context():
            table = droits_effectifs()
            table["propose_carto"]["user"] = True
            enregistrer_droits(table)
            brut = json.loads(db.session.get(AppSetting, CLE_DROITS).value)
        assert brut == {"propose_carto": {"user": True}}, (
            "seul l'écart doit être stocké, pas la table entière : %s" % brut)

    def test_revenir_au_defaut_efface_l_ecart(self, app, table_propre, comptes):
        import json
        from Code.extensions import db
        from Code.models.models import AppSetting
        from Code.permissions import (CLE_DROITS, DROITS_DEFAUT,
                                      droits_effectifs, enregistrer_droits)
        with app.app_context():
            table = droits_effectifs()
            table["propose_carto"]["user"] = True
            enregistrer_droits(table)
            enregistrer_droits({d: dict(v) for d, v in DROITS_DEFAUT.items()})
            brut = json.loads(db.session.get(AppSetting, CLE_DROITS).value)
        assert brut == {}

    def test_le_tableau_rendu_porte_les_quatre_paliers(self, app, client,
                                                       table_propre, comptes):
        _en_tant_que(client, comptes["admin"], "t81.admin@devoptiq.com")
        d = client.get("/comptes/droits").get_json()
        assert d["paliers"] == ["user", "champion", "coordinateur", "admin"]
        assert d["modifiable"] is True
        for droit, ligne in d["droits"].items():
            assert set(ligne) == {"user", "champion", "coordinateur", "admin"}, droit
            assert ligne["admin"] is True, droit
