# tests/test_78_i18n_couverture.py
"""
Couverture COMPLÈTE de la traduction français / anglais.

Tout ce qu'un utilisateur lit doit exister dans les deux langues : les textes,
les titres de fenêtre, les messages d'erreur, les listes vides, les info-bulles,
les libellés de boutons. Ce fichier vérifie les quatre mécanismes que l'app
emploie, et surtout la manière dont chacun ÉCHOUE — car aucun ne lève d'erreur :

  1. `Code/translations.py` — `t('cle')`. ⚠️ `t()` retombe en SILENCE sur le
     français quand la clé manque en anglais, puis rend la clé brute quand elle
     manque partout. Rien ne casse : on lit « nav.activities » ou une phrase
     française au milieu d'une page anglaise.
  2. Les catalogues injectés par les gabarits (`window.XXX_I18N`) — le JS y
     puise. ⚠️ Chaque fichier JS embarque un REPLI FRANÇAIS en dur : une clé
     oubliée dans l'injection donne du français à l'anglophone, sans trace.
  3. Le catalogue interne de `competences_v2.js` (`{ fr: {…}, en: {…} }`).
  4. Le rendu réel : on demande les pages EN anglais et on relit ce qui sort.

⚠️ Ces tests lisent des FICHIERS SOURCES (gabarits, JS). Les gabarits et
`static/` vivent dans l'image cliente ; les `.py`, non (image bytecode-only) —
le balayage des sources Python se saute donc de lui-même, comme
`tests/test_67_schema_postgres.py`.
"""
import io
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
GABARITS = RACINE / "Code" / "routes" / "templates"
JS = RACINE / "static" / "js"
SOURCES_PY = RACINE / "Code"


def _lire(chemin):
    return io.open(chemin, encoding="utf-8", errors="replace").read()


def _gabarits():
    return sorted(GABARITS.glob("*.html"))


def _js():
    return sorted(JS.glob("*.js"))


# ══════════════════════════════════════════════════════════════════════
#  Analyse des catalogues injectés  (window.XXX_I18N)
# ══════════════════════════════════════════════════════════════════════
# Une clé d'objet JS : précédée d'une accolade ou d'une virgule, guillemets
# facultatifs.
_CLE = re.compile(r"[{,]\s*(?:['\"])?([A-Za-z_][A-Za-z_0-9]*)(?:['\"])?\s*:")


def _instruction(texte, depart):
    """Le texte de l'instruction ouverte à `depart`, accolades équilibrées.

    ⚠️ L'injection s'écrit `window.X = Object.assign(window.X || {}, { … })` :
    prendre « la première accolade après le = » tombe sur le `{}` du repli et
    ne rend AUCUNE clé — le contrôle passerait alors au vert sans rien voir.
    """
    prof, i, n = 0, depart, len(texte)
    while i < n:
        c = texte[i]
        if c in "{([":
            prof += 1
        elif c in "})]":
            prof -= 1
        elif c == ";" and prof <= 0:
            return texte[depart:i]
        i += 1
    return texte[depart:]


def _injections():
    """{ 'TASK_I18N': {'cles': {...}, 'gabarits': {...}, 'bloc': '...'} }"""
    out = {}
    for f in _gabarits():
        s = _lire(f)
        for m in re.finditer(r"window\.([A-Z_0-9]*I18N)\s*=", s):
            cat = m.group(1)
            bloc = _instruction(s, m.end())
            d = out.setdefault(cat, {"cles": set(), "gabarits": set(), "blocs": []})
            d["cles"].update(_CLE.findall(bloc))
            d["gabarits"].add(f.name)
            d["blocs"].append((f.name, bloc))
    return out


def _helpers_i18n(source):
    """Noms des fonctions du fichier qui lisent un `window.XXX_I18N`.

    C'est par elles que passent presque toutes les lectures : `tl('hours',
    'heures')`, `_CR('cle')`, `_toolI18n('cle')`… Repérer la fonction permet
    ensuite de relever les clés LITTÉRALES qu'on lui passe — bien plus sûr que
    de deviner quel objet du fichier sert de repli.
    """
    noms = {}
    for m in re.finditer(r"function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", source):
        nom, debut = m.group(1), m.end() - 1
        corps = _instruction(source, debut)
        # ⚠️ Le compteur d'accolades ne saute ni les chaînes ni les expressions
        # régulières : une accolade dans un littéral déséquilibre le décompte et
        # le « corps » court jusqu'à la fin du fichier. On attribuait alors à
        # l'accesseur TOUTES les chaînes du fichier — d'où des « clés » comme
        # « carto-wizard-popup », qui est un identifiant de DOM. Un accesseur
        # i18n tient en quelques lignes : au-delà, ce n'en est pas un.
        if len(corps) > 1200:
            continue
        cats = set(re.findall(r"window\.([A-Z_0-9]*I18N)", corps))
        if cats:
            noms[nom] = cats
    return noms


def _cles_lues(source):
    """{ 'TASK_I18N': {clés demandées littéralement} } pour UN fichier JS."""
    lues = {}

    def ajoute(cat, cle):
        lues.setdefault(cat, set()).add(cle)

    # a) accès direct : TASK_I18N.empty  /  TASK_I18N['empty']
    for m in re.finditer(r"\b([A-Z_0-9]*I18N)\s*(?:\.\s*([A-Za-z_]\w*)"
                         r"|\[\s*['\"]([^'\"]+)['\"]\s*\])", source):
        cle = m.group(2) or m.group(3)
        if cle:
            ajoute(m.group(1), cle)

    # b) via un alias : const L = window.TASK_I18N || {};  puis  L.empty
    for m in re.finditer(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
                         r"window\.([A-Z_0-9]*I18N)", source):
        alias, cat = m.group(1), m.group(2)
        for a in re.finditer(r"\b%s\s*(?:\.\s*([A-Za-z_]\w*)"
                             r"|\[\s*['\"]([^'\"]+)['\"]\s*\])" % re.escape(alias),
                             source):
            cle = a.group(1) or a.group(2)
            if cle:
                ajoute(cat, cle)

    # b bis) la forme repliée : (window.PROPOSE_I18N || {}).result_singular
    for m in re.finditer(r"\(\s*window\.([A-Z_0-9]*I18N)\s*\|\|[^)]*\)\s*"
                         r"(?:\.\s*([A-Za-z_]\w*)|\[\s*['\"]([^'\"]+)['\"]\s*\])", source):
        cle = m.group(2) or m.group(3)
        if cle:
            ajoute(m.group(1), cle)

    # c) via une fonction d'accès : tl('hours', 'heures'), _CR('cle')…
    #    On n'accepte qu'un littéral en FORME DE CLÉ : ces accesseurs reçoivent
    #    aussi des identifiants de DOM, qui n'ont rien à faire dans un catalogue.
    forme_cle = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")
    for nom, cats in _helpers_i18n(source).items():
        for a in re.finditer(r"\b%s\s*\(\s*['\"]([^'\"]+)['\"]" % re.escape(nom), source):
            if not forme_cle.match(a.group(1)):
                continue
            for cat in cats:
                ajoute(cat, a.group(1))
    return lues


# ══════════════════════════════════════════════════════════════════════
#  1 · Le catalogue Python
# ══════════════════════════════════════════════════════════════════════
class TestCataloguePython:
    """`Code/translations.py` — la source de tout ce qui est rendu par le
    serveur. Une asymétrie ici donne une page anglaise à moitié française."""

    def test_les_deux_langues_portent_exactement_les_memes_cles(self):
        from Code.translations import TRANSLATIONS

        fr, en = set(TRANSLATIONS["fr"]), set(TRANSLATIONS["en"])
        manque_en = sorted(fr - en)
        manque_fr = sorted(en - fr)
        assert not manque_en, (
            "%d clé(s) sans version ANGLAISE — l'anglophone lira du français "
            "sans que rien ne le signale : %s" % (len(manque_en), manque_en[:15]))
        assert not manque_fr, (
            "%d clé(s) sans version FRANÇAISE : %s" % (len(manque_fr), manque_fr[:15]))

    def test_aucune_traduction_vide(self):
        """Une chaîne vide passe tous les contrôles d'existence et n'affiche
        RIEN à l'écran — un bouton sans libellé, une colonne sans titre."""
        from Code.translations import TRANSLATIONS

        vides = [(lg, k) for lg, d in TRANSLATIONS.items()
                 for k, v in d.items() if not str(v).strip()]
        assert not vides, "traductions vides : %s" % vides[:15]

    def test_les_variables_survivent_a_la_traduction(self):
        """Un libellé porte parfois un trou à remplir — `{n}`, `[[n]]`, `%s`.
        S'il disparaît de la version anglaise, le nombre ne s'affiche plus ;
        s'il change de nom, le remplacement échoue en silence."""
        from Code.translations import TRANSLATIONS

        motif = re.compile(r"\{\w+\}|\[\[\w+\]\]|%[sd]")
        ecarts = []
        for k, v_fr in TRANSLATIONS["fr"].items():
            v_en = TRANSLATIONS["en"].get(k)
            if v_en is None:
                continue
            a, b = sorted(motif.findall(str(v_fr))), sorted(motif.findall(str(v_en)))
            if a != b:
                ecarts.append((k, a, b))
        assert not ecarts, "variables différentes entre FR et EN : %s" % ecarts[:10]

    def test_aucune_cle_employee_dans_un_gabarit_n_est_absente(self):
        """⚠️ `t('cle.inconnue')` ne lève RIEN : la clé brute s'affiche telle
        quelle. « conf_done_go » s'est déjà retrouvé écrit sur un bouton."""
        from Code.translations import TRANSLATIONS

        emploi = re.compile(r"\bt\(\s*['\"]([a-zA-Z0-9_.\-]+)['\"]")
        inconnues = {}
        for f in _gabarits():
            for cle in set(emploi.findall(_lire(f))):
                if "." not in cle:
                    continue        # `t('x')` sans point n'est pas une clé
                if cle not in TRANSLATIONS["fr"] or cle not in TRANSLATIONS["en"]:
                    inconnues.setdefault(cle, []).append(f.name)
        assert not inconnues, (
            "clé(s) employée(s) dans un gabarit mais absente(s) du catalogue — "
            "elles s'afficheront telles quelles : %s" % dict(list(inconnues.items())[:10]))

    def test_aucune_cle_employee_dans_le_code_python_n_est_absente(self):
        """⚠️ Sauté dans l'arbre d'image : les `.py` y sont compilés en `.pyc`
        et les sources n'existent plus (même parti pris que test_67)."""
        from Code.translations import TRANSLATIONS

        sources = sorted(SOURCES_PY.rglob("*.py"))
        if len(sources) < 5:
            pytest.skip("sources Python absentes (arbre bytecode-only)")

        emploi = re.compile(r"\bt\(\s*['\"]([a-zA-Z0-9_.\-]+)['\"]")
        inconnues = {}
        for f in sources:
            if f.name == "translations.py":
                continue
            for cle in set(emploi.findall(_lire(f))):
                if "." not in cle:
                    continue
                if cle not in TRANSLATIONS["fr"] or cle not in TRANSLATIONS["en"]:
                    inconnues.setdefault(cle, []).append(f.name)
        assert not inconnues, (
            "clé(s) employée(s) dans une route mais absente(s) du catalogue : %s"
            % dict(list(inconnues.items())[:10]))

    def test_le_repli_rend_la_cle_et_jamais_une_autre_langue(self):
        """Contrat de `t()` : clé inconnue → la clé elle-même. C'est ce qui rend
        un oubli VISIBLE à l'écran plutôt que silencieux."""
        from Code.translations import t

        assert t("cle.qui.nexiste.pas", lang="en") == "cle.qui.nexiste.pas"
        assert t("cle.qui.nexiste.pas", lang="fr") == "cle.qui.nexiste.pas"
        # Langue inconnue → français, pas une erreur.
        assert t("nav.activities", lang="xx") == t("nav.activities", lang="fr")


# ══════════════════════════════════════════════════════════════════════
#  2 · Les catalogues injectés dans le JS
# ══════════════════════════════════════════════════════════════════════
class TestInjectionsDesGabarits:
    """Tout ce que le JS affiche vient d'un `window.XXX_I18N` posé par un
    gabarit. Ce qui n'y passe pas n'est jamais traduit."""

    def test_chaque_valeur_injectee_passe_par_le_catalogue(self):
        """Une chaîne écrite en dur dans une injection ne suit pas la langue.
        Elle a l'air traduite — elle est dans un objet i18n — et ne l'est pas."""
        dures = []
        for cat, d in _injections().items():
            for nom, bloc in d["blocs"]:
                for m in re.finditer(r"[{,]\s*(?:['\"])?([A-Za-z_]\w*)(?:['\"])?\s*:"
                                     r"\s*([^,\n}]+)", bloc):
                    cle, val = m.group(1), m.group(2).strip()
                    if val.startswith(("{{", "{%")) or val in ("{", "["):
                        continue
                    if re.fullmatch(r"(true|false|null|\d+|window\.[\w.]+|\w+)", val):
                        continue
                    dures.append("%s · %s.%s = %s" % (nom, cat, cle, val[:40]))
        assert not dures, (
            "valeur(s) écrite(s) en dur dans une injection i18n — elles ne "
            "suivront jamais la langue : %s" % dures[:10])

    def test_aucune_traduction_entre_guillemets_dans_un_script(self):
        """⚠️ Le navigateur décode les entités HTML dans un ATTRIBUT, jamais
        dans un `<script>`. `"{{ t('propose.err_saving') }}"` arrive donc dans
        le JS avec « n&#39;est » écrit en toutes lettres, et s'affiche ainsi.
        `| tojson` produit une vraie chaîne JS (`n\\u0027est`).

        Relevé au moment d'écrire ce test : **34 occurrences**, dont 7 déjà
        visiblement abîmées. En attribut HTML la même écriture est correcte —
        d'où le découpage strict par bloc `<script>`.
        """
        script = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
        guillemete = re.compile(r"""(['"])\{\{\s*(t\(.*?\))\s*\}\}\1""", re.S)
        fautes = []
        for f in _gabarits():
            for bloc in script.finditer(_lire(f)):
                for m in guillemete.finditer(bloc.group(1)):
                    if "tojson" in m.group(2):
                        continue
                    fautes.append("%s · %s" % (f.name, m.group(2)[:46]))
        assert not fautes, (
            "traduction entre guillemets dans un <script> au lieu de "
            "`|tojson` — les apostrophes sortiront en entités HTML : %s"
            % fautes[:12])

    def test_toute_cle_lue_par_le_js_est_injectee(self):
        """⚠️ LE défaut à attraper. Chaque JS embarque un repli français ; si
        le gabarit oublie une clé, `L[cle]` est `undefined` et l'anglophone
        reçoit le repli — en français, sans erreur, sans trace."""
        inj = _injections()
        oublis = []
        for f in _js():
            for cat, cles in _cles_lues(_lire(f)).items():
                connues = inj.get(cat, {}).get("cles")
                if connues is None:
                    continue        # catalogue posé ailleurs (voir OPTIQ_I18N)
                for cle in sorted(cles - connues):
                    oublis.append("%s lit %s.%s — jamais injecté" % (f.name, cat, cle))
        assert not oublis, (
            "clé(s) lue(s) par le JS mais absente(s) de l'injection : %s" % oublis[:15])


# ══════════════════════════════════════════════════════════════════════
#  3 · Le catalogue interne de la page Compétences
# ══════════════════════════════════════════════════════════════════════
class TestCatalogueCompetences:
    """`competences_v2.js` porte ses ~194 libellés × 2 langues dans le fichier.
    Même règle, mêmes pièges — et une part importante de l'app passe par là."""

    FICHIER = JS / "competences_v2.js"

    def _tranches(self):
        """(clés fr, clés en, corps) — commentaires retirés.

        ⚠️ Deux versions de ce découpage ont crié sur des dizaines de faux
        positifs : l'une ne voyait que les clés en DÉBUT de ligne (elles sont
        indentées, souvent plusieurs par ligne), l'autre les cherchait derrière
        une virgule, ce qui rate la première clé qui suit un commentaire.
        """
        s = re.sub(r"^\s*//.*$", "", _lire(self.FICHIER), flags=re.M)
        i, j = s.index("    fr: {"), s.index("    en: {")
        k = s.index("\n  };", j)
        c0 = s.index("const COMMUN = {")
        cle = re.compile(r"(?:^\s*|[{,]\s*)([a-z_][a-z_0-9]*)\s*:", re.M)

        def lot(a, b):
            return set(cle.findall(s[a:b])) - {"fr", "en"}

        # `COMMUN` est recopié dans les deux langues au chargement.
        commun = lot(c0, s.index("\n  };", c0))
        return lot(i, j) | commun, lot(j, k) | commun, s[k:]

    def test_les_deux_langues_portent_les_memes_cles(self):
        fr, en, _ = self._tranches()
        assert not (fr ^ en), (
            "clé(s) déclarée(s) d'un seul côté — la page basculerait de langue "
            "au milieu d'une phrase : %s" % sorted(fr ^ en)[:15])

    def test_aucune_cle_employee_n_est_absente(self):
        fr, _, corps = self._tranches()
        employees = set(re.findall(r"\bTv?\(\s*'([a-z_][a-z_0-9]*)'", corps))
        # Clés composées à la volée : T('ia_conf_' + conf), T('q_dit_' + n)…
        prefixes = re.findall(r"\bTv?\(\s*'([a-z_][a-z_0-9]*_)'\s*\+", corps)
        manquantes = sorted(c for c in employees - fr
                            if not any(c.startswith(p) for p in prefixes))
        assert not manquantes, (
            "clé(s) employée(s) mais jamais déclarée(s) — elles s'afficheront "
            "brutes, comme « conf_done_go » sur son bouton : %s" % manquantes)

    def test_le_catalogue_est_bien_garni(self):
        """Garde-fou du découpage lui-même : si un jour les repères changent et
        que l'analyse ne trouve plus rien, les deux tests au-dessus passeraient
        au vert en ne regardant RIEN."""
        fr, en, _ = self._tranches()
        assert len(fr) > 150 and len(en) > 150, (
            "analyse du catalogue cassée : %d clés FR / %d EN" % (len(fr), len(en)))


# ══════════════════════════════════════════════════════════════════════
#  4 · Le rendu RÉEL : on demande les pages en anglais et on relit
# ══════════════════════════════════════════════════════════════════════
def _texte_visible(html, garder_data_i18n=False):
    """Ce qu'un lecteur voit : sans script, sans style, sans commentaire.

    ⚠️ Un élément porteur de `data-i18n` est servi EN FRANÇAIS puis réécrit par
    le JS (`applyStaticI18n`) : son texte de gabarit n'est qu'un brouillon, il
    ne dit rien de ce que l'utilisateur lit. On l'écarte ici — et on le garde
    par un contrôle dédié, `TestDataI18n`, qui vérifie que la clé annoncée
    existe vraiment dans le catalogue JS. Sans ce second contrôle, une clé
    absente laisserait le français en place sans que rien ne le dise.
    """
    h = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    h = re.sub(r"<style\b.*?</style>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<!--.*?-->", " ", h, flags=re.S)
    if not garder_data_i18n:
        h = re.sub(r"<[^>]*\bdata-i18n\s*=[^>]*>[^<]*", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", h)


class TestDataI18n:
    """Le second mécanisme de la page Compétences : le gabarit écrit le
    français et pose `data-i18n="cle"`, le JS remplace au chargement.

    ⚠️ Si la clé n'existe pas dans le catalogue, `applyStaticI18n` ne remplace
    RIEN et le français reste affiché — en anglais comme en français, sans la
    moindre trace. C'est exactement le mode d'échec que ce contrôle ferme.
    """

    def test_toute_cle_data_i18n_existe_dans_le_catalogue_js(self):
        catalogue = _lire(JS / "competences_v2.js")
        sans_com = re.sub(r"^\s*//.*$", "", catalogue, flags=re.M)
        cle = re.compile(r"(?:^\s*|[{,]\s*)([a-z_][a-z_0-9]*)\s*:", re.M)
        i, j = sans_com.index("    fr: {"), sans_com.index("    en: {")
        k = sans_com.index("\n  };", j)
        c0 = sans_com.index("const COMMUN = {")
        declarees = (set(cle.findall(sans_com[i:j]))
                     | set(cle.findall(sans_com[j:k]))
                     | set(cle.findall(sans_com[c0:sans_com.index(chr(10) + "  };", c0)])))

        inconnues = []
        for f in _gabarits():
            for m in re.finditer(r"data-i18n\s*=\s*['\"]([^'\"]+)['\"]", _lire(f)):
                if m.group(1) not in declarees:
                    inconnues.append("%s · %s" % (f.name, m.group(1)))
        assert not inconnues, (
            "clé(s) `data-i18n` absente(s) du catalogue JS — le français du "
            "gabarit resterait affiché tel quel : %s" % inconnues[:12])


class TestRenduAnglais:
    """Le contrôle qui ne dépend d'AUCUN mécanisme.

    On demande les pages en anglais, et on cherche dedans les chaînes
    FRANÇAISES du catalogue. C'est exact par construction : une phrase du
    catalogue français n'a aucune raison d'apparaître sur une page anglaise.
    ⚠️ Et cela ne se trompe jamais sur les DONNÉES — les noms d'activités, de
    rôles ou d'entités sont français dans le jeu de test, mais ils ne sont pas
    dans le catalogue, donc jamais relevés.
    """

    # ⚠️ Un piège doit être une PHRASE. Les libellés d'un seul mot — « Rôle »,
    # « Savoir-faire », « Compétences » — sont aussi des noms que les
    # utilisateurs donnent à leurs objets : « Savoir-faire » est arrivé sur la
    # page Activités en anglais parce qu'un AUTRE fichier de tests avait créé
    # un savoir-faire portant ce nom. Le défaut ne se voyait qu'en suite
    # complète, la base étant partagée. Exiger une espace écarte cette classe
    # entière de coïncidences sans rien perdre d'utile : une phrase
    # d'interface qui fuit en porte toujours une.
    LONGUEUR_MIN = 12

    # ⚠️ Une route inexistante rend 404, donc `skip` — la page passait pour
    # contrôlée sans l'être. Ces chemins sont ceux de `url_map`.
    PAGES = [
        "/parametres/", "/activities/view", "/gestion_rh/", "/roles_view/",
        "/competences/view", "/temps/", "/gestion_outils/", "/share/",
        "/projection_metier/", "/cartography/viewer", "/activities/map",
    ]

    def _pieges(self):
        """Chaînes FR qui trahiraient une page anglaise, avec leur clé."""
        from Code.translations import TRANSLATIONS

        out = []
        for cle, v_fr in TRANSLATIONS["fr"].items():
            v_en = TRANSLATIONS["en"].get(cle)
            v_fr = str(v_fr).strip()
            if not v_en or str(v_en).strip() == v_fr:
                continue                       # identique dans les deux langues
            if len(v_fr) < self.LONGUEUR_MIN or " " not in v_fr:
                continue
            if v_fr in str(v_en):
                continue                       # le FR est inclus dans l'EN
            out.append((cle, v_fr))
        return out

    def test_le_jeu_de_pieges_est_consequent(self):
        """Garde-fou : si le catalogue ou le seuil changeaient au point de ne
        plus rien retenir, le test suivant passerait au vert sans rien lire."""
        assert len(self._pieges()) > 300, (
            "seulement %d chaînes françaises testables" % len(self._pieges()))

    def _donnees(self, app):
        """Noms saisis par les utilisateurs : rôles, entités, activités.

        ⚠️ Le jeu de test porte des libellés FRANÇAIS — `test_73` crée un rôle
        « Développeur de compétences », qui est aussi une clé du catalogue. La
        page anglaise l'affiche légitimement : c'est une DONNÉE, pas un libellé
        d'interface. Sans ce filtre, le contrôle accusait la page Temps à tort.
        """
        from Code.models.models import (Activities, Aptitude, Competency,
                                         Entity, Role, Savoir, SavoirFaire,
                                         Softskill, Task, Tool)

        # Chaque modèle porte son libellé sous un nom différent : on prend le
        # premier qui existe. Un modèle qui n'en a aucun est simplement ignoré.
        modeles = (Role, Entity, Activities, Task, Tool, Competency,
                   Savoir, SavoirFaire, Softskill, Aptitude)
        with app.app_context():
            session = app.extensions["sqlalchemy"].session
            noms = set()
            for modele in modeles:
                colonne = next((getattr(modele, c) for c in
                                ("name", "description", "habilete")
                                if hasattr(modele, c)), None)
                if colonne is None:
                    continue
                try:
                    for (n,) in session.query(colonne).all():
                        if n:
                            noms.add(str(n).strip())
                except Exception:
                    session.rollback()
            return noms

    @pytest.mark.parametrize("route", PAGES)
    def test_aucune_phrase_francaise_sur_la_page_anglaise(self, app, auth_client, route):
        donnees = self._donnees(app)
        pieges = [(c, t) for c, t in self._pieges() if t not in donnees]
        auth_client.post("/parametres/set_language", json={"lang": "en"})
        try:
            r = auth_client.get(route)
            if r.status_code != 200:
                pytest.skip("%s rend %d dans le jeu de test" % (route, r.status_code))
            visible = _texte_visible(r.data.decode("utf-8", "replace"))
            fuites = [(cle, txt) for cle, txt in pieges if txt in visible]
            assert not fuites, (
                "%s affiche %d libellé(s) FRANÇAIS en anglais : %s"
                % (route, len(fuites),
                   ["%s → %s" % (c, t[:52]) for c, t in fuites[:8]]))
        finally:
            auth_client.post("/parametres/set_language", json={"lang": "fr"})

    def test_la_page_francaise_reste_francaise(self, auth_client):
        """Symétrique : le mécanisme doit marcher dans les deux sens. Sans ce
        cas, une page qui n'afficherait RIEN passerait le test ci-dessus."""
        from Code.translations import TRANSLATIONS

        auth_client.post("/parametres/set_language", json={"lang": "fr"})
        visible = _texte_visible(auth_client.get("/parametres/").data.decode())
        assert TRANSLATIONS["fr"]["settings.title"] in visible
        assert TRANSLATIONS["en"]["settings.subtitle"] not in visible


# ══════════════════════════════════════════════════════════════════════
#  5 · Le français écrit EN DUR dans les gabarits
# ══════════════════════════════════════════════════════════════════════
_ACCENTS = "àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ"
_MOTS_FR = (r"\b(?:le|la|les|des|une|aux|pour|avec|dans|sans|vous|votre|aucun"
            r"|aucune|cette|ce|est|sont|pas|plus|tous|toutes|ou|et|par|sur|du|au)\b")


def _fragments_francais(html):
    """Textes visibles d'un gabarit qui sont manifestement du français.

    On retire tout ce qui n'est pas lu tel quel : scripts, styles, commentaires
    Jinja et HTML, expressions `{{ }}` / `{% %}`, et les éléments porteurs de
    `data-i18n` (traduits par le JS au chargement).
    """
    h = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    h = re.sub(r"<style\b.*?</style>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<!--.*?-->", " ", h, flags=re.S)
    h = re.sub(r"\{#.*?#\}", " ", h, flags=re.S)
    h = re.sub(r"<[^>]*\bdata-i18n\s*=[^>]*>[^<]*", " ", h)
    h = re.sub(r"\{%.*?%\}", " ", h, flags=re.S)
    h = re.sub(r"\{\{.*?\}\}", " ", h, flags=re.S)

    out = []
    for m in re.finditer(r">([^<>]{3,})<", h):
        txt = re.sub(r"&[a-z]+;|&#\d+;", " ", m.group(1))
        txt = re.sub(r"\s+", " ", txt).strip()
        if len(txt) < 3:
            continue
        if any(c in _ACCENTS for c in txt) or len(re.findall(_MOTS_FR, txt.lower())) >= 2:
            out.append(txt)
    return out


class TestFrancaisEnDur:
    """Du texte écrit directement dans un gabarit ne passe par AUCUN
    mécanisme : il reste français quelle que soit la langue choisie.

    ⚠️ Ce contrôle est un CLIQUET, pas un mur. Relevé le 16/09/2026 : 78
    fragments sur 12 gabarits, dont trois écrans jamais traduits
    (`import_full_modal`, `projection_metier`, `import_tasks_modal`). Les
    traduire demande d'écrire de vraies tournures anglaises, pas de déplacer du
    texte — c'est un travail à part entière. En attendant, la dette est ÉCRITE
    ici, et elle ne peut que décroître : un gabarit absent de l'inventaire doit
    être propre, et un gabarit présent ne doit pas empirer.

    ✅ 17/09/2026 — `import_full_modal` est SORTI de l'inventaire : l'écran
    entier passe par le catalogue (`impf.*`), y compris les phrases bâties par
    `import_full.js` et celles que la route RENVOIE (`analysis_notes`, motifs
    d'appariement, erreurs). Le cliquet a fait son travail : il a refusé de
    laisser le plafond à 25 pour 0 fragment réel.
    """

    # gabarit → nombre de fragments français tolérés aujourd'hui.
    DETTE = {
        "projection_metier.html":       14,
        "import_tasks_modal.html":      10,
        "cartography_editor.html":       7,
        "chatbot_widget.html":           5,
        "license_blocked.html":          4,
        "activities_map.html":           3,
        "cartography_viewer.html":       2,
        "setup_wizard.html":             2,
        "settings.html":                 1,
        # `gestion_compte_new.html` est sorti de l'inventaire : la page Comptes
        # a été refaite, tout y passe par le catalogue.
    }

    def test_aucun_gabarit_neuf_ne_porte_du_francais_en_dur(self):
        surprises = {}
        for f in _gabarits():
            if f.name in self.DETTE:
                continue
            fr = _fragments_francais(_lire(f))
            if fr:
                surprises[f.name] = fr[:3]
        assert not surprises, (
            "gabarit(s) hors inventaire portant du français en dur — ce texte "
            "restera français en anglais : %s" % surprises)

    @pytest.mark.parametrize("gabarit", sorted(DETTE))
    def test_la_dette_ne_grandit_pas(self, gabarit):
        chemin = GABARITS / gabarit
        if not chemin.exists():
            pytest.skip("%s n'existe plus" % gabarit)
        fr = _fragments_francais(_lire(chemin))
        plafond = self.DETTE[gabarit]
        assert len(fr) <= plafond, (
            "%s porte %d fragments français en dur (plafond %d) — %s"
            % (gabarit, len(fr), plafond, fr[:4]))

    def test_l_inventaire_suit_la_realite(self):
        """Un plafond devenu trop large masquerait un retour en arrière : quand
        un gabarit est nettoyé, son chiffre doit descendre avec lui."""
        trop_larges = []
        for nom, plafond in self.DETTE.items():
            chemin = GABARITS / nom
            if not chemin.exists():
                continue
            reel = len(_fragments_francais(_lire(chemin)))
            if reel < plafond:
                trop_larges.append("%s : %d toléré(s) pour %d réel(s)"
                                   % (nom, plafond, reel))
        assert not trop_larges, (
            "inventaire à resserrer — la dette a baissé, le plafond doit "
            "suivre : %s" % trop_larges)
