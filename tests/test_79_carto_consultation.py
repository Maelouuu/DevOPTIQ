# tests/test_79_carto_consultation.py
"""
L'éditeur ouvert par quelqu'un qui n'a que le droit de CONSULTER.

Le palier `user` regarde la cartographie ; il ne la modifie pas et ne propose
rien. Le serveur le refusait déjà (`/api/save` et `/api/changes`) — mais
l'écran, lui, offrait encore toute la panoplie de l'éditeur :

⚠️ **Le glisser-déposer HTML5 ne passe PAS par `onDown`.** Le garde de lecture
seule vivait dans le gestionnaire `mousedown` du canevas ; tirer une forme
depuis la barre d'outils emprunte `dragstart` → `dragover` → `drop`, qui ne le
croisent jamais. Un compte en lecture seule posait donc des activités sur la
carto, et ne l'apprenait qu'à l'enregistrement — après le travail.

Ce fichier tient les deux bouts : ce que le gabarit ANNONCE (le drapeau et la
classe), et ce que le code REFUSE. Il vérifie aussi que le dépôt ne peut plus
fabriquer une forme hors du domaine des nombres — mesuré : un « ajuster » joué
sur un canevas pas encore posé rendait un zoom NUL, la division par ce zéro
envoyait la forme à l'infini, et la carto entière devenait illisible.

⚠️ Les boutons sont MASQUÉS, jamais retirés du document : `editor.js` les câble
sans garde, et un id absent lève une TypeError qui interrompt toute l'init —
chargement de la carto compris (cf. `tests/test_49_carto_dom_contract.py`).
"""
import io
import os
import re

import pytest

pytestmark = pytest.mark.cartography_editor

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITOR_JS = os.path.join(RACINE, "static", "optiqcarto", "editor.js")
STYLE_CSS = os.path.join(RACINE, "static", "optiqcarto", "style.css")
GABARIT = os.path.join(RACINE, "Code", "routes", "templates",
                       "cartography_editor.html")


def _lire(chemin):
    return io.open(chemin, encoding="utf-8").read()


def _corps(source, entete):
    """Le corps d'une fonction, accolades équilibrées."""
    debut = source.index(entete)
    i = source.index("{", debut)
    prof, j = 0, i
    while j < len(source):
        if source[j] == "{":
            prof += 1
        elif source[j] == "}":
            prof -= 1
            if prof == 0:
                return source[i:j + 1]
        j += 1
    raise AssertionError("corps non refermé : %s" % entete)


ANCRE_DEPOT = "canvas.addEventListener('drop'"


# ══════════════════════════════════════════════════════════════════════
#  1 · Ce que le code REFUSE
# ══════════════════════════════════════════════════════════════════════
class TestCeQueLEditeurRefuse:

    def test_le_depot_d_une_forme_est_refuse_en_lecture_seule(self):
        """Le chemin par lequel une activité arrivait quand même sur la carto."""
        js = _lire(EDITOR_JS)
        bloc = js[js.index(ANCRE_DEPOT):][:2200]
        assert "OPTIQCARTO_READONLY" in bloc, (
            "le gestionnaire `drop` ne consulte pas la lecture seule — "
            "un compte qui consulte peut déposer une activité")
        # Le refus doit précéder la création de la forme.
        assert (bloc.index("OPTIQCARTO_READONLY")
                < bloc.index("state.shapes.push")), (
            "le refus doit précéder la création de la forme")

    def test_on_ne_peut_meme_pas_tirer_la_forme_depuis_la_barre(self):
        """Refuser au lâcher, c'est laisser espérer pendant tout le trajet."""
        js = _lire(EDITOR_JS)
        departs = [m.start()
                   for m in re.finditer(r"addEventListener\('dragstart'", js)]
        palette = [d for d in departs if "text/shape-subtype" in js[d:d + 500]]
        assert len(palette) >= 2, "les deux sources de formes doivent être vues"
        for d in palette:
            assert "OPTIQCARTO_READONLY" in js[d:d + 400], (
                "un `dragstart` de la palette n'est pas gardé")

    @pytest.mark.parametrize("fonction", [
        "function undo() {",
        "function redo() {",
        "function deleteSelected() {",
        "function createGroup() {",
        "function createPile() {",
        "async function saveJSON() {",
    ])
    def test_les_fonctions_qui_ecrivent_se_refusent_elles_memes(self, fonction):
        """⚠️ Masquer un bouton ne désarme pas son raccourci clavier.

        Suppr, Ctrl+Z, Ctrl+S et « G » appellent ces fonctions directement. Et
        en consultation on SÉLECTIONNE désormais une forme pour lire sa fiche :
        sans garde, Suppr l'aurait retirée de l'écran sans rien enregistrer —
        une carto fausse sous les yeux.
        """
        js = _lire(EDITOR_JS)
        corps = _corps(js, fonction)
        assert "OPTIQCARTO_READONLY" in corps[:220], (
            "%s n'a pas de garde de lecture seule" % fonction)


# ══════════════════════════════════════════════════════════════════════
#  2 · Un zoom nul empoisonnait la carto
# ══════════════════════════════════════════════════════════════════════
class TestLeZoomNePeutPasValoirZero:
    """Mesuré : `fitView()` joué sur un canevas de largeur 0 (onglet caché,
    volet replié) posait `scale(0)`. `screenToSVG` divise par ce facteur : la
    forme déposée naissait à une coordonnée infinie, `_fitShapeIntoBand`
    ajoutait cet infini à la hauteur d'une bande, le rendu jetait des attributs
    SVG « NaN » — et l'enregistrement aurait propagé le tout en base."""

    def test_fitview_borne_le_facteur_et_refuse_un_canevas_degenere(self):
        # `bornes` et `plancher` : un cadre imposé et un zoom minimum plus bas,
        # pour les vignettes de la comparaison avant / après. Le plancher reste
        # STRICTEMENT positif — c'est tout l'objet de ce test.
        corps = _corps(_lire(EDITOR_JS), "function fitView(bornes, plancher) {")
        assert "ZOOM_MIN" in corps, "fitView ne borne pas le zoom par le bas"
        assert "plancher > 0" in corps, "un plancher nul rendrait un zoom nul possible"
        assert "r.width > 0" in corps and "r.height > 0" in corps, (
            "fitView doit renoncer sur un canevas pas encore posé")
        assert "Number.isFinite(dw)" in corps and "Number.isFinite(dh)" in corps, (
            "des bornes non finies ne donnent pas un zoom")

    def test_screentosvg_ne_divise_jamais_par_zero(self):
        corps = _corps(_lire(EDITOR_JS), "function screenToSVG(sx, sy) {")
        assert "/ vpScale" not in corps, (
            "screenToSVG divise encore par le zoom brut")
        assert "vpScale > 0" in corps and "Number.isFinite(vpScale)" in corps

    def test_la_vue_ne_peut_plus_devenir_illisible(self):
        """Dernier filet : un `scale(0)` ou un `translate(NaN,NaN)` ne lève
        AUCUNE exception — la carto disparaît simplement, le navigateur
        s'étrangle sur des attributs SVG « NaN », et la page paraît gelée. Les
        chemins connus sont bouchés en amont ; celui-ci ferme les autres."""
        corps = _corps(_lire(EDITOR_JS), "function applyViewport() {")
        for garde in ("Number.isFinite(vpX)", "Number.isFinite(vpY)",
                      "Number.isFinite(vpScale)", "vpScale <= 0"):
            assert garde in corps, "applyViewport ne vérifie pas %s" % garde
        assert corps.index("vpScale = 0.5") < corps.index("setAttribute"), (
            "le repli doit être posé AVANT d'écrire la transformation")

    def test_le_depot_refuse_un_point_hors_des_nombres(self):
        js = _lire(EDITOR_JS)
        bloc = js[js.index(ANCRE_DEPOT):][:2200]
        assert "Number.isFinite(x)" in bloc and "Number.isFinite(y)" in bloc, (
            "une forme née hors du domaine des nombres empoisonne la carto "
            "pour de bon — on ne dépose rien plutôt que n'importe quoi")


# ══════════════════════════════════════════════════════════════════════
#  3 · Le défilement au bord ne s'emballe plus
# ══════════════════════════════════════════════════════════════════════
class TestLeDefilementAuBordSArrete:
    """`_edgeScrollStep` se rappelle lui-même tant qu'une vitesse est posée, et
    SEULS un mousemove ou une sortie du canevas l'arrêtaient. Or un
    glisser-déposer HTML5 n'émet ni l'un ni l'autre : une fois lancé, la carto
    filait toute seule sous le pointeur et la forme atterrissait ailleurs que
    là où on visait."""

    @pytest.mark.parametrize("evenement",
                             ["mouseup", "dragstart", "dragend", "drop", "blur"])
    def test_la_fin_d_un_geste_coupe_le_defilement(self, evenement):
        js = _lire(EDITOR_JS)
        bloc = js[js.index("function _stopEdgeScroll"):][:2000]
        assert "'%s'" % evenement in bloc, (
            "« %s » ne coupe pas le défilement au bord" % evenement)

    def test_l_animation_en_cours_est_bien_annulee(self):
        corps = _corps(_lire(EDITOR_JS), "function _stopEdgeScroll() {")
        assert "cancelAnimationFrame" in corps, (
            "remettre la vitesse à zéro ne suffit pas : la frame déjà demandée "
            "s'exécute encore")


# ══════════════════════════════════════════════════════════════════════
#  4 · Ce que l'écran montre — et ne montre plus
# ══════════════════════════════════════════════════════════════════════
# Les contrôles que le palier `user` ne doit PAS voir, et l'id ou la classe qui
# les désigne dans la feuille de style.
CACHES = [
    ("annuler",        "#btn-undo"),
    ("rétablir",       "#btn-redo"),
    ("sélection box",  "#btn-lasso-select"),
    ("bandes / formes / calques / grouper / pile", ".tb-section--create"),
    ("curseur labels", "#label-pos-ctl"),
    ("vérifier",       "#btn-architect"),
    ("supprimer",      "#btn-delete"),
    ("enregistrer",    "#btn-save"),
    ("charger",        "#btn-load"),
    ("importer visio", "#btn-import-vsdx"),
]


class TestLaBarreDOutilsEnConsultation:

    @pytest.mark.parametrize("libelle,selecteur", CACHES,
                             ids=[c[1].lstrip("#.") for c in CACHES])
    def test_le_controle_est_masque(self, libelle, selecteur):
        css = _lire(STYLE_CSS)
        assert "body.carto-consultation %s" % selecteur in css, (
            "« %s » (%s) reste visible pour un compte qui consulte"
            % (libelle, selecteur))

    @pytest.mark.parametrize("selecteur", [
        "#btn-export-svg", "#btn-export-pdf", "#btn-export-carto",
        "#btn-fit", "#btn-folder-toggle", "#btn-right-panel-open",
    ])
    def test_ce_qui_reste_n_est_pas_masque(self, selecteur):
        """La carte, le zoom, le panneau et les EXPORTS du menu Fichier."""
        css = _lire(STYLE_CSS)
        assert "body.carto-consultation %s" % selecteur not in css, (
            "%s doit rester accessible en consultation" % selecteur)

    def test_les_boutons_restent_dans_le_document(self):
        """⚠️ Masqués, jamais retirés : `editor.js` les câble sans garde, et un
        id absent lève une TypeError qui interrompt TOUTE l'init — la page
        afficherait un cadre gris et vide alors que les données sont en base."""
        gabarit = _lire(GABARIT)
        for _, selecteur in CACHES:
            if not selecteur.startswith("#"):
                continue
            ident = selecteur[1:]
            assert 'id="%s"' % ident in gabarit, (
                "%s a été RETIRÉ du gabarit — c'est le piège du contrat DOM, "
                "pas la solution" % ident)

    def test_la_mini_map_reste_dessinee_en_consultation(self):
        """Elle déplace le REGARD, pas la carto. Elle reste absente du viewer,
        qui est une vignette posée dans la page Carte."""
        corps = _corps(_lire(EDITOR_JS), "function renderMinimap() {")
        assert "OPTIQCARTO_CONSULTATION" in corps, (
            "la mini map est refusée à qui vient consulter")

    def test_le_panneau_proprietes_est_verrouille_une_fois_pour_toutes(self):
        """Il est écrit dans le gabarit, pas reconstruit à chaque sélection :
        on le verrouille à l'init. `updateProps()` pose quand même les valeurs,
        donc on lit la fiche entière sans pouvoir y toucher."""
        js = _lire(EDITOR_JS)
        corps = _corps(js, "function _verrouillerProprietes() {")
        assert "input, textarea, select" in corps
        assert "disabled = true" in corps
        assert "if (window.OPTIQCARTO_CONSULTATION) _verrouillerProprietes();" in js


# ══════════════════════════════════════════════════════════════════════
#  5 · Le gabarit, rendu pour de vrai
# ══════════════════════════════════════════════════════════════════════
def _compte(app, statut):
    from Code.extensions import db
    from Code.models.models import User
    from Code.security import hash_password
    mail = "t79.%s@devoptiq.com" % statut
    with app.app_context():
        u = User.query.filter_by(email=mail).first()
        if u is None:
            u = User(first_name="T79", last_name=statut.capitalize(), email=mail,
                     password=hash_password("Motdepasse123!"), status=statut)
            db.session.add(u)
        u.status = statut
        db.session.commit()
        return u.id, mail


def _en_tant_que(client, uid, mail):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["user_email"] = mail
        sess["lang"] = "fr"


@pytest.fixture
def carto_commune(app):
    """Une carto commune ouverte à tous : c'est là que les paliers se lisent."""
    from Code.extensions import db
    from Code.models.models import Entity, User
    from Code.security import hash_password
    with app.app_context():
        proprio = User.query.filter_by(email="t79.proprio@devoptiq.com").first()
        if proprio is None:
            proprio = User(first_name="T79", last_name="Proprio",
                           email="t79.proprio@devoptiq.com",
                           password=hash_password("Motdepasse123!"),
                           status="coordinateur")
            db.session.add(proprio)
            db.session.commit()
        ent = Entity.query.filter_by(name="Carto T79").first()
        if ent is None:
            # ⚠️ Un `owner_id` est obligatoire : une entité sans propriétaire est
            # lisible par TOUT LE MONDE (`entity.owner_id in (None, user.id)`)
            # et devient le repli « aucune entité active » d'autres fichiers.
            ent = Entity(name="Carto T79", owner_id=proprio.id)
            db.session.add(ent)
        ent.is_shared = True
        db.session.commit()
        eid = ent.id
    yield eid
    # ⚠️ La base est partagée : une carto laissée COMMUNE et ouverte à tous
    # devient le repli des fichiers suivants.
    with app.app_context():
        ent = db.session.get(Entity, eid)
        if ent:
            ent.is_shared = False
            db.session.commit()


class TestLeGabaritDitLePalier:

    @pytest.mark.parametrize("statut,consultation", [
        ("user", True),
        ("champion", False),
        ("coordinateur", False),
        ("admin", False),
    ])
    def test_seule_la_consultation_porte_la_classe(self, app, client,
                                                   carto_commune, statut,
                                                   consultation):
        uid, mail = _compte(app, statut)
        _en_tant_que(client, uid, mail)
        with client.session_transaction() as sess:
            sess["active_entity_id"] = carto_commune

        corps = client.get("/cartography/editor").data.decode()
        marque = 'class="carto-consultation"' in corps
        assert marque is consultation, (
            "%s : classe carto-consultation présente = %s" % (statut, marque))
        assert "window.OPTIQCARTO_CONSULTATION" in corps, (
            "le drapeau doit toujours être posé — editor.js le lit")

    def test_les_comptes_du_banc_sont_nettoyes(self, app):
        from Code.extensions import db
        from Code.models.models import Entity, User
        with app.app_context():
            for u in User.query.filter(User.email.like("t79.%")).all():
                db.session.delete(u)
            ent = Entity.query.filter_by(name="Carto T79").first()
            if ent:
                db.session.delete(ent)
            db.session.commit()
            assert User.query.filter(User.email.like("t79.%")).count() == 0
