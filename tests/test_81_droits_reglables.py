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

# ══════════════════════════════════════════════════════════════════════
#  5 · Modifier le compte d'un AUTRE
# ══════════════════════════════════════════════════════════════════════
#
# Demandé par le pilote : un coordinateur doit pouvoir corriger la fiche d'un
# collaborateur sans passer par un administrateur. Le droit se règle comme les
# autres ; par défaut il est ouvert au coordinateur, fermé au champion et au
# simple utilisateur.
#
# ⚠️ Le cas qui décide de tout est `test_on_ne_modifie_jamais_un_palier_plus_haut` :
# `/comptes/set_password` passe par la MÊME porte. Sans cette règle, un
# coordinateur réinitialiserait le mot de passe d'un administrateur puis se
# connecterait à sa place — le droit de modifier vaudrait le droit d'être
# administrateur.


class TestModifierUnCompte:

    def _porte(self, app, acteur, cible, comptes):
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import can_edit_account
        with app.app_context():
            moi = db.session.get(User, comptes[acteur])
            return can_edit_account(comptes[cible], moi)

    # ── Le défaut ───────────────────────────────────────────────────────
    def test_par_defaut_le_coordinateur_modifie_un_autre_compte(
            self, app, table_propre, comptes):
        assert self._porte(app, "coordinateur", "user", comptes) is True
        assert self._porte(app, "coordinateur", "champion", comptes) is True

    def test_par_defaut_le_champion_ne_modifie_pas_un_autre_compte(
            self, app, table_propre, comptes):
        assert self._porte(app, "champion", "user", comptes) is False

    def test_par_defaut_le_simple_utilisateur_ne_modifie_personne(
            self, app, table_propre, comptes):
        assert self._porte(app, "user", "champion", comptes) is False

    def test_l_administrateur_modifie_tout_le_monde(self, app, table_propre, comptes):
        for cible in ("user", "champion", "coordinateur", "admin"):
            assert self._porte(app, "admin", cible, comptes) is True, cible

    # ── Son propre compte, toujours ─────────────────────────────────────
    def test_chacun_modifie_son_PROPRE_compte_sans_aucun_droit(
            self, app, table_propre, comptes):
        """Même fermé à tous les paliers, le droit ne verrouille pas sa propre
        fiche : on n'a pas besoin d'une permission pour changer son mot de
        passe."""
        from Code.permissions import droits_effectifs, enregistrer_droits
        with app.app_context():
            table = droits_effectifs()
            for palier in ("user", "champion", "coordinateur"):
                table["modifie_comptes"][palier] = False
            enregistrer_droits(table)
        for qui in ("user", "champion", "coordinateur", "admin"):
            assert self._porte(app, qui, qui, comptes) is True, qui

    # ── Le garde-fou ────────────────────────────────────────────────────
    def test_on_ne_modifie_jamais_un_palier_plus_haut(
            self, app, table_propre, comptes):
        assert self._porte(app, "coordinateur", "admin", comptes) is False
        assert self._porte(app, "champion", "admin", comptes) is False

    def test_un_pair_reste_modifiable(self, app, table_propre, comptes):
        """Deux coordinateurs sont au même palier : l'un corrige la fiche de
        l'autre. Ce n'est pas une montée en droits, c'est le travail."""
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import can_edit_account
        from Code.security import hash_password
        with app.app_context():
            autre = User(first_name="T81", last_name="Coord2",
                         email="t81.coord2@devoptiq.com",
                         password=hash_password("Motdepasse123!"),
                         status="coordinateur")
            db.session.add(autre)
            db.session.commit()
            aid = autre.id
            moi = db.session.get(User, comptes["coordinateur"])
            try:
                assert can_edit_account(aid, moi) is True
            finally:
                User.query.filter_by(id=aid).delete()
                db.session.commit()

    # ── Le réglage change vraiment le comportement ──────────────────────
    def test_fermer_le_droit_retire_la_modification_au_coordinateur(
            self, app, table_propre, comptes):
        from Code.permissions import droits_effectifs, enregistrer_droits
        with app.app_context():
            table = droits_effectifs()
            table["modifie_comptes"]["coordinateur"] = False
            enregistrer_droits(table)
        assert self._porte(app, "coordinateur", "user", comptes) is False
        # ⚠️ L'administrateur garde la main : c'est lui qui rouvre le droit.
        assert self._porte(app, "admin", "user", comptes) is True

    def test_ouvrir_le_droit_au_champion_le_lui_donne(
            self, app, table_propre, comptes):
        from Code.permissions import droits_effectifs, enregistrer_droits
        with app.app_context():
            table = droits_effectifs()
            table["modifie_comptes"]["champion"] = True
            enregistrer_droits(table)
        assert self._porte(app, "champion", "user", comptes) is True
        # …mais jamais au-dessus de lui.
        assert self._porte(app, "champion", "coordinateur", comptes) is False

    # ── Les routes suivent la porte ─────────────────────────────────────
    def test_set_password_suit_la_porte(self, app, client, table_propre, comptes):
        """La route qui réinitialise un mot de passe passe par `can_edit_account` :
        c'est elle qui rendrait une montée en droits possible."""
        _en_tant_que(client, comptes["coordinateur"], "t81.coordinateur@devoptiq.com")
        ok = client.post("/comptes/set_password/%d" % comptes["user"],
                         json={"password": "NouveauMdp123!"})
        assert ok.status_code == 200, ok.get_data(as_text=True)[:200]

        refus = client.post("/comptes/set_password/%d" % comptes["admin"],
                            json={"password": "NouveauMdp123!"})
        assert refus.status_code == 403

    def test_le_bouton_Modifier_suit_la_porte(self, app, client, table_propre, comptes):
        """Le gabarit ne redit pas la règle : il lit le drapeau calculé par la
        MÊME fonction que les routes."""
        _en_tant_que(client, comptes["coordinateur"], "t81.coordinateur@devoptiq.com")
        html = client.get("/comptes/").get_data(as_text=True)
        attendu = 'data-action="modifier" data-id="%d"'
        assert (attendu % comptes["user"]) in html
        assert (attendu % comptes["admin"]) not in html

    def test_le_droit_parait_dans_le_tableau_rendu(self, app, client, table_propre,
                                                   comptes):
        _en_tant_que(client, comptes["admin"], "t81.admin@devoptiq.com")
        table = client.get("/comptes/droits").get_json()
        assert "modifie_comptes" in table["droits"]
        assert table["droits"]["modifie_comptes"]["admin"] is True
        assert table["defaut"]["modifie_comptes"]["champion"] is False

# ══════════════════════════════════════════════════════════════════════
#  6 · Changer le STATUT de quelqu'un
# ══════════════════════════════════════════════════════════════════════
#
# Le statut se change depuis la fiche, par qui peut modifier le compte — ce
# n'est plus réservé aux administrateurs. Trois règles le bornent, et c'est la
# troisième qui compte :
#
#   1. jamais le sien ;
#   2. jamais au-dessus de soi ;
#   3. ⚠️ le palier administrateur ne se DONNE ni ne se RETIRE que par un
#      administrateur. La règle 2 couvre le don ; c'est le RETRAIT qu'elle
#      laisse passer — sans la règle 3, un coordinateur rétrograderait un
#      administrateur puis ferait ce qu'il veut de son compte.


class TestChangerLeStatut:

    def _regle(self, app, acteur, cible, nouveau, comptes):
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import peut_changer_statut
        with app.app_context():
            return peut_changer_statut(db.session.get(User, comptes[acteur]),
                                       db.session.get(User, comptes[cible]),
                                       nouveau)

    # ── Ce que la demande ouvre ─────────────────────────────────────────
    def test_le_coordinateur_change_le_statut_d_un_collaborateur(
            self, app, table_propre, comptes):
        assert self._regle(app, "coordinateur", "user", "champion", comptes) is None

    def test_le_coordinateur_monte_quelqu_un_a_son_propre_palier(
            self, app, table_propre, comptes):
        assert self._regle(app, "coordinateur", "user", "coordinateur", comptes) is None

    # ── Le palier administrateur ────────────────────────────────────────
    def test_le_coordinateur_ne_DONNE_pas_le_palier_administrateur(
            self, app, table_propre, comptes):
        assert self._regle(app, "coordinateur", "user", "administrateur",
                           comptes) == "error_status_admin_only"

    def test_le_coordinateur_ne_RETIRE_pas_le_palier_administrateur(
            self, app, table_propre, comptes):
        """Le cas qui justifie la règle à lui seul."""
        assert self._regle(app, "coordinateur", "admin", "user",
                           comptes) == "error_status_admin_only"

    def test_l_administrateur_donne_le_palier_administrateur(
            self, app, table_propre, comptes):
        assert self._regle(app, "admin", "user", "administrateur", comptes) is None

    def test_l_administrateur_retire_le_palier_a_un_autre_administrateur(
            self, app, table_propre, comptes):
        from Code.extensions import db
        from Code.models.models import User
        from Code.security import hash_password
        with app.app_context():
            autre = User(first_name="T81", last_name="Admin2",
                         email="t81.admin2@devoptiq.com",
                         password=hash_password("Motdepasse123!"),
                         status="administrateur")
            db.session.add(autre)
            db.session.commit()
            aid = autre.id
        try:
            from Code.permissions import peut_changer_statut
            with app.app_context():
                moi = db.session.get(User, comptes["admin"])
                assert peut_changer_statut(moi, db.session.get(User, aid),
                                           "user") is None
        finally:
            with app.app_context():
                User.query.filter_by(id=aid).delete()
                db.session.commit()

    # ── Jamais le sien ──────────────────────────────────────────────────
    def test_personne_ne_change_son_PROPRE_statut(self, app, table_propre, comptes):
        """Un administrateur qui se retire son palier perd l'écran depuis
        lequel il le remettrait."""
        for qui in ("user", "champion", "coordinateur", "admin"):
            assert self._regle(app, qui, qui, "user", comptes) == "error_status_self", qui

    # ── Jamais au-dessus de soi ─────────────────────────────────────────
    def test_on_ne_monte_personne_au_dessus_de_soi(self, app, table_propre, comptes):
        assert self._regle(app, "champion", "user", "coordinateur",
                           comptes) == "error_status_too_high"

    # ── La route applique la règle ──────────────────────────────────────
    def _fiche(self, client, uid, statut, email):
        return client.post("/comptes/update/%d" % uid,
                           data={"first_name": "T81", "last_name": "Cible",
                                 "email": email, "status": statut},
                           headers={"Accept": "application/json"})

    def test_la_route_laisse_un_coordinateur_promouvoir(
            self, app, client, table_propre, comptes):
        from Code.extensions import db
        from Code.models.models import User
        _en_tant_que(client, comptes["coordinateur"], "t81.coordinateur@devoptiq.com")
        r = self._fiche(client, comptes["user"], "champion", "t81.user@devoptiq.com")
        assert r.status_code == 200, r.get_data(as_text=True)[:200]
        with app.app_context():
            from Code.permissions import famille_statut
            assert famille_statut(db.session.get(User, comptes["user"]).status) == "champion"

    def test_la_route_refuse_le_palier_administrateur_a_un_coordinateur(
            self, app, client, table_propre, comptes):
        from Code.extensions import db
        from Code.models.models import User
        _en_tant_que(client, comptes["coordinateur"], "t81.coordinateur@devoptiq.com")
        r = self._fiche(client, comptes["user"], "administrateur",
                        "t81.user@devoptiq.com")
        assert r.status_code == 403
        assert r.get_json()["code"] == "error_status_admin_only"
        # ⚠️ Et RIEN n'a été écrit — pas même le nom.
        with app.app_context():
            from Code.permissions import famille_statut
            assert famille_statut(db.session.get(User, comptes["user"]).status) == "user"

    def test_enregistrer_sans_toucher_au_statut_ne_refuse_rien(
            self, app, client, table_propre, comptes):
        """La fiche renvoie TOUJOURS le champ statut. Comparer les libellés
        ferait échouer un simple changement de nom."""
        _en_tant_que(client, comptes["coordinateur"], "t81.coordinateur@devoptiq.com")
        r = self._fiche(client, comptes["coordinateur"], "coordinateur",
                        "t81.coordinateur@devoptiq.com")
        assert r.status_code == 200, r.get_data(as_text=True)[:200]

    def test_le_libelle_d_origine_survit_quand_le_palier_ne_change_pas(
            self, app, client, table_propre, comptes):
        """« manager » est un libellé historique du palier coordinateur : le
        réenregistrer ne doit pas le réécrire en « coordinateur »."""
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            u = db.session.get(User, comptes["champion"])
            u.status = "manager"
            db.session.commit()
        _en_tant_que(client, comptes["admin"], "t81.admin@devoptiq.com")
        r = self._fiche(client, comptes["champion"], "coordinateur",
                        "t81.champion@devoptiq.com")
        assert r.status_code == 200
        with app.app_context():
            assert db.session.get(User, comptes["champion"]).status == "manager"

    # ── La colonne admin du TABLEAU DES DROITS ──────────────────────────
    def test_un_coordinateur_ne_touche_pas_la_colonne_administrateur(
            self, app, client, table_propre, comptes):
        """Demandé explicitement : la colonne `admin` du tableau des droits ne
        se règle par personne — un coordinateur ne l'écrit pas, et même un
        administrateur ne peut pas la décocher.

        ⚠️ Le verrou est tenu par DEUX mécanismes, dont le second par
        accident : `droits_effectifs` reforce la colonne à vrai, et
        `enregistrer_droits` ne stocke que les ÉCARTS au défaut — or aucune
        ligne de `DROITS_DEFAUT` ne porte de clé « admin », donc un
        `admin: False` posté est « égal au défaut » et n'est jamais écrit.
        Retirer le premier seul ne change donc RIEN, et le cliquet de ce test
        ne mord qu'en remettant AUSSI la version naïve de l'écriture (stocker
        la table telle qu'elle est demandée). C'est le piège : qui
        « simplifierait » un jour la logique des écarts déverrouillerait la
        colonne sans s'en apercevoir."""
        from Code.permissions import droits_effectifs
        with app.app_context():
            table = droits_effectifs()
        table["parametres_admin"]["admin"] = False

        _en_tant_que(client, comptes["coordinateur"], "t81.coordinateur@devoptiq.com")
        assert client.post("/comptes/droits", json={"droits": table}).status_code == 403

        _en_tant_que(client, comptes["admin"], "t81.admin@devoptiq.com")
        assert client.post("/comptes/droits", json={"droits": table}).status_code == 200
        with app.app_context():
            assert droits_effectifs()["parametres_admin"]["admin"] is True
