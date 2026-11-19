# -*- coding: utf-8 -*-
"""Atelier du hub — le plan de travail et son miroir.

Le hub est un service SÉPARÉ (son propre Cloud Run, son propre workflow) : ces
cas lisent `hub/atelier.py` comme `test_124` lit `hub/courrier.py`.

⚠️ Ils SAUTENT dans l'arbre d'image (bytecode-only) : `spec_from_file_location`
veut le chemin exact d'un `.py`, et la purge du Dockerfile les retire. Un test
qui rougirait à chaque exécution sur l'instance n'est plus lu — et le jour où
il a raison, personne ne regarde.

Deux promesses sont gardées ici, et elles comptent plus que le reste :

1. **Sans `HUB_ATELIER_DB`, rien ne lève.** L'atelier doit s'ouvrir et
   s'écrire entièrement dans le navigateur. Un outil de travail qui exige un
   secret avant la première note n'est pas un outil de travail.
2. **L'atelier n'écrit JAMAIS dans une base d'instance.** `HUB_DBS_B64` est en
   lecture seule (voir `courrier.py`) ; l'atelier écrit, il lui faut donc une
   base à lui. Confondre les deux ferait écrire le hub dans la base d'un
   client.
"""
import ast
import importlib.util
import io
import json
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = os.path.join(RACINE, "hub")
SRC = os.path.join(HUB, "atelier.py")
SRC_MOD = os.path.join(HUB, "atelier_modeles.py")


def _module():
    """Un module NEUF à chaque test : `atelier` garde son moteur dans un
    global, et deux cas qui partagent une base SQLite se marchent dessus."""
    if not os.path.exists(SRC):
        pytest.skip("hub/ en bytecode — service séparé, sources absentes")
    spec = importlib.util.spec_from_file_location("hub_atelier_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fichier(nom):
    chemin = os.path.join(HUB, nom)
    if not os.path.exists(chemin):
        pytest.skip("hub/ en bytecode — service séparé, sources absentes")
    return io.open(chemin, encoding="utf-8").read()


def _code_py(nom):
    """Les mots du CODE, sans les commentaires ni les docstrings.

    ⚠️ Ces fichiers s'expliquent beaucoup : une interdiction cherchée dans le
    texte brut se déclenche sur le commentaire qui dit justement pourquoi on
    ne fait pas la chose. Les littéraux de chaîne, eux, RESTENT — c'est
    précisément là que se cacherait un `os.getenv("HUB_DBS")`.
    """
    arbre = ast.parse(_fichier(nom))
    docs = set()
    for n in ast.walk(arbre):
        corps = getattr(n, "body", None)
        if not isinstance(corps, list) or not corps:
            continue
        if not isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)):
            continue
        tete = corps[0]
        if (isinstance(tete, ast.Expr) and isinstance(tete.value, ast.Constant)
                and isinstance(tete.value.value, str)):
            docs.add(id(tete.value))
    mots = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if id(n) not in docs:
                mots.append(n.value)
        elif isinstance(n, ast.Name):
            mots.append(n.id)
        elif isinstance(n, ast.Attribute):
            mots.append(n.attr)
        elif isinstance(n, ast.Import):
            mots.extend(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            mots.append(n.module or "")
            mots.extend(a.name for a in n.names)
    return "\n".join(mots)


def _code_js(nom):
    """Idem côté JavaScript : blocs `/* */` et lignes `//` retirés.

    On ne retire QUE les lignes entièrement commentées : couper à chaque `//`
    mangerait les URL des littéraux (`http://www.w3.org/2000/svg`)."""
    src = re.sub(r"/\*.*?\*/", "", _fichier(nom), flags=re.S)
    return "\n".join(l for l in src.split("\n")
                     if not l.strip().startswith("//"))


@pytest.fixture
def at():
    return _module()


@pytest.fixture
def mod():
    if not os.path.exists(SRC_MOD):
        pytest.skip("hub/ en bytecode — service séparé, sources absentes")
    spec = importlib.util.spec_from_file_location("hub_atelier_modeles_test",
                                                  SRC_MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def env(tmp_path):
    """Une base SQLite jetable, passée explicitement — jamais os.environ : un
    test qui laisse traîner une variable en contamine un autre."""
    return {"HUB_ATELIER_DB": "sqlite:///" + str(tmp_path / "atelier.db")}


DOC = json.dumps({"v": 1, "active": "t1", "toiles": [
    {"id": "t1", "nom": "Plan", "noeuds": [], "liens": [],
     "cam": {"x": 0, "y": 0, "k": 1}}]})

PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
       "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


# ══════════════════════════════════════════════════════════════════════════
#  1 · La base de l'atelier
# ══════════════════════════════════════════════════════════════════════════

class TestLaBaseDeLAtelier:

    def test_sans_variable_RIEN_ne_leve(self, at):
        """La promesse n°1 : l'atelier marche sans miroir, et le dit."""
        vide = {}
        assert at.disponible(vide) is False
        assert at.etat(vide)["miroir"] is False
        assert at.lire("principale", vide) == {
            "miroir": False, "erreur": None, "rev": 0, "contenu": None}
        assert at.ecrire("principale", DOC, env=vide)["ok"] is False
        assert at.pieces_connues(["p1_a"], vide) == []
        assert at.piece_lire("p1_a", vide) is None
        assert at.piece_ecrire("p1_a", "image/png", PNG, vide)["ok"] is False

    def test_une_variable_VIDE_n_est_pas_une_variable_absente(self, at):
        """⚠️ Le piège qui a fait croire des mois durant que l'envoi de mail
        était configuré : `getenv(cle, defaut)` ne regarde JAMAIS son défaut
        quand la variable existe et vaut la chaîne vide."""
        assert at.url_base({"HUB_ATELIER_DB": ""}) == ""
        assert at.url_base({"HUB_ATELIER_DB": "   "}) == ""
        assert at.disponible({"HUB_ATELIER_DB": ""}) is False

    def test_le_pilote_postgres_est_NOMME(self, at):
        """⚠️ `postgresql://` seul désignait psycopg2 en SQLAlchemy 2.0 et
        désigne psycopg (v3) depuis 2.1 : l'image du hub a déjà tué toutes
        ses lectures sur un saut de version que personne n'avait décidé."""
        u = at.url_base({"HUB_ATELIER_DB": "postgresql://u:p@h/db"})
        assert u.startswith("postgresql+psycopg2://")

    def test_l_ancien_schema_de_neon_est_converti(self, at):
        u = at.url_base({"HUB_ATELIER_DB": 'postgres://u:p@h/db'})
        assert u.startswith("postgresql+psycopg2://")

    def test_les_guillemets_colles_par_gcloud_sont_retires(self, at):
        u = at.url_base({"HUB_ATELIER_DB": '"sqlite:///x.db"'})
        assert u == "sqlite:///x.db"


# ══════════════════════════════════════════════════════════════════════════
#  2 · La toile
# ══════════════════════════════════════════════════════════════════════════

class TestLaToile:

    def test_ecrire_puis_relire(self, at, env):
        assert at.lire("principale", env) == {
            "miroir": True, "erreur": None, "rev": 0, "contenu": None,
            "maj": None}
        r = at.ecrire("principale", DOC, 0, env)
        assert r["ok"] and r["rev"] == 1
        lu = at.lire("principale", env)
        assert lu["miroir"] is True and lu["rev"] == 1
        assert json.loads(lu["contenu"])["active"] == "t1"
        assert lu["maj"]

    def test_chaque_ecriture_avance_la_revision(self, at, env):
        assert at.ecrire("principale", DOC, 0, env)["rev"] == 1
        assert at.ecrire("principale", DOC, 1, env)["rev"] == 2
        assert at.ecrire("principale", DOC, 2, env)["rev"] == 3

    def test_une_revision_perimee_est_REFUSEE(self, at, env):
        """⚠️ Pas un verrou : un garde-fou. Un seul compte écrit ici, mais
        deux onglets sont vite ouverts, et le second ne doit pas remplacer en
        silence le travail du premier."""
        at.ecrire("principale", DOC, 0, env)
        at.ecrire("principale", DOC, 1, env)
        r = at.ecrire("principale", DOC, 0, env)
        assert r["ok"] is False and r["conflit"] is True
        assert r["rev"] == 2          # on rend la version en place
        assert at.lire("principale", env)["rev"] == 2   # rien n'a bougé

    def test_sans_revision_on_ecrase_volontairement(self, at, env):
        """L'import d'une sauvegarde ne connaît aucune révision : il remplace,
        et c'est l'utilisateur qui l'a confirmé à l'écran."""
        at.ecrire("principale", DOC, 0, env)
        assert at.ecrire("principale", DOC, None, env)["ok"] is True

    def test_une_cle_hostile_est_refusee(self, at, env):
        for mauvaise in ("../../etc/passwd", "a b", "", "x" * 65, "a;drop"):
            assert at.lire(mauvaise, env)["erreur"], mauvaise
            assert at.ecrire(mauvaise, DOC, env=env)["ok"] is False, mauvaise

    def test_plusieurs_toiles_cohabitent(self, at, env):
        at.ecrire("principale", DOC, 0, env)
        at.ecrire("brouillon", DOC, 0, env)
        assert at.lire("principale", env)["rev"] == 1
        assert at.lire("brouillon", env)["rev"] == 1
        assert at.etat(env)["toiles"] == 2

    def test_une_toile_trop_lourde_est_refusee(self, at, env):
        """Au-delà, c'est un emballement (collage en rafale, boucle
        d'enregistrement) : mieux vaut refuser que gonfler la base sans fin."""
        r = at.ecrire("principale", "x" * (at.TAILLE_MAX + 1), env=env)
        assert r["ok"] is False and "lourde" in r["erreur"]
        assert at.lire("principale", env)["rev"] == 0

    def test_un_dictionnaire_est_serialise_pour_l_appelant(self, at, env):
        at.ecrire("principale", {"v": 1, "toiles": []}, 0, env)
        assert json.loads(at.lire("principale", env)["contenu"])["v"] == 1

    def test_une_base_injoignable_rend_une_erreur_pas_une_exception(self, at):
        mauvais = {"HUB_ATELIER_DB":
                   "postgresql://personne:rien@127.0.0.1:1/absente"
                   "?connect_timeout=1"}
        lu = at.lire("principale", mauvais)
        assert lu["miroir"] is False and lu["erreur"]
        assert at.etat(mauvais)["miroir"] is False


# ══════════════════════════════════════════════════════════════════════════
#  3 · Les pièces (captures collées)
# ══════════════════════════════════════════════════════════════════════════

class TestLesPieces:

    def test_une_piece_n_est_rangee_qu_une_fois(self, at, env):
        """Une capture est IMMUABLE. C'est tout l'intérêt de la sortir du
        document : sans ça, chaque enregistrement repousserait plusieurs
        méga-octets d'images inchangées pour un titre corrigé."""
        assert at.piece_ecrire("p1_abc", "image/png", PNG, env) == {
            "ok": True, "deja": False}
        assert at.piece_ecrire("p1_abc", "image/png", PNG, env) == {
            "ok": True, "deja": True}
        assert at.etat(env)["pieces"] == 1

    def test_le_miroir_dit_ce_qu_il_a_deja(self, at, env):
        at.piece_ecrire("p1_abc", "image/png", PNG, env)
        assert at.pieces_connues(["p1_abc", "p2_zzz"], env) == ["p1_abc"]
        assert at.pieces_connues([], env) == []

    def test_une_piece_se_relit_a_l_identique(self, at, env):
        at.piece_ecrire("p1_abc", "image/png", PNG, env)
        p = at.piece_lire("p1_abc", env)
        assert p["id"] == "p1_abc" and p["mime"] == "image/png"
        assert p["donnees"] == PNG

    def test_une_piece_inconnue_rend_None(self, at, env):
        assert at.piece_lire("p9_inconnue", env) is None

    def test_un_identifiant_hostile_est_refuse(self, at, env):
        assert at.piece_ecrire("../x", "image/png", PNG, env)["ok"] is False
        assert at.piece_lire("../x", env) is None
        assert at.pieces_connues(["../x"], env) == []

    def test_une_piece_trop_lourde_est_refusee(self, at, env):
        gros = "data:image/png;base64," + "A" * (at.PIECE_MAX + 1)
        assert at.piece_ecrire("p1_gros", "image/png", gros, env)["ok"] is False

    def test_seule_une_data_url_valide_entre(self, at):
        """Ranger une chaîne qu'aucun navigateur ne saura réafficher, c'est
        perdre la capture en silence."""
        assert at.data_url_valide(PNG) is True
        assert at.data_url_valide("") is False
        assert at.data_url_valide("pas une data-url") is False
        assert at.data_url_valide("javascript:alert(1)") is False
        assert at.data_url_valide("data:image/png,pasdebase64") is False

    def test_une_piece_devenue_inutile_s_oublie(self, at, env):
        at.piece_ecrire("p1_abc", "image/png", PNG, env)
        assert at.piece_oublier("p1_abc", env) is True
        assert at.piece_lire("p1_abc", env) is None


# ══════════════════════════════════════════════════════════════════════════
#  4 · L'état affiché en haut de page
# ══════════════════════════════════════════════════════════════════════════

class TestLEtat:

    def test_il_NOMME_la_variable_attendue(self, at):
        """Sinon l'écran dit « pas de miroir » sans dire quoi poser."""
        assert at.etat({})["variable"] == "HUB_ATELIER_DB"

    def test_il_compte_ce_qui_est_range(self, at, env):
        at.ecrire("principale", DOC, 0, env)
        at.piece_ecrire("p1_abc", "image/png", PNG, env)
        e = at.etat(env)
        assert e["miroir"] is True and e["toiles"] == 1 and e["pieces"] == 1


# ══════════════════════════════════════════════════════════════════════════
#  5 · La page
# ══════════════════════════════════════════════════════════════════════════

class TestLaPage:

    def test_le_rendu_ne_bloque_PAS_sur_une_lecture(self):
        """⚠️ La leçon de /panel : un appel inter-services dans la vue faisait
        attendre 25 s puis afficher « l'instance ne répond pas ». Le squelette
        part tout de suite ; la toile locale s'affiche avant tout réseau."""
        app = _fichier("app.py")
        debut = app.index('def page_atelier(')
        corps = app[debut:app.index("@app.route", debut)]
        assert "atelier.lire" not in corps
        assert "atelier.etat" not in corps
        assert "render_template" in corps

    def test_les_routes_sont_toutes_protegees(self):
        app = _fichier("app.py")
        for chemin in ('"/atelier"', '"/api/atelier/etat"',
                       '"/api/atelier/toile/<cle>"', '"/api/atelier/pieces"',
                       '"/api/atelier/piece/<ident>"'):
            i = app.index(chemin)
            suite = app[i:i + 260]
            assert "@login_required" in suite, chemin

    def test_le_beacon_de_fermeture_peut_POSTER(self):
        """⚠️ `navigator.sendBeacon` n'envoie qu'en POST, et c'est lui qui
        pousse la dernière frappe quand l'onglet se ferme. Un 405 là-dessus
        ne se voit nulle part : la page n'existe déjà plus."""
        app = _fichier("app.py")
        i = app.index('"/api/atelier/toile/<cle>"')
        assert '"POST"' in app[i:i + 120]
        js = _fichier(os.path.join("static", "atelier.js"))
        assert "sendBeacon" in js

    def test_la_cle_de_nav_est_le_NOM_DE_L_ENDPOINT(self):
        """`page_active` vaut `request.endpoint` : la clé de `PAGES` doit lui
        correspondre, et la vue ne peut pas s'appeler `atelier` sans masquer
        le module du même nom."""
        app = _fichier("app.py")
        assert 'endpoint="atelier"' in app
        inv = _fichier("inventaire.py")
        assert '"cle": "atelier"' in inv
        assert '"/atelier"' in inv

    def test_l_accent_et_l_icone_de_la_section_existent(self):
        css = _fichier(os.path.join("static", "hub.css"))
        assert ".page--atelier" in css and ".acc-atelier" in css
        base = _fichier(os.path.join("templates", "base.html"))
        assert 'id="i-palette"' in base

    def test_le_bandeau_est_un_BLOC_remplacable(self):
        """L'atelier prend le cadre entier : il remplace l'arche, il ne la
        pousse pas hors de l'écran."""
        base = _fichier(os.path.join("templates", "base.html"))
        assert "{% block heros %}" in base
        page = _fichier(os.path.join("templates", "atelier.html"))
        assert "{% block heros %}" in page
        assert "colonne--plein" in page

    def test_hidden_est_neutralise(self):
        """⚠️ `hidden` ne vaut qu'un `display:block` par défaut : le moindre
        `display:grid` le piétine. L'aide, le rail et le sélecteur de page
        s'affichaient en permanence par-dessus la toile."""
        css = _fichier(os.path.join("static", "atelier.css"))
        bloc = css[:css.index(".at-teinte-craie")]
        for sel in (".at-voile[hidden]", ".at-pop[hidden]", ".at-rail[hidden]"):
            assert sel in bloc, sel
        assert "display:none !important" in bloc


# ══════════════════════════════════════════════════════════════════════════
#  6 · Le cloisonnement
# ══════════════════════════════════════════════════════════════════════════

class TestLeCloisonnement:

    def test_l_atelier_n_ouvre_JAMAIS_une_base_d_instance(self):
        """La promesse n°2. `HUB_DBS_B64` porte les bases des CLIENTS et ne se
        lit qu'en lecture seule ; l'atelier écrit. Les deux ne doivent pas se
        croiser, même par une variable lue au mauvais endroit."""
        src = _code_py("atelier.py")
        assert "HUB_DBS" not in src
        assert "HUB_DBS_B64" not in src
        assert "load_sources" not in src
        assert "courrier" not in src
        # Et réciproquement : la lecture seule ne passe pas par l'atelier.
        assert "atelier" not in _code_py("courrier.py")

    def test_la_toile_vit_dans_IndexedDB_pas_dans_localStorage(self):
        """⚠️ `localStorage` plafonne autour de 5 Mo pour TOUT le domaine :
        une dizaine de captures suffisaient à faire échouer un enregistrement
        en silence."""
        js = _code_js(os.path.join("static", "atelier.js"))
        assert "indexedDB" in js
        assert "localStorage" not in js
        assert "sessionStorage" not in js

    def test_le_deploiement_ne_pose_la_variable_que_si_elle_existe(self):
        chemin = os.path.join(RACINE, ".github", "workflows", "deploy-hub.yml")
        if not os.path.exists(chemin):
            pytest.skip("workflows absents (arbre d'image)")
        wf = io.open(chemin, encoding="utf-8").read()
        assert "secrets.HUB_ATELIER_DB" in wf
        assert 'if [ -n "$HUB_ATELIER_DB" ]; then' in wf
        # Jamais l'URL d'une base en clair dans le fichier.
        for ligne in wf.split("\n"):
            nu = ligne.strip()
            if nu.startswith("#") or "HUB_ATELIER_DB" not in nu:
                continue
            assert ("secrets.HUB_ATELIER_DB" in nu
                    or "$HUB_ATELIER_DB" in nu
                    or "${HUB_ATELIER_DB}" in nu
                    or nu.endswith("HUB_ATELIER_DB:")), nu


# ══════════════════════════════════════════════════════════════════════════
#  7 · Le badge de page — ce que l'outil sert à faire
# ══════════════════════════════════════════════════════════════════════════

class TestLesBadgesDePage:

    def test_une_maquette_se_rafraichit_quand_on_lui_accroche_ailleurs(self):
        """⚠️ Une maquette affiche ce que les AUTRES pièces lui accrochent :
        sa signature doit en tenir compte, sinon le badge apparaît sur la note
        et la section reste vide — on croit le rattachement perdu."""
        js = _fichier(os.path.join("static", "atelier.js"))
        bloc = js[js.index("function sig("):js.index("function placer(")]
        assert 'n.type === "maquette"' in bloc
        assert "attaches(" in bloc

    def test_un_badge_orphelin_est_efface_avec_sa_maquette(self):
        """Un badge « page supprimée » qu'on ne peut plus suivre n'apprend
        rien."""
        js = _fichier(os.path.join("static", "atelier.js"))
        bloc = js[js.index("function supprimer("):js.index("function dupliquer(")]
        assert "n.page = null" in bloc
        assert "it.page = null" in bloc

    def test_la_selection_ne_sort_JAMAIS_par_slice(self):
        """⚠️ `sel` est un Set. `[].slice.call(unSet)` rend un tableau VIDE
        sans lever : `slice` veut une `length`, un Set a une `size`.
        Supprimer, déplacer et dupliquer se croyaient exécutés et ne
        touchaient rien — `sel.size` disait 7, l'argument était vide."""
        js = _code_js(os.path.join("static", "atelier.js"))
        assert "slice.call(sel)" not in js
        assert "Array.from(sel)" in js

    def test_dupliquer_ne_recopie_pas_les_identifiants(self):
        """Deux sections au même id, et un badge pointerait sur les deux."""
        js = _fichier(os.path.join("static", "atelier.js"))
        bloc = js[js.index("function dupliquer("):js.index("function dansUnChamp(")]
        assert 'uid("i")' in bloc and 'uid("s")' in bloc


# ══════════════════════════════════════════════════════════════════════════
#  8 · Les modèles — le plan de l'app et les chantiers
# ══════════════════════════════════════════════════════════════════════════

class TestLesModeles:

    def test_le_catalogue_annonce_ses_trois_entrees(self, mod):
        cles = [m["cle"] for m in mod.catalogue()]
        assert cles == ["tout", "pages", "chantiers"]
        for m in mod.catalogue():
            assert m["titre"] and m["quoi"]

    def test_une_cle_inconnue_ne_rend_rien(self, mod):
        assert mod.modele("inexistant") is None

    def test_chaque_page_a_un_chemin_et_des_sections(self, mod):
        assert len(mod.PAGES) >= 10
        for p in mod.PAGES:
            assert p["titre"] and p["chemin"].startswith("/")
            assert p["sections"], p["titre"]
            for nom, genre, quoi in p["sections"]:
                assert nom and quoi, (p["titre"], nom)
                # Le genre doit exister côté atelier, sinon le croquis tombe
                # sur la classe CSS par défaut sans qu'on le voie.
                assert genre in ("entete", "liste", "table", "form", "graphe",
                                 "panneau", "pied"), (p["titre"], nom, genre)

    def test_les_identifiants_du_modele_sont_uniques(self, mod):
        """⚠️ L'atelier les remplace à l'insertion, mais il s'appuie dessus
        pour remapper les rattachements : deux pièces au même id, et un badge
        pointerait sur la mauvaise."""
        for cle in ("tout", "pages", "chantiers"):
            vus = set()
            for n in mod.modele(cle)["noeuds"]:
                assert n["id"] not in vus, (cle, n["id"])
                vus.add(n["id"])
                for s in n.get("sections", []):
                    assert s["id"] not in vus, (cle, s["id"])
                    vus.add(s["id"])

    def test_CHAQUE_chantier_vise_une_page_ET_une_section_qui_EXISTENT(self, mod):
        """⚠️ Le garde-fou qui compte. Les chantiers désignent leur page par
        NOM : une faute de frappe ne lève rien, elle fait silencieusement
        disparaître le badge — et la ligne se retrouve orpheline sur la toile
        sans que personne ne sache pourquoi."""
        connues = {}
        for p in mod.PAGES:
            connues[p["titre"]] = {s[0] for s in p["sections"]}
        for texte, page, section in mod.CHANTIERS:
            assert page in connues, "page inconnue : %r (%s)" % (page, texte)
            assert section in connues[page], \
                "section inconnue : %r dans %r (%s)" % (section, page, texte)

    def test_les_chantiers_portent_un_page_ref_pas_un_id(self, mod):
        """Ils se rattachent à des maquettes POSÉES, peut-être il y a trois
        jours : la résolution se fait par nom, pas par identifiant local."""
        liste = mod.modele("chantiers")["noeuds"][0]
        assert liste["type"] == "liste"
        assert len(liste["items"]) == len(mod.CHANTIERS)
        for it in liste["items"]:
            assert it["texte"]
            assert it["fait"] is False
            assert set(it["page_ref"]) == {"page", "section"}
            assert "page" not in it

    def test_le_modele_complet_porte_les_deux_et_ne_les_superpose_pas(self, mod):
        tout = mod.modele("tout")["noeuds"]
        maquettes = [n for n in tout if n["type"] == "maquette"]
        listes = [n for n in tout if n["type"] == "liste"]
        assert len(maquettes) == len(mod.PAGES)
        assert len(listes) == 1
        # La liste à gauche, les pages à sa droite : rien ne se chevauche.
        gauche = listes[0]
        assert all(m["x"] >= gauche["x"] + gauche["w"] for m in maquettes)

    def test_les_pages_ne_se_chevauchent_pas(self, mod):
        """Le rangement en colonnes doit laisser une toile lisible, pas un
        tas de maquettes empilées."""
        noeuds = mod.modele("pages")["noeuds"]
        for i, a in enumerate(noeuds):
            for b in noeuds[i + 1:]:
                chevauche = (a["x"] < b["x"] + b["w"]
                             and b["x"] < a["x"] + a["w"]
                             and a["y"] < b["y"] + b["h"]
                             and b["y"] < a["y"] + a["h"])
                assert not chevauche, (a["titre"], b["titre"])

    def test_les_routes_des_modeles_sont_protegees(self):
        app = _fichier("app.py")
        for chemin in ('"/api/atelier/modeles"', '"/api/atelier/modele/<cle>"'):
            i = app.index(chemin)
            assert "@login_required" in app[i:i + 200], chemin

    def test_les_modeles_ne_touchent_a_aucune_base(self, mod):
        """Ce sont des données du dépôt. Rien à lire, rien à écrire — et donc
        rien qui dépende de HUB_ATELIER_DB."""
        src = _code_py("atelier_modeles.py")
        for interdit in ("create_engine", "HUB_ATELIER_DB", "HUB_DBS",
                         "sqlalchemy", "os.environ"):
            assert interdit not in src, interdit
        # Et il répond la même chose sans aucune variable d'environnement.
        assert mod.modele("tout")["noeuds"]
