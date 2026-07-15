# Code/routes/result_capabilities.py
# CDC 2 (V1.1) — Génération de la compétence PRINCIPALE (fondée sur les RÉSULTATS) et
# analyse S/SF/HSC PAR RÉSULTAT. La compétence = capacité démontrée à tenir l'activité en
# produisant ses résultats au niveau requis ; elle n'énumère PAS les S/SF/HSC. Les S/SF/HSC
# sont reliés à chaque RESULT (table result_capability_links) pour le diagnostic d'écart.
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session
from Code.extensions import db
from Code.models.models import (
    Data, Task, Activities, Competency, Savoir, SavoirFaire, Softskill,
    ResultCapabilityLink, Entity, Link,
)
from Code.routes.propose_common import openai_client_or_none
from Code.routes.qualify_outputs import get_activity_outputs

result_cap_bp = Blueprint("result_capabilities", __name__, url_prefix="/competence")

ITEM_MODELS = {"SAVOIR": Savoir, "SAVOIR_FAIRE": SavoirFaire, "HSC": Softskill}


def _lang():
    return session.get("lang", "fr")


def _results_of(activity_id):
    return [d for d in get_activity_outputs(activity_id) if d.semantic_nature == "RESULT"]


def _result_ctx(activity, results):
    tasks = Task.query.filter_by(activity_id=activity.id).order_by(Task.order).all()
    lines = [f"Activité: {activity.name}", f"Description: {activity.description or '-'}", "Tâches:"]
    lines += [f"  - {t.name}" for t in tasks] or ["  -"]
    lines.append("Résultats de l'activité (RESULT) :")
    for d in results:
        std = f" — standard minimal: {d.minimum_performance_text}" if d.minimum_performance_text else ""
        lines.append(f"  - [id={d.id}] {d.name}{std}")
    return "\n".join(lines)


# ─────────────────────────── Compétence principale (CDC 2.2–2.4) ───────────────────────────
COMP_SYSTEM = (
    "Tu es un analyste de la méthode OPTIQ. La compétence est la CAPACITÉ DÉMONTRÉE à tenir "
    "régulièrement une activité en produisant ses RÉSULTATS au niveau minimal de performance requis. "
    "La formulation de la compétence NE DOIT PAS énumérer les savoirs, savoir-faire ou HSC mobilisés, "
    "ni recopier le standard de performance. Analyse UNIQUEMENT les résultats (RESULT) pour définir ce "
    "qui démontre la tenue de l'activité ; les tâches et autres données ne servent que de contexte. "
    "Propose UNE SEULE compétence principale. Si plusieurs résultats sont très indépendants, produisent "
    "des finalités différentes et reposent sur des chaînes de tâches différentes, lève une alerte de "
    "granularité (sans créer ni supprimer d'activité). Réponds UNIQUEMENT en JSON."
)
COMP_SCHEMA = (
    '{"activity_competence": {"description_fr": "...", "description_en": "..."}, '
    '"result_ids_used": [<int>], '
    '"granularity_alert": {"alert": <bool>, "reason_fr": "...", "reason_en": "..."}}'
)


@result_cap_bp.route("/generate/<int:activity_id>", methods=["POST"])
def generate_competence(activity_id):
    """Génère (sans sauvegarder) la compétence principale fondée sur les RESULT."""
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "activity_not_found"}), 404
    lang = _lang()
    results = _results_of(activity_id)
    if not results:
        return jsonify({"competence": None, "source": "no_result",
                        "warning": ("Aucun résultat qualifié : la compétence ne peut pas être générée."
                                    if lang == "fr" else "No qualified result: competence cannot be generated.")}), 200
    client, err = openai_client_or_none()
    if client is None:
        return jsonify({"competence": None, "source": err or "no_ai"}), 200
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": COMP_SYSTEM},
                {"role": "user", "content": f"=== CONTEXTE ===\n{_result_ctx(activity, results)}\n\n"
                                             f"Renvoie un JSON respectant EXACTEMENT ce schéma :\n{COMP_SCHEMA}"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = json.loads(resp.choices[0].message.content)
        comp = raw.get("activity_competence") or {}
        return jsonify({
            "competence": {
                "description_fr": (comp.get("description_fr") or "").strip(),
                "description_en": (comp.get("description_en") or "").strip(),
            },
            "result_ids_used": [i for i in (raw.get("result_ids_used") or []) if i in {d.id for d in results}],
            "granularity_alert": raw.get("granularity_alert") or {"alert": False},
            "source": "AI",
        }), 200
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"competence": None, "source": "error", "error": str(e)}), 200


@result_cap_bp.route("/save/<int:activity_id>", methods=["POST"])
def save_competence(activity_id):
    """Enregistre LA compétence principale (remplace les compétences existantes de l'activité)."""
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "activity_not_found"}), 404
    payload = request.get_json(force=True) or {}
    desc = (payload.get("description") or "").strip()
    if not desc:
        return jsonify({"error": "empty_description"}), 400
    Competency.query.filter_by(activity_id=activity_id).delete()
    db.session.add(Competency(activity_id=activity_id, description=desc))
    db.session.commit()
    return jsonify({"ok": True, "description": desc}), 200


# ─────────────────────── S/SF/HSC par résultat (CDC 2.5–2.7) ───────────────────────
SFHSC_SYSTEM = (
    "Tu es un analyste OPTIQ. Pour CHAQUE résultat (RESULT) d'une activité, tu identifies, dans "
    "cet ordre : les savoir-faire opératoires nécessaires pour produire le résultat, puis les savoirs "
    "(connaissances/règles/référentiels) qui les soutiennent, puis UNIQUEMENT les HSC réellement "
    "sollicitées par les contraintes, arbitrages ou interactions de la situation. Un savoir-faire n'est "
    "pas une tâche ni un résultat ; un savoir est une connaissance, pas une action ; une HSC n'est pas un "
    "trait de personnalité vague. Donne pour chaque HSC un niveau requis 1 à 4. Réponds UNIQUEMENT en JSON."
)
SFHSC_SCHEMA = (
    '{"results": [{"data_id": <int>, '
    '"savoir_faires": ["..."], "savoirs": ["..."], '
    '"hsc": [{"name": "...", "required_level": <1-4>}]}]}'
)


def _get_or_create_item(item_type, activity_id, text, required_level=None):
    """Récupère un item (Savoir/SavoirFaire/Softskill) par texte insensible à la casse dans
    l'activité, sinon le crée. Renvoie l'id."""
    text = (text or "").strip()
    if not text:
        return None
    Model = ITEM_MODELS[item_type]
    if item_type == "HSC":
        existing = Softskill.query.filter(Softskill.activity_id == activity_id,
                                          db.func.lower(Softskill.habilete) == text.lower()).first()
        if existing:
            return existing.id
        obj = Softskill(activity_id=activity_id, habilete=text,
                        niveau=str(required_level) if required_level else "1")
    else:
        existing = Model.query.filter(Model.activity_id == activity_id,
                                      db.func.lower(Model.description) == text.lower()).first()
        if existing:
            return existing.id
        obj = Model(activity_id=activity_id, description=text)
    db.session.add(obj)
    db.session.flush()
    return obj.id


@result_cap_bp.route("/result_links/generate/<int:activity_id>", methods=["POST"])
def generate_result_links(activity_id):
    """Génère les S/SF/HSC PAR RÉSULTAT, crée les items manquants et les liens
    result_capability_links (source=AI). Déduplique les liens (contrainte d'unicité)."""
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "activity_not_found"}), 404
    results = _results_of(activity_id)
    if not results:
        return jsonify({"links": [], "source": "no_result"}), 200
    client, err = openai_client_or_none()
    if client is None:
        return jsonify({"links": [], "source": err or "no_ai"}), 200
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SFHSC_SYSTEM},
                {"role": "user", "content": f"=== CONTEXTE ===\n{_result_ctx(activity, results)}\n\n"
                                             f"Renvoie un JSON respectant EXACTEMENT ce schéma :\n{SFHSC_SCHEMA}"},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = json.loads(resp.choices[0].message.content)
        entity_id = activity.entity_id
        valid_ids = {d.id for d in results}
        created = 0
        for block in (raw.get("results") or []):
            did = block.get("data_id")
            if did not in valid_ids:
                continue
            triples = ([("SAVOIR_FAIRE", t, None) for t in (block.get("savoir_faires") or [])]
                       + [("SAVOIR", t, None) for t in (block.get("savoirs") or [])]
                       + [("HSC", h.get("name"), h.get("required_level")) for h in (block.get("hsc") or []) if isinstance(h, dict)])
            for item_type, text, lvl in triples:
                item_id = _get_or_create_item(item_type, activity_id, text, lvl)
                if not item_id:
                    continue
                exists = ResultCapabilityLink.query.filter_by(
                    activity_id=activity_id, data_id=did, item_type=item_type, item_id=item_id).first()
                if exists:
                    if lvl and not exists.required_level:
                        exists.required_level = lvl
                    continue
                db.session.add(ResultCapabilityLink(
                    entity_id=entity_id, activity_id=activity_id, data_id=did,
                    item_type=item_type, item_id=item_id,
                    required_level=lvl if isinstance(lvl, int) else None, source="AI"))
                created += 1
        db.session.commit()
        return jsonify({"source": "AI", "created": created, "links": _links_payload(activity_id)}), 200
    except Exception as e:
        current_app.logger.exception(e)
        db.session.rollback()
        return jsonify({"links": [], "source": "error", "error": str(e)}), 200


def _item_label(item_type, item_id):
    Model = ITEM_MODELS.get(item_type)
    if not Model:
        return None
    obj = Model.query.get(item_id)
    if not obj:
        return None
    return obj.habilete if item_type == "HSC" else obj.description


def _links_payload(activity_id):
    """Liens groupés par résultat + badges par item (résultats auxquels il est relié)."""
    results = {d.id: d.name for d in _results_of(activity_id)}
    links = ResultCapabilityLink.query.filter_by(activity_id=activity_id).all()
    by_result, badges = {}, {}
    # numérotation R1, R2… stable par ordre d'id
    order = {rid: f"R{i+1}" for i, rid in enumerate(sorted(results))}
    for lk in links:
        rlabel = order.get(lk.data_id)
        by_result.setdefault(lk.data_id, {"result_label": rlabel, "result_name": results.get(lk.data_id),
                                          "items": []})
        by_result[lk.data_id]["items"].append({
            "id": lk.id, "item_type": lk.item_type, "item_id": lk.item_id,
            "item_label": _item_label(lk.item_type, lk.item_id),
            "required_level": lk.required_level, "source": lk.source})
        key = f"{lk.item_type}:{lk.item_id}"
        badges.setdefault(key, []).append({"result_id": lk.data_id, "result_label": rlabel,
                                           "result_name": results.get(lk.data_id)})
    return {"by_result": list(by_result.values()), "badges": badges}


@result_cap_bp.route("/result_links/<int:activity_id>", methods=["GET"])
def get_result_links(activity_id):
    if not Activities.query.get(activity_id):
        return jsonify({"error": "activity_not_found"}), 404
    return jsonify(_links_payload(activity_id)), 200


@result_cap_bp.route("/result_links/<int:activity_id>", methods=["POST"])
def upsert_result_link(activity_id):
    """Crée/supprime un lien manuellement (correction utilisateur, source=MANUAL).
    Payload create : {data_id, item_type, item_id, required_level?}. Payload delete : {delete_id}."""
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "activity_not_found"}), 404
    payload = request.get_json(force=True) or {}
    if payload.get("delete_id"):
        ResultCapabilityLink.query.filter_by(id=payload["delete_id"], activity_id=activity_id).delete()
        db.session.commit()
        return jsonify({"ok": True, "links": _links_payload(activity_id)}), 200
    did, it, iid = payload.get("data_id"), payload.get("item_type"), payload.get("item_id")
    if not (did and it in ITEM_MODELS and iid):
        return jsonify({"error": "invalid_payload"}), 400
    exists = ResultCapabilityLink.query.filter_by(
        activity_id=activity_id, data_id=did, item_type=it, item_id=iid).first()
    if not exists:
        db.session.add(ResultCapabilityLink(
            entity_id=activity.entity_id, activity_id=activity_id, data_id=did, item_type=it,
            item_id=iid, required_level=payload.get("required_level"), source="MANUAL"))
        db.session.commit()
    return jsonify({"ok": True, "links": _links_payload(activity_id)}), 200
