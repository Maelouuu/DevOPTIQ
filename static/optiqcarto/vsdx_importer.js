/* ══════════════════════════════════════════════════════════════════
   VsdxImporter — pure Visio XML → carto data (no DOM/state mutation)
   Entry point: vsdxParse(file, onProgress, onOrphans?)
   Returns Promise<{ bands, shapes, connections, groups }>
   ══════════════════════════════════════════════════════════════════ */

class VsdxImporter {
  constructor(zip, onProgress) {
    this.zip  = zip;
    this.log  = onProgress || (() => {});
    this._p   = new DOMParser();

    // Master lookups
    this.masterIdToName      = {};
    this.masterIdToFile      = {};
    this.masterInfoCache     = {};
    this.masterSubShapeFills = {}; // masterId → { subShapeId → fillColor }

    // Debug report (null unless debugMode=true in vsdxParse)
    this.debug = null;

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

  // ─── Debug helper ────────────────────────────────────────────────
  _dlog(level, msg) { if (this.debug) this.debug[level](msg); }

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

  // A color is "washed out" if it's near-white or desaturated light gray
  isWashedOut(hex) {
    if (!hex || !hex.startsWith('#') || hex.length < 7) return true;
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    const lum = (r*299 + g*587 + b*114) / 1000;
    if (lum > 240) return true; // near-white → always washed
    const max = Math.max(r,g,b), min = Math.min(r,g,b);
    const sat = max === 0 ? 0 : (max - min) / max;
    return lum > 210 && sat < 0.25; // washed only if unsaturated AND very light
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
                       isStadium: false, isWavyBottom: false, aspect: 1, fillColor: null };
    if (!mid) return DEFAULTS;
    if (this.masterInfoCache[mid]) return this.masterInfoCache[mid];
    const fpath = this.masterIdToFile[mid];
    if (!fpath) return this.masterInfoCache[mid] = { ...DEFAULTS };
    try {
      const xml = await this.zip.file(fpath).async('text');
      const doc = this.parseXml(xml);

      // ── Dimensions + style du shape primaire ──
      let bw, bh, lp = 1, fp = 1, fillColor = null, rounding = 0;
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
        // Cellule Rounding : Visio arrondit les coins via propriété de style (pas des arcs
        // dans la géométrie). Une valeur élevée (≥ 30 % de la petite dim.) crée l'aspect
        // "activité externe" (côtés en parenthèses) sans aucun EllipticalArcTo dans la geom.
        const rv = this.vCell(s, 'Rounding');
        if (rv) rounding = Math.max(rounding, parseFloat(rv) || 0);
        if (bw && bh) break;
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

      // Collect all sub-shape fills (indexed by shape ID) for _extractLaneFill fallback.
      // Needed when a lane child has no explicit page-level FillForegnd and inherits
      // its color from the master stencil (e.g. 'couloir color' master=8 in hard.vsdx).
      const subFills = {};
      for (const s of doc.getElementsByTagName('Shape')) {
        const sid = s.getAttribute('ID');
        const fc  = this.vCell(s, 'FillForegnd');
        if (sid && fc && fc.startsWith('#')) subFills[sid] = fc;
      }
      this.masterSubShapeFills[mid] = subFills;

      return this.masterInfoCache[mid] = {
        w: bw || 0.9449, h: bh || 0.7087,
        linePattern: lp, fillPattern: fp, fillColor,
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
    this.bandShifts     = [];
    this.laneIdToBandInfo = {}; // lane_xml_id → { bandIdx (0-based), abs, bandH }

    if (lanes.length === 0) {
      newBands.push({ id: 1, label: 'Activités', color: '#22c55e', fontSize: 22, height: 500 });
      return;
    }

    let ourCum = 0;
    for (const { el: s, abs, id: laneId } of lanes) {
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
        this._dlog('info', `Lane ID=${laneId} "${label}" ignorée (légende)`);
        continue;
      }

      // laneIdToBandInfo: used by importActivities to place shapes via XML parent chain
      // instead of coordinate arithmetic (100% reliable band assignment).
      this.laneIdToBandInfo[laneId] = { bandIdx: newBands.length, abs, bandH };
      this.bandShifts.push({ naturalTop, naturalBottom, shift: ourCum - naturalTop });
      ourCum += bandH;

      const bandDisplayIdx = newBands.length + 1;
      const usedFallback   = this.isWashedOut(fill);
      const color = usedFallback ? FALLBACK_COLORS[bandDisplayIdx % FALLBACK_COLORS.length] : fill;
      const displayLabel   = label || `Bande ${bandDisplayIdx}`;
      newBands.push({ id: bandDisplayIdx, label: displayLabel, color, fontSize: 22, height: bandH });

      if (usedFallback) this._dlog('warn', `"${displayLabel}" [${color}] h=${bandH}px — couleur Visio absente, fallback appliqué`);
      else              this._dlog('ok',   `"${displayLabel}" [${color}] h=${bandH}px`);
    }

    if (this.debug) this._dlog('info', `${newBands.length} bandes créées — pageMaxW=${this.pageMaxW.toFixed(2)}"`);
  }

  // Build nearestLaneOf[shapeId] = laneXmlId — walks the parent chain of every
  // shape to find its closest swimlane ancestor. Used in importActivities to
  // assign shapes to bands via the XML hierarchy (avoids coordinate arithmetic).
  buildNearestLaneMap() {
    const parentOf = {};
    for (const { id, parentId } of this.allShapes) parentOf[id] = parentId;

    this.nearestLaneOf = {};
    for (const { id } of this.allShapes) {
      let cur = parentOf[id];
      while (cur) {
        if (this.laneIdToBandInfo[cur]) { this.nearestLaneOf[id] = cur; break; }
        cur = parentOf[cur];
      }
    }
  }

  // Collect and sort swimlane elements (large container groups, top→bottom).
  // Excludes the outer Pool/CFF container (parent of swimlanes) which would otherwise
  // be inserted between real lanes (its pinY = diagram center) and corrupt band shifts.
  // Deduplicates separator slivers that are too close together.
  _collectLanes(allShapes, containerIds, shapePinAbs, pageMaxW) {
    // Containers that are direct parents of other containers = Pool/outer frame, not lanes.
    const poolIds = new Set();
    for (const { id, parentId } of allShapes)
      if (containerIds.has(id) && parentId && containerIds.has(parentId))
        poolIds.add(parentId);

    const laneList = [];
    for (const { el: s, id } of allShapes) {
      if (!containerIds.has(id)) continue;
      if (poolIds.has(id)) {
        this._dlog('info', `Lane ID=${id} exclu : conteneur Pool/CFF (parent d'autres swimlanes)`);
        continue;
      }
      // 'Swimlane' (master=2) = layout header/separator, not a real content band
      const mn = (this.masterIdToName[s.getAttribute('Master')] || '').trim();
      if (/^swimlane(\s+for\s+separation)?$/i.test(mn)) {
        this._dlog('info', `Lane ID=${id} exclu : master="${mn}" = élément de layout CFF, pas une bande`);
        continue;
      }
      const abs = shapePinAbs[id] || {};
      if (!abs.h || abs.h < 0.3 || abs.h > 25) {
        this._dlog('info', `Lane ID=${id} exclu : hauteur hors limites (h=${(abs.h||0).toFixed(2)}")`);
        continue;
      }
      if (!abs.w || abs.w < pageMaxW * 0.3) {
        this._dlog('info', `Lane ID=${id} exclu : largeur trop petite (w=${(abs.w||0).toFixed(2)}" < ${(pageMaxW*0.3).toFixed(2)}")`);
        continue;
      }
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

  // Extract the fill color of a swimlane.
  // Priority: lane element FillForegnd → child page fill → child master fill.
  // The third level is critical for 'couloir color' bands (master=8) in CFF diagrams
  // where child shapes carry no explicit page fill but inherit from the master stencil.
  _extractLaneFill(el) {
    const fill = this.vCell(el, 'FillForegnd');
    if (!this.isWashedOut(fill)) return fill;

    const laneMid  = el.getAttribute('Master');
    const subFills = laneMid ? (this.masterSubShapeFills[laneMid] || {}) : {};

    const childEl = this.vEl(el, 'Shapes');
    if (childEl) {
      for (const child of this.vAll(childEl, 'Shape')) {
        if (child.getAttribute('Type') === 'Group') continue;
        // 1. Explicit fill on the page-level child
        const cf = this.vCell(child, 'FillForegnd');
        if (cf && cf.startsWith('#') && !this.isWashedOut(cf)) return cf;
        // 2. Fill inherited from the master stencil sub-shape
        const msId = child.getAttribute('MasterShape');
        const mf   = msId ? subFills[msId] : null;
        if (mf && !this.isWashedOut(mf)) return mf;
      }
    }
    return fill;
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
      if (/^(title|text|annotation|callout|note|border|background|frame)$/.test(mn)) {
        this._dlog('info', `Forme ID=${id} exclue : master="${mn}" (titre/texte/décoration)`);
        continue;
      }
      // "N-"/"D-"/"T-" prefix = CFF navigation cross-reference arrows (not activities)
      if (/^[ndt]\s*[-–]/.test(mn)) {
        this._dlog('info', `Forme ID=${id} exclue : master="${mn}" (flèche de navigation CFF)`);
        continue;
      }

      // LayerMember=3 = "Si petit"/"Si grand" visual decorators — exclude entirely
      if (this.vCell(s, 'LayerMember') === '3') continue;

      const abs = shapePinAbs[id] || {};
      const vW  = abs.w || 0;
      const vH  = abs.h || 0;
      if (vW < 0.2 || vH < 0.25) {
        this._dlog('info', `Forme ID=${id} exclue : trop petite (${vW.toFixed(2)}"×${vH.toFixed(2)}")`);
        continue;
      }
      if (vW > 8   || vH > 4   ) {
        this._dlog('info', `Forme ID=${id} exclue : trop grande (${vW.toFixed(2)}"×${vH.toFixed(2)}")`);
        continue;
      }

      // Exclude shapes outside the diagram's horizontal bounds
      const MARGIN_X = 1.5;
      if (this.rightEdge && (abs.pinX < leftEdge - MARGIN_X || abs.pinX > this.rightEdge + MARGIN_X)) {
        this._dlog('warn', `Forme ID=${id} "${this.vText(s)}" exclue : hors limites horizontales (pinX=${abs.pinX.toFixed(2)}")`);
        continue;
      }
      // Exclude shapes above the diagram top (they would pile up at y=0)
      if (abs.pinY > topOfDiagram + 1.0) {
        this._dlog('warn', `Forme ID=${id} "${this.vText(s)}" exclue : au-dessus du diagramme (pinY=${abs.pinY.toFixed(2)}" > top=${topOfDiagram.toFixed(2)}")`);
        continue;
      }

      // Compute screen position from center (so capping doesn't shift center point)
      const rawW = Math.round(vW * SCALE);
      const rawH = Math.round(vH * SCALE);
      const screenW = Math.min(MAX_ACT_W, rawW);
      const screenH = Math.min(MAX_ACT_H, rawH);
      const screenX = Math.max(144, Math.round((abs.pinX - leftEdge) * SCALE) - Math.round(screenW / 2));

      // ── Y position: XML parent-chain approach (100% reliable band assignment) ──
      // Each shape in a CFF diagram is a direct/indirect child of a swimlane.
      // We use that relationship to place the shape in the correct band, then
      // compute its Y offset relative to the lane's top using Visio coordinates.
      // Fallback (coordinate-based bandShift) only for floating shapes with no lane ancestor.
      let screenY;
      const laneId   = this.nearestLaneOf && this.nearestLaneOf[id];
      const laneInfo = laneId ? this.laneIdToBandInfo[laneId] : null;
      if (laneInfo) {
        const { bandIdx, abs: la, bandH: bH } = laneInfo;
        // Distance from lane top in canvas pixels (Y-down).
        // la.pinY + la.h/2 = Visio Y of lane top edge; abs.pinY = Visio Y of shape center.
        const distFromTop = (la.pinY + la.h / 2 - abs.pinY) * SCALE;
        const bandStartY  = newBands.slice(0, bandIdx).reduce((s, b) => s + b.height, 0);
        const PAD = 5;
        screenY = Math.round(Math.max(bandStartY + PAD,
                    Math.min(bandStartY + bH - screenH - PAD, bandStartY + distFromTop - screenH / 2)));
      } else {
        const naturalScreenY = Math.round((topOfDiagram - abs.pinY) * SCALE) - Math.round(screenH / 2);
        const naturalCenterY = naturalScreenY + screenH / 2;
        screenY = Math.max(0, naturalScreenY + this._bandShiftFor(naturalCenterY));
      }
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

      const oid = this.nextOid++;
      shapeIdMap[id] = oid;
      const shapeLabel = this.vText(s);
      newShapes.push({
        id: oid, type: shapeType, subtype,
        x: screenX, y: screenY, w: screenW, h: screenH,
        label:          shapeLabel,
        color:          shapeColor,
        textColor:      '#ffffff',
        strokeColor:    '',
        fontSize:       18,
        validationBadge: false,
        validationColor: '#4DB868',
        colorVariant:   0,
      });

      if (this.debug) {
        let cumYdbg = 0, bandIdxDbg = -1;
        for (let bi = 0; bi < newBands.length; bi++) {
          if (screenY + screenH / 2 >= cumYdbg && screenY + screenH / 2 < cumYdbg + newBands[bi].height) { bandIdxDbg = bi; break; }
          cumYdbg += newBands[bi].height;
        }
        const via = laneInfo ? 'ancêtre XML' : 'coords Visio';
        this._dlog('ok', `"${shapeLabel || '(sans label)'}" [${shapeType}${subtype !== 'normal' ? '/'+subtype : ''}] → bande ${bandIdxDbg + 1} y=${screenY}px (${via})`);
      }
    }

    const nExt   = newShapes.filter(s => s.subtype === 'external').length;
    const nExtco = newShapes.filter(s => s.subtype === 'extco').length;
    if (nExt   > 0) this.log(`✓ ${nExt} activité(s) externe(s) (forme stade) détectée(s)`);
    if (nExtco > 0) this.log(`✓ ${nExtco} activité(s) hachurée(s) détectée(s)`);
    this._dlog('info', `${newShapes.length} formes importées${nExt ? `, ${nExt} externes` : ''}${nExtco ? `, ${nExtco} hachurées` : ''}`);
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

    // 2. Master's default fill (shape inherits from stencil)
    const masterFill = (this.masterInfoCache[mid] || {}).fillColor;
    if (masterFill && !this.isWashedOut(masterFill)) return masterFill;

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
      // Layer 3 = "Si petit" visual-only indicators → skip
      const sEl = _shapeElById.get(visioId);
      if (sEl && this.vCell(sEl, 'LayerMember') === '3') continue;
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
        // Splice: A→B becomes A→D then D→B
        delete connMap[connId];
        connMap[`__sp${synCtr++}`] = { source: sv,          target: dec.visioId };
        connMap[`__sp${synCtr++}`] = { source: dec.visioId, target: tv, _origConnId: connId };
      }
    }
  }

  // Nudge portT values that are too close on the same endpoint+direction pair.
  // Preserves exact Visio positions and only separates near-duplicates (< MIN_GAP apart).
  _nudgePortConflicts(conns) {
    const MIN_GAP = 0.05;
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

  async buildConnections() {
    this.log('Reconstruction des connexions…');
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

    function readConnGeom(el, bx, by, ex, ey) {
      const raw = [];
      for (const child of Array.from(el.childNodes)) {
        if (child.nodeType !== 1 || child.localName !== 'Section') continue;
        if (child.getAttribute('N') !== 'Geometry') continue;
        for (const row of Array.from(child.childNodes)) {
          if (row.nodeType !== 1 || row.localName !== 'Row') continue;
          const T = row.getAttribute('T');
          if (T !== 'MoveTo' && T !== 'LineTo') continue;
          let rx = null, ry = null;
          for (const cell of Array.from(row.childNodes)) {
            if (cell.nodeType !== 1 || cell.localName !== 'Cell') continue;
            const N = cell.getAttribute('N');
            if (N === 'X') rx = parseFloat(cell.getAttribute('V') || '0');
            if (N === 'Y') ry = parseFloat(cell.getAttribute('V') || '0');
          }
          if (rx !== null && ry !== null) raw.push({ x: rx, y: ry });
        }
        break;
      }
      if (raw.length < 2) return [];
      const distAbs = Math.hypot(raw[0].x - bx, raw[0].y - by);
      const distRel = Math.hypot(raw[0].x, raw[0].y);
      const isRel   = distRel < distAbs;
      return raw.map(p => ({ x: isRel ? bx + p.x : p.x, y: isRel ? by + p.y : p.y }));
    }

    // Wrap visioToScreen pour appliquer le bandShift sur Y (cohérent avec
    // l'ajustement appliqué dans importActivities — sinon les customPath
    // des connecteurs partent du milieu d'une bande quand les shapes ont
    // été décalés vers le bas par l'inflation min 80).
    const self = this;
    function visioToScreen(vx, vy) {
      const ny = (topOfDiagram - vy) * SCALE;
      return { x: (vx - leftEdge) * SCALE, y: ny + self._bandShiftFor(ny) };
    }

    function snapToEdge(s, dir, t, halo) {
      const h = halo || 0, T = t !== undefined ? t : 0.5;
      switch (dir) {
        case 'right':  return { x: s.x + s.w + h,  y: s.y + s.h * T };
        case 'left':   return { x: s.x - h,          y: s.y + s.h * T };
        case 'top':    return { x: s.x + s.w * T,    y: s.y - h };
        case 'bottom': return { x: s.x + s.w * T,    y: s.y + s.h + h };
        default:       return { x: s.x + s.w / 2,    y: s.y + s.h / 2 };
      }
    }

    const newConns = this.newConns;
    for (const [connId, ends] of Object.entries(connMap)) {
      const { source: sv, target: tv } = ends;
      if (!sv || !tv) continue;
      const fromId = _shapeIdMap[sv] || _groupIdMap[sv];
      const toId   = _shapeIdMap[tv] || _groupIdMap[tv];
      if (!fromId || !toId) {
        this._dlog('warn', `Connexion ${connId} ignorée : endpoint non trouvé (src=${sv} → tgt=${tv})`);
        continue;
      }
      const srcShape = newShapes.find(s => s.id === fromId) || newGroups.find(g => g.id === fromId);

      const connItem = shapeMap[ends._origConnId || connId];
      const connLabel = connItem ? (this.vText(connItem.el) || '') : '';
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
        const rawGeom = readConnGeom(ce, bx, by, ex, ey);
        if (rawGeom.length >= 2) {
          const THRESH  = 1.5;
          const geomRel = rawGeom.map(p => ({ x: bx + p.x, y: by + p.y }));
          const geomAbs = rawGeom;
          const errRelS = Math.hypot(geomRel[0].x - bx, geomRel[0].y - by);
          const errRelE = Math.hypot(geomRel[geomRel.length-1].x - ex, geomRel[geomRel.length-1].y - ey);
          const errAbsS = Math.hypot(geomAbs[0].x - bx, geomAbs[0].y - by);
          const errAbsE = Math.hypot(geomAbs[geomAbs.length-1].x - ex, geomAbs[geomAbs.length-1].y - ey);
          const useRel  = (errRelS + errRelE) <= (errAbsS + errAbsE);
          const geomVis = useRel ? geomRel : geomAbs;
          const errS = useRel ? errRelS : errAbsS, errE = useRel ? errRelE : errAbsE;
          if (errS < THRESH && errE < THRESH) {
            const srcS = newShapes.find(s => s.id === (_shapeIdMap[sv] || _groupIdMap[sv]));
            const tgtS = newShapes.find(s => s.id === (_shapeIdMap[tv] || _groupIdMap[tv]));
            const pts  = geomVis.map(p => visioToScreen(p.x, p.y));
            if (srcS && fromPortT !== undefined) pts[0] = snapToEdge(srcS, fromPortDir, fromPortT, srcS.type === 'process' ? 7 : 0);
            if (tgtS && toPortT   !== undefined) pts[pts.length-1] = snapToEdge(tgtS, toPortDir, toPortT, tgtS.type === 'process' ? 7 : 0);
            customPath = pts;
          }
        }
      } else if (sAbs && tAbs) {
        const dx = tAbs.pinX - sAbs.pinX, dy = tAbs.pinY - sAbs.pinY;
        fromPortDir = Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'top' : 'bottom');
        toPortDir   = OPP[fromPortDir];
      }

      const connObj = {
        id: this.nextOid++, fromId, toId, fromPortDir, toPortDir,
        color: srcShape ? srcShape.color : '#567460',
        label: VsdxImporter._wrapConnLabel(connLabel), style: isDashed ? 'dashed' : 'solid', routing: 'orthogonal',
      };
      if (fromPortT !== undefined) connObj.fromPortT = fromPortT;
      if (toPortT   !== undefined) connObj.toPortT   = toPortT;
      if (customPath)              connObj.customPath = customPath;
      newConns.push(connObj);

      if (this.debug) {
        const fLbl = (newShapes.find(s => s.id === fromId) || {}).label || String(fromId);
        const tLbl = (newShapes.find(s => s.id === toId)   || {}).label || String(toId);
        const extras = [
          isDashed ? 'pointillée' : '',
          customPath ? `+chemin Visio (${customPath.length} pts)` : '',
          connObj.label ? `label:"${connObj.label.replace(/\n/g,' ')}"` : '',
        ].filter(Boolean).join(', ');
        this._dlog('ok', `"${fLbl}" → "${tLbl}"${extras ? '  ['+extras+']' : ''}`);
      }
    }

    this._dlog('info', `${newConns.length} connexions créées`);

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

  async parse(onOrphans) {
    await this.parseMasters();
    await this.parsePage();
    await this.prefetchMasters();
    this.computeAbsCoords();
    this.buildConnMap();
    this.identifyContainers();
    this.buildBands();
    this.buildNearestLaneMap();

    // ── Capture étape 1 : bandes ──────────────────────────────────
    if (this.debug) this.debug.capture(1, 'Étape 1 — Bandes (swimlanes)', this.newBands, [], []);

    this.detectContainerGroups();
    this.importActivities();
    this.applyLayoutCorrections();

    // ── Capture étape 2 : formes ──────────────────────────────────
    if (this.debug) this.debug.capture(2, 'Étape 2 — Formes', this.newBands, this.newShapes, []);

    this.buildGroups();
    this.spliceDecisions();
    await this.buildConnections();
    this.cleanupBands();

    // ── Capture étape 3 : connexions ─────────────────────────────
    if (this.debug) this.debug.capture(3, 'Étape 3 — Connexions', this.newBands, this.newShapes, this.newConns);

    // ── Orphan handling (empty + unconnected shapes) ──
    if (onOrphans) {
      const connectedIds = new Set([
        ...this.newConns.map(c => c.fromId),
        ...this.newConns.map(c => c.toId),
      ]);
      const orphans = this.newShapes.filter(s => (!s.label || !s.label.trim()) && !connectedIds.has(s.id));
      if (orphans.length > 0) {
        const choice = await onOrphans(orphans);
        if (choice === 'cancel') return null;
        if (choice === 'clean') {
          const orphanIds = new Set(orphans.map(s => s.id));
          orphans.forEach(s => this.newShapes.splice(this.newShapes.indexOf(s), 1));
          for (const g of this.newGroups)
            if (g.shapeIds) g.shapeIds = g.shapeIds.filter(id => !orphanIds.has(id));
          this._dlog('info', `${orphanIds.size} forme(s) orpheline(s) supprimées`);
        }
      }
    }

    this.antiOverlap();
    this.stretchBands();

    // ── Capture étape 4 : modèle final avec labels ────────────────
    if (this.debug) {
      const nLabels = this.newConns.filter(c => c.label).length;
      this._dlog('info', `${nLabels} label(s) sur connexions — placement sur le segment le plus long`);
      this.debug.capture(4, 'Étape 4 — Modèle final (labels + layout)', this.newBands, this.newShapes, this.newConns);
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

// ── Debug report builder ──────────────────────────────────────────────────────
// Created only when debugMode=true in vsdxParse. Collects per-step logs and
// SVG snapshots, then generates a self-contained HTML diagnostic report.

class VsdxDebugReport {
  constructor() {
    this.steps = [];
    this._logs = [];
  }

  ok(msg)   { this._logs.push({ level: 'ok',   msg }); }
  warn(msg) { this._logs.push({ level: 'warn', msg }); }
  err(msg)  { this._logs.push({ level: 'err',  msg }); }
  info(msg) { this._logs.push({ level: 'info', msg }); }

  capture(idx, title, bands, shapes, conns) {
    const svg  = this._renderSvg([...bands], [...shapes], [...conns], idx);
    const logs = this._logs.splice(0); // drain and clear
    this.steps.push({ idx, title, svg, logs });
  }

  static _pastel(hex) {
    if (!hex || hex.length < 7) return '#1e2436';
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return '#' + [r*.15+255*.85, g*.15+255*.85, b*.15+255*.85]
      .map(c => Math.round(Math.min(255,c)).toString(16).padStart(2,'0')).join('');
  }

  static _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  _renderSvg(bands, shapes, conns, stepIdx) {
    const INDEX_W  = 140;
    const totalBandH = bands.reduce((s, b) => s + b.height, 0);
    if (!totalBandH) return `<svg width="900" height="50"><rect width="900" height="50" fill="#0d1117"/><text x="10" y="30" fill="#7d8590" font-family="sans-serif">Aucune bande</text></svg>`;

    const rawW  = shapes.length
      ? Math.max(1200, shapes.reduce((m, s) => Math.max(m, s.x + s.w + 80), INDEX_W + 160))
      : 1400;
    const scale = Math.min(1, 900 / rawW);
    const svgW  = Math.round(rawW * scale);
    const svgH  = Math.max(40, Math.round(totalBandH * scale));
    const iW    = Math.round(INDEX_W * scale);
    const e     = VsdxDebugReport._esc;

    const lines = [
      `<svg xmlns="http://www.w3.org/2000/svg" width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}" style="background:#0d1117;border-radius:6px;display:block">`,
      '<defs><marker id="dbgarr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0.5 L0,5.5 L6,3 z" fill="#94a3b8"/></marker></defs>',
    ];

    // Bands
    let yB = 0;
    for (const band of bands) {
      const bH  = Math.max(2, Math.round(band.height * scale));
      const pas = VsdxDebugReport._pastel(band.color);
      lines.push(`<rect x="0" y="${yB}" width="${iW}" height="${bH}" fill="${e(band.color)}"/>`);
      lines.push(`<rect x="${iW}" y="${yB}" width="${svgW-iW}" height="${bH}" fill="${e(pas)}"/>`);
      lines.push(`<line x1="0" y1="${yB+bH}" x2="${svgW}" y2="${yB+bH}" stroke="${e(band.color)}" stroke-width="1.5"/>`);
      if (bH > 16) {
        const fs  = Math.max(7, Math.min(12, Math.round(bH * 0.24)));
        const lx  = iW / 2, ly = yB + bH / 2;
        const lbl = band.label.length > 22 ? band.label.slice(0,21)+'…' : band.label;
        lines.push(`<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" fill="white" font-family="Segoe UI,sans-serif" font-weight="700" font-size="${fs}" transform="rotate(-90,${lx},${ly})">${e(lbl)}</text>`);
      }
      yB += bH;
    }

    // Shapes (step ≥ 2)
    if (stepIdx >= 2) {
      for (const s of shapes) {
        const sx = Math.round(s.x * scale), sy = Math.round(s.y * scale);
        const sw = Math.max(3, Math.round(s.w * scale)), sh = Math.max(2, Math.round(s.h * scale));
        const col = e(s.color || '#22c55e');
        if (s.type === 'decision') {
          const cx = sx+sw/2, cy = sy+sh/2;
          lines.push(`<polygon points="${cx},${sy} ${sx+sw},${cy} ${cx},${sy+sh} ${sx},${cy}" fill="${col}"/>`);
        } else if (s.type === 'start-end') {
          lines.push(`<ellipse cx="${sx+sw/2}" cy="${sy+sh/2}" rx="${sw/2}" ry="${sh/2}" fill="${col}"/>`);
        } else {
          lines.push(`<rect x="${sx}" y="${sy}" width="${sw}" height="${sh}" rx="${Math.min(4,Math.round(sh/4))}" fill="${col}"/>`);
        }
        if (s.label && sw > 12 && sh > 7) {
          const fs2 = Math.max(5, Math.min(9, Math.round(sh * 0.38)));
          const lbl2 = s.label.length > 16 ? s.label.slice(0,15)+'…' : s.label;
          lines.push(`<text x="${sx+sw/2}" y="${sy+sh/2}" text-anchor="middle" dominant-baseline="middle" fill="white" font-family="Segoe UI,sans-serif" font-size="${fs2}">${e(lbl2)}</text>`);
        }
      }
    }

    // Connections (step ≥ 3): straight lines between shape centers
    if (stepIdx >= 3 && conns.length) {
      const byId = {};
      for (const s of shapes) byId[s.id] = s;
      for (const c of conns) {
        const from = byId[c.fromId], to = byId[c.toId];
        if (!from || !to) continue;
        const fx = Math.round((from.x+from.w/2)*scale), fy = Math.round((from.y+from.h/2)*scale);
        const tx = Math.round((to.x  +to.w/2  )*scale), ty = Math.round((to.y  +to.h/2  )*scale);
        lines.push(`<line x1="${fx}" y1="${fy}" x2="${tx}" y2="${ty}" stroke="${e(c.color||'#567460')}" stroke-width="1" marker-end="url(#dbgarr)" opacity="0.65"/>`);
      }
    }

    // Labels (step ≥ 4)
    if (stepIdx >= 4) {
      const byId = {};
      for (const s of shapes) byId[s.id] = s;
      for (const c of conns) {
        if (!c.label) continue;
        const from = byId[c.fromId], to = byId[c.toId];
        if (!from || !to) continue;
        const lx  = Math.round(((from.x+from.w/2 + to.x+to.w/2)/2)*scale);
        const ly  = Math.round(((from.y+from.h/2 + to.y+to.h/2)/2)*scale);
        const lbl3 = c.label.replace(/\n/g,' ');
        const fw  = Math.max(20, Math.min(lbl3.length*4+10, 120));
        lines.push(`<rect x="${lx-fw/2}" y="${ly-6}" width="${fw}" height="12" rx="2" fill="rgba(255,255,255,0.93)"/>`);
        lines.push(`<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" fill="#0d1117" font-family="Segoe UI,sans-serif" font-size="6.5" font-weight="600">${e(lbl3.length>20?lbl3.slice(0,19)+'…':lbl3)}</text>`);
      }
    }

    lines.push('</svg>');
    return lines.join('');
  }

  generateHtml(filename) {
    const fname = filename || 'import.vsdx';
    const now   = new Date().toLocaleString('fr-FR');
    const e     = VsdxDebugReport._esc;

    const stepsHtml = this.steps.map(step => {
      const n = { ok: 0, warn: 0, err: 0 };
      for (const l of step.logs) if (n[l.level] !== undefined) n[l.level]++;
      const badges = [
        n.ok   ? `<span class="badge ok">${n.ok} ✓</span>`    : '',
        n.warn ? `<span class="badge warn">${n.warn} ⚠</span>` : '',
        n.err  ? `<span class="badge err">${n.err} ✗</span>`   : '',
      ].filter(Boolean).join('') || '<span class="badge info">0 événement</span>';

      const rows = step.logs.map(l => {
        const icon = { ok:'✓', warn:'⚠', err:'✗', info:'·' }[l.level] || '·';
        return `<tr class="l-${l.level}"><td class="icon">${icon}</td><td>${e(l.msg)}</td></tr>`;
      }).join('');

      return `
<section class="step" id="step${step.idx}">
  <div class="sh">
    <span class="snum">${step.idx}</span>
    <h2>${e(step.title)}</h2>
    <div class="badges">${badges}</div>
  </div>
  <div class="sb">
    <div class="sv">${step.svg}</div>
    <div class="sl">
      <table>
        <thead><tr><th style="width:22px"></th><th>Événement</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="2" class="empty">Aucun événement</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</section>`;
    }).join('\n');

    return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Debug VSDX — ${e(fname)}</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#cdd6f4;font-size:13px;line-height:1.5}
header{background:#161b22;border-bottom:2px solid #22c55e;padding:16px 24px}
header h1{font-size:17px;font-weight:700;color:#e6edf3}
header p{font-size:11px;color:#7d8590;margin-top:3px}
.step{margin:18px 20px;border:1px solid #21262d;border-radius:10px;overflow:hidden;background:#161b22}
.sh{display:flex;align-items:center;gap:10px;padding:11px 16px;background:#1c2128;border-bottom:1px solid #21262d}
.snum{background:#22c55e;color:#0d1117;font-weight:800;font-size:12px;border-radius:5px;padding:1px 8px;flex-shrink:0}
.sh h2{font-size:13.5px;font-weight:600;color:#e6edf3;flex:1}
.badges{display:flex;gap:5px;flex-shrink:0}
.badge{padding:1px 8px;border-radius:20px;font-size:10px;font-weight:700}
.badge.ok{background:rgba(34,197,94,.12);color:#22c55e;border:1px solid rgba(34,197,94,.25)}
.badge.warn{background:rgba(245,158,11,.12);color:#f59e0b;border:1px solid rgba(245,158,11,.25)}
.badge.err{background:rgba(239,68,68,.12);color:#ef4444;border:1px solid rgba(239,68,68,.25)}
.badge.info{background:rgba(99,102,241,.1);color:#818cf8;border:1px solid rgba(99,102,241,.2)}
.sb{display:flex;min-height:180px}
.sv{flex-shrink:0;overflow-x:auto;background:#0a0d14;padding:8px;border-right:1px solid #21262d}
.sl{flex:1;overflow-y:auto;max-height:420px;min-width:220px;background:#0f1319}
.sl table{width:100%;border-collapse:collapse}
.sl thead th{padding:6px 9px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#7d8590;background:#161b22;border-bottom:1px solid #21262d;position:sticky;top:0;z-index:1}
.sl td{padding:3px 8px;font-size:11px;border-bottom:1px solid rgba(255,255,255,0.03);vertical-align:top;word-break:break-word}
.l-ok td{color:#d1fae5}.l-ok .icon{color:#22c55e;font-weight:700}
.l-warn td{color:#fef3c7}.l-warn .icon{color:#f59e0b;font-weight:700}
.l-err td{color:#fee2e2}.l-err .icon{color:#ef4444;font-weight:700}
.l-info td{color:#a0aec0}.l-info .icon{color:#718096}
.empty{color:#7d8590;font-style:italic;padding:10px 9px!important}
</style>
</head>
<body>
<header>
  <h1>Rapport d'import VSDX</h1>
  <p>Fichier&nbsp;: <strong>${e(fname)}</strong> &nbsp;·&nbsp; ${e(now)}</p>
</header>
${stepsHtml}
</body>
</html>`;
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
// Usage: const result = await vsdxParse(file, setStatus, onOrphans, debugMode)
// When debugMode=true, result.debugHtml contains a self-contained HTML report.
async function vsdxParse(file, onProgress, onOrphans, debugMode = false) {
  const zip = await JSZip.loadAsync(file);
  const importer = new VsdxImporter(zip, onProgress);
  if (debugMode) importer.debug = new VsdxDebugReport();
  const result = await importer.parse(onOrphans);
  if (result && importer.debug) result.debugHtml = importer.debug.generateHtml(file.name);
  return result;
}
