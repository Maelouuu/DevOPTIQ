"""Vidéos de démonstration du guide — de VRAIS parcours utilisateur.

Chaque flux rejoue, dans l'ordre, le pas-à-pas écrit dans la section
correspondante du guide (docs/guide.html) : ce que le texte explique,
la vidéo le montre. Curseur visible + halo de clic, rythme lent.
Sortie : docs/assets/guide/flux-*.webm (session déjà ouverte, pas de login
à l'écran ; pop-up de bienvenue neutralisée ; CDN externes coupés pour un
rendu immédiat).
"""
import os
import shutil
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(BASE, '..', '..', 'docs', 'assets', 'guide'))
STATE = os.path.join(BASE, 'auth_state.json')
URL = 'http://127.0.0.1:5601'

CURSOR_JS = open(os.path.join(BASE, 'capture_screens.py')).read().split('CURSOR_JS = """')[1].split('"""')[0]


def slow_click(pg, locator, before=500, after=1100):
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box:
        pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, steps=26)
    pg.wait_for_timeout(before)
    locator.click()
    pg.wait_for_timeout(after)


def type_slow(pg, locator, text, clear=False, delay=70):
    slow_click(pg, locator, after=250)
    if clear:
        locator.fill('')
    pg.keyboard.type(text, delay=delay)
    pg.wait_for_timeout(400)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')

    # Session une fois pour toutes (le login n'apparaît pas dans les vidéos)
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(URL + '/login')
    pg.fill('input[name="email"]', 'demo@afdec.fr')
    pg.fill('input[name="password"]', 'Visual123!')
    pg.click('button[type="submit"], input[type="submit"]')
    pg.wait_for_load_state('networkidle')
    ctx.storage_state(path=STATE)
    ctx.close()

    def video(name, flow, start):
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800},
                                  storage_state=STATE,
                                  record_video_dir=OUT,
                                  record_video_size={'width': 1280, 'height': 800})
        ctx.add_init_script(CURSOR_JS)
        ctx.add_init_script("sessionStorage.setItem('optiq_welcome_seen_v4','1');")
        for pat in ['**://fonts.googleapis.com/**', '**://fonts.gstatic.com/**',
                    '**://cdnjs.cloudflare.com/**', '**://cdn.jsdelivr.net/**']:
            ctx.route(pat, lambda r: r.abort())
        pg = ctx.new_page()
        pg.goto(URL + start, wait_until='domcontentloaded')
        pg.wait_for_timeout(1600)
        try:
            flow(pg)
        except Exception as e:
            print('FLOW ERROR', name, e)
        pg.wait_for_timeout(1200)
        path = pg.video.path()
        ctx.close()
        shutil.move(path, os.path.join(OUT, name))
        print('video', name)

    # ── Cartographie : se déplacer, zoomer, ouvrir une activité ─────────────
    # (pas-à-pas « Naviguer dans la carte », étapes 1-2-3)
    def flow_carto(pg):
        cv = pg.locator('svg').first
        box = cv.bounding_box()
        if box:
            cx, cy = box['x'] + box['width'] * 0.5, box['y'] + box['height'] * 0.4
            # 1. déplacer (cliquer-glisser)
            pg.mouse.move(cx, cy, steps=22)
            pg.wait_for_timeout(500)
            pg.mouse.down()
            pg.mouse.move(cx - 160, cy - 60, steps=30)
            pg.mouse.up()
            pg.wait_for_timeout(700)
            # 2. zoomer à la molette
            for _ in range(4):
                pg.mouse.wheel(0, -240)
                pg.wait_for_timeout(450)
            pg.wait_for_timeout(600)
        # 3. cliquer une activité dans la liste de droite → sa fiche s'ouvre
        item = pg.locator('text=Analyse de faisabilité').last
        if item.count():
            slow_click(pg, item, after=2500)

    # ── Activités : rechercher, déplier, parcourir les onglets ──────────────
    def flow_activite(pg):
        s = pg.locator('.activity-search-input')
        type_slow(pg, s, 'cotation', delay=140)
        pg.wait_for_timeout(900)
        slow_click(pg, pg.locator('.activity-container:visible .activity-header').first, after=1500)
        for label in ['Compétences', 'Savoirs', 'Temps']:
            t = pg.locator('.tab-button:visible', has_text=label).first
            if t.count():
                slow_click(pg, t, after=1700)

    # ── Rôles : rechercher, déplier, éditer la mission, parcourir 2 volets ──
    def flow_role(pg):
        s = pg.locator('#roleSearchInput')
        type_slow(pg, s, 'customer', delay=130)
        pg.wait_for_timeout(700)
        slow_click(pg, pg.locator('.role-container:visible .role-header').first, after=1300)
        # Mission générale : compléter puis Enregistrer
        ta = pg.locator('.role-container:visible .mission-area').first
        if ta.count():
            slow_click(pg, ta, after=250)
            pg.keyboard.press('End')
            pg.keyboard.type(' Répondre au client sous 48 h.', delay=55)
            pg.wait_for_timeout(400)
            save = pg.locator('.role-container:visible .mission-footer .btn-primary').first
            if save.count():
                slow_click(pg, save, after=1400)
        for txt in ['Garant', 'Savoir']:
            b = pg.locator('.role-container:visible .block-header', has_text=txt).first
            if b.count():
                slow_click(pg, b, after=1700)

    # ── Compétences : collaborateur → rôles → ouvrir l'évaluation ───────────
    def flow_competences(pg):
        li = pg.locator('.cv2-collab li').first
        if li.count():
            slow_click(pg, li, after=2200)
        pills = pg.locator('.cv2-role')
        if pills.count() > 1:
            slow_click(pg, pills.nth(1), after=2000)
            slow_click(pg, pills.first, after=2000)
        ev = pg.locator('.cv2-tab button', has_text='Évaluer').first
        if ev.count():
            slow_click(pg, ev, after=3000)

    # ── Temps / Projet : nommer, remplir, ajouter une ligne, enregistrer ────
    def flow_projet(pg):
        type_slow(pg, pg.locator('#project-name'), 'Salon professionnel 2026', delay=55)
        row = pg.locator('#project-rows tr').first
        type_slow(pg, row.locator('.cell-dur'), '2', clear=True, delay=120)
        row.locator('.cell-du select').select_option(label='heures')
        pg.wait_for_timeout(500)
        type_slow(pg, row.locator('.cell-del'), '1', clear=True, delay=120)
        row.locator('.cell-deu select').select_option(label='jours')
        pg.wait_for_timeout(500)
        type_slow(pg, row.locator('.cell-nbp'), '2', clear=True, delay=120)
        slow_click(pg, pg.locator('#btn-add-line'), after=900)
        row2 = pg.locator('#project-rows tr').nth(1)
        row2.locator('.cell-act select').select_option(index=3)
        pg.wait_for_timeout(400)
        type_slow(pg, row2.locator('.cell-dur'), '4', clear=True, delay=120)
        row2.locator('.cell-du select').select_option(label='heures')
        pg.wait_for_timeout(800)
        pg.locator('.kpis').first.scroll_into_view_if_needed()
        pg.wait_for_timeout(1200)
        slow_click(pg, pg.locator('#btn-save-project'), after=2200)

    # ── Temps / Faiblesse : saisie complète puis calcul ─────────────────────
    def flow_faiblesse(pg):
        slow_click(pg, pg.locator('.subtab[data-subtab="faiblesse"]'), after=1000)
        type_slow(pg, pg.locator('#fw-k'), 'Données client incomplètes', delay=55)
        f = pg.locator('#fw-n'); f.click(); f.fill(''); pg.keyboard.type('4', delay=140)
        f = pg.locator('#fw-l'); f.click(); pg.keyboard.type('25', delay=140)
        f = pg.locator('#fw-m'); f.click(); pg.keyboard.type('120', delay=140)
        if pg.locator('#fw-dur').input_value() in ('', '0'):
            f = pg.locator('#fw-dur'); f.click(); f.fill(''); pg.keyboard.type('40', delay=130)
        slow_click(pg, pg.locator('#btn-fw-calc'), after=1500)
        pg.locator('#fw-results-section').scroll_into_view_if_needed()
        pg.wait_for_timeout(2600)

    # ── Rôles : exporter (périmètre + format) ───────────────────────────────
    def flow_export(pg):
        slow_click(pg, pg.locator('#btn-export-roles'), after=1500)
        sel = pg.locator('#exportRoleSelect')
        if sel.count():
            sel.select_option(index=1)
            pg.wait_for_timeout(900)
        slow_click(pg, pg.locator('#fmt-html-card'), after=1200)
        slow_click(pg, pg.locator('#fmt-excel-card'), after=1200)
        slow_click(pg, pg.locator('#exportModalCancel'), after=600)

    video('flux-carto.webm', flow_carto, '/activities/map')
    video('flux-activite.webm', flow_activite, '/activities/view')
    video('flux-role.webm', flow_role, '/roles_view/')
    video('flux-competences.webm', flow_competences, '/competences/view')
    video('flux-projet.webm', flow_projet, '/temps/')
    video('flux-faiblesse.webm', flow_faiblesse, '/temps/')
    video('flux-export.webm', flow_export, '/roles_view/')
    browser.close()
print('VIDEOS OK')
