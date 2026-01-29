# Code/routes/translate_softskills.py
import os
import json
import re
from flask import Blueprint, request, jsonify, current_app

translate_softskills_bp = Blueprint('translate_softskills_bp', __name__, url_prefix='/translate_softskills')

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

PROMPT_TRANSLATE_HSC = """
Tu es un expert des habiletés socio-cognitives (HSC) selon la norme X50-766, et tu appliques une logique OPTIQ.
Objectif : traduire les soft skills en langage naturel de l'utilisateur en une COMBINAIRE de 4 à 6 HSC, cohérente avec la tenue réelle de l'activité (résultats, tâches, contraintes, performances). Ce n'est PAS un mapping 1 soft skill -> 1 HSC.

Soft skills saisies par l'utilisateur : "{user_input}"

Activité : {activity_name}

Tâches (T1..Tn) :
{tasks_text}

Contraintes (C1..Cn) :
{constraints_text}

Performances attendues (P1..Pn) :
{perf_text}

Liste COMPLETE des HSC X50-766 (n'utilise QUE ces termes, strictement) :
{x50_766_hsc}

Niveaux possibles (n'utilise QUE ces libellés) :
1 (Aptitude)
2 (Acquisition)
3 (Maîtrise)
4 (Excellence)

RÈGLES DE RAISONNEMENT (obligatoire) :

1) IDENTIFIER 1 à 3 RESULTATS MAJEURS de l'activité (R1..Rk) à partir des tâches et/ou performances.
   - L'activité peut avoir plusieurs résultats : ta combinatoire de HSC doit couvrir l'ensemble des résultats R1..Rk.

2) TRADUCTION PAR COMBINAIRE (pas de mot-à-mot) :
   - Analyse l'ensemble des soft skills dans "{user_input}" comme une intention globale.
   - Sélectionne 4 à 6 HSC qui, ensemble, expliquent comment satisfaire cette intention dans cette activité.
   - Une HSC peut couvrir plusieurs soft skills, et une soft skill peut nécessiter plusieurs HSC.

2bis) PRIORITÉ À LA TENUE DE L'ACTIVITÉ :
   - Ta sélection d'HSC doit d'abord couvrir les exigences de l'activité (R/T/C/P), même si "{user_input}" est incomplet ou imprécis.
   - Si une HSC est indispensable pour R/T/C/P mais n'est pas exprimée dans "{user_input}", tu dois quand même la retenir.
   - Inversement, si une soft skill exprimée est hors-sujet, tu la rattaches au plus proche en niveau minimal, mais elle ne doit pas remplacer une HSC indispensable.

3) RÈGLE ANTI-ÉVIDENCE / ANTI-GÉNÉRIQUE :
   - N'ajoute pas une HSC "par réflexe".
   - Exclure "Planification" sauf si les T/C/P montrent une complexité réelle de plan (jalons, dépendances critiques, replanification, ressources limitées, multi-acteurs, aléas).
   - Chaque HSC retenue doit être justifiée par un lien concret à R(i), T(i), C(i) ou P(i).

4) SOFT SKILL PEU UTILE :
   - Si une soft skill de "{user_input}" est peu utile pour cette activité :
       * tu la rattaches à la HSC la plus proche,
       * mais tu mets "niveau" à "1 (Aptitude)" et la "sollicitation" plutôt à "NA" ou "1".

5) COUVERTURE / NON-REDONDANCE :
   - 4 à 6 HSC MAX.
   - Évite les doublons : chaque HSC doit apporter une contribution différente à la réussite.

6) TEST FINAL DE COUVERTURE :
   - Avant de répondre, vérifie que chaque résultat majeur R(i) est couvert par au moins une HSC avec "Sollicitation: 2".
   - Si ce n'est pas le cas, ajuste la sélection (sans dépasser 6 HSC).

FORMAT DE SORTIE (obligatoire) :
- Réponds UNIQUEMENT avec un tableau JSON brut (aucun texte hors JSON, pas de backticks).
- 4 à 6 entrées. Chaque entrée = {{
    "habilete": <str parmi la liste X50-766>,
    "niveau": "X (Label)",
    "justification": "Sollicitation: <NA|1|2>. D'abord: 1 à 2 phrases expliquant en quoi cette HSC permet de tenir l'activité (références T/C/P, et résultats si nécessaire). Ensuite: 1 phrase qui termine par 'Cela constitue une composante des soft skills \\"{{user_input}}\\"...' en citant les fragments pertinents, ET en indiquant les HSC complémentaires utiles (même si elles ne sont pas retenues dans les 4-6)."
}}

Contraintes rédactionnelles :
- La justification doit mentionner explicitement "{user_input}".
- La justification doit référencer au moins un élément parmi T(i), C(i) ou P(i).
- Ne sors pas de champs supplémentaires : uniquement habilete, niveau, justification.

RÉPONDS UNIQUEMENT AVEC LE TABLEAU JSON.
"""


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, "Clé OpenAI manquante (OPENAI_API_KEY)."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        return client, None
    except Exception as e:
        return None, str(e)


def clean_json_response(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text


def make_enumeration(prefix, items):
    lines = []
    for i, it in enumerate(items, start=1):
        if isinstance(it, dict):
            desc = it.get("description", str(it))
            lines.append(f"{prefix}{i}: {desc}")
        else:
            lines.append(f"{prefix}{i}: {it}")
    return "\n".join(lines) if lines else f"(Aucune {prefix.strip()})"


@translate_softskills_bp.route('/translate', methods=['POST'])
def translate_softskills():
    data = request.get_json() or {}
    user_input = data.get("user_input", "").strip()
    activity_data = data.get("activity_data", {})

    if not user_input:
        return jsonify({"error": "Aucun texte saisi pour la traduction."}), 400

    activity_name = activity_data.get("name", "Activité sans nom")
    tasks_list = activity_data.get("tasks", [])
    constraints_list = activity_data.get("constraints", [])
    outgoing_list = activity_data.get("outgoing", [])

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
    perf_text = "\n".join(perf_lines) if perf_lines else "(Aucune performance)"

    prompt = PROMPT_TRANSLATE_HSC.format(
        user_input=user_input,
        activity_name=activity_name,
        tasks_text=tasks_text,
        constraints_text=constraints_text,
        perf_text=perf_text,
        x50_766_hsc=X50_766_HSC,
    )

    client, err = get_openai_client()
    if client is None:
        return jsonify({"error": err}), 500

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Tu es un assistant spécialisé en habiletés socio-cognitives X50-766. Tu réponds UNIQUEMENT en JSON valide, sans markdown ni texte supplémentaire."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1200
        )
        ai_text = response.choices[0].message.content.strip()
        cleaned_text = clean_json_response(ai_text)

        try:
            proposals = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            current_app.logger.error(f"JSON parse error: {e}. Raw text: {ai_text[:500]}")
            return jsonify({"error": f"Erreur de parsing JSON: {str(e)}"}), 400

        if not isinstance(proposals, list):
            if isinstance(proposals, dict):
                proposals = [proposals]
            else:
                return jsonify({"error": "Le JSON renvoyé n'est pas un tableau d'objets."}), 400

        niveau_map = {
            "1": "1 (Aptitude)",
            "2": "2 (Acquisition)",
            "3": "3 (Maîtrise)",
            "4": "4 (Excellence)"
        }

        for p in proposals:
            niveau = p.get("niveau", "2")
            if isinstance(niveau, int) or (isinstance(niveau, str) and niveau.isdigit()):
                p["niveau"] = niveau_map.get(str(niveau), "2 (Acquisition)")

        return jsonify({"proposals": proposals}), 200

    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"error": str(e)}), 500
