# Code/routes/vsdx_decision_extractor.py
"""
Extracts decision-diamond data from raw VSDX files for debug/comparison.

Returns structured data about:
- Which shapes are diamonds (by master name or geometry + size heuristics)
- Their incoming / outgoing connections (from explicit Connect elements)
- Virtual connections for "placed on line" diamonds (proximity splice)
- Any Oui/Non badge shapes near those connections
"""

import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List
import re

VISIO_NS = {'v': 'http://schemas.microsoft.com/office/visio/2012/main'}

_DECISION_RE = re.compile(
    r'\b(decision|diamond|gateway|exclusive|parallel|condition|conditional|'
    r'losange|branchement|rhombus|si\s*grand|si\s*petit|big\s*if|small\s*if|'
    r'gateway|exclusive|conditional)\b',
    re.I
)

# Masters that are definitely NOT decision nodes (annotation/legend/misc)
_EXCLUDE_MASTER_RE = re.compile(
    r'\b(feedback|annotation|note|callout|legend|text|label|box|'
    r'rectangle|square|page|background|frame)\b',
    re.I
)

OUI_NON_RE = re.compile(r'^(oui|non|yes|no)$', re.I)


def _text_of(el) -> str:
    text_el = el.find('.//v:Text', VISIO_NS)
    if text_el is None:
        return ''
    return ' '.join(''.join(text_el.itertext()).split())


def _cell_val(shape_el, name: str) -> str:
    c = shape_el.find(f".//v:Cell[@N='{name}']", VISIO_NS)
    return c.get('V', c.get('v', '')) if c is not None else ''


def _cell_float(shape_el, name: str) -> float:
    v = _cell_val(shape_el, name)
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _is_pure_diamond_geometry(shape_el) -> bool:
    """Exactly 1 MoveTo + 4 LineTo in one Geometry section (no arcs)."""
    for geom in shape_el.findall(".//v:Section[@N='Geometry']", VISIO_NS):
        rows = geom.findall('.//v:Row', VISIO_NS)
        types = [r.get('T', r.get('N', '')) for r in rows]
        move = sum(1 for t in types if t in ('MoveTo', 'M'))
        line = sum(1 for t in types if t in ('LineTo', 'L'))
        arc  = sum(1 for t in types if 'Arc' in t or t == 'A')
        if move == 1 and line == 4 and arc == 0:
            return True
    return False


def _is_likely_annotation(shape_el, master_name: str, text: str) -> bool:
    """Returns True if this shape looks like a legend/annotation box, not a decision."""
    # Explicitly excluded master names
    if master_name and _EXCLUDE_MASTER_RE.search(master_name):
        return True
    # Long text → annotation / legend
    if len(text) > 60:
        return True
    # Very large shape → annotation box (PinX/Y not useful here, use Width/Height)
    w = _cell_float(shape_el, 'Width')
    h = _cell_float(shape_el, 'Height')
    if w > 3.0 or h > 3.0:  # inches in Visio coordinates
        return True
    # Shapes on layer 2 with non-empty text are typically legend/annotation
    layer = _cell_val(shape_el, 'LayerMember')
    if layer == '2' and text:
        return True
    return False


def _parse_masters_xml(zf, masters_by_uid: Dict[str, str]):
    if 'visio/masters/masters.xml' not in zf.namelist():
        return
    try:
        root = ET.fromstring(zf.read('visio/masters/masters.xml'))
        for m in root.findall('.//v:Master', VISIO_NS):
            mid = m.get('ID', '')
            name = m.get('NameU', m.get('Name', ''))
            if mid:
                masters_by_uid[mid] = name.lower()
    except Exception:
        pass


def extract_decisions_from_vsdx(vsdx_path: str) -> Dict:
    """
    Returns {
        decisions: [
            {
                id: str,
                label: str,
                master_name: str,
                layer: str,
                outgoing: [{conn_id, to_id, to_label, conn_label, badge}],
                incoming: [{conn_id, from_id, from_label, conn_label, badge}],
                splice: bool   # True if found by proximity, not explicit Connect
            }
        ],
        total_shapes: int,
        total_connectors: int,
        errors: [str]
    }
    """
    result: Dict = {
        'decisions': [],
        'total_shapes': 0,
        'total_connectors': 0,
        'errors': [],
    }

    try:
        with zipfile.ZipFile(vsdx_path, 'r') as zf:
            masters_by_uid: Dict[str, str] = {}
            _parse_masters_xml(zf, masters_by_uid)

            page_files = sorted(
                f for f in zf.namelist()
                if f.startswith('visio/pages/page') and f.endswith('.xml')
            )
            if not page_files:
                result['errors'].append('Aucune page trouvée dans le VSDX')
                return result

            page_xml = zf.read(page_files[0])
            _parse_page(page_xml, masters_by_uid, result)

    except zipfile.BadZipFile:
        result['errors'].append('Fichier VSDX corrompu')
    except Exception as e:
        result['errors'].append(f'Erreur: {e}')

    return result


def _parse_page(page_xml: bytes, masters_by_uid: Dict, result: Dict):
    try:
        root = ET.fromstring(page_xml)
    except ET.ParseError as e:
        result['errors'].append(f'XML parse error: {e}')
        return

    all_shapes = root.findall('.//v:Shape', VISIO_NS)
    result['total_shapes'] = len(all_shapes)

    # 1 — Build shape info index
    shape_info: Dict[str, Dict] = {}
    for s in all_shapes:
        sid = s.get('ID', '')
        if not sid:
            continue
        master_id = s.get('Master', '')
        mname = masters_by_uid.get(master_id, '')
        text = _text_of(s)
        layer = _cell_val(s, 'LayerMember')
        pin_x = _cell_float(s, 'PinX')
        pin_y = _cell_float(s, 'PinY')

        is_decision = (
            (bool(_DECISION_RE.search(mname)) or _is_pure_diamond_geometry(s))
            and not _is_likely_annotation(s, mname, text)
        )

        shape_info[sid] = {
            'id': sid,
            'text': text,
            'master_name': mname,
            'layer': layer,
            'is_decision': is_decision,
            'pin_x': pin_x,
            'pin_y': pin_y,
            '_el': s,
        }

    # 2 — Build connector map
    connects = root.findall('.//v:Connect', VISIO_NS)
    result['total_connectors'] = len(connects)

    connectors: Dict[str, Dict] = {}
    for c in connects:
        from_sheet = c.get('FromSheet', '')
        from_cell  = c.get('FromCell', '')
        to_sheet   = c.get('ToSheet', '')
        if not from_sheet or not to_sheet:
            continue
        if from_sheet not in connectors:
            connectors[from_sheet] = {'source': None, 'target': None}
        if 'BeginX' in from_cell:
            connectors[from_sheet]['source'] = to_sheet
        elif 'EndX' in from_cell:
            connectors[from_sheet]['target'] = to_sheet

    # Keep track of explicitly-connected decision IDs
    conn_src_set = {e['source'] for e in connectors.values() if e['source']}
    conn_tgt_set = {e['target'] for e in connectors.values() if e['target']}
    explicitly_connected = conn_src_set | conn_tgt_set

    # 3 — Badge shapes
    badge_shapes = [
        info for info in shape_info.values()
        if OUI_NON_RE.match(info['text'])
    ]

    # connector_id → badge text
    connector_badge: Dict[str, str] = {}

    # 3a. Group membership
    for grp in root.findall('.//v:Shape', VISIO_NS):
        children = grp.findall('v:Shapes/v:Shape', VISIO_NS)
        if len(children) < 2:
            continue
        child_ids = [c.get('ID', '') for c in children]
        badge_texts = [shape_info[cid]['text'] for cid in child_ids
                       if cid in shape_info and OUI_NON_RE.match(shape_info[cid]['text'])]
        conn_ids_in_grp = [cid for cid in child_ids if cid in connectors]
        if badge_texts and conn_ids_in_grp:
            for cid in conn_ids_in_grp:
                connector_badge[cid] = badge_texts[0]

    # 3b. Connector own text is Oui/Non
    for conn_id in connectors:
        if conn_id in shape_info and conn_id not in connector_badge:
            t = shape_info[conn_id]['text']
            if OUI_NON_RE.match(t):
                connector_badge[conn_id] = t

    # 3c. Proximity fallback
    if not connector_badge and badge_shapes:
        for badge in badge_shapes:
            bx, by = badge['pin_x'], badge['pin_y']
            if not bx and not by:
                continue
            best_conn, best_dist = None, 999.0
            for conn_id, ends in connectors.items():
                src_id, tgt_id = ends.get('source'), ends.get('target')
                if not src_id or not tgt_id:
                    continue
                src = shape_info.get(src_id, {})
                tgt = shape_info.get(tgt_id, {})
                sx, sy = src.get('pin_x', 0), src.get('pin_y', 0)
                tx, ty = tgt.get('pin_x', 0), tgt.get('pin_y', 0)
                mid_x, mid_y = (sx + tx) / 2, (sy + ty) / 2
                dist = ((bx - mid_x) ** 2 + (by - mid_y) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist, best_conn = dist, conn_id
            if best_conn and best_dist < 1.5:
                connector_badge[best_conn] = badge['text']

    # 4 — Splice: find "placed on line" diamonds (like spliceDecisions in JS)
    # For diamonds NOT explicitly connected, find ALL connectors passing close to them
    SPLICE_THRESH = 0.6  # inches

    decision_ids = {sid for sid, info in shape_info.items() if info['is_decision']}
    unconnected_decisions = decision_ids - explicitly_connected

    syn_ctr = 0
    for did in unconnected_decisions:
        dec = shape_info[did]
        dx, dy = dec['pin_x'], dec['pin_y']
        if not dx and not dy:
            continue

        # Collect ALL connectors passing near this diamond
        to_splice = []
        for conn_id, ends in list(connectors.items()):
            if ends.get('_origConnId'):
                continue
            sv, tv = ends.get('source'), ends.get('target')
            if not sv or not tv or sv == did or tv == did:
                continue
            src = shape_info.get(sv, {})
            tgt = shape_info.get(tv, {})
            ax, ay = src.get('pin_x', 0), src.get('pin_y', 0)
            bx, by = tgt.get('pin_x', 0), tgt.get('pin_y', 0)
            abx, aby = bx - ax, by - ay
            len2 = abx * abx + aby * aby
            if len2 < 1e-9:
                continue
            t = ((dx - ax) * abx + (dy - ay) * aby) / len2
            if t < 0.05 or t > 0.95:
                continue
            px = ax + t * abx
            py = ay + t * aby
            if ((dx - px) ** 2 + (dy - py) ** 2) ** 0.5 < SPLICE_THRESH:
                to_splice.append(conn_id)

        # Splice all nearby connectors for this diamond
        new_conns: Dict[str, Dict] = {}
        for conn_id in to_splice:
            if conn_id not in connectors:
                continue
            ends = connectors[conn_id]
            sv, tv = ends['source'], ends['target']
            badge = connector_badge.get(conn_id, '')
            conn_label = shape_info.get(conn_id, {}).get('text', '')
            k1 = f'__sp{syn_ctr}'
            k2 = f'__sp{syn_ctr+1}'
            syn_ctr += 2
            new_conns[k1] = {'source': sv, 'target': did, 'badge': '', 'conn_label': ''}
            new_conns[k2] = {'source': did, 'target': tv, 'badge': badge,
                             'conn_label': conn_label, '_origConnId': conn_id}
            del connectors[conn_id]
        connectors.update(new_conns)

    # 5 — Build decision entries
    for did in sorted(decision_ids):
        info = shape_info[did]
        outgoing: List[Dict] = []
        incoming: List[Dict] = []
        is_splice = did in unconnected_decisions

        for conn_id, ends in connectors.items():
            src, tgt = ends.get('source'), ends.get('target')
            badge = connector_badge.get(conn_id, ends.get('badge', ''))
            conn_label = ends.get('conn_label', '') or shape_info.get(conn_id, {}).get('text', '')

            if src == did:
                tgt_info = shape_info.get(tgt, {})
                outgoing.append({
                    'conn_id': conn_id,
                    'to_id': tgt,
                    'to_label': tgt_info.get('text', ''),
                    'conn_label': conn_label,
                    'badge': badge or conn_label,
                })
            elif tgt == did:
                src_info = shape_info.get(src, {})
                incoming.append({
                    'conn_id': conn_id,
                    'from_id': src,
                    'from_label': src_info.get('text', ''),
                    'conn_label': conn_label,
                    'badge': badge,
                })

        result['decisions'].append({
            'id': did,
            'label': info['text'],
            'master_name': info['master_name'],
            'layer': info['layer'],
            'splice': is_splice,
            'outgoing': outgoing,
            'incoming': incoming,
        })
