# Code/routes/hsc_positioning.py
# CDC 7 (V1.1) — Auto-positionnement et évaluation des HSC. On positionne à partir de
# COMPORTEMENTS OBSERVABLES et de situations vécues, sans demander à la personne de choisir
# directement un niveau. L'IA propose un niveau PROBABLE ; seul un évaluateur habilité valide.
import json
from flask import Blueprint, request, jsonify, current_app, session
from Code.prompts import get_prompt, prompts_available
from Code.extensions import db
from Code.models.models import HscLevelDescriptor, Entity
from Code.routes.propose_common import ai_model, openai_client_or_none

hsc_bp = Blueprint("hsc_positioning", __name__, url_prefix="/hsc")

# Libellés de niveau STABILISÉS partout (CDC 7.2). « Excellence » supprimé : niveau 4 = Expertise.
HSC_LEVELS = {
    1: {"fr": "Aptitude",   "en": "Basic"},
    2: {"fr": "Acquisition", "en": "Developing"},
    3: {"fr": "Maîtrise",   "en": "Proficient"},
    4: {"fr": "Expertise",  "en": "Expert"},
}


def _lang():
    return session.get("lang", "fr")


@hsc_bp.route("/levels", methods=["GET"])
def levels():
    lang = _lang()
    return jsonify({"levels": {str(k): v[lang] for k, v in HSC_LEVELS.items()}}), 200


@hsc_bp.route("/descriptors/<path:hsc_name>", methods=["GET"])
def descriptors(hsc_name):
    lang = _lang()
    eid = Entity.get_active_id()
    q = HscLevelDescriptor.query.filter_by(hsc_name=hsc_name)
    rows = q.filter((HscLevelDescriptor.entity_id == eid) | (HscLevelDescriptor.entity_id.is_(None))).all()
    by_level = {}
    for r in rows:
        by_level[r.level] = {
            "level": r.level, "level_label": HSC_LEVELS.get(r.level, {}).get(lang),
            "descriptor": (r.descriptor_en if lang == "en" and r.descriptor_en else r.descriptor_fr),
            "observable_behaviors": (r.observable_behaviors_en if lang == "en" and r.observable_behaviors_en else r.observable_behaviors_fr),
            "example_situations": (r.example_situations_en if lang == "en" and r.example_situations_en else r.example_situations_fr),
            "development_focus": (r.development_focus_en if lang == "en" and r.development_focus_en else r.development_focus_fr),
        }
    return jsonify({"hsc_name": hsc_name, "descriptors": [by_level[k] for k in sorted(by_level)]}), 200


@hsc_bp.route("/descriptors", methods=["POST"])
def upsert_descriptor():
    """Enregistre/complète un descripteur comportemental (référentiel HSC)."""
    p = request.get_json(force=True) or {}
    name, lvl = (p.get("hsc_name") or "").strip(), p.get("level")
    if not name or lvl not in HSC_LEVELS:
        return jsonify({"error": "invalid"}), 400
    eid = Entity.get_active_id()
    row = HscLevelDescriptor.query.filter_by(entity_id=eid, hsc_name=name, level=lvl).first()
    if not row:
        row = HscLevelDescriptor(entity_id=eid, hsc_name=name, level=lvl)
        db.session.add(row)
    for f in ("descriptor_fr", "descriptor_en", "observable_behaviors_fr", "observable_behaviors_en",
              "example_situations_fr", "example_situations_en", "development_focus_fr", "development_focus_en"):
        if f in p:
            setattr(row, f, (p.get(f) or "").strip() or None)
    db.session.commit()
    return jsonify({"ok": True, "id": row.id}), 200




@hsc_bp.route("/position", methods=["POST"])
def position():
    """Auto-positionnement (CDC 7.4). Entrée : {hsc_name, responses:[...], examples?}. Sortie IA :
    niveau probable + confiance + ce qui manque pour le niveau suivant. Repli sans clé → null."""
    p = request.get_json(force=True) or {}
    name = (p.get("hsc_name") or "").strip()
    if not name:
        return jsonify({"error": "invalid"}), 400
    lang = _lang()
    client, err = openai_client_or_none()
    pos_system = get_prompt("hsc.positioning.system")
    if client is None or pos_system is None:
        return jsonify({"proposal": None, "source": err or "no_ai"}), 200
    responses = p.get("responses") or []
    examples = p.get("examples") or ""
    schema = ('{"probable_level": <1-4>, "confidence": "high|medium|low", "evidence_summary": "...", '
              '"missing_evidence_for_next_level": "...", "development_focus": "..."}')
    try:
        resp = client.chat.completions.create(
            model=ai_model(),
            messages=[{"role": "system", "content": pos_system},
                      {"role": "user", "content": f"HSC : {name}\nRéponses situations :\n"
                                                  + "\n".join(f"- {r}" for r in responses)
                                                  + (f"\nExemple vécu : {examples}" if examples else "")
                                                  + f"\nRéponds en {'français' if lang == 'fr' else 'English'}.\n{schema}"}],
            temperature=0.2, response_format={"type": "json_object"})
        raw = json.loads(resp.choices[0].message.content)
        lvl = raw.get("probable_level")
        if lvl not in HSC_LEVELS:
            lvl = None
        return jsonify({"proposal": {
            "hsc_name": name, "probable_level": lvl,
            "probable_label": HSC_LEVELS.get(lvl, {}).get(lang) if lvl else None,
            "confidence": raw.get("confidence") or "medium",
            "evidence_summary": raw.get("evidence_summary") or "",
            "missing_evidence_for_next_level": raw.get("missing_evidence_for_next_level") or "",
            "development_focus": raw.get("development_focus") or "",
        }, "source": "AI", "note": "Proposition — à valider par un évaluateur habilité."}), 200
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"proposal": None, "source": "error", "error": str(e)}), 200
