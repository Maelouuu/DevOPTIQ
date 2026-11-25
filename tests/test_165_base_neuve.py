# -*- coding: utf-8 -*-
"""Une base NEUVE : le scenario du client le jour 1.

Mesure d'avant, sur un vrai PostgreSQL 16 vierge monte par le demarrage
NORMAL de l'application : sur les 104 routes GET sans parametre, DEUX
rendaient 500 — et aucune des 5176 lignes de la suite ne pouvait les voir,
parce que la suite tourne sur SQLite.

  1. `/temps/api/tableau_de_bord` : `get_calendar_params` ne trouve pas de
     ligne `entreprise_settings` (base neuve), retombe sur
     `get_company_params`, dont le SELECT sur `company_params` echoue — la
     table n'a AUCUN modele, rien ne la cree. Le `except: pass` ne reparait
     pas la transaction, et sur PostgreSQL un ordre rate AVORTE TOUTE LA
     TRANSACTION : la requete suivante de la MEME requete HTTP tombait.
     Mesure : SQLite, lui, SURVIT au SELECT rate. D'ou le silence de la suite.

  2. `/performance_perso/*` : une DDL ecrite en SQLite PUR (`AUTOINCREMENT`,
     `datetime('now')`) en tete de six des sept routes du blueprint.
     `test_67_schema_postgres` compile le DDL des MODELES avec le dialecte
     PostgreSQL ; une chaine brute dans une route lui echappe.
"""
import io
import os
import re

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


#     ⚠️ L'image client est compilee en bytecode (`compileall -b` puis les `.py`
# supprimes) : un cas qui relit une SOURCE y rougit a chaque execution, et un
# controle qui rougit toujours n'est plus lu — le jour ou il a raison, personne
# ne regarde. Les deux balayages de ce fichier portent donc un GARDE-FOU DE
# VOLUME : sous 40 sources lues, ils sautent franchement au lieu de verdir en
# ne lisant rien. Tout le reste est comportemental, donc portable.
def _sans_commentaires(src):
    """⚠️ Neuvieme fois que ce piege se presente : un controle qui cherche une
    chaine s'attrape sur le COMMENTAIRE qui l'explique."""
    return re.sub(r"^\s*#.*$", "", src, flags=re.M)


class TestLaSondeDuCalendrierNeTouchePasLaSession:
    """⚠️ Ce cas attrape les DEUX fausses pistes autant que le defaut d'origine.

    `db.session.rollback()` dans le `except` repare la transaction, mais jette
    le travail en attente de l'appelant — et `get_calendar_params` est appele
    depuis des routes qui ECRIVENT. `db.session.begin_nested()` (SAVEPOINT)
    a l'air de regler ca et ne le regle PAS : il FLUSHE la session avant de
    poser le point de reprise, donc le travail en attente part DANS le
    savepoint et le rollback l'emporte. Mesure : l'objet ajoute juste avant
    disparaissait de `session.new`.
    """

    def test_le_travail_en_attente_de_l_appelant_SURVIT(self, app):
        from Code.models.models import Entity
        from Code.routes.time_view import get_company_params
        with app.app_context():
            temoin = Entity(name="temoin-sonde-calendrier-165")
            db.session.add(temoin)
            try:
                get_company_params()
                reste = [o for o in db.session.new
                         if getattr(o, "name", None) == "temoin-sonde-calendrier-165"]
                assert reste, (
                    "la sonde du calendrier a JETE le travail en attente de "
                    "l'appelant : elle doit tourner sur une connexion A PART, "
                    "jamais sur la session ORM")
            finally:
                # ⚠️ On retire MON temoin, on ne rollback PAS : la session est
                # partagee par toute la suite (portee session dans conftest), et
                # un rollback sec jetterait le travail en attente d'un autre
                # fichier — l'echec se lirait trois fichiers plus loin.
                if temoin in db.session:
                    db.session.expunge(temoin)

    def test_la_sonde_n_emet_NI_savepoint_NI_rollback(self, app):
        """Un SAVEPOINT trahit un `begin_nested` ; un ROLLBACK, un `except`
        qui repare la session. Ni l'un ni l'autre n'a sa place ici."""
        from sqlalchemy import event
        from Code.routes.time_view import get_company_params
        with app.app_context():
            vus = []

            @event.listens_for(db.engine, "after_cursor_execute")
            def _note(conn, cur, stmt, params, ctx, many):
                s = (stmt or "").strip().upper()
                if s.startswith(("SAVEPOINT", "RELEASE SAVEPOINT",
                                 "ROLLBACK TO SAVEPOINT")):
                    vus.append(s[:40])

            try:
                get_company_params()
            finally:
                event.remove(db.engine, "after_cursor_execute", _note)
            assert vus == [], "la sonde touche a la transaction : %s" % vus

    def test_la_sonde_ouvre_SA_PROPRE_connexion(self, app):
        """⚠️ Le seul cas qui tombe sur les TROIS versions fautives.

        Le defaut d'ORIGINE — `db.session.execute` plus un `except: pass` —
        est INVISIBLE sur SQLite : la session y survit au SELECT rate (mesure).
        Aucun cas comportemental ne peut donc le reproduire dans cette suite.
        Ce qu'on garde a la place, c'est l'INVARIANT qui le ferme : la sonde ne
        touche pas a la session, elle ouvre sa propre connexion. Une table
        sondee par requete, donc deux ouvertures.
        """
        from Code.routes import time_view
        with app.app_context():
            vrai = db.engine.connect
            compte = {"n": 0}

            def espion(*a, **k):
                compte["n"] += 1
                return vrai(*a, **k)

            # On remplace sur l'objet Engine, pas sur le proxy : c'est lui que
            # la sonde appelle.
            db.engine.connect = espion
            try:
                time_view.get_company_params()
            finally:
                try:
                    del db.engine.connect
                except AttributeError:
                    db.engine.connect = vrai
            assert compte["n"] >= len(time_view._SONDES_CALENDRIER), (
                "la sonde n'a ouvert que %d connexion(s) pour %d tables : elle "
                "passe par la session ORM, et sur PostgreSQL un SELECT rate y "
                "avorte TOUTE la transaction"
                % (compte["n"], len(time_view._SONDES_CALENDRIER)))

    def test_elle_rend_bien_le_repli_quand_les_tables_manquent(self, app):
        """Les deux tables sondees n'ont AUCUN modele : rien ne les cree, et
        c'est normal. La fonction doit rendre ses valeurs par defaut."""
        from Code.routes.time_view import get_company_params
        with app.app_context():
            assert get_company_params() == {"Js": 5, "Sa": 47, "Ja": 220}


class TestLeTableauDeBordRepondSurUneBaseNEUVE:
    """⚠️ Ce cas ne reproduit PAS le poison — sur SQLite la session survit au
    SELECT rate. Il garde le CHEMIN de l'installation neuve : le tableau de
    bord doit repondre sans aucun calendrier enregistre."""

    def test_sans_calendrier_enregistre_il_rend_200(self, auth_client, app):
        from Code.models.models import EntrepriseSettings
        with app.app_context():
            n = EntrepriseSettings.query.count()
        rep = auth_client.get("/temps/api/tableau_de_bord")
        assert rep.status_code == 200, (
            "le tableau de bord tombe (%s lignes entreprise_settings en base)"
            % n)
        j = rep.get_json()
        assert "calendrier" in j and "charge" in j


class TestAucuneDDLBruteNEstEcriteEnSQLitePur:
    """La DDL de l'historique des performances tournait en 500 sur PostgreSQL
    depuis toujours, sur les deux instances, et la suite ne pouvait pas le
    voir : sur SQLite cette syntaxe est VALIDE."""

    def test_la_DDL_de_l_historique_suit_le_dialecte(self, app):
        """Comportemental, donc portable : on capte l'ordre REELLEMENT emis
        avec le dialecte PostgreSQL annonce, et on y cherche la syntaxe que
        PostgreSQL refuse."""
        from Code.routes import performance_personnalisee as pp
        vus = []
        vrai_execute = db.session.execute
        vrai_dialecte = pp._dialecte_postgres
        with app.app_context():
            try:
                pp._dialecte_postgres = lambda: True
                db.session.execute = lambda sql, *a, **k: vus.append(str(sql)) or None
                pp.ensure_history_schema()
            finally:
                db.session.execute = vrai_execute
                pp._dialecte_postgres = vrai_dialecte
        assert vus, "aucun ordre emis : le cas ne verifie rien"
        ddl = vus[0].upper()
        assert "AUTOINCREMENT" not in ddl, (
            "PostgreSQL refuse AUTOINCREMENT — c'est le 500 d'origine")
        assert "DATETIME('NOW')" not in ddl, (
            "datetime('now') est une fonction SQLite ; PostgreSQL ne l'a pas")
        assert "SERIAL" in ddl or "GENERATED" in ddl

    # ⚠️ L'INVENTAIRE, pas un ban. Trois fichiers portent legitimement de la
    # syntaxe SQLite, chacun pour une raison ecrite :
    #   · competences_plan      : DEUX branches de DDL, choisies sur
    #                             `information_schema` — la branche SQLite a
    #                             le droit d'ecrire AUTOINCREMENT ;
    #   · roles_view            : un `PRAGMA table_info` DORMANT — il n'est
    #                             atteint que si une table heritee
    #                             (`user_role_validations`) existe, ce qui
    #                             n'est pas le cas d'une base neuve ;
    #   · time_view             : `ensure_time_role_schema` est un rattrapage
    #                             d'ANCIENS fichiers SQLite, assume (son
    #                             docstring le dit) et son `except` repare la
    #                             session par un rollback. Sur PostgreSQL il
    #                             ne fait rien : les colonnes qu'il ajoute
    #                             viennent de `create_all`.
    # Un QUATRIEME fichier qui s'y mettrait est un defaut : la DDL doit
    # brancher sur le dialecte, ou ne pas etre ecrite a la main.
    #     ⚠️ `performance_personnalisee.py` n'y est PAS, et c'est la preuve
    # que le correctif a porte : depuis qu'il branche sur le dialecte, son
    # AUTOINCREMENT vit dans une VARIABLE, hors du `text(...)` — le fichier est
    # propre au sens de ce controle.
    INVENTAIRE = {
        "Code/routes/competences_plan.py",
        "Code/routes/roles_view.py",
        "Code/routes/time_view.py",
    }
    SQLITE_SEUL = ("AUTOINCREMENT", "DATETIME('NOW')", "PRAGMA ")

    def _sql_brut(self, src):
        """Le contenu des `text(...)`, et lui seul.

        ⚠️ Sans ce cadrage, `db.Column(..., autoincrement=True)` de
        `models.py` — qui est PORTABLE — ferait crier le controle a tort."""
        return " ".join(re.findall(
            r"text\(\s*(?:\"\"\".*?\"\"\"|'''.*?'''|f?\"[^\"]*\"|f?'[^']*')",
            src, re.S)).upper()

    def test_seuls_les_fichiers_INVENTORIES_portent_de_la_syntaxe_SQLite(self):
        coupables = {}
        lus = 0
        racine_code = os.path.join(RACINE, "Code")
        if not os.path.isdir(racine_code):
            pytest.skip("Code/ absent")
        for racine, dossiers, fichiers in os.walk(racine_code):
            dossiers[:] = [d for d in dossiers
                           if d not in ("__pycache__", "templates")]
            for f in fichiers:
                if not f.endswith(".py"):
                    continue
                chemin = os.path.join(racine, f)
                rel = os.path.relpath(chemin, RACINE).replace(os.sep, "/")
                lus += 1
                sql = self._sql_brut(_sans_commentaires(
                    io.open(chemin, encoding="utf-8").read()))
                vus = [m for m in self.SQLITE_SEUL if m in sql]
                if vus and rel not in self.INVENTAIRE:
                    coupables[rel] = vus
        # ⚠️ GARDE-FOU DE VOLUME : dans l'arbre d'image, `Code/` n'a plus aucun
        # `.py` — le balayage y lirait ZERO fichier et ce cas verdirait sans
        # rien verifier. On saute franchement plutot que de mentir.
        if lus < 40:
            pytest.skip("seulement %d sources lues dans Code/ — arbre d'image "
                        "(bytecode seul)" % lus)
        assert not coupables, (
            "syntaxe SQLite SEULE hors inventaire — PostgreSQL la refuse, et "
            "la suite ne peut pas le voir : %s" % coupables)

    def test_l_inventaire_ne_couvre_pas_des_fichiers_DEJA_propres(self):
        """Sans ce garde-fou, l'inventaire grossirait sans jamais maigrir."""
        inutiles = []
        for rel in sorted(self.INVENTAIRE):
            p = os.path.join(RACINE, rel)
            if not os.path.exists(p):
                pytest.skip("%s absent (arbre d'image)" % rel)
            sql = self._sql_brut(_sans_commentaires(
                io.open(p, encoding="utf-8").read()))
            if not any(m in sql for m in self.SQLITE_SEUL):
                inutiles.append(rel)
        assert not inutiles, (
            "ces fichiers sont propres : les retirer de INVENTAIRE, sinon le "
            "cliquet cesse de les surveiller — %s" % inutiles)


class TestLUrlDeLaBaseNommeSonPILOTE:
    """`postgresql://` seul designait psycopg2 en SQLAlchemy 2.0 ; depuis la
    2.1 il designe psycopg (v3), qui n'est pas installe. C'est l'incident du
    29/10 qui a mis tout le hub a terre sans qu'un seul commit ne change, et
    le correctif n'avait ete porte que dans `hub/` et `pulse/`.

    ⚠️ Comportemental sur une FONCTION DE MODULE, donc portable : il tourne
    aussi dans l'arbre d'image, ou `Code/app.py` n'est plus lisible en source.
    """

    def test_un_postgresql_nu_recoit_psycopg2(self):
        from Code.app import normaliser_url_db
        rendu = normaliser_url_db("postgresql://u:p@serveur:5432/base")
        assert rendu == "postgresql+psycopg2://u:p@serveur:5432/base"

    def test_l_ancien_postgres_nu_aussi(self):
        """Heroku et quelques hebergeurs servent encore `postgres://`."""
        from Code.app import normaliser_url_db
        rendu = normaliser_url_db("postgres://u:p@serveur/base")
        assert rendu == "postgresql+psycopg2://u:p@serveur/base"

    @pytest.mark.parametrize("url", [
        "postgresql+psycopg://u@h/b",
        "postgresql+asyncpg://u@h/b",
        "sqlite:///chemin/vers.db",
        "mysql+pymysql://u@h/b",
        "",
        None,
    ])
    def test_une_url_qui_dit_deja_son_pilote_n_est_PAS_reecrite(self, url):
        """⚠️ Reecrire une URL qui nomme son pilote, ce serait decider a la
        place de celui qui l'a posee."""
        from Code.app import normaliser_url_db
        assert normaliser_url_db(url) == url

    def test_l_URL_que_le_KIT_CLIENT_passe_recoit_son_pilote(self):
        """⚠️ `distribution/docker-compose.yml` passe au client un
        `postgresql://` NU. Tant que l'app nomme le pilote, une reconstruction
        d'image avec une SQLAlchemy plus recente ne casse pas son
        installation."""
        from Code.app import normaliser_url_db
        chemin = os.path.join(RACINE, "distribution", "docker-compose.yml")
        if not os.path.exists(chemin):
            pytest.skip("kit client absent (arbre d'image)")
        compose = io.open(chemin, encoding="utf-8").read()
        urls = re.findall(r"(postgres(?:ql)?(?:\+\w+)?://[^\s]+)", compose)
        assert urls, "aucune URL de base dans le compose client : cas a revoir"
        for u in urls:
            assert "+psycopg2://" in normaliser_url_db(u), (
                "l'URL du kit client ne recevrait pas son pilote : %s" % u)


class TestLesTablesSansModeleSontINVENTORIEES:
    """Cinq tables sont nommees en SQL brut sans qu'aucun modele ne les cree.
    Trois se creent elles-memes a chaud ; DEUX sont seulement LUES, et c'est
    ce qui a produit le 500 du tableau de bord.

    ⚠️ L'inventaire est un CLIQUET : une table de plus doit etre un choix
    ecrit, pas un effet de bord. `entreprise_settings` et `user_activity_plans`
    ont chacune coute un 500 en production avant d'obtenir leur modele.
    """

    CONNUES = {
        # lues seulement, jamais creees — d'ou le repli de get_company_params
        "company_params", "gestion_rh_params",
        # creees a chaud par leur route
        "performance_personnalisee_historique", "training_plan",
        "prerequis_comment",
        # sondees pour savoir si elles existent
        "user_role_validations", "role_validations",
        # pas des tables de l'application
        "information_schema", "sqlite_master", "alembic_version", "pg_catalog",
    }

    def test_aucune_table_inconnue_n_est_lue_en_SQL_brut(self, app):
        motif = re.compile(
            r"(?:FROM|INTO|UPDATE|DELETE\s+FROM|JOIN)\s+([a-z_][a-z_0-9]*)\b")
        noms = set()
        lus = 0
        for racine, dossiers, fichiers in os.walk(os.path.join(RACINE, "Code")):
            dossiers[:] = [d for d in dossiers
                           if d not in ("__pycache__", "templates")]
            for f in fichiers:
                if not f.endswith(".py"):
                    continue
                lus += 1
                src = _sans_commentaires(
                    io.open(os.path.join(racine, f), encoding="utf-8").read())
                # On ne lit QUE l'interieur des text(...) : ailleurs, « from »
                # est un import et « update » un nom de methode.
                for bloc in re.findall(r"text\(\s*(?:f?\"\"\".*?\"\"\"|f?\"[^\"]*\"|f?'[^']*')",
                                       src, re.S):
                    noms |= {m.lower() for m in motif.findall(bloc)}
        # ⚠️ Meme garde-fou de volume : zero source lue = zero table trouvee
        # = un vert qui ne prouve rien.
        if lus < 40:
            pytest.skip("seulement %d sources lues dans Code/ — arbre d'image "
                        "(bytecode seul)" % lus)
        with app.app_context():
            declarees = set(db.metadata.tables.keys())
        inconnues = sorted(noms - declarees - self.CONNUES)
        assert not inconnues, (
            "table(s) nommee(s) en SQL brut sans modele ni inventaire : %s — "
            "donner un modele, ou l'inscrire dans CONNUES en disant pourquoi"
            % inconnues)

    def test_l_inventaire_suit_la_realite(self, app):
        """Sans ce garde-fou, l'inventaire grossirait sans jamais maigrir."""
        with app.app_context():
            declarees = set(db.metadata.tables.keys())
        doublons = sorted(self.CONNUES & declarees)
        assert not doublons, (
            "ces tables ont desormais un MODELE : les retirer de CONNUES, "
            "sinon le cliquet cesse de les surveiller — %s" % doublons)
