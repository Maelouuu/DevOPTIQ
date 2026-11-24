# -*- coding: utf-8 -*-
"""Les prompts IA : joignables, complets, et dans la langue de l'écran.

L'application appelle l'IA à **vingt-trois endroits** dans `Code/` — vingt-deux
routes, plus le prompt trivial de `role_i18n` — et rien ne vérifiait que
chacun dit au modèle dans quelle langue répondre. Trois façons de le dire
cohabitent, toutes légitimes :

  1. le prompt a une VARIANTE par langue (`qualify.system.fr` / `.en`) ;
  2. la route AJOUTE une consigne au message utilisateur (`diagnostic`, `hsc`) ;
  3. la langue voyage dans le CONTEXTE JSON (`plan_formation`, `import`).

Ce qui ne marche pas, c'est de ne rien dire : un prompt français rend du
français, quelle que soit la langue de l'écran. Et le défaut est silencieux —
personne ne lève d'erreur, le pilote anglophone lit simplement du français.

⚠️ Deux familles de contrôles, et la séparation est VOULUE :

  • `TestLeCatalogue…` lit `Code/prompts/catalog.py`, qui est **exclu de
    l'image client** (`.dockerignore`, remplacé par `prompts.enc`) : ces cas
    SAUTENT dans l'arbre d'image, et c'est la bonne réponse — le fichier n'y
    est pas.
  • tous les autres passent par un magasin de MARQUEURS et un client IA qui
    enregistre : ils lisent le comportement des ROUTES, pas le texte des
    prompts, et tournent donc partout. C'est la partie qui garde le défaut.
"""
import importlib
import json
import re

import pytest


# ─────────────────────────── Le client IA qui enregistre ───────────────────────────

# Une réponse qui satisfait tous les parseurs : chaque route lit la clé qui
# l'intéresse. Ce qu'on vérifie, c'est ce qui PART — pas ce qui revient.
CORPS = json.dumps({
    "items": [], "actions": [], "results": [], "plan": [], "resolved": [],
    "still_unmatched": [], "proposals": [], "activity_competence": {},
    "probable_level": 2, "outputs": [], "modules": [],
})


class _Msg:
    def __init__(self, contenu):
        self.content = contenu


class _Choix:
    def __init__(self, contenu):
        self.message = _Msg(contenu)


class _Reponse:
    def __init__(self, contenu=CORPS):
        self.choices = [_Choix(contenu)]


class FauxClient:
    """Enregistre tout ce qu'on envoie au modèle, et rend une réponse neutre."""

    def __init__(self):
        self.envois = []
        self.chat = self
        self.completions = self

    def create(self, **kw):
        self.envois.append(kw)
        return _Reponse()

    @property
    def texte(self):
        bouts = []
        for kw in self.envois:
            for m in (kw.get("messages") or []):
                bouts.append(str(m.get("content", "")))
        return "\n".join(bouts)

    @property
    def cles(self):
        """Les clés de prompt que les marqueurs révèlent dans ce qui est parti."""
        return set(re.findall(r"<<([a-z0-9_.]+)>>", self.texte))


class Marqueurs:
    """Magasin de prompts qui rend un MARQUEUR pour n'importe quelle clé.

    ⚠️ On ne peut pas se servir du vrai catalogue ici : il est exclu de l'image
    client. Le marqueur dit QUELLE CLÉ la route a demandée — la seule chose
    qu'on veuille garder — et il porte `[[lang_instr]]`, le seul placeholder
    dont la VALEUR est une consigne de langue (`skills.competencies`).
    """

    def __init__(self):
        self.demandees = []

    def get(self, cle):
        self.demandees.append(cle)
        return "<<%s>>[[lang_instr]]" % cle

    def __bool__(self):
        return True


MODULES_AVEC_CLE = (
    "Code.routes.skills", "Code.routes.changelog", "Code.routes.onboarding",
    "Code.routes.translate_softskills", "Code.routes.propose_common",
    "Code.routes.import_full", "Code.routes.chatbot",
)


@pytest.fixture
def ia(monkeypatch):
    """Une IA factice, et un catalogue de marqueurs."""
    faux = FauxClient()
    from Code import prompts as P
    faux.magasin = Marqueurs()
    monkeypatch.setattr(P, "_store", faux.magasin, raising=False)
    import Code.ai_client as AC
    monkeypatch.setattr(AC, "make_ai_client",
                        lambda timeout=None: (faux, "modele-de-test", None))
    # ⚠️ Ces modules importent `get_openai_key` AU NIVEAU DU MODULE : remplacer
    # `Code.ai_key.get_openai_key` ne changerait rien pour eux.
    for nom in MODULES_AVEC_CLE:
        mod = importlib.import_module(nom)
        if hasattr(mod, "get_openai_key"):
            monkeypatch.setattr(mod, "get_openai_key", lambda: "sk-de-test")
    return faux


@pytest.fixture
def en(auth_client):
    """L'écran en anglais, et la langue RENDUE en partant.

    ⚠️ `client` est partagé par toute la suite : une langue laissée à « en »
    change les messages que les fichiers suivants comparent (la leçon de
    `test_82` et `test_83`)."""
    with auth_client.session_transaction() as s:
        avant = s.get("lang")
        s["lang"] = "en"
    yield auth_client
    with auth_client.session_transaction() as s:
        if avant is None:
            s.pop("lang", None)
        else:
            s["lang"] = avant


@pytest.fixture
def fr(auth_client):
    with auth_client.session_transaction() as s:
        avant = s.get("lang")
        s["lang"] = "fr"
    yield auth_client
    with auth_client.session_transaction() as s:
        if avant is None:
            s.pop("lang", None)
        else:
            s["lang"] = avant


@pytest.fixture
def activite_avec_sortie(app):
    """Une carto À SOI, avec une activité qui produit une donnée nommée.

    ⚠️ Pas l'activité du décor commun : écrire dedans s'équilibre peut-être à
    la ligne près, mais l'entité ACTIVE ne revient pas toute seule — et le
    défaut se lit alors chez un fichier qui ne parle pas du même sujet.
    ⚠️ `owner_id` est posé : une entité de test SANS propriétaire est lisible
    par tout le monde et devient le repli des fichiers suivants.
    """
    from Code.extensions import db
    from Code.models.models import Activities, Data, Entity, Link, Role, User

    with app.app_context():
        moi = User.query.filter_by(email="test@devoptiq.com").first()
        ent = Entity(name="Carto prompts IA", description="test_164", owner_id=moi.id)
        db.session.add(ent)
        db.session.flush()
        amont = Activities(entity_id=ent.id, name="Chiffrer l'offre")
        aval = Activities(entity_id=ent.id, name="Valider l'offre")
        db.session.add_all([amont, aval])
        db.session.flush()
        # Une flèche SANS libellé ne produit aucune sortie (règle du 03/11) :
        # celle-ci en porte un.
        db.session.add(Link(entity_id=ent.id, source_activity_id=amont.id,
                            target_activity_id=aval.id, description="Offre chiffrée",
                            type="declenchante"))
        # ⚠️ Un nom UNIQUE : les rôles sont communs à l'entreprise depuis le
        # 23/09, un nom fixe fait collision dès que deux fichiers tournent.
        role = Role(entity_id=ent.id, name="Rôle prompts IA test_164")
        db.session.add(role)
        db.session.commit()
        ids = (ent.id, amont.id, role.id)

    yield ids

    with app.app_context():
        ent_id = ids[0]
        Role.query.filter_by(id=ids[2]).delete()
        Link.query.filter_by(entity_id=ent_id).delete()
        Data.query.filter_by(entity_id=ent_id).delete()
        Activities.query.filter_by(entity_id=ent_id).delete()
        Entity.query.filter_by(id=ent_id).delete()
        db.session.commit()


# ─────────────────────── La règle, écrite une fois ───────────────────────

def doit_dire_anglais(faux):
    """En anglais : une clé `.en` OU le mot « English », et JAMAIS le français.

    Les trois façons de dire la langue passent par ce même crible — c'est ce
    qui en fait une règle et pas une liste de cas particuliers.
    """
    assert faux.envois, "aucun appel au modèle : la route est tombée dans un repli"
    texte = faux.texte
    dit = ".en>>" in texte or "English" in texte
    assert dit, "rien ne dit l'anglais dans ce qui est parti :\n" + texte[:900]
    assert ".fr>>" not in texte, "une variante FRANÇAISE est partie :\n" + texte[:900]
    assert "français" not in texte, "le mot « français » est parti :\n" + texte[:900]


def doit_dire_francais(faux):
    assert faux.envois, "aucun appel au modèle : la route est tombée dans un repli"
    texte = faux.texte
    dit = ".fr>>" in texte or "français" in texte
    assert dit, "rien ne dit le français dans ce qui est parti :\n" + texte[:900]
    assert ".en>>" not in texte, "une variante ANGLAISE est partie :\n" + texte[:900]


# Les routes qui ne demandent qu'un corps JSON : l'activité y voyage entière.
CHARGE_ACTIVITE = {
    "name": "Chiffrer l'offre", "title": "Chiffrer l'offre",
    "description": "Produire une offre chiffrée",
    "tasks": [{"name": "Relever les besoins", "tools": ["ERP"]}],
    "constraints": ["Délai de 48 h"], "outgoing": [], "incoming": [],
    "input_data": ["Demande client"], "output_data": ["Offre chiffrée"],
    "tools": ["ERP"], "savoir_faires": ["Chiffrer"], "savoirs": [], "hsc": [],
    "aptitudes": [], "competences": [], "available_tools": ["ERP"],
}

ROUTES_SANS_DECOR = [
    ("/propose_savoirs/propose", CHARGE_ACTIVITE),
    ("/propose_savoir_faires/propose", CHARGE_ACTIVITE),
    ("/propose_softskills/propose", CHARGE_ACTIVITE),
    ("/propose_aptitudes/propose", CHARGE_ACTIVITE),
    ("/propose_aptitudes/feasibility", {"activity_name": "Chiffrer l'offre",
                                        "inclusion_scoring_json": "{}",
                                        "assistive_products": []}),
    ("/skills/propose", dict(CHARGE_ACTIVITE, tasks=["Relever les besoins"])),
    ("/translate_softskills/translate", {"user_input": "sait arbitrer vite",
                                         "activity": CHARGE_ACTIVITE}),
    ("/hsc/position", {"hsc_name": "Arbitrage", "responses": ["a tranché seul"]}),
    ("/diagnostic/plan", {"user_id": 1, "activity_id": 1, "data_id": 999999,
                          "families": ["ABILITY_TO_ACT"]}),
    ("/api/chatbot/chat", {"activity": CHARGE_ACTIVITE, "history": [],
                           "demarrage": True, "mode": "creer"}),
]


class TestChaqueRouteDitLaLangue:
    """Le cœur du fichier : ce qui PART vers le modèle porte la langue."""

    @pytest.mark.parametrize("url,charge", ROUTES_SANS_DECOR,
                             ids=[u for u, _ in ROUTES_SANS_DECOR])
    def test_en_anglais(self, en, ia, url, charge):
        en.post(url, json=charge)
        doit_dire_anglais(ia)

    @pytest.mark.parametrize("url,charge", ROUTES_SANS_DECOR,
                             ids=[u for u, _ in ROUTES_SANS_DECOR])
    def test_en_francais(self, fr, ia, url, charge):
        fr.post(url, json=charge)
        doit_dire_francais(ia)

    def test_qualifier_les_sorties_en_anglais(self, en, ia, activite_avec_sortie):
        """⚠️ Et le bloc de CONTEXTE avec : sous un prompt système anglais, des
        intitulés français sont le signal mixte qui fait répondre en français.
        ⚠️ L'assertion sur `envois` compte double ici : l'ajout du paramètre
        `lang` a d'abord levé un NameError DANS le `try` de la route, avalé —
        `/qualify/analyze` rendait son repli en 200, l'appel IA disparu sans un
        mot. C'est le banc qui l'a vu ; ce cas le verrait aussi."""
        aid = activite_avec_sortie[1]
        en.post("/qualify/analyze/%d" % aid, json={})
        doit_dire_anglais(ia)
        texte = ia.texte
        assert "Output data (to qualify)" in texte, texte[:600]
        assert "Données de sortie" not in texte

    def test_la_competence_principale_en_anglais(self, en, ia, activite_avec_sortie):
        """⚠️ Et son bloc de CONTEXTE. Premier essai : `doit_dire_anglais` seul
        — vert avec le contexte remis en français, parce que « Activité: » et
        « Tâches: » ne contiennent pas le mot « français ». La règle générale
        voit la VARIANTE du prompt ; elle ne voit pas les intitulés du contexte,
        qui sont pourtant le texte le plus long du message."""
        aid = activite_avec_sortie[1]
        en.post("/competence/generate/%d" % aid, json={})
        doit_dire_anglais(ia)
        texte = ia.texte
        assert "Results of the activity (RESULT)" in texte, texte[:600]
        assert "Résultats de l'activité" not in texte
        assert "Tâches:" not in texte

    def test_les_capacites_par_resultat_en_anglais(self, en, ia, activite_avec_sortie):
        """⚠️ C'était le trou le plus coûteux : ces libellés sont ENREGISTRÉS
        (Savoir.description, SavoirFaire.description, Softskill.habilete). Nés
        en français chez un compte anglais, ils y restaient — rien ne les
        retraduit ensuite, contrairement aux rôles (`role_i18n`)."""
        aid = activite_avec_sortie[1]
        en.post("/competence/result_links/generate/%d" % aid, json={})
        doit_dire_anglais(ia)

    def test_le_plan_de_formation_porte_la_langue_dans_son_contexte(self, app, ia):
        """Troisième façon de dire la langue : un champ du contexte JSON."""
        from Code.routes.plan_formation import _plan_ia
        activites = [{
            "activity_id": 1, "activity_name": "Chiffrer l'offre",
            "competence": "Tenir le chiffrage", "demonstrated_label": "1",
            "required_label": "3", "gap": -2, "results_in_gap": [], "capabilities": [],
        }]
        with app.test_request_context():
            _plan_ia(activites, {"heures_semaine": 4, "semaines": 6}, "en")
        assert ia.envois, "aucun appel au modèle"
        assert '"langue": "English"' in ia.texte

    def test_le_chatbot_ne_renvoie_plus_un_contexte_FRANCAIS(self, en, ia):
        """Le prompt système anglais fait 4 100 signes, mais le bloc de contexte
        revient à CHAQUE tour : ses intitulés étaient en dur en français, et
        c'est une ancre française permanente dans la conversation."""
        en.post("/api/chatbot/chat", json={"activity": CHARGE_ACTIVITE,
                                           "history": [], "demarrage": True})
        texte = ia.texte
        assert "FULL ACTIVITY CONTEXT" in texte
        assert "CONTEXTE COMPLET" not in texte
        assert "TÂCHES DÉJÀ SAISIES" not in texte


class TestLaConsigneNEstPasPorteeParDuFrancais:
    """« Réponds en English. » — le mot y est, la phrase est française."""

    def test_le_diagnostic_demande_en_anglais_EN_ANGLAIS(self, en, ia):
        en.post("/diagnostic/plan", json={"user_id": 1, "activity_id": 1,
                                          "data_id": 999999,
                                          "families": ["ABILITY_TO_ACT"]})
        assert "Answer in English" in ia.texte
        assert "Réponds en" not in ia.texte
        assert "Contexte:" not in ia.texte

    def test_le_positionnement_HSC_demande_en_anglais_EN_ANGLAIS(self, en, ia):
        en.post("/hsc/position", json={"hsc_name": "Arbitrage",
                                       "responses": ["a tranché seul"],
                                       "examples": "un arbitrage en comité"})
        texte = ia.texte
        assert "Answer in English" in texte
        assert "Réponds en" not in texte
        assert "Réponses situations" not in texte
        assert "Real-life example" in texte


class TestLesReplisParlentLaLangue:
    """Sans clé IA — le cas le plus courant chez un client qui n'en a pas."""

    def test_les_savoirs_proposes_sans_IA_sont_en_anglais(self, en):
        r = en.post("/propose_savoirs/propose", json=CHARGE_ACTIVITE)
        assert r.status_code == 200
        textes = " ".join(r.get_json()["proposals"])
        assert "Know the main procedures" in textes
        assert "Connaître" not in textes
        # « » est une convention FRANÇAISE : pas de guillemets français ici.
        assert "«" not in textes

    def test_les_savoir_faire_proposes_sans_IA_sont_en_anglais(self, en):
        r = en.post("/propose_savoir_faires/propose", json=CHARGE_ACTIVITE)
        textes = " ".join(r.get_json()["proposals"])
        assert "Apply the main procedures" in textes
        assert "Appliquer" not in textes

    def test_les_HSC_proposees_sans_IA_sont_en_anglais(self, en):
        r = en.post("/propose_softskills/propose", json=CHARGE_ACTIVITE)
        props = r.get_json()["proposals"]
        assert props, "le repli ne rend rien"
        assert all("Develop" in p["habilete"] for p in props), props
        assert all("Développer" not in p["habilete"] for p in props)

    def test_le_repli_francais_n_a_pas_bouge(self, fr):
        r = fr.post("/propose_savoirs/propose", json=CHARGE_ACTIVITE)
        textes = " ".join(r.get_json()["proposals"])
        assert "Connaître les procédures principales" in textes

    def test_le_contexte_envoye_suit_la_langue(self):
        """Un bloc de contexte français sous un prompt anglais est le signal
        mixte qui fait repasser le modèle au français : c'est le texte le plus
        long du message, il pèse plus que la consigne."""
        from Code.routes.propose_common import build_activity_context
        ctx_en = build_activity_context({"title": "Chiffrer", "tasks": ["Relever"]}, "en")
        assert "# Activity" in ctx_en and "# Tasks" in ctx_en
        assert "Activité" not in ctx_en and "Tâches" not in ctx_en
        ctx_fr = build_activity_context({"title": "Chiffrer"}, "fr")
        assert "# Activité" in ctx_fr

    def test_le_titre_est_retrouve_dans_les_DEUX_langues(self):
        """⚠️ Le repli relit le contexte pour y prendre le titre : il cherchait
        « Titre: », qui n'existe plus quand le contexte est anglais."""
        from Code.routes.propose_common import build_activity_context, dummy_from_context
        ctx = build_activity_context({"title": "Chiffrer l'offre"}, "en")
        assert "Chiffrer l'offre" in " ".join(dummy_from_context(ctx, "savoir", "en"))

    def test_les_refus_de_la_traduction_HSC_suivent_la_langue(self, en):
        """Trois refus de `/translate_softskills/translate` étaient écrits en dur
        en français, et c'est la modale « Traduire les soft skills » qui les
        affiche telle quelle."""
        r = en.post("/translate_softskills/translate", json={"user_input": ""})
        assert r.status_code == 400
        assert "No text entered" in r.get_json()["error"]

    def test_sans_cle_le_message_de_skills_suit_la_langue(self, en, monkeypatch):
        """« Clé IA non renseignée » est un MARQUEUR lu par optiqAiCheck ; sa
        regex porte aussi la forme anglaise, la traduire est sûr."""
        import Code.routes.skills as S
        from Code import prompts as P
        monkeypatch.setattr(P, "_store", Marqueurs(), raising=False)
        monkeypatch.setattr(S, "get_openai_key", lambda: None)
        r = en.post("/skills/propose", json=dict(CHARGE_ACTIVITE,
                                                 tasks=["Relever les besoins"]))
        assert "AI key not configured" in r.get_json()["error"]


class TestLeChangelogPorteLesDeuxLangues:
    """Il est MIS EN CACHE et relu par des comptes de langues différentes."""

    def test_le_dernier_recours_est_bilingue(self):
        from Code.routes.changelog import _fallback_changelog
        for it in _fallback_changelog()["items"]:
            assert it.get("title_en") and it.get("desc_en"), it

    def test_la_traduction_se_fait_a_la_LECTURE(self, app):
        """⚠️ Jamais avant la mise en cache : la langue du premier lecteur
        gèlerait celle de tous les suivants pendant une heure."""
        from Code.routes.changelog import _servir
        data = {"items": [{"title": "Nouveau", "desc": "Du neuf",
                           "title_en": "New", "desc_en": "Something new"}]}
        with app.test_request_context():
            from flask import session
            session["lang"] = "en"
            vu = _servir(data)
        assert vu["items"][0]["title"] == "New"
        # L'original n'est pas touché : c'est LUI qui reste en cache.
        assert data["items"][0]["title"] == "Nouveau"

    def test_la_ROUTE_sert_la_langue_du_lecteur(self, en, monkeypatch):
        """⚠️ `_servir` juste n'est pas un câblage juste : la route rendait
        `jsonify({**data})` sans passer par lui. On neutralise le fichier curé
        (qui a la priorité absolue) pour atteindre le chemin généré."""
        import Code.routes.changelog as C
        monkeypatch.setattr(C, "_read_curated", lambda: None)
        monkeypatch.setattr(C, "_get_recent_commits", lambda n=30: [])
        monkeypatch.setattr(C, "_changelog_cache", {}, raising=False)
        r = en.get("/api/changelog")
        titres = " ".join(i["title"] for i in r.get_json()["items"])
        assert "New features" in titres
        assert "Nouvelles fonctionnalités" not in titres

    def test_un_changelog_sans_items_ne_casse_pas(self, app):
        from Code.routes.changelog import _servir
        with app.test_request_context():
            assert _servir({"erreur": "rien"}) == {"erreur": "rien"}


class TestLesPropositionsIASontDesLectures:
    """La porte d'écriture refusait des routes qui n'écrivent rien."""

    LECTURES = ("/propose_savoirs/propose", "/propose_savoir_faires/propose",
                "/propose_softskills/propose", "/propose_aptitudes/propose",
                "/propose_aptitudes/feasibility", "/translate_softskills/translate",
                "/skills/propose", "/diagnostic/plan", "/hsc/position",
                "/api/chatbot/chat")

    @pytest.mark.parametrize("url", LECTURES)
    def test_la_porte_les_laisse_passer(self, app, url):
        """⚠️ Sur une carto COMMUNE, `can_edit` rend faux pour un champion : il
        recevait `lecture_seule` — le motif réservé à `user` — pour une route
        qui ne fait qu'appeler l'IA. Aucune proposition n'était joignable."""
        from Code.ecriture import porte
        with app.test_request_context("/"):
            assert porte(url, "POST", en_test=False) is None, url

    @pytest.mark.parametrize("url,methode", [
        ("/skills/add", "POST"), ("/skills/12", "DELETE"),
        ("/diagnostic/save", "POST"), ("/hsc/descriptors", "POST"),
    ])
    def test_ce_qu_elles_preparent_reste_sous_la_porte(self, app, url, methode):
        """Proposer n'est pas enregistrer. ⚠️ Les trois préfixes sont PRÉCIS :
        exempter `/skills` ou `/hsc` aurait ouvert leurs écritures.
        ⚠️ `porte()` appelle `current_user()` dès que le chemin n'est pas
        exempté : il lui faut un contexte de requête, sinon le cas tombe pour
        une raison qui n'est pas la sienne."""
        from Code.ecriture import porte
        with app.test_request_context("/"):
            assert porte(url, methode, en_test=False) == "non_connecte", url

    def test_aucune_LIGNE_ne_naît_derrière_ces_routes(self, en, app):
        """⚠️ L'exemption ouvre dix POST à TOUT compte connecté, `user` compris.
        Elle ne tient que si ces routes n'écrivent rien — et le vérifier en
        lisant les imports ne suffit pas : un helper venu d'ailleurs pourrait
        écrire. On COMPTE donc les lignes, avant et après.

        C'est le défaut que `Code/ecriture.py` existe pour fermer : si l'une de
        ces routes se mettait à écrire, un compte en lecture seule écrirait."""
        from Code.models.models import (Activities, Aptitude, Competency, Data,
                                        Savoir, SavoirFaire, Softskill, Task,
                                        Tool)
        modeles = (Activities, Aptitude, Competency, Data, Savoir, SavoirFaire,
                   Softskill, Task, Tool)

        def compter():
            with app.app_context():
                return {m.__name__: m.query.count() for m in modeles}

        avant = compter()
        for url, charge in ROUTES_SANS_DECOR:
            en.post(url, json=charge)
        apres = compter()
        bouge = {k: (avant[k], apres[k]) for k in avant if avant[k] != apres[k]}
        assert not bouge, "ces routes ont ÉCRIT : %s" % bouge

    @pytest.mark.parametrize("module", [
        "Code.routes.propose_savoirs", "Code.routes.propose_savoir_faires",
        "Code.routes.propose_softskills", "Code.routes.propose_aptitudes",
        "Code.routes.translate_softskills",
    ])
    def test_ces_blueprints_n_ecrivent_RIEN(self, module):
        """L'exemption ne tient que parce que c'est vrai. On le vérifie sur le
        MODULE CHARGÉ, pas sur son source : l'arbre d'image n'a pas les `.py`."""
        mod = importlib.import_module(module)
        for nom in ("db", "commit", "add"):
            assert not hasattr(mod, nom), "%s expose %s" % (module, nom)
        from Code.extensions import db
        vus = [n for n in dir(mod) if getattr(mod, n, None) is db]
        assert not vus, "%s tient la session SQLAlchemy : %s" % (module, vus)


class TestAucunPromptNeVitDansUneRoute:
    """Huit prompts système étaient ÉCRITS DANS les routes.

    ⚠️ Ils nomment les référentiels (XP X50-766, CIF) : c'est du savoir-faire,
    et le catalogue existe précisément pour qu'il soit chiffré dans l'image
    client au lieu de voyager dans le bytecode d'une route.

    ⚠️ Le cliquet porte sur ce que la route DEMANDE au catalogue, pas sur le
    texte envoyé : un prompt réécrit en dur contiendrait peut-être encore le
    mot « English » — c'est d'ailleurs ce que faisaient les deux prompts des
    aptitudes — et la consigne de langue, seule, ne l'aurait pas vu. La clé
    manquante, elle, se voit.
    ⚠️ Et il ne lit AUCUN source : l'arbre d'image n'a pas les `.py`.
    """

    ATTENDU = [
        ("/propose_savoirs/propose", CHARGE_ACTIVITE,
         {"propose.savoirs.header.en", "propose.system.en"}),
        ("/propose_savoir_faires/propose", CHARGE_ACTIVITE,
         {"propose.savoir_faires.header.en", "propose.system.en"}),
        ("/propose_softskills/propose", CHARGE_ACTIVITE,
         {"propose.softskills.header.en", "referential.x50_766.en",
          "propose.softskills.system.en"}),
        ("/propose_aptitudes/propose", CHARGE_ACTIVITE,
         {"propose.aptitudes.inclusion_scoring",
          "propose.aptitudes.inclusion_scoring.system.en"}),
        ("/propose_aptitudes/feasibility",
         {"activity_name": "Chiffrer", "inclusion_scoring_json": "{}",
          "assistive_products": []},
         {"propose.aptitudes.handicap_icf",
          "propose.aptitudes.handicap_icf.system.en"}),
        ("/skills/propose", dict(CHARGE_ACTIVITE, tasks=["Relever les besoins"]),
         {"skills.competencies.en", "skills.system.en"}),
        ("/translate_softskills/translate",
         {"user_input": "sait arbitrer", "activity": CHARGE_ACTIVITE},
         {"translate.hsc.en", "referential.x50_766.en", "translate.hsc.system.en"}),
        ("/hsc/position", {"hsc_name": "Arbitrage", "responses": ["a tranché"]},
         {"hsc.positioning.system.en"}),
        ("/diagnostic/plan", {"user_id": 1, "activity_id": 1, "data_id": 999999,
                              "families": ["ABILITY_TO_ACT"]},
         {"diagnostic.plan.system.en"}),
        ("/api/chatbot/chat", {"activity": CHARGE_ACTIVITE, "history": [],
                               "demarrage": True},
         {"chatbot.system.en", "chatbot.mode_creer.en"}),
    ]

    @pytest.mark.parametrize("url,charge,cles", ATTENDU,
                             ids=[u for u, _, _ in ATTENDU])
    def test_la_route_demande_ses_prompts_au_catalogue(self, en, ia, url, charge, cles):
        en.post(url, json=charge)
        demandees = set(ia.magasin.demandees)
        assert cles <= demandees, "%s : clés absentes %s" % (url, sorted(cles - demandees))

    @pytest.mark.parametrize("url", ["/competence/generate/%d",
                                     "/competence/result_links/generate/%d"])
    def test_la_consigne_de_langue_FERME_le_message(self, en, ia,
                                                    activite_avec_sortie, url):
        """La variante du prompt dit déjà la langue ; la consigne finale la
        redit en DERNIER, juste après le schéma. ⚠️ Depuis le passage en
        variantes, plus aucun autre cas ne la garde : une ligne que rien ne
        garde est une ligne qui pourrit."""
        en.post(url % activite_avec_sortie[1], json={})
        assert "Answer in English" in ia.texte, ia.texte[-400:]

    @pytest.mark.parametrize("url,cle", [
        ("/competence/generate/%d", "result_capabilities.competency.system.en"),
        ("/competence/result_links/generate/%d", "result_capabilities.sfhsc.system.en"),
    ])
    def test_les_prompts_de_competence_sont_des_VARIANTES(self, en, ia,
                                                          activite_avec_sortie, url, cle):
        """⚠️ Mesuré : avec un prompt français et une consigne anglaise ajoutée,
        `/competence/generate` envoyait 6 marqueurs français pour 3 anglais."""
        en.post(url % activite_avec_sortie[1], json={})
        assert cle in set(ia.magasin.demandees), sorted(ia.magasin.demandees)

    def test_l_onboarding_demande_son_prompt_systeme(self, en, ia, activite_avec_sortie):
        rid = activite_avec_sortie[2]
        en.post("/roles/%d/onboarding/generate" % rid, json={"hsc_list": ["Arbitrage"]})
        demandees = set(ia.magasin.demandees)
        assert {"onboarding.plan.en", "onboarding.system.en"} <= demandees, demandees

    def test_l_enrichissement_d_import_passe_la_langue(self, app, ia, en):
        """⚠️ `import.enrich` rédige « match_reason » dans
        « langue_des_remarques » quand elle est fournie — et ce chemin-ci ne la
        fournissait pas. `import_hub` la passe depuis toujours : deux chemins du
        MÊME prompt, dont un seul disait la langue."""
        from Code.routes.import_full import _try_openai_enrich
        with app.test_request_context("/"):
            from flask import session
            session["lang"] = "en"
            _try_openai_enrich([{"activity_name_excel": "Identify Part"}],
                               [{"id": 1, "name": "Chiffrer l'offre"}])
        assert ia.envois, "aucun appel au modèle"
        assert '"langue_des_remarques": "English"' in ia.texte


# ────────────────── Le catalogue lui-même (absent de l'image) ──────────────────

try:
    from Code.prompts.catalog import PROMPTS as _CATALOGUE
except Exception:                                      # pragma: no cover
    _CATALOGUE = None

sans_catalogue = pytest.mark.skipif(
    _CATALOGUE is None,
    reason="Code/prompts/catalog.py est exclu de l'image client (.dockerignore) : "
           "il y est remplacé par prompts.enc, déchiffré par PROMPTS_KEY.",
)

# ⚠️ Deux inventaires, et deux raisons différentes. Un prompt neuf sans
# variante de langue doit entrer dans l'un ou l'autre — ou dire sa langue.
#
# 1. Ce qui ne rend PAS de prose : il n'y a pas de langue à porter.
SANS_PROSE = {
    # Visio : elles renvoient des coordonnées, et recopient les libellés
    # fournis sans les traduire (« conserve exactement les labels »).
    "carto.decisions.system", "carto.reposition.system",
    # Une ligne de rôle, sans un mot de sortie ; la consigne de langue vit dans
    # `skills.competencies`, via [[lang_instr]].
    "skills.system",
    # Les prompts UTILISATEUR des aptitudes : leur consigne de langue est dans
    # le prompt SYSTÈME qui les accompagne (`…system.fr` / `.en`).
    "propose.aptitudes.inclusion_scoring", "propose.aptitudes.handicap_icf",
}

# 2. Ce dont la langue est dite par la ROUTE, au message utilisateur.
#    ⚠️ Cet inventaire est VIDE, et c'est le résultat de la mesure : un prompt
#    français suivi d'un « Answer in English » envoyait, pour cinq routes,
#    DEUX FOIS PLUS de français que d'anglais (le prompt pèse plus que son
#    post-scriptum). Les cinq sont passées en variantes. La liste reste, parce
#    que c'est elle qui obligera à décider pour le prompt suivant — et la
#    consigne ajoutée reste gardée par
#    `TestLaConsigneNEstPasPorteeParDuFrancais`, qui vérifie en plus qu'elle
#    n'est pas elle-même portée par du français.
LANGUE_DITE_PAR_LA_ROUTE = set()      # ⚠️ vide, et c'est voulu : voir plus bas

MOTS_FRANCAIS = ("Réponds", "Rédige", "Tu es ", "Vous êtes", "français",
                 "Réponses", "Donne pour", "Analyse UNIQUEMENT")


@sans_catalogue
class TestLeCatalogueEstComplet:

    def test_le_catalogue_est_bien_garni(self):
        """⚠️ Garde-fou de volume : si un jour les repères changent et que
        l'analyse ne trouve plus rien, les contrôles passeraient au vert en ne
        lisant plus RIEN."""
        assert len(_CATALOGUE) >= 45, len(_CATALOGUE)

    def test_chaque_paire_fr_en_est_complete(self):
        manque = []
        for cle in _CATALOGUE:
            m = re.match(r"^(.*)\.(fr|en)$", cle)
            if not m:
                continue
            jumelle = "%s.%s" % (m.group(1), "en" if m.group(2) == "fr" else "fr")
            if jumelle not in _CATALOGUE:
                manque.append(jumelle)
        assert not manque, "variantes absentes : %s" % sorted(manque)

    def test_la_variante_anglaise_est_vraiment_en_anglais(self):
        """Un `.en` recopié du français rend du français, et rien ne le dit."""
        fautifs = {}
        for cle, texte in _CATALOGUE.items():
            if not cle.endswith(".en"):
                continue
            vus = [m for m in MOTS_FRANCAIS if m in texte]
            if vus:
                fautifs[cle] = vus
        assert not fautifs, fautifs

    def test_aucun_prompt_ne_promet_UNE_SEULE_langue(self):
        """`changelog.system` disait « Langue : français uniquement », et son
        résultat s'affiche dans la fenêtre de bienvenue de chaque page."""
        fautifs = [c for c, t in _CATALOGUE.items()
                   if re.search(r"fran[cç]ais uniquement|in French only|only in French", t, re.I)]
        assert not fautifs, fautifs

    def test_un_prompt_sans_variante_dit_sa_langue_ou_est_inventorie(self):
        """⚠️ Le cliquet qui compte : un prompt neuf sans variante de langue
        oblige à décider — il dit sa langue, ou il entre dans `SANS_PROSE` avec
        la raison écrite."""
        muets = []
        for cle, texte in _CATALOGUE.items():
            if (re.search(r"\.(fr|en)$", cle) or cle in SANS_PROSE
                    or cle in LANGUE_DITE_PAR_LA_ROUTE):
                continue
            if not re.search(r"langue|language|anglais|english|fran[cç]ais|\[\[lang", texte, re.I):
                muets.append(cle)
        assert not muets, (
            "ces prompts ne disent pas dans quelle langue répondre : %s" % sorted(muets))

    def test_le_changelog_demande_LES_DEUX_langues(self):
        """⚠️ On vise le SCHÉMA, pas le token. Premier essai : `"title_en" in t`
        — vert même le schéma vidé, parce que la consigne juste au-dessus cite
        « title_en/desc_en » en toutes lettres. Un cliquet qui cherche une
        chaîne doit borner sa zone, et l'homonyme peut être une ligne qu'on
        vient d'écrire soi-même."""
        t = _CATALOGUE["changelog.system"]
        assert '"title_en":"' in t, "le schéma ne demande pas le titre anglais"
        assert '"desc_en":"' in t, "le schéma ne demande pas la description anglaise"

    def test_la_competence_est_demandee_dans_LES_DEUX_langues(self):
        """La compétence est stockée en FR et en EN (`Competency.description_fr`
        / `_en`) : les deux variantes du prompt doivent le demander."""
        for lang in ("fr", "en"):
            t = _CATALOGUE["result_capabilities.competency.system.%s" % lang]
            assert "_fr" in t and "_en" in t, lang

    def test_les_prompts_de_prose_ont_TOUS_leur_variante(self):
        """⚠️ C'est la première des trois façons de dire la langue, et la seule
        qui ne se batte pas contre son propre support : le prompt entier est
        écrit dans la langue demandée."""
        for base in ("diagnostic.plan.system", "hsc.positioning.system",
                     "result_capabilities.competency.system",
                     "result_capabilities.sfhsc.system",
                     "skills.system", "skills.competencies"):
            for lang in ("fr", "en"):
                assert "%s.%s" % (base, lang) in _CATALOGUE, base
            assert base not in _CATALOGUE, base + " : l'ancienne clé survit"

    def test_les_prompts_rapatries_des_routes_sont_la(self):
        """Les huit prompts système qui vivaient DANS les routes : ils nomment
        les référentiels (X50-766, CIF), c'est du savoir-faire — il appartient
        au catalogue chiffré, pas au bytecode d'une route."""
        for base in ("propose.aptitudes.inclusion_scoring.system",
                     "propose.aptitudes.handicap_icf.system",
                     "propose.softskills.system", "translate.hsc.system",
                     "onboarding.system"):
            for lang in ("fr", "en"):
                assert "%s.%s" % (base, lang) in _CATALOGUE, base

    def test_tous_les_placeholders_sont_REMPLIS(self, ia_reelle, en_reel):
        """Un `[[nom]]` oublié part TEL QUEL vers le modèle : `get_prompt`
        remplace ce qu'on lui donne et laisse le reste littéral, sans rien
        lever. C'est le seul contrôle qui a besoin du vrai catalogue."""
        faux = ia_reelle
        for url, charge in ROUTES_SANS_DECOR:
            faux.envois.clear()
            en_reel.post(url, json=charge)
            restes = re.findall(r"\[\[[a-z0-9_]+\]\]", faux.texte)
            assert not restes, "%s : placeholders non remplis %s" % (url, set(restes))


@pytest.fixture
def ia_reelle(monkeypatch):
    """Le VRAI catalogue, et un client qui enregistre."""
    faux = FauxClient()
    import Code.ai_client as AC
    monkeypatch.setattr(AC, "make_ai_client",
                        lambda timeout=None: (faux, "modele-de-test", None))
    from Code import prompts as P
    monkeypatch.setattr(P, "_store", dict(_CATALOGUE or {}), raising=False)
    for nom in MODULES_AVEC_CLE:
        mod = importlib.import_module(nom)
        if hasattr(mod, "get_openai_key"):
            monkeypatch.setattr(mod, "get_openai_key", lambda: "sk-de-test")
    return faux


@pytest.fixture
def en_reel(en):
    return en
