# -*- coding: utf-8 -*-
"""Les alertes des JS de la fiche activité passent par le catalogue.

Trente-neuf libellés s'affichaient EN DUR, donc en français quel que soit
l'écran : les dix alertes de `performance.js`, les quatre « Confirmez-vous la
suppression… » (contrainte, HSC, rôle, outil), les erreurs des quatre écrans
« Proposer… », les deux de `file-picker.js` et les six titres et invites de
l'écran des aptitudes. Ils sortent précisément quand quelque chose rate —
chez un client sans clé IA ou avec un réseau capricieux, donc souvent.

⚠️ `test_78` ne les voyait pas : il lit les GABARITS, et ces phrases vivent
dans le JS. Le détecteur qui a servi ici est au banc ; ce fichier garde le
résultat.

⚠️ Une chaîne française en SECOND argument d'un accesseur (`_CR('cle')`,
`_piSav('cle', "repli")`) ou à droite d'un `||` n'est PAS en dur : c'est un
repli, et il ne s'affiche que si la clé manque. Les compter ferait crier le
contrôle sur du code juste, et on finirait par ne plus le lire.
"""
import io
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GABARITS = os.path.join(RACINE, "Code", "routes", "templates")
JS = os.path.join(RACINE, "static", "js")

ACC = u"[àâäéèêëîïôöùûüç]"
MOTS = (r"\b(?:le|la|les|des|une|un|du|aux|est|sont|pas|pour|avec|dans|sur|"
        r"vous|votre|vos|cette|ces|qui|que|son|ses|aucun|aucune|veuillez|"
        r"impossible|erreur|lors|ajout|suppression|chargement)\b")

# Le PREMIER argument d'une alerte : une chaîne littérale, et rien d'autre.
EN_DUR = re.compile(
    r"""(?<![\w.])(?:alert|confirm)\s*\(\s*('[^'\n]*'|"[^"\n]*"|`[^`]*`)""")

# ── INVENTAIRE DE DETTE ─────────────────────────────────────────────────
#     Deux fichiers portent encore du français en dur, et chacun pour une
# raison écrite :
#   · activities_map.js  : dans du code MORT — l'ancien assistant d'import
#                          VSDX/SVG (`#wizard-title`, `#wizard-progress`,
#                          `screen-import` absents du gabarit), les panneaux
#                          SCS/VCM et l'import de paquet (son bouton
#                          `#wizard-import-carto-btn` n'existe plus, donc
#                          `wireCartoImport` rend la main tout de suite).
#                          ⚠️ Sa modale « Envoyer une copie », elle, est
#                          VIVANTE (`#wizard-copy-btn` est dans le gabarit) —
#                          et déjà traduite : ses phrases sont les replis de
#                          `SHARE_I18N`. À supprimer plutôt qu'à traduire,
#                          mais c'est une passe à part : séparer le vif du
#                          mort dans un fichier de 1900 lignes ne se fait pas
#                          en passant.
#   · projection_metier.js : écran ENTIER injoignable — aucun lien depuis la
#                          nav ni depuis aucun gabarit, et il demande des
#                          identifiants France Travail (classification ROME).
#                          Le traduire serait du travail perdu ; le supprimer
#                          ou le rebrancher est une décision produit.
#     ⚠️ Le plafond ne peut que BAISSER : nettoyer un fichier sans baisser son
# chiffre laisserait une marge où un retour en arrière passerait inaperçu.
#     Les trois alertes restantes d'`activities_map.js` : deux dans
# `importCartoPackage` (injoignable, son bouton n'existe plus) et une dans
# `submitWizard` (l'ancien assistant d'import).
DETTE = {
    "activities_map.js": 3,
    "projection_metier.js": 0,
}


def _js_charges():
    """Les JS qu'un gabarit charge vraiment."""
    noms = set()
    for r, d, fs in os.walk(GABARITS):
        for f in fs:
            if f.endswith(".html"):
                s = io.open(os.path.join(r, f), encoding="utf-8").read()
                noms |= set(re.findall(r"js/([A-Za-z0-9_.-]+\.js)", s))
    return noms


def _replis(ligne):
    """Les chaînes de CETTE ligne qui sont des replis, pas des libellés."""
    out = set()
    for m in re.finditer(
            r"""\b[A-Za-z_$][\w$]*\s*\(\s*(?:'[^']*'|"[^"]*")\s*,\s*"""
            r"""('[^'\n]*'|"[^"\n]*"|`[^`]*`)""", ligne):
        out.add(m.group(1))
    for m in re.finditer(r"""\|\|\s*('[^'\n]*'|"[^"\n]*"|`[^`]*`)""", ligne):
        out.add(m.group(1))
    return out


def _francais_en_dur(nom):
    p = os.path.join(JS, nom)
    if not os.path.exists(p):
        return None
    trouves = []
    for n, l in enumerate(io.open(p, encoding="utf-8"), 1):
        nu = l.strip()
        if nu[:2] in ("//", "/*") or nu[:1] == "*":
            continue
        replis = _replis(l)
        for m in EN_DUR.finditer(l):
            c = m.group(1)
            if c in replis:
                continue
            t = c[1:-1]
            if len(t) < 6:
                continue
            if re.search(ACC, t) or len(re.findall(MOTS, t, re.I)) >= 2:
                trouves.append((n, t[:80]))
    return trouves


VENDOR = ("jquery", ".min.js", "libavoid", "html2canvas", "jspdf")


@pytest.fixture(scope="module")
def charges():
    noms = _js_charges()
    if len(noms) < 20:
        pytest.skip("seulement %d JS reperes — gabarits absents ?" % len(noms))
    return noms


class TestAucuneAlerteNEstEcriteEnDur:

    def test_le_balayage_lit_bien_les_fichiers(self, charges):
        """⚠️ Garde-fou de volume : zéro fichier lu = zéro alerte trouvée =
        un vert qui ne prouve rien. Dans l'arbre d'image `static/js` est
        présent, mais une erreur de chemin passerait sinon inaperçue."""
        lus = sum(1 for n in charges
                  if os.path.exists(os.path.join(JS, n)))
        assert lus >= 20, "seulement %d JS lus sur %d" % (lus, len(charges))

    def test_aucun_fichier_HORS_inventaire_ne_porte_de_francais(self, charges):
        coupables = {}
        for nom in sorted(charges):
            if any(v in nom for v in VENDOR) or nom in DETTE:
                continue
            t = _francais_en_dur(nom)
            if t:
                coupables[nom] = t
        assert not coupables, (
            "alerte(s) ecrite(s) en dur, donc en francais sur l'ecran "
            "anglais : %s" % coupables)

    @pytest.mark.parametrize("nom,plafond", sorted(DETTE.items()))
    def test_l_inventaire_de_dette_ne_grossit_pas(self, nom, plafond):
        t = _francais_en_dur(nom)
        if t is None:
            pytest.skip("%s absent" % nom)
        assert len(t) <= plafond, (
            "%s : %d alertes en dur pour un plafond de %d — %s"
            % (nom, len(t), plafond, t))

    @pytest.mark.parametrize("nom,plafond", sorted(DETTE.items()))
    def test_l_inventaire_suit_la_REALITE(self, nom, plafond):
        """Sans ce garde-fou, l'inventaire ne maigrirait jamais : on
        nettoierait un fichier et la marge resterait, prête à masquer un
        retour en arrière."""
        t = _francais_en_dur(nom)
        if t is None:
            pytest.skip("%s absent" % nom)
        assert len(t) == plafond, (
            "%s porte %d alertes en dur et le plafond est a %d : BAISSER le "
            "plafond (ou retirer le fichier de DETTE s'il est propre)"
            % (nom, len(t), plafond))


class TestLEcranDesAptitudesLitLeCatalogue:
    """⚠️ Ses six libellés ne sont pas des ALERTES : ce sont des titres et des
    invites écrits dans du HTML (`innerHTML`, `placeholder=`). Le balayage
    ci-dessus ne regarde que `alert(`/`confirm(` — il ne les voyait pas, et
    remettre l'un d'eux en dur le laissait VERT. On garde donc ici ce qui
    compte vraiment : que chaque libellé passe par le catalogue."""

    CLES = ["apt_feasibility", "apt_result", "apt_comment_ph",
            "apt_aids_other_ph", "apt_added_1", "apt_added_n",
            "apt_added_errors"]

    def test_les_six_libelles_passent_par_l_accesseur(self):
        p = os.path.join(JS, "propose_aptitudes.js")
        if not os.path.exists(p):
            pytest.skip("propose_aptitudes.js absent")
        s = io.open(p, encoding="utf-8").read()
        corps = re.sub(r"//[^\n]*", " ", s)
        assert "window.PROPOSE_I18N" in corps, (
            "cet ecran doit lire le catalogue des propositions")
        manquantes = [k for k in self.CLES
                      if ("'%s'" % k) not in corps and ('"%s"' % k) not in corps]
        assert not manquantes, (
            "libelle(s) qui ne passent pas par le catalogue : %s" % manquantes)


class TestLesCataloguesPortentLesCles:
    """Une clé absente ne lève RIEN : l'accesseur rend son repli français, ou
    la clé brute. C'est le silence qu'on ferme ici."""

    CLES_CRUD = [
        "confirm_delete_perf", "confirm_delete_constraint",
        "confirm_delete_hsc", "confirm_delete_role", "confirm_delete_tool",
        "err_read_constraint", "err_no_activity", "err_upload",
        "err_upload_unknown", "err_upload_net", "err_carto_update",
        "added_ok", "summary", "perf_field_missing", "perf_need_name",
        "perf_err_create", "perf_err_create_c", "perf_not_found",
        "perf_err_update", "perf_err_update_c", "perf_err_delete",
    ]
    CLES_PROPOSE = [
        "err_fetch_savoirs", "err_add_savoirs", "err_fetch_proposals",
        "err_bad_response", "err_generic", "apt_feasibility", "apt_result",
        "apt_comment_ph", "apt_aids_other_ph", "apt_added_1", "apt_added_n",
        "apt_added_errors",
    ]

    def _catalogue(self, langue):
        from Code.translations import TRANSLATIONS
        return TRANSLATIONS[langue]

    @pytest.mark.parametrize("langue", ["fr", "en"])
    def test_les_cles_crud_existent_dans_les_deux_langues(self, langue):
        cat = self._catalogue(langue)
        manquantes = [k for k in self.CLES_CRUD if "crud." + k not in cat]
        assert not manquantes, "%s : %s" % (langue, manquantes)

    @pytest.mark.parametrize("langue", ["fr", "en"])
    def test_les_cles_propose_existent_dans_les_deux_langues(self, langue):
        cat = self._catalogue(langue)
        manquantes = [k for k in self.CLES_PROPOSE
                      if "propose." + k not in cat]
        assert not manquantes, "%s : %s" % (langue, manquantes)

    def test_le_francais_et_l_anglais_different_vraiment(self):
        """Une clé recopiée telle quelle d'une langue à l'autre n'a pas été
        traduite : elle passerait tous les contrôles de présence."""
        fr, en = self._catalogue("fr"), self._catalogue("en")
        identiques = []
        for prefixe, cles in (("crud.", self.CLES_CRUD),
                              ("propose.", self.CLES_PROPOSE)):
            for k in cles:
                c = prefixe + k
                if c in fr and c in en and fr[c] == en[c]:
                    identiques.append(c)
        # `added_ok` et `apt_added_errors` sont des gabarits de nombre ;
        # `err_upload_unknown` est un mot. Tout le reste doit differer.
        tolere = {"crud.added_ok"}
        assert not (set(identiques) - tolere), (
            "non traduites (FR == EN) : %s" % sorted(set(identiques) - tolere))


class TestLeCatalogueCrudEstSurTOUTES_LES_PAGES:
    """⚠️ Il n'était injecté que par `display_list.html`. `file-picker.js`
    sert aussi la page Outils, qui n'inclut pas ce gabarit : son message
    d'erreur y retombait sur le repli français. Il vit donc dans
    `header_buttons.html`, que porte chaque page de l'application."""

    def test_header_buttons_injecte_le_catalogue(self):
        p = os.path.join(GABARITS, "header_buttons.html")
        if not os.path.exists(p):
            pytest.skip("header_buttons.html absent")
        s = io.open(p, encoding="utf-8").read()
        # ⚠️ On vise l'AFFECTATION, pas le nom : `window.CRUD_I18N` se
        # retrouve dans `window.CRUD_I18N_DESACTIVE`, et le cliquet restait
        # vert sur le defaut remis. Un controle qui cherche une chaine doit
        # viser l'EMPLOI, pas la presence du nom.
        assert re.search(r"window\.CRUD_I18N\s*=\s*\{", s), (
            "le catalogue CRUD doit vivre dans la nav, qui est sur chaque page")

    def test_display_list_ne_le_redeclare_PAS(self):
        """Deux sources, c'est la derniere rendue qui gagne — et plus
        personne ne sait laquelle."""
        p = os.path.join(GABARITS, "display_list.html")
        if not os.path.exists(p):
            pytest.skip("display_list.html absent")
        s = io.open(p, encoding="utf-8").read()
        s = re.sub(r"\{#.*?#\}", " ", s, flags=re.S)   # les commentaires Jinja
        assert "window.CRUD_I18N =" not in s, (
            "CRUD_I18N est redeclare ici alors qu'il vit dans la nav")

    def test_file_picker_ne_depend_pas_de__CR(self):
        """`optiq_alert.js` — qui définit `_CR` — n'est PAS chargé par la page
        Outils. Un composant partagé par deux pages ne s'appuie que sur ce
        qu'il apporte lui-même."""
        p = os.path.join(JS, "file-picker.js")
        if not os.path.exists(p):
            pytest.skip("file-picker.js absent")
        s = io.open(p, encoding="utf-8").read()
        corps = re.sub(r"//[^\n]*", " ", s)
        assert "_CR(" not in corps, (
            "file-picker.js appelle _CR, absent de la page Outils")
        assert "window.CRUD_I18N" in corps, (
            "il doit lire le catalogue global lui-meme")
