/* ══════════════════════════════════════════════════════════════════
   VsdxImporter — pure Visio XML → carto data (no DOM/state mutation)
   Entry point: vsdxParse(file, onProgress, onOrphans?)
   Returns Promise<{ bands, shapes, connections, groups }>
   ══════════════════════════════════════════════════════════════════ */

class VsdxImporter {
  // Types de Row qui se terminent sur un sommet (X,Y). Les arcs sont réduits à
  // leur point d'arrivée : le renderer arrondit lui-même les angles.
  static VERTEX_ROW = { MoveTo:1, LineTo:1, ArcTo:1, EllipticalArcTo:1,
                        PolylineTo:1, NURBSTo:1, SplineStart:1, SplineKnot:1 };

  constructor(zip, onProgress) {
    this.zip  = zip;
    this.log  = onProgress || (() => {});
    this._p   = new DOMParser();

    // Master lookups
    this.masterIdToName  = {};
    this.masterIdToFile  = {};
    this.masterInfoCache = {};

    // Page data
    this.allShapes   = [];
    this.shapeMap    = {};
    this.shapePinAbs = {};
    this.connMap     = {};
    this.connectorIds = new Set();
    this.containerIds = new Set();
    this.pageMaxW    = 0;
    this.pageDoc     = null;

    // Band geometry
    this.topOfDiagram = 0;
    this.leftEdge     = 0;
    this.legendBounds = [];

    // Results
    this.newBands   = [];
    this.newShapes  = [];
    this.newConns   = [];
    this.newGroups  = [];
    this.nextOid    = (Date.now() % 1e7) | 0;

    this.SCALE = 130 / 0.9449; // px per Visio inch
    this.FALLBACK_COLORS = ['#22c55e','#3b82f6','#f59e0b','#e85d4a','#8b5cf6',
                            '#06b6d4','#ec4899','#f43f5e','#14b8a6','#a855f7'];
  }

  // ─── XML Helpers ─────────────────────────────────────────────────

  parseXml(text) { return this._p.parseFromString(text, 'application/xml'); }

  vEl(el, name) {
    for (const c of el.childNodes)
      if (c.nodeType === 1 && c.localName === name) return c;
    return null;
  }

  vAll(el, name) {
    return Array.from(el.childNodes).filter(c => c.nodeType === 1 && c.localName === name);
  }

  vDeep(el, name) {
    const q = [el];
    while (q.length) {
      const curr = q.shift();
      if (curr.nodeType !== 1) continue;
      if (curr.localName === name) return curr;
      for (const c of curr.childNodes) if (c.nodeType === 1) q.push(c);
    }
    return null;
  }

  vCell(el, name) {
    for (const c of el.childNodes)
      if (c.nodeType === 1 && c.localName === 'Cell' && c.getAttribute('N') === name)
        return c.getAttribute('V');
    return null;
  }

  // Searches Cell in direct children AND within Section > Row > Cell
  // Couleur de trait telle qu'elle est VUE dans Visio : celle posée sur la forme,
  // sinon celle héritée du master. C'est le seul signal fiable pour rattacher un
  // losange décoratif à SA flèche : dans une carto métier, toutes les flèches
  // d'une même décision partagent la couleur du losange (pleines ou pointillées,
  // peu importe). Les valeurs de thème (THEMEVAL…) ne sont pas des couleurs.
  async visioLineColor(el) {
    const direct = this.vCellDeep(el, 'LineColor');
    if (direct && direct.startsWith('#')) return direct.toLowerCase();
    const mid = el.getAttribute('Master') || el.getAttribute('MasterShape');
    if (!mid) return null;
    const info = await this.getMasterInfo(mid);
    const c = info && info.lineColor;
    return c && c.startsWith('#') ? c.toLowerCase() : null;
  }

  vCellDeep(el, name) {
    const direct = this.vCell(el, name);
    if (direct !== null) return direct;
    for (const sec of el.childNodes) {
      if (sec.nodeType !== 1 || sec.localName !== 'Section') continue;
      for (const row of sec.childNodes) {
        if (row.nodeType !== 1 || row.localName !== 'Row') continue;
        for (const cell of row.childNodes)
          if (cell.nodeType === 1 && cell.localName === 'Cell' && cell.getAttribute('N') === name)
            return cell.getAttribute('V');
      }
    }
    return null;
  }

  vText(el) {
    const t = this.vDeep(el, 'Text');
    return t ? t.textContent.trim() : '';
  }

  // A color is "washed out" if it's near-white or desaturated light gray.
  // Used for shape fills and level-1 lane fill (reject transparent/default backgrounds).
  isWashedOut(hex) {
    if (!hex || !hex.startsWith('#') || hex.length < 7) return true;
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    const lum = (r*299 + g*587 + b*114) / 1000;
    if (lum > 240) return true;
    const max = Math.max(r,g,b), min = Math.min(r,g,b);
    const sat = max === 0 ? 0 : (max - min) / max;
    return lum > 210 && sat < 0.25;
  }

  // Permissive check for band index-strip colors: only reject near-white (lum > 245).
  // Intentional pastels (#d4f4dd, #fdd2cc…) are kept — they are valid band colors.
  _isNearWhite(hex) {
    if (!hex || !hex.startsWith('#') || hex.length < 7) return true;
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return (r*299 + g*587 + b*114) / 1000 > 245;
  }

  // ─── Phase 1: Parse Masters ──────────────────────────────────────

  async parseMasters() {
    this.log('Analyse des masters…');
    try {
      const mastersXml  = await this.zip.file('visio/masters/masters.xml').async('text');
      const mastersRels = await this.zip.file('visio/masters/_rels/masters.xml.rels').async('text');
      const mDoc = this.parseXml(mastersXml);
      const rDoc = this.parseXml(mastersRels);

      const ridToFile = {};
      for (const rel of rDoc.getElementsByTagName('Relationship'))
        ridToFile[rel.getAttribute('Id')] = rel.getAttribute('Target');

      for (const m of mDoc.getElementsByTagName('Master')) {
        const mid   = m.getAttribute('ID');
        const nameU = m.getAttribute('NameU') || '';
        const nameL = m.getAttribute('Name')  || '';
        this.masterIdToName[mid] = nameU || nameL;
        const relEl = this.vDeep(m, 'Rel');
        if (relEl) {
          let rid = null;
          for (const attr of relEl.attributes)
            if (attr.localName === 'id') { rid = attr.value; break; }
          if (rid && ridToFile[rid])
            this.masterIdToFile[mid] = 'visio/masters/' + ridToFile[rid];
        }
      }
    } catch(e) { console.warn('[VsdxImporter] Masters:', e); }
  }

  // ── Static helper: analyse géométrique du master XML ──────────────────────
  // Scopée au shape primaire (premier enfant direct de <Shapes>) pour éviter
  // que les sous-shapes imbriqués (placeholder texte, etc.) n'inflatent les compteurs.
  // Retourne les flags de classification + logs console pour le debug.
  static _parseGeometry(doc, masterName) {
    // 1. Trouver le shape primaire
    const shapesRoot = doc.getElementsByTagName('Shapes')[0];
    let primaryShape = null;
    if (shapesRoot) {
      for (let ci = 0; ci < shapesRoot.childNodes.length; ci++) {
        const n = shapesRoot.childNodes[ci];
        if (n.nodeType === 1 && n.tagName === 'Shape') { primaryShape = n; break; }
      }
    }
    if (!primaryShape) primaryShape = doc.getElementsByTagName('Shape')[0] || null;

    // 2. Sections Geometry enfants DIRECTS du shape primaire seulement
    const geomSects = [];
    if (primaryShape) {
      for (let ci = 0; ci < primaryShape.childNodes.length; ci++) {
        const n = primaryShape.childNodes[ci];
        if (n.nodeType === 1 && n.tagName === 'Section' && n.getAttribute('N') === 'Geometry')
          geomSects.push(n);
      }
    }

    // 3. Compter les types de Row
    const LINE_TYPES = new Set(['LineTo', 'RelLineTo', 'PolylineTo']);
    const ARC_TYPES  = new Set(['EllipticalArcTo', 'RelEllipticalArcTo', 'ArcTo', 'RelArcTo',
                                'NURBSTo', 'SplineTo', 'RelSplineTo']);
    const MOVE_TYPES = new Set(['MoveTo', 'RelMoveTo']);
    const geomSeq = []; // 'L' | 'A'
    const unknownTypes = new Set();
    let moveTos = 0, totalRows = 0;

    for (const sect of geomSects) {
      const rows = sect.getElementsByTagName('Row');
      for (let ri = 0; ri < rows.length; ri++) {
        const t = rows[ri].getAttribute('T') || '';
        totalRows++;
        if (LINE_TYPES.has(t))      geomSeq.push('L');
        else if (ARC_TYPES.has(t))  geomSeq.push('A');
        else if (!MOVE_TYPES.has(t) && t) unknownTypes.add(t);
        if (MOVE_TYPES.has(t)) moveTos++;
      }
    }

    const arcCount     = geomSeq.filter(v => v === 'A').length;
    const lineCount    = geomSeq.filter(v => v === 'L').length;
    const geomSectCount = geomSects.length;

    // 4. Classifications
    const isEllipse = arcCount > 0 && arcCount > lineCount * 2;
    let isDiamond = false;
    if (arcCount > 0) {
      const lastA = geomSeq.lastIndexOf('A');
      if (lastA < geomSeq.length - 1) isDiamond = geomSeq.slice(lastA + 1).includes('L');
    }
    let hasConsecArcs = false;
    for (let i = 0; i < geomSeq.length - 1; i++)
      if (geomSeq[i] === 'A' && geomSeq[i+1] === 'A') { hasConsecArcs = true; break; }
    const isWavyBottom = hasConsecArcs && !isEllipse && !isDiamond;
    const isSubprocess = (geomSectCount >= 2 || moveTos >= 3 || isWavyBottom) && !isEllipse && !isDiamond;

    // 5. Stadium — 4 chemins de détection
    const isStadiumCanon   = lineCount === 2 && arcCount >= 2;
    const isStadiumAllArc  = lineCount <= 1 && arcCount >= 4;
    const isStadiumByRatio = arcCount >= 1 && lineCount <= 2; // aspect checked by caller
    // Fallback: sections trouvées mais tous les types de Row sont inconnus (ex: format VSDX exotique)
    // → si le ratio est élongé et pas de vague, c'est probablement un stadium.
    const isStadiumUnknown = geomSectCount > 0 && totalRows > 0 && arcCount === 0 && lineCount === 0;

    // Log détaillé dans la console navigateur — ouvrir DevTools lors de l'import pour voir
    console.debug(
      '[VSDX geom]', (masterName || '?').padEnd(30),
      '| sects:', geomSectCount, '| rows:', totalRows,
      '| arcs:', arcCount, '| lines:', lineCount, '| moveTos:', moveTos,
      '| seq:', geomSeq.join('') || '(vide)',
      unknownTypes.size ? '| unknownRowTypes: ' + [...unknownTypes].join(',') : '',
      '| isStadiumCanon:', isStadiumCanon, '| byRatio(no-asp):', isStadiumByRatio,
      '| isStadiumUnknown:', isStadiumUnknown,
      '| isWavy:', isWavyBottom, '| isSubprocess:', isSubprocess,
      '| isEllipse:', isEllipse, '| isDiamond:', isDiamond
    );

    return { arcCount, lineCount, moveTos, geomSectCount, totalRows, geomSeq,
             isEllipse, isDiamond: isDiamond, isWavyBottom, isSubprocess,
             isStadiumCanon, isStadiumByRatio, isStadiumAllArc, isStadiumUnknown,
             unknownTypes };
  }

  async getMasterInfo(mid) {
    const DEFAULTS = { w: 0.9449, h: 0.7087, linePattern: 1, fillPattern: 1,
                       isEllipse: false, isDiamond: false, isSubprocess: false,
                       isStadium: false, isWavyBottom: false, aspect: 1,
                       fillColor: null, lineColor: null, subFills: {} };
    if (!mid) return DEFAULTS;
    if (this.masterInfoCache[mid]) return this.masterInfoCache[mid];
    const fpath = this.masterIdToFile[mid];
    if (!fpath) return this.masterInfoCache[mid] = { ...DEFAULTS };
    try {
      const xml = await this.zip.file(fpath).async('text');
      const doc = this.parseXml(xml);

      // ── Dimensions + style du shape primaire ──
      let bw, bh, lp = 1, fp = 1, fillColor = null, lineColor = null, rounding = 0;
      const subFills = {};
      for (const s of doc.getElementsByTagName('Shape')) {
        const w = this.vCell(s, 'Width'), h = this.vCell(s, 'Height');
        if (w) bw = parseFloat(w);
        if (h) bh = parseFloat(h);
        const lv = this.vCellDeep(s, 'LinePattern');
        if (lv) lp = parseInt(lv) || 1;
        const fpv = this.vCellDeep(s, 'FillPattern');
        if (fpv) fp = parseInt(fpv) || 1;
        const fc = this.vCell(s, 'FillForegnd');
        if (fc && fc.startsWith('#') && !fillColor) fillColor = fc;
        const lc = this.vCell(s, 'LineColor');
        if (lc && lc.startsWith('#') && !lineColor) lineColor = lc;
        // Cellule Rounding : Visio arrondit les coins via propriété de style (pas des arcs
        // dans la géométrie). Une valeur élevée (≥ 30 % de la petite dim.) crée l'aspect
        // "activité externe" (côtés en parenthèses) sans aucun EllipticalArcTo dans la geom.
        const rv = this.vCell(s, 'Rounding');
        if (rv) rounding = Math.max(rounding, parseFloat(rv) || 0);
        if (bw && bh) break;
      }
      // Remplissage PAR SOUS-FORME, sur TOUTES les formes du gabarit : la boucle
      // ci-dessus s'arrête à la forme primaire (break dès qu'on a ses dimensions)
      // et ne voit donc jamais les sous-formes. Or un couloir qui ne redéfinit
      // rien hérite la couleur de la sous-forme correspondante (MasterShape) —
      // c'est de là que vient la couleur de sa bande.
      for (const sub of doc.getElementsByTagName('Shape')) {
        const sid = sub.getAttribute('ID');
        const sfc = this.vCell(sub, 'FillForegnd');
        if (sid && sfc && sfc.startsWith('#')) subFills[sid] = sfc;
      }

      // Second pass FillPattern (sous-shapes)
      if (fp === 1) {
        for (const s of doc.getElementsByTagName('Shape')) {
          const fpv = this.vCellDeep(s, 'FillPattern');
          if (fpv) { const n = parseInt(fpv) || 1; if (n !== 1) { fp = n; break; } }
        }
      }

      const aspect = (bw && bh) ? Math.max(bw, bh) / Math.min(bw, bh) : 1;
      const masterName = Object.entries(this.masterIdToName || {}).find(([k]) => k === mid)?.[1] || '';

      // ── Analyse géométrique (scopée au shape primaire) ──
      const g = VsdxImporter._parseGeometry(doc, masterName);

      // Certaines formes Visio (ex: "Processus arrondi" / "Rounded process") encodent
      // leur aspect arrondi via la cellule Rounding (propriété de style), sans aucun arc
      // dans la section Geometry. Si le rayon ≥ 30 % de la petite dimension, la forme
      // est visuellement un stade → traiter comme activité externe.
      const minDim = (bw && bh) ? Math.min(bw, bh) : 0;
      const isRoundedAsStadium = rounding > 0 && minDim > 0 && (rounding / minDim) >= 0.3;

      // Stadium : aspect ratio vérifié ici (pas dans _parseGeometry)
      const isStadium = !g.isEllipse && !g.isDiamond && !g.isWavyBottom && (
        g.isStadiumCanon ||
        g.isStadiumAllArc ||
        (g.isStadiumByRatio && aspect >= 1.5) ||
        (g.isStadiumUnknown && aspect >= 1.5) ||  // fallback types inconnus
        isRoundedAsStadium                         // rounding cellule élevé → côtés arrondis
      );

      console.debug(
        '[VSDX master]', (masterName || '?').padEnd(30),
        '| aspect:', aspect.toFixed(2), '| isStadium:', isStadium,
        '| rounding:', rounding.toFixed(3), '| isRoundedAsStadium:', isRoundedAsStadium,
        '| isSubprocess:', g.isSubprocess, '| fp:', fp, '| fillColor:', fillColor || '-'
      );

      return this.masterInfoCache[mid] = {
        w: bw || 0.9449, h: bh || 0.7087,
        linePattern: lp, fillPattern: fp, fillColor, lineColor, subFills,
        isEllipse: g.isEllipse, isDiamond: g.isDiamond,
        isSubprocess: g.isSubprocess, isWavyBottom: g.isWavyBottom,
        isStadium, aspect,
      };
    } catch(e) {
      console.warn('[VSDX getMasterInfo] mid=', mid, e);
      return this.masterInfoCache[mid] = { ...DEFAULTS };
    }
  }

  // ─── Phase 2: Parse Page XML ─────────────────────────────────────

  async parsePage() {
    this.log('Lecture de la page…');
    const pageXml = await this.zip.file('visio/pages/page1.xml').async('text');
    this.pageDoc  = this.parseXml(pageXml);
    this.allShapes = [];
    const rootShapesEl = this.vEl(this.pageDoc.documentElement, 'Shapes');
    if (rootShapesEl) this._collectShapes(rootShapesEl, 0, null, this.allShapes);
    this.shapeMap = {};
    for (const item of this.allShapes) this.shapeMap[item.id] = item;
  }

  _collectShapes(shapesEl, depth, parentId, acc) {
    for (const s of this.vAll(shapesEl, 'Shape')) {
      acc.push({ el: s, id: s.getAttribute('ID'), depth, parentId });
      const child = this.vEl(s, 'Shapes');
      if (child) this._collectShapes(child, depth + 1, s.getAttribute('ID'), acc);
    }
  }

  // ─── Phase 3: Pre-fetch all master info ──────────────────────────

  async prefetchMasters() {
    this.log('Analyse des masters…');
    const ids = [...new Set(this.allShapes.map(({el}) => el.getAttribute('Master')).filter(Boolean))];
    for (const mid of ids) await this.getMasterInfo(mid);
  }

  // ─── Phase 4: Compute absolute coordinates ───────────────────────
  // PinX/PinY is relative to parent's bottom-left corner for depth > 0.

  computeAbsCoords() {
    for (const { el: s, id, depth, parentId } of this.allShapes) {
      const mid   = s.getAttribute('Master');
      const mInfo = this.masterInfoCache[mid] || { w: 0, h: 0 };
      const px = parseFloat(this.vCell(s, 'PinX')   || '0');
      const py = parseFloat(this.vCell(s, 'PinY')   || '0');
      const sw = parseFloat(this.vCell(s, 'Width')  || '0') || mInfo.w;
      const sh = parseFloat(this.vCell(s, 'Height') || '0') || mInfo.h;
      if (depth === 0 || !parentId || !this.shapePinAbs[parentId]) {
        this.shapePinAbs[id] = { pinX: px, pinY: py, w: sw, h: sh };
      } else {
        const par = this.shapePinAbs[parentId];
        this.shapePinAbs[id] = {
          pinX: (par.pinX - par.w / 2) + px,
          pinY: (par.pinY - par.h / 2) + py,
          w: sw, h: sh,
        };
      }
    }
  }

  // ─── Phase 5: Build connection map ───────────────────────────────
  // Scans the full page XML for <Connect> elements.
  // connMap[connectorId] = { source: shapeId, target: shapeId }

  buildConnMap() {
    const connMap      = this.connMap;
    const connectorIds = this.connectorIds;
    function scanConnects(el) {
      for (const c of el.childNodes) {
        if (c.nodeType !== 1) continue;
        if (c.localName === 'Connect') {
          const from = c.getAttribute('FromSheet');
          const to   = c.getAttribute('ToSheet');
          const cell = c.getAttribute('FromCell');
          if (from) {
            connectorIds.add(from);
            if (!connMap[from]) connMap[from] = {};
            if (cell === 'BeginX') connMap[from].source = to;
            else if (cell === 'EndX') connMap[from].target = to;
          }
        } else { scanConnects(c); }
      }
    }
    scanConnects(this.pageDoc.documentElement);
  }

  // ─── Phase 6: Identify lane containers ──────────────────────────
  // containerIds = groups that are swim lanes or cross-functional pools

  identifyContainers() {
    const LANE_RE = /\b(lane|swimlane|couloir)\b/;
    const POOL_RE = /\b(pool|cross.?functional)\b/;
    let maxW = 0;
    for (const { id } of this.allShapes) {
      const abs = this.shapePinAbs[id];
      if (abs) maxW = Math.max(maxW, abs.w);
    }
    this.pageMaxW = maxW;
    for (const { el: s, id } of this.allShapes) {
      if (s.getAttribute('Type') !== 'Group') continue;
      const mn  = (this.masterIdToName[s.getAttribute('Master')] || '').toLowerCase();
      const abs = this.shapePinAbs[id] || {};
      if (LANE_RE.test(mn) || POOL_RE.test(mn) || (abs.w > maxW * 0.4 && this.vEl(s, 'Shapes')))
        this.containerIds.add(id);
    }
  }

  // ─── Phase 7: Build swim-lane bands ──────────────────────────────
  // Extracts lane elements as bands, computes topOfDiagram/leftEdge.
  // Populates this.newBands, this.legendBounds and this.bandShifts.

  buildBands() {
    this.log('Construction des bandes…');
    const { allShapes, containerIds, shapePinAbs, pageMaxW, SCALE, FALLBACK_COLORS } = this;

    const lanes = this._collectLanes(allShapes, containerIds, shapePinAbs, pageMaxW);

    // Compute diagram boundaries from lanes or all shapes
    let topOfDiagram, leftEdge = 0;
    if (lanes.length > 0) {
      topOfDiagram  = lanes[0].abs.pinY + lanes[0].abs.h / 2;
      leftEdge      = Math.min(...lanes.map(l => l.abs.pinX - l.abs.w / 2));
      this.rightEdge = Math.max(...lanes.map(l => l.abs.pinX + l.abs.w / 2));
    } else {
      let maxY = 0;
      for (const { id } of allShapes) {
        const abs = shapePinAbs[id];
        if (abs && abs.pinY + abs.h / 2 > maxY) maxY = abs.pinY + abs.h / 2;
      }
      topOfDiagram = maxY || 42;
    }
    this.topOfDiagram = topOfDiagram;
    this.leftEdge     = leftEdge;

    const newBands    = this.newBands;
    const legendBounds = this.legendBounds;

    // bandShifts: maps natural canvas Y positions (derived directly from Visio
    // coordinates) to rendered Y positions (with per-band min-height inflation).
    //
    // CRITICAL: naturalTop/naturalBottom are computed from ACTUAL Visio coords,
    // NOT from a running sum of processed band heights. A running sum ignores
    // inter-band gaps (e.g. "Prescriber" H=0 band leaves a ~700px gap between
    // adjacent bands), causing all subsequent band shifts to be wrong.
    this.bandShifts = [];

    if (lanes.length === 0) {
      newBands.push({ id: 1, label: 'Activités', color: '#22c55e', fontSize: 22, height: 500 });
      return;
    }

    let ourCum = 0;
    for (const { el: s, abs } of lanes) {
      // Natural canvas Y of this band's top and bottom edges,
      // measured directly from Visio coords (Y-up → Y-down conversion).
      const naturalTop    = Math.round((topOfDiagram - (abs.pinY + abs.h / 2)) * SCALE);
      const naturalBottom = Math.round((topOfDiagram - (abs.pinY - abs.h / 2)) * SCALE);
      const naturalH      = naturalBottom - naturalTop;
      const bandH         = Math.round(Math.max(80, naturalH));

      const label = this._extractLaneLabel(s);
      const fill  = this._extractLaneFill(s);

      if (/l[eé]gende?|legend/i.test(label)) {
        legendBounds.push({
          xMin: abs.pinX - abs.w / 2, xMax: abs.pinX + abs.w / 2,
          yMin: abs.pinY - abs.h / 2, yMax: abs.pinY + abs.h / 2,
        });
        continue;
      }

      // shift = ourCum - naturalTop maps from natural canvas Y to rendered Y.
      // For a shape with naturalCenterY inside [naturalTop, naturalBottom]:
      //   renderedY = naturalCenterY + shift = naturalCenterY + ourCum - naturalTop
      // which correctly maps the band's top (naturalTop) to ourCum.
      this.bandShifts.push({ naturalTop, naturalBottom, shift: ourCum - naturalTop });
      ourCum += bandH;

      const bandIdx = newBands.length + 1;
      // Aucune couleur lisible dans le fichier → gris neutre. Piocher dans une
      // palette de repli affichait des couleurs qui n'existent PAS dans le Visio
      // d'origine, et la carto ne ressemblait plus à ce que l'utilisateur a dessiné.
      const color = fill || '#d1d5db';
      newBands.push({ id: bandIdx, label: label || `Bande ${bandIdx}`, color, fontSize: 22, height: bandH });
    }
  }

  // Collect and sort swimlane elements (large container groups, top→bottom).
  // Deduplicates separator slivers that are too close together.
  _collectLanes(allShapes, containerIds, shapePinAbs, pageMaxW) {
    const laneList = [];
    for (const { el: s, id } of allShapes) {
      if (!containerIds.has(id)) continue;
      const abs = shapePinAbs[id] || {};
      if (!abs.h || abs.h < 0.3 || abs.h > 25) continue;
      if (!abs.w || abs.w < pageMaxW * 0.3)    continue;
      laneList.push({ el: s, id, abs });
    }
    laneList.sort((a, b) => b.abs.pinY - a.abs.pinY); // highest Y first (Visio Y-up = top of diagram)

    const lanes = [];
    for (const ln of laneList) {
      const prev = lanes[lanes.length - 1];
      if (prev && Math.abs(ln.abs.pinY - prev.abs.pinY) < 0.15) continue; // deduplicate slivers
      lanes.push(ln);
    }
    return lanes;
  }

  // Extract the visible text label from a swimlane element.
  // Looks in direct non-Shapes children first, then in nested child shapes.
  _extractLaneLabel(el) {
    for (const c of el.childNodes) {
      if (c.nodeType !== 1 || c.localName === 'Shapes') continue;
      const t = this.vDeep(c, 'Text');
      if (t && t.textContent.trim()) return t.textContent.trim();
    }
    const nested = this.vEl(el, 'Shapes');
    if (nested) {
      for (const child of this.vAll(nested, 'Shape')) {
        const t = this.vText(child);
        if (t && t.length > 0 && t.length < 100) return t;
      }
    }
    return '';
  }

  // Mix color 30 % vivid + 70 % white → pastel version.
  _toPastel(hex) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return '#' + [r*0.3+255*0.7, g*0.3+255*0.7, b*0.3+255*0.7]
      .map(v => Math.round(v).toString(16).padStart(2,'0')).join('');
  }

  // Extract the fill color of a swimlane.
  //
  // Visio CFF swimlane structure (always 2 children):
  //   child[0] = background rect (may be grey or transparent — NOT the band color)
  //   child[1] = index strip (the colored sidebar with the lane label)
  //
  // Strategy:
  //   1. Lane's own FillForegnd — use as-is if not washed out.
  //   2. Last non-near-white child = index strip — use as-is regardless of saturation.
  //      No pastelification: vivid colors stay vivid, pastels stay pastel.
  //      (Stakeholder of the Order has no text node on its label — its label is a
  //      Visio formula — so the LAST child approach is needed to skip the grey
  //      background shape and land on the correct colored index strip.)
  // Couleur d'un couloir = celle de son BANDEAU D'INDEX (l'enfant qui porte le
  // libellé de la bande). Deux pièges :
  //  • prendre « le dernier enfant coloré » ramenait tantôt le bandeau, tantôt
  //    le fond du couloir — d'où des bandes qui ne ressemblaient pas au fichier ;
  //  • un couloir qui ne redéfinit rien HÉRITE la couleur de son gabarit
  //    (MasterShape) : sans la résoudre, on inventait une couleur de repli.
  _extractLaneFill(el) {
    const childEl = this.vEl(el, 'Shapes');

    // Couleur posée sur l'enfant, sinon celle qu'il HÉRITE de la sous-forme
    // correspondante du gabarit : un couloir qui ne redéfinit rien s'affiche bien
    // avec la couleur du gabarit dans Visio (3e bande de la carto client = rouge).
    const sousFormes = (this.masterInfoCache[el.getAttribute('Master')] || {}).subFills || {};
    const couleurDe = (child) => {
      const propre = this.vCell(child, 'FillForegnd');
      if (propre) return (propre.startsWith('#') && !this._isNearWhite(propre)) ? propre : null;
      if (this.vCell(child, 'FillPattern') === '0') return null;   // explicitement sans remplissage
      const heritee = sousFormes[child.getAttribute('MasterShape')];
      return (heritee && heritee.startsWith('#') && !this._isNearWhite(heritee)) ? heritee : null;
    };

    if (childEl) {
      const enfants = this.vAll(childEl, 'Shape');
      // 1) l'enfant qui porte le libellé = le bandeau
      for (const child of enfants) {
        if (!this.vText(child)) continue;
        const c = couleurDe(child);
        if (c) return c;
      }
      // 2) à défaut, le dernier enfant coloré (ancien comportement)
      let best = null;
      for (const child of enfants) {
        const c = couleurDe(child);
        if (c) best = c;
      }
      if (best) return best;
    }

    const fill = this.vCell(el, 'FillForegnd');
    return this.isWashedOut(fill) ? null : fill;
  }

  // Détermine le shift Y à appliquer à un point dont le Y naturel (sans
  // contrainte de hauteur min) est donné, en se basant sur la bandShiftMap.
  // Sans cette correction, une bande étroite inflée au min 80 décale
  // visuellement toutes les bandes en dessous, et les shapes (placées
  // d'après leurs coords VSDX naturelles) finissent dans la mauvaise bande.
  _bandShiftFor(naturalY) {
    const map = this.bandShifts;
    if (!map || map.length === 0) return 0;
    for (const bs of map) {
      if (naturalY >= bs.naturalTop && naturalY < bs.naturalBottom) return bs.shift;
    }
    // Hors de toutes les bandes (ex: bande Prescriber H=0 filtrée) →
    // utiliser le shift de la bande dont l'ARÊTE la plus proche est la plus
    // près (edge-based, plus précis que la distance au centre pour les gaps).
    let nearest = map[0], nearestDist = Infinity;
    for (const bs of map) {
      const d = Math.min(Math.abs(naturalY - bs.naturalTop), Math.abs(naturalY - bs.naturalBottom));
      if (d < nearestDist) { nearestDist = d; nearest = bs; }
    }
    return nearest.shift;
  }

  // Returns true if a shape's center falls inside a legend lane
  isInLegend(id) {
    if (this.legendBounds.length === 0) return false;
    const a = this.shapePinAbs[id];
    if (!a) return false;
    for (const b of this.legendBounds)
      if (a.pinX > b.xMin && a.pinX < b.xMax && a.pinY > b.yMin && a.pinY < b.yMax) return true;
    return false;
  }

  // ─── Phase 8: Detect transparent container groups ────────────────
  // These are large semi-transparent labeled boxes that visually wrap
  // activities in Visio but are NOT XML parents of those activities.
  // Shapes that are connection endpoints cannot be container groups.

  detectContainerGroups() {
    const connEndpoints = new Set(
      Object.values(this.connMap).flatMap(e => [e.source, e.target]).filter(Boolean)
    );
    this._shapeElById = new Map(this.allShapes.map(({el, id}) => [id, el]));

    const containerGroupIds  = new Set();
    const containerGroupData = [];

    const MAX_ACT_W = 260, MAX_ACT_H = 150; // same cap as importActivities

    for (const { el: s, id } of this.allShapes) {
      if (this.connectorIds.has(id) || this.containerIds.has(id)) continue;
      // Connection endpoints are normally activities, NOT container groups.
      // Exception: if the shape would be way oversized as an activity (e.g. Installation
      // w=6.36"), it is a visual container even if it participates in some connections.
      if (connEndpoints.has(id)) {
        const abs_ep = this.shapePinAbs[id] || {};
        const wouldBeCapped = (abs_ep.w || 0) * this.SCALE > MAX_ACT_W
                           || (abs_ep.h || 0) * this.SCALE > MAX_ACT_H;
        if (!wouldBeCapped) continue; // normal-sized endpoint → treat as activity
        // oversized endpoint → fall through and evaluate as potential container group
      }
      const mid_cg = s.getAttribute('Master');
      const mInfo_cg = this.masterInfoCache[mid_cg] || {};
      if (mInfo_cg.isDiamond || mInfo_cg.isEllipse) continue;
      const ft = parseFloat(this.vCell(s, 'FillForegndTrans') || '0');
      const bt = parseFloat(this.vCell(s, 'FillBkgndTrans')   || '0');
      if (Math.max(ft, bt) < 0.4) continue;
      const abs = this.shapePinAbs[id] || {};
      if (!abs.w || !abs.h || abs.w < 1 || abs.h < 0.5) continue;
      if (abs.w > this.pageMaxW * 0.9) continue;
      const label = this.vText(s);
      if (!label || label.length > 80) continue;
      containerGroupIds.add(id);
      containerGroupData.push({ id, label, abs });
    }
    this._containerGroupIds  = containerGroupIds;
    this._containerGroupData = containerGroupData;
  }

  // ─── Phase 9: Import activities as shapes ────────────────────────
  // Key fixes:
  //   - Cap oversized shapes (group boxes that are also connection endpoints)
  //   - Read VSDX FillForegnd → master fillColor → band color (in priority order)
  //   - Respect LayerMember=6 exclusion (drapeaux retour)

  importActivities() {
    this.log('Import des activités…');
    const { allShapes, connectorIds, containerIds, shapePinAbs, masterInfoCache,
            masterIdToName, SCALE, newBands, topOfDiagram, leftEdge,
            _containerGroupIds } = this;

    const newShapes  = this.newShapes;
    const shapeIdMap = this._shapeIdMap = {};
    const totalBandH = newBands.reduce((s, b) => s + b.height, 0);
    const MAX_ACT_W = 260, MAX_ACT_H = 150; // cap for oversized group-box shapes
    const validationMarkers = []; // validation badge symbols, resolved after all shapes

    for (const { el: s, id } of allShapes) {
      if (connectorIds.has(id))       continue;
      if (containerIds.has(id))       continue;
      if (_containerGroupIds.has(id)) continue;
      if (this.isInLegend(id))        continue;

      const mid   = s.getAttribute('Master');
      const vType = s.getAttribute('Type');
      if (!mid && vType !== 'Group') continue;

      const mn = (masterIdToName[mid] || '').toLowerCase();
      if (/\b(connector|dynamic connector|line|arrow)\b/.test(mn)) continue;
      if (/^(title|text|annotation|callout|note|border|background|frame)$/.test(mn)) continue;
      // "N-"/"D-"/"T-" prefix = CFF navigation cross-reference arrows (not activities)
      if (/^[ndt]\s*[-–]/.test(mn)) continue;

      // LayerMember=3 marks the "Si petit"/"Si grand" layer.
      // In Visio CFF diagrams these shapes ARE the actual decision diamonds (isDiamond=true).
      // Only exclude non-diamond LayerMember=3 shapes (genuine decorators/annotations).
      const mInfoLayer = masterInfoCache[mid] || {};
      if (this.vCell(s, 'LayerMember') === '3' && !mInfoLayer.isDiamond) continue;

      const abs = shapePinAbs[id] || {};
      const vW  = abs.w || 0;
      const vH  = abs.h || 0;

      // Capture validation/approval badge symbols before the size filter (they are ~0.22" squares).
      // Master names: "Approbation…", "Approuve…", "Approval…", "Checkmark", "Coche"
      if (/^(approbation|approuve|approval|checkmark|coche)\b/i.test(mn) && abs.pinX) {
        const vmW = Math.round(vW * SCALE);
        const vmH = Math.round(vH * SCALE);
        const vmX = Math.max(144, Math.round((abs.pinX - leftEdge) * SCALE) - Math.round(vmW / 2));
        const vmNY = Math.round((topOfDiagram - abs.pinY) * SCALE) - Math.round(vmH / 2);
        const vmY = Math.max(0, vmNY + this._bandShiftFor(vmNY + vmH / 2));
        if (vmY <= totalBandH + 100) validationMarkers.push({ x: vmX, y: vmY, w: vmW, h: vmH });
        continue;
      }

      if (vW < 0.2 || vH < 0.25) continue; // <0.25" height = thin nav arrow, not an activity
      if (vW > 8   || vH > 4   ) continue;

      // Exclude shapes outside the diagram's horizontal bounds
      // (e.g. legend shapes, return indicators far outside the CFF container)
      const MARGIN_X = 1.5; // inches tolerance beyond band edges
      if (this.rightEdge && (abs.pinX < leftEdge - MARGIN_X || abs.pinX > this.rightEdge + MARGIN_X)) continue;
      // Exclude shapes above the diagram top (they would pile up at y=0)
      if (abs.pinY > topOfDiagram + 1.0) continue;

      // Compute screen position from center (so capping doesn't shift center point)
      const rawW = Math.round(vW * SCALE);
      const rawH = Math.round(vH * SCALE);
      const screenW = Math.min(MAX_ACT_W, rawW);
      const screenH = Math.min(MAX_ACT_H, rawH);
      const screenX = Math.max(144, Math.round((abs.pinX - leftEdge) * SCALE) - Math.round(screenW / 2));
      // Y "naturel" : position basée sur les coords VSDX brutes × SCALE,
      // SANS prendre en compte le minimum 80 px sur la hauteur des bandes.
      const naturalScreenY = Math.round((topOfDiagram - abs.pinY) * SCALE) - Math.round(screenH / 2);
      const naturalCenterY = naturalScreenY + screenH / 2;
      // bandShift corrige le décalage cumulatif quand une bande étroite a
      // été inflée au min 80 px : on ramène le shape dans la bande à laquelle
      // il appartient naturellement, même si nos bandes sont plus hautes.
      const bandShift = this._bandShiftFor(naturalCenterY);
      const screenY = Math.max(0, naturalScreenY + bandShift);
      if (screenY > totalBandH + 100) continue; // outside diagram

      const mInfoForType = masterInfoCache[mid] || {};
      const masterName  = masterIdToName[mid] || '';
      // Fallback nom : couvre les masters Visio "External Process", "Activité
      // externe", "Sous-traitance", etc. — utile quand la géométrie ne suffit
      // pas (ex: shape custom redessinée mais qui garde le nom du stencil).
      const isExternalByName = /\b(external|externe|outsourc\w*|sous.?trait\w*)\b/i.test(masterName);

      // isStadiumByAspect : forme élongée non-vague mal classée par la géométrie
      // → dernier recours si isStadium=false mais aspect >= 1.5 et pas de vague
      const isStadiumByAspect = !mInfoForType.isWavyBottom
                                && (mInfoForType.aspect || 1) >= 1.5
                                && !mInfoForType.isEllipse && !mInfoForType.isDiamond;

      let shapeType = detectShapeType(masterName, vType,
                          mInfoForType.isEllipse, mInfoForType.isDiamond,
                          mInfoForType.isSubprocess,
                          mInfoForType.isStadium || isExternalByName);

      // Safety nets — overrides quand la géométrie ou le nom n'ont pas suffi
      if (shapeType === 'special') {
        if (isExternalByName) {
          // Nom explicitement "external / externe" → process externe
          shapeType = 'process';
        } else if (isStadiumByAspect && vType !== 'Group') {
          // Forme élongée non-vague sans master Group → probablement externe
          shapeType = 'process';
        }
        // Note: vType === 'Group' elongated est ambigu (peut être un container),
        // on le laisse en 'special' si ni name ni géométrie n'ont confirmé.
      }

      // ── Subtype detection (only for 'process' shapes) ─────────────────
      const shapeFillPattern = parseInt(this.vCellDeep(s, 'FillPattern') || '0') || (mInfoForType.fillPattern || 1);
      let subtype = 'normal';
      if (shapeType === 'process') {
        if (mInfoForType.isStadium || isExternalByName || isStadiumByAspect) {
          subtype = 'external';
          console.debug('[VSDX external]', this.vText(s) || id,
            'master=', masterName, 'stadium=', !!mInfoForType.isStadium,
            'byName=', isExternalByName, 'byAspect=', isStadiumByAspect,
            'aspect=', (mInfoForType.aspect || 1).toFixed(2));
        } else if (shapeFillPattern >= 2) {
          subtype = 'extco';
          console.debug('[VSDX hatch]', this.vText(s) || id, 'FillPattern=', shapeFillPattern, 'master=', masterName);
        }
      }

      // ── Color: VSDX shape fill → master fill → band color ──
      // Preserves original Visio colors (e.g. yellow logistics, blue ops shapes).
      // Only falls back to band color when the shape has no explicit fill.
      const shapeColor = this._resolveShapeColor(s, mid, shapeType, screenY, screenH);

      // Validation/approval symbols → set badge on nearest activity instead of adding as sub-shape
      if (/\b(validation|approbation|approuve|approval|checkmark|coche)\b/i.test(masterName)) {
        validationMarkers.push({ x: screenX, y: screenY, w: screenW, h: screenH });
        continue;
      }

      const oid = this.nextOid++;
      shapeIdMap[id] = oid;
      newShapes.push({
        id: oid, type: shapeType, subtype,
        x: screenX, y: screenY, w: screenW, h: screenH,
        label:          this.vText(s),
        color:          shapeColor,
        textColor:      '#ffffff',
        strokeColor:    '',
        fontSize:       18,
        validationBadge: false,
        validationColor: '#4DB868',
        colorVariant:   0,
      });
    }

    // Apply validation badges: find nearest process shape for each validation marker
    for (const vm of validationMarkers) {
      const vmCX = vm.x + vm.w / 2, vmCY = vm.y + vm.h / 2;
      let bestShape = null, bestDist = Infinity;
      for (const s of newShapes) {
        if (s.type !== 'process') continue;
        const d = Math.hypot(vmCX - (s.x + s.w / 2), vmCY - (s.y + s.h / 2));
        if (d < bestDist) { bestDist = d; bestShape = s; }
      }
      if (bestShape) {
        bestShape.validationBadge = true;
        bestShape.validationColor = bestShape.color; // badge takes activity's own color
      }
    }
    if (validationMarkers.length > 0)
      this.log(`✓ ${validationMarkers.length} badge(s) validation détecté(s) et appliqué(s)`);

    const nExt   = newShapes.filter(s => s.subtype === 'external').length;
    const nExtco = newShapes.filter(s => s.subtype === 'extco').length;
    if (nExt   > 0) this.log(`✓ ${nExt} activité(s) externe(s) (forme stade) détectée(s)`);
    if (nExtco > 0) this.log(`✓ ${nExtco} activité(s) hachurée(s) détectée(s)`);
    if (nExt === 0 && nExtco === 0) this.log('ℹ Aucune activité externe ou hachurée détectée (voir console pour détails)');
  }

  // Resolve the best color for a shape:
  // 1. Shape's own FillForegnd (explicit override in VSDX)
  // 2. Master's default fillColor (inherited from stencil)
  // 3. Band color based on Y position
  _resolveShapeColor(el, mid, shapeType, screenY, screenH) {
    if (shapeType === 'decision') return '#9ca3af';

    // 1. Shape's own explicit fill
    const shapeFill = this.vCell(el, 'FillForegnd');
    if (shapeFill && !this.isWashedOut(shapeFill)) return shapeFill;

    // 2. Master's default fill (shape inherits from stencil).
    // Use _isNearWhite (not isWashedOut) — intentional greys like #d8d8d8 are valid
    // stencil colors and must not be discarded as "washed out".
    const masterFill = (this.masterInfoCache[mid] || {}).fillColor;
    if (masterFill && !this._isNearWhite(masterFill)) return masterFill;

    // 3. Band color
    let cumY = 0;
    for (const b of this.newBands) {
      if (screenY + screenH / 2 >= cumY && screenY + screenH / 2 < cumY + b.height)
        return b.color;
      cumY += b.height;
    }
    return this.newBands[0]?.color || '#22c55e';
  }

  // ─── Phase 10: Layout corrections ───────────────────────────────

  applyLayoutCorrections() {
    const { newShapes, newBands, SCALE, topOfDiagram, leftEdge } = this;

    // Clamp shapes within their band (prevents band-overlap)
    const PAD_BAND = 6;
    let cumY = 0;
    const bRanges = newBands.map(b => { const y0 = cumY; cumY += b.height; return { y0, y1: cumY }; });
    for (const s of newShapes) {
      const cy = s.y + s.h / 2;
      const br = bRanges.find(r => cy >= r.y0 && cy < r.y1) ||
        bRanges.reduce((best, r) => {
          const dm = Math.abs(cy - (r.y0 + r.y1) / 2);
          return dm < Math.abs(cy - (best.y0 + best.y1) / 2) ? r : best;
        }, bRanges[bRanges.length - 1]);
      if (!br) continue;
      if (s.y < br.y0 + PAD_BAND) s.y = br.y0 + PAD_BAND;
      if (s.y + s.h > br.y1 - PAD_BAND) s.y = Math.max(br.y0 + PAD_BAND, br.y1 - PAD_BAND - s.h);
    }

    // Nudge decision diamonds toward nearby shapes for better routing
    const NUDGE = 18;
    for (const s of newShapes) {
      if (s.type !== 'decision') continue;
      const neighbors = newShapes.filter(o => o.id !== s.id && o.type !== 'decision');
      if (neighbors.length === 0) continue;
      const nearX = neighbors
        .map(o => ({ dx: Math.abs((o.x + o.w/2) - (s.x + s.w/2)), cx: o.x + o.w/2 }))
        .filter(o => o.dx < 200).sort((a, b) => a.dx - b.dx).slice(0, 4);
      if (nearX.length === 0) continue;
      const avgX  = nearX.reduce((sum, o) => sum + o.cx, 0) / nearX.length;
      const shift = Math.max(-NUDGE, Math.min(NUDGE, (avgX - (s.x + s.w/2)) * 0.3));
      if (Math.abs(shift) > 3) s.x = Math.round(s.x + shift);
    }
  }

  // ─── Rattachement des losanges décoratifs à LEUR flèche ──────────
  // Un losange de décision n'est pas connecté dans Visio : il est posé SUR les
  // flèches. « La flèche la plus proche » se trompe dès que deux tracés se
  // frôlent — ce qui arrive constamment autour d'un losange.
  //
  // Le signal fiable est la COULEUR DE TRAIT, portée par les flèches (le losange
  // lui-même n'a pas de couleur propre : c'est une forme « Small If » qui hérite
  // tout de son master). Les flèches d'une même décision partagent une couleur :
  // l'entrée et les une ou deux sorties. On choisit donc la FAMILLE de couleur la
  // mieux représentée autour du losange, puis on le pose sur elle — au point de
  // divergence quand la décision a deux sorties, au plus près sinon.
  async tagDecorativeDiamonds() {
    const { newShapes, newConns } = this;
    const RAYON = 90;          // au-delà, le losange ne « touche » plus rien
    const SEUIL_COUPE = 45;    // le losange est vraiment POSÉ sur la flèche
    const SEUIL_SEUL  = 14;    // décision à une seule sortie : exigence plus stricte
    const coupes = [];

    const connectes = new Set();
    for (const c of newConns) { connectes.add(c.fromId); connectes.add(c.toId); }

    const projeter = (px, py, pts) => {
      let best = Infinity, bx = pts[0].x, by = pts[0].y, frac = 0, seg = 0, total = 0;
      const longs = [];
      for (let i = 0; i < pts.length - 1; i++) {
        const l = Math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y);
        longs.push(l); total += l;
      }
      let parcouru = 0;
      for (let i = 0; i < pts.length - 1; i++) {
        const a = pts[i], b = pts[i + 1];
        const dx = b.x - a.x, dy = b.y - a.y, l2 = dx * dx + dy * dy;
        const t = l2 ? Math.max(0, Math.min(1, ((px - a.x) * dx + (py - a.y) * dy) / l2)) : 0;
        const qx = a.x + t * dx, qy = a.y + t * dy;
        const d = Math.hypot(px - qx, py - qy);
        if (d < best) { best = d; bx = qx; by = qy; seg = i; frac = total ? (parcouru + t * longs[i]) / total : 0; }
        parcouru += longs[i];
      }
      return { dist: best, x: bx, y: by, frac, seg };
    };

    // Point de divergence d'une fourche : dernier sommet commun aux membres.
    const divergence = (membres) => {
      const debut = (membres[0].bundleId || 'f').startsWith('f');
      const prof = Math.min(...membres.map(c => (debut ? c.trunkFrom : c.trunkTo) || 0));
      if (!prof) return null;
      const pts = membres[0].customPath;
      return debut ? pts[prof] : pts[pts.length - 1 - prof];
    };

    let taggés = 0, parCouleur = 0, surFourche = 0;
    for (const D of newShapes) {
      if (D.type !== 'decision' || connectes.has(D.id)) continue;
      const cx = D.x + D.w / 2, cy = D.y + D.h / 2;

      const proches = [];
      for (const c of newConns) {
        if (!c.customPath || c.customPath.length < 2) continue;
        const pr = projeter(cx, cy, c.customPath);
        if (pr.dist <= RAYON) proches.push({ c, pr });
      }
      if (!proches.length) continue;

      // Familles de couleur autour du losange : la mieux représentée gagne
      // (une décision amène au moins une entrée + une sortie de même couleur),
      // à égalité c'est la plus proche.
      const familles = new Map();
      for (const item of proches) {
        const k = item.c._visioColor || '?';
        const f = familles.get(k) || { membres: [], plusProche: Infinity };
        f.membres.push(item);
        f.plusProche = Math.min(f.plusProche, item.pr.dist);
        familles.set(k, f);
      }
      let famille = null;
      for (const [k, f] of familles) {
        if (k === '?') continue;
        if (!famille || f.membres.length > famille.membres.length ||
            (f.membres.length === famille.membres.length && f.plusProche < famille.plusProche)) {
          famille = f;
        }
      }
      const retenus = famille && famille.membres.length ? famille.membres : proches;
      if (famille && famille.membres.length > 1) parCouleur++;

      // Score = distance + pénalité si le losange tombe sur une EXTRÉMITÉ du
      // tracé : au départ d'une activité, toutes ses flèches sortantes passent
      // par le même point, donc « la plus proche » est un tirage au sort. Celle
      // que le losange traverse en son milieu est la bonne.
      const PENALITE_BOUT = 60;
      const score = i => i.pr.dist + ((i.pr.frac < 0.06 || i.pr.frac > 0.94) ? PENALITE_BOUT : 0);
      retenus.sort((a, b) => score(a) - score(b));
      const choisi = retenus[0];
      D.seatConnId = choisi.c.id;
      D.seatFrac = +choisi.pr.frac.toFixed(4);
      taggés++;

      // Deux sorties issues du même tronc : le losange se pose PILE à la
      // bifurcation, c'est là que la décision se lit.
      const paquet = retenus.map(i => i.c).filter(c => c.bundleId === choisi.c.bundleId);
      if (choisi.c.bundleId && paquet.length > 1) {
        const p = divergence(paquet);
        if (p && Math.hypot(p.x - cx, p.y - cy) <= RAYON) {
          const pr = projeter(p.x, p.y, choisi.c.customPath);
          D.seatFrac = +pr.frac.toFixed(4);
          D.x = Math.round(p.x - D.w / 2);
          D.y = Math.round(p.y - D.h / 2);
          surFourche++;
        }
      }

      // Une décision, c'est UNE entrée et une ou deux sorties : on ne coupe que
      // les flèches qui viennent de la MÊME source (le tronc qui se divise).
      // Les autres ne font que passer à côté — les couper fabriquerait des
      // entrées parasites, et c'est ce qui avait fait abandonner l'insertion
      // automatique des losanges dans le flux.
      const traversantes = retenus.filter(i => i.pr.dist <= SEUIL_COUPE &&
                                               i.pr.frac > 0.06 && i.pr.frac < 0.94);
      const parSource = new Map();
      for (const i of traversantes) {
        const k = String(i.c.fromId);
        (parSource.get(k) || parSource.set(k, []).get(k)).push(i);
      }
      let tronc = null;
      for (const groupe of parSource.values()) {
        if (!tronc || groupe.length > tronc.length ||
            (groupe.length === tronc.length &&
             groupe[0].pr.dist < tronc[0].pr.dist)) tronc = groupe;
      }
      // Une seule flèche : on ne coupe que si le losange est vraiment DESSUS.
      if (tronc && (tronc.length > 1 || tronc[0].pr.dist <= SEUIL_SEUL))
        coupes.push({ D, membres: tronc });
    }

    // ── Couper les flèches sur le losange ────────────────────────────────
    // Une décision, c'est UNE entrée et une ou deux sorties. Tant que le
    // losange n'est qu'un décor posé sur N flèches indépendantes, chaque
    // branche redessine le tronc : deux traits presque superposés que rien ne
    // peut aligner parfaitement. En coupant, le tronc n'existe qu'une fois.
    let entrees = 0, sorties = 0;
    const remplacements = new Map();   // ancienne flèche → [entrée, sortie] issues de la coupe
    const dirDepuis = (a, b) => Math.abs(b.x - a.x) >= Math.abs(b.y - a.y)
      ? (b.x >= a.x ? 'right' : 'left') : (b.y >= a.y ? 'bottom' : 'top');

    const MEME_PT = 6;   // deux sommets à moins de 6 px sont « le même point »

    for (const { D, membres: membresInitiaux } of coupes) {
      const cxD0 = D.x + D.w / 2, cyD0 = D.y + D.h / 2;
      const couleur = membresInitiaux[0].c._visioColor;

      // Recalcul sur les flèches ACTUELLES : une flèche traversée par deux
      // losanges a déjà été coupée par le précédent, et c'est sur sa moitié
      // qu'il faut travailler — sinon on recrée une flèche complète en doublon.
      const dispo = newConns.filter(c => !c._remplacée && c.customPath &&
                                         c.customPath.length >= 2 &&
                                         (!couleur || c._visioColor === couleur));
      const candidats = dispo
        .map(c => ({ c, pr: projeter(cxD0, cyD0, c.customPath) }))
        .filter(i => i.pr.dist <= SEUIL_COUPE && i.pr.frac > 0.04 && i.pr.frac < 0.96);
      if (!candidats.length) continue;

      const parSrc = new Map();
      for (const i of candidats) {
        const k = String(i.c.fromId);
        (parSrc.get(k) || parSrc.set(k, []).get(k)).push(i);
      }
      let membres = null;
      for (const g of parSrc.values()) {
        g.sort((a, b) => a.pr.dist - b.pr.dist);
        if (!membres || g.length > membres.length ||
            (g.length === membres.length && g[0].pr.dist < membres[0].pr.dist)) membres = g;
      }
      if (!membres || (membres.length === 1 && membres[0].pr.dist > SEUIL_SEUL)) continue;

      const chemins = membres.map(m => m.c.customPath);

      // Point de DIVERGENCE : dernier sommet commun à toutes les branches. Dans
      // Visio c'est exactement l'angle droit du losange — une décision à deux
      // sorties fait toujours 90° pile entre elles. Couper là (et non chacune à
      // sa propre projection) garantit un tronc unique et des sorties alignées.
      let profondeur = 0;
      if (chemins.length > 1) {
        const mini = Math.min(...chemins.map(p => p.length));
        while (profondeur + 1 < mini) {
          const ref = chemins[0][profondeur + 1];
          const tous = chemins.every(p =>
            Math.hypot(p[profondeur + 1].x - ref.x, p[profondeur + 1].y - ref.y) <= MEME_PT);
          if (!tous) break;
          profondeur++;
        }
      }

      // La bifurcation ne fait foi QUE si elle tombe sous le losange. Deux
      // branches peuvent partager un long tronc depuis leur source commune :
      // couper là déplacerait le losange à l'autre bout de la carto.
      let coupe = null;
      const cxD = D.x + D.w / 2, cyD = D.y + D.h / 2;
      if (chemins.length > 1 && profondeur >= 1) {
        const bif = chemins[0][profondeur];
        if (Math.hypot(bif.x - cxD, bif.y - cyD) <= SEUIL_COUPE)
          coupe = { x: bif.x, y: bif.y };
      }
      if (!coupe) coupe = { x: membres[0].pr.x, y: membres[0].pr.y };

      // Toutes les branches sont coupées au MÊME point : c'est ce qui garantit
      // un tronc unique et, sur une décision à deux sorties, l'angle droit.
      const indices = membres.map(m => {
        const pr = projeter(coupe.x, coupe.y, m.c.customPath);
        return Math.max(1, Math.min(m.c.customPath.length - 1, pr.seg + 1));
      });

      let troncPose = false;
      membres.forEach((m, i) => {
        const c = m.c;
        const idx = Math.max(1, Math.min(c.customPath.length - 1, indices[i]));
        const avant = c.customPath.slice(0, idx).concat([coupe]);
        const apres = [coupe].concat(c.customPath.slice(idx));
        if (avant.length < 2 || apres.length < 2) return;

        if (!troncPose) {
          troncPose = true;
          newConns.push({
            id: this.nextOid++, fromId: c.fromId, toId: D.id,
            fromPortDir: c.fromPortDir, toPortDir: dirDepuis(coupe, avant[avant.length - 2]),
            color: c.color, label: '', style: c.style, routing: 'orthogonal',
            fromPortT: c.fromPortT, customPath: avant, _visioColor: c._visioColor,
          });
          entrees++;
        }
        newConns.push({
          id: this.nextOid++, fromId: D.id, toId: c.toId,
          fromPortDir: dirDepuis(coupe, apres[1]), toPortDir: c.toPortDir,
          color: c.color, label: c.label, style: c.style, routing: 'orthogonal',
          toPortT: c.toPortT, customPath: apres, _visioColor: c._visioColor,
        });
        sorties++;
        c._remplacée = true;
        remplacements.set(c.id, [newConns[newConns.length - 2], newConns[newConns.length - 1]]);
      });

      if (troncPose) {
        // Le losange se cale sur l'angle : son CENTRE est le point de coupe.
        D.x = Math.round(coupe.x - D.w / 2);
        D.y = Math.round(coupe.y - D.h / 2);
        D.seatConnId = null;
        D.seatFrac = null;
      }
    }
    // Un losange rattaché à une flèche qui vient d'être coupée doit suivre la
    // MOITIÉ qui passe encore chez lui ; sinon il pointe dans le vide et l'éditeur
    // le repose sur « la plus proche », c'est-à-dire n'importe laquelle.
    for (const D of newShapes) {
      if (D.type !== 'decision' || !D.seatConnId) continue;
      const cx = D.x + D.w / 2, cy = D.y + D.h / 2;
      // Une moitie peut avoir ete recoupee par un losange suivant : on suit la
      // chaine jusqu a une fleche qui existe encore.
      for (let tour = 0; tour < 6; tour++) {
        const moities = remplacements.get(D.seatConnId);
        if (!moities) break;
        let best = null, bestD = Infinity, bestFrac = 0;
        for (const m of moities) {
          if (!m || !m.customPath || m.customPath.length < 2) continue;
          const pr = projeter(cx, cy, m.customPath);
          if (pr.dist < bestD) { bestD = pr.dist; best = m; bestFrac = pr.frac; }
        }
        if (!best) { D.seatConnId = null; D.seatFrac = null; break; }
        D.seatConnId = best.id;
        D.seatFrac = +bestFrac.toFixed(4);
      }
    }

    for (let i = newConns.length - 1; i >= 0; i--)
      if (newConns[i]._remplacée) newConns.splice(i, 1);
    if (coupes.length)
      console.log(`[VSDX] losanges insérés dans le flux : ${coupes.length} (${entrees} entrée(s), ${sorties} sortie(s))`);
    {
    console.log(`[VSDX] losanges rattachés : ${taggés} (dont ${parCouleur} par une famille de couleur, ${surFourche} posés sur une bifurcation)`);
    this.log(`Losanges rattachés à leur flèche : ${taggés}`);
    }
  }

  // ─── Phase 11: Build groups from Visio container groups ──────────

  buildGroups() {
    const { newShapes, topOfDiagram, leftEdge, SCALE } = this;
    const newGroups  = this.newGroups;
    const groupIdMap = this._groupIdMap = {};

    for (const { id: visioContId, label, abs } of this._containerGroupData) {
      const cLeft   = (abs.pinX - abs.w/2 - leftEdge) * SCALE;
      const cRight  = (abs.pinX + abs.w/2 - leftEdge) * SCALE;
      const cTop    = Math.max(0, (topOfDiagram - (abs.pinY + abs.h/2)) * SCALE);
      const cBottom = Math.max(0, (topOfDiagram - (abs.pinY - abs.h/2)) * SCALE);
      const memberIds = newShapes
        .filter(s => {
          const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
          return cx > cLeft && cx < cRight && cy > cTop && cy < cBottom;
        }).map(s => s.id);
      if (memberIds.length < 2) continue;
      const gid = this.nextOid++;
      groupIdMap[visioContId] = gid;
      newGroups.push({ id: gid, label, shapeIds: memberIds, color: '#b3a0ff' });
    }
  }

  // ─── Phase 12: Splice unconnected decision nodes ─────────────────
  // Some Visio decision diamonds have no <Connect> elements — they are
  // placed visually on a connector line. For each such diamond D, we find
  // connector A→B whose line passes within SPLICE_THRESH of D's center,
  // then replace A→B with A→D + D→B.
  // Filter: LayerMember=3 = "Si petit" visual decorators → excluded.

  spliceDecisions() {
    const { connMap, shapePinAbs, newShapes, _shapeIdMap, _shapeElById } = this;
    const SPLICE_THRESH = 0.6;

    const connSrcSet = new Set(Object.values(connMap).map(e => e.source).filter(Boolean));
    const connTgtSet = new Set(Object.values(connMap).map(e => e.target).filter(Boolean));

    const toPatch = [];
    for (const [visioId, appId] of Object.entries(_shapeIdMap)) {
      const appShape = newShapes.find(s => s.id === appId);
      if (!appShape || appShape.type !== 'decision') continue;
      if (connSrcSet.has(visioId) || connTgtSet.has(visioId)) continue; // already connected
      const abs = shapePinAbs[visioId];
      if (!abs) continue;
      if (abs.w < 0.4 || abs.h < 0.4) continue; // micro-shapes → skip
      toPatch.push({ visioId, pinX: abs.pinX, pinY: abs.pinY });
    }

    let synCtr = 0;
    for (const dec of toPatch) {
      const Dx = dec.pinX, Dy = dec.pinY;
      const realEntries = Object.entries(connMap).filter(([, e]) => !e._origConnId);
      for (const [connId, ends] of realEntries) {
        const sv = ends.source, tv = ends.target;
        if (!sv || !tv || sv === dec.visioId || tv === dec.visioId) continue;
        const sAbs = shapePinAbs[sv], tAbs = shapePinAbs[tv];
        if (!sAbs || !tAbs) continue;
        const Ax = sAbs.pinX, Ay = sAbs.pinY;
        const Bx = tAbs.pinX, By = tAbs.pinY;
        const ABx = Bx - Ax, ABy = By - Ay;
        const len2 = ABx*ABx + ABy*ABy;
        if (len2 < 1e-9) continue;
        const t = ((Dx - Ax)*ABx + (Dy - Ay)*ABy) / len2;
        if (t < 0.05 || t > 0.95) continue;
        const px = Ax + t*ABx, py = Ay + t*ABy;
        if (Math.hypot(Dx - px, Dy - py) >= SPLICE_THRESH) continue;
        // Splice: A→B becomes A→D then D→B. Les DEUX moitiés pointent vers le
        // connecteur d'origine (_origConnId) pour hériter du STYLE (trait/pointillé) ;
        // le label du connecteur n'apparaît qu'une fois (sur D→B) via _suppressLabel.
        delete connMap[connId];
        connMap[`__sp${synCtr++}`] = { source: sv,          target: dec.visioId, _origConnId: connId, _suppressLabel: true };
        connMap[`__sp${synCtr++}`] = { source: dec.visioId, target: tv,          _origConnId: connId };
      }
    }
  }

  // Nudge portT values that are too close on the same endpoint+direction pair.
  // Preserves exact Visio positions and only separates near-duplicates (< MIN_GAP apart).
  // EXCEPTION : deux flèches qui partent EXACTEMENT du même point de connexion
  // Visio sont les branches d'une même fourche. Les écarter casse leur tronc
  // commun — c'est ce qui produisait deux traits parallèles décalés là où la
  // carte d'origine n'en montre qu'un qui se divise.
  _nudgePortConflicts(conns) {
    const MIN_GAP = 0.05;
    const SAME = 1e-4;
    const byKey = {};
    for (const c of conns) {
      for (const [idKey, dirKey, tKey] of [
        [c.fromId, c.fromPortDir, 'fromPortT'],
        [c.toId,   c.toPortDir,   'toPortT'],
      ]) {
        if (c[tKey] === undefined) continue;
        const k = `${idKey}:${dirKey}`;
        if (!byKey[k]) byKey[k] = [];
        byKey[k].push({ c, tKey });
      }
    }
    for (const entries of Object.values(byKey)) {
      if (entries.length <= 1) continue;
      entries.sort((a, b) => a.c[a.tKey] - b.c[b.tKey]);
      for (let i = 1; i < entries.length; i++) {
        const prev = entries[i-1].c[entries[i-1].tKey];
        const cur  = entries[i].c[entries[i].tKey];
        if (Math.abs(cur - prev) <= SAME) continue;   // même point exact → fourche
        if (cur - prev < MIN_GAP) {
          entries[i].c[entries[i].tKey] = Math.min(0.95, prev + MIN_GAP);
        }
      }
    }
  }

  // Wrap a connection label to 2 lines if it's longer than MAX_CHARS.
  // Splits at the space nearest to the midpoint so both halves are balanced.
  static _wrapConnLabel(label, maxChars = 26) {
    if (!label || label.length <= maxChars) return label;
    const mid = Math.floor(label.length / 2);
    let splitAt = -1;
    for (let i = 0; i <= mid; i++) {
      if (label[mid - i] === ' ') { splitAt = mid - i; break; }
      if (mid + i < label.length && label[mid + i] === ' ') { splitAt = mid + i; break; }
    }
    if (splitAt === -1) return label; // no space — leave as-is
    return label.slice(0, splitAt) + '\n' + label.slice(splitAt + 1);
  }

  // ─── Phase 13: Build connections ────────────────────────────────

  // Récupère les connexions « à moitié collées » : certains connecteurs Visio n'ont
  // un <Connect> que d'UN côté (l'autre bout « flotte », mais tombe PILE dans une
  // forme). On infère l'extrémité manquante en cherchant la forme (ou, à défaut, le
  // groupe) dont la boîte Visio contient le point qui flotte. Sans ça, ces connecteurs
  // sont jetés (source/target absent) → flèches et renvois perdus à l'import
  // (mesuré hard.vsdx : renvoi « Spare Parts Stock » isolé, 10 connecteurs jetés).
  _recoverFloatingConnections() {
    const { connMap, shapePinAbs, shapeMap, _shapeIdMap, _groupIdMap } = this;
    const gMap = _groupIdMap || {};
    const cand = [];
    for (const vid in shapePinAbs) {
      const a = shapePinAbs[vid]; if (!a || !a.w) continue;
      const isShape = !!_shapeIdMap[vid], isGroup = !!gMap[vid];
      if (!isShape && !isGroup) continue;
      cand.push({ vid, isShape, x0: a.pinX - a.w / 2, x1: a.pinX + a.w / 2, y0: a.pinY - a.h / 2, y1: a.pinY + a.h / 2, area: a.w * a.h });
    }
    const TOL = 0.4;   // slack Visio : le bout d'un connecteur peut tomber un poil HORS
                       // du bord (points de connexion) → tolérance courte, bien < l'écart
                       // aux groupes voisins (~2,7) pour éviter les faux raccords.
    const distBox = (c, x, y) => {
      const dx = Math.max(c.x0 - x, 0, x - c.x1), dy = Math.max(c.y0 - y, 0, y - c.y1);
      return Math.hypot(dx, dy);
    };
    // forme la plus proche à ≤TOL (plus petite d'abord si ex æquo) ; à défaut, groupe.
    const find = (x, y) => {
      let bestS = null, bestSd = Infinity, bestG = null, bestGd = Infinity;
      for (const c of cand) {
        const d = distBox(c, x, y);
        if (c.isShape) { if (d < bestSd || (d === bestSd && bestS && c.area < bestS.area)) { bestSd = d; bestS = c; } }
        else           { if (d < bestGd) { bestGd = d; bestG = c; } }
      }
      if (bestS && bestSd <= TOL) return bestS.vid;
      if (bestG && bestGd <= TOL) return bestG.vid;
      return null;
    };
    let recovered = 0;
    for (const cid in connMap) {
      const e = connMap[cid];
      if ((e.source && e.target) || cid.startsWith('__sp')) continue;
      const el = (shapeMap[cid] || {}).el; if (!el) continue;
      if (!e.source) {
        const bx = parseFloat(this.vCell(el, 'BeginX') || 'NaN'), by = parseFloat(this.vCell(el, 'BeginY') || 'NaN');
        if (!isNaN(bx) && !isNaN(by)) { const v = find(bx, by); if (v) { e.source = v; recovered++; } }
      }
      if (!e.target) {
        const ex = parseFloat(this.vCell(el, 'EndX') || 'NaN'), ey = parseFloat(this.vCell(el, 'EndY') || 'NaN');
        if (!isNaN(ex) && !isNaN(ey)) { const v = find(ex, ey); if (v) { e.target = v; recovered++; } }
      }
    }
    if (recovered) this.log(`Connexions récupérées (extrémité flottante) : ${recovered}`);
  }

  async buildConnections() {
    this.log('Reconstruction des connexions…');
    this._recoverFloatingConnections();
    const { connMap, shapePinAbs, shapeMap, newShapes, newGroups,
            _shapeIdMap, _groupIdMap, topOfDiagram, leftEdge, SCALE } = this;
    const OPP = { right:'left', left:'right', top:'bottom', bottom:'top' };

    function portDirFromPt(px, py, abs) {
      const dR = Math.abs(px - (abs.pinX + abs.w/2));
      const dL = Math.abs(px - (abs.pinX - abs.w/2));
      const dT = Math.abs(py - (abs.pinY + abs.h/2));
      const dB = Math.abs(py - (abs.pinY - abs.h/2));
      const m = Math.min(dR, dL, dT, dB);
      return m === dR ? 'right' : m === dL ? 'left' : m === dT ? 'top' : 'bottom';
    }

    function computePortT(vx, vy, abs, dir) {
      const sL = (abs.pinX - abs.w/2 - leftEdge) * SCALE;
      const sT = (topOfDiagram - (abs.pinY + abs.h/2)) * SCALE;
      const sW = abs.w * SCALE, sH = abs.h * SCALE;
      const sx = (vx - leftEdge) * SCALE, sy = (topOfDiagram - vy) * SCALE;
      const t  = (dir === 'left' || dir === 'right') ? (sy - sT) / sH : (sx - sL) / sW;
      return Math.min(0.95, Math.max(0.05, t));
    }

    // Lit la polyligne d'un connecteur en coordonnées page Visio.
    //
    // Deux erreurs corrigées ici, à l'origine de la quasi-totalité des dégâts
    // à l'import :
    //  • Les Row d'une Section Geometry sont exprimées dans le repère LOCAL du
    //    connecteur, dont l'origine est Pin − LocPin — et NON le point Begin.
    //    LocPinY vaut la demi-hauteur du connecteur : on décalait donc chaque
    //    tracé de quelques millimètres, d'où les flèches en biais.
    //  • Une Cell X ou Y absente d'une Row est HÉRITÉE du master. On jetait la
    //    Row entière : sur ce fichier client, 60 % des connecteurs perdaient
    //    ainsi leur géométrie et retombaient sur le routage automatique.
    const readConnGeom = (el, connVisioId, bx, by, ex, ey) => {
      const abs = shapePinAbs[connVisioId];
      if (!abs) return [];
      const cw = parseFloat(this.vCell(el, 'Width')  || '0');
      const ch = parseFloat(this.vCell(el, 'Height') || '0');
      const lpXv = this.vCell(el, 'LocPinX'), lpYv = this.vCell(el, 'LocPinY');
      const lpX = lpXv !== null ? parseFloat(lpXv) : cw / 2;
      const lpY = lpYv !== null ? parseFloat(lpYv) : ch / 2;
      const ox = abs.pinX - (isNaN(lpX) ? 0 : lpX);
      const oy = abs.pinY - (isNaN(lpY) ? 0 : lpY);

      let sec = null;
      for (const child of Array.from(el.childNodes)) {
        if (child.nodeType !== 1 || child.localName !== 'Section') continue;
        if (child.getAttribute('N') !== 'Geometry') continue;
        if (this.vCell(child, 'NoShow') === '1') continue;
        sec = child; break;
      }
      if (!sec) return [];

      const rows = [];
      for (const row of Array.from(sec.childNodes)) {
        if (row.nodeType !== 1 || row.localName !== 'Row') continue;
        if (row.getAttribute('Del') === '1') continue;       // Row supprimée par Visio
        if (!VsdxImporter.VERTEX_ROW[row.getAttribute('T')]) continue;
        let rx = null, ry = null;
        for (const cell of Array.from(row.childNodes)) {
          if (cell.nodeType !== 1 || cell.localName !== 'Cell') continue;
          const N = cell.getAttribute('N');
          if (N === 'X') { const v = parseFloat(cell.getAttribute('V')); if (!isNaN(v)) rx = v; }
          if (N === 'Y') { const v = parseFloat(cell.getAttribute('V')); if (!isNaN(v)) ry = v; }
        }
        rows.push({ x: rx, y: ry });
      }
      if (rows.length === 0) return [];

      const last = rows.length - 1;
      if (rows[0].x === null)    rows[0].x    = bx - ox;
      if (rows[0].y === null)    rows[0].y    = by - oy;
      if (rows[last].x === null) rows[last].x = ex - ox;
      if (rows[last].y === null) rows[last].y = ey - oy;
      for (let i = 1; i <= last; i++) {
        if (rows[i].x === null) rows[i].x = rows[i-1].x;
        if (rows[i].y === null) rows[i].y = rows[i-1].y;
      }

      const pts = rows.map(p => ({ x: p.x + ox, y: p.y + oy }));
      // MoveTo entièrement héritée → le vrai départ est Begin.
      if (Math.hypot(pts[0].x - bx, pts[0].y - by) > 0.02) pts.unshift({ x: bx, y: by });
      const lp = pts[pts.length - 1];
      if (Math.hypot(lp.x - ex, lp.y - ey) > 0.02) pts.push({ x: ex, y: ey });

      const out = [pts[0]];
      for (let i = 1; i < pts.length; i++)
        if (Math.hypot(pts[i].x - out[out.length-1].x, pts[i].y - out[out.length-1].y) > 0.004)
          out.push(pts[i]);
      if (out.length < 2) return [];
      // Garde-fou : un sommet très loin du couloir Begin→End = repère mal lu.
      const span = Math.hypot(ex - bx, ey - by) + 4;
      for (const p of out)
        if (Math.hypot(p.x - bx, p.y - by) > span * 3 + 10) return [];
      return out;
    };

    // Wrap visioToScreen pour appliquer le bandShift sur Y (cohérent avec
    // l'ajustement appliqué dans importActivities — sinon les customPath
    // des connecteurs partent du milieu d'une bande quand les shapes ont
    // été décalés vers le bas par l'inflation min 80).
    const self = this;
    function visioToScreen(vx, vy) {
      const ny = (topOfDiagram - vy) * SCALE;
      return { x: (vx - leftEdge) * SCALE, y: ny + self._bandShiftFor(ny) };
    }

    const snapToEdge = (s, dir, t, halo) => this.snapEdge(s, dir, t, halo);

    const newConns = this.newConns;
    for (const [connId, ends] of Object.entries(connMap)) {
      const { source: sv, target: tv } = ends;
      if (!sv || !tv) continue;
      const fromId = _shapeIdMap[sv] || _groupIdMap[sv];
      const toId   = _shapeIdMap[tv] || _groupIdMap[tv];
      if (!fromId || !toId) continue;
      const srcShape = newShapes.find(s => s.id === fromId) || newGroups.find(g => g.id === fromId);

      const connItem = shapeMap[ends._origConnId || connId];
      const connLabel = (connItem && !ends._suppressLabel) ? (this.vText(connItem.el) || '') : '';
      const connMid   = connItem ? connItem.el.getAttribute('Master') : null;
      const masterLp  = connMid ? (await this.getMasterInfo(connMid)).linePattern : 1;
      const lpStr     = connItem ? (this.vCellDeep(connItem.el, 'LinePattern') || String(masterLp)) : '1';
      const isDashed  = parseInt(lpStr) > 1;

      const isSynthetic = connId.startsWith('__sp');
      const sAbs = shapePinAbs[sv], tAbs = shapePinAbs[tv];
      let fromPortDir = 'right', toPortDir = 'left';
      let fromPortT, toPortT, customPath;

      if (!isSynthetic && connItem && sAbs && tAbs) {
        const ce = connItem.el;
        const bx = parseFloat(this.vCell(ce, 'BeginX') || '0');
        const by = parseFloat(this.vCell(ce, 'BeginY') || '0');
        const ex = parseFloat(this.vCell(ce, 'EndX')   || '0');
        const ey = parseFloat(this.vCell(ce, 'EndY')   || '0');
        if (bx || by) { fromPortDir = portDirFromPt(bx, by, sAbs); fromPortT = computePortT(bx, by, sAbs, fromPortDir); }
        if (ex || ey) { toPortDir   = portDirFromPt(ex, ey, tAbs); toPortT   = computePortT(ex, ey, tAbs, toPortDir); }
        const geomVis = readConnGeom(ce, connId, bx, by, ex, ey);
        if (geomVis.length >= 2) {
          const srcS = newShapes.find(s => s.id === fromId);
          const tgtS = newShapes.find(s => s.id === toId);
          const pts  = geomVis.map(p => visioToScreen(p.x, p.y));
          if (srcS) pts[0]            = snapToEdge(srcS, fromPortDir, fromPortT);
          if (tgtS) pts[pts.length-1] = snapToEdge(tgtS, toPortDir,   toPortT);
          customPath = this.orthoClean(pts, fromPortDir, toPortDir);
        }
      } else if (sAbs && tAbs) {
        const dx = tAbs.pinX - sAbs.pinX, dy = tAbs.pinY - sAbs.pinY;
        fromPortDir = Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'top' : 'bottom');
        toPortDir   = OPP[fromPortDir];
      }

      const visioColor = connItem ? await this.visioLineColor(connItem.el) : null;
      const connObj = {
        id: this.nextOid++, fromId, toId, fromPortDir, toPortDir,
        color: srcShape ? srcShape.color : '#567460',
        label: VsdxImporter._wrapConnLabel(connLabel), style: isDashed ? 'dashed' : 'solid', routing: 'orthogonal',
      };
      if (fromPortT !== undefined) connObj.fromPortT = fromPortT;
      if (toPortT   !== undefined) connObj.toPortT   = toPortT;
      if (customPath)              connObj.customPath = customPath;
      // Sert au rattachement des losanges (phase suivante) ; retiré avant sauvegarde.
      if (visioColor)              connObj._visioColor = visioColor;
      if (!isSynthetic && connItem) connObj._visioId = ends._origConnId || connId;
      newConns.push(connObj);
    }

    // Post-process: nudge portT values that are too close on the same endpoint+direction.
    // We KEEP the exact Visio positions (pixel-perfect) and only separate near-duplicates.
    // Deleting portT entirely would lose Visio precision and cause connections to overlap.
    this._nudgePortConflicts(newConns);
  }

  // ─── Phase 14: Remove separator bands ────────────────────────────
  // Bands whose labels are just numbers or "Band N" / "Bande N" are
  // Visio layout separators with no semantic meaning.

  cleanupBands() {
    this.log('Nettoyage des bandes séparateurs…');
    const { newBands, newShapes } = this;
    const bRanges = [];
    { let y0 = 0; for (const b of newBands) { bRanges.push({ y0, y1: y0+b.height, band: b }); y0 += b.height; } }
    const SEP_RE = /^(bands?\s+|band[ae]s?\s+|bande?s?\s+)?\d+\s*$/i;
    const toRemove = bRanges.filter(({ band }) => SEP_RE.test(band.label.trim()));
    toRemove.sort((a, b) => b.y0 - a.y0); // bottom-up to avoid cascade shifts
    for (const { band, y0: bandStart } of toRemove) {
      const h = band.height;
      newBands.splice(newBands.indexOf(band), 1);
      for (const s of newShapes) { if (s.y + s.h/2 >= bandStart + h) s.y -= h; }
      // Même décalage sur les tracés Visio, sinon les flèches se détachent des
      // formes qu'on vient de remonter (stretchBands le fait déjà de son côté).
      for (const c of this.newConns) {
        if (!c.customPath) continue;
        for (const pt of c.customPath) if (pt.y >= bandStart + h) pt.y -= h;
      }
    }
    newBands.forEach((b, i) => { b.id = i + 1; });
    for (const s of newShapes) { if (s.y < 0) s.y = 0; }
  }

  // ─── Phase 15: Stretch bands to contain all shapes ───────────────
  // When a band must grow to fit its shapes, we also shift down every
  // shape and customPath point sitting BELOW it by the same delta — otherwise
  // shapes from lower bands end up visually inside the stretched band
  // (e.g. "Definition of Strategic Priorities" landing in Maintenance instead
  // of Piloting because Logistic was stretched above).

  stretchBands() {
    let y0 = 0;
    for (let i = 0; i < this.newBands.length; i++) {
      const band = this.newBands[i];
      const bandTop = y0;
      const bandBottom = y0 + band.height;
      const inBand = this.newShapes.filter(s => {
        const m = s.y + s.h/2;
        return m >= bandTop && m < bandBottom;
      });
      const bot = inBand.reduce((m, s) => Math.max(m, s.y + s.h), 0);
      const needed = bot + 20 - bandTop;
      if (needed > band.height) {
        const delta = needed - band.height;
        // Push everything that lives below the band's CURRENT bottom edge down by delta
        for (const s of this.newShapes) {
          if (s.y + s.h/2 >= bandBottom) s.y += delta;
        }
        for (const c of this.newConns) {
          if (!c.customPath) continue;
          for (const pt of c.customPath) {
            if (pt.y >= bandBottom) pt.y += delta;
          }
        }
        band.height = needed;
      }
      y0 += band.height;
    }
  }

  // Point d'ancrage d'une flèche sur le bord d'une forme. Les losanges se
  // branchent toujours sur la pointe — même règle que spreadPort côté renderer,
  // sinon le tracé importé démarre à côté de la flèche affichée.
  snapEdge(sh, dir, t, halo) {
    const h = halo !== undefined ? halo : (sh.type === 'process' ? 7 : 0);
    const T = t !== undefined ? t : 0.5;
    const cx = sh.x + sh.w / 2, cy = sh.y + sh.h / 2;
    if (sh.type === 'decision') {
      if (dir === 'right')  return { x: sh.x + sh.w, y: cy };
      if (dir === 'left')   return { x: sh.x,        y: cy };
      if (dir === 'top')    return { x: cx,          y: sh.y };
      if (dir === 'bottom') return { x: cx,          y: sh.y + sh.h };
      return { x: cx, y: cy };
    }
    switch (dir) {
      case 'right':  return { x: sh.x + sh.w + h, y: sh.y + sh.h * T };
      case 'left':   return { x: sh.x - h,        y: sh.y + sh.h * T };
      case 'top':    return { x: sh.x + sh.w * T, y: sh.y - h };
      case 'bottom': return { x: sh.x + sh.w * T, y: sh.y + sh.h + h };
      default:       return { x: cx, y: cy };
    }
  }

  // Ré-équerre une polyligne. Les coordonnées Visio portent du bruit flottant
  // (1e-15) et les deux extrémités ont été replacées sur les ports réels : sans
  // cette passe, les flèches partent de quelques pixels en biais sur toute leur
  // longueur — ce que l'utilisateur voit comme « des traits pas droits ».
  orthoClean(pts, fdir, tdir) {
    const EPS = 4.5;
    const vert = d => d === 'top' || d === 'bottom';
    let p = pts.map(q => ({ x: q.x, y: q.y }));
    const N = p.length;
    if (N < 2) return pts;

    for (let i = 2; i < N - 1; i++) {
      const dx = Math.abs(p[i].x - p[i-1].x), dy = Math.abs(p[i].y - p[i-1].y);
      if (dx <= dy && dx < EPS) p[i].x = p[i-1].x;
      else if (dy < dx && dy < EPS) p[i].y = p[i-1].y;
    }

    // Raccord des extrémités : petit écart → on aligne ; gros écart → vrai coude.
    if (N === 2) {
      const dx = p[1].x - p[0].x, dy = p[1].y - p[0].y;
      if (Math.abs(dx) < Math.abs(dy) && Math.abs(dx) < EPS) { const m = (p[0].x + p[1].x)/2; p[0].x = m; p[1].x = m; }
      else if (Math.abs(dy) < Math.abs(dx) && Math.abs(dy) < EPS) { const m = (p[0].y + p[1].y)/2; p[0].y = m; p[1].y = m; }
      else if (Math.abs(dx) > EPS && Math.abs(dy) > EPS)
        p = vert(fdir) ? [p[0], { x: p[0].x, y: p[1].y }, p[1]]
                       : [p[0], { x: p[1].x, y: p[0].y }, p[1]];
    } else {
      const fv = vert(fdir);
      const off0 = fv ? Math.abs(p[1].x - p[0].x) : Math.abs(p[1].y - p[0].y);
      if (off0 <= EPS) { if (fv) p[1].x = p[0].x; else p[1].y = p[0].y; }
      else p.splice(1, 0, fv ? { x: p[0].x, y: p[1].y } : { x: p[1].x, y: p[0].y });

      const m = p.length, tv = vert(tdir);
      const offN = tv ? Math.abs(p[m-2].x - p[m-1].x) : Math.abs(p[m-2].y - p[m-1].y);
      if (offN <= EPS) { if (tv) p[m-2].x = p[m-1].x; else p[m-2].y = p[m-1].y; }
      else p.splice(m-1, 0, tv ? { x: p[m-1].x, y: p[m-2].y } : { x: p[m-2].x, y: p[m-1].y });
    }

    const out = [p[0]];
    for (let i = 1; i < p.length; i++) {
      const prev = out[out.length-1];
      if (Math.hypot(p[i].x - prev.x, p[i].y - prev.y) < 0.5) continue;
      out.push(p[i]);
    }
    for (let i = 1; i < out.length - 1; ) {
      const a = out[i-1], b = out[i], c = out[i+1];
      const cross = (b.x-a.x)*(c.y-a.y) - (b.y-a.y)*(c.x-a.x);
      if (Math.abs(cross) < 1) out.splice(i, 1); else i++;
    }
    // Résidus de quelques pixels : on autorise le glissement des extrémités LE
    // LONG du bord de la forme. Invisible, et ça évite les longues verticales
    // qui penchent de 3 px.
    for (let i = out.length - 1; i >= 1; i--) {
      const dx = Math.abs(out[i].x - out[i-1].x), dy = Math.abs(out[i].y - out[i-1].y);
      if (dx > 0 && dx <= EPS && dx < dy) out[i-1].x = out[i].x;
      else if (dy > 0 && dy <= EPS && dy < dx) out[i-1].y = out[i].y;
    }
    return out.length >= 2 ? out : pts;
  }

  // ─── Phase 17: Ré-ancrage final des tracés ───────────────────────
  // cleanupBands / antiOverlap / stretchBands bougent les formes APRÈS la
  // construction des connexions. On recolle donc les deux extrémités de chaque
  // tracé Visio sur les bords définitifs, puis on ré-équerre.

  finalizeConnPaths() {
    const byId = {};
    for (const sh of this.newShapes) byId[sh.id] = sh;
    for (const c of this.newConns) {
      if (!c.customPath || c.customPath.length < 2) continue;
      const f = byId[c.fromId], t = byId[c.toId];
      const pts = c.customPath.map(p => ({ x: p.x, y: p.y }));
      if (f) pts[0]              = this.snapEdge(f, c.fromPortDir, c.fromPortT);
      if (t) pts[pts.length - 1] = this.snapEdge(t, c.toPortDir,   c.toPortT);
      c.customPath = this.orthoClean(pts, c.fromPortDir, c.toPortDir);
    }
  }

  // ─── Phase 18: Multi-liens (fourches et fusions) ─────────────────
  // Visio dessine « une flèche qui se divise en deux » comme N connecteurs qui
  // partagent leurs premiers sommets — le tronc — avant de diverger. Lus
  // littéralement, ces troncs deviennent N polylignes presque, mais pas tout à
  // fait, identiques : le renderer les traite alors comme N flèches distinctes
  // et les écarte, d'où la bouillie de traits superposés au départ des
  // losanges. On aligne ici chaque portion commune sur une polyligne unique et
  // on marque les membres, pour qu'une fourche s'affiche comme UN tronc et ses
  // branches. Idem en sens inverse pour les fusions.

  bundleMultiLinks() {
    const TOL = 7;            // px — deux sommets aussi proches sont « le même »
    const conns = this.newConns.filter(c => c.customPath && c.customPath.length >= 2);
    let seq = 0;

    const clusters = (list, fromEnd) => {
      const buckets = {};
      for (const c of list) {
        const k = fromEnd ? `${c.fromId}|${c.fromPortDir}` : `${c.toId}|${c.toPortDir}`;
        (buckets[k] = buckets[k] || []).push(c);
      }
      const out = [];
      for (const group of Object.values(buckets)) {
        const cls = [];
        for (const c of group) {
          const p = fromEnd ? c.customPath[0] : c.customPath[c.customPath.length - 1];
          let cl = cls.find(cl => Math.hypot(cl.x - p.x, cl.y - p.y) <= TOL);
          if (!cl) { cl = { x: p.x, y: p.y, list: [] }; cls.push(cl); }
          cl.list.push(c);
        }
        for (const cl of cls) if (cl.list.length >= 2) out.push(cl.list);
      }
      return out;
    };

    const snapRun = (members, forward, bundleId) => {
      const at = (c, i) => forward ? c.customPath[i] : c.customPath[c.customPath.length - 1 - i];
      const walk = (list, idx) => {
        // ne jamais absorber la propre extrémité d'un connecteur dans un tronc
        const alive = list.filter(c => idx < c.customPath.length - 1);
        if (alive.length < 2) return;
        const groups = [];
        for (const c of alive) {
          const p = at(c, idx);
          let g = groups.find(g => Math.hypot(g.x - p.x, g.y - p.y) <= TOL);
          if (!g) { g = { x: p.x, y: p.y, list: [] }; groups.push(g); }
          g.list.push(c);
        }
        for (const g of groups) {
          if (g.list.length < 2) continue;
          let sx = 0, sy = 0;
          for (const c of g.list) { const p = at(c, idx); sx += p.x; sy += p.y; }
          const ax = sx / g.list.length, ay = sy / g.list.length;
          for (const c of g.list) {
            const p = at(c, idx); p.x = ax; p.y = ay;
            if (forward) c.trunkFrom = Math.max(c.trunkFrom || 0, idx);
            else         c.trunkTo   = Math.max(c.trunkTo   || 0, idx);
            c.bundleId = bundleId;
          }
          walk(g.list, idx + 1);
        }
      };
      walk(members, 0);
    };

    for (const m of clusters(conns, true))  snapRun(m, true,  `f${seq++}`);
    for (const m of clusters(conns, false)) snapRun(m, false, `t${seq++}`);
  }

  // ─── Phase 16: Anti-overlap light pass ───────────────────────────

  antiOverlap() {
    const { newShapes } = this;
    const INDEX_W_SVG = 140;
    for (let iter = 0; iter < 80; iter++) {
      let moved = false;
      for (let i = 0; i < newShapes.length; i++) {
        for (let j = i+1; j < newShapes.length; j++) {
          const a = newShapes[i], b = newShapes[j];
          // Inclure le halo visuel des shapes "process" (7 px de chaque côté)
          // pour éviter que les auréoles se chevauchent visuellement.
          const haloA = a.type === 'process' ? 7 : 0;
          const haloB = b.type === 'process' ? 7 : 0;
          const gap   = haloA + haloB + 2; // +2 px de respiration
          const ovX = Math.min(a.x+a.w, b.x+b.w) + gap - Math.max(a.x, b.x);
          const ovY = Math.min(a.y+a.h, b.y+b.h) + gap - Math.max(a.y, b.y);
          if (ovX <= 0 || ovY <= 0) continue;
          if (ovX <= ovY) {
            const half = ovX / 2;
            if (a.x + a.w/2 <= b.x + b.w/2) { a.x -= half; b.x += half; }
            else { a.x += half; b.x -= half; }
          } else {
            const half = ovY / 2;
            if (a.y + a.h/2 <= b.y + b.h/2) { a.y -= half; b.y += half; }
            else { a.y += half; b.y -= half; }
          }
          a.x = Math.max(INDEX_W_SVG + 4, a.x);
          b.x = Math.max(INDEX_W_SVG + 4, b.x);
          moved = true;
        }
      }
      if (!moved) break;
    }
  }

  // ─── Orchestrator ────────────────────────────────────────────────
  // Runs all phases in order. Returns data ready to apply to state.
  // onOrphans(orphans) is an optional async callback that receives the
  // list of unlabelled disconnected shapes and returns 'clean'|'keep'|'cancel'.

  async parse(onOrphans, opts = {}) {
    await this.parseMasters();
    await this.parsePage();
    await this.prefetchMasters();
    this.computeAbsCoords();
    this.buildConnMap();
    this.identifyContainers();
    this.buildBands();
    this.detectContainerGroups();
    this.importActivities();
    this.applyLayoutCorrections();
    this.buildGroups();
    // spliceDecisions is opt-in: enables it for diagnostic tools without
    // affecting the editor's connection topology.
    if (opts.spliceDecisions) this.spliceDecisions();
    await this.buildConnections();
    await this.tagDecorativeDiamonds();
    this.cleanupBands();

    // ── Orphan handling (empty + unconnected shapes) ──
    if (onOrphans) {
      const connectedIds = new Set([
        ...this.newConns.map(c => c.fromId),
        ...this.newConns.map(c => c.toId),
      ]);
      // Decision shapes are intentionally unconnected (placed visually on arrows).
      const orphans = this.newShapes.filter(s => (!s.label || !s.label.trim()) && !connectedIds.has(s.id) && s.type !== 'decision');
      if (orphans.length > 0) {
        const choice = await onOrphans(orphans);
        if (choice === 'cancel') return null; // caller handles UI
        if (choice === 'clean') {
          const orphanIds = new Set(orphans.map(s => s.id));
          orphans.forEach(s => this.newShapes.splice(this.newShapes.indexOf(s), 1));
          for (const g of this.newGroups)
            if (g.shapeIds) g.shapeIds = g.shapeIds.filter(id => !orphanIds.has(id));
        }
      }
    }

    this.antiOverlap();   // résoudre les chevauchements avant d'étirer les bandes
    this.stretchBands();  // étirer les bandes pour contenir les shapes repositionnés
    this.finalizeConnPaths(); // recoller les tracés Visio sur les bords définitifs
    this.bundleMultiLinks();  // fusionner les troncs des fourches / fusions

    // Shift from importer space (y=0 at top of first band) to editor space
    // (y=-200 at top of first band, matching BAND_Y_START in renderBands/getBandForY).
    // All internal layout passes use y=0 as reference; this is the only place
    // the offset needs to be applied.
    const BAND_Y_START = -200;
    for (const s of this.newShapes) s.y += BAND_Y_START;
    for (const c of this.newConns) {
      if (c.customPath) for (const pt of c.customPath) pt.y += BAND_Y_START;
    }

    return {
      bands:       this.newBands,
      shapes:      this.newShapes,
      connections: this.newConns,
      groups:      this.newGroups,
      nextOid:     this.nextOid,
    };
  }
}

// ── Shape type detection (extracted from editor.js for modularity) ───────────
// Maps a Visio master name + geometry flags to our OptiqCarto shape types:
// 'process' | 'start-end' | 'special' | 'decision'
// Check order: decision → subprocess → stadium → ellipse → default process
// Stadium is checked BEFORE ellipse-by-name so master names like "External
// process oval" map to 'process' (with subtype 'external'), not to start-end.
function detectShapeType(masterName, visioType, isEllipse, isDiamond, isSubprocess, isStadium) {
  const mn = (masterName || '')
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[-_/]/g, ' ')
    .replace(/\s+/g, ' ').trim();

  // 1. Decision / diamond
  if (/\b(decision|diamond|gateway|exclusive|parallel|condition|conditional|losange|branchement|rhombus|si grand|si petit|big if|small if)\b/.test(mn)
      || mn === 'conditional' || mn === 'decision') return 'decision';
  if (isDiamond) return 'decision';

  // 2. Stadium / capsule — checked BEFORE name-based off-page check so that
  //    "Goto X" masters that have capsule geometry (2L+2A) are correctly
  //    classified as external process, not as off-page subprocess.
  if (isStadium) return 'process';

  // 3. Off-page connectors → subprocess style (only if not a stadium)
  if (/\bgot[ot]+\b|\bext\.?\s*ret\b|\bext\.?\s*return\b|\baller\s+[aà]\b|\bautre\s+carte\b/.test(mn)) return 'special';

  // 4. Subprocess — by geometry (wavy bottom, multiple sections, multiple paths)
  if (isSubprocess) return 'special';
  if (/\b(subprocess|sub process|predefined|processus predefini|activite partielle|sous activite|sous processus|sous tache|tache multiple|multi instance|callout|offpage|off page)\b/.test(mn)) return 'special';

  // 5. Start/end — oval/circle shapes (isEllipse now means "pure arc shape")
  if (/\b(terminator|oval|ellipse|circle|event|rond|cercle|ronde|circulaire)\b/.test(mn)
      || mn === 'start' || mn === 'end'
      || mn.includes('start end') || mn.includes('debut fin') || mn.includes('start/end')
      || isEllipse) return 'start-end';

  // 6. Visio Group that is not a swimlane → subprocess style
  if (visioType === 'Group') return 'special';

  return 'process';
}

// ── Public entry point ────────────────────────────────────────────
// Usage: const result = await vsdxParse(file, setStatus, onOrphans)
async function vsdxParse(file, onProgress, onOrphans, opts = {}) {
  const zip = await JSZip.loadAsync(file);
  const importer = new VsdxImporter(zip, onProgress);
  return await importer.parse(onOrphans, opts);
}
