'use strict';

/* ══════════════════════════════════════════════════
   Activities Map — Mode "mise en évidence des activités externes"
   ──────────────────────────────────────────────────
   Toggle qui passe l'ensemble du SVG (bandes, formes, connecteurs, textes)
   en gris à l'exception des activités dont l'id figure dans
   `window.EXTCO_ACTIVITY_IDS` (rempli côté serveur depuis le JSON
   OptiqCarto : subtype ∈ {extco, external}).

   Approche : JS-driven, on modifie directement les attributs `fill` / `stroke`
   de chaque élément peint, en sauvegardant l'original via dataset pour pouvoir
   restaurer. On ÉVITE volontairement les CSS `filter` sur des parents : le
   pipeline de rendu SVG applique le filtre parent à tout le sous-arbre, ce
   qui rend impossible de "désaturer parent + colorer enfant" via CSS seul.
   ══════════════════════════════════════════════════ */

let _extcoMapActive = false;

const DIM_FILL   = '#cbd5e1'; // gris bleuté clair
const DIM_STROKE = '#94a3b8'; // gris bleuté foncé
const DIM_TEXT   = '#94a3b8';

function isExtcoMapHighlightActive() {
  return _extcoMapActive;
}

function extcoMapCount() {
  return (window.EXTCO_ACTIVITY_IDS || []).length;
}

// Retourne true si `node` est un descendant (ou égal) d'un des `roots`.
function _isInside(node, roots) {
  for (const r of roots) if (r === node || r.contains(node)) return true;
  return false;
}

function applyExtcoMapHighlight(svgRoot) {
  if (!svgRoot) return;
  const extcoIds = new Set((window.EXTCO_ACTIVITY_IDS || []).map(v => String(v)));

  // Sous-arbres à conserver en couleur (les activités externes).
  const keepRoots = [];
  svgRoot.querySelectorAll('.carto-activity').forEach(el => {
    const aid = String(el.dataset.activityId || '');
    if (extcoIds.has(aid)) {
      keepRoots.push(el);
      el.classList.add('extco-keep');
    }
  });

  // Parcours brut : tout élément peint qui n'est PAS dans un sous-arbre keepRoot
  // se voit appliquer un fill/stroke gris (la valeur d'origine est sauvée
  // dans dataset.extcoFill / dataset.extcoStroke pour restauration).
  const allPainted = svgRoot.querySelectorAll('[fill], [stroke]');
  allPainted.forEach(el => {
    if (_isInside(el, keepRoots)) return;
    if (el.tagName && el.tagName.toLowerCase() === 'defs') return;

    if (el.hasAttribute('fill') && !('extcoFill' in el.dataset)) {
      const orig = el.getAttribute('fill');
      el.dataset.extcoFill = orig === null ? '__NULL__' : orig;
      // Conserve "none" et les transparents tels quels — on grise seulement
      // les fills qui sont réellement visibles.
      if (orig && orig !== 'none' && orig !== 'transparent') {
        const isText = el.tagName && el.tagName.toLowerCase() === 'text';
        el.setAttribute('fill', isText ? DIM_TEXT : DIM_FILL);
      }
    }
    if (el.hasAttribute('stroke') && !('extcoStroke' in el.dataset)) {
      const orig = el.getAttribute('stroke');
      el.dataset.extcoStroke = orig === null ? '__NULL__' : orig;
      if (orig && orig !== 'none' && orig !== 'transparent') {
        el.setAttribute('stroke', DIM_STROKE);
      }
    }
  });

  // Halo rose autour des activités conservées (filtre uniquement sur l'élément
  // racine de l'activité, pas sur un parent — donc pas d'effet d'héritage).
  keepRoots.forEach(el => {
    el.dataset.extcoOrigFilter = el.style.filter || '';
    el.style.filter = 'drop-shadow(0 0 6px rgba(236, 72, 153, 0.85)) drop-shadow(0 0 14px rgba(236, 72, 153, 0.45))';
  });

  svgRoot.classList.add('extco-highlight-active');
  _extcoMapActive = true;
}

function clearExtcoMapHighlight(svgRoot) {
  if (!svgRoot) return;

  svgRoot.querySelectorAll('[data-extco-fill]').forEach(el => {
    const orig = el.dataset.extcoFill;
    if (orig === '__NULL__') el.removeAttribute('fill');
    else                     el.setAttribute('fill', orig);
    delete el.dataset.extcoFill;
  });
  svgRoot.querySelectorAll('[data-extco-stroke]').forEach(el => {
    const orig = el.dataset.extcoStroke;
    if (orig === '__NULL__') el.removeAttribute('stroke');
    else                     el.setAttribute('stroke', orig);
    delete el.dataset.extcoStroke;
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
