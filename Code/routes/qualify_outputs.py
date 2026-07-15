# Code/routes/qualify_outputs.py
# CDC 1 (V1.1) — Qualification automatique des données de sortie.
# Distingue les données qui DÉMONTRENT la tenue de l'activité (RESULT) de celles qui
# mesurent (MEASURE), signalent (EVENT) ou informent (INFORMATION). L'IA propose une
# nature pour chaque sortie ; l'utilisateur valide globalement et ne corrige que les
# exceptions. Les codes RESULT/MEASURE/EVENT/INFORMATION ne sont JAMAIS affichés tels
# quels : l'UI récupère le libellé FR ou EN via NATURE_LABELS.
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session
from Code.extensions import db
from Code.models.models import Data, Link, Task, Activities
from Code.routes.propose_common import openai_client_or_none

qualify_bp = Blueprint("qualify_outputs", __name__, url_prefix="/qualify")

# Codes techniques internes → libellés localisés (jamais stocker le libellé en base).
NATURE_LABELS = {
    "RESULT":      {"fr": "Résultat de l'activité", "en": "Activity result"},
    "MEASURE":     {"fr": "Mesure / preuve",        "en": "Measure / evidence"},
    "EVENT":       {"fr": "Événement / signal",     "en": "Event / signal"},
    "INFORMATION": {"fr": "Information produite",    "en": "Produced information"},
}
VALID_NATURES = set(NATURE_LABELS)


def _lang():
    return session.get("lang", "fr")


def label_for(nature, lang=None):
    lang = lang or _lang()
    if not nature or nature not in NATURE_LABELS:
        return None
    return NATURE_LABELS[nature].get(lang, NATURE_LABELS[nature]["fr"])


def get_activity_outputs(activity_id):
    """Données de sortie d'une activité = Data ciblées par un Link sortant
    (source_activity_id = activité, target_data_id renseigné)."""
    links = Link.query.filter(
        Link.source_activity_id == activity_id,
        Link.target_data_id.isnot(None),
    ).all()
    seen, ids = set(), []
    for lk in links:
        if lk.target_data_id not in seen:
            seen.add(lk.target_data_id)
            ids.append(lk.target_data_id)
    if not ids:
        return []
    by_id = {d.id: d for d in Data.query.filter(Data.id.in_(ids)).all()}
    return [by_id[i] for i in ids if i in by_id]


def _serialize_output(d, lang=None):
    return {
        "data_id": d.id,
        "name": d.name,
        "flux_type": d.type,                       # type de flux (≠ nature sémantique)
        "nature": d.semantic_nature,               # code interne (peut être None)
        "nature_label": label_for(d.semantic_nature, lang),
        "minimum_performance_text": d.minimum_performance_text or "",
        "qualification_source": d.qualification_source,
        "qualified": bool(d.semantic_nature),
    }


def _build_context(activity, outputs):
    """Contexte transmis à l'IA (CDC 1.6) : activité, description, tâches, sorties,
    type de flux et activités destinataires."""
    tasks = Task.query.filter_by(activity_id=activity.id).order_by(Task.order).all()
    dest = {}
    for lk in Link.query.filter(Link.source_activity_id == activity.id).all():
        if lk.target_activity_id:
            a = Activities.query.get(lk.target_activity_id)
            if a:
                dest[a.id] = a.name
    lines = [
        f"Activité: {activity.name}",
        f"Description: {activity.description or '-'}",
        "Tâches:",
    ]
    lines += [f"  - {t.name}" for t in tasks] or ["  -"]
    lines.append("Données de sortie (à qualifier):")
    for d in outputs:
        lines.append(f"  - [id={d.id}] {d.name} (type de flux: {d.type})")
    lines.append("Activités destinataires: " + (", ".join(dest.values()) or "-"))
    return "\n".join(lines)


PROMPT_SYSTEM = {
    "fr": (
        "Tu es un analyste de la méthode OPTIQ. Tu qualifies la NATURE SÉMANTIQUE de chaque "
        "donnée de sortie d'une activité, selon ces définitions strictes :\n"
        "- RESULT : production dont la tenue au standard attendu démontre DIRECTEMENT que l'activité "
        "est correctement tenue.\n"
        "- MEASURE : donnée qui mesure, constate ou objectivise un état, un déroulement ou un résultat.\n"
        "- EVENT : survenue d'un fait qui déclenche ou conditionne une autre activité ; sa seule "
        "production ne démontre pas la maîtrise de l'activité source.\n"
        "- INFORMATION : information utile à une autre activité, sans être un résultat démonstratif, "
        "une mesure ni un événement.\n"
        "Pour chaque RESULT, propose un standard minimal de performance (niveau à partir duquel "
        "l'activité est considérée tenue de manière autonome). Ne modifie jamais la cartographie. "
        "Réponds UNIQUEMENT en JSON."
    ),
    "en": (
        "You are an OPTIQ method analyst. Qualify the SEMANTIC NATURE of each activity output, "
        "using these strict definitions:\n"
        "- RESULT: output whose achievement at the expected standard DIRECTLY demonstrates the "
        "activity is correctly performed.\n"
        "- MEASURE: data that measures, observes or objectifies a state, a process or a result.\n"
        "- EVENT: occurrence of a fact that triggers or conditions another activity; producing it "
        "alone does not demonstrate mastery of the source activity.\n"
        "- INFORMATION: information useful to another activity, without being a demonstrative result, "
        "a measure or an event.\n"
        "For each RESULT, propose a minimum performance standard (threshold from which the activity is "
        "considered performed autonomously). Never modify the cartography. Answer ONLY in JSON."
    ),
}


def _prompt_user(ctx, lang):
    schema = (
        '{"outputs": [{"data_id": <int>, "suggested_nature": "RESULT|MEASURE|EVENT|INFORMATION", '
        '"confidence": "high|medium|low", "justification": "<courte phrase>", '
        '"suggested_minimum_performance": "<uniquement si RESULT, sinon omettre>"}]}'
    )
    head = "=== CONTEXTE ACTIVITÉ ===" if lang == "fr" else "=== ACTIVITY CONTEXT ==="
    ask = (
        "Qualifie chaque donnée de sortie. Renvoie un objet JSON respectant EXACTEMENT ce schéma :"
        if lang == "fr"
        else "Qualify each output. Return a JSON object matching EXACTLY this schema:"
    )
    return f"{head}\n{ctx}\n\n{ask}\n{schema}"


def _fallback_proposals(outputs):
    """IA indisponible (CDC §8) : ne JAMAIS inventer de nature. On renvoie « à qualifier »."""
    return [{
        "data_id": d.id,
        "name": d.name,
        "suggested_nature": None,
        "confidence": "none",
        "justification": "",
        "suggested_minimum_performance": "",
    } for d in outputs]


@qualify_bp.route("/outputs/<int:activity_id>", methods=["GET"])
def outputs(activity_id):
    """Sorties de l'activité + qualification courante (pour le panneau de validation)."""
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "activity_not_found"}), 404
    lang = _lang()
    outs = get_activity_outputs(activity_id)
    return jsonify({
        "activity_id": activity_id,
        "outputs": [_serialize_output(d, lang) for d in outs],
        "labels": {k: v[lang] for k, v in NATURE_LABELS.items()},
        "all_qualified": all(d.semantic_nature for d in outs) if outs else False,
    }), 200


@qualify_bp.route("/analyze/<int:activity_id>", methods=["POST"])
def analyze(activity_id):
    """Lance la qualification IA des sorties de l'activité (CDC 1.5/1.6).
    N'écrit rien : renvoie des propositions à valider. Repli sans clé → « à qualifier »."""
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "activity_not_found"}), 404
    lang = _lang()
    outs = get_activity_outputs(activity_id)
    if not outs:
        return jsonify({"outputs": [], "source": "no_outputs",
                        "warning": ("Cette activité n'a aucune donnée de sortie."
                                    if lang == "fr" else "This activity has no output data.")}), 200

    client, err = openai_client_or_none()
    if client is None:
        return jsonify({"outputs": _fallback_proposals(outs), "source": err or "no_ai"}), 200

    try:
        ctx = _build_context(activity, outs)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM.get(lang, PROMPT_SYSTEM["fr"])},
                {"role": "user", "content": _prompt_user(ctx, lang)},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = json.loads(resp.choices[0].message.content)
        valid_ids = {d.id for d in outs}
        props = []
        for o in (raw.get("outputs") or []):
            did = o.get("data_id")
            if did not in valid_ids:
                continue
            nature = o.get("suggested_nature")
            if nature not in VALID_NATURES:
                nature = None
            props.append({
                "data_id": did,
                "name": next((d.name for d in outs if d.id == did), ""),
                "suggested_nature": nature,
                "confidence": o.get("confidence") or "medium",
                "justification": (o.get("justification") or "").strip(),
                "suggested_minimum_performance": (o.get("suggested_minimum_performance") or "").strip(),
            })
        # sorties non traitées par l'IA → à qualifier
        done = {p["data_id"] for p in props}
        props += [p for p in _fallback_proposals(outs) if p["data_id"] not in done]

        n_result = sum(1 for p in props if p["suggested_nature"] == "RESULT")
        warning = None
        if n_result == 0:
            warning = ("Aucun résultat de l'activité n'a été identifié. La compétence ne peut pas "
                       "être générée de manière fiable." if lang == "fr"
                       else "No activity result was identified. The competence cannot be reliably generated.")
        elif n_result > 3:
            warning = ("Plus de trois résultats identifiés : vérifiez la granularité de l'activité."
                       if lang == "fr" else "More than three results identified: check the activity granularity.")
        return jsonify({"outputs": props, "source": "AI", "warning": warning}), 200
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"outputs": _fallback_proposals(outs), "source": "error", "error": str(e)}), 200


@qualify_bp.route("/save/<int:activity_id>", methods=["POST"])
def save(activity_id):
    """Persiste les qualifications validées (CDC 1.7). Payload :
    {"outputs":[{"data_id","nature"(code|null),"minimum_performance_text","source"(AI|MANUAL)}]}"""
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "activity_not_found"}), 404
    payload = request.get_json(force=True) or {}
    items = payload.get("outputs") or []
    valid_ids = {d.id for d in get_activity_outputs(activity_id)}
    now = datetime.utcnow()
    warnings = []
    saved = 0
    for it in items:
        did = it.get("data_id")
        if did not in valid_ids:
            continue
        d = Data.query.get(did)
        if not d:
            continue
        nature = it.get("nature")
        if nature not in VALID_NATURES:
            nature = None
        # CDC 1.9 : requalifier un RESULT déjà utilisé → avertir (non bloquant)
        if d.semantic_nature == "RESULT" and nature != "RESULT":
            warnings.append({"data_id": did, "name": d.name,
                             "message": ("Cette donnée était un résultat : vérifiez les évaluations/liens associés."
                                         if _lang() == "fr" else
                                         "This data was a result: check related evaluations/links.")})
        d.semantic_nature = nature
        d.minimum_performance_text = (it.get("minimum_performance_text") or "").strip() or None
        d.qualification_source = "MANUAL" if it.get("source") == "MANUAL" else ("AI" if nature else None)
        d.qualification_updated_at = now
        saved += 1
    db.session.commit()
    outs = get_activity_outputs(activity_id)
    return jsonify({"saved": saved, "warnings": warnings,
                    "outputs": [_serialize_output(d) for d in outs]}), 200
