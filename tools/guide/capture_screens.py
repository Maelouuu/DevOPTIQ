"""Captures d'écran du guide utilisateur (les vidéos : capture_videos.py).

Produit dans ./guide_assets/ :
  - des PNG (pages et détails) — viewport 1440x900
  - des WEBM (manipulations, curseur visible, rythme lent) — 1280x800
"""
import os
import shutil
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(BASE, '..', '..', 'docs', 'assets', 'guide'))
os.makedirs(OUT, exist_ok=True)
URL = 'http://127.0.0.1:5601'

# Curseur visible + halo de clic pour les vidéos
CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;z-index:2147483647;width:18px;height:18px;'
    + 'border-radius:50%;background:rgba(15,23,42,.85);border:2.5px solid #fff;'
    + 'box-shadow:0 1px 6px rgba(0,0,0,.45);pointer-events:none;'
    + 'transform:translate(-50%,-50%);left:-40px;top:-40px;transition:left .05s linear, top .05s linear;';
  document.body.appendChild(c);
  window.addEventListener('mousemove', e => { c.style.left = e.clientX+'px'; c.style.top = e.clientY+'px'; }, true);
  window.addEventListener('mousedown', e => {
    const r = document.createElement('div');
    r.style.cssText = 'position:fixed;z-index:2147483646;width:14px;height:14px;border-radius:50%;'
      + 'border:3px solid rgba(37,99,235,.9);pointer-events:none;transform:translate(-50%,-50%);'
      + 'left:'+e.clientX+'px;top:'+e.clientY+'px;transition:all .5s ease-out;opacity:1;';
    document.body.appendChild(r);
    requestAnimationFrame(() => { r.style.width='52px'; r.style.height='52px'; r.style.opacity='0'; });
    setTimeout(() => r.remove(), 650);
  }, true);
});
"""


def login(pg):
    pg.goto(URL + '/login')
    pg.fill('input[name="email"]', 'demo@afdec.fr')
    pg.fill('input[name="password"]', 'Visual123!')
    pg.click('button[type="submit"], input[type="submit"]')
    pg.wait_for_load_state('networkidle')


def dismiss(pg):
    try:
        btn = pg.locator('#welcome-popup-close')
        if btn.count() and btn.is_visible():
            btn.click()
            pg.wait_for_timeout(300)
    except Exception:
        pass


def goto(pg, path, wait=900):
    pg.goto(URL + path, wait_until='networkidle')
    pg.wait_for_timeout(wait)
    dismiss(pg)


def slow_click(pg, locator, before=600, after=900):
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box:
        pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, steps=28)
    pg.wait_for_timeout(before)
    locator.click()
    pg.wait_for_timeout(after)


def shot(pg, name, full=False, clip=None):
    pg.screenshot(path=os.path.join(OUT, name), full_page=full, clip=clip)
    print('shot', name)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')

    # ════════════ CAPTURES ════════════
    ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()

    # Connexion (avant login)
    pg.goto(URL + '/login')
    pg.wait_for_timeout(600)
    shot(pg, 'login.png')

    login(pg)
    pg.wait_for_timeout(1500)
    # Pop-up de bienvenue (élément du produit, utile au guide)
    if pg.locator('#welcome-popup-overlay').count():
        shot(pg, 'bienvenue.png')
    dismiss(pg)

    # Cartographie
    shot(pg, 'carto.png')
    shot(pg, 'nav.png', clip={'x': 120, 'y': 8, 'width': 1200, 'height': 92})

    # Activités
    goto(pg, '/activities/view')
    shot(pg, 'activites-liste.png')
    slow_click(pg, pg.locator('.activity-header').first, before=100, after=800)
    shot(pg, 'activite-fiche.png')
    tab = pg.locator('.tab-button', has_text='Compétences').first
    if tab.count():
        slow_click(pg, tab, before=100, after=800)
        shot(pg, 'activite-onglet-competences.png')

    # Rôles
    goto(pg, '/roles_view/')
    shot(pg, 'roles-liste.png')
    slow_click(pg, pg.locator('.role-header').first, before=100, after=700)
    b1 = pg.locator('.block-header', has_text='Garant').first
    if b1.count():
        slow_click(pg, b1, before=100, after=700)
    shot(pg, 'role-detail.png', full=True)
    # Modale export
    pg.locator('#btn-export-roles').click()
    pg.wait_for_timeout(900)
    shot(pg, 'roles-export.png')
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(400)

    # Compétences
    goto(pg, '/competences/view')
    li = pg.locator('.cv2-collab li').first
    if li.count():
        slow_click(pg, li, before=100, after=1400)
    shot(pg, 'competences.png')

    # Temps
    goto(pg, '/temps/')
    acc = pg.locator('#project-list .acc-head').first
    if acc.count():
        slow_click(pg, acc, before=100, after=800)
    shot(pg, 'temps-projet.png')
    slow_click(pg, pg.locator('.subtab[data-subtab="role"]'), before=100, after=900)
    shot(pg, 'temps-role.png')
    slow_click(pg, pg.locator('.subtab[data-subtab="faiblesse"]'), before=100, after=700)
    pg.locator('#fw-k').fill('Données client incomplètes à la réception')
    pg.locator('#fw-n').fill('4')
    pg.locator('#fw-l').fill('25')
    pg.locator('#fw-m').fill('120')
    if pg.locator('#fw-dur').input_value() in ('', '0'):
        pg.locator('#fw-dur').fill('40')
    slow_click(pg, pg.locator('#btn-fw-calc'), before=200, after=1200)
    shot(pg, 'temps-faiblesse.png', full=True)

    # Comptes / RH / Outils / Paramètres
    goto(pg, '/comptes/')
    shot(pg, 'comptes.png')
    goto(pg, '/gestion_rh/')
    shot(pg, 'rh.png', full=True)
    goto(pg, '/gestion_outils/')
    shot(pg, 'outils.png')
    goto(pg, '/parametres/')
    shot(pg, 'parametres.png')

    ctx.close()

    browser.close()
print('CAPTURES OK ->', OUT)
