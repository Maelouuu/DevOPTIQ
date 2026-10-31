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


def _valeurs_welcome():
    """Les couples (fr, en) des clés `welcome.*` qui DIFFÈRENT d'une langue à
    l'autre — les seules sur lesquelles une fuite se voie."""
    from Code.translations import TRANSLATIONS

    couples = []
    for cle, fr in TRANSLATIONS["fr"].items():
        if not cle.startswith("welcome."):
            continue
        en = TRANSLATIONS["en"].get(cle)
        if not isinstance(fr, str) or not isinstance(en, str):
            continue
        # « Bonjour %s » : on compare le morceau fixe.
        fr_fixe, en_fixe = fr.split("%s")[0].strip(), en.split("%s")[0].strip()
        if fr_fixe and en_fixe and fr_fixe != en_fixe:
            couples.append((cle, fr_fixe, en_fixe))
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
