"""Vidéos de démonstration du guide — de VRAIS parcours utilisateur, commentés.

Chaque flux rejoue, dans l'ordre, le pas-à-pas écrit dans la section
correspondante du guide (docs/guide.html) : ce que le texte explique,
la vidéo le montre.

RÈGLE D'ÉCRITURE DES BULLES — chaque vidéo raconte UN cas précis, nommé,
chiffré. Elle ne décrit pas l'interface : on ne dit pas « chaque onglet montre
une facette », on montre ce qu'on cherche et ce qu'on trouve. Concrètement :

  - la carte-titre pose la SITUATION (« Claire part en congés, qui reprend
    la cotation ? »), pas la fonctionnalité ;
  - chaque bulle nomme la donnée manipulée (l'activité, le collaborateur,
    la valeur saisie) plutôt que le widget cliqué ;
  - la bulle de conclusion donne le RÉSULTAT obtenu — un chiffre, un nom,
    une décision — et pas un résumé de ce qu'on vient de voir.

En plus du curseur visible et du halo de clic :

  - une CARTE-TITRE en ouverture (nom de la page, objectif du parcours) ;
  - un BANDEAU D'ÉTAPE en bas (Étape i/n — libellé, points de progression) ;
  - une BULLE D'EXPLICATION ancrée sur l'élément manipulé, à chaque étape ;
  - une BULLE DE CONCLUSION (✓) en fin de parcours.

Sortie : docs/assets/guide/flux-*.webm (session déjà ouverte, pas de login
à l'écran ; pop-up de bienvenue neutralisée ; CDN externes coupés pour un
rendu immédiat).
"""
import os
import shutil
from playwright.sync_api import sync_playwright

# Langue des vidéos : GUIDE_LANG=en produit le jeu anglais (interface de l'app
# ET bulles). Les fichiers sortent alors suffixés « -en ».
LANG = os.environ.get('GUIDE_LANG', 'fr')
SUFFIXE = '' if LANG == 'fr' else '-' + LANG


def T(fr, en):
    """Texte selon la langue du tournage."""
    return en if LANG == 'en' else fr


try:
    from traductions_videos import TRAD
except ImportError:                                   # table absente = tournage FR
    TRAD = {}

_manquants = []


def tx(texte):
    """Traduit un texte de bulle / carte-titre quand on tourne en anglais."""
    if LANG == 'fr' or not texte:
        return texte
    if texte in TRAD:
        return TRAD[texte]
    _manquants.append(texte)
    return texte

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(BASE, '..', '..', 'docs', 'assets', 'guide'))
STATE = os.path.join(BASE, 'auth_state.json')
URL = 'http://127.0.0.1:5601'

CURSOR_JS = open(os.path.join(BASE, 'capture_screens.py')).read().split('CURSOR_JS = """')[1].split('"""')[0]

# ── Surcouche pédagogique : carte-titre, bandeau d'étape, bulles ancrées ──────
OVERLAY_JS = r"""
(() => {
  const FONT = "'DM Sans',system-ui,-apple-system,'Segoe UI',sans-serif";
  function ensure() {
    if (document.getElementById('__ovl_css')) return;
    const st = document.createElement('style');
    st.id = '__ovl_css';
    st.textContent = `
      /* ── Halo : désigne l'élément dont parle la bulle ─────────────── */
      #__ovl_focus{position:fixed;z-index:2147483638;pointer-events:none;border-radius:14px;
        box-shadow:0 0 0 3px var(--ovl-a,#2563eb),0 0 0 9px color-mix(in srgb,var(--ovl-a,#2563eb) 22%,transparent),
                   0 18px 44px -14px color-mix(in srgb,var(--ovl-a,#2563eb) 60%,transparent);
        opacity:0;transform:scale(.97);
        transition:opacity .32s ease,transform .38s cubic-bezier(.2,.9,.3,1.2),
                   top .38s cubic-bezier(.2,.9,.3,1.2),left .38s cubic-bezier(.2,.9,.3,1.2),
                   width .38s ease,height .38s ease}
      #__ovl_focus.on{opacity:1;transform:scale(1)}

      /* ── Bulle d'explication ──────────────────────────────────────── */
      #__ovl_b{position:fixed;z-index:2147483640;pointer-events:none;font-family:${FONT}}
      #__ovl_b .bulle{max-width:404px;border-radius:18px;padding:15px 19px 15px 15px;
        background:linear-gradient(152deg,#111c30 0%,#0b1220 62%);
        color:#eef2f8;font-size:16.5px;line-height:1.52;font-weight:500;letter-spacing:-.002em;
        border:1px solid rgba(148,175,255,.16);
        box-shadow:0 2px 6px rgba(8,13,25,.34),0 26px 60px -18px rgba(8,13,25,.72),
                   inset 0 1px 0 rgba(255,255,255,.06);
        display:flex;gap:13px;align-items:flex-start;position:relative;
        opacity:0;transform:translateY(12px) scale(.965);
        transition:opacity .36s ease,transform .42s cubic-bezier(.2,.9,.28,1.16)}
      #__ovl_b.on .bulle{opacity:1;transform:translateY(0) scale(1)}
      #__ovl_b .num{flex:none;width:30px;height:30px;border-radius:10px;display:grid;place-items:center;
        background:linear-gradient(150deg,var(--ovl-a,#2563eb),color-mix(in srgb,var(--ovl-a,#2563eb) 62%,#000));
        color:#fff;font-weight:800;font-size:15px;margin-top:1px;
        box-shadow:0 3px 10px -2px color-mix(in srgb,var(--ovl-a,#2563eb) 75%,transparent),
                   inset 0 1px 0 rgba(255,255,255,.28)}
      #__ovl_b .num.ok{background:linear-gradient(150deg,#22c55e,#15803d);font-size:16px;
        box-shadow:0 3px 10px -2px rgba(34,197,94,.7),inset 0 1px 0 rgba(255,255,255,.3)}
      #__ovl_b .tail{position:absolute;width:15px;height:15px;background:#0d1626;transform:rotate(45deg);
        border:1px solid rgba(148,175,255,.16);border-top:none;border-left:none}
      #__ovl_b b{color:#fff;font-weight:750}

      /* ── Bandeau de progression ───────────────────────────────────── */
      #__ovl_banner{position:fixed;left:50%;bottom:22px;transform:translate(-50%,86px);z-index:2147483641;
        display:flex;align-items:center;gap:13px;padding:9px 20px 9px 10px;border-radius:999px;
        background:rgba(255,255,255,.9);backdrop-filter:blur(14px) saturate(1.35);
        border:1px solid rgba(15,23,42,.07);
        box-shadow:0 2px 5px rgba(15,23,42,.10),0 18px 44px -14px rgba(15,23,42,.5);
        font-family:${FONT};font-size:15px;font-weight:650;color:#0f172a;letter-spacing:-.002em;
        transition:transform .46s cubic-bezier(.2,.9,.28,1.14),opacity .3s;opacity:0;pointer-events:none}
      #__ovl_banner.on{transform:translate(-50%,0);opacity:1}
      #__ovl_banner .step{flex:none;display:grid;place-items:center;min-width:34px;height:34px;padding:0 9px;
        border-radius:999px;font-size:13px;font-weight:800;color:#fff;letter-spacing:.01em;
        background:linear-gradient(150deg,var(--ovl-a,#2563eb),color-mix(in srgb,var(--ovl-a,#2563eb) 62%,#000));
        box-shadow:0 3px 9px -2px color-mix(in srgb,var(--ovl-a,#2563eb) 70%,transparent)}
      #__ovl_banner .rail{flex:none;width:86px;height:5px;border-radius:99px;background:rgba(15,23,42,.10);
        overflow:hidden;margin-left:2px}
      #__ovl_banner .rail i{display:block;height:100%;border-radius:99px;width:0;
        background:linear-gradient(90deg,var(--ovl-a,#2563eb),color-mix(in srgb,var(--ovl-a,#2563eb) 55%,#fff));
        transition:width .5s cubic-bezier(.2,.9,.3,1)}

      /* ── Carte-titre d'ouverture ──────────────────────────────────── */
      #__ovl_title{position:fixed;inset:0;z-index:2147483645;display:grid;place-items:center;
        background:radial-gradient(1100px 620px at 50% 38%,
                     color-mix(in srgb,var(--ovl-a,#2563eb) 26%,#0b1220) 0%,
                     rgba(11,18,32,.975) 58%,rgba(8,13,24,.985) 100%);
        opacity:0;transition:opacity .55s ease;pointer-events:none;
        font-family:${FONT};text-align:center;color:#fff}
      #__ovl_title.on{opacity:1}
      #__ovl_title .in{transform:translateY(16px) scale(.985);
        transition:transform .62s cubic-bezier(.18,.82,.28,1)}
      #__ovl_title.on .in{transform:none}
      #__ovl_title .chip{display:inline-flex;align-items:center;gap:9px;margin-bottom:22px;
        padding:9px 20px;border-radius:999px;font-size:13px;font-weight:800;letter-spacing:.11em;
        text-transform:uppercase;color:#fff;
        background:linear-gradient(140deg,var(--ovl-a,#2563eb),color-mix(in srgb,var(--ovl-a,#2563eb) 58%,#000));
        box-shadow:0 6px 22px -6px color-mix(in srgb,var(--ovl-a,#2563eb) 85%,transparent),
                   inset 0 1px 0 rgba(255,255,255,.26)}
      #__ovl_title .t{font-size:41px;font-weight:800;letter-spacing:-.022em;line-height:1.1;
        text-shadow:0 2px 26px rgba(0,0,0,.35)}
      #__ovl_title .rule{width:64px;height:3px;border-radius:99px;margin:19px auto 0;
        background:linear-gradient(90deg,transparent,var(--ovl-a,#2563eb),transparent)}
      #__ovl_title .s{font-size:18.5px;color:#c9d7ee;margin-top:15px;font-weight:500;max-width:600px;
        line-height:1.5}
    `;
    document.documentElement.appendChild(st);
  }
  window.__ovlAccent = c => { ensure(); document.documentElement.style.setProperty('--ovl-a', c); };

  window.__ovlTitle = ([chip, t, s]) => {
    ensure();
    let d = document.getElementById('__ovl_title');
    if (!d) { d = document.createElement('div'); d.id = '__ovl_title'; document.body.appendChild(d); }
    d.innerHTML = `<div class="in"><div class="chip">${chip}</div><div class="t">${t}</div>` +
                  `<div class="rule"></div><div class="s">${s}</div></div>`;
    requestAnimationFrame(() => requestAnimationFrame(() => d.classList.add('on')));
  };
  window.__ovlTitleHide = () => {
    const d = document.getElementById('__ovl_title');
    if (d) { d.classList.remove('on'); setTimeout(() => d.remove(), 600); }
  };

  window.__ovlBanner = ([i, n, label]) => {
    ensure();
    let b = document.getElementById('__ovl_banner');
    if (!b) { b = document.createElement('div'); b.id = '__ovl_banner'; document.body.appendChild(b); }
    b.innerHTML = `<span class="step">${i}/${n}</span><span>${label}</span>` +
                  `<span class="rail"><i></i></span>`;
    const fill = b.querySelector('.rail i');
    requestAnimationFrame(() => {
      b.classList.add('on');
      requestAnimationFrame(() => { fill.style.width = Math.round(i / n * 100) + '%'; });
    });
  };
  window.__ovlBannerHide = () => {
    const b = document.getElementById('__ovl_banner');
    if (b) b.classList.remove('on');
  };

  // Halo autour de l'élément commenté — on regarde au bon endroit.
  window.__ovlFocus = ([x, y, w, h]) => {
    ensure();
    let f = document.getElementById('__ovl_focus');
    if (!f) { f = document.createElement('div'); f.id = '__ovl_focus'; document.body.appendChild(f); }
    const P = 6;
    f.style.left = (x - P) + 'px'; f.style.top = (y - P) + 'px';
    f.style.width = (w + P * 2) + 'px'; f.style.height = (h + P * 2) + 'px';
    requestAnimationFrame(() => f.classList.add('on'));
  };
  window.__ovlFocusHide = () => {
    const f = document.getElementById('__ovl_focus');
    if (f) f.classList.remove('on');
  };

  window.__ovlClear = () => {
    const w = document.getElementById('__ovl_b');
    if (w) { w.classList.remove('on'); setTimeout(() => w.remove(), 380); }
    window.__ovlFocusHide();
  };

  // Bulle ancrée sur (x,y) — place = côté de la CIBLE où poser la bulle
  window.__ovlBulle = ([html, x, y, place, num, ok]) => {
    ensure();
    const old = document.getElementById('__ovl_b'); if (old) old.remove();
    const w = document.createElement('div'); w.id = '__ovl_b';
    const chip = num ? `<span class="num${ok ? ' ok' : ''}">${ok ? '✓' : num}</span>` : '';
    w.innerHTML = `<div class="bulle">${chip}<span>${html}</span></div><div class="tail"></div>`;
    document.body.appendChild(w);
    const b = w.firstChild, tail = w.lastChild;
    const bw = b.offsetWidth, bh = b.offsetHeight, vw = innerWidth, vh = innerHeight, G = 18;
    let left, top;
    if (place === 'center') {
      left = (vw - bw) / 2; top = (vh - bh) / 2; tail.style.display = 'none';
    } else if (place === 'top') { left = x - bw / 2; top = y - bh - G; }
    else if (place === 'bottom') { left = x - bw / 2; top = y + G; }
    else if (place === 'left') { left = x - bw - G; top = y - bh / 2; }
    else { left = x + G; top = y - bh / 2; }
    left = Math.max(12, Math.min(left, vw - bw - 12));
    top = Math.max(12, Math.min(top, vh - bh - 12));
    w.style.left = left + 'px'; w.style.top = top + 'px';
    const T = 'transform:rotate(45deg);';
    if (place === 'top') tail.style.cssText += `left:${Math.max(14, Math.min(x - left - 7, bw - 28))}px;bottom:-6px;`;
    else if (place === 'bottom') tail.style.cssText += `left:${Math.max(14, Math.min(x - left - 7, bw - 28))}px;top:-6px;${T}rotate:180deg;`;
    else if (place === 'left') tail.style.cssText += `top:${Math.max(14, Math.min(y - top - 7, bh - 28))}px;right:-6px;`;
    else if (place === 'right') tail.style.cssText += `top:${Math.max(14, Math.min(y - top - 7, bh - 28))}px;left:-6px;`;
    requestAnimationFrame(() => requestAnimationFrame(() => w.classList.add('on')));
  };
})();
"""


def _settle(pg, locator, tries=2):
    """Amène l'élément à l'écran ; tolère un DOM qui vient d'être re-rendu."""
    for k in range(tries):
        try:
            locator.scroll_into_view_if_needed()
            return True
        except Exception:
            pg.wait_for_timeout(700)
    return False


def slow_click(pg, locator, before=500, after=1100):
    _settle(pg, locator)
    try:
        box = locator.bounding_box()
    except Exception:
        box = None
    if box:
        pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, steps=26)
    pg.wait_for_timeout(before)
    locator.click()          # auto-wait de Playwright : re-résout si besoin
    pg.wait_for_timeout(after)


def type_slow(pg, locator, text, clear=False, delay=70):
    slow_click(pg, locator, after=250)
    if clear:
        locator.fill('')
    pg.keyboard.type(text, delay=delay)
    pg.wait_for_timeout(400)


# ── Aides « surcouche » ───────────────────────────────────────────────────────

def banner(pg, i, n, label):
    pg.evaluate("window.__ovlBanner", [i, n, label])


def bulle(pg, text, locator=None, place='top', num=None, hold=2100, dx=0, dy=0, ok=False):
    """Affiche une bulle ancrée sur `locator` (côté `place`), la laisse `hold` ms."""
    x = y = None
    if locator is not None:
        try:
            _settle(pg, locator)
            pg.wait_for_timeout(250)
            box = locator.bounding_box()
            if box:
                if place == 'top':
                    x, y = box['x'] + box['width'] / 2, box['y']
                elif place == 'bottom':
                    x, y = box['x'] + box['width'] / 2, box['y'] + box['height']
                elif place == 'left':
                    x, y = box['x'], box['y'] + box['height'] / 2
                else:
                    x, y = box['x'] + box['width'], box['y'] + box['height'] / 2
            # halo : on désigne l'élément dont parle la bulle
            if box and place != 'center':
                pg.evaluate("window.__ovlFocus",
                            [box['x'], box['y'], box['width'], box['height']])
        except Exception:
            pass
    if x is None:
        x, y, place = 640, 420, 'center'
    pg.evaluate("window.__ovlBulle", [tx(text), x + dx, y + dy, place, num, ok])
    pg.wait_for_timeout(hold)


def clear_bulle(pg):
    try:
        pg.evaluate("window.__ovlClear()")
    except Exception:
        pass
    pg.wait_for_timeout(300)


def step(pg, i, n, label, text, locator=None, place='top', hold=2100, dx=0, dy=0):
    """Bandeau d'étape + bulle d'explication, puis efface la bulle (le bandeau reste)."""
    banner(pg, i, n, label)
    bulle(pg, text, locator, place, num=i, hold=hold, dx=dx, dy=dy)
    clear_bulle(pg)


def done(pg, text, hold=2300):
    """Bulle de conclusion (✓ verte) au centre, bandeau masqué."""
    try:
        pg.evaluate("window.__ovlBannerHide()")
    except Exception:
        pass
    bulle(pg, text, None, 'center', num='✓', hold=hold, ok=True)
    clear_bulle(pg)


# Chromium : CHROME_PATH si fourni, sinon celui installé par
# « playwright install chromium ». Le chemin /opt/pw-browsers de l'env web
# n'existe pas sur un poste de dev.
_LAUNCH = {"executable_path": os.environ["CHROME_PATH"]} if os.environ.get("CHROME_PATH") else {}

with sync_playwright() as p:
    browser = p.chromium.launch(**_LAUNCH)

    # Session une fois pour toutes (le login n'apparaît pas dans les vidéos)
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(URL + '/login')
    pg.fill('input[name="email"]', 'demo@afdec.fr')
    pg.fill('input[name="password"]', 'Visual123!')
    pg.click('button[type="submit"], input[type="submit"]')
    pg.wait_for_load_state('networkidle')
    # Langue de l app pour ce tournage (GUIDE_LANG).
    pg.request.post(URL + '/parametres/set_language', data={'lang': LANG})
    pg.wait_for_timeout(300)
    ctx.storage_state(path=STATE)
    ctx.close()

    # ONLY=flux-carto.webm → ne re-tourne que cette vidéo (mise au point d'un
    # parcours sans repasser les huit).
    ONLY = {n for n in (os.environ.get('ONLY') or '').split(',') if n.strip()}

    def video(name, flow, start, accent, chip, titre, sous_titre):
        if ONLY and name not in ONLY:
            return
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800},
                                  storage_state=STATE,
                                  record_video_dir=OUT,
                                  record_video_size={'width': 1280, 'height': 800})
        ctx.add_init_script(CURSOR_JS)
        ctx.add_init_script(OVERLAY_JS)
        ctx.add_init_script(f"window.addEventListener('DOMContentLoaded',()=>__ovlAccent('{accent}'));")
        ctx.add_init_script("sessionStorage.setItem('optiq_welcome_seen_v4','1');")
        for pat in ['**://fonts.googleapis.com/**', '**://fonts.gstatic.com/**',
                    '**://cdnjs.cloudflare.com/**', '**://cdn.jsdelivr.net/**']:
            ctx.route(pat, lambda r: r.abort())
        pg = ctx.new_page()
        # Sans plafond, un sélecteur qui ne matche pas fait attendre 30 s — et un
        # tournage entier peut y passer une heure sans rien dire.
        pg.set_default_timeout(8000)
        pg.goto(URL + start, wait_until='domcontentloaded')
        pg.wait_for_timeout(1400)
        # Carte-titre d'ouverture (sert aussi de poster à la vidéo)
        pg.evaluate("window.__ovlTitle", [tx(chip), tx(titre), tx(sous_titre)])
        pg.wait_for_timeout(2400)
        pg.evaluate("window.__ovlTitleHide()")
        pg.wait_for_timeout(650)
        try:
            flow(pg)
        except Exception as e:
            print('FLOW ERROR', name, e)
        pg.wait_for_timeout(900)
        path = pg.video.path()
        ctx.close()
        cible = name.replace('.webm', SUFFIXE + '.webm')
        shutil.move(path, os.path.join(OUT, cible))
        print('video', cible)

    # ── Cartographie ────────────────────────────────────────────────────────
    # Cas suivi : « un client demande un prix — par où ça passe chez nous ? »
    def flow_carto(pg):
        N = 3
        cv = pg.locator('svg').first
        box = cv.bounding_box()
        if box:
            cx, cy = box['x'] + box['width'] * 0.5, box['y'] + box['height'] * 0.4
            step(pg, 1, N, T('Suivre le flux', 'Follow the flow'),
                 "On cherche le trajet d'une <b>demande de prix</b>. On fait glisser la carte "
                 "vers la gauche pour remonter au début du flux.",
                 cv, 'bottom', dy=-260)
            pg.mouse.move(cx, cy, steps=22)
            pg.wait_for_timeout(400)
            pg.mouse.down()
            pg.mouse.move(cx - 160, cy - 60, steps=30)
            pg.mouse.up()
            pg.wait_for_timeout(600)
            step(pg, 2, N, T('Lire les enchaînements', 'Read the chain'),
                 "On zoome pour lire les <b>flèches</b> : chacune est une donnée qui passe d'une "
                 "activité à la suivante. C'est ça, le flux réel.",
                 cv, 'bottom', dy=-260)
            for _ in range(4):
                pg.mouse.wheel(0, -240)
                pg.wait_for_timeout(420)
            pg.wait_for_timeout(500)
        # 3. l'activité qui nous intéresse → sa fiche
        item = pg.locator('text=' + T('Analyse de faisabilité', 'Feasibility analysis')).last
        if item.count():
            step(pg, 3, N, T('Ouvrir le maillon', 'Open the link'),
                 "L'étape qui nous intéresse est <b>Analyse de faisabilité</b>. Un clic dessus "
                 "pour savoir qui la tient et ce qu'elle produit.",
                 item, 'left')
            slow_click(pg, item, after=2000)
            done(pg, "En trois gestes on est passé d'une carte muette à <b>la fiche d'Analyse de "
                     "faisabilité</b> : ses tâches, ses données d'entrée et de sortie, ses compétences.")

    # ── Activités ───────────────────────────────────────────────────────────
    # Cas suivi : « Claire part en congés — que faut-il savoir faire pour
    # reprendre la cotation ? »
    def flow_activite(pg):
        N = 3
        s = pg.locator('.activity-search-input')
        step(pg, 1, N, T("Retrouver l'activité", 'Find the activity'),
             "La question du jour : <b>que faut-il maîtriser pour reprendre la cotation&nbsp;?</b> "
             "On tape « cotation », la liste se réduit à l'activité concernée.", s, 'bottom')
        type_slow(pg, s, T('cotation', 'pricing'), delay=130)
        pg.wait_for_timeout(700)
        hdr = pg.locator('.activity-container:visible .activity-header').first
        step(pg, 2, N, T('Ouvrir sa fiche', 'Open its record'),
             "Un clic sur la barre violette déplie la fiche&nbsp;: on y voit d'abord les "
             "<b>tâches</b> et les <b>données</b> que la cotation consomme et produit.", hdr, 'bottom')
        slow_click(pg, hdr, after=1400)
        ONGLETS = [T('Compétences', 'Competencies'),
                   T('Savoirs', 'Knowledge'),
                   T('Temps', 'Time')]
        libelles = {
            ONGLETS[0]: "Onglet <b>Compétences</b>&nbsp;: le résultat attendu, formulé comme on "
                           "l'évaluera — « produire une cotation conforme du premier coup ».",
            ONGLETS[1]:    "Onglet <b>Savoirs</b>&nbsp;: ce qu'il faut connaître pour y arriver — ici "
                           "le processus qualité ISO 9001 du site.",
            ONGLETS[2]:    "Onglet <b>Temps</b>&nbsp;: la durée de chaque tâche. C'est ce qui alimentera "
                           "le chiffrage dans la page Temps.",
        }
        i = 3
        for label in ONGLETS:
            t = pg.locator('.tab-button:visible', has_text=label).first
            if t.count():
                bulle(pg, libelles[label], t, 'bottom', num=i if label == ONGLETS[0] else None,
                      hold=2000)
                if label == ONGLETS[0]:
                    banner(pg, 3, N, T('Lire ce qu\'il faut savoir faire', 'Read what must be mastered'))
                clear_bulle(pg)
                slow_click(pg, t, after=1200)
        done(pg, "Réponse en trois clics&nbsp;: pour reprendre la cotation il faut <b>ce résultat</b>, "
                 "<b>ces savoirs</b> et compter <b>ce temps-là</b>. Rien à aller chercher ailleurs.")

    # ── Rôles : rechercher, déplier, éditer la mission, parcourir 2 volets ──
    def flow_role(pg):
        N = 4
        s = pg.locator('#roleSearchInput')
        step(pg, 1, N, T('Trouver le rôle', 'Find the role'),
             "On prépare l'entretien annuel de <b>Relation client</b>&nbsp;: il faut sa fiche de "
             "poste à jour. On tape son nom.", s, 'bottom')
        type_slow(pg, s, T('relation', 'customer'), delay=120)
        pg.wait_for_timeout(600)
        hdr = pg.locator('.role-container:visible .role-header').first
        step(pg, 2, N, T('Lire la fiche', 'Read the record'),
             "La fiche est déjà remplie&nbsp;: elle hérite des <b>activités</b> que ce rôle garantit "
             "dans la carte. Personne ne l'a saisie à la main.", hdr, 'bottom')
        slow_click(pg, hdr, after=1200)
        # Mission générale : compléter puis Enregistrer
        ta = pg.locator('.role-container:visible .mission-area').first
        if ta.count():
            step(pg, 3, N, T('Ajouter un engagement', 'Add a commitment'),
                 "Seule la <b>mission</b> se rédige à la main. On y ajoute l'engagement pris cette "
                 "année&nbsp;: répondre au client sous 48&nbsp;h.", ta, 'top')
            slow_click(pg, ta, after=250)
            pg.keyboard.press('End')
            pg.keyboard.type(' Répondre au client sous 48 h.', delay=50)
            pg.wait_for_timeout(350)
            save = pg.locator('.role-container:visible .mission-footer .btn-primary').first
            if save.count():
                slow_click(pg, save, after=1300)
        first = True
        for txt in [T('Garant', 'Guarantor'), T('Savoir', 'Knowledge')]:
            b = pg.locator('.role-container:visible .block-header', has_text=txt).first
            if b.count():
                if first:
                    step(pg, 4, N, T('Vérifier le contenu', 'Check the content'),
                         "<b>Activités garanties</b> puis <b>Savoirs</b>&nbsp;: c'est le contenu réel du "
                         "poste, celui dont on parlera en entretien.", b, 'top')
                    first = False
                slow_click(pg, b, after=1500)
        done(pg, "La fiche de poste de Relation client est prête pour l'entretien&nbsp;: elle a suivi "
                 "la carte toute l'année, on n'a eu qu'<b>une phrase à écrire</b>.")

    # ── Compétences : collaborateur → rôles → ouvrir l'évaluation ───────────
    def flow_competences(pg):
        N = 3
        li = pg.locator('.cv2-collab li').first
        if li.count():
            step(pg, 1, N, T('Ouvrir le collaborateur', 'Open the team member'),
                 "Entretien de <b>Claire Dupont</b>&nbsp;: on veut savoir où elle en est, résultat par "
                 "résultat, avant d'en parler avec elle.", li, 'right')
            slow_click(pg, li, after=1900)
        pills = pg.locator('.cv2-role')
        if pills.count() > 1:
            step(pg, 2, N, T('Se placer sur un rôle', 'Work inside a role'),
                 "Claire tient <b>plusieurs rôles</b>. On évalue toujours dans un rôle donné&nbsp;: "
                 "les attendus ne sont pas les mêmes.", pills.nth(1), 'bottom')
            slow_click(pg, pills.nth(1), after=1700)
            slow_click(pg, pills.first, after=1700)
        ev = pg.locator('.cv2-tab button', has_text=T('Évaluer', 'Evaluate')).first
        if ev.count():
            step(pg, 3, N, T("Évaluer sur le résultat", 'Assess on the result'),
                 "On ne note pas « Claire, 3/5 »&nbsp;: on se prononce sur <b>chaque résultat qu'elle "
                 "produit</b>, de 0 à 4.", ev, 'left')
            slow_click(pg, ev, after=2400)
            done(pg, "Un seul résultat à 1 tire le niveau du rôle à 1&nbsp;: le global est le "
                     "<b>minimum</b>, jamais une moyenne. C'est ce qui rend l'écart actionnable — "
                     "on sait exactement quoi travailler.")

    # ── Temps / Projet : nommer, remplir, ajouter une ligne, enregistrer ────
    def flow_projet(pg):
        N = 4
        nom = pg.locator('#project-name')
        step(pg, 1, N, T('Poser la question', 'Ask the question'),
             "La direction demande&nbsp;: <b>combien coûte notre présence au salon&nbsp;?</b> "
             "On assemble les activités qu'il faudra mobiliser.", nom, 'bottom')
        type_slow(pg, nom, 'Salon professionnel 2026', delay=50)
        row = pg.locator('#project-rows tr').first
        step(pg, 2, N, T('Chiffrer la 1re activité', 'Cost the 1st activity'),
             "Première activité&nbsp;: <b>2&nbsp;h</b> de travail, <b>1&nbsp;jour</b> d'attente avant "
             "la suite, <b>2&nbsp;personnes</b>. Le délai n'est pas du travail — il ne coûte rien.",
             row, 'bottom')
        type_slow(pg, row.locator('.cell-dur'), '2', clear=True, delay=110)
        row.locator('.cell-du select').select_option(label=T('heures', 'hours'))
        pg.wait_for_timeout(450)
        type_slow(pg, row.locator('.cell-del'), '1', clear=True, delay=110)
        row.locator('.cell-deu select').select_option(label=T('jours', 'days'))
        pg.wait_for_timeout(450)
        type_slow(pg, row.locator('.cell-nbp'), '2', clear=True, delay=110)
        add = pg.locator('#btn-add-line')
        step(pg, 3, N, T('Ajouter la suivante', 'Add the next one'),
             "Le salon mobilise une <b>seconde activité</b>&nbsp;: on l'ajoute et on la chiffre à "
             "<b>4&nbsp;h</b>.", add, 'top')
        slow_click(pg, add, after=800)
        row2 = pg.locator('#project-rows tr').nth(1)
        row2.locator('.cell-act select').select_option(index=3)
        pg.wait_for_timeout(350)
        type_slow(pg, row2.locator('.cell-dur'), '4', clear=True, delay=110)
        row2.locator('.cell-du select').select_option(label=T('heures', 'hours'))
        pg.wait_for_timeout(600)
        kpis = pg.locator('.kpis').first
        kpis.scroll_into_view_if_needed()
        step(pg, 4, N, T('Lire la réponse', 'Read the answer'),
             "La <b>charge globale</b> s'affiche&nbsp;: c'est le nombre d'heures de travail réellement "
             "engagées. Voilà le chiffre à donner à la direction.", kpis, 'top', hold=2600)
        slow_click(pg, pg.locator('#btn-save-project'), after=1800)
        done(pg, "Le projet est enregistré&nbsp;: l'an prochain on repart de ce chiffrage au lieu "
                 "de <b>réestimer au doigt mouillé</b>.")

    # ── Temps / Faiblesse : saisie complète puis calcul ─────────────────────
    def flow_faiblesse(pg):
        N = 4
        slow_click(pg, pg.locator('.subtab[data-subtab="faiblesse"]'), after=900)
        k = pg.locator('#fw-k')
        step(pg, 1, N, T("Nommer l'irritant", 'Name the irritant'),
             "Tout le monde s'en plaint sans jamais le chiffrer&nbsp;: <b>les données client arrivent "
             "incomplètes</b> et il faut relancer. On va le mettre en euros.", k, 'bottom')
        type_slow(pg, k, 'Données client incomplètes', delay=50)
        n_ = pg.locator('#fw-n')
        step(pg, 2, N, T('À quelle fréquence', 'How often'),
             "L'équipe l'estime à <b>un dossier sur quatre</b>. Pas besoin de mesure exacte&nbsp;: "
             "un ordre de grandeur partagé suffit.", n_, 'bottom')
        f = n_; f.click(); f.fill(''); pg.keyboard.type('4', delay=130)
        step(pg, 3, N, T("Ce que ça coûte à chaque fois", 'What it costs each time'),
             "Quand ça arrive&nbsp;: <b>25&nbsp;min</b> de travail en plus pour relancer, et "
             "<b>120&nbsp;min</b> d'attente avant la réponse du client.", pg.locator('#fw-l'), 'bottom')
        f = pg.locator('#fw-l'); f.click(); pg.keyboard.type('25', delay=130)
        f = pg.locator('#fw-m'); f.click(); pg.keyboard.type('120', delay=130)
        if pg.locator('#fw-dur').input_value() in ('', '0'):
            f = pg.locator('#fw-dur'); f.click(); f.fill(''); pg.keyboard.type('40', delay=120)
        calc = pg.locator('#btn-fw-calc')
        step(pg, 4, N, T('Obtenir le montant', 'Get the amount'),
             "Trois estimations, un clic&nbsp;: l'application croise fréquence, temps perdu et volume "
             "annuel.", calc, 'top')
        slow_click(pg, calc, after=1300)
        res = pg.locator('#fw-results-section')
        res.scroll_into_view_if_needed()
        pg.wait_for_timeout(800)
        bulle(pg, "Le <b>coût annuel</b> en rouge, c'est l'irritant traduit en euros. On ne dit plus "
                  "« ça nous fait perdre du temps »&nbsp;: on dit combien, et l'arbitrage se fait tout seul.",
              res, 'top', num='✓', hold=3000, ok=True)
        clear_bulle(pg)

    # ── Rôles : exporter (périmètre + format) ───────────────────────────────
    def flow_export(pg):
        N = 3
        btn = pg.locator('#btn-export-roles')
        step(pg, 1, N, T("Sortir la fiche", 'Pull the record'),
             "Le RH demande la fiche de poste d'<b>un</b> rôle pour un recrutement. On part de "
             "<b>Exporter</b>, en haut à droite.", btn, 'bottom')
        slow_click(pg, btn, after=1300)
        sel = pg.locator('#exportRoleSelect')
        if sel.count():
            step(pg, 2, N, T('Un seul rôle', 'One role only'),
                 "On ne sort pas toute l'entité&nbsp;: on choisit <b>le rôle concerné</b>. L'export "
                 "ne contiendra que lui.", sel, 'bottom')
            sel.select_option(index=1)
            pg.wait_for_timeout(800)
        html_card = pg.locator('#fmt-html-card')
        step(pg, 3, N, T('Le bon format', 'The right format'),
             "<b>HTML</b> pour l'envoyer tel quel ou l'imprimer&nbsp;; <b>Excel</b> si le RH doit "
             "retravailler le contenu.", html_card, 'top')
        slow_click(pg, html_card, after=1100)
        slow_click(pg, pg.locator('#fmt-excel-card'), after=1100)
        done(pg, "Fiche de poste prête à envoyer, tirée de la carte&nbsp;: elle dit ce que le poste "
                 "<b>fait vraiment</b>, pas ce qu'on avait écrit il y a trois ans.")
        slow_click(pg, pg.locator('#exportModalCancel'), after=500)

    # ── Partage d'entité ────────────────────────────────────────────────────
    # Cas suivi : « la carte est prête, il faut que l'équipe l'ait aussi »
    def flow_partage(pg):
        N = 4
        ouvrir = pg.locator('#carto-wizard-btn')
        step(pg, 1, N, T('Ouvrir la gestion', 'Open the manager'),
             "La carte du site est finie et corrigée. Il faut maintenant que <b>l'équipe l'ait "
             "aussi</b>, sans la refaire. On ouvre la gestion des entités.", ouvrir, 'bottom')
        slow_click(pg, ouvrir, after=1200)
        carte = pg.locator('.entity-grid-item').first
        if carte.count():
            step(pg, 2, N, T("Choisir l'entité", 'Pick the entity'),
                 "On sélectionne l'entité à transmettre — ici <b>AFDEC Industrie</b>, celle qui "
                 "porte la carte qu'on vient de terminer.", carte, 'right')
            slow_click(pg, carte, after=1100)
        partager = pg.locator('#wizard-share-btn')
        if not partager.count():
            return  # bouton réservé aux administrateurs
        step(pg, 3, N, T('Choisir les destinataires', 'Pick the recipients'),
             "<b>Partager</b> n'apparaît que pour les administrateurs. On coche les collègues qui "
             "doivent travailler sur cette carte.", partager, 'top')
        slow_click(pg, partager, after=1500)
        cases = pg.locator('.share-user-cb')
        n = cases.count()
        for k in range(min(2, n)):
            slow_click(pg, cases.nth(k), after=650)
        valider = pg.locator('#share-confirm-btn')
        step(pg, 4, N, T('Déposer la copie', 'Drop the copy'),
             "Chacun reçoit <b>sa propre copie</b> de l'entité&nbsp;: il pourra la modifier sans "
             "toucher à l'originale.", valider, 'top')
        slow_click(pg, valider, after=2600)
        done(pg, "C'est fait&nbsp;: la carte, ses activités et ses rôles sont <b>déjà dans leur "
                 "compte</b>. Personne n'a eu à réimporter le fichier Visio.")

    # La carte-titre pose la SITUATION : le spectateur doit savoir, avant que
    # la première bulle apparaisse, quelle question la vidéo va résoudre.
    video('flux-carto.webm', flow_carto, '/activities/map', '#0d9488',
          'Cartographie', 'Un client demande un prix',
          'Par où passe la demande chez nous, et qui fait quoi ?')
    video('flux-activite.webm', flow_activite, '/activities/view', '#7c3aed',
          'Activités', 'Claire part en congés',
          'Que faut-il savoir faire pour reprendre la cotation ?')
    video('flux-role.webm', flow_role, '/roles_view/', '#059669',
          'Rôles', "Préparer un entretien annuel",
          'La fiche de poste de Relation client est-elle à jour ?')
    video('flux-competences.webm', flow_competences, '/competences/view', '#2563eb',
          'Compétences', 'Où en est Claire Dupont ?',
          "S'évaluer sur des résultats produits, pas sur une note globale")
    video('flux-projet.webm', flow_projet, '/temps/', '#d97706',
          'Temps · Projet', 'Combien coûte le salon ?',
          'Assembler les activités mobilisées et lire la charge réelle')
    video('flux-faiblesse.webm', flow_faiblesse, '/temps/', '#d97706',
          'Temps · Faiblesse', 'Des données client incomplètes',
          "Mettre un montant annuel sur un irritant que tout le monde subit")
    video('flux-export.webm', flow_export, '/roles_view/', '#059669',
          'Rôles · Export', 'Le RH demande une fiche de poste',
          'Sortir un seul rôle, au bon format, en trois clics')
    video('flux-partage.webm', flow_partage, '/activities/map', '#0d9488',
          'Cartographie · Partage', "L'équipe doit avoir la même carte",
          'Déposer une copie de son entité chez ses collègues')
    browser.close()

if _manquants:
    print('\n!! ' + str(len(set(_manquants))) + ' texte(s) sans traduction anglaise :')
    for t in sorted(set(_manquants)):
        print('   ' + t[:110])
print('VIDEOS OK (' + LANG + ')')
