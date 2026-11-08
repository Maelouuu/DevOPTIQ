# -*- coding: utf-8 -*-
"""La fenêtre de bienvenue — ce qu'elle montre, à qui, et quand elle revient.

⚠️ Ce fichier existe à cause d'un défaut que la documentation donnait pour
corrigé. Mesuré au banc (`tools/devrun_bienvenue.py` + Playwright), la garde par
signature en `localStorage` tenait le cas simple mais lâchait par trois chemins,
tous reproduits ici :

  1. la signature était bâtie sur de la PROSE TRADUITE, donc elle changeait
     avec la langue — et `DEFAULT_LANG` vaut 'en' ;
  2. un `localStorage` qui refuse d'écrire faisait revenir la fenêtre dans
     CHAQUE nouvel onglet, indéfiniment ;
  3. la décision dépendait d'un `fetch`, et le voile était `display:flex` au
     repos : un changelog en erreur rendait l'application entière cliquable
     nulle part, sans que rien ne se voie.

La correction déplace la décision côté SERVEUR. Chaque test ci-dessous se
vérifie ROUGE en retirant la garde qu'il surveille — c'est écrit au-dessus de
chacun.
"""
import io
import json
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GABARIT = os.path.join(RACINE, "Code", "routes", "templates", "welcome_popup.html")
FEUILLE = os.path.join(RACINE, "static", "welcome_popup.css")
NAV = os.path.join(RACINE, "Code", "routes", "templates", "header_buttons.html")


def _lire(chemin):
    return io.open(chemin, encoding="utf-8").read()


# ══════════════════════════════════════════════════════════════════════════
#  Outillage : quatre comptes, un par palier
# ══════════════════════════════════════════════════════════════════════════

PALIERS = {"user": "user", "champion": "champion",
           "coordinateur": "coordinateur", "admin": "administrateur"}


@pytest.fixture(scope="module")
def comptes(app):
    """Un compte par palier, créés une fois pour ce fichier."""
    from werkzeug.security import generate_password_hash

    from Code.extensions import db
    from Code.models.models import User

    crees = {}
    with app.app_context():
        for palier, statut in PALIERS.items():
            email = f"bienvenue-{palier}@devoptiq.com"
            u = User.query.filter_by(email=email).first()
            if u is None:
                u = User(first_name=palier.capitalize(), last_name="Bienvenue",
                         email=email, password=generate_password_hash("Test1234!"),
                         status=statut, lang="fr")
                db.session.add(u)
                db.session.commit()
            crees[palier] = u.id
    return crees


def _connecter(app, client, user_id, lang="fr"):
    """Pose une session valide pour ce compte, dans cette langue."""
    from Code import mot_de_passe as _mdp
    from Code.extensions import db
    from Code.models.models import User

    with app.app_context():
        u = db.session.get(User, user_id)
        db.session.expire(u)
        empreinte = _mdp.empreinte_session(u)
        email = u.email
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user_id
        sess["user_email"] = email
        sess["pwd_at"] = empreinte
        sess["lang"] = lang
    return client


def _oublier(app, user_id):
    """Efface la mémoire « déjà vue » de ce compte."""
    from Code.extensions import db
    from Code.models.models import WelcomeSeen

    with app.app_context():
        ligne = db.session.get(WelcomeSeen, user_id)
        if ligne is not None:
            db.session.delete(ligne)
            db.session.commit()


def _page(client, chemin="/activities/view"):
    rep = client.get(chemin, follow_redirects=True)
    return rep.get_data(as_text=True)


def _fenetre_affichee(html):
    """La fenêtre s'ouvre-t-elle à l'arrivée ?

    On lit l'attribut que le SERVEUR pose, pas une classe : c'est lui qui
    décide désormais, et c'est précisément ce qu'on veut garder.
    """
    i = html.find('id="welcome-popup-overlay"')
    if i < 0:
        return False
    # La balise peut tenir sur plusieurs lignes : on s'arrête au '>' fermant.
    balise = html[i:html.find(">", i)]
    return "display:flex" in balise.replace(" ", "")


# ══════════════════════════════════════════════════════════════════════════
#  1. Le défaut signalé : un nouvel onglet ne doit PAS la réafficher
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Le client de test n'a NI `localStorage` NI `sessionStorage` : chacune de
# ses requêtes est donc, par construction, « un onglet tout neuf ». C'est ce
# qui rend ce test capable de voir le défaut — l'ancien montage, qui lisait le
# stockage du navigateur, rouvrait la fenêtre à chaque appel.

def test_la_fenetre_s_ouvre_a_la_premiere_arrivee(app, client, comptes):
    _oublier(app, comptes["admin"])
    _connecter(app, client, comptes["admin"])
    assert _fenetre_affichee(_page(client)), (
        "la fenêtre doit s'ouvrir quand le compte n'a jamais lu ces nouveautés")


def test_un_nouvel_onglet_ne_la_reaffiche_pas(app, client, comptes):
    """RATCHET : remettre la décision dans le navigateur (ou retirer la
    mémoire par compte de `Code/bienvenue.py`) fait virer ce test au ROUGE —
    chaque requête repart alors d'un stockage vide et rouvre la fenêtre."""
    _oublier(app, comptes["admin"])
    _connecter(app, client, comptes["admin"])
    assert _fenetre_affichee(_page(client))

    assert client.post("/api/bienvenue/vue").status_code == 200

    # Un nouvel onglet : même compte, même session serveur, AUCUN stockage.
    assert not _fenetre_affichee(_page(client)), (
        "la fenêtre est revenue dans un onglet neuf alors qu'elle a été lue")
    # Et sur une autre page de l'application non plus.
    assert not _fenetre_affichee(_page(client, "/activities/map"))


def test_elle_revient_quand_les_nouveautes_changent(app, client, comptes):
    """Lue, puis le changelog change : elle doit revenir UNE fois."""
    from Code.extensions import db
    from Code.models.models import WelcomeSeen

    _oublier(app, comptes["admin"])
    _connecter(app, client, comptes["admin"])
    client.post("/api/bienvenue/vue")
    assert not _fenetre_affichee(_page(client))

    with app.app_context():
        ligne = db.session.get(WelcomeSeen, comptes["admin"])
        ligne.signature = "b1:autre-chose"
        db.session.commit()

    assert _fenetre_affichee(_page(client)), (
        "de nouvelles nouveautés doivent rouvrir la fenêtre")


# ══════════════════════════════════════════════════════════════════════════
#  2. La cause mesurée : la signature ne doit pas dépendre de la langue
# ══════════════════════════════════════════════════════════════════════════

def test_la_signature_est_la_meme_dans_les_deux_langues(app):
    """RATCHET : rebâtir la signature sur `title`/`desc` APRÈS résolution de
    la langue (ce que faisait l'ancien JavaScript) fait virer ce test au
    ROUGE. C'est le chemin par lequel la fenêtre revenait réellement."""
    from Code.bienvenue import signature_nouveautes

    with app.test_request_context("/"):
        from flask import session
        session["lang"] = "fr"
        en_francais = signature_nouveautes()
    with app.test_request_context("/"):
        from flask import session
        session["lang"] = "en"
        en_anglais = signature_nouveautes()

    assert en_francais == en_anglais != "", (
        "la signature change avec la langue : les mêmes nouveautés seraient "
        "annoncées deux fois à qui bascule de langue")


def test_reformuler_une_nouveaute_ne_la_fait_pas_reannoncer(app, tmp_path,
                                                            monkeypatch):
    """C'est l'`id` qui identifie une nouveauté, pas son texte.

    Corriger une faute — en français comme en anglais — ne doit pas rouvrir la
    fenêtre chez tout le monde pour une nouveauté déjà lue.

    RATCHET : retirer la lecture de l'`id` (`cle = str(item.get('id')…)`), donc
    retomber sur une empreinte du TEXTE, fait virer ce test au ROUGE.
    """
    from Code import bienvenue

    items = [{"id": "un", "title": "Un", "desc": "A", "title_en": "One"},
             {"id": "deux", "title": "Deux", "desc": "B", "title_en": "Two"}]
    f = tmp_path / "changelog_user.json"
    f.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bienvenue, "_fichier_cure", lambda: str(f))
    avant = bienvenue.signature_nouveautes()

    items[0]["title"] = "Un (reformulé)"
    items[0]["title_en"] = "One (corrected)"
    items[1]["desc"] = "B, dit autrement"
    f.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

    assert bienvenue.signature_nouveautes() == avant, (
        "une simple reformulation a changé la signature : la fenêtre "
        "reviendrait chez tout le monde pour une nouveauté déjà lue")


def test_une_nouveaute_ajoutee_change_la_signature(app, tmp_path, monkeypatch):
    """Le pendant du test précédent : la signature doit quand même BOUGER
    quand le contenu change pour de bon, sinon elle ne garde plus rien."""
    from Code import bienvenue

    items = [{"id": "un", "title": "Un", "desc": "A"}]
    f = tmp_path / "changelog_user.json"
    f.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bienvenue, "_fichier_cure", lambda: str(f))
    avant = bienvenue.signature_nouveautes()

    items.append({"id": "deux", "title": "Deux", "desc": "B"})
    f.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

    assert bienvenue.signature_nouveautes() != avant


def test_chaque_nouveaute_porte_un_identifiant_stable():
    """`changelog_user.json` doit porter un `id` par entrée : sans lui on
    retombe sur une empreinte du texte français, qu'une simple reformulation
    ferait changer."""
    items = json.loads(_lire(os.path.join(RACINE, "static", "changelog_user.json")))
    assert items, "le fichier curé est vide"
    ids = [it.get("id") for it in items]
    assert all(ids), "une nouveauté sans `id` : %r" % (ids,)
    assert len(set(ids)) == len(ids), "deux nouveautés partagent un `id`"


# ══════════════════════════════════════════════════════════════════════════
#  3. Le voile ne doit JAMAIS rester tendu sur l'application
# ══════════════════════════════════════════════════════════════════════════

def test_le_voile_est_display_none_au_repos_dans_la_feuille():
    """RATCHET : remettre `display: flex` dans la règle de base de
    `#welcome-popup-overlay` (ce qu'elle portait) fait virer ce test au ROUGE.

    ⚠️ Ce n'est pas cosmétique : le voile est `position: fixed; inset: 0;
    z-index: 9999`. Tendu et transparent, il avale TOUS les clics de la page.
    """
    css = _lire(FEUILLE)
    i = css.find("#welcome-popup-overlay {")
    assert i >= 0, "la règle de base du voile a disparu"
    regle = css[i:css.find("}", i)]
    assert "display: none" in regle, (
        "la règle de base du voile ne pose pas `display: none` : "
        "il reste tendu sur la page tant que rien ne le referme")
    assert "display: flex" not in regle, (
        "`display: flex` est revenu dans la règle de base du voile")


def test_le_voile_ne_depend_plus_du_reseau(app, client, comptes):
    """RATCHET : remettre un `fetch` dont dépend l'affichage fait virer ce
    test au ROUGE. Le gabarit ne doit appeler le réseau QUE pour annoncer la
    lecture — jamais pour décider."""
    # ⚠️ Les commentaires d'abord : celui en tête du gabarit CITE l'ancien
    # appel pour expliquer pourquoi il est parti. Le lire comme du code
    # ferait échouer ce test sur sa propre explication.
    src = re.sub(r"<!--.*?-->", "", _lire(GABARIT), flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    assert "/api/changelog" not in src, (
        "le gabarit réinterroge le changelog : la décision redevient une course")
    appels = [ligne for ligne in src.splitlines() if "fetch(" in ligne]
    assert len(appels) == 1 and "/api/bienvenue/vue" in appels[0], (
        "un seul appel réseau est attendu, et seulement pour annoncer la "
        "lecture — trouvé : %r" % (appels,))


def test_la_chaine_des_popups_reste_intacte():
    """Les deux pop-ups qui suivent attendent `display === 'none'` sur CET
    élément, en surveillant ses attributs `style` et `class`.

    RATCHET : fermer la fenêtre en retirant seulement une classe, sans
    repasser `style.display` à `none`, fait virer ce test au ROUGE — et, dans
    l'application, les deux fenêtres suivantes n'apparaîtraient jamais.
    """
    src = _lire(GABARIT)
    assert 'id="welcome-popup-overlay"' in src
    assert "voile.style.display = 'none'" in src, (
        "la fermeture ne repose plus `display:none` sur le voile : "
        "entity_share_popup et carto_decision_popup attendraient leur tour "
        "indéfiniment")

    # Et les deux guetteurs n'ont pas changé de contrat de leur côté.
    for nom in ("entity_share_popup.html", "carto_decision_popup.html"):
        suite = _lire(os.path.join(RACINE, "Code", "routes", "templates", nom))
        assert "welcome-popup-overlay" in suite
        assert "display" in suite


# ══════════════════════════════════════════════════════════════════════════
#  4. Le palier : jamais une porte qu'on ne peut pas franchir
# ══════════════════════════════════════════════════════════════════════════

def _portes(app, user_id, lang="fr"):
    from Code.bienvenue import portes_ouvertes
    from Code.extensions import db
    from Code.models.models import User

    with app.app_context():
        u = db.session.get(User, user_id)
        return [p["libelle"] for p in portes_ouvertes(u, lang)]


def test_un_user_ne_voit_aucune_porte_d_ecriture(app, comptes):
    """RATCHET : afficher les portes sans les filtrer par `a_le_droit` fait
    virer ce test au ROUGE."""
    libelles = " ".join(_portes(app, comptes["user"]))
    assert "Consulter la cartographie" in libelles
    for interdit in ("Gestion RH", "Créer", "Modifier un compte",
                     "Paramètres d'administration", "Arbitrer",
                     "Enregistrer sur une carto"):
        assert interdit not in libelles, (
            "un `user` se voit annoncer « %s », qu'il ne peut pas faire"
            % interdit)


def test_l_echelle_des_paliers_est_croissante(app, comptes):
    """Plus on monte, plus la fenêtre ouvre de portes — et jamais moins."""
    n = {p: len(_portes(app, comptes[p])) for p in PALIERS}
    assert n["user"] < n["champion"] < n["coordinateur"] <= n["admin"], (
        "l'échelle ne se lit plus dans la fenêtre : %r" % (n,))


def test_un_admin_voit_les_portes_d_administration(app, comptes):
    libelles = " ".join(_portes(app, comptes["admin"]))
    assert "Paramètres d'administration" in libelles
    assert "Gestion RH" in libelles


def test_les_portes_suivent_le_TABLEAU_des_droits_pas_le_statut(app, comptes):
    """⚠️ LE test du palier. Les droits des trois premiers paliers se règlent
    depuis la page Comptes : la fenêtre doit lire ce tableau, jamais une liste
    de statuts écrite en dur.

    RATCHET : remplacer `a_le_droit('acces_rh')` par un test du genre
    `statut in ('coordinateur', 'admin')` fait virer ce test au ROUGE — le
    champion continuerait de ne pas voir la porte alors qu'on vient de la lui
    ouvrir.
    """
    from Code.permissions import droits_effectifs, enregistrer_droits

    avant = " ".join(_portes(app, comptes["champion"]))
    assert "Gestion RH" not in avant, "le champion n'ouvre pas la RH par défaut"

    with app.app_context():
        table = droits_effectifs()
        table["acces_rh"]["champion"] = True
        enregistrer_droits(table)
    try:
        apres = " ".join(_portes(app, comptes["champion"]))
        assert "Gestion RH" in apres, (
            "le droit a été accordé au palier champion, et la fenêtre "
            "continue de lui cacher la porte : elle ne lit pas le tableau")
    finally:
        with app.app_context():
            table = droits_effectifs()
            table["acces_rh"]["champion"] = False
            enregistrer_droits(table)

    assert "Gestion RH" not in " ".join(_portes(app, comptes["champion"]))


def test_une_porte_fermee_disparait_de_la_PAGE_rendue(app, client, comptes):
    """Le filtrage doit tenir jusque dans le HTML, pas seulement en Python."""
    _oublier(app, comptes["user"])
    _connecter(app, client, comptes["user"])
    html = _page(client)
    assert "wp-porte" in html, "les portes ne sont pas rendues"
    assert "Paramètres d'administration" not in html
    assert "Ouvrir la Gestion RH" not in html


# ══════════════════════════════════════════════════════════════════════════
#  5. La réouverture
# ══════════════════════════════════════════════════════════════════════════

def test_le_bouton_de_reouverture_existe_et_n_est_pas_une_page():
    """⚠️ Dans cette barre, un `nav-card` est une PAGE. La fenêtre n'en est
    pas une : son bouton ne doit pas en porter la classe, sous peine de la
    faire passer pour un écran de plus.

    RATCHET : donner la classe `nav-card` au bouton fait virer ce test au ROUGE.
    """
    nav = _lire(NAV)
    i = nav.find('id="nav-bienvenue"')
    assert i >= 0, "le bouton de réouverture a disparu de la barre"
    debut = nav.rfind("<button", 0, i)
    balise = nav[debut:nav.find(">", i)]
    assert "nav-bienvenue" in balise
    assert "nav-card" not in balise, (
        "le bouton porte la classe des PAGES : la fenêtre se lirait comme un "
        "écran de plus dans la navigation")
    # Il doit rester HORS de la zone qui défile (celle des pages).
    fin_scroll = nav.find("</div>", nav.find('class="card-scroll"'))
    assert i > fin_scroll, "le bouton a été posé parmi les cartes de page"


def test_la_reouverture_ne_re_rend_rien(app, client, comptes):
    """La fenêtre est rendue même quand elle ne s'ouvre pas : c'est ce qui
    permet de la rouvrir sans seconde voie de rendu en JavaScript — donc sans
    second jeu de libellés à tenir.

    RATCHET : ne rendre le gabarit que lorsque `montrer` est vrai fait virer
    ce test au ROUGE (le bouton n'aurait plus rien à rouvrir).
    """
    _oublier(app, comptes["admin"])
    _connecter(app, client, comptes["admin"])
    client.post("/api/bienvenue/vue")
    html = _page(client)

    assert not _fenetre_affichee(html), "elle ne doit pas s'ouvrir d'elle-même"
    assert 'id="welcome-popup-overlay"' in html, (
        "la fenêtre n'est plus dans la page : le bouton ne peut plus la rouvrir")
    assert "wp-porte" in html and "wp-new" in html, "son contenu manque"
    assert 'id="nav-bienvenue"' in html
    assert "window.optiqRouvrirBienvenue" in html, (
        "le point d'entrée de la réouverture a disparu")


# ══════════════════════════════════════════════════════════════════════════
#  6. L'API de lecture
# ══════════════════════════════════════════════════════════════════════════

def test_api_vue_refuse_un_anonyme(client):
    with client.session_transaction() as sess:
        sess.clear()
    assert client.post("/api/bienvenue/vue").status_code == 401


def test_api_vue_ecrit_la_signature_DU_SERVEUR(app, client, comptes):
    """RATCHET : reprendre la signature envoyée par le navigateur fait virer
    ce test au ROUGE. Sinon un appel suffirait à faire taire la fenêtre pour
    des nouveautés jamais lues."""
    from Code.bienvenue import signature_nouveautes
    from Code.extensions import db
    from Code.models.models import WelcomeSeen

    _oublier(app, comptes["coordinateur"])
    _connecter(app, client, comptes["coordinateur"])
    rep = client.post("/api/bienvenue/vue", json={"signature": "je-mens"})
    assert rep.status_code == 200

    with app.app_context():
        attendue = signature_nouveautes()
        ligne = db.session.get(WelcomeSeen, comptes["coordinateur"])
        assert ligne is not None, "rien n'a été mémorisé"
        assert ligne.signature == attendue
        assert ligne.signature != "je-mens"


# ══════════════════════════════════════════════════════════════════════════
#  7. Les deux langues — le détecteur de fuites
# ══════════════════════════════════════════════════════════════════════════

def _fenetre_rendue(html):
    """Le MARKUP de la fenêtre, script exclu.

    ⚠️ On s'arrête à la balise `<script>`, pas à `</script>` : le nom de la
    fonction de réouverture (`optiqRouvrirBienvenue`) contient « Bienvenue »
    et faisait crier le détecteur sur du code, pas sur une phrase lue. Laisser
    le script dehors ne crée pas d'angle mort : la fenêtre ne fabrique AUCUN
    texte en JavaScript, et `test_le_script_ne_fabrique_aucun_texte` le garde.
    """
    i = html.find('id="welcome-popup-overlay"')
    assert i >= 0, "la fenêtre n'est pas dans la page"
    fin = html.find("<script", i)
    return html[i:fin if fin > i else len(html)]


def test_le_script_ne_fabrique_aucun_texte():
    """RATCHET : revenir à un contenu construit en JavaScript (ce que faisait
    l'ancienne fenêtre, avec ses phrases françaises en dur dans des
    `innerHTML`) fait virer ce test au ROUGE."""
    src = re.sub(r"<!--.*?-->", "", _lire(GABARIT), flags=re.S)
    debut = src.find("<script")
    script = src[debut:] if debut >= 0 else ""
    assert "innerHTML" not in script, (
        "la fenêtre refabrique du contenu en JavaScript : les libellés "
        "échapperaient au catalogue")


#: Longueur minimale d'un fragment cherché dans le HTML.
#: ⚠️ Un fragment court est un FAUX POSITIF garanti : « et %s de plus » laissait
#: le morceau « et », qu'on retrouve dans n'importe quel texte anglais. Six
#: signes est le seuil où un fragment cesse d'apparaître par hasard.
FRAGMENT_MIN = 6


def _fragments(valeur):
    """Les morceaux FIXES d'un libellé à trou, du plus long au plus court.

    ⚠️ On lit TOUS les morceaux, pas seulement celui d'avant le `%s` : un
    libellé dont le nombre vient en premier (« %s autres en attente ») n'avait
    aucun préfixe, et sortait donc entièrement du contrôle.
    """
    return sorted((m.strip() for m in valeur.split("%s")),
                  key=len, reverse=True)


def _valeurs_welcome():
    """Les couples (fr, en) des clés `welcome.*` qui DIFFÈRENT d'une langue à
    l'autre — les seules sur lesquelles une fuite se voie.

    Pour un libellé à trou, on retient son fragment fixe le plus long, à
    condition qu'il atteigne `FRAGMENT_MIN`. Une clé dont aucun fragment n'est
    assez long sort du contrôle : `test_les_libelles_neufs_existent_dans_LES_DEUX_langues`
    garde alors qu'elle est bien traduite.
    """
    from Code.translations import TRANSLATIONS

    couples = []
    for cle, fr in TRANSLATIONS["fr"].items():
        if not cle.startswith("welcome."):
            continue
        en = TRANSLATIONS["en"].get(cle)
        if not isinstance(fr, str) or not isinstance(en, str):
            continue
        frs = [m for m in _fragments(fr) if len(m) >= FRAGMENT_MIN]
        ens = [m for m in _fragments(en) if len(m) >= FRAGMENT_MIN]
        if frs and ens and frs[0] != ens[0]:
            couples.append((cle, frs[0], ens[0]))
    return couples


def test_chaque_palier_a_sa_phrase_dans_les_deux_langues():
    """⚠️ La phrase de palier se résout en PYTHON, avec quatre clés écrites en
    toutes lettres. Une clé assemblée dans le gabarit
    (`t('welcome.tier.' ~ palier)`) échappait au contrôle de couverture, qui
    l'a d'ailleurs attrapée : un cinquième palier aurait affiché
    « welcome.tier.machin » en clair.

    RATCHET : retirer une entrée de `PHRASE_PALIER`, ou sa traduction, fait
    virer ce test au ROUGE.
    """
    from Code.bienvenue import PHRASE_PALIER
    from Code.permissions import PALIERS as PALIERS_PERMISSIONS
    from Code.translations import TRANSLATIONS

    assert set(PHRASE_PALIER) == set(PALIERS_PERMISSIONS), (
        "les paliers de `permissions.py` et les phrases de la fenêtre ont "
        "divergé : %r vs %r" % (sorted(PHRASE_PALIER), sorted(PALIERS_PERMISSIONS)))
    for palier, cle in PHRASE_PALIER.items():
        for lang in ("fr", "en"):
            assert TRANSLATIONS[lang].get(cle), (
                "le palier %s n'a pas de phrase en %s (clé %s)"
                % (palier, lang, cle))


def test_le_gabarit_n_assemble_aucune_cle_de_traduction():
    """RATCHET : revenir à `t('welcome.tier.' ~ …)` fait virer ce test au
    ROUGE — et le contrôle de couverture avec lui."""
    src = re.sub(r"<!--.*?-->", "", _lire(GABARIT), flags=re.S)
    assembles = re.findall(r"t\(\s*'[^']*'\s*~", src) + \
                re.findall(r"t\(\s*\"[^\"]*\"\s*~", src)
    assert not assembles, (
        "une clé de traduction est assemblée dans le gabarit : %r — elle "
        "échappe au contrôle de couverture" % (assembles,))


def test_toutes_les_cles_welcome_existent_en_anglais():
    from Code.translations import TRANSLATIONS

    manquantes = [c for c in TRANSLATIONS["fr"]
                  if c.startswith("welcome.") and c not in TRANSLATIONS["en"]]
    assert not manquantes, "clés sans traduction anglaise : %r" % (manquantes,)


def test_le_detecteur_lit_AUSSI_les_suffixes():
    """⚠️ Il ne comparait que le morceau d'AVANT le `%s`. Un libellé dont le
    nombre vient en premier — « %s modification(s) de fiche » — n'avait donc
    aucun préfixe, et sortait entièrement du contrôle de fuite.

    RATCHET : revenir à `fr.split("%s")[0]` fait virer ce test au ROUGE.
    """
    couverts = {cle for cle, _fr, _en in _valeurs_welcome()}
    assert "welcome.props_fiche" in couverts, (
        "un libellé dont le nombre vient en premier échappe au contrôle")
    # Et le seuil écarte bien les fragments trop courts pour signifier quoi
    # que ce soit : « et » se retrouve dans n'importe quel texte anglais.
    for _cle, fr, en in _valeurs_welcome():
        assert len(fr) >= FRAGMENT_MIN and len(en) >= FRAGMENT_MIN, (fr, en)


@pytest.mark.parametrize("palier", list(PALIERS))
def test_la_page_anglaise_ne_laisse_filtrer_aucune_phrase_francaise(
        app, client, comptes, palier):
    """⚠️ On relit le HTML BRUT, attributs compris (`title`, `aria-label`) :
    une fuite se cache aussi bien dans une info-bulle que dans le texte.

    RATCHET : réécrire une phrase en dur dans le gabarit (comme l'ancien
    « Aucune nouveauté à afficher. ») fait virer ce test au ROUGE.
    """
    _oublier(app, comptes[palier])
    _connecter(app, client, comptes[palier], lang="en")
    # On ne lit que la fenêtre : le reste de la page a ses propres contrôles.
    fenetre = _fenetre_rendue(_page(client))

    fuites = [(cle, fr) for cle, fr, _en in _valeurs_welcome() if fr in fenetre]
    assert not fuites, "phrases françaises dans la fenêtre anglaise : %r" % (fuites,)


@pytest.mark.parametrize("palier", list(PALIERS))
def test_la_page_francaise_ne_laisse_filtrer_aucune_phrase_anglaise(
        app, client, comptes, palier):
    _oublier(app, comptes[palier])
    _connecter(app, client, comptes[palier], lang="fr")
    fenetre = _fenetre_rendue(_page(client))

    fuites = [(cle, en) for cle, _fr, en in _valeurs_welcome() if en in fenetre]
    assert not fuites, "phrases anglaises dans la fenêtre française : %r" % (fuites,)


@pytest.mark.parametrize("lang,autre", [("en", "fr"), ("fr", "en")])
def test_le_bouton_de_la_nav_est_traduit_jusque_dans_ses_attributs(
        app, client, comptes, lang, autre):
    """⚠️ Le bouton de réouverture n'a PAS de libellé visible : tout ce qu'il
    dit vit dans `title` et `aria-label`. C'est exactement l'endroit qu'un
    contrôle de traduction oublie — et le seul que lise une personne au
    lecteur d'écran.

    RATCHET : écrire le libellé en dur dans `header_buttons.html` fait virer ce
    test au ROUGE.
    """
    from Code.translations import t

    _connecter(app, client, comptes["admin"], lang=lang)
    html = _page(client)
    i = html.find('id="nav-bienvenue"')
    assert i >= 0, "le bouton de réouverture a disparu de la page"
    balise = html[html.rfind("<button", 0, i):html.find(">", i)]

    attendu = t("welcome.reopen", lang)
    indesirable = t("welcome.reopen", autre)
    assert f'title="{attendu}"' in balise, (
        "le `title` n'est pas dans la langue du compte : %r" % (balise,))
    assert f'aria-label="{attendu}"' in balise, (
        "l'`aria-label` n'est pas dans la langue du compte : %r" % (balise,))
    assert indesirable not in balise, (
        "la phrase de l'autre langue fuit dans les attributs du bouton")


def test_la_fenetre_se_rend_bien_dans_les_deux_langues(app, client, comptes):
    """Le contrôle d'en face : les fuites se taisent aussi quand RIEN ne
    s'affiche. On vérifie donc que la fenêtre porte bien, dans chaque langue,
    la phrase de palier attendue."""
    from Code.translations import t

    for lang in ("fr", "en"):
        _oublier(app, comptes["admin"])
        _connecter(app, client, comptes["admin"], lang=lang)
        html = _page(client)
        attendu = t("welcome.tier.admin", lang)
        assert attendu in html, (
            "la phrase de palier manque en %s : %r" % (lang, attendu))
        assert t("welcome.doors", lang) in html


# ══════════════════════════════════════════════════════════════════════════
#  Elle se déploie en LARGEUR, pas en hauteur
# ══════════════════════════════════════════════════════════════════════════

def _regle(css, selecteur):
    """Le corps d'une règle CSS, du sélecteur à son accolade fermante."""
    i = css.find(selecteur + " {")
    assert i >= 0, "règle introuvable : %s" % selecteur
    return css[i:css.find("}", i)]


def test_la_fenetre_se_deploie_en_largeur():
    """RATCHET : repasser le corps en une seule colonne, ou rétrécir la carte,
    fait virer ce test au ROUGE.

    ⚠️ Mesuré : en colonne unique, un compte d'administrateur donnait une
    carte de 620 x 780 px qui passait sous le pli d'un portable. En deux
    colonnes elle fait 1000 x 701 px et tient entière jusqu'en 1280 x 800.
    La largeur est la ressource dont on dispose — pas la hauteur.
    """
    css = _lire(FEUILLE)

    carte = _regle(css, "#welcome-popup-card")
    largeur = re.search(r"max-width:\s*(\d+)px", carte)
    assert largeur, "la carte ne borne plus sa largeur"
    assert int(largeur.group(1)) >= 900, (
        "la carte est revenue à une colonne étroite (max-width: %spx) : "
        "le contenu repart en hauteur" % largeur.group(1))

    corps = _regle(css, "#welcome-popup-body")
    assert "display: grid" in corps, (
        "le corps de la fenêtre n'est plus une grille : les sections "
        "s'empilent de nouveau")
    pistes = re.search(r"grid-template-columns:([^;]+);", corps)
    assert pistes, "le corps ne déclare plus ses colonnes"
    assert pistes.group(1).count("minmax(") >= 2, (
        "le corps n'a plus qu'une colonne : %r" % pistes.group(1).strip())


def test_sur_un_ecran_etroit_elle_retombe_en_une_colonne():
    """RATCHET : retirer le repli fait virer ce test au ROUGE.

    Deux colonnes sur un écran étroit donnent des libellés sur quatre lignes —
    plus HAUT que la version empilée qu'on cherchait à raccourcir. Le seuil se
    compare à la largeur réelle de la fenêtre : les requêtes média ignorent le
    `zoom` du body.
    """
    css = _lire(FEUILLE)
    i = css.find("@media (max-width: 900px)")
    assert i >= 0, (
        "le repli en colonne unique a disparu : sur un écran étroit la "
        "fenêtre garde deux colonnes illisibles")
    bloc = css[i:css.find("\n}", i)]

    assert "#welcome-popup-body" in bloc, (
        "le repli ne touche plus le corps de la fenêtre")
    corps = bloc[bloc.find("#welcome-popup-body"):]
    pistes = re.search(r"grid-template-columns:([^;]+);", corps)
    assert pistes and pistes.group(1).count("minmax(") == 1, (
        "le corps ne retombe pas sur une seule colonne : %r"
        % (pistes.group(1).strip() if pistes else None,))

    # ⚠️ `.wp-portes:has(...)` est plus spécifique que `.wp-portes` : sans le
    # même sélecteur ici, les portes d'un administrateur resteraient sur deux
    # colonnes dans un écran où elles ne tiennent pas.
    assert ".wp-portes:has(" in bloc, (
        "le repli des portes n'a pas la spécificité de la règle qu'il "
        "annule : elle l'emportera")


# ══════════════════════════════════════════════════════════════════════════
#  Ce qu'elle montre de CONCRET : les propositions reçues
#
#  ⚠️⚠️ Le défaut de fond réparé ici : `attentes()` ne lisait qu'UNE des deux
#  files de propositions (`carto_sharing`), alors que le bandeau de la page
#  Carte lit les DEUX — un coordinateur pouvait donc lire « 2 à arbitrer »
#  dans cette fenêtre et « 5 » sur le bandeau, pour la même attente.
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def decor_props(app, comptes):
    """Une carto commune du champion, et des propositions en attente dessus.

    ⚠️ Tout est détruit en partant : une carto laissée COMMUNE devient le repli
    « aucune entité active » des fichiers suivants, et une proposition en
    attente ferait apparaître un bandeau dans des tests qui ne parlent pas de
    gouvernance.
    """
    from Code.extensions import db
    from Code.models.models import (ActivityChangeRequest, CartoChangeRequest,
                                    Entity)

    with app.app_context():
        ent = Entity(name="T127 carto commune", owner_id=comptes["champion"],
                     is_shared=True)
        db.session.add(ent)
        db.session.commit()
        eid = ent.id
    yield {"entity": eid, "auteur": comptes["champion"]}
    with app.app_context():
        CartoChangeRequest.query.filter_by(entity_id=eid).delete()
        ActivityChangeRequest.query.filter_by(entity_id=eid).delete()
        e = db.session.get(Entity, eid)
        if e is not None:
            db.session.delete(e)
        db.session.commit()


def _proposer_carto(app, eid, auteur, n=1):
    from Code.extensions import db
    from Code.models.models import CartoChangeRequest
    with app.app_context():
        for i in range(n):
            db.session.add(CartoChangeRequest(
                entity_id=eid, author_id=auteur, status="pending",
                title="T127 carte %d" % i, diagram="{}"))
        db.session.commit()


def _proposer_fiche(app, eid, auteur, gestes=2, statut="pending"):
    import json as _json
    from Code.extensions import db
    from Code.models.models import ActivityChangeRequest
    actions = [{"op": "task.add", "objet": "T127 tache %d" % i}
               for i in range(gestes)]
    with app.app_context():
        cr = ActivityChangeRequest(entity_id=eid, author_id=auteur,
                                   status=statut, actions=_json.dumps(actions))
        db.session.add(cr)
        db.session.commit()
        return cr.id


def _props(app, user_id, lang="fr"):
    from Code import bienvenue
    with app.test_request_context("/"):
        from flask import session
        session["user_id"] = user_id
        session["lang"] = lang
        return bienvenue.propositions_recues(lang=lang)


def _attentes(app, user_id, lang="fr"):
    from Code import bienvenue
    with app.test_request_context("/"):
        from flask import session
        session["user_id"] = user_id
        session["lang"] = lang
        return bienvenue.attentes(lang=lang)


def test_les_DEUX_files_de_propositions_sont_lues(app, comptes, decor_props):
    """⚠️ Le cliquet du défaut : en ne lisant que `carto_sharing`, on compte 2
    au lieu de 3 — et la fenêtre contredit le bandeau de la page Carte."""
    _proposer_carto(app, decor_props["entity"], decor_props["auteur"], n=2)
    _proposer_fiche(app, decor_props["entity"], decor_props["auteur"])

    vu = _props(app, comptes["coordinateur"])
    assert vu["n"] == 3, vu
    genres = sorted(l["genre"] for l in vu["lignes"])
    assert genres == ["carto", "carto", "fiche"], genres


def test_le_compte_annonce_est_celui_des_DEUX_sources(app, comptes, decor_props):
    """L'invariant, pas une seconde implémentation : ce que la fenêtre annonce
    doit valoir ce que rendent les deux fonctions dont le bandeau se sert."""
    _proposer_carto(app, decor_props["entity"], decor_props["auteur"], n=2)
    _proposer_fiche(app, decor_props["entity"], decor_props["auteur"])

    from Code.permissions import current_user
    with app.test_request_context("/"):
        from flask import session
        session["user_id"] = comptes["coordinateur"]
        from Code.routes.activite_propositions import (
            propositions_a_examiner as fiches)
        from Code.routes.carto_sharing import propositions_a_examiner as cartos
        acteur = current_user()
        attendu = len(cartos(acteur)) + len(fiches(acteur))
        from Code import bienvenue
        assert bienvenue.propositions_recues()["n"] == attendu


def test_chaque_proposition_est_NOMMEE_pas_comptee(app, comptes, decor_props):
    """Un chiffre n'apprend rien : il fallait ouvrir la file pour savoir ce
    qu'on venait de recevoir."""
    _proposer_fiche(app, decor_props["entity"], decor_props["auteur"], gestes=2)
    ligne = _props(app, comptes["coordinateur"])["lignes"][0]
    assert ligne["auteur"] and ligne["auteur"] != "", ligne
    assert "Bienvenue" in ligne["auteur"], ligne          # nom de famille du décor
    assert ligne["carto"] == "T127 carto commune", ligne
    assert "2" in ligne["quoi"], ligne                    # deux gestes


def test_au_dela_de_trois_elle_dit_et_n_de_plus(app, comptes, decor_props):
    """La fenêtre est LARGE, pas haute : dix lignes la feraient défiler, et
    c'est la file d'examen qui est faite pour les lire toutes."""
    from Code.bienvenue import PROPOSITIONS_NOMMEES
    _proposer_carto(app, decor_props["entity"], decor_props["auteur"],
                    n=PROPOSITIONS_NOMMEES + 2)
    vu = _props(app, comptes["coordinateur"])
    assert len(vu["lignes"]) == PROPOSITIONS_NOMMEES, vu
    assert vu["reste"] == 2, vu
    assert vu["n"] == PROPOSITIONS_NOMMEES + 2, vu


def test_rien_pour_qui_ne_tranche_pas(app, comptes, decor_props):
    """Les deux sources rendent [] tout de suite pour qui ne valide pas : la
    section n'existe donc pas, et son coût est nul pour ces paliers."""
    _proposer_carto(app, decor_props["entity"], decor_props["auteur"], n=2)
    for palier in ("user", "champion"):
        vu = _props(app, comptes[palier])
        assert vu["lignes"] == [], (palier, vu)
        assert vu["n"] == 0, (palier, vu)


def test_on_ne_s_alerte_pas_soi_meme(app, comptes, decor_props):
    from Code.extensions import db
    from Code.models.models import CartoChangeRequest
    with app.app_context():
        db.session.add(CartoChangeRequest(
            entity_id=decor_props["entity"], author_id=comptes["coordinateur"],
            status="pending", title="T127 la mienne", diagram="{}"))
        db.session.commit()
    assert _props(app, comptes["coordinateur"])["n"] == 0


def test_la_section_ne_redit_pas_ce_que_les_attentes_disaient(app, comptes,
                                                              decor_props):
    """⚠️ La ligne « n propositions à arbitrer » a cédé la place à la section
    qui les NOMME. Les deux ensemble diraient deux fois la même chose, et son
    libellé est devenu une clé morte."""
    _proposer_carto(app, decor_props["entity"], decor_props["auteur"], n=2)
    cles = [a["cle"] for a in _attentes(app, comptes["coordinateur"])]
    assert "arbitrer" not in cles, cles

    from Code.translations import TRANSLATIONS
    for langue in ("fr", "en"):
        assert "welcome.wait.review" not in TRANSLATIONS[langue], langue


def test_les_decisions_comptent_les_DEUX_files(app, comptes, decor_props):
    """⚠️ Seule celle de la carto l'était : une décision sur une proposition de
    FICHE ne s'annonçait nulle part ici."""
    from Code.extensions import db
    from Code.models.models import ActivityChangeRequest, CartoChangeRequest
    with app.app_context():
        db.session.add(CartoChangeRequest(
            entity_id=decor_props["entity"], author_id=comptes["champion"],
            status="approved", title="T127 tranchee", diagram="{}"))
        db.session.commit()
    _proposer_fiche(app, decor_props["entity"], comptes["champion"],
                    statut="rejected")

    att = {a["cle"]: a["n"] for a in _attentes(app, comptes["champion"])}
    assert att.get("decisions") == 2, att


def test_un_brouillon_non_envoye_est_annonce(app, comptes, decor_props):
    """Le geste le plus facile à oublier : on range trois modifications, on
    change de page, et personne ne les examinera jamais."""
    _proposer_fiche(app, decor_props["entity"], comptes["champion"],
                    gestes=3, statut="draft")
    att = {a["cle"]: a["n"] for a in _attentes(app, comptes["champion"])}
    assert att.get("brouillon") == 3, att


def test_un_brouillon_VIDE_ne_s_annonce_pas(app, comptes, decor_props):
    """On compte les GESTES, pas les lignes : un brouillon ouvert et vide
    n'attend rien de personne."""
    _proposer_fiche(app, decor_props["entity"], comptes["champion"],
                    gestes=0, statut="draft")
    cles = [a["cle"] for a in _attentes(app, comptes["champion"])]
    assert "brouillon" not in cles, cles


def test_les_seances_a_tenir_sont_annoncees(app, comptes):
    from datetime import date, timedelta

    from Code.extensions import db
    from Code.models.models import SessionEvaluation
    with app.app_context():
        s = SessionEvaluation(user_id=comptes["user"],
                              developpeur_user_id=comptes["coordinateur"],
                              date_prevue=date.today() + timedelta(days=2),
                              statut="prevue")
        db.session.add(s)
        db.session.commit()
        sid = s.id
    try:
        att = {a["cle"]: a["n"] for a in _attentes(app, comptes["coordinateur"])}
        assert att.get("seances") == 1, att
    finally:
        with app.app_context():
            obj = db.session.get(SessionEvaluation, sid)
            if obj is not None:
                db.session.delete(obj)
            db.session.commit()


def test_la_fenetre_ne_charge_JAMAIS_toute_la_table_des_seances():
    """⚠️ `_sessions_lisibles` rend `SessionEvaluation.query.all()` pour un
    statut élevé. Cette fenêtre est rendue à CHAQUE page : un COUNT indexé,
    jamais ce chargement."""
    src = _lire(os.path.join(RACINE, "Code", "bienvenue.py"))
    # ⚠️ On retire les COMMENTAIRES avant de chercher : celui qui explique
    # POURQUOI on n'appelle pas `_sessions_lisibles` cite son nom, et ce
    # contrôle s'est d'abord attrapé lui-même. Quatrième occurrence de ce
    # piège dans ce dépôt (les clés i18n construites, le `<section>` de la doc
    # technique, les guillemets du standard minimal).
    code = re.sub(r"(?m)^\s*#.*$", "", src)
    code = re.sub(r'"""(?:.|\n)*?"""', "", code)
    assert "_sessions_lisibles" not in code, (
        "la fenêtre de bienvenue charge toutes les sessions à chaque page")
    i = code.find("SessionEvaluation")
    assert i > 0 and ".count()" in code[i:i + 700], (
        "le compte des séances n'est pas un COUNT")


def test_les_auteurs_sont_lus_en_UNE_requete(app, comptes, decor_props):
    """⚠️ `cr.author` dans la boucle ferait un aller par proposition, sur une
    fenêtre rendue à CHAQUE page de l'application.

    ⚠️ Le décor sème TROIS auteurs différents : avec un seul, `ids` n'a qu'un
    élément et une requête par ligne rend exactement le même compte — le
    cliquet restait vert en remettant le défaut (vérifié).
    """
    from sqlalchemy import event

    from Code.extensions import db
    from Code.models.models import CartoChangeRequest

    auteurs = [comptes["champion"], comptes["user"], comptes["admin"]]
    with app.app_context():
        for i, auteur in enumerate(auteurs * 2):
            db.session.add(CartoChangeRequest(
                entity_id=decor_props["entity"], author_id=auteur,
                status="pending", title="T127 cout %d" % i, diagram="{}"))
        db.session.commit()

    with app.app_context():
        moteur = db.engine
        vues = []

        def espion(conn, cur, stmt, params, ctx, many):
            vues.append(" ".join(str(stmt).split()))

        event.listen(moteur, "before_cursor_execute", espion)
        try:
            with app.test_request_context("/"):
                from flask import session
                session["user_id"] = comptes["coordinateur"]
                from Code import bienvenue
                vu = bienvenue.propositions_recues()
        finally:
            event.remove(moteur, "before_cursor_execute", espion)

    assert vu["n"] == 6, vu
    # Les noms des auteurs : UNE seule requête, et elle les demande ENSEMBLE.
    sur_users = [q for q in vues
                 if "FROM users" in q and "users.id IN" in q]
    assert len(sur_users) == 1, (
        "les auteurs sont lus en %d requête(s) au lieu d'une : %r"
        % (len(sur_users), sur_users[:3]))
    # Et les trois noms sont bien là : on ne lit pas qu'un auteur sur trois.
    noms = {l["auteur"] for l in vu["lignes"]}
    assert len(noms) >= 2, noms


def test_les_libelles_neufs_existent_dans_LES_DEUX_langues():
    """⚠️ On lit les DICTIONNAIRES, pas `t()` : une clé absente de l'anglais
    retombe SILENCIEUSEMENT sur le français, et le contrôle passerait."""
    from Code.translations import TRANSLATIONS
    neuves = ["welcome.props", "welcome.props_open", "welcome.props_more",
              "welcome.props_cartos", "welcome.props_carto",
              "welcome.props_fiche", "welcome.props_anon",
              "welcome.wait.draft", "welcome.wait.sessions"]
    for langue in ("fr", "en"):
        manquantes = [c for c in neuves if c not in TRANSLATIONS[langue]]
        assert not manquantes, (langue, manquantes)
    identiques = [c for c in neuves
                  if TRANSLATIONS["fr"][c] == TRANSLATIONS["en"][c]]
    assert not identiques, identiques


def test_les_libelles_a_trou_gardent_leur_marqueur():
    """`%s` résolu en Python, comme `welcome.hello` — pas `[[n]]`, qui est la
    convention des catalogues lus par le JavaScript."""
    from Code.translations import TRANSLATIONS
    for cle in ("welcome.props_more", "welcome.props_cartos",
                "welcome.props_fiche"):
        for langue in ("fr", "en"):
            valeur = TRANSLATIONS[langue][cle]
            assert "%s" in valeur, (cle, langue, valeur)
            assert "[[" not in valeur, (cle, langue, valeur)


def test_la_section_vit_dans_la_colonne_DE_GAUCHE():
    """⚠️ La contrainte du gabarit : « une section de plus va dans une colonne
    existante — une troisième colonne ne tiendrait pas la largeur »."""
    g = _lire(GABARIT)
    debut = g.index('class="wp-col wp-col--actu"')
    fin = g.index('class="wp-col wp-col--portes"')
    colonne = g[debut:fin]
    assert "wp-bloc--props" in colonne, (
        "la section des propositions n'est pas dans la colonne de gauche")
    # Et AVANT les nouveautés : c'est la seule chose sur laquelle on attend
    # une réponse de ce compte.
    assert colonne.index("wp-bloc--props") < colonne.index("welcome.news"), (
        "les propositions passent après les nouveautés")
    assert g.count('class="wp-col') == 2, (
        "une troisième colonne est apparue dans la fenêtre")


def test_la_section_n_est_pas_rendue_quand_il_n_y_a_rien(app, client, comptes):
    """Une section d'alerte qui s'affiche à vide cesse d'être lue."""
    _connecter(app, client, comptes["coordinateur"])
    html = _page(client)
    assert "wp-bloc--props" not in html


def test_la_section_est_rendue_dans_les_deux_langues(app, client, comptes,
                                                     decor_props):
    _proposer_carto(app, decor_props["entity"], decor_props["auteur"], n=1)
    for langue, mot in (("fr", "Propositions reçues"),
                        ("en", "Proposals received")):
        _connecter(app, client, comptes["coordinateur"], lang=langue)
        html = _page(client)
        assert "wp-bloc--props" in html, langue
        assert mot in html, langue
        # Aucune clé brute, aucun marqueur laissé en plan.
        assert "welcome.props" not in html, langue
        assert ">%s<" not in html, langue


def test_l_habillage_de_la_section_ne_lit_pas_l_accent_de_la_RACINE():
    """⚠️ `--pg-accent-soft` et ses frères sont déclarés sur `:root`, où
    `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS sur
    toute l'application."""
    css = _lire(FEUILLE)
    sans_commentaires = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    i = sans_commentaires.find(".wp-bloc--props")
    assert i > 0, "l'habillage de la section est absent"
    for jeton in ("--pg-accent-soft", "--pg-accent-softer",
                  "--pg-accent-border", "--pg-accent-glow"):
        assert jeton not in sans_commentaires[i:], jeton
