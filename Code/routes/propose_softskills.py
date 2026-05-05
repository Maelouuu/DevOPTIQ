# Code/routes/propose_softskills.py
import json
import re
from flask import Blueprint, request, jsonify, current_app
from .propose_common import (
    openai_client_or_none,
    dummy_from_context,
)

bp_propose_softskills = Blueprint("propose_softskills", __name__)

X50_766_HSC = """
Liste officielle X50-766 :
- Auto-évaluation
- Auto-régulation
- Auto-organisation
- Auto-mobilisation
- Sensibilité sociale
- Adaptation relationnelle
- Coopération
- Raisonnement logique
- Planification
- Arbitrage
- Traitement de l'information
- Synthèse
- Conceptualisation
- Flexibilité mentale
- Projection
- Approche globale
"""

PROMPT_HEADER_HSC = """
Tu es un expert en analyse du travail, en sciences cognitives et en ingénierie des compétences.
Tu appliques une logique OPTIQ : les HSC retenues doivent expliquer la tenue réelle de l'activité au regard des RESULTATS attendus, des tâches, des contraintes et des performances (pas de généralités).

🎯 Objectif : Proposer directement (sans soft skills utilisateur) une COMBINAIRE de 4 à 6 HSC essentielles pour l'activité fournie.
- 4 à 6 HSC : centrées sur l'essentiel, robustes au contexte, sans catalogue.
- Une activité peut produire plusieurs résultats : ta combinatoire doit couvrir l'ensemble.

Activité : {activity_name}

Valeur(s) ajoutée(s) / Résultat(s) attendu(s) / Performances :
{perf_text}

Tâches (T1..Tn) :
{tasks_text}

Contraintes (C1..Cn) :
{constraints_text}

Liste COMPLETE des HSC X50-766 (n'utilise QUE ces termes, strictement) :
{x50_766_hsc}

Niveaux possibles (n'utilise QUE ces libellés) :
1 (Aptitude)
2 (Acquisition)
3 (Maîtrise)
4 (Excellence)

RÈGLES DE RAISONNEMENT (obligatoire) :

1) IDENTIFIER 1 à 3 RESULTATS MAJEURS de l'activité (R1..Rk) à partir des performances et/ou des tâches.
   - L'activité peut avoir plusieurs résultats : ta combinatoire de HSC doit couvrir l'ensemble des résultats R1..Rk.

2) SÉLECTION PAR ESSENTIEL :
   - Ne retiens une HSC QUE si elle est nécessaire pour :
     a) produire un résultat R(i), OU
     b) respecter une contrainte C(i), OU
     c) atteindre une performance P(i).
   - Chaque HSC doit apporter une contribution différente (éviter doublons de sens).

3) RÈGLE ANTI-ÉVIDENCE / ANTI-GÉNÉRIQUE :
   - N'ajoute pas une HSC "par réflexe".
   - Exclure "Planification" sauf si les T/C/P montrent une complexité réelle de plan (jalons, dépendances critiques, replanification, ressources limitées, multi-acteurs, aléas).
   - Si l'enchaînement des tâches est simplement "normal", ne pas citer Planification.

4) NIVEAU (1 à 4) :
   - Le niveau attendu dépend du degré de variabilité, d'incertitude, d'enjeux QCD, de multi-acteurs et de formalisation exigée par T/C/P.
   - N'attribue pas 4 (Excellence) sans justification forte liée à T/C/P.

5) TEST FINAL DE COUVERTURE :
   - Avant de répondre, vérifie que chaque résultat majeur R(i) est couvert par au moins une HSC.
   - Si ce n'est pas le cas, ajuste la sélection (sans dépasser 6 HSC).

FORMAT DE SORTIE (obligatoire) :
- Réponds UNIQUEMENT avec un tableau JSON brut (aucun texte hors JSON, pas de backticks).
- 4 à 6 entrées. Chaque entrée = {{
    "habilete": <str parmi la liste X50-766>,
    "niveau": "X (Label)",
    "justification": "Sollicitation: <NA|1|2>. 2 à 3 phrases maximum expliquant en quoi cette HSC permet de tenir l'activité (références à R(i), T(i), C(i), P(i) si pertinent)."
}}

Contraintes rédactionnelles :
- La justification doit référencer au moins un élément parmi T(i), C(i) ou P(i) (et plusieurs si pertinent).
- Ne sors pas de champs supplémentaires : uniquement habilete, niveau, justification.
- RÉPONDS UNIQUEMENT AVEC LE TABLEAU JSON.
"""

# --------------------------------------------------------------------
# OUTILS : extraction JSON propre
# --------------------------------------------------------------------
def clean_json_response(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())

    start_bracket = text.find('[')
    start_brace = text.find('{')

    if start_bracket == -1 and start_brace == -1:
        return text

    if start_bracket == -1:
        start = start_brace
    elif start_brace == -1:
        start = start_bracket
    else:
        start = min(start_bracket, start_brace)

    if text[start] == '[':
        end = text.rfind(']')
    else:
        end = text.rfind('}')

    if end == -1 or end < start:
        return text

    return text[start:end+1]


def make_enumeration(prefix, items):
    lines = []
    for i, it in enumerate(items, start=1):
        if isinstance(it, dict):
            desc = it.get("description", str(it))
            lines.append(f"{prefix}{i}: {desc}")
        else:
            lines.append(f"{prefix}{i}: {it}")
    return "\n".join(lines) if lines else f"(Aucune {prefix.strip()})"


# --------------------------------------------------------------------
# ROUTE PRINCIPALE
# --------------------------------------------------------------------
@bp_propose_softskills.route("/propose_softskills/propose", methods=["POST"])
def propose_softskills():
    try:
        activity = request.get_json(force=True) or {}

        client, err = openai_client_or_none()
        if client is None:
            proposals = [
                {
                    "habilete": item,
                    "niveau": "2 (Acquisition)",
                    "justification": "Proposition générée sans IA (clé OpenAI absente).",
                }
                for item in dummy_from_context("", "hsc")
            ]
            return jsonify({"proposals": proposals, "source": err}), 200

        activity_name = activity.get("name") or activity.get("title") or "Activité sans nom"

        tasks_list = activity.get("tasks") or []
        constraints_list = activity.get("constraints") or []
        outgoing_list = activity.get("outgoing") or []

        tasks_text = make_enumeration("T", tasks_list)
        constraints_text = make_enumeration("C", constraints_list)

        perf_lines = []
        perf_idx = 1
        for o in outgoing_list:
            if isinstance(o, dict):
                perf = o.get("performance")
                if perf:
                    name = perf.get("name", "")
                    desc = perf.get("description", "")
                    perf_lines.append(f"P{perf_idx}: {name} - {desc}")
                    perf_idx += 1
        perf_text = "\n".join(perf_lines) if perf_lines else "(Aucune performance renseignée)"

        prompt = PROMPT_HEADER_HSC.format(
            activity_name=activity_name,
            perf_text=perf_text,
            tasks_text=tasks_text,
            constraints_text=constraints_text,
            x50_766_hsc=X50_766_HSC,
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un assistant RH expert en habiletés sociocognitives X50-766. "
                        "Tu DOIS répondre uniquement en JSON valide. "
                        "Jamais de texte extérieur, jamais de markdown."
                    )
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
        )

        text = resp.choices[0].message.content.strip()
        cleaned_text = clean_json_response(text)

        proposals = []
        parsed_ok = False

        try:
            data = json.loads(cleaned_text)
            if isinstance(data, dict):
                data = [data]

            niveau_map = {
                "1": "1 (Aptitude)",
                "2": "2 (Acquisition)",
                "3": "3 (Maîtrise)",
                "4": "4 (Excellence)"
            }

            for item in data:
                raw_niveau = item.get("niveau", "2")
                if isinstance(raw_niveau, str):
                    num = re.findall(r"\d", raw_niveau)
                    raw_niveau = num[0] if num else "2"
                elif isinstance(raw_niveau, int):
                    raw_niveau = str(raw_niveau)

                level = niveau_map.get(raw_niveau, "2 (Acquisition)")

                proposals.append({
                    "habilete": item.get("habilete", "Habileté"),
                    "niveau": level,
                    "justification": item.get("justification", ""),
                })

            parsed_ok = True

        except Exception as e:
            current_app.logger.warning(f"[HSC JSON FAIL] {e} | TEXT={cleaned_text[:200]}")

        if not parsed_ok or not proposals:
            lines = [
                l.strip("-•* ").strip()
                for l in text.splitlines()
                if l.strip() and not l.strip().startswith("```")
            ]
            for line in lines:
                if len(line) > 3:
                    proposals.append({
                        "habilete": line[:100],
                        "niveau": "2 (Acquisition)",
                        "justification": "",
                    })

        if not proposals:
            proposals = [
                {
                    "habilete": "Communication professionnelle",
                    "niveau": "2 (Acquisition)",
                    "justification": "Habileté de base requise pour l'activité.",
                }
            ]

        return jsonify({"proposals": proposals}), 200

    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({
            "proposals": [
                {
                    "habilete": "Habileté non déterminée (erreur serveur).",
                    "niveau": "2 (Acquisition)",
                    "justification": "",
                }
            ],
            "error": str(e),
        }), 200
