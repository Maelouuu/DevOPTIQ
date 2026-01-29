from flask import Blueprint, request, jsonify, current_app
import json
import re
from .propose_common import openai_client_or_none

bp_propose_aptitudes = Blueprint("propose_aptitudes", __name__)

PROMPT_INCLUSION_SCORING = """
Tu es expert en analyse du travail, prevention sante/securite et inclusion (amenagement raisonnable).
Important : ne traite PAS les HSC (cognitif/competences fines). Ici : accessibilite, prevention, conditions de travail.

Activite : {activity_name}
Resume activite (outils, delais, conformite, environnement) :
{activity_summary}

Contexte optionnel (si renseigne ; sinon ignorer sans penaliser) :
- Competences attendues : {competences_text}
- Savoirs attendus : {savoirs_text}
- Savoir-faire attendus : {savoir_faire_text}
- HSC essentielles (deja calculees) : {hsc_context}

ECHELLE DE COTATION (utilise exactement ces libelles) :
0 (Aucune) | 1 (Faible) | 2 (Moderee) | 3 (Elevee)

CATEGORIES (uniquement celles-ci) :
1) Vision
2) Physique (haut du corps / bas du corps / fatigabilite)
3) Environnemental (bruit/interruptions + modalites oral/ecrit + exigences de qualite de communication si explicites)
4) Exposition / Risque (accident, machines, hauteur, engins, chimique, exterieur, isolement)

REGLES :
A) Concision : chaque categorie = 1 risque court + 1 a 2 leviers (specifiques).
B) Leviers = adaptations inclusion : integrer, quand pertinent, des adaptations possibles (poste, logiciel, modalites, outils d'assistance).
   - Vision : inclure au moins 1 levier de type "accessibilite numerique" si outil/logiciel est central (zoom/contraste, navigation clavier, lecteur d'ecran, conformite accessibilite type WCAG/EN 301 549 si applicable).
C) Anti-generique : pas "ergonomie standard" (chaise/posture) sauf si le resume indique saisie intensive / longues plages / pic sous delai.
D) Performance/delai : ne l'utiliser comme facteur de risque QUE si c'est manifestement contraignant ou a tolerance zero.
   Exemples de signaux "evidents" : delai tres court/urgent, penalites, "0 erreur", "zero defaut", securite critique, audit, conformite bloquante.
   Sinon, ignorer le delai comme facteur de risque.
E) Exposition/Risque :
   - Si aucune exposition explicite dans le resume : niveau 0 + 1 seul levier conditionnel max (pas plus).
F) Profils valorisables : 2 max, toujours formules prudemment et conditionnes par "si exigences metier acquises".

FORMAT DE SORTIE :
Reponds UNIQUEMENT en JSON brut (pas de texte hors JSON, pas de backticks) :

{{
  "vision": {{
    "niveau": "X (Libelle)",
    "risque": "<7-12 mots>",
    "leviers": ["<adaptation inclusive 7-12 mots>", "<optionnel>"]
  }},
  "physique": {{
    "haut_du_corps": "X (Libelle)",
    "bas_du_corps": "X (Libelle)",
    "fatigabilite": "X (Libelle)",
    "risque": "<7-12 mots>",
    "leviers": ["<adaptation inclusive 7-12 mots>", "<optionnel>"]
  }},
  "environnemental": {{
    "niveau": "X (Libelle)",
    "risque": "<7-12 mots>",
    "leviers": ["<adaptation inclusive 7-12 mots>", "<optionnel>"]
  }},
  "exposition_risque": {{
    "niveau": "X (Libelle)",
    "risque": "<7-12 mots>",
    "leviers": ["<0 ou 1 levier si niveau 0 ; sinon 1-2>"]
  }},
  "profils_valorisables": [
    {{
      "profil": "<profil/handicap generique>",
      "atout_possible": "<7-14 mots>",
      "condition": "Si exigences metier acquises : <cadre necessaire, 7-14 mots>"
    }}
  ]
}}
"""

PROMPT_HANDICAP_FEASIBILITY_ICF = """
Tu es expert prevention et inclusion. Tu n'etablis aucun diagnostic medical.
Objectif : evaluer la faisabilite d'adaptation d'une personne (limitations fonctionnelles) a une activite, en tenant compte des aides/compensations deja en place.

Reference : description fonctionnelle inspiree ICF/CIF (OMS).

Activite : {activity_name}
Analyse exigences (JSON) :
{inclusion_scoring_json}

Profil fonctionnel (si une dimension est inconnue, mettre "inconnu") :
- Vision : {vision}
- Audition/communication : {audition}
- Motricite fine (mains) : {motricite_fine}
- Mobilite/posture : {mobilite_posture}
- Endurance/fatigabilite : {endurance}
- Sensibilite environnementale (bruit/lumiere/interruptions) : {sensibilite_env}
- Commentaire court (facultatif, sans detail medical) : {commentaire_court}

Aides / compensations deja en place (liste + eventuel "Autres") :
{assistive_products_text}

REGLES :
1) Statut : "OK", "OK avec adaptations", "A instruire", ou "Non recommande sans changement majeur".
2) Tu dois distinguer :
   - "mesures_deja_en_place" : ce qui est deja present et pertinent (a conserver),
   - "ajouts_recommandes" : ce qui manque (2 a 4 max),
   - "a_ajuster" : ce qui est en place mais insuffisant/mal aligne (0 a 2 max).
3) Ne repropose pas comme "ajout" une mesure deja listee dans les aides/compensations : au contraire, place-la dans "mesures_deja_en_place" ou "a_ajuster".
4) Tes ajouts doivent etre alignes sur Vision/Physique/Environnemental/Exposition du JSON d'exigences.
5) Si incertitude ou exposition/securite non triviale : "A instruire" + points a clarifier + recommander validation ergonomie/sante au travail (ou equivalent selon pays).

FORMAT (JSON brut uniquement) :
{{
  "statut": "OK|OK avec adaptations|A instruire|Non recommande sans changement majeur",
  "mesures_deja_en_place": ["...", "..."],
  "ajouts_recommandes": ["...", "...", "..."],
  "a_ajuster": ["...", "..."],
  "risque_residuel": "<1 phrase>",
  "points_a_instruire": ["...", "..."],
  "commentaire": "<1-2 phrases prudentes>"
}}
"""


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


def build_activity_summary(activity):
    parts = []
    desc = activity.get("description", "")
    if desc:
        parts.append(desc)

    tools = activity.get("tools") or activity.get("outils") or []
    if tools:
        tool_strs = [str(t) for t in tools]
        parts.append(f"Outils : {', '.join(tool_strs)}")

    constraints = activity.get("constraints") or []
    if constraints:
        c_strs = [str(c) for c in constraints]
        parts.append(f"Contraintes : {', '.join(c_strs)}")

    tasks = activity.get("tasks") or []
    if tasks:
        for i, t in enumerate(tasks, 1):
            if isinstance(t, dict):
                parts.append(f"T{i}: {t.get('description', str(t))}")
            else:
                parts.append(f"T{i}: {t}")

    outgoing = activity.get("outgoing") or []
    for o in outgoing:
        perf = o.get("performance")
        if perf:
            parts.append(f"Performance : {perf.get('name', '')} - {perf.get('description', '')}")

    return "\n".join(parts) if parts else "Non renseigné"


@bp_propose_aptitudes.route("/propose_aptitudes/propose", methods=["POST"])
def propose_aptitudes():
    try:
        activity = request.get_json(force=True) or {}
        client, err = openai_client_or_none()
        if client is None:
            return jsonify({"proposals": {}, "source": err}), 200

        activity_name = activity.get("name") or activity.get("title") or "Activité sans nom"
        activity_summary = build_activity_summary(activity)
        competences_text = activity.get("competences_text") or "Non renseigné"
        savoirs_text = activity.get("savoirs_text") or "Non renseigné"
        savoir_faire_text = activity.get("savoir_faire_text") or "Non renseigné"
        hsc_context = activity.get("hsc_context") or "Non renseigné"

        prompt = PROMPT_INCLUSION_SCORING.format(
            activity_name=activity_name,
            activity_summary=activity_summary,
            competences_text=competences_text,
            savoirs_text=savoirs_text,
            savoir_faire_text=savoir_faire_text,
            hsc_context=hsc_context,
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Tu es un expert en analyse du travail, prevention sante/securite et inclusion. Tu reponds UNIQUEMENT en JSON valide, sans markdown ni texte supplementaire."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message.content.strip()
        cleaned = clean_json_response(text)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as e:
            current_app.logger.warning(f"[INCLUSION SCORING JSON FAIL] {e} | TEXT={cleaned[:300]}")
            return jsonify({"proposals": {}, "error": f"Erreur parsing JSON: {str(e)}"}), 200

        return jsonify({"proposals": result}), 200

    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"proposals": {}, "error": str(e)}), 200


@bp_propose_aptitudes.route("/propose_aptitudes/feasibility", methods=["POST"])
def propose_feasibility():
    try:
        data = request.get_json(force=True) or {}
        client, err = openai_client_or_none()
        if client is None:
            return jsonify({"result": {}, "source": err}), 200

        activity_name = data.get("activity_name") or "Activité sans nom"
        inclusion_scoring_json = data.get("inclusion_scoring_json") or "{}"
        if isinstance(inclusion_scoring_json, dict):
            inclusion_scoring_json = json.dumps(inclusion_scoring_json, ensure_ascii=False, indent=2)

        profil = data.get("profil_fonctionnel") or {}
        vision = profil.get("vision", "inconnu")
        audition = profil.get("audition", "inconnu")
        motricite_fine = profil.get("motricite_fine", "inconnu")
        mobilite_posture = profil.get("mobilite_posture", "inconnu")
        endurance = profil.get("endurance", "inconnu")
        sensibilite_env = profil.get("sensibilite_env", "inconnu")
        commentaire_court = data.get("commentaire_court") or ""

        assistive_products = data.get("assistive_products") or []
        if isinstance(assistive_products, list):
            assistive_products_text = "\n".join(f"- {p}" for p in assistive_products) if assistive_products else "Aucune aide renseignée"
        else:
            assistive_products_text = str(assistive_products)

        prompt = PROMPT_HANDICAP_FEASIBILITY_ICF.format(
            activity_name=activity_name,
            inclusion_scoring_json=inclusion_scoring_json,
            vision=vision,
            audition=audition,
            motricite_fine=motricite_fine,
            mobilite_posture=mobilite_posture,
            endurance=endurance,
            sensibilite_env=sensibilite_env,
            commentaire_court=commentaire_court,
            assistive_products_text=assistive_products_text,
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Tu es un expert prevention et inclusion. Tu reponds UNIQUEMENT en JSON valide, sans markdown ni texte supplementaire."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message.content.strip()
        cleaned = clean_json_response(text)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as e:
            current_app.logger.warning(f"[FEASIBILITY JSON FAIL] {e} | TEXT={cleaned[:300]}")
            return jsonify({"result": {}, "error": f"Erreur parsing JSON: {str(e)}"}), 200

        return jsonify({"result": result}), 200

    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"result": {}, "error": str(e)}), 200
