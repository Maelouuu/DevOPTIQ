/*
 * drive.mjs — pilote Chromium (Playwright) sur harness.html, imprime les métriques
 * (croisements, etc.) et enregistre une capture du SVG rendu.
 *
 * Prérequis :
 *   1) servir la racine du repo en HTTP :  python3 -m http.server 8099
 *   2) Playwright + Chromium disponibles (déjà installés dans l'env web).
 *
 * Usage :
 *   node drive.mjs [urlQuery] [out.png]
 *   node drive.mjs ""                         # hard.vsdx, agencement auto, vue globale
 *   node drive.mjs "?declutter=0"             # sans aération (comparaison)
 *   node drive.mjs "?route=0"    raw.png      # positions Visio brutes
 *   node drive.mjs "?cx=8089&cy=94&zw=1500&zh=1150" group.png   # zoom région
 *
 * Paramètres d'URL (harness.html) :
 *   vsdx=/Code/xxx.vsdx   carto à charger (défaut /Code/hard.vsdx — la référence)
 *   declutter=0           désactive align+declutter
 *   route=0               n'exécute pas l'agencement auto (positions brutes)
 *   cx,cy,zw,zh           zoom sur une région (coordonnées carto)
 */
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
// Playwright est installé en global dans l'env web ; adapte le chemin si besoin.
const PW = process.env.PLAYWRIGHT_PATH || '/opt/node22/lib/node_modules/playwright';
const { chromium } = require(PW);

const BASE = process.env.HARNESS_BASE || 'http://localhost:8099';
const CHROME = process.env.CHROME_PATH || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

const query = process.argv[2] || '';
const shot  = process.argv[3] || '';
const url = `${BASE}/tests/carto/harness.html${query}`;

const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox', '--disable-gpu'] });
const page = await browser.newPage({ viewport: { width: 1750, height: 1300 } });
const errs = [];
page.on('pageerror', e => errs.push(e.message));
try {
  await page.goto(url, { waitUntil: 'load', timeout: 30000 });
  await page.waitForFunction('document.title === "DONE"', { timeout: 120000 });
  const R = await page.evaluate(() => window.__R__);
  console.log(JSON.stringify(R, null, 2));
  if (shot) { const cv = await page.$('#canvas'); if (cv) await cv.screenshot({ path: shot }); console.error('SHOT ' + shot); }
} catch (e) {
  console.error('DRIVE ERROR ' + (e.stack || e));
  console.error(errs.slice(0, 5).join('\n'));
} finally {
  await browser.close();
}
