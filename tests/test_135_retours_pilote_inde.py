# -*- coding: utf-8 -*-
"""Retours du pilote indien (OPTIQ Tool Query, 07/09 → 29/10/2026).

Trente-six lignes, dont beaucoup déjà réglées sur `staging` depuis — la
cartographie à nom unique, l'historique des imports, le mot du valideur, la
langue du journal. Ce fichier ne garde que ce qui restait VRAIMENT ouvert, et
chaque cliquet a été vérifié ROUGE avant d'être gardé.

Ce qui tient ailleurs, et qu'on ne redit pas :
  • un nom de carto unique → `test_91`
  • l'historique des imports → `test_91`
  • la décision parvient à l'auteur → `test_88`
  • le journal dans la langue du lecteur → `test_83`
  • les cinq récurrences, trimestre compris → `test_105`
"""
import io
import os

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(rel):
    return io.open(os.path.join(RACINE, *rel.split("/")), encoding="utf-8").read()


def _code_js(src):
    """Le JS sans ses commentaires — un contrôle qui cherche une phrase dans du
    code ne doit pas tomber sur le commentaire qui l'explique."""
    import re
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", src)


def _compte(app, client, statut, suffixe=""):
    """Get-or-create : `users.email` est UNIQUE, et plusieurs cas demandent le
    même palier — le second tomberait en IntegrityError."""
    from Code.models.models import User
    from Code.security import hash_password
    courriel = "t131.%s%s@test" % (statut, suffixe)
    with app.app_context():
        u = User.query.filter_by(email=courriel).first()
        if u is None:
            u = User(first_name="T131", last_name=statut + suffixe,
                     email=courriel, password=hash_password("Test1234!"),
                     status=statut)
            db.session.add(u)
            db.session.commit()
        uid = u.id
    with client.session_transaction() as s:
        s["user_id"] = uid
    return uid


@pytest.fixture
def cartos(app):
    """Trois cartos, et le ménage en partant.

    ⚠️ Une carto laissée SANS propriétaire est lisible par tout le monde et
    devient le repli « aucune entité active » des fichiers suivants ; une carto
    laissée commune aussi. Elles sont détruites en fin de cas.
    """
    from Code.models.models import Entity, User
    with app.app_context():
        tiers = User.query.filter_by(email="t131.proprio@test").first()
        if tiers is None:
            from Code.security import hash_password
            tiers = User(first_name="T131", last_name="proprio",
                         email="t131.proprio@test",
                         password=hash_password("Test1234!"), status="user")
            db.session.add(tiers)
            db.session.commit()
        orpheline = Entity(name="T131 sans proprietaire", owner_id=None)
        partagee = Entity(name="T131 commune d un tiers",
                          owner_id=tiers.id, is_shared=True)
        privee = Entity(name="T131 privee d un tiers",
                        owner_id=tiers.id, is_shared=False)
        db.session.add_all([orpheline, partagee, privee])
        db.session.commit()
        ids = {"orpheline": orpheline.id, "partagee": partagee.id,
               "privee": privee.id, "tiers": tiers.id}
    yield ids
    with app.app_context():
        for cle in ("orpheline", "partagee", "privee"):
            e = db.session.get(Entity, ids[cle])
            if e is not None:
                db.session.delete(e)
        db.session.commit()


@pytest.fixture
def decor_garant(app):
    """Une activité et un rôle À NOUS.

    ⚠️ `Role.query.first()` rendait `None` quand ce fichier tourne seul, et
    dépendrait de l'ordre des fichiers en suite complète — le décor du module
    est remanié par les tests de ménage. Les rôles sont COMMUNS à l'entreprise
    depuis le 23/09 : un nom fixe ferait collision.
    """
    from Code.models.models import Activities, Entity, Role
    with app.app_context():
        ent = Entity(name="T131 decor garant")
        db.session.add(ent)
        db.session.flush()
        act = Activities(name="T131 activite garant", entity_id=ent.id)
        role = Role(name="T131 role garant", entity_id=ent.id)
        db.session.add_all([act, role])
        db.session.commit()
        trio = (act.id, role.id, role.name)
        eid = ent.id
    yield trio
    with app.app_context():
        for modele, ident in ((Activities, trio[0]), (Role, trio[1]),
                              (Entity, eid)):
            objet = db.session.get(modele, ident)
            if objet is not None:
                db.session.delete(objet)
        db.session.commit()


# ════════════════════════════════════════════════════════════════════════
#  « Not able to change the name or rename the imported Map »  (11, 21)
# ════════════════════════════════════════════════════════════════════════
class TestRenommerUneCartoQuOnVoit:
    """⚠️ MÊME DÉFAUT que celui corrigé dans `delete_entity` le 23/09, resté
    dans `update_entity` : la carto était cherchée par `(id, owner_id)` alors
    que la LISTE en montre d'autres — celles sans propriétaire, et les cartos
    communes ouvertes à ses rôles. Le bouton « Renommer » était donc offert sur
    une carto de sa propre liste, et la réponse disait « Entité non trouvée ».
    """

    def test_une_carto_sans_proprietaire_se_renomme(self, app, cartos):
        from Code.models.models import Entity
        c = app.test_client()
        _compte(app, c, "user")
        r = c.patch("/activities/api/entities/%d" % cartos["orpheline"],
                    json={"name": "T131 renommee"})
        assert r.status_code == 200, r.data
        with app.app_context():
            assert db.session.get(Entity, cartos["orpheline"]).name == "T131 renommee"

    def test_le_refus_dit_POURQUOI_au_lieu_de_nier_la_carto(self, app, cartos):
        """Elle est VISIBLE dans sa liste (commune, donc lisible) : répondre
        « non trouvée » envoie chercher une carto disparue."""
        from Code.models.models import Entity
        c = app.test_client()
        _compte(app, c, "user")
        r = c.patch("/activities/api/entities/%d" % cartos["partagee"],
                    json={"name": "T131 vol"})
        assert r.status_code == 403, r.data
        assert r.get_json().get("code") == "lecture_seule", r.data
        with app.app_context():
            assert db.session.get(Entity, cartos["partagee"]).name \
                == "T131 commune d un tiers"

    def test_un_coordinateur_renomme_une_carto_commune(self, app, cartos):
        from Code.models.models import Entity
        c = app.test_client()
        _compte(app, c, "coordinateur")
        r = c.patch("/activities/api/entities/%d" % cartos["partagee"],
                    json={"name": "T131 commune renommee"})
        assert r.status_code == 200, r.data
        with app.app_context():
            assert db.session.get(Entity, cartos["partagee"]).name \
                == "T131 commune renommee"

    def test_un_nom_deja_pris_reste_refuse(self, app, cartos):
        """Non-régression : l'unicité des noms (test_91) ne doit pas sauter."""
        c = app.test_client()
        _compte(app, c, "user")
        r = c.patch("/activities/api/entities/%d" % cartos["orpheline"],
                    json={"name": "T131 privee d un tiers"})
        assert r.status_code == 409, r.data
        assert r.get_json().get("code") == "nom_pris"

    def test_une_carto_absente_reste_une_404(self, app):
        c = app.test_client()
        _compte(app, c, "user")
        r = c.patch("/activities/api/entities/987654321", json={"name": "X"})
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════════
#  « Can not delete the map »  (26)
# ════════════════════════════════════════════════════════════════════════
class TestSupprimerUneCartoQuOnVoit:
    def test_le_refus_porte_un_motif_pas_une_negation(self, app, cartos):
        from Code.models.models import Entity
        c = app.test_client()
        _compte(app, c, "user")
        r = c.delete("/activities/api/entities/%d" % cartos["partagee"])
        assert r.status_code == 403, r.data
        assert r.get_json().get("code") == "pas_proprietaire", r.data
        with app.app_context():
            assert db.session.get(Entity, cartos["partagee"]) is not None

    def test_une_carto_sans_proprietaire_se_supprime_toujours(self, app, cartos):
        """Le correctif du 23/09 ne doit pas sauter avec le message."""
        from Code.models.models import Entity
        c = app.test_client()
        _compte(app, c, "user")
        r = c.delete("/activities/api/entities/%d" % cartos["orpheline"])
        assert r.status_code == 200, r.data
        with app.app_context():
            assert db.session.get(Entity, cartos["orpheline"]) is None

    def test_les_deux_refus_se_lisent_dans_les_deux_langues(self):
        from Code.translations import t
        for cle in ("map.err_renommer_refuse", "map.err_supprimer_refuse"):
            for langue in ("fr", "en"):
                phrase = t(cle, langue)
                assert phrase and not phrase.startswith("map."), (cle, langue)
            assert t(cle, "fr") != t(cle, "en"), cle


# ════════════════════════════════════════════════════════════════════════
#  « In Time Management - quaterly recurrence is not available »  (34)
# ════════════════════════════════════════════════════════════════════════
class TestLaRecurrenceTrimestrielle:
    """⚠️ Le piège : une récurrence INCONNUE retombe sur `return q`, c'est-à-dire
    sur l'ANNUEL. Ajouter l'option sans le facteur aurait fait compter une
    charge trimestrielle quatre fois trop peu, en silence. Les deux
    implémentations changent ensemble, et c'est ce que ce cliquet garde.
    """

    def test_le_serveur_compte_quatre_periodes_par_an(self, app):
        from Code.routes.time_view import annuel_minutes
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 47}
        assert annuel_minutes(10, "trimestriel", p) == 40
        assert annuel_minutes(10, "annuel", p) == 10

    def test_le_navigateur_applique_le_MEME_facteur(self):
        js = _lire("static/js/time.js")
        bloc = js[js.index("function annuelMinutes"):][:900]
        assert "startsWith('trimestr')" in bloc, bloc
        assert "q * 4" in bloc, bloc

    def test_la_faiblesse_compte_quatre_trimestres_pour_une_annee(self, app):
        """⚠️ L'onglet Faiblesse compte en semaines TRAVAILLÉES, pas en
        calendrier civil : ce n'est pas la même base que `annuel_minutes`, mais
        le RAPPORT entre un trimestre et une année doit valoir 4 des deux
        côtés."""
        from Code.routes.time_view import cout_faiblesse
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 48}
        commun = dict(duree_std_min=60, delai_std_min=60, travail_ajoute_min=10,
                      attente_ajoutee_min=5, denom_proba=1, frequence=1,
                      params=p, pct_proba=100.0)
        an = cout_faiblesse(recurrence="annuel", **commun)
        tri = cout_faiblesse(recurrence="trimestriel", **commun)
        # AA = les occurrences par an, U = le travail refait sur l'année.
        assert tri["AA"] == pytest.approx(an["AA"] * 4), (tri["AA"], an["AA"])
        assert tri["U"] == pytest.approx(an["U"] * 4), (tri["U"], an["U"])
        assert tri["V"] == pytest.approx(an["V"] * 4), (tri["V"], an["V"])

    def test_l_option_existe_partout_ou_on_choisit_une_recurrence(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        js = _lire("static/js/time.js")
        assert g.count("<option value=\"trimestriel\">") == 2, g.count("trimestriel")
        assert "value=\"trimestriel\"" in js

    def test_le_libelle_existe_dans_les_deux_langues(self):
        from Code.translations import t
        assert t("time.rec_quarterly", "fr") == "Trimestriel"
        assert t("time.rec_quarterly", "en") == "Quarterly"

    def test_le_libelle_est_injecte_dans_TIME_I18N(self):
        """Sans quoi `addRoleRow` afficherait son repli français en dur."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert "rec_quarterly:" in g
        assert "t('time.rec_quarterly')|tojson" in g


# ════════════════════════════════════════════════════════════════════════
#  « Unable to set the garentor in activity list »  (35)
# ════════════════════════════════════════════════════════════════════════
class TestDesignerLeGarantSePropose:
    """Le garant est une donnée d'activité comme les autres. Il manquait
    pourtant à la liste des gestes proposables (19/10) : un champion sur une
    carto commune se faisait refuser au lieu de déposer une proposition.

    ⚠️ Et il ne fallait PAS ouvrir tout `/roles` : la suppression d'un rôle
    emporte ses titulaires et ses liens dans TOUTES les cartos, et elle est
    réservée à l'administrateur depuis le 03/11.
    """

    def test_le_geste_est_reconnu(self, app, decor_garant):
        from Code.propositions_activite import lire_geste
        act_id, role_id, role_nom = decor_garant
        with app.app_context():
            g = lire_geste("/roles/garant/activity/%d" % act_id, "POST",
                           {"role_id": role_id})
        assert g is not None, "le garant n'est pas proposable"
        assert g["op"] == "garant.designer", g
        assert g["activity_id"] == act_id, g
        assert g["objet"] == role_nom, g

    def test_la_suppression_d_un_role_n_est_PAS_proposable(self, app, decor_garant):
        """Le garde-fou : sinon un champion proposerait d'effacer un rôle de
        toute l'entreprise."""
        from Code.propositions_activite import lire_geste
        _act, role_id, _nom = decor_garant
        with app.app_context():
            assert lire_geste("/roles/%d" % role_id, "DELETE", {}) is None
            assert lire_geste("/roles/%d" % role_id, "PUT", {"name": "X"}) is None

    def test_le_coordinateur_lit_une_phrase_et_pas_un_code(self):
        from Code.translations import t
        for langue in ("fr", "en"):
            for cle in ("acp.v_designer", "acp.f_garant"):
                phrase = t(cle, langue)
                assert phrase and not phrase.startswith("acp."), (cle, langue)
        assert t("acp.v_designer", "fr") != t("acp.v_designer", "en")

    def test_les_deux_ecrans_injectent_les_deux_libelles(self):
        """⚠️ L'auteur et le coordinateur regardent le même geste : deux écrans
        qui n'injectent pas les mêmes clés finissent par dire deux choses."""
        for gabarit in ("Code/routes/templates/activite_propositions.html",
                        "Code/routes/templates/carto_examen_modal.html"):
            g = _lire(gabarit)
            assert "v_designer:" in g, gabarit
            assert "f_garant:" in g, gabarit


# ════════════════════════════════════════════════════════════════════════
#  « Add search option to find chart »  (36)
# ════════════════════════════════════════════════════════════════════════
class TestRechercherUneCarto:
    """Le pilote porte une quinzaine de cartos, dont neuf du même nom de base
    numérotées par `entites_uniques` : la grille se parcourait à l'œil."""

    def test_le_champ_existe_dans_la_pop_up_des_entites(self):
        g = _lire("Code/routes/templates/activities_map.html")
        assert 'id="wizard-entity-search"' in g
        assert "t('map.entity_search_ph')" in g

    def test_le_filtre_ecoute_la_FRAPPE_et_pas_la_perte_de_focus(self):
        """⚠️ `change` n'arrive qu'à la perte du focus : branché là, le champ ne
        filtrerait rien pendant qu'on tape, sans aucune erreur pour le dire."""
        js = _lire("static/js/activities_map.js")
        bloc = js[js.index("function brancherRechercheEntites"):][:600]
        assert 'addEventListener("input"' in bloc, bloc
        assert 'addEventListener("change"' not in bloc, bloc

    def test_il_MASQUE_au_lieu_de_re_rendre(self):
        """Réécrire la grille à chaque frappe ferait perdre le curseur du champ
        qu'on tape — le piège déjà rencontré sur le plan de formation."""
        js = _lire("static/js/activities_map.js")
        bloc = js[js.index("function filtrerEntites"):][:800]
        assert "el.hidden" in bloc, bloc
        assert "innerHTML" not in bloc, bloc

    def test_le_masquage_masque_vraiment(self):
        """⚠️ `[hidden]` est une règle du NAVIGATEUR : `.entity-grid-item` pose
        son propre `display`, et une classe d'auteur l'emporte. Quatrième fois
        que ce piège mord dans cette application."""
        css = _lire("static/cartography.css")
        assert ".entity-grid-item[hidden]" in css
        assert "display: none" in css[css.index(".entity-grid-item[hidden]"):][:90]

    def test_les_libelles_sont_dans_les_deux_langues(self):
        from Code.translations import t
        for cle in ("map.entity_search_ph", "map.entity_search_none"):
            for langue in ("fr", "en"):
                assert not t(cle, langue).startswith("map."), (cle, langue)
            assert t(cle, "fr") != t(cle, "en"), cle


# ════════════════════════════════════════════════════════════════════════
#  « AI assistance is not in english language »  (32)
# ════════════════════════════════════════════════════════════════════════
class TestLAssistantRepondDansLaLangueDeLEcran:
    """⚠️⚠️ LE DÉFAUT DE FOND, et il n'était pas dans l'interface. Le prompt
    système est bien servi en anglais par `chatbot.py`, mais `chatbot.js`
    construisait le PREMIER TOUR UTILISATEUR en français — « Mode création
    activé. Je souhaite créer les tâches pour l'activité "X" via un entretien
    guidé. Commence l'interview. » Un modèle qui reçoit une consigne française
    répond en français.

    Et c'était un prompt écrit dans le navigateur, ce que le catalogue chiffré
    interdit (`Code/prompts/catalog.py` est exclu de l'image client).
    """

    def test_aucune_amorce_francaise_ne_part_du_navigateur(self):
        """⚠️ On retire les COMMENTAIRES avant de chercher : le commentaire qui
        explique ce correctif cite la phrase fautive, et ce contrôle s'est
        d'abord attrapé lui-même. Troisième fois que ce piège se présente dans
        ce dépôt (les clés i18n construites, le `<section>` de la doc)."""
        js = _code_js(_lire("static/js/chatbot.js"))
        for morceau in ("Mode création activé", "Mode révision activé",
                        "Commence l'interview", "entretien guidé"):
            assert morceau not in js, morceau

    def test_le_demarrage_n_ajoute_AUCUN_tour_utilisateur(self, app, auth_client):
        """Le serveur ouvre la conversation : la consigne d'ouverture vit déjà
        dans `chatbot.mode_*.<lang>`, ajoutée au prompt système."""
        from Code.routes import chatbot as mod
        vus = {}

        def faux_prompt(cle, **kw):
            return "PROMPT:" + cle

        class FauxClient:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kw):
                        vus["messages"] = kw["messages"]
                        raise RuntimeError("stop apres capture")

        mod_get_prompt = mod.get_prompt
        mod.get_prompt = faux_prompt
        try:
            import Code.ai_client as ai
            vrai_make = ai.make_ai_client
            vrai_key = mod.get_openai_key
            ai.make_ai_client = lambda *a, **k: (FauxClient(), "m", None)
            mod.get_openai_key = lambda *a, **k: "clef-de-test"
            try:
                auth_client.post("/api/chatbot/chat", json={
                    "activity": {"name": "A", "tasks": []},
                    "history": [], "message": "", "mode": "creer",
                    "demarrage": True})
            finally:
                ai.make_ai_client = vrai_make
                mod.get_openai_key = vrai_key
        finally:
            mod.get_prompt = mod_get_prompt

        assert "messages" in vus, "la requete n'a pas atteint le client IA"
        roles = [m["role"] for m in vus["messages"]]
        assert "user" not in roles, vus["messages"]

    def test_un_message_vide_HORS_demarrage_reste_refuse(self, app, auth_client):
        r = auth_client.post("/api/chatbot/chat", json={
            "activity": {"name": "A"}, "history": [], "message": "",
            "mode": "creer"})
        assert r.status_code == 400, r.data

    def test_toutes_les_cles_lues_par_le_JS_sont_injectees(self):
        """⚠️ `CL()` rend la CLÉ quand elle manque — jamais un repli français,
        qu'on ne verrait pas. Encore faut-il que le gabarit les injecte."""
        import re
        js = _lire("static/js/chatbot.js")
        g = _lire("Code/routes/templates/chatbot_widget.html")
        lues = set(re.findall(r"C[LF]\('([a-z0-9_]+)'", js))
        assert len(lues) >= 20, lues
        injectees = set(re.findall(r"^\s{4}([a-z0-9_]+):\s+\{\{", g, re.M))
        manquantes = sorted(lues - injectees)
        assert not manquantes, manquantes

    def test_les_libelles_existent_dans_LES_DEUX_langues(self):
        """⚠️ On lit les DICTIONNAIRES, pas `t()`. Une clé absente de l'anglais
        retombe SILENCIEUSEMENT sur le français (c'est le repli voulu pour que
        rien n'affiche une clé brute) : passer par `t()` rendait ce cliquet
        incapable de voir l'oubli — vérifié, il restait vert.
        """
        import re
        from Code.translations import TRANSLATIONS
        g = _lire("Code/routes/templates/chatbot_widget.html")
        cles = sorted(set(re.findall(r"t\('(chat\.[a-z0-9_]+)'\)", g)))
        assert len(cles) >= 30, cles
        for langue in ("fr", "en"):
            manquantes = [c for c in cles if c not in TRANSLATIONS[langue]]
            assert not manquantes, (langue, manquantes)
        # Et elles doivent VRAIMENT différer : recopier le français en anglais
        # est l'autre façon de ne pas traduire.
        identiques = [c for c in cles
                      if TRANSLATIONS["fr"][c] == TRANSLATIONS["en"][c]]
        assert len(identiques) <= 2, identiques

    def test_le_gabarit_ne_porte_plus_de_francais_en_dur(self):
        """⚠️ Y COMPRIS les attributs : `test_78` ne lit que le texte, et les
        six `title` / `aria-label` / `placeholder` du widget étaient français."""
        import re
        g = _lire("Code/routes/templates/chatbot_widget.html")
        for attribut, valeur in re.findall(
                r'(title|placeholder|aria-label)="([^"]*)"', g):
            assert "{{" in valeur or "}}" in valeur, (attribut, valeur)

    def test_la_substitution_suit_la_convention_du_fichier(self):
        """⚠️ Deux conventions coexistent dans l'application : `{n}` et
        `[[n]]`. Une clé qui prend la mauvaise affiche son marqueur TEL QUEL,
        et rien ne lève d'erreur."""
        from Code.translations import t
        for cle, marqueur in (("chat.inject", "[[n]]"),
                              ("chat.ctx_counts", "[[t]]"),
                              ("chat.greeting", "[[a]]"),
                              ("chat.loaded", "[[m]]")):
            for langue in ("fr", "en"):
                assert marqueur in t(cle, langue), (cle, langue)
                assert "{%s}" % marqueur[2:-2] not in t(cle, langue), (cle, langue)
