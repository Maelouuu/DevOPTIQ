# -*- coding: utf-8 -*-
"""Pages Compétences et Gestion RH : ce qui restait en français en anglais.

Les catalogues étaient complets (`test_78` le tient) : chaque clé existe dans
les deux langues. Ce qui passait à travers, c'est tout ce qui NE passe PAS par
une clé :

* le rôle système « Développeur de compétences », créé en français pour chaque
  entité et affiché tel quel dans les listes de rôles ;
* la compétence principale, que l'IA rédige dans les deux langues mais dont on
  ne gardait qu'une version ;
* la ponctuation française (« Libellé : valeur ») écrite dans le JS, et
  l'abréviation « S » de semaine ;
* des attributs d'accessibilité et le <title> de la page, écrits en dur.
"""
import json
import os
import re

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(*chemin):
    with open(os.path.join(RACINE, *chemin), encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def scene(app):
    """Un coordinateur, une entité, un rôle ordinaire, une activité reliée."""
    from Code.models.models import Activities, Entity, Role, User, activity_roles
    from Code.security import hash_password
    with app.app_context():
        u = User(first_name="T82", last_name="Coord", email="t82.coord@devoptiq.com",
                 password=hash_password("Motdepasse123!"), status="coordinateur")
        db.session.add(u)
        db.session.flush()
        e = Entity(name="T82 Carto", owner_id=u.id)
        db.session.add(e)
        db.session.flush()
        r = Role(name="Chargé d'affaires T82", entity_id=e.id)
        a = Activities(name="Chiffrer T82", entity_id=e.id, shape_id="t82_a")
        db.session.add_all([r, a])
        db.session.flush()
        db.session.execute(activity_roles.insert().values(activity_id=a.id, role_id=r.id,
                                                          status="Garant"))
        db.session.commit()
        ids = {"user": u.id, "entity": e.id, "role": r.id, "activity": a.id}
    yield ids
    with app.app_context():
        from Code.models.models import Competency, EntityRoleAccess, UserRole
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.activity_id == ids["activity"]))
        Competency.query.filter_by(activity_id=ids["activity"]).delete()
        roles = [x.id for x in Role.query.filter_by(entity_id=ids["entity"]).all()]
        EntityRoleAccess.query.filter(EntityRoleAccess.role_id.in_(roles or [-1])).delete(
            synchronize_session=False)
        UserRole.query.filter(UserRole.role_id.in_(roles or [-1])).delete(
            synchronize_session=False)
        Role.query.filter_by(entity_id=ids["entity"]).delete()
        Activities.query.filter_by(id=ids["activity"]).delete()
        Entity.query.filter_by(id=ids["entity"]).delete()
        User.query.filter_by(id=ids["user"]).delete()
        db.session.commit()


def _connecte(client, app, uid, lang):
    from Code.models.models import User
    with app.app_context():
        mail = db.session.get(User, uid).email
    with client.session_transaction() as s:
        s.clear()
        s["user_id"] = uid
        s["user_email"] = mail
        s["lang"] = lang


# ══════════════════════════════════════════════════════════════════════
#  Le rôle système se traduit ; les autres suivent la page Rôles
# ══════════════════════════════════════════════════════════════════════
class TestLeRoleSystemeSeTraduit:

    def test_le_developpeur_de_competences_vient_du_catalogue(self, app):
        from Code.models.models import Role
        from Code.role_i18n import nom_affiche
        with app.app_context():
            r = Role(name="Développeur de compétences")
            assert nom_affiche(r, "en") == "Competency developer"
            assert nom_affiche(r, "fr") == "Développeur de compétences"
            # ⚠️ les anciens libellés désignent le même rôle
            assert nom_affiche(Role(name="manager"), "en") == "Competency developer"

    def test_un_role_metier_prend_la_traduction_en_cache_sans_appeler_l_IA(self, app):
        from Code.models.models import Role
        from Code.role_i18n import nom_affiche
        with app.app_context():
            assert nom_affiche(Role(name="Qualité", name_en="Quality"), "en") == "Quality"
            # pas de cache : le nom d'origine, jamais un texte inventé
            assert nom_affiche(Role(name="Qualité"), "en") == "Qualité"

    def test_la_page_RH_anglaise_n_affiche_plus_le_role_en_francais(self, app, client, scene):
        """Vérifié ROUGE sur le code d'avant : « Développeur de compétences »
        sortait tel quel dans la liste des rôles de la page anglaise."""
        _connecte(client, app, scene["user"], "en")
        d = client.get(f"/gestion_rh/api/tableau?entity_id={scene['entity']}").get_json()
        systeme = [r for r in d["roles"] if r["permanent"]]
        assert systeme, "le rôle système est créé à l'affichage"
        assert systeme[0]["name"] == "Competency developer"
        assert all("Développeur" not in r["name"] for r in d["roles"])


# ══════════════════════════════════════════════════════════════════════
#  La compétence principale, dans les deux langues
# ══════════════════════════════════════════════════════════════════════
class TestLaCompetenceDansLesDeuxLangues:

    def test_les_deux_versions_sont_gardees_et_chacun_lit_la_sienne(self, app, client, scene):
        """Vérifié ROUGE sur le code d'avant : on ne gardait que la version
        de la personne qui configurait."""
        from Code.routes.mastery import dashboard_rows
        _connecte(client, app, scene["user"], "fr")
        r = client.post(f"/competence/save/{scene['activity']}", data=json.dumps({
            "description": "Chiffrer une offre complète.",
            "description_fr": "Chiffrer une offre complète.",
            "description_en": "Price a complete offer."}), content_type="application/json")
        assert r.status_code == 200
        for lang, attendu in (("fr", "Chiffrer une offre complète."),
                              ("en", "Price a complete offer.")):
            with app.test_request_context():
                from flask import session
                session["lang"] = lang
                ligne = next(x for x in dashboard_rows(scene["user"], scene["role"])
                             if x["activity_id"] == scene["activity"])
                assert ligne["competence"] == attendu, lang

    def test_une_competence_d_avant_s_affiche_telle_quelle(self, app, scene):
        """Pas de version par langue (saisie à la main, ou configurée avant ce
        correctif) : on montre l'originale plutôt que rien."""
        from Code.models.models import Competency
        with app.app_context():
            c = Competency(activity_id=scene["activity"], description="Texte d'origine")
            assert c.texte("en") == "Texte d'origine"
            assert c.texte("fr") == "Texte d'origine"


# ══════════════════════════════════════════════════════════════════════
#  Ce qui s'écrit dans le code et échappe au catalogue
# ══════════════════════════════════════════════════════════════════════
JS = ("static/js/competences_v2.js", "static/js/gestion_rh.js")


class TestLaTypographieSuitLaLangue:

    @pytest.mark.parametrize("fichier", JS)
    def test_pas_de_deux_points_a_la_francaise_ecrits_en_dur(self, fichier):
        """« Minimum standard : … » dans une page anglaise : l'espace avant les
        deux-points est une règle FRANÇAISE. Le séparateur suit la langue."""
        src = _lire(*fichier.split("/"))
        fautes = re.findall(r"\)\}\s:\s\$\{", src)
        assert not fautes, f"{fichier} : {len(fautes)} « : » écrits en dur"

    def test_l_abreviation_de_semaine_suit_la_langue(self):
        """« S1 » pour « semaine 1 » n'a pas de sens en anglais (« W1 »)."""
        assert "`S${i + 1}" not in _lire("static", "js", "competences_v2.js")


GABARITS = ("competences_view.html", "gestion_rh.html", "header_buttons.html")


class TestLesAttributsSontTraduits:

    @pytest.mark.parametrize("gabarit", GABARITS)
    def test_aucun_libelle_d_accessibilite_ecrit_en_dur(self, gabarit):
        """Les lecteurs d'écran lisaient « Fermer », « Ouvrir le menu »,
        « Navigation principale » dans l'interface anglaise. Invisible à l'œil,
        donc invisible aux contrôles qui ne regardent que le texte."""
        src = _lire("Code", "routes", "templates", gabarit)
        en_dur = [m.group(0) for m in re.finditer(
            r'\b(aria-label|title|placeholder|alt)="([^"{]*)"', src)
            if re.search(r"[A-Za-zÀ-ÿ]{3,}", m.group(2)) and m.group(2) != "OPTIQ"]
        assert not en_dur, en_dur

    def test_le_titre_de_l_onglet_suit_la_langue(self):
        """L'onglet disait « OPTIQ — Compétences » dans l'interface anglaise."""
        titre = re.search(r"<title>(.*?)</title>",
                          _lire("Code", "routes", "templates", "competences_view.html"))
        assert titre and "{{ t(" in titre.group(1)
