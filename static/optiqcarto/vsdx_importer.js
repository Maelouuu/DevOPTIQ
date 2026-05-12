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

  async getMasterInfo(mid) {
    const DEFAULTS = { w: 0.9449, h: 0.7087, linePattern: 1, isEllipse: false, isDiamond: false, isSubprocess: false, fillColor: null };
    if (!mid) return DEFAULTS;
    if (this.masterInfoCache[mid]) return this.masterInfoCache[mid];
    const fpath = this.masterIdToFile[mid];
    if (!fpath) return this.masterInfoCache[mid] = { ...DEFAULTS };
    try {
      const xml = await this.zip.file(fpath).async('text');
      const doc = this.parseXml(xml);
      let bw, bh, lp = 1, isDiamond = false, fillColor = null;

      const geomRows = doc.getElementsByTagName('Row');
      const geomSeq = [];
      let moveTos = 0;
      for (let ri = 0; ri < geomRows.length; ri++) {
        const t = geomRows[ri].getAttribute('T');
        if (t === 'LineTo'  || t === 'EllipticalArcTo') geomSeq.push(t);
        if (t === 'MoveTo') moveTos++;
      }

      const arcCount  = geomSeq.filter(t => t === 'EllipticalArcTo').length;
      const lineCount = geomSeq.filter(t => t === 'LineTo').length;

      // Pure ellipse: geometry is predominantly arcs with few/no straight edges.
      // arcCount > lineCount*2 catches ovals (4 arcs, 0 lines) and stadiums (4 arcs, 1 line).
      const isEllipse = arcCount > 0 && arcCount > lineCount * 2;

      // Diamond: EllipticalArcTo intercalated with LineTo (Si grand/Si petit pattern).
      // Requires at least some arcs, AND a LineTo after the last arc.
      if (arcCount > 0) {
        const lastArcIdx = geomSeq.lastIndexOf('EllipticalArcTo');
        if (lastArcIdx !== -1 && lastArcIdx < geomSeq.length - 1)
          isDiamond = geomSeq.slice(lastArcIdx + 1).includes('LineTo');
      }

      // Wavy-bottom subprocess: mixed arcs+lines with CONSECUTIVE arcs (wave).
      // Rounded rectangles have arcs alternating with lines (never consecutive).
      let hasConsecutiveArcs = false;
      for (let i = 0; i < geomSeq.length - 1; i++) {
        if (geomSeq[i] === 'EllipticalArcTo' && geomSeq[i+1] === 'EllipticalArcTo') {
          hasConsecutiveArcs = true; break;
        }
      }
      const isWavyBottom = hasConsecutiveArcs && !isEllipse && !isDiamond;

      // Sub-process (predefined process): multiple geometry sections (= internal markers),
      // ≥3 MoveTo sub-paths, OR a wavy bottom edge.
      let geomSectCount = 0;
      const allSects = doc.getElementsByTagName('Section');
      for (let si = 0; si < allSects.length; si++)
        if (allSects[si].getAttribute('N') === 'Geometry') geomSectCount++;
      const isSubprocess = (geomSectCount >= 2 || moveTos >= 3 || isWavyBottom) && !isEllipse && !isDiamond;

      for (const s of doc.getElementsByTagName('Shape')) {
        const w = this.vCell(s, 'Width'), h = this.vCell(s, 'Height');
        if (w) bw = parseFloat(w);
        if (h) bh = parseFloat(h);
        const lv = this.vCellDeep(s, 'LinePattern');
        if (lv) lp = parseInt(lv) || 1;
        const fc = this.vCell(s, 'FillForegnd');
        if (fc && fc.startsWith('#') && !fillColor) fillColor = fc;
        if (bw && bh) break;
      }
      return this.masterInfoCache[mid] = { w: bw || 0.9449, h: bh || 0.7087, linePattern: lp, isEllipse, isDiamond, isSubprocess, fillColor };
    } catch(e) {
      return this.masterInfoCache[mid] = { w: 0.9449, h: 0.7087, linePattern: 1, isEllipse: false, isDiamond: false, isSubprocess: false, fillColor: null };
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
  // Populates this.newBands and this.legendBounds.

  buildBands() {
    this.log('Construction des bandes…');
    const { allShapes, containerIds, shapePinAbs, pageMaxW, SCALE, FALLBACK_COLORS } = this;

    const laneList = [];
    for (const { el: s, id } of allShapes) {
      if (!containerIds.has(id)) continue;
      const abs = shapePinAbs[id] || {};
      if (!abs.h || abs.h < 0.3 || abs.h > 25) continue;
      if (!abs.w || abs.w < pageMaxW * 0.3)    continue;
      laneList.push({ el: s, id, abs });
    }
    laneList.sort((a, b) => b.abs.pinY - a.abs.pinY); // top-first (Visio Y-up)

    // Deduplicate lanes that are too close (separator slivers)
    const lanes = [];
    for (const ln of laneList) {
      const prev = lanes[lanes.length - 1];
      if (prev && Math.abs(ln.abs.pinY - prev.abs.pinY) < 0.15) continue;
      lanes.push(ln);
    }

    let topOfDiagram;
    let leftEdge = 0;
    if (lanes.length > 0) {
      topOfDiagram = lanes[0].abs.pinY + lanes[0].abs.h / 2;
      leftEdge     = Math.min(...lanes.map(l => l.abs.pinX - l.abs.w / 2));
    } else {
      let maxY = 0;
      for (const { id } of allShapes) {
        const abs = shapePinAbs[id];
        if (abs && abs.pinY + abs.h/2 > maxY) maxY = abs.pinY + abs.h/2;
      }
      topOfDiagram = maxY || 42;
    }
    this.topOfDiagram = topOfDiagram;
    this.leftEdge     = leftEdge;

    const newBands    = this.newBands;
    const legendBounds = this.legendBounds;

    if (lanes.length > 0) {
      for (let i = 0; i < lanes.length; i++) {
        const { el: s, abs } = lanes[i];
        const bandH = Math.round(Math.max(80, abs.h * SCALE));

        // Lane label: look for text in direct children (skip nested groups)
        let label = '';
        for (const c of s.childNodes)
          if (c.nodeType !== 1 || c.localName !== 'Shapes') {
            const t = this.vDeep(c, 'Text');
            if (t && t.textContent.trim()) { label = t.textContent.trim(); break; }
          }
        if (!label) {
          const nested = this.vEl(s, 'Shapes');
          if (nested) {
            for (const child of this.vAll(nested, 'Shape')) {
              const t = this.vText(child);
              if (t && t.length > 0 && t.length < 100) { label = t; break; }
            }
          }
        }

        let fill = this.vCell(s, 'FillForegnd');
        if (this.isWashedOut(fill)) {
          const childEl = this.vEl(s, 'Shapes');
          if (childEl) {
            for (const child of this.vAll(childEl, 'Shape')) {
              if (child.getAttribute('Type') === 'Group') continue;
              const cf = this.vCell(child, 'FillForegnd');
              if (cf && cf.startsWith('#') && !this.isWashedOut(cf)) { fill = cf; break; }
            }
          }
        }

        // Legend lane: store its bounds for spatial filtering
        if (/l[eé]gende?|legend/i.test(label)) {
          legendBounds.push({
            xMin: abs.pinX - abs.w/2, xMax: abs.pinX + abs.w/2,
            yMin: abs.pinY - abs.h/2, yMax: abs.pinY + abs.h/2,
          });
          continue;
        }

        const bandIdx = newBands.length + 1;
        const color = !this.isWashedOut(fill) ? fill : FALLBACK_COLORS[bandIdx % FALLBACK_COLORS.length];
        newBands.push({ id: bandIdx, label: label || `Bande ${bandIdx}`, color, fontSize: 22, height: bandH });
      }
    } else {
      newBands.push({ id: 1, label: 'Activités', color: '#22c55e', fontSize: 22, height: 500 });
    }
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
      if (/^(title|text|annotation|callout|note|border|background|frame)$/.test(mn)) continue;

      const abs = shapePinAbs[id] || {};
      const vW  = abs.w || 0;
      const vH  = abs.h || 0;
      if (vW < 0.2 || vH < 0.1) continue;
      if (vW > 8   || vH > 4  ) continue;

      // Compute screen position from center (so capping doesn't shift center point)
      const rawW = Math.round(vW * SCALE);
      const rawH = Math.round(vH * SCALE);
      const screenW = Math.min(MAX_ACT_W, rawW);
      const screenH = Math.min(MAX_ACT_H, rawH);
      const screenX = Math.max(144, Math.round((abs.pinX - leftEdge) * SCALE) - Math.round(screenW / 2));
      const screenY = Math.max(0, Math.round((topOfDiagram - abs.pinY) * SCALE) - Math.round(screenH / 2));
      if (screenY > totalBandH + 100) continue; // outside diagram

      const mInfoForType = masterInfoCache[mid] || {};
      const shapeType = detectShapeType(masterIdToName[mid], vType,
                          mInfoForType.isEllipse, mInfoForType.isDiamond, mInfoForType.isSubprocess);

      // ── Color: VSDX shape fill → master fill → band color ──
      // Preserves original Visio colors (e.g. yellow logistics, blue ops shapes).
      // Only falls back to band color when the shape has no explicit fill.
      const shapeColor = this._resolveShapeColor(s, mid, shapeType, screenY, screenH);

      const oid = this.nextOid++;
      shapeIdMap[id] = oid;
      newShapes.push({
        id: oid, type: shapeType, subtype: 'normal',
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
      const br = bRanges.find(r => cy >= r.y0 && cy < r.y1) || bRanges[bRanges.length - 1];
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

    function visioToScreen(vx, vy) {
      return { x: (vx - leftEdge) * SCALE, y: (topOfDiagram - vy) * SCALE };
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
      if (!fromId || !toId) continue;
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
        label: connLabel, style: isDashed ? 'dashed' : 'solid', routing: 'orthogonal',
      };
      if (fromPortT !== undefined) connObj.fromPortT = fromPortT;
      if (toPortT   !== undefined) connObj.toPortT   = toPortT;
      if (customPath)              connObj.customPath = customPath;
      newConns.push(connObj);
    }
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

  stretchBands() {
    let y0 = 0;
    for (const band of this.newBands) {
      const bot = this.newShapes
        .filter(s => { const m = s.y + s.h/2; return m >= y0 && m < y0 + band.height; })
        .reduce((m, s) => Math.max(m, s.y + s.h), 0);
      if (bot + 20 > y0 + band.height) band.height = Math.round(bot + 20 - y0);
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
          const ovX = Math.min(a.x+a.w, b.x+b.w) - Math.max(a.x, b.x);
          const ovY = Math.min(a.y+a.h, b.y+b.h) - Math.max(a.y, b.y);
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
    this.detectContainerGroups();
    this.importActivities();
    this.applyLayoutCorrections();
    this.buildGroups();
    this.spliceDecisions();
    await this.buildConnections();
    this.cleanupBands();

    // ── Orphan handling (empty + unconnected shapes) ──
    if (onOrphans) {
      const connectedIds = new Set([
        ...this.newConns.map(c => c.fromId),
        ...this.newConns.map(c => c.toId),
      ]);
      const orphans = this.newShapes.filter(s => (!s.label || !s.label.trim()) && !connectedIds.has(s.id));
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

    this.stretchBands();
    this.antiOverlap();

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
// Check order: decision → subprocess → ellipse → default process
// Subprocess is checked BEFORE ellipse so wavy-bottom shapes are not captured
// by the isEllipse guard (which is now "pure arc shape" only).
function detectShapeType(masterName, visioType, isEllipse, isDiamond, isSubprocess) {
  const mn = (masterName || '')
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[-_/]/g, ' ')
    .replace(/\s+/g, ' ').trim();

  // 1. Decision / diamond
  if (/\b(decision|diamond|gateway|exclusive|parallel|condition|conditional|losange|branchement|rhombus|si grand|si petit|big if|small if)\b/.test(mn)
      || mn === 'conditional' || mn === 'decision') return 'decision';
  if (isDiamond) return 'decision';

  // 2. Off-page connectors → subprocess style
  if (/\bgot[ot]+\b|\bext\.?\s*ret\b|\bext\.?\s*return\b|\baller\s+[aà]\b|\bautre\s+carte\b/.test(mn)) return 'special';

  // 3. Subprocess — by geometry (wavy bottom, multiple sections, multiple paths)
  //    Checked BEFORE ellipse so wavy shapes are not swallowed by the isEllipse guard.
  if (isSubprocess) return 'special';
  if (/\b(subprocess|sub process|predefined|processus predefini|activite partielle|sous activite|sous processus|sous tache|tache multiple|multi instance|callout|offpage|off page)\b/.test(mn)) return 'special';

  // 4. Start/end — oval/circle shapes (isEllipse now means "pure arc shape")
  if (/\b(terminator|oval|ellipse|circle|event|rond|cercle|ronde|circulaire)\b/.test(mn)
      || mn === 'start' || mn === 'end'
      || mn.includes('start end') || mn.includes('debut fin') || mn.includes('start/end')
      || isEllipse) return 'start-end';

  // 5. Visio Group that is not a swimlane → subprocess style
  if (visioType === 'Group') return 'special';

  return 'process';
}

// ── Public entry point ────────────────────────────────────────────
// Usage: const result = await vsdxParse(file, setStatus, onOrphans)
async function vsdxParse(file, onProgress, onOrphans) {
  const zip = await JSZip.loadAsync(file);
  const importer = new VsdxImporter(zip, onProgress);
  return await importer.parse(onOrphans);
}
