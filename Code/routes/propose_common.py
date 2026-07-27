# Code/routes/propose_common.py
import os
from flask import current_app
from Code.ai_key import get_openai_key

def build_activity_context(activity_json: dict) -> str:
    title = activity_json.get("title") or activity_json.get("name") or ""
    description = activity_json.get("description") or ""
    inputs = activity_json.get("input_data") or []
    outputs = activity_json.get("output_data") or []
    tools = activity_json.get("tools") or activity_json.get("outils") or []
    constraints = activity_json.get("constraints") or []
    tasks = activity_json.get("tasks") or []

    def norm_list(lst):
        if not lst:
            return "-"
        return "\n".join(f"- {str(x)}" for x in lst)

    return f"""# Activité
Titre: {title}
Description: {description}

# Données d'entrée
{norm_list(inputs)}

# Données de sortie
{norm_list(outputs)}

# Outils
{norm_list(tools)}

# Contraintes
{norm_list(constraints)}

# Tâches
{norm_list(tasks)}
"""


def openai_client_or_none():
    """
    Essaie d'instancier le client OpenAI.
    Si la clé n'est pas là → on renvoie (None, "raison").
    """
    key = get_openai_key()
    if not key:
        return None, "Clé IA non renseignée."
    try:
        from openai import OpenAI
        return OpenAI(api_key=key), None
    except Exception as e:
        current_app.logger.exception(e)
        return None, str(e)


def dummy_from_context(ctx: str, kind: str = "savoir"):
    """
    Fallback déterministe : on fabrique 3 items à partir du contexte.
    Ça évite de faire planter le front en prod.
    """
    base = ctx.splitlines()
    titre = ""
    for line in base:
        if line.startswith("Titre:"):
            titre = line.replace("Titre:", "").strip()
            break

    if kind == "savoir_faire":
        prefix = "Appliquer"
    elif kind == "hsc":
        prefix = "Développer"
    else:
        prefix = "Connaître"

    titre_part = f" de l'activité « {titre} »" if titre else ""
    return [
        f"{prefix} les procédures principales{titre_part}",
        f"{prefix} les outils ou données associés{titre_part}",
        f"{prefix} les contraintes / règles métier{titre_part}",
    ]
