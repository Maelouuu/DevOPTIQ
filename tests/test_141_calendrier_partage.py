# -*- coding: utf-8 -*-
"""Le CALENDRIER PARTAGÉ — deux sources sur une même grille.

⚠️⚠️ La decision que ce fichier garde : une activite N'A PAS DE DATE. Elle a
un creneau — une recurrence et une frequence. Lui inventer un jour
fabriquerait un rendez-vous auquel personne ne s'est engage. Chaque rythme se
pose donc sur l'etendue qu'il occupe vraiment : le mois, la semaine, ou
chaque jour ouvre.
"""
import io
import json
import os

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(chemin):
    return io.open(os.path.join(RACINE, chemin), encoding="utf-8").read()


@pytest.fixture(scope="module")
def carto(app, request):
    """⚠️ SA PROPRE carto, jamais celle du decor commun. `test_14` et
    `test_15` lisent la carto de l'entite ACTIVE ; un fichier neuf qui ecrit
    dans la leur se lit en echec chez eux, sans rapport apparent.
    ⚠️ Et avec un `owner_id` : une entite de test sans proprietaire est
    lisible par TOUT LE MONDE et devient le repli des fichiers suivants."""
    from Code.models.models import Entity, User
    proprio = User.query.filter_by(email="test@devoptiq.com").first()
    e = Entity(name="CAL-141-CARTO", description="calendrier partage",
               owner_id=proprio.id if proprio else None)
    db.session.add(e)
    db.session.commit()
    eid = e.id

    def menage():
        from Code.models.models import Activities, TimeAnalysis
        for x in TimeAnalysis.query.filter(TimeAnalysis.activity_id.in_(
                [a.id for a in Activities.query.filter_by(entity_id=eid).all()]
                or [0])).all():
            db.session.delete(x)
        for a in Activities.query.filter_by(entity_id=eid).all():
            db.session.delete(a)
        db.session.delete(db.session.get(Entity, eid))
        db.session.commit()

    request.addfinalizer(menage)
    return {"entity_id": eid, "user_id": proprio.id if proprio else None}


def _activite(carto, nom):
    from Code.models.models import Activities
    a = Activities(name=nom, entity_id=carto["entity_id"])
    db.session.add(a)
    db.session.commit()
    return a


def _analyse(activite, recurrence, duree=60, freq=1, gens=1):
    from Code.models.models import TimeAnalysis
    x = TimeAnalysis(type="activity", activity_id=activite.id, duration=duree,
                     recurrence=recurrence, frequency=freq, nb_people=gens,
                     delay=None, impact_unit="minutes")
    db.session.add(x)
    db.session.commit()
    return x


@pytest.fixture(autouse=True)
def _rendre_la_session_intacte(auth_client, ids, carto):
    """⚠️ `client` est PARTAGÉ par toute la suite, et ce fichier ouvre des
    pages avec des comptes jetables. On repose la carto du décor et la langue
    après chaque cas : `auth_client` pose l'entité avec `setdefault`, donc il
    ne corrigerait pas une valeur laissée derrière — et `Entity.get_active`
    retomberait alors sur « sa première entité », qui n'est pas forcément
    celle que les fichiers suivants lisent (`test_14` lit la carto de
    l'entité ACTIVE). L'échec se lirait chez eux, sans rapport apparent."""
    from Code.models.models import Activities, Entity, Role, TimeAnalysis, User

    def photo():
        e = db.session.get(Entity, ids["entity_id"])
        return {"carto": e.optiqcarto_data, "svg": e.svg_content,
                "entites": Entity.query.count(),
                "activites": Activities.query.count(),
                "analyses": TimeAnalysis.query.count(),
                "roles": Role.query.count(), "gens": User.query.count()}

    with auth_client.session_transaction() as sess:
        langue = sess.get("lang")
        sess["active_entity_id"] = carto["entity_id"]
    avant = photo()
    yield
    with auth_client.session_transaction() as sess:
        sess["active_entity_id"] = ids["entity_id"]
        if langue is None:
            sess.pop("lang", None)
        else:
            sess["lang"] = langue
    # ⚠️ Et on le PROUVE : un reliquat de ce fichier se lirait trois fichiers
    # plus loin (`test_14` lit la carto de l'entite ACTIVE), dans un echec
    # qui ne parle ni de calendrier ni de temps.
    db.session.expire_all()
    assert photo() == avant, "ce fichier a laisse quelque chose derriere lui"


def _donnees(client):
    r = client.get("/calendrier/api/donnees")
    assert r.status_code == 200, r.data
    d = json.loads(r.data)
    assert d["ok"], d
    return d


class TestLaPorteEstFermeeAuxAutres:
    """⚠️ Premier jet : l'administrateur seul. Le masquage n'est pas une
    securite — la page redirige ET l'API refuse."""

    def test_sans_connexion_la_page_renvoie_au_login(self, app):
        anonyme = app.test_client()          # `client` est partage et connecte
        r = anonyme.get("/calendrier/")
        assert r.status_code in (301, 302)
        assert "/login" in r.headers.get("Location", "")

    def test_sans_connexion_l_api_refuse(self, app):
        anonyme = app.test_client()
        r = anonyme.get("/calendrier/api/donnees")
        assert r.status_code == 401

    def test_un_compte_ordinaire_est_refuse(self, app, ids):
        from Code.models.models import User
        from Code.security import hash_password
        u = User(first_name="Cal", last_name="Ordinaire",
                 email="cal-ordinaire@test.local",
                 password=hash_password("Test1234!"), status="user", lang="fr")
        db.session.add(u)
        db.session.commit()
        try:
            c = app.test_client()
            with c.session_transaction() as sess:
                sess["user_id"] = u.id
            assert c.get("/calendrier/api/donnees").status_code == 403
            page = c.get("/calendrier/")
            assert page.status_code in (301, 302)
            assert "/calendrier" not in page.headers.get("Location", "")
        finally:
            db.session.delete(db.session.get(User, u.id))
            db.session.commit()

    def test_un_administrateur_entre(self, auth_client):
        assert auth_client.get("/calendrier/").status_code == 200
        assert auth_client.get("/calendrier/api/donnees").status_code == 200


class TestUneActiviteNAPasDeDate:
    """Le cœur de l'ecran."""

    def test_chaque_rythme_va_dans_SON_registre(self, auth_client, carto):
        a1 = _activite(carto, "CAL-141-chaque-jour")
        a2 = _activite(carto, "CAL-141-chaque-semaine")
        a3 = _activite(carto, "CAL-141-chaque-mois")
        xs = [_analyse(a1, "journalier"), _analyse(a2, "hebdomadaire"),
              _analyse(a3, "mensuel")]
        try:
            c = _donnees(auth_client)["creneaux"]
            noms = {k: {x["activite"] for x in v} for k, v in c.items()}
            assert "CAL-141-chaque-jour" in noms["jour"]
            assert "CAL-141-chaque-semaine" in noms["semaine"]
            assert "CAL-141-chaque-mois" in noms["mois"]
            # ⚠️ Et une seule fois : un creneau posé dans deux registres se
            # compterait deux fois dans la charge.
            for k in ("semaine", "mois"):
                assert "CAL-141-chaque-jour" not in noms[k], k
        finally:
            for x in xs:
                db.session.delete(x)
            for a in (a1, a2, a3):
                db.session.delete(a)
            db.session.commit()

    def test_le_trimestriel_et_l_annuel_vont_dans_la_bande_du_MOIS(self, auth_client, carto):
        """Ils reviennent trop rarement pour une bande de semaine, et ils
        n'ont pas plus de jour que les autres."""
        a = _activite(carto, "CAL-141-rare")
        xs = [_analyse(a, "trimestriel"), _analyse(a, "annuel")]
        try:
            c = _donnees(auth_client)["creneaux"]
            rythmes = {x["recurrence"] for x in c["mois"]}
            assert {"trimestriel", "annuel"} <= rythmes, rythmes
        finally:
            for x in xs:
                db.session.delete(x)
            db.session.delete(a)
            db.session.commit()

    def test_une_recurrence_INCONNUE_ne_se_pose_pas_sur_chaque_jour(self, auth_client, carto):
        """⚠️ La poser sur chaque jour ouvre multiplierait par vingt une
        charge dont on ne sait rien. Elle tombe dans la bande du mois."""
        a = _activite(carto, "CAL-141-lunaire")
        x = _analyse(a, "lunaire")
        try:
            c = _donnees(auth_client)["creneaux"]
            assert "CAL-141-lunaire" not in {y["activite"] for y in c["jour"]}
            assert "CAL-141-lunaire" in {y["activite"] for y in c["mois"]}
        finally:
            db.session.delete(x)
            db.session.delete(a)
            db.session.commit()

    def test_les_minutes_sont_la_MEME_expression_que_le_tableau_de_bord(self, auth_client, carto):
        """Duree x frequence x personnes, pour UNE occurrence de la periode.
        Deux expressions finiraient par donner deux chiffres de la meme
        chose — c'est le defaut que `dashboard_rows` a deja montre."""
        a = _activite(carto, "CAL-141-mesure")
        x = _analyse(a, "hebdomadaire", duree=45, freq=3, gens=2)
        try:
            c = _donnees(auth_client)["creneaux"]["semaine"]
            vu = [y for y in c if y["activite"] == "CAL-141-mesure"][0]
            assert vu["minutes"] == pytest.approx(45 * 3 * 2)
            tdb = json.loads(auth_client.get("/temps/api/tableau_de_bord").data)
            meme = [y for y in tdb["par_activite"] if y["id"] == x.id][0]
            assert vu["minutes"] == pytest.approx(meme["par_periode_min"])
        finally:
            db.session.delete(x)
            db.session.delete(a)
            db.session.commit()


class TestCeQueLEcranNePeutPasFaire:

    def test_aucun_creneau_ne_recoit_de_DATE(self, auth_client, carto):
        """Le serveur ne rend jamais de date pour une activite : il n'en a
        aucune a rendre, et une date inventee serait un rendez-vous."""
        a = _activite(carto, "CAL-141-sans-date")
        x = _analyse(a, "journalier")
        try:
            c = _donnees(auth_client)["creneaux"]
            for registre in c.values():
                for y in registre:
                    assert "date" not in y, y
                    assert "date_prevue" not in y, y
                    assert "jour" not in y, y
        finally:
            db.session.delete(x)
            db.session.delete(a)
            db.session.commit()

    def test_le_JS_ne_pose_un_creneau_que_sur_une_BANDE(self):
        js = _lire("static/js/calendrier.js")
        # Les pastilles de creneau ne se construisent que dans les deux bandes.
        assert js.count("pastille)") == 2, "une bande du mois, une de semaine"
        # Et la case d'un jour ne porte que la CHARGE, jamais un nom.
        bloc = js[js.index("for (var j = 1; j <= nJours"):][:1400]
        assert "pastille" not in bloc, bloc

    def test_la_charge_ne_se_met_QUE_sur_un_jour_ouvre(self):
        """Les activites journalieres se comptent en jours travailles —
        c'est la regle de toute la page Temps."""
        js = _lire("static/js/calendrier.js")
        assert "if (!we && chargeJour > 0)" in js


class TestLesTroisNiveauxDeFiltre:

    def test_les_trois_niveaux_existent_et_un_seul_est_actif(self):
        js = _lire("static/js/calendrier.js")
        for n in ("'tout'", "'role'", "'personne'"):
            assert n in js, n
        # ⚠️ On choisit d'office le premier : « par role » sans role choisi
        # n'afficherait rien, et l'ecran paraitrait casse.
        assert "if (etat.portee === 'role' && !etat.roleId" in js
        assert "if (etat.portee === 'personne' && !etat.userId" in js

    def test_un_creneau_suit_les_ROLES_qui_tiennent_son_activite(self, auth_client, carto):
        from Code.models.models import Role, activity_roles
        a = _activite(carto, "CAL-141-portee")
        r = Role(name="CAL-141-role", entity_id=carto["entity_id"])
        db.session.add(r)
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=a.id, role_id=r.id, status="Garant"))
        db.session.commit()
        x = _analyse(a, "mensuel")
        try:
            d = _donnees(auth_client)
            vu = [y for y in d["creneaux"]["mois"]
                  if y["activite"] == "CAL-141-portee"][0]
            assert r.id in vu["roles"]
            assert r.id in {z["id"] for z in d["roles"]}
        finally:
            db.session.execute(activity_roles.delete().where(
                activity_roles.c.role_id == r.id))
            db.session.delete(x)
            db.session.delete(db.session.get(Role, r.id))
            db.session.delete(a)
            db.session.commit()

    def test_le_cout_ne_grandit_pas_avec_le_nombre_d_activites(self, app, auth_client, carto):
        """⚠️ Trois requetes pour toute la carto, jamais une par activite :
        cet ecran s'ouvre d'un clic et une carto en porte des centaines."""
        from sqlalchemy import event

        def compter():
            n = [0]

            def vu(*_a, **_k):
                n[0] += 1
            event.listen(db.engine, "before_cursor_execute", vu)
            try:
                _donnees(auth_client)
            finally:
                event.remove(db.engine, "before_cursor_execute", vu)
            return n[0]

        # ⚠️ Le repere se prend sur une carto qui porte DEJA une activite :
        # mesure depuis une carto vide, on compterait le cout FIXE qui
        # apparait (`_qui_tient_quoi` sort tout de suite sans activite), et
        # le cas accuserait un cout par activite qui n'existe pas.
        faits = []
        temoin = _activite(carto, "CAL-141-cout-temoin")
        faits.append((temoin, _analyse(temoin, "mensuel")))
        try:
            avant = compter()
            for i in range(6):
                a = _activite(carto, "CAL-141-cout-%d" % i)
                faits.append((a, _analyse(a, "mensuel")))
            apres = compter()
            assert apres == avant, (avant, apres)
        finally:
            for a, x in faits:
                db.session.delete(x)
                db.session.delete(a)
            db.session.commit()


class TestLesTroisPortes:

    def test_elles_ne_se_rendent_QUE_pour_qui_peut_ouvrir(self):
        """⚠️ Le MEME verdict que la route (`calendrier_ouvert`) : un bouton
        ne doit jamais mener a un ecran qui refuse."""
        for gab in ("time_dashboard.html", "competences_view.html",
                    "welcome_popup.html"):
            g = _lire("Code/routes/templates/" + gab)
            assert "/calendrier/" in g, gab
            i = g.index("/calendrier/")
            assert "calendrier_ouvert" in g[max(0, i - 700):i], gab

    def test_un_compte_ordinaire_ne_voit_AUCUNE_porte(self, app, ids):
        """Le gabarit et la route disent la même chose — vérifié sur le RENDU,
        pas sur le texte du gabarit : c'est le seul moyen de savoir que la
        condition porte bien sur le lien."""
        from Code.models.models import User
        from Code.security import hash_password
        u = User(first_name="Cal", last_name="SansPorte",
                 email="cal-sansporte@test.local",
                 password=hash_password("Test1234!"), status="user", lang="fr")
        db.session.add(u)
        db.session.commit()
        try:
            c = app.test_client()
            with c.session_transaction() as sess:
                sess["user_id"] = u.id
            for url in ("/temps/", "/competences/view"):
                page = c.get(url)
                assert page.status_code == 200, (url, page.status_code)
                assert b"/calendrier/" not in page.data, url
        finally:
            db.session.delete(db.session.get(User, u.id))
            db.session.commit()

    def test_un_administrateur_les_voit_TOUTES(self, auth_client):
        for url, attendu in (("/temps/", b'/calendrier/?de=temps'),
                             ("/competences/view", b'/calendrier/?de=comp')):
            page = auth_client.get(url)
            assert page.status_code == 200, url
            assert attendu in page.data, url
        # La fenêtre de bienvenue est incluse partout : sa porte aussi.
        assert b'class="wp-cal"' in auth_client.get("/temps/").data

    def test_la_source_par_defaut_depend_de_la_PORTE(self):
        """Entre depuis la page Temps, on ne veut voir QUE le temps ; depuis
        les Competences, QUE les seances. Sans parametre, les deux."""
        assert "/calendrier/?de=temps" in _lire(
            "Code/routes/templates/time_dashboard.html")
        assert "/calendrier/?de=comp" in _lire(
            "Code/routes/templates/competences_view.html")
        js = _lire("static/js/calendrier.js")
        assert "if (de === 'temps') { etat.temps = true; etat.comp = false; }" in js
        assert "else if (de === 'comp') { etat.temps = false; etat.comp = true; }" in js

    def test_la_PORTE_et_la_ROUTE_disent_la_meme_chose(self, app, auth_client, ids):
        """Trois gabarits et une route : une seconde regle finirait par
        s'ecarter de la premiere.

        ⚠️ Sur le COMPORTEMENT, jamais en relisant `Code/app.py` : l'arbre
        d'image est compile en bytecode, et un cas qui lit une source y
        rougit a chaque execution."""
        from Code.models.models import User
        from Code.security import hash_password

        # L'administrateur : la porte s'affiche ET la route s'ouvre.
        assert b"/calendrier/" in auth_client.get("/temps/").data
        assert auth_client.get("/calendrier/api/donnees").status_code == 200

        u = User(first_name="Cal", last_name="Accord",
                 email="cal-accord@test.local",
                 password=hash_password("Test1234!"), status="champion", lang="fr")
        db.session.add(u)
        db.session.commit()
        try:
            c = app.test_client()
            with c.session_transaction() as sess:
                sess["user_id"] = u.id
            # Pas de porte, et pas de route : les deux vont ensemble.
            assert b"/calendrier/" not in c.get("/temps/").data
            assert c.get("/calendrier/api/donnees").status_code == 403
        finally:
            db.session.delete(db.session.get(User, u.id))
            db.session.commit()


class TestLesDeuxLangues:

    def test_toute_clef_lue_par_le_JS_est_injectee_et_traduite(self):
        import re
        from Code.translations import TRANSLATIONS
        js = _lire("static/js/calendrier.js")
        gab = _lire("Code/routes/templates/calendrier.html")
        injectees = set(re.findall(r"^\s*(\w+):\s*\{\{", gab, re.M)) - {"lang"}
        assert len(injectees) >= 30, injectees
        # ⚠️ TOUTE chaine du JS qui porte le nom d'une clef, pas seulement
        # `T('x')` : sept libelles de jour, trois niveaux de portee et les
        # deux sources sont lus depuis des TABLEAUX. Une recherche limitee
        # aux appels directs les croirait morts, et l'ecran afficherait la
        # CLEF BRUTE — l'accesseur rend la clef quand elle manque, il ne leve
        # rien. C'est le defaut deja paye sur la page Temps.
        # ⚠️ Les clefs LUES se reconnaissent au CATALOGUE, jamais aux
        # injections : en les croisant avec les injections, retirer une
        # injection la faisait sortir des deux ensembles d'un coup, et le cas
        # restait vert sur le defaut meme qu'il garde.
        connues = {k[len("cal."):] for k in TRANSLATIONS["fr"]
                   if k.startswith("cal.")}
        chaines = set(re.findall(r"'([a-z0-9_]+)'", js))
        lues = chaines & connues
        lues |= set(re.findall(r"T\('([a-z0-9_]+)'\)", js))
        lues |= set(re.findall(r"phrase\('([a-z0-9_]+)'", js))
        assert len(lues) >= 30, sorted(lues)
        manquantes = lues - injectees
        assert not manquantes, manquantes
        # Et dans l'autre sens : pas d'injection morte.
        assert not (injectees - lues), sorted(injectees - lues)
        for cle in injectees:
            for lg in ("fr", "en"):
                assert TRANSLATIONS[lg].get("cal." + cle), (lg, cle)

    def test_le_titre_de_la_page_existe_dans_les_deux_langues(self):
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            assert TRANSLATIONS[lg].get("page.calendrier"), lg

    def test_la_page_se_rend_en_ANGLAIS_sans_fuite(self, auth_client):
        from Code.translations import TRANSLATIONS
        with auth_client.session_transaction() as sess:
            avant = sess.get("lang")
            sess["lang"] = "en"
        try:
            page = auth_client.get("/calendrier/").data.decode("utf-8")
            for cle, fr in TRANSLATIONS["fr"].items():
                if not cle.startswith("cal."):
                    continue
                en = TRANSLATIONS["en"].get(cle)
                if not en or en == fr or len(fr) < 12:
                    continue
                assert fr not in page, (cle, fr[:50])
        finally:
            # ⚠️ `client` est partage : une langue laissee a « en » changerait
            # les messages que les fichiers suivants comparent.
            with auth_client.session_transaction() as sess:
                if avant is None:
                    sess.pop("lang", None)
                else:
                    sess["lang"] = avant
