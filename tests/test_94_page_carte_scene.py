# -*- coding: utf-8 -*-
"""La page Carte : une rangée de tuiles, le dessin, la liste.

Mesuré au banc avant la première refonte : la carto occupait **34 % de la
fenêtre** sur un 1920×1080, le dessin commençait à 311 px du bord, et la page
DÉBORDAIT sur 1280×800. Trois bandeaux empilés — barre de page, rappel de
navigation, en-tête de la carte — répétaient le titre et le nom de l'entité
avant qu'on voie quoi que ce soit. Mesuré après : 66,3 % (79,2 % liste
repliée), rien ne déborde de 1280 à 1920.

Ce fichier ne mesure pas des pixels (un test Python ne rend rien) : il tient la
STRUCTURE qui donne ces pixels, et qu'une retouche distraite remettrait en
place sans s'en apercevoir.
"""
import pytest

from Code.extensions import db

# Une carto minimale, mais VRAIE : deux bandes colorées, deux formes — dont une
# dont la couleur n'est pas un hexadécimal et ne doit jamais atteindre le
# gabarit (elle partirait dans un attribut `style`).
CARTO = (
    '{"bands": ['
    '{"id": "b1", "label": "Qualit\\u00e9", "color": "#ff0000", "height": 180},'
    '{"id": "b2", "label": "Logistique", "color": "#0088cc", "height": 180}],'
    ' "shapes": ['
    '{"id": "t94_1", "label": "T94 Chiffrer", "color": "#ff0000", "y": -190, "h": 70},'
    '{"id": "t94_2", "label": "T94 Injecter", "color": "red;background:url(x)", "y": -10, "h": 70}],'
    ' "connections": []}'
)


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
        avec = Entity(name="T94 Avec carto", owner_id=u.id, optiqcarto_data=CARTO)
        sans = Entity(name="T94 Sans carto", owner_id=u.id)
        db.session.add_all([avec, sans])
        db.session.flush()
        db.session.add_all([
            Activities(name="T94 Chiffrer", entity_id=avec.id, shape_id="t94_1"),
            Activities(name="T94 Injecter", entity_id=avec.id, shape_id="t94_2"),
        ])
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
        assert 'cs-f--aide' in html

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
        geste qu'on refait sans arrêt."""
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

    def test_la_rangee_du_haut_est_dans_le_FLUX(self, app, client, scene):
        """⚠️ Renversement de la passe précédente, et il est voulu : la barre
        FLOTTAIT sur le dessin, elle redevient une rangée au-dessus de lui.
        C'est ce que montre le board, et c'est ce qui rend le tiroir capable
        de POUSSER le dessin au lieu de le recouvrir."""
        html = _page(client, app, scene["u"], scene["avec"])
        barre = html.index('class="cs-bar"')
        corps = html.index('class="carto-container"')
        gauche = html.index('class="carto-left"')
        assert barre < corps < gauche

    def test_ce_qui_se_pose_sur_le_dessin_vit_DANS_le_dessin(self, app, client, scene):
        """⚠️ `position: absolute` cherche son repère dans le premier ANCÊTRE
        positionné. Les trois gestes de l'écran se posent au coin du DESSIN :
        sortis de `.carto-left`, ils se poseraient n'importe où — et le
        bandeau des connexions, lui, se cale sur le corps entier."""
        html = _page(client, app, scene["u"], scene["avec"])
        corps = html.index('class="carto-container"')
        bandeau = html.index('id="carto-info-cross"')
        gauche = html.index('class="carto-left"')
        flottants = html.index('class="cs-flottants"')
        tiroir = html.index('id="carto-right"')
        assert corps < bandeau < gauche < flottants < tiroir
        assert 'cs-flot' in html

    def test_le_repli_n_emporte_que_les_reglages(self, app, client, scene):
        """« Les boutons prennent trop de place » : les quatre tuiles de
        réglage se rangent derrière un chevron. Mais ouvrir l'éditeur et
        recadrer restent DEHORS, toujours à un clic — l'un après la poignée
        de repli, l'autre carrément au coin du dessin."""
        html = _page(client, app, scene["u"], scene["avec"])
        pliable = html.index('id="cs-pliable"')
        poignee = html.index('id="cs-plier"')
        editeur = html.index('cs-t--prim')
        flottants = html.index('class="cs-flottants"')
        assert pliable < poignee < editeur < flottants

    def test_le_bouton_fleche_du_board_n_existe_pas(self, app, client, scene):
        """Le board portait un carré blanc à flèche posé sur « Ouvrir
        l'éditeur ». Il ne correspond à AUCUNE fonction de la page : la tuile
        entière est le lien."""
        html = _page(client, app, scene["u"], scene["avec"])
        d = html.index('cs-t--prim')
        tuile = html[d:html.index("</a>", d)]
        assert 'fa-arrow' not in tuile
        assert tuile.count("<i ") == 2   # l'icône de la pastille, et le filigrane


class TestLaCouleurVientDuDessin:

    def test_la_pastille_d_une_activite_porte_la_couleur_de_sa_forme(self, app, client, scene):
        """La couleur d'une forme vient de sa bande (`editor.js` :
        `s.color = band.color`). La pastille numérotée porte donc exactement
        la couleur du rectangle qu'elle désigne — on retrouve une activité
        dans le dessin sans lire son nom."""
        html = _page(client, app, scene["u"], scene["avec"])
        assert 'style="--c: #ff0000"' in html
        assert '<span class="num">01</span>' in html

    def test_une_couleur_qui_n_est_pas_un_hexa_est_ecartee(self, app, client, scene):
        """⚠️ Elle vient d'un fichier Visio et part dans un attribut `style` :
        Jinja protège de la sortie d'attribut, PAS de l'injection d'une
        propriété CSS. Sans forme reconnue, la pastille est NEUTRE — on
        n'invente pas une couleur."""
        html = _page(client, app, scene["u"], scene["avec"])
        assert 'background:url(x)' not in html
        assert 'red;' not in html
        # L'activité est là quand même, avec sa pastille neutre.
        assert '<span class="num">02</span>' in html

    def test_la_bande_des_couleurs_est_la_cle_des_pastilles(self, app, client, scene):
        """Rien ne disait d'où venait la couleur d'une pastille. Les bandes de
        la carto, dans leur ordre, le disent — leur nom au survol."""
        html = _page(client, app, scene["u"], scene["avec"])
        assert html.count('class="cs-bande"') == 2
        assert 'title="Qualité"' in html
        assert 'title="Logistique"' in html

    def test_le_compte_du_tiroir_est_en_deux_morceaux(self, app, client, scene):
        """⚠️ Le nombre est le TITRE du panneau (38 px) et son mot le suit.
        Un seul élément ne pourrait pas porter les deux tailles : il est écrit
        par `textContent`, qui effacerait un `<strong>` niché dedans."""
        html = _page(client, app, scene["u"], scene["avec"])
        assert '<span class="cs-tiroir-n" id="cs-tiroir-n">2</span>' in html
        assert 'class="activities-panel-count">activités<' in html
        assert 'majCompteListe' in _lire("static/js/activities_map.js")


def _lire(chemin):
    import io
    import os
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return io.open(os.path.join(racine, chemin), encoding="utf-8").read()


class TestLesDeuxLangues:

    @pytest.mark.parametrize("lang,attendus", [
        # ⚠️ Jinja échappe l'apostrophe : « Ouvrir l&#39;éditeur » dans le rendu.
        ("fr", ["Replier les réglages", "Replier la liste", "diteur</span>", ">Bandes<"]),
        ("en", ["Collapse the settings", "Collapse the list", "Open editor", ">Bands<"]),
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
