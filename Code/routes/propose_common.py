# Code/routes/propose_common.py
import os
from flask import current_app
from Code.ai_key import get_openai_key

def build_activity_context(activity_json: dict, lang: str = "fr") -> str:
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

    # ⚠️ Les en-têtes suivent la langue. Un bloc de contexte en français sous un
    # prompt anglais est le signal mixte qui fait repasser le modèle au
    # français : c'est le texte le plus LONG du message, il pèse plus que la
    # consigne qui l'accompagne.
    if lang == "en":
        return f"""# Activity
Title: {title}
Description: {description}

# Input data
{norm_list(inputs)}

# Output data
{norm_list(outputs)}

# Tools
{norm_list(tools)}

# Constraints
{norm_list(constraints)}

# Tasks
{norm_list(tasks)}
"""
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
    Client IA unifié (Claude via point d'accès compatible OpenAI, ou OpenAI —
    voir Code/ai_client.py). Signature conservée : (client, raison_ou_None).
    Le modèle à utiliser avec ce client est donné par ai_model().
    """
    from Code.ai_client import make_ai_client
    client, _model, err = make_ai_client()
    if err:
        return None, err
    return client, None


def ai_model():
    """Modèle IA effectif — remplace les model="gpt-4o-mini" en dur."""
    from Code.ai_client import ai_model as _ai_model
    return _ai_model()


def dummy_from_context(ctx: str, kind: str = "savoir", lang: str = "fr"):
    """
    Fallback déterministe : on fabrique 3 items à partir du contexte.
    Ça évite de faire planter le front en prod.

    ⚠️ Il suit la LANGUE : c'est ce que voit un compte anglais sur une instance
    sans clé IA — donc le cas le plus courant chez un client qui n'en a pas.
    """
    base = ctx.splitlines()
    titre = ""
    for line in base:
        if line.startswith("Titre:") or line.startswith("Title:"):
            titre = line.split(":", 1)[1].strip()
            break

    if lang == "en":
        prefix = {"savoir_faire": "Apply", "hsc": "Develop"}.get(kind, "Know")
        # ⚠️ Pas de « » ici : ce sont les guillemets du FRANÇAIS.
        part = f' of activity "{titre}"' if titre else ""
        return [
            f"{prefix} the main procedures{part}",
            f"{prefix} the related tools and data{part}",
            f"{prefix} the constraints and business rules{part}",
        ]

    prefix = {"savoir_faire": "Appliquer", "hsc": "Développer"}.get(kind, "Connaître")
    titre_part = f" de l'activité « {titre} »" if titre else ""
    return [
        f"{prefix} les procédures principales{titre_part}",
        f"{prefix} les outils ou données associés{titre_part}",
        f"{prefix} les contraintes / règles métier{titre_part}",
    ]
