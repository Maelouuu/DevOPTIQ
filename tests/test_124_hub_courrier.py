# -*- coding: utf-8 -*-
"""Page Courrier du hub — les chiffres de réinitialisation et la boîte d'envoi.

Le hub est un service SÉPARÉ (son propre Cloud Run, son propre workflow) : ces
cas lisent `hub/courrier.py` comme `test_61` lit `pulse/aggregates.py`.

⚠️ Ils SAUTENT dans l'arbre d'image (bytecode-only) : `spec_from_file_location`
veut le chemin exact d'un `.py`, et la purge du Dockerfile les retire. Un test
qui rougirait à chaque exécution sur l'instance n'est plus lu — et le jour où il
a raison, personne ne regarde. C'est la même garde que la fixture `pulse_app`,
`test_65`, `test_107` et `test_111`.
"""
import importlib.util
import io
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = os.path.join(RACINE, "hub")
SRC = os.path.join(HUB, "courrier.py")


def _module():
    if not os.path.exists(SRC):
        pytest.skip("hub/ en bytecode — service séparé, sources absentes")
    spec = importlib.util.spec_from_file_location("hub_courrier_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fichier(nom):
    chemin = os.path.join(HUB, nom)
    if not os.path.exists(chemin):
        pytest.skip("hub/ en bytecode — service séparé, sources absentes")
    return io.open(chemin, encoding="utf-8").read()


@pytest.fixture
def cr():
    return _module()


# ══════════════════════════════════════════════════════════════════════════
#  1 · Les bases suivies
# ══════════════════════════════════════════════════════════════════════════

class TestLesBasesSuivies:

    def test_en_clair_et_en_base64(self, cr):
        import base64
        brut = json.dumps([{"name": "Staging", "url": "postgresql://a/b"}])
        os.environ["HUB_DBS"] = brut
        try:
            assert cr.load_sources() == [{"name": "Staging",
                                          "url": "postgresql://a/b"}]
        finally:
            del os.environ["HUB_DBS"]
        os.environ["HUB_DBS_B64"] = base64.b64encode(brut.encode()).decode()
        try:
            assert cr.load_sources()[0]["name"] == "Staging"
        finally:
            del os.environ["HUB_DBS_B64"]

    def test_l_ancien_schema_de_neon_est_reecrit(self, cr):
        """Neon rend parfois `postgres://`, que SQLAlchemy 2 ne connaît plus."""
        os.environ["HUB_DBS"] = json.dumps([{"name": "X",
                                             "url": "postgres://u:p@h/d"}])
        try:
            assert cr.load_sources()[0]["url"].startswith("postgresql://")
        finally:
            del os.environ["HUB_DBS"]

    def test_rien_ou_illisible_ne_leve_pas(self, cr):
        """⚠️ Une variable absente, vide ou abîmée doit rendre une liste vide :
        la page dit alors « aucune base suivie ». Une exception ici couperait
        la moitié des chiffres ET la boîte."""
        for valeur in (None, "", "   ", "pas du json", "{}"):
            if valeur is None:
                os.environ.pop("HUB_DBS", None)
            else:
                os.environ["HUB_DBS"] = valeur
            os.environ.pop("HUB_DBS_B64", None)
            try:
                assert cr.load_sources() == [], repr(valeur)
            finally:
                os.environ.pop("HUB_DBS", None)


# ══════════════════════════════════════════════════════════════════════════
#  2 · Les chiffres, lus sur une vraie base
# ══════════════════════════════════════════════════════════════════════════

def _base_jetable(lignes, comptes=(), table=True):
    """Une base SQLite avec le schéma réel de `password_resets`.

    L'agrégation est 100 % Python (comme `pulse/aggregates.py`) : elle se joue
    donc sur SQLite, sans PostgreSQL ni serveur.
    """
    fd, chemin = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cx = sqlite3.connect(chemin)
    cx.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, first_name TEXT, "
               "last_name TEXT, email TEXT, lang TEXT)")
    if table:
        cx.execute("CREATE TABLE password_resets (id INTEGER PRIMARY KEY, "
                   "user_id INTEGER, email_hash TEXT, jeton_hash TEXT, "
                   "ip_hash TEXT, cree_le TIMESTAMP, expire_le TIMESTAMP, "
                   "utilise_le TIMESTAMP)")
        for n, (user_id, cree, utilise) in enumerate(lignes, 1):
            cx.execute("INSERT INTO password_resets (id, user_id, email_hash, "
                       "jeton_hash, ip_hash, cree_le, utilise_le) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (n, user_id, "EMPREINTE_ADRESSE_%d" % n,
                        "EMPREINTE_JETON_%d" % n, "EMPREINTE_IP_%d" % n,
                        cree, utilise))
    for uid, prenom, nom, mail, langue in comptes:
        cx.execute("INSERT INTO users (id, first_name, last_name, email, lang) "
                   "VALUES (?,?,?,?,?)", (uid, prenom, nom, mail, langue))
    cx.commit()
    cx.close()
    return "sqlite:///" + chemin.replace("\\", "/"), chemin


class TestLesChiffres:

    def test_il_compte_les_demandes_les_abouties_et_les_inconnues(self, cr):
        maintenant = datetime(2026, 10, 29, 12, 0, 0)
        hier = maintenant - timedelta(days=1)
        url, chemin = _base_jetable(
            lignes=[(7, hier, maintenant),       # aboutie
                    (7, hier, None),             # sans suite
                    (9, maintenant, maintenant), # aboutie
                    (None, maintenant, None)],   # adresse inconnue
            comptes=[(7, "Lou", "Vasseur", "lou@exemple.fr", "fr"),
                     (9, "Noe", "Mehta", "noe@exemple.in", "en")])
        try:
            s = cr.stats_une_base(url, jours=30, maintenant=maintenant)
        finally:
            os.unlink(chemin)
        assert s["present"] is True and s["erreur"] is None
        assert s["total"] == 4
        assert s["abouties"] == 2
        assert s["abandonnees"] == 2
        assert s["inconnues"] == 1

    def test_les_comptes_sont_nommes_le_plus_demandeur_d_abord(self, cr):
        """⚠️ Celui qui redemande sans cesse est celui qui a un problème : il
        passe devant, sinon on lit une liste dans laquelle il faut chercher."""
        maintenant = datetime(2026, 10, 29, 12, 0, 0)
        url, chemin = _base_jetable(
            lignes=[(9, maintenant, None), (7, maintenant, None),
                    (7, maintenant, None), (7, maintenant, None)],
            comptes=[(7, "Lou", "Vasseur", "lou@exemple.fr", "fr"),
                     (9, "Noe", "Mehta", "noe@exemple.in", "en")])
        try:
            s = cr.stats_une_base(url, jours=30, maintenant=maintenant)
        finally:
            os.unlink(chemin)
        assert [c["nom"] for c in s["comptes"]] == ["Lou Vasseur", "Noe Mehta"]
        assert s["comptes"][0]["demandes"] == 3
        assert s["comptes"][0]["langue"] == "fr"
        assert s["comptes"][1]["langue"] == "en"

    def test_AUCUNE_empreinte_ne_sort(self, cr):
        """⚠️⚠️ `password_resets` ne porte que des EMPREINTES de l'adresse
        saisie, du jeton et de l'IP — c'est voulu : une lecture de la base ne
        doit pas rendre un lien utilisable, ni la liste des adresses qu'un
        inconnu a essayées. Rien de tout cela ne doit remonter jusqu'à la page.
        """
        maintenant = datetime(2026, 10, 29, 12, 0, 0)
        url, chemin = _base_jetable(
            lignes=[(7, maintenant, None), (None, maintenant, None)],
            comptes=[(7, "Lou", "Vasseur", "lou@exemple.fr", "fr")])
        try:
            s = cr.stats_une_base(url, jours=30, maintenant=maintenant)
        finally:
            os.unlink(chemin)
        rendu = json.dumps(s, default=str)
        for interdit in ("EMPREINTE_ADRESSE", "EMPREINTE_JETON", "EMPREINTE_IP",
                         "email_hash", "jeton_hash", "ip_hash"):
            assert interdit not in rendu, interdit

    def test_la_serie_couvre_la_periode_et_somme_le_total(self, cr):
        maintenant = datetime(2026, 10, 29, 12, 0, 0)
        url, chemin = _base_jetable(
            lignes=[(7, maintenant, None),
                    (7, maintenant - timedelta(days=3), None)],
            comptes=[(7, "Lou", "Vasseur", "lou@exemple.fr", "fr")])
        try:
            s = cr.stats_une_base(url, jours=10, maintenant=maintenant)
        finally:
            os.unlink(chemin)
        assert len(s["serie"]) == 11            # 10 jours + aujourd'hui
        assert sum(p["n"] for p in s["serie"]) == 2
        assert s["serie"][-1]["jour"] == "2026-10-29"

    def test_une_instance_SANS_la_table_est_un_etat_pas_une_erreur(self, cr):
        """⚠️ La réinitialisation n'est déployée que sur staging et le pilote.
        Une instance en retard n'a pas la table : la page doit dire « pas
        encore déployée », pas afficher une erreur de base de données."""
        url, chemin = _base_jetable(lignes=[], table=False)
        try:
            s = cr.stats_une_base(url, jours=30)
        finally:
            os.unlink(chemin)
        assert s["present"] is False
        assert s["erreur"] is None
        assert s["total"] == 0

    def test_une_base_injoignable_ne_fait_pas_tomber_les_autres(self, cr):
        s = cr.stats_une_base("postgresql://personne@127.0.0.1:1/absente",
                              jours=30)
        assert s["present"] is False
        assert s["erreur"]                      # dit pourquoi
        assert len(s["erreur"]) <= 200          # jamais une trace entière

    def test_les_instances_sont_lues_en_parallele_et_nommees(self, cr):
        maintenant = datetime(2026, 10, 29, 12, 0, 0)
        url, chemin = _base_jetable(lignes=[(7, maintenant, None)],
                                    comptes=[(7, "Lou", "V", "l@x.fr", "fr")])
        try:
            res = cr.stats_reset([{"name": "Staging", "url": url},
                                  {"name": "Pilote", "url": url}],
                                 jours=30, maintenant=maintenant)
        finally:
            os.unlink(chemin)
        assert [r["nom"] for r in res] == ["Staging", "Pilote"]
        assert all(r["total"] == 1 for r in res)

    def test_sans_base_suivie_la_liste_est_vide(self, cr):
        assert cr.stats_reset([]) == []


# ══════════════════════════════════════════════════════════════════════════
#  3 · La boîte d'envoi
# ══════════════════════════════════════════════════════════════════════════

class TestLaBoite:

    def test_sans_identifiants_la_moitie_s_eteint_proprement(self, cr):
        b = cr.boite(env={})
        assert b["configure"] is False
        assert b["erreur"] is None
        assert b["messages"] == []

    def test_une_variable_VIDE_n_est_pas_une_variable_absente(self, cr):
        """⚠️ Le défaut qui a fait croire pendant des mois que l'envoi de mail
        était configuré : `--update-env-vars` CRÉE la variable même quand le
        secret n'existe pas, elle arrive PRÉSENTE ET VIDE, et
        `getenv(cle, defaut)` ne regarde alors jamais son défaut."""
        for env in ({"HUB_IMAP_USER": "", "HUB_IMAP_PASSWORD": ""},
                    {"HUB_IMAP_USER": "a@b.c", "HUB_IMAP_PASSWORD": ""},
                    {"HUB_IMAP_USER": "", "HUB_IMAP_PASSWORD": "x"},
                    {"HUB_IMAP_USER": "   ", "HUB_IMAP_PASSWORD": "   "}):
            assert cr.boite(env=env)["configure"] is False, env

    def test_une_connexion_refusee_est_dite_pas_avalee(self, cr):
        b = cr.boite(env={"HUB_IMAP_USER": "a@b.c",
                          "HUB_IMAP_PASSWORD": "faux"},
                     serveur="127.0.0.1")
        assert b["configure"] is True
        assert b["erreur"]
        assert b["messages"] == []

    def test_un_rejet_se_reconnait_a_l_expediteur_ou_a_l_objet(self, cr):
        assert cr._nature("MAILER-DAEMON@googlemail.com", "n'importe") == "rejet"
        assert cr._nature("x@y.z", "Undelivered Mail Returned to Sender") == "rejet"
        assert cr._nature("x@y.z", "Adresse introuvable") == "rejet"
        assert cr._nature("x@y.z", "Automatic reply: congés") == "auto"
        assert cr._nature("x@y.z", "Réponse automatique") == "auto"
        assert cr._nature("lou@exemple.fr", "Merci !") == "reponse"

    def test_la_lecture_ne_touche_a_RIEN(self, cr):
        """⚠️ `readonly=True` et `BODY.PEEK` : on ne marque rien comme lu, on ne
        déplace rien, on ne supprime rien. Et seuls les EN-TÊTES sont
        téléchargés — on cherche ce qui est revenu, pas à lire le courrier."""
        src = _fichier("courrier.py")
        assert 'cx.select("INBOX", readonly=True)' in src
        assert "BODY.PEEK[HEADER.FIELDS" in src
        assert "BODY[" not in src.replace("BODY.PEEK[", "")
        for interdit in ("cx.store(", "cx.copy(", "cx.expunge(", '"\\\\Deleted"'):
            assert interdit not in src, interdit


# ══════════════════════════════════════════════════════════════════════════
#  4 · La page, et ce qu'elle ne fait pas
# ══════════════════════════════════════════════════════════════════════════

class TestLaPage:

    def test_le_rendu_ne_bloque_PAS_sur_une_lecture(self):
        """⚠️ La leçon de /panel : la route interrogeait l'instance pour deux
        nombres et bloquait le HTML le temps d'un appel inter-services — 25 s
        d'attente, puis une page qui annonçait « l'instance ne répond pas »
        alors que tout allait bien. Ici une base Neon froide demande ~1 s et
        IMAP deux à quatre secondes : le squelette part d'abord."""
        src = _fichier("app.py")
        debut = src.index("def page_courrier(")
        fin = src.index("@app.route", debut)
        corps = src[debut:fin]
        for interdit in ("courrier.stats_reset", "courrier.boite",
                         "courrier.cache"):
            assert interdit not in corps, interdit
        assert "render_template(\"courrier.html\")" in corps

    def test_les_deux_moities_ont_leur_propre_route(self):
        src = _fichier("app.py")
        for chemin in ('@app.route("/api/courrier/reset")',
                       '@app.route("/api/courrier/boite")'):
            assert chemin in src, chemin
        # Derrière la porte du hub, comme tout le reste.
        for vue in ("def page_courrier(", "def api_courrier_reset(",
                    "def api_courrier_boite("):
            avant = src[:src.index(vue)]
            assert avant.rstrip().endswith("@login_required"), vue

    def test_la_cle_de_nav_est_le_NOM_DE_L_ENDPOINT(self):
        """⚠️ `page_active` vaut `request.endpoint` et la nav le compare à la
        clé de `inventaire.PAGES` : sans `endpoint="courrier"` explicite,
        l'entrée ne s'allumerait jamais. Et la vue ne peut PAS s'appeler
        `courrier`, cela masquerait le module du même nom."""
        inv = _fichier("inventaire.py")
        assert '"cle": "courrier"' in inv
        assert '"route": "/courrier"' in inv
        src = _fichier("app.py")
        assert '@app.route("/courrier", endpoint="courrier")' in src
        assert "\ndef courrier(" not in src

    def test_la_page_dit_quoi_faire_quand_la_boite_n_est_pas_branchee(self):
        """Un « non configuré » sec envoie chercher ailleurs. L'écran nomme les
        deux secrets et dit que le mot de passe d'application doit être un
        SECOND, distinct de celui qui sert à envoyer."""
        js = _fichier(os.path.join("static", "courrier.js"))
        assert "HUB_IMAP_USER" in js and "HUB_IMAP_PASSWORD" in js
        assert "second" in js.lower()

    def test_l_accent_et_l_icone_de_la_section_existent(self):
        css = _fichier(os.path.join("static", "hub.css"))
        assert ".page--courrier" in css
        assert ".acc-courrier" in css
        base = _fichier(os.path.join("templates", "base.html"))
        assert 'id="i-courrier"' in base


# ══════════════════════════════════════════════════════════════════════════
#  5 · Le déploiement
# ══════════════════════════════════════════════════════════════════════════

class TestLeDeploiementDuHub:

    def _wf(self):
        chemin = os.path.join(RACINE, ".github", "workflows", "deploy-hub.yml")
        if not os.path.exists(chemin):
            pytest.skip("workflows absents (arbre d'image)")
        return io.open(chemin, encoding="utf-8").read()

    def test_les_bases_arrivent_au_service(self):
        wf = self._wf()
        assert "HUB_DBS_B64" in wf
        assert "Composer la liste des bases suivies" in wf
        # Les mêmes secrets que pulse : aucune URL recopiée à la main.
        for s in ("PILOT_DATABASE_URL", "STAGING_DATABASE_URL",
                  "PROD_DATABASE_URL"):
            assert "secrets.%s" % s in wf, s

    def test_les_identifiants_imap_ne_sont_poses_que_s_ils_existent(self):
        """⚠️ Sinon `--update-env-vars` crée les variables VIDES, et la page
        croirait la boîte branchée."""
        wf = self._wf()
        assert ('if [ -n "$HUB_IMAP_USER" ] && [ -n "$HUB_IMAP_PASSWORD" ]; then'
                in wf)

    def test_rien_en_clair_dans_le_fichier(self):
        wf = self._wf()
        for ligne in wf.split("\n"):
            nu = ligne.strip()
            if nu.startswith("#") or "IMAP_PASSWORD" not in nu:
                continue
            # Soit le secret GitHub, soit la variable d'étape — jamais un mot.
            assert ("secrets.HUB_IMAP_PASSWORD" in nu
                    or "$HUB_IMAP_PASSWORD" in nu
                    or "${HUB_IMAP_PASSWORD}" in nu
                    or nu.endswith("HUB_IMAP_PASSWORD:")), nu

    def test_aucun_commentaire_dans_la_commande_gcloud(self):
        """⚠️ Un commentaire au milieu d'une commande à antislashs devient un
        ARGUMENT : le déploiement échouerait. Déjà failli arriver une fois."""
        wf = self._wf()
        dedans = False
        for ligne in wf.split("\n"):
            nu = ligne.strip()
            if nu.startswith("gcloud ") or nu.startswith("if ! gcloud "):
                dedans = nu.endswith("\\")
                continue
            if dedans:
                assert not nu.startswith("#"), nu
                dedans = nu.endswith("\\")
