# -*- coding: utf-8 -*-
"""La page Carte est une SCÈNE : la carto y prend toute la place.

Mesuré avant la refonte, au banc : la carto occupait **34 % de la fenêtre** sur
un 1920×1080, le dessin commençait à 311 px du bord, et la page DÉBORDAIT sur
1280×800. Trois bandeaux empilés — barre de page, rappel de navigation, en-tête
de la carte — répétaient le titre et le nom de l'entité avant qu'on voie quoi
que ce soit.

Ce fichier ne mesure pas des pixels (un test Python ne rend rien) : il tient la
STRUCTURE qui donne ces pixels, et qu'une retouche distraite remettrait en
place sans s'en apercevoir.
"""
import pytest

from Code.extensions import db


@pytest.fixture(autouse=True)
def _session_rendue(client):
    """`client` est partagé : on rend la session telle qu'on l'a trouvée."""
    with client.session_transaction() as s:
        avant = dict(s)
    yield
    with client.session_transaction() as s:
        s.clear()
        s.update(avant)


@pytest.fixture()
def scene(app):
    from Code.models.models import Activities, Entity, User
    from Code.security import hash_password
    with app.app_context():
        u = User(first_name="T94", last_name="Admin", email="t94.admin@devoptiq.com",
                 password=hash_password("Motdepasse123!"), status="admin")
        db.session.add(u)
        db.session.flush()
        avec = Entity(name="T94 Avec carto", owner_id=u.id,
                      optiqcarto_data='{"shapes": [], "bands": [], "connections": []}')
        sans = Entity(name="T94 Sans carto", owner_id=u.id)
        db.session.add_all([avec, sans])
        db.session.flush()
        db.session.add(Activities(name="T94 Chiffrer", entity_id=avec.id, shape_id="t94_1"))
        db.session.commit()
        ids = {"u": u.id, "avec": avec.id, "sans": sans.id}
    yield ids
    with app.app_context():
        from Code.models.models import Activities, Entity, User
        ents = [ids["avec"], ids["sans"]]
        Activities.query.filter(Activities.entity_id.in_(ents)).delete(synchronize_session=False)
        Entity.query.filter(Entity.id.in_(ents)).delete(synchronize_session=False)
        User.query.filter(User.email.like("t94%")).delete(synchronize_session=False)
        db.session.commit()


def _sans_script(html):
    """Le HTML privé de ses blocs `<script>` : ce qui se lit à l'écran."""
    out, reste = [], html
    while True:
        d = reste.find("<script")
        if d < 0:
            out.append(reste)
            break
        out.append(reste[:d])
        f = reste.find("</script>", d)
        if f < 0:
            break
        reste = reste[f + 9:]
    return "".join(out)


def _page(client, app, uid, entity_id, lang="fr"):
    from Code.models.models import User
    with app.app_context():
        mail = db.session.get(User, uid).email
    with client.session_transaction() as s:
        s.clear()
        s["user_id"] = uid
        s["user_email"] = mail
        s["lang"] = lang
        s["active_entity_id"] = entity_id
    return client.get("/activities/map").get_data(as_text=True)


class TestLaCartoPrendToutePlace:

    def test_la_page_est_une_scene(self, app, client, scene):
        html = _page(client, app, scene["u"], scene["avec"])
        assert 'id="carto-scene"' in html
        assert 'class="carto-page carto-scene"' in html
        assert 'js/carto_scene.js' in html

    def test_le_bandeau_de_navigation_a_disparu(self, app, client, scene):
        """⚠️ Il tenait une LIGNE ENTIÈRE au-dessus du dessin pour rappeler
        qu'on déplace à la souris. Le rappel attend derrière le « ? »."""
        html = _page(client, app, scene["u"], scene["avec"])
        assert 'id="carto-info-default"' not in html
        assert 'carto-nav-icon' not in html
        # mais le texte existe toujours — en info-bulle.
        assert 'cs-aide' in html

    def test_le_titre_et_l_entite_ne_s_ecrivent_qu_une_fois(self, app, client, scene):
        """Le nom de l'entité était répété dans le badge de page ET dans
        l'en-tête de la carte, à 60 px d'écart.

        ⚠️ On compte ce qui est AFFICHÉ : le nom vit aussi dans un `<script>`
        (`window.ACTIVE_ENTITY`) et dans l'attribut `title` du titre — qui le
        rend quand il est tronqué. Ni l'un ni l'autre ne se LIT."""
        html = _sans_script(_page(client, app, scene["u"], scene["avec"]))
        assert html.count(">T94 Avec carto<") == 1
        assert html.count("T94 Avec carto") == 2   # le texte, et son title
        assert 'carto-viewer-cardheader' not in html
        assert 'carto-viewer-cardentity' not in html

    def test_les_trois_gestes_de_la_scene_sont_la(self, app, client, scene):
        """Le PLEIN ÉCRAN a été retiré : agrandir la fenêtre ne sert presque
        jamais ici, alors que RECADRER le dessin au milieu de la zone est le
        geste qu'on refait sans arrêt. Le bouton qui portait le cadre porte
        maintenant celui-là."""
        html = _page(client, app, scene["u"], scene["avec"])
        for quoi in ('data-cs="fit"', 'data-cs="actions"', 'data-cs="panneau"'):
            assert quoi in html, quoi
        assert 'data-cs="plein"' not in html
        assert 'id="cs-languette"' in html

    def test_sans_carto_la_scene_n_offre_pas_ses_boutons(self, app, client, scene):
        """Recadrer ou replier la liste n'a aucun sens devant un écran
        d'accueil : les boutons ne sont pas RENDUS, pas seulement masqués."""
        html = _page(client, app, scene["u"], scene["sans"])
        assert 'id="cs-recadrer"' not in html
        assert 'id="cs-panneau"' not in html
        assert 'carto-no-carto-card' in html

    def test_tout_ce_qui_flotte_vit_DANS_le_corps(self, app, client, scene):
        """⚠️ `position: absolute` cherche son repère dans le premier ANCÊTRE
        positionné. Le bandeau des connexions ET la barre des commandes se
        posent sur le dessin : laissés au-dessus du corps, ils se poseraient
        n'importe où — et la barre reprendrait au dessin la hauteur qu'on
        vient de lui rendre."""
        html = _page(client, app, scene["u"], scene["avec"])
        corps = html.index('class="carto-container"')
        bandeau = html.index('id="carto-info-cross"')
        barre = html.index('class="cs-bar"')
        gauche = html.index('class="carto-left"')
        assert corps < bandeau < barre < gauche
        assert 'cs-flot' in html

    def test_le_repli_n_emporte_que_les_reglages(self, app, client, scene):
        """« Les boutons prennent trop de place » : ils se rangent derrière un
        chevron. Mais recadrer est le geste le plus utile de l'écran — il
        reste DEHORS, toujours à un clic."""
        html = _page(client, app, scene["u"], scene["avec"])
        pliable = html.index('id="cs-pliable"')
        prim = html.index('cs-b--prim')
        seg = html.index('class="cs-seg"')
        assert pliable < prim < seg


class TestLesDeuxLangues:

    @pytest.mark.parametrize("lang,attendus", [
        # ⚠️ Jinja échappe l'apostrophe : « Ouvrir l&#39;éditeur » dans le rendu.
        ("fr", ["Replier les réglages", "Replier la liste", "diteur</span>"]),
        ("en", ["Collapse the settings", "Collapse the list", "Open editor"]),
    ])
    def test_les_libelles_de_la_scene_suivent_la_langue(self, app, client, scene,
                                                        lang, attendus):
        html = _page(client, app, scene["u"], scene["avec"], lang)
        for a in attendus:
            assert a in html, "%s manque en %s" % (a, lang)

    def test_la_scene_lit_ses_libelles_dans_le_catalogue_injecte(self, app, client, scene):
        """`carto_scene.js` change le titre des boutons quand on les actionne :
        il lit MAP_I18N, donc les clés doivent y être."""
        html = _page(client, app, scene["u"], scene["avec"])
        for cle in ("sc_actions_plier:", "sc_actions_deplier:",
                    "sc_panneau_fermer:", "sc_panneau_ouvrir:"):
            assert cle in html, cle
