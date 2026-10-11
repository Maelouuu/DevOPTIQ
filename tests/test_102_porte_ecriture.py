# -*- coding: utf-8 -*-
"""La porte d'écriture : qui peut écrire, et qui ne peut pas.

Relevé le 11/10/2026 : **39 fichiers de routes portaient des écritures et
AUCUN contrôle d'accès**. Mesuré, porte retirée :

  * un compte `user` créait une tâche, réécrivait la description d'un outil du
    catalogue partagé et pouvait remplacer le fichier de référence DCP ;
  * `POST /tasks/add` **sans aucun compte** rendait 201 et écrivait la tâche.

Le tableau des droits disait pourtant depuis le début que `user` consulte et
ne modifie rien. Ce fichier tient la porte qui le fait respecter.

⚠️ Il appelle `porte()` DIRECTEMENT, avec `en_test=False`. C'est voulu : sous
TESTING la règle anonyme s'efface (115 tests fabriquent des clients anonymes
pour s'isoler de la session partagée, pas pour éprouver l'anonymat). Passer la
suite ne prouve donc PAS que l'anonyme est fermé — seul ce fichier le prouve.
"""
import pytest

from Code.ecriture import DROIT_ECRITURE, METHODES_ECRITURE, TOUT_COMPTE, porte
from Code.extensions import db


@pytest.fixture()
def comptes(app):
    """Un compte par palier, plus l'entité de test."""
    from Code.models.models import User
    from Code.security import hash_password

    faits = {}
    with app.app_context():
        for palier, statut in (("user", "user"), ("champion", "champion"),
                               ("coord", "coordinateur"), ("admin", "admin")):
            mail = "t102.%s@devoptiq.com" % palier
            u = User.query.filter_by(email=mail).first()
            if not u:
                u = User(first_name="T102", last_name=palier, email=mail,
                         password=hash_password("Motdepasse123!"), status=statut)
                db.session.add(u)
                db.session.flush()
            faits[palier] = u.id
        db.session.commit()
    yield faits
    with app.app_context():
        from Code.models.models import User
        User.query.filter(User.email.like("t102.%")).delete(synchronize_session=False)
        db.session.commit()


def _en_session(app, uid):
    """Un contexte de requête où `current_user()` rend ce compte."""
    from flask import session
    ctx = app.test_request_context("/")
    ctx.push()
    session["user_id"] = uid
    return ctx


class TestCeQueLaPorteRefuse:

    @pytest.mark.parametrize("chemin,methode", [
        ("/tasks/add", "POST"),
        ("/tasks/update/1", "POST"),
        ("/gestion_outils/api/tools/1", "PUT"),
        ("/savoirs/add", "POST"),
        ("/savoir_faires/add", "POST"),
        ("/aptitudes/add", "POST"),
        ("/softskills/add", "POST"),
        ("/roles/add", "POST"),
        ("/constraints/add", "POST"),
        ("/propose_from_file/upload_ref", "POST"),
        ("/temps/api/project", "POST"),
    ])
    def test_un_compte_user_n_ecrit_pas(self, app, comptes, chemin, methode):
        """R01 / R02 de l'audit : IA User a créé une tâche et réécrit la
        description de Pathfinder. C'est exactement ce qui est refusé ici."""
        ctx = _en_session(app, comptes["user"])
        try:
            assert porte(chemin, methode) == "lecture_seule", chemin
        finally:
            ctx.pop()

    def test_un_champion_non_plus(self, app, comptes):
        """Le champion PROPOSE une modification de carto ; il n'écrit pas les
        données directement. C'est la règle du tableau des droits."""
        ctx = _en_session(app, comptes["champion"])
        try:
            assert porte("/tasks/add", "POST") == "lecture_seule"
        finally:
            ctx.pop()

    def test_sans_aucun_compte_non_plus(self, app):
        """⚠️ Mesuré avant la porte : `POST /tasks/add` sans compte rendait
        201 et écrivait la tâche en base. C'est pire que le défaut signalé par
        l'audit, et ça ne se voyait nulle part."""
        ctx = app.test_request_context("/")
        ctx.push()
        try:
            assert porte("/tasks/add", "POST", en_test=False) == "non_connecte"
        finally:
            ctx.pop()

    def test_mais_la_suite_laisse_passer_l_anonyme(self, app):
        """⚠️ Le contrepoids, écrit noir sur blanc : sous TESTING la règle
        anonyme s'efface. Si ce test tombe un jour, c'est que la suite peut
        enfin l'assumer — et la dérogation doit disparaître avec lui."""
        ctx = app.test_request_context("/")
        ctx.push()
        try:
            assert porte("/tasks/add", "POST", en_test=True) is None
        finally:
            ctx.pop()


class TestCeQueLaPorteLaissePasser:

    @pytest.mark.parametrize("palier", ["coord", "admin"])
    def test_coordinateur_et_admin_ecrivent(self, app, comptes, palier):
        ctx = _en_session(app, comptes[palier])
        try:
            assert porte("/tasks/add", "POST") is None
        finally:
            ctx.pop()

    def test_la_lecture_n_est_jamais_gardee(self, app, comptes):
        """Un `user` consulte tout ce qu'il a le droit d'ouvrir : la porte ne
        regarde QUE les méthodes d'écriture."""
        ctx = _en_session(app, comptes["user"])
        try:
            for methode in ("GET", "HEAD", "OPTIONS"):
                assert porte("/tasks/add", methode) is None, methode
        finally:
            ctx.pop()

    @pytest.mark.parametrize("prefixe", sorted(TOUT_COMPTE))
    def test_les_exemptions_sont_effectives(self, app, comptes, prefixe):
        """⚠️ Chaque exemption nomme la garde qui prend le relais — la porte
        s'efface devant une règle PLUS FINE, elle ne la remplace pas."""
        ctx = _en_session(app, comptes["user"])
        try:
            assert porte(prefixe + "/x", "POST") is None, prefixe
        finally:
            ctx.pop()

    def test_se_connecter_ne_demande_pas_d_etre_connecte(self, app):
        ctx = app.test_request_context("/")
        ctx.push()
        try:
            for chemin in ("/login", "/logout", "/reset/x", "/pulse/beat"):
                assert porte(chemin, "POST", en_test=False) is None, chemin
        finally:
            ctx.pop()


class TestLaFormeDeLaPorte:

    def test_elle_garde_les_quatre_methodes_d_ecriture(self):
        assert METHODES_ECRITURE == {"POST", "PUT", "PATCH", "DELETE"}

    def test_elle_s_appuie_sur_le_tableau_des_droits(self):
        """⚠️ Pas une liste de statuts en dur : le droit se règle depuis la
        page Comptes, et la porte doit suivre ce réglage."""
        from Code.permissions import DROITS_DEFAUT
        assert DROIT_ECRITURE in DROITS_DEFAUT

    def test_elle_est_branchee_une_fois_pour_toute_l_application(self, app):
        """⚠️ Une garde par route laisserait la PROCHAINE route écrite
        ouverte — c'est exactement comme ça que 39 fichiers le sont devenus.

        On regarde le CÂBLAGE, pas le texte de `app.py` : l'arbre d'image est
        en bytecode seul, un test qui lit une source y échoue toujours.
        """
        poses = [f.__name__ for f in app.before_request_funcs.get(None, [])]
        assert poses.count("_porte_ecriture") == 1, poses
