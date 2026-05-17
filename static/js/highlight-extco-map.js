'use strict';

/* ══════════════════════════════════════════════════
   Activities Map — Mode "mise en évidence des activités externes"
   ──────────────────────────────────────────────────
   Toggle qui passe l'ensemble du SVG (bandes, formes, connecteurs, textes)
   en gris à l'exception des activités dont l'id figure dans
   `window.EXTCO_ACTIVITY_IDS` (rempli côté serveur depuis le JSON
   OptiqCarto : subtype ∈ {extco, external}).

   Approche : JS-driven, on parcourt chaque élément peint du SVG et on
   override `fill` / `stroke` via inline-style (priorité CSS la plus haute,
   bat à la fois les attributs présentationnels et les règles CSS). On
   sauvegarde l'attribut ET l'inline-style d'origine pour pouvoir restaurer
   exactement. Indispensable pour les SVG Visio qui utilisent souvent
   `style="fill:..."` plutôt que `fill="..."`.

   On évite volontairement les `filter: grayscale(...)` appliqués sur des
   parents : le pipeline SVG les hérite dans tout le sous-arbre, ce qui
   empêcherait les `.extco-keep` de ressortir.
   ══════════════════════════════════════════════════ */

let _extcoMapActive = false;

const DIM_FILL   = '#cbd5e1'; // gris bleuté clair (formes)
const DIM_STROKE = '#94a3b8'; // gris bleuté foncé (contours, connecteurs)
const DIM_TEXT   = '#94a3b8'; // gris pour les labels

const _SKIP_TAGS = new Set([
  'defs','pattern','lineargradient','radialgradient','stop','marker',
  'clippath','mask','filter','desc','title','metadata','style','script',
]);
const _TEXT_TAGS = new Set(['text','tspan','textpath']);

function isExtcoMapHighlightActive() {
  return _extcoMapActive;
}

function extcoMapCount() {
  return (window.EXTCO_ACTIVITY_IDS || []).length;
}

function _isInside(node, roots) {
  for (const r of roots) if (r === node || r.contains(node)) return true;
  return false;
}

// "fill" → { dsAttr: "extcoFillAttr", dsStyle: "extcoFillStyle" }
function _dsKeys(prop) {
  const P = prop[0].toUpperCase() + prop.slice(1);
  return { dsAttr: 'extco' + P + 'Attr', dsStyle: 'extco' + P + 'Style' };
}

function _hasVisibleColor(v) {
  if (!v) return false;
  const s = String(v).trim().toLowerCase();
  return s !== '' && s !== 'none' && s !== 'transparent' && s !== 'rgba(0, 0, 0, 0)' && s !== 'rgba(0,0,0,0)';
}

// Repeint un élément (attr présentationnel + inline-style) en couleur gris.
// Retourne true si une modification a eu lieu.
function _saveAndDim(el, dimColor, prop) {
  const { dsAttr, dsStyle } = _dsKeys(prop);
  if (dsAttr in el.dataset || dsStyle in el.dataset) return false;

  const attrVal   = el.getAttribute(prop);
  const inlineVal = el.style ? el.style[prop] : '';
  let computedVal = '';
  try { computedVal = window.getComputedStyle(el)[prop] || ''; } catch (_) {}

  const visible = _hasVisibleColor(attrVal) || _hasVisibleColor(inlineVal) || _hasVisibleColor(computedVal);
  if (!visible) return false;

  el.dataset[dsAttr]  = attrVal === null ? '__NULL__'  : attrVal;
  el.dataset[dsStyle] = inlineVal       ? inlineVal    : '__EMPTY__';
  // Inline-style l'emporte sur attribut et règle CSS — toujours efficace.
  if (el.style) el.style[prop] = dimColor;
  return true;
}

function _restoreProp(el, prop) {
  const { dsAttr, dsStyle } = _dsKeys(prop);
  if (dsStyle in el.dataset) {
    const orig = el.dataset[dsStyle];
    if (el.style) el.style[prop] = (orig === '__EMPTY__') ? '' : orig;
    delete el.dataset[dsStyle];
  }
  if (dsAttr in el.dataset) {
    const orig = el.dataset[dsAttr];
    if (orig === '__NULL__') el.removeAttribute(prop);
    else                     el.setAttribute(prop, orig);
    delete el.dataset[dsAttr];
  }
}

function applyExtcoMapHighlight(svgRoot) {
  if (!svgRoot) return;
  const extcoIds = new Set((window.EXTCO_ACTIVITY_IDS || []).map(v => String(v)));

  // 1. Repère les activités à garder en couleur
  const keepRoots = [];
  svgRoot.querySelectorAll('.carto-activity').forEach(el => {
    const aid = String(el.dataset.activityId || '');
    if (extcoIds.has(aid)) {
      keepRoots.push(el);
      el.classList.add('extco-keep');
    }
  });

  // 2. Grise tout le reste
  let dimmed = 0;
  svgRoot.querySelectorAll('*').forEach(el => {
    if (_isInside(el, keepRoots)) return;
    const tn = (el.tagName || '').toLowerCase();
    if (_SKIP_TAGS.has(tn)) return;
    const dimFill = _TEXT_TAGS.has(tn) ? DIM_TEXT : DIM_FILL;
    if (_saveAndDim(el, dimFill,   'fill'))   dimmed++;
    if (_saveAndDim(el, DIM_STROKE, 'stroke')) dimmed++;
  });

  console.debug('[extco-map] dimmed', dimmed, 'props on', svgRoot.querySelectorAll('*').length, 'elements — kept', keepRoots.length, 'activities');

  // 3. Halo rose autour des activités conservées (filtre sur l'élément
  //    directement → pas d'héritage qui regrise les enfants).
  keepRoots.forEach(el => {
    el.dataset.extcoOrigFilter = el.style.filter || '';
    el.style.filter = 'drop-shadow(0 0 6px rgba(236, 72, 153, 0.85)) drop-shadow(0 0 14px rgba(236, 72, 153, 0.45))';
  });

  svgRoot.classList.add('extco-highlight-active');
  _extcoMapActive = true;
}

function clearExtcoMapHighlight(svgRoot) {
  if (!svgRoot) return;

  svgRoot.querySelectorAll('*').forEach(el => {
    _restoreProp(el, 'fill');
    _restoreProp(el, 'stroke');
  });
  svgRoot.querySelectorAll('.extco-keep').forEach(el => {
    if ('extcoOrigFilter' in el.dataset) {
      el.style.filter = el.dataset.extcoOrigFilter;
      delete el.dataset.extcoOrigFilter;
    }
    el.classList.remove('extco-keep');
  });

  svgRoot.classList.remove('extco-highlight-active');
  _extcoMapActive = false;
}

function toggleExtcoMapHighlight(svgRoot) {
  if (_extcoMapActive) clearExtcoMapHighlight(svgRoot);
  else                 applyExtcoMapHighlight(svgRoot);
  return _extcoMapActive;
}
