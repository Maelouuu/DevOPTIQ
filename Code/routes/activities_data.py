# Code/routes/activities_data.py
from flask import jsonify
from .activities_bp import activities_bp
from Code.extensions import db
from Code.models.models import (
    Activities,
    Task,
    Role,
    Performance,
    Link,
    Data,
    Constraint,
    Competency,
    Softskill,
)
# Selon ton modèle, ces classes existent très probablement :
# Savoir, SavoirFaire, Aptitude
try:
    from Code.models.models import Savoir, SavoirFaire, Aptitude
except Exception:  # on reste tolérant si les noms diffèrent dans certains environnements
    Savoir = None
    SavoirFaire = None
    Aptitude = None


def _safe_list(iterable):
    return list(iterable) if iterable is not None else []


def _unique_sorted(seq):
    """Déduplique tout en préservant l'ordre d'apparition."""
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


@activities_bp.route('/<int:activity_id>/details', methods=['GET'])
def get_activity_details(activity_id):
    """
    Détail complet d'une activité, utilisé par les modales "Proposer ...",
    et par les rafraîchissements front (savoirs / savoir-faire / softskills / aptitudes).
    """
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "Activité non trouvée"}), 404

    # -----------------------------
    # Tâches (liste simple)
    # -----------------------------
    tasks_list = [t.name for t in _safe_list(getattr(activity, "tasks", []))]

    # -----------------------------
    # Outils (agrégés depuis les tâches, dédupliqués)
    # -----------------------------
    tools_collected = []
    for t in _safe_list(getattr(activity, "tasks", [])):
        for tl in _safe_list(getattr(t, "tools", [])):
            name = getattr(tl, "name", None)
            if name:
                tools_collected.append(name)
    tools_list = _unique_sorted(tools_collected)

    # -----------------------------
    # Contraintes (objets dict {"description": ...})
    # -----------------------------
    constraints_list = [
        {"description": getattr(c, "description", "")}
        for c in _safe_list(getattr(activity, "constraints", []))
    ]

    # -----------------------------
    # Compétences existantes (si tu les affiches quelque part)
    # -----------------------------
    competencies_list = [
        {"description": getattr(comp, "description", "")}
        for comp in _safe_list(getattr(activity, "competencies", []))
    ]

    # -----------------------------
    # Données d'entrée / sortie.
    # Il n'existe pas de relation "data_items"/"data" ni de colonne "direction" sur
    # Activities/Data : ces attributs n'ont jamais existé dans le modèle, si bien que
    # ces deux listes étaient TOUJOURS vides, quoi qu'il y ait en base. La sortie d'une
    # activité est une Data ancrée via `producer_activity_id` (cf. qualify_outputs.py) ;
    # son entrée est une Data qui l'alimente via un Link "nourrissante".
    # -----------------------------
    output_data = [
        (d.name or "").strip()
        for d in Data.query.filter_by(producer_activity_id=activity.id).all()
        if (d.name or "").strip()
    ]

    input_data = []
    for link in Link.query.filter_by(target_activity_id=activity.id).all():
        if not link.source_data_id:
            continue
        source_data = db.session.get(Data, link.source_data_id)
        if source_data is None:
            continue
        text = (source_data.name or "").strip() or (source_data.description or "").strip()
        if text:
            input_data.append(text)
    input_data = _unique_sorted(input_data)

    # -----------------------------
    # Performances "sortantes" via liens (source_activity_id → performance)
    # -----------------------------
    outgoing = []
    for link in Link.query.filter_by(source_activity_id=activity.id).all():
        perf_obj = getattr(link, "performance", None)
        if perf_obj:
            outgoing.append(
                {
                    "performance": {
                        "id": getattr(perf_obj, "id", None),
                        "name": getattr(perf_obj, "name", ""),
                        "description": getattr(perf_obj, "description", ""),
                    }
                }
            )
        else:
            outgoing.append({"performance": None})

    # -----------------------------
    # Listes éditables (CRUD) utilisées par le front :
    # - savoirs
    # - savoir_faires
    # - softskills
    # - aptitudes
    # -----------------------------
    # Tri stable par id ASC pour éviter qu'un item modifié "descende" visuellement.
    def _collect_query(model_cls, label_field="description"):
        if model_cls is None:
            return []
        q = model_cls.query.filter_by(activity_id=activity.id)
        # order_by id ASC si colonne "id" existe
        try:
            q = q.order_by(model_cls.id.asc())
        except Exception:
            pass
        items = []
        for obj in q.all():
            items.append(
                {
                    "id": getattr(obj, "id", None),
                    "name": getattr(obj, "name", None),
                    "description": getattr(obj, label_field, "")
                    or getattr(obj, "name", "")
                    or "",
                }
            )
        return items

    savoirs = _collect_query(Savoir, "description")
    savoir_faires = _collect_query(SavoirFaire, "description")

    # Softskill: ton modèle peut avoir "name" ou "description"
    softskills_items = []
    try:
        qss = Softskill.query.filter_by(activity_id=activity.id).order_by(Softskill.id.asc())
        for ss in qss.all():
            softskills_items.append(
                {
                    "id": getattr(ss, "id", None),
                    "name": getattr(ss, "name", None) or getattr(ss, "description", ""),
                    "description": getattr(ss, "description", "") or getattr(ss, "name", ""),
                }
            )
    except Exception:
        # si pas de modèle Softskill ou colonnes différentes
        softskills_items = []

    aptitudes = _collect_query(Aptitude, "description")

    # -----------------------------
    # Rendu JSON
    # -----------------------------
    activity_data = {
        "id": activity.id,
        # on sert les deux clés pour compat : certains JS lisent "name", d'autres "title"
        "name": getattr(activity, "name", ""),
        "title": getattr(activity, "name", ""),
        "description": getattr(activity, "description", "") or "",
        "tasks": tasks_list,
        "tools": tools_list,
        "constraints": constraints_list,
        "competencies": competencies_list,
        "outgoing": outgoing,
        # listes (pas de strings)
        "input_data": input_data,
        "output_data": output_data,
        # blocs éditables consommés par le front
        "savoirs": savoirs,
        "savoir_faires": savoir_faires,
        "softskills": softskills_items,
        "aptitudes": aptitudes,
    }
    return jsonify(activity_data), 200
