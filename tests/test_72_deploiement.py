# tests/test_72_deploiement.py
"""
Ce que le hub AFFICHE des déploiements doit être ce qui se PASSE vraiment.

Deux dérives ont coûté cher, et aucune n'était visible depuis l'application :

  * le hub annonçait « `devoptiq` ← push sur main » et un `deploy-beta.yml` qui
    n'a jamais existé ;
  * surtout, la branche officielle `nouveau-point` n'avait AUCUN workflow. Elle
    avançait, l'instance ne bougeait pas — `devoptiq` a servi le code de mai
    2026 pendant quatre mois sans que rien ne le signale.

On relit donc les fichiers `.github/workflows/*.yml` et on les confronte à
`hub/inventaire.py`. Et parce que deux workflows visaient le MÊME service depuis
deux branches, dont une figée avant OptiqCarto, on vérifie aussi qu'un service
n'a qu'un seul chemin de déploiement automatique.
"""
import io
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(RACINE, ".github", "workflows")
INVENTAIRE = os.path.join(RACINE, "hub", "inventaire.py")

# `.github/` et `hub/` sont exclus de l'image applicative (.dockerignore), qui
# est en outre bytecode-only : il n'y a rien à relire là-bas. Le contrôle garde
# tout son sens sur un poste de développement et en CI — les deux endroits où
# un workflow se rédige.
sans_source = pytest.mark.skipif(
    not os.path.isdir(WORKFLOWS) or not os.path.exists(INVENTAIRE),
    reason=".github/workflows ou hub/inventaire.py absent — contrôle de source")


def _lire(nom):
    with io.open(os.path.join(WORKFLOWS, nom), encoding="utf-8") as f:
        return f.read()


def _workflows():
    return [n for n in sorted(os.listdir(WORKFLOWS))
            if n.endswith((".yml", ".yaml"))]


# PyYAML n'est pas une dépendance du projet : s'en remettre à lui ferait sauter
# ce contrôle en CI comme sur le poste, et un test qui ne s'exécute jamais ne
# protège de rien. On lit donc le seul bloc qui nous intéresse — `on: push:
# branches:` — dans les deux écritures possibles (liste en ligne ou en tirets).
def _branches_de_push(nom):
    dans_on = dans_push = dans_branches = False
    branches = []
    for ligne in _lire(nom).splitlines():
        nue = ligne.strip()
        if not nue or nue.startswith("#"):
            continue
        creux = len(ligne) - len(ligne.lstrip())
        if creux == 0:
            dans_on = nue.startswith("on:")
            dans_push = dans_branches = False
            continue
        if not dans_on:
            continue
        if creux == 2:
            dans_push = nue.startswith("push:")
            dans_branches = False
            continue
        if not dans_push:
            continue
        if nue.startswith("branches:"):
            reste = nue[len("branches:"):].strip()
            if reste.startswith("["):
                branches += [b.strip().strip("\"'")
                             for b in reste.strip("[]").split(",") if b.strip()]
                dans_branches = False
            else:
                dans_branches = True          # liste en tirets, elle suit dessous
        elif dans_branches and nue.startswith("- "):
            branches.append(nue[2:].strip().strip("\"'"))
        elif not nue.startswith("- "):
            dans_branches = False
    return branches


def _services_deployes(nom):
    """Les services Cloud Run qu'un workflow déploie, lus dans ses commandes."""
    texte = _lire(nom)
    services = set()
    # La cible est presque toujours une variable — `${{ env.SERVICE }}` contient
    # des espaces, un simple \S+ n'en ramenait que « ${{ ».
    for cible in re.findall(r"gcloud run deploy\s+(\$\{\{[^}]*\}\}|\S+)", texte):
        ref = re.match(r"\$\{\{\s*env\.(\w+)\s*\}\}", cible)
        if ref:
            trouve = re.search(r"^\s+%s:\s*(\S+)" % ref.group(1), texte, re.M)
            if trouve:
                services.add(trouve.group(1))
        else:
            services.add(cible)
    return services


def _inventaire():
    """Lit les listes du hub sans importer Flask (le hub n'est pas dans le path)."""
    espace = {}
    with io.open(INVENTAIRE, encoding="utf-8") as f:
        exec(compile(f.read(), INVENTAIRE, "exec"), espace)
    return espace


@sans_source
class TestLaBrancheOfficielleSeDeploie:

    def test_nouveau_point_a_bien_un_workflow(self):
        """La dérive d'origine : une branche officielle que rien ne déploie."""
        porteurs = [n for n in _workflows() if "nouveau-point" in _branches_de_push(n)]
        assert porteurs, (
            "aucun workflow ne se déclenche sur `nouveau-point` : la version "
            "officielle interne avancerait sans que le service `devoptiq` bouge")

    def test_ce_workflow_vise_bien_le_service_devoptiq(self):
        for nom in _workflows():
            if "nouveau-point" in _branches_de_push(nom):
                assert "devoptiq" in _services_deployes(nom)

    def test_le_panel_de_tests_reste_a_staging(self):
        """`/testpanel` n'a aucune authentification : pas sur l'officielle."""
        for nom in _workflows():
            if "nouveau-point" not in _branches_de_push(nom):
                continue
            texte = _lire(nom)
            assert "--build-arg WITH_TESTS=1" not in texte
            assert "TESTPANEL_ENABLED=1" not in texte


@sans_source
class TestUnServiceUnChemin:

    def test_aucun_service_n_a_deux_deploiements_automatiques(self):
        """`deploy-production.yml` visait `devoptiq` depuis `prod-stable`, figée
        au 07/05/2026 : un push là-bas ramenait l'officielle avant OptiqCarto."""
        auto = {}
        for nom in _workflows():
            if not _branches_de_push(nom):
                continue
            for service in _services_deployes(nom):
                auto.setdefault(service, []).append(nom)
        doublons = {s: n for s, n in auto.items() if len(n) > 1}
        assert not doublons, "deux workflows déploient le même service : %s" % doublons


@sans_source
class TestLeHubDitLaVerite:

    def test_les_workflows_annonces_existent(self):
        inv = _inventaire()
        presents = set(_workflows())
        for entree in inv["WORKFLOWS"]:
            assert entree["fichier"] in presents, entree["fichier"]

    def test_chaque_service_annonce_son_vrai_workflow(self):
        inv = _inventaire()
        presents = set(_workflows())
        for entree in inv["SERVICES_RUN"]:
            fichier = entree["workflow"]
            if fichier.startswith("—"):          # déploiement manuel assumé
                continue
            assert fichier in presents, "%s : %s introuvable" % (entree["service"], fichier)
            assert entree["service"] in _services_deployes(fichier)

    def test_le_declencheur_annonce_est_le_vrai(self):
        """« push sur main » alors que le workflow écoutait `prod-stable`."""
        inv = _inventaire()
        for entree in inv["SERVICES_RUN"]:
            fichier = entree["workflow"]
            annonce = entree["declencheur"]
            if fichier.startswith("—") or not annonce.startswith("push sur "):
                continue
            branche = annonce[len("push sur "):].strip()
            reelles = _branches_de_push(fichier)
            assert branche in reelles, (
                "%s : le hub annonce « %s », le workflow écoute %s"
                % (fichier, annonce, reelles))
