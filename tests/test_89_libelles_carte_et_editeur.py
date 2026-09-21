# -*- coding: utf-8 -*-
"""La page Carte et l'éditeur dans la langue choisie — y compris ce qu'ils
écrivent EUX-MÊMES en JavaScript, et ce qu'on ne lit qu'au survol.

Relevé le 21/09/2026 en parcourant les écrans en anglais puis en français :
- l'éditeur portait des info-bulles écrites en dur, en français (« Position
  des labels… », « Créer une pile… ») ET en anglais (« Box select — drag… ») ;
  ses fenêtres construites en JS (diagnostic, correction des erreurs,
  placement des losanges, fichier Visio incomplet, suppression d'une bande)
  et les avertissements des piles ne passaient par aucun catalogue ;
- la page Carte écrivait « 42 activités » dans la gestion des entités, et
  toute la fenêtre des liaisons entre cartos en français ;
- une erreur réseau à l'envoi d'une proposition affichait une CLÉ brute
  (`editor.toast.error_network` n'existait pas).

`test_78` ne voyait rien de tout ça : il lit le texte des gabarits, pas leurs
attributs, et il ne lit pas le JavaScript de l'éditeur.
"""
import io
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
GABARITS = RACINE / "Code" / "routes" / "templates"
OPTIQCARTO = RACINE / "static" / "optiqcarto"


def _lire(p):
    return io.open(p, encoding="utf-8").read()


def _sans_commentaires_js(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", s)


# ══════════════════════════════════════════════════════════════════════
#  1 · Les attributs lus au survol ou par un lecteur d'écran
# ══════════════════════════════════════════════════════════════════════
_ATTR = re.compile(r'\b(title|aria-label|placeholder|alt)="([^"{]*[A-Za-zÀ-ÿ]{3,}[^"{]*)"')


class TestAttributsEnDur:
    """Une info-bulle, un `aria-label`, un texte indicatif écrits en dur ne
    suivent pas la langue — et `test_78` ne lit que le texte entre balises.

    Même cliquet que pour le texte : un gabarit hors inventaire doit être
    propre, un gabarit inventorié ne doit pas empirer, et le plafond suit la
    réalité quand on nettoie.
    """

    # Ni du français ni de l'anglais : une marque, un exemple de format.
    NEUTRES = {"OPTIQ", "Role1, Role2"}

    # Écrans jamais traduits (déjà dans l'inventaire de `test_78`) et
    # l'assistant d'installation : un chantier à part entière chacun.
    DETTE = {
        "chatbot_widget.html":    6,
        "import_tasks_modal.html": 3,
        "setup_wizard.html":      3,
        "projection_metier.html": 2,
    }

    def _attributs(self, chemin):
        return [(a, v) for a, v in _ATTR.findall(_lire(chemin))
                if v.strip() not in self.NEUTRES]

    def test_aucun_gabarit_hors_inventaire_ne_porte_d_attribut_en_dur(self):
        surprises = {}
        for f in sorted(GABARITS.glob("*.html")):
            if f.name in self.DETTE:
                continue
            trouves = self._attributs(f)
            if trouves:
                surprises[f.name] = trouves[:3]
        assert not surprises, (
            "attribut(s) écrit(s) en dur — l'info-bulle restera dans sa langue "
            "d'écriture quelle que soit la langue choisie : %s" % surprises)

    @pytest.mark.parametrize("gabarit", sorted(DETTE))
    def test_la_dette_ne_grandit_pas(self, gabarit):
        n = len(self._attributs(GABARITS / gabarit))
        assert n <= self.DETTE[gabarit], (
            "%s porte %d attribut(s) en dur (plafond %d)" % (gabarit, n, self.DETTE[gabarit]))

    def test_l_inventaire_suit_la_realite(self):
        trop_larges = ["%s : %d toléré(s) pour %d réel(s)" % (nom, plafond, n)
                       for nom, plafond in self.DETTE.items()
                       for n in [len(self._attributs(GABARITS / nom))]
                       if n < plafond]
        assert not trop_larges, "inventaire à resserrer : %s" % trop_larges


# ══════════════════════════════════════════════════════════════════════
#  2 · L'éditeur : chaque clé qu'il demande existe dans les deux langues
# ══════════════════════════════════════════════════════════════════════
class TestClesDeLEditeur:
    """`_L(cle)` rend la clé brute quand elle n'existe pas — c'est voulu (un
    oubli se voit), mais encore faut-il que personne ne l'oublie."""

    @pytest.mark.parametrize("fichier,accesseur", [
        ("editor.js", "_L"),
        ("carto_sharing.js", "L"),
    ])
    def test_toute_cle_litterale_existe_dans_les_deux_langues(self, fichier, accesseur):
        from Code.translations import TRANSLATIONS

        source = _sans_commentaires_js(_lire(OPTIQCARTO / fichier))
        cles = set(re.findall(r"\b%s\(\s*'([a-z][\w.]*)'\s*[,)]" % accesseur, source))
        cles = {c for c in cles if "." in c}
        assert len(cles) > 20, "garde-fou : l'analyse ne trouve presque rien dans %s" % fichier
        manque = sorted(c for c in cles
                        if c not in TRANSLATIONS["fr"] or c not in TRANSLATIONS["en"])
        assert not manque, "%s demande des clés absentes du catalogue : %s" % (fichier, manque)

    def test_plus_aucun_texte_en_dur_dans_les_fenetres_de_l_editeur(self):
        """Les phrases relevées le 21/09 ne doivent pas revenir."""
        source = _lire(OPTIQCARTO / "editor.js")
        for phrase in (
            "Pile prerequisite not met",
            "Select at least 2 shapes",
            "Dans le groupe (",
            "Aucun problème détecté",
            "problème(s) trouvé(s)",
            "Corriger les erreurs",
            "Placement des losanges",
            "Tout garder",
            "Fichier incomplet",
            "Supprimer quand même",
            "Sans nom",
            "Agencement auto appliqué",
            "seul le format .vsdx est accepté",
        ):
            assert phrase not in source, "« %s » est revenu en dur dans editor.js" % phrase


# ══════════════════════════════════════════════════════════════════════
#  3 · Ce que les pages envoient au navigateur, en anglais
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture
def en_anglais(auth_client):
    # `client` est partagé par toute la session de tests : on la rend telle
    # qu'on l'a trouvée (même parti pris que test_82 / test_83).
    with auth_client.session_transaction() as s:
        avant = dict(s)
    auth_client.post("/parametres/set_language", json={"lang": "en"})
    yield auth_client
    with auth_client.session_transaction() as s:
        s.clear()
        s.update(avant)


class TestEnAnglais:

    def test_la_page_carte_embarque_ses_libelles_anglais(self, en_anglais):
        html = en_anglais.get("/activities/map").get_data(as_text=True)
        m = re.search(r"window\.MAP_I18N = \{(.*?)\n  \};", html, re.S)
        assert m, "la page Carte n'embarque plus MAP_I18N"
        bloc = m.group(1)
        for attendu in ("Make official", "No link found in the other maps.",
                        "Network error.", "activities"):
            assert attendu in bloc, "%r absent de MAP_I18N en anglais" % attendu
        assert "Officialiser" not in bloc

    def test_l_editeur_n_affiche_plus_d_info_bulle_francaise(self, en_anglais):
        html = en_anglais.get("/cartography/editor").get_data(as_text=True)
        for francais in ("Position des labels", "Créer une pile",
                         "Revenir à la carto de base", "SÉLECTION MULTIPLE"):
            assert francais not in html, "%r reste en français dans l'éditeur" % francais
        assert 'aria-label="Label position"' in html
