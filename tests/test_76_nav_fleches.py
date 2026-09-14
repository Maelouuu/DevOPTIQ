# tests/test_76_nav_fleches.py
"""
Le défilement de la nav se fait par DEUX FLÈCHES, pas par un rail à tirer.

Un liseré de 3 px qu'on tire est un geste que rien n'annonce. Deux flèches
disent d'elles-mêmes ce qu'elles font.

⚠️ Elles bordent la ZONE DES ITEMS. Le logo (à gauche) et la déconnexion (à
droite) vivent en dehors et ne défilent pas : poser les flèches à leur hauteur
laisserait croire qu'elles les concernent. C'est une contrainte d'ORDRE dans le
gabarit, que rien d'autre ne vérifie — un déplacement de bloc la casserait sans
qu'aucune requête n'échoue.
"""
import io
import os

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GABARIT = os.path.join(RACINE, "Code", "routes", "templates", "header_buttons.html")
CSS = os.path.join(RACINE, "static", "cardnav.css")
JS = os.path.join(RACINE, "static", "js", "cardnav.js")

sans_source = pytest.mark.skipif(
    not all(os.path.exists(p) for p in (GABARIT, CSS, JS)),
    reason="gabarit ou sources absents (arbre bytecode)")


def _lire(chemin):
    return io.open(chemin, encoding="utf-8").read()


@sans_source
class TestPlacement:

    def test_les_fleches_encadrent_les_items_et_rien_d_autre(self):
        html = _lire(GABARIT)
        i_logo = html.index('class="logo-container"')
        i_gauche = html.index('id="card-arrow-prev"')
        i_items = html.index('class="card-scroll"')
        i_droite = html.index('id="card-arrow-next"')
        i_sortie = html.index('class="logout-btn"')

        assert i_logo < i_gauche < i_items < i_droite < i_sortie, (
            "les flèches doivent border la zone des items — le logo et la "
            "déconnexion restent en dehors, ils ne défilent pas")

    def test_elles_vivent_dans_la_zone_qui_defile(self):
        """Hors de `card-nav-content`, elles se retrouveraient à la hauteur du
        logo et de la déconnexion."""
        html = _lire(GABARIT)
        debut = html.index('class="card-nav-content"')
        fin = html.index('class="logout-btn"')
        zone = html[debut:fin]
        assert 'id="card-arrow-prev"' in zone
        assert 'id="card-arrow-next"' in zone

    def test_l_ancien_lisere_a_bien_disparu(self):
        """Deux mécanismes de défilement finiraient par se contredire."""
        for chemin in (GABARIT, CSS, JS):
            assert "card-scrollbar" not in _lire(chemin), os.path.basename(chemin)


@sans_source
class TestVerre:
    """Les flèches doivent appartenir à la barre, pas s'y poser."""

    def test_elles_sont_en_verre_comme_la_nav(self):
        css = _lire(CSS)
        bloc = css[css.index(".card-arrow {"):]
        bloc = bloc[:bloc.index("}")]
        for propriete in ("backdrop-filter", "border", "box-shadow", "background"):
            assert propriete in bloc, propriete
        assert "blur(" in bloc

    def test_elles_s_effacent_quand_tout_tient_a_l_ecran(self):
        """Une flèche qui ne mène nulle part est une promesse non tenue."""
        css = _lire(CSS)
        assert ".card-arrow:not(.is-usable)" in css
        assert ".card-arrow.is-end" in css


@sans_source
class TestComportement:

    def test_le_magnetisme_est_neutralise_pendant_le_geste(self):
        """⚠️ `scroll-snap-type: x mandatory` ramène chaque image du défilement
        sur l'item le plus proche : un `scrollTo` fluide se traîne. L'ancien
        liseré neutralisait déjà le magnétisme pendant qu'on le tirait ; les
        flèches font de même, et le rendent après."""
        js = _lire(JS)
        bloc = js[js.index("function glisser("):]
        bloc = bloc[:bloc.index("precedent.addEventListener")]
        assert "scrollSnapType = 'none'" in bloc
        assert "scrollSnapType = ''" in bloc

    def test_la_molette_rend_la_main_en_butee(self):
        """Sinon on bloquerait le défilement de la PAGE au survol de la nav."""
        js = _lire(JS)
        assert "scroll.scrollLeft <= 0" in js
        assert "scroll.scrollLeft >= max - 1" in js

    def test_on_recalcule_apres_le_chargement_des_icones(self):
        """Les icônes Font Awesome arrivent APRÈS le premier rendu : la largeur
        utile change, et sans ce recalcul les flèches restent masquées sur une
        nav qui déborde pourtant."""
        js = _lire(JS)
        assert "window.addEventListener('load', rafraichir)" in js


@sans_source
class TestLibelles:

    def test_les_deux_langues_nomment_les_fleches(self, app):
        """Une flèche sans libellé n'est rien pour un lecteur d'écran."""
        from Code.translations import TRANSLATIONS

        for langue in ("fr", "en"):
            for cle in ("nav.scroll_left", "nav.scroll_right"):
                assert cle in TRANSLATIONS[langue], f"{langue}:{cle}"
                assert TRANSLATIONS[langue][cle] != cle
