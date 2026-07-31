"""Ré-enregistre les 6 vidéos du guide en session déjà ouverte (pas de login à l'écran)."""
import os
import shutil
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(BASE, '..', '..', 'docs', 'assets', 'guide'))
STATE = os.path.join(BASE, 'auth_state.json')
URL = 'http://127.0.0.1:5601'

CURSOR_JS = open(os.path.join(BASE, 'capture_screens.py')).read().split('CURSOR_JS = """')[1].split('"""')[0]


def dismiss(pg):
    try:
        btn = pg.locator('#welcome-popup-close')
        if btn.count() and btn.is_visible():
            btn.click()
            pg.wait_for_timeout(300)
    except Exception:
        pass


def goto(pg, path, wait=1000):
    pg.goto(URL + path, wait_until='domcontentloaded')
    pg.wait_for_timeout(wait)
    dismiss(pg)


def slow_click(pg, locator, before=500, after=1100):
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box:
        pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, steps=26)
    pg.wait_for_timeout(before)
    locator.click()
    pg.wait_for_timeout(after)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')

    # Session une fois pour toutes
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
        # Pop-up de bienvenue neutralisée + CDN externes coupés (rendu immédiat)
        ctx.add_init_script("sessionStorage.setItem('optiq_welcome_seen_v4','1');")
        ctx.route('**://fonts.googleapis.com/**', lambda r: r.abort())
        ctx.route('**://fonts.gstatic.com/**', lambda r: r.abort())
        ctx.route('**://cdnjs.cloudflare.com/**', lambda r: r.abort())
        ctx.route('**://cdn.jsdelivr.net/**', lambda r: r.abort())
        pg = ctx.new_page()
        pg.goto(URL + start, wait_until='domcontentloaded')
        pg.wait_for_timeout(1600)
        try:
            flow(pg)
        except Exception as e:
            print('FLOW ERROR', name, e)
        pg.wait_for_timeout(900)
        path = pg.video.path()
        ctx.close()
        shutil.move(path, os.path.join(OUT, name))
        print('video', name)

    def flow_activite(pg):
        s = pg.locator('.activity-search-input')
        slow_click(pg, s, after=300)
        pg.keyboard.type('cotation', delay=150)
        pg.wait_for_timeout(1100)
        slow_click(pg, pg.locator('.activity-container:visible .activity-header').first, after=1300)
        for label in ['Compétences', 'Temps']:
            t = pg.locator('.tab-button:visible', has_text=label).first
            if t.count():
                slow_click(pg, t, after=1600)

    def flow_role(pg):
        slow_click(pg, pg.locator('.role-header').first, after=1200)
        for txt in ['Garant', 'Savoir']:
            b = pg.locator('.block-header', has_text=txt).first
            if b.count():
                slow_click(pg, b, after=1600)

    def flow_faiblesse(pg):
        slow_click(pg, pg.locator('.subtab[data-subtab="faiblesse"]'), after=1000)
        f = pg.locator('#fw-k'); slow_click(pg, f, after=200)
        pg.keyboard.type('Données client incomplètes', delay=60)
        f = pg.locator('#fw-n'); f.click(); f.fill(''); pg.keyboard.type('4', delay=140)
        f = pg.locator('#fw-l'); f.click(); pg.keyboard.type('25', delay=140)
        f = pg.locator('#fw-m'); f.click(); pg.keyboard.type('120', delay=140)
        if pg.locator('#fw-dur').input_value() in ('', '0'):
            f = pg.locator('#fw-dur'); f.click(); f.fill(''); pg.keyboard.type('40', delay=130)
        slow_click(pg, pg.locator('#btn-fw-calc'), after=1500)
        pg.locator('#fw-results-section').scroll_into_view_if_needed()
        pg.wait_for_timeout(2400)

    def flow_carto(pg):
        cv = pg.locator('svg').first
        box = cv.bounding_box()
        if box:
            cx, cy = box['x'] + box['width'] * 0.45, box['y'] + box['height'] * 0.35
            pg.mouse.move(cx, cy, steps=25)
            pg.wait_for_timeout(600)
            for _ in range(4):
                pg.mouse.wheel(0, -240)
                pg.wait_for_timeout(500)
            pg.mouse.move(cx + 130, cy + 60, steps=22)
            pg.wait_for_timeout(900)
        srch = pg.locator('input[placeholder*="activité" i]').first
        if srch.count():
            slow_click(pg, srch, after=300)
            pg.keyboard.type('analyse', delay=140)
            pg.wait_for_timeout(1500)

    def flow_export(pg):
        slow_click(pg, pg.locator('#btn-export-roles'), after=1400)
        slow_click(pg, pg.locator('#fmt-html-card'), after=1100)
        slow_click(pg, pg.locator('#fmt-excel-card'), after=1100)
        slow_click(pg, pg.locator('#exportModalCancel'), after=600)

    def flow_competences(pg):
        li = pg.locator('.cv2-collab li').first
        if li.count():
            slow_click(pg, li, after=2200)
        li2 = pg.locator('.cv2-collab li').nth(1)
        if li2.count():
            slow_click(pg, li2, after=2200)

    video('flux-activite.webm', flow_activite, '/activities/view')
    video('flux-role.webm', flow_role, '/roles_view/')
    video('flux-faiblesse.webm', flow_faiblesse, '/temps/')
    video('flux-carto.webm', flow_carto, '/activities/map')
    video('flux-export.webm', flow_export, '/roles_view/')
    video('flux-competences.webm', flow_competences, '/competences/view')
    browser.close()
print('VIDEOS OK')
