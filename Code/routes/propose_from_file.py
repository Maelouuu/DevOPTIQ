# Code/routes/propose_from_file.py
"""
Propositions Knowledge/SF/Aptitudes/HSC basées sur un fichier Excel de référence
fourni par l'utilisateur (ex : JobwiseCompetency.xlsx).

Structure attendue du fichier :
  Col A  ObjectID   (ignoré)
  Col B  JobId      (ignoré)
  Col C  JobText    — intitulé du poste
  Col D  GrpName    — catégorie :
            'Behavioural Competencies' | 'Leadership Competencies'
              → HSC / SCA
            'Technical Skills' | 'Functional Competencies'
              → Knowledge & Practical Skills (savoirs + savoir-faires)
              → Aptitudes
  Col E  CompName   — nom de la compétence
  Col F  Required Score  (ignoré)

Le fichier est stocké dans FileBlob sous le nom 'refcomp_u{user_id}.xlsx'.
"""

import io
import re
from collections import Counter, defaultdict

from flask import Blueprint, request, jsonify, session
from sqlalchemy.orm.attributes import flag_modified

from Code.extensions import db
from Code.models.models import Activities, FileBlob, Task

propose_from_file_bp = Blueprint('propose_from_file', __name__, url_prefix='/propose_from_file')

GROUPS_SF    = ['Technical Skills', 'Functional Competencies']
GROUPS_HSC   = ['Behavioural Competencies', 'Leadership Competencies']
STOP_WORDS   = {
    'the', 'de', 'du', 'des', 'le', 'la', 'les', 'et', 'of', 'and',
    'for', 'in', 'à', 'un', 'une', 'en', 'sur', 'par', 'avec', 'au',
    'management', 'manager', 'gestion', 'senior', 'junior', 'head',
    'chief', 'officer', 'specialist', 'coordinateur', 'responsable',
}

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _user_id():
    return session.get('user_id')


def _blob_name(uid):
    return f'refcomp_u{uid}.xlsx'


def _load_blob(uid) -> bytes | None:
    blob = FileBlob.query.filter_by(filename=_blob_name(uid)).first()
    return blob.data if blob else None


def _tokenize(text: str) -> set:
    tokens = re.sub(r'[^\w\s]', '', text.lower()).split()
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 2}


def _parse_file(data: bytes):
    """Parse l'Excel et retourne { job_title_lower: { group: [comp_name, ...] } }."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    job_map: dict[str, defaultdict[str, list]] = defaultdict(lambda: defaultdict(list))
    for row in ws.iter_rows(min_row=2, values_only=True):
        job_text = row[2] if len(row) > 2 else None
        grp      = row[3] if len(row) > 3 else None
        comp     = row[4] if len(row) > 4 else None
        if job_text and grp and comp:
            job_map[str(job_text).lower()][str(grp)].append(str(comp))
    return job_map


def _parse_stats(data: bytes) -> dict:
    job_map = _parse_file(data)
    grp_names = Counter()
    for job_grps in job_map.values():
        for grp in job_grps:
            grp_names[grp] += 1
    # unique competencies per group
    grp_comps: dict[str, set] = defaultdict(set)
    for job_grps in job_map.values():
        for grp, comps in job_grps.items():
            grp_comps[grp].update(comps)
    return {grp: len(names) for grp, names in grp_comps.items()}


def _build_activity_context(act: Activities) -> str:
    """Contexte enrichi : nom + description + noms des tâches existantes."""
    parts = [act.name or '']
    if act.description:
        parts.append(act.description)
    tasks = Task.query.filter_by(activity_id=act.id).all()
    parts.extend(t.name for t in tasks if t.name)
    return ' '.join(parts)


def _propose_from_job_map(activity_context: str, job_map, groups: list, max_results: int = 12) -> list[str]:
    """Retourne les compétences les plus pertinentes pour l'activité donnée."""
    act_tokens = _tokenize(activity_context)

    # Scorer chaque poste
    job_scores: list[tuple[int, list]] = []
    for job_title, grps in job_map.items():
        comps = []
        for g in groups:
            comps.extend(grps.get(g, []))
        if not comps:
            continue
        job_tokens = _tokenize(job_title)
        overlap = len(act_tokens & job_tokens)
        partial = sum(1 for at in act_tokens for jt in job_tokens
                      if at in jt or jt in at) if overlap == 0 else 0
        score = overlap * 3 + partial
        if score > 0:
            job_scores.append((score, comps))

    if job_scores:
        job_scores.sort(key=lambda x: -x[0])
        comp_scores: Counter = Counter()
        for score, comps in job_scores[:5]:
            for c in comps:
                comp_scores[c] += score
        # Bonus : si le nom de la compétence contient des tokens de l'activité,
        # on augmente son score (double signal : poste ET nom de compétence)
        for c in list(comp_scores.keys()):
            c_tokens = _tokenize(c)
            overlap = len(act_tokens & c_tokens)
            if overlap:
                comp_scores[c] += overlap * 2
        proposals = [c for c, _ in comp_scores.most_common(max_results)]
        if proposals:
            return proposals

    # Fallback : score direct nom de compétence ↔ contexte activité,
    # puis les plus fréquentes
    direct_scores: Counter = Counter()
    all_comps: Counter = Counter()
    for grps in job_map.values():
        for g in groups:
            for c in grps.get(g, []):
                all_comps[c] += 1
                c_tokens = _tokenize(c)
                overlap = len(act_tokens & c_tokens)
                if overlap:
                    direct_scores[c] += overlap
    if direct_scores:
        return [c for c, _ in direct_scores.most_common(max_results)]
    top = [c for c, _ in all_comps.most_common(max_results * 3)]
    step = max(1, len(top) // max_results)
    return [top[i] for i in range(0, min(len(top), max_results * step), step)][:max_results]


# ────────────────────────────────────────────────────────────────────────────
# Routes
# ────────────────────────────────────────────────────────────────────────────

@propose_from_file_bp.route('/upload', methods=['POST'])
def upload_ref():
    uid = _user_id()
    if not uid:
        return jsonify({"error": "Non autorisé"}), 403

    f = request.files.get('file')
    if not f:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    raw = f.read()
    fname = _blob_name(uid)
    blob = FileBlob.query.filter_by(filename=fname).first()
    if blob:
        blob.data = raw
        blob.mimetype = f.content_type or 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        blob = FileBlob(
            filename=fname,
            mimetype=f.content_type or 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            data=raw,
        )
        db.session.add(blob)
    db.session.commit()

    try:
        stats = _parse_stats(raw)
        return jsonify({"ok": True, "stats": stats}), 200
    except Exception as exc:
        return jsonify({"ok": True, "stats": {}, "warning": str(exc)}), 200


@propose_from_file_bp.route('/status', methods=['GET'])
def ref_status():
    uid = _user_id()
    if not uid:
        return jsonify({"has_file": False}), 200
    data = _load_blob(uid)
    if not data:
        return jsonify({"has_file": False}), 200
    try:
        stats = _parse_stats(data)
        return jsonify({"has_file": True, "stats": stats}), 200
    except Exception:
        return jsonify({"has_file": True, "stats": {}}), 200


@propose_from_file_bp.route('/propose_sf', methods=['POST'])
def propose_sf():
    """Propose Knowledge & Practical Skills depuis le fichier de référence."""
    uid = _user_id()
    if not uid:
        return jsonify({"error": "Non autorisé"}), 403

    data = _load_blob(uid)
    if not data:
        return jsonify({"error": "no_file"}), 404

    body = request.get_json(force=True) or {}
    act = Activities.query.get(body.get('activity_id')) if body.get('activity_id') else None
    ctx = _build_activity_context(act) if act else (body.get('activity_name') or '')

    job_map = _parse_file(data)
    proposals = _propose_from_job_map(ctx, job_map, GROUPS_SF, max_results=14)
    # Répartir ~60% savoir-faires, ~40% savoirs
    split = max(1, len(proposals) * 6 // 10)
    return jsonify({
        "proposals_sf": proposals[:split],
        "proposals_s":  proposals[split:],
        "source": "file",
    }), 200


@propose_from_file_bp.route('/propose_aptitudes', methods=['POST'])
def propose_aptitudes():
    """Propose Aptitudes depuis le fichier de référence."""
    uid = _user_id()
    if not uid:
        return jsonify({"error": "Non autorisé"}), 403

    data = _load_blob(uid)
    if not data:
        return jsonify({"error": "no_file"}), 404

    body = request.get_json(force=True) or {}
    act = Activities.query.get(body.get('activity_id')) if body.get('activity_id') else None
    ctx = _build_activity_context(act) if act else (body.get('activity_name') or '')

    job_map = _parse_file(data)
    proposals = _propose_from_job_map(ctx, job_map, GROUPS_SF, max_results=8)
    return jsonify({"proposals": proposals, "source": "file"}), 200


@propose_from_file_bp.route('/propose_hsc', methods=['POST'])
def propose_hsc():
    """Propose SCA/HSC depuis le fichier de référence (Behavioural + Leadership)."""
    uid = _user_id()
    if not uid:
        return jsonify({"error": "Non autorisé"}), 403

    data = _load_blob(uid)
    if not data:
        return jsonify({"error": "no_file"}), 404

    body = request.get_json(force=True) or {}
    act = Activities.query.get(body.get('activity_id')) if body.get('activity_id') else None
    ctx = _build_activity_context(act) if act else (body.get('activity_name') or '')

    job_map = _parse_file(data)
    proposals = _propose_from_job_map(ctx, job_map, GROUPS_HSC, max_results=9)
    hsc_list = [
        {"habilete": name, "niveau": "2 (Acquisition)", "justification": ""}
        for name in proposals
    ]
    return jsonify({"proposals": hsc_list, "source": "file"}), 200
