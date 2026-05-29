#!/usr/bin/env python3
"""Generate a PDF document listing all AI prompts used in DevOPTIQ."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

W, H = A4

PINK   = colors.HexColor("#ec4899")
DARK   = colors.HexColor("#1e1e2e")
GRAY   = colors.HexColor("#6b7280")
LGRAY  = colors.HexColor("#f3f4f6")
WHITE  = colors.white

def make_styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle("cover_title", fontName="Helvetica-Bold",
            fontSize=28, textColor=PINK, alignment=TA_CENTER, spaceAfter=6),
        "cover_sub": ParagraphStyle("cover_sub", fontName="Helvetica",
            fontSize=14, textColor=GRAY, alignment=TA_CENTER, spaceAfter=4),
        "cover_date": ParagraphStyle("cover_date", fontName="Helvetica",
            fontSize=11, textColor=GRAY, alignment=TA_CENTER, spaceAfter=2),
        "section_title": ParagraphStyle("section_title", fontName="Helvetica-Bold",
            fontSize=16, textColor=PINK, spaceBefore=18, spaceAfter=4),
        "card_title": ParagraphStyle("card_title", fontName="Helvetica-Bold",
            fontSize=13, textColor=DARK, spaceBefore=10, spaceAfter=2),
        "desc": ParagraphStyle("desc", fontName="Helvetica-Oblique",
            fontSize=10, textColor=GRAY, spaceAfter=8, leading=14),
        "label": ParagraphStyle("label", fontName="Helvetica-Bold",
            fontSize=9, textColor=PINK, spaceAfter=2, spaceBefore=6),
        "mono": ParagraphStyle("mono", fontName="Courier",
            fontSize=8, textColor=DARK, spaceAfter=4, leading=12,
            backColor=LGRAY, borderPad=6),
        "toc": ParagraphStyle("toc", fontName="Helvetica",
            fontSize=10, textColor=DARK, spaceAfter=3, leftIndent=12),
        "toc_num": ParagraphStyle("toc_num", fontName="Helvetica-Bold",
            fontSize=10, textColor=PINK, spaceAfter=3),
        "normal": base["Normal"],
    }


PROMPTS = [
    {
        "id": "01",
        "title": "Proposer Compétences",
        "page": "Page liste des activités (onglet Compétences)",
        "endpoint": "POST /skills/propose",
        "file": "Code/routes/skills.py",
        "desc": (
            "Génère exactement 3 propositions de compétences (norme NF X50-124) "
            "pour une activité. Chaque compétence commence par un verbe d'action "
            "et est contextualisée par les tâches, outils et connexions de l'activité."
        ),
        "system": "Vous êtes un assistant spécialisé en compétences NF X50-124. [+ instruction de langue]",
        "user": """\
Vous êtes un expert en gestion des compétences selon la norme NF X50-124.
Rédigez exactement 3 propositions de compétences,
chacune sur une nouvelle ligne distincte,
sans puce ni numérotation,
en commençant par un verbe d'action.
[+ instruction de langue]

Activité : {activity_name}
Entrées : {input_data}
Sorties : {output_data}
Tâches : {tasks}
Connexions sortantes : {outgoing}
Outils : {tools}""",
    },
    {
        "id": "02",
        "title": "Proposer Savoir-Faire",
        "page": "Page liste des activités (onglet Savoirs & SF)",
        "endpoint": "POST /propose_savoir_faires/propose",
        "file": "Code/routes/propose_savoir_faires.py",
        "desc": (
            "Propose 3 à 7 savoir-faire concrets et opérationnels pour une activité. "
            "Chaque item est formulé par un verbe d'action et précise l'objet "
            "sur lequel s'exerce le savoir-faire (outil, norme, procédure…). "
            "Cette étape est toujours appelée avant la proposition de Savoirs."
        ),
        "system": "Tu es un assistant RH/formation, précis et concis. [+ instruction de langue]",
        "user": """\
Analyse les informations d'activité ci-dessous et propose uniquement des SAVOIR-FAIRE
concrets et opérationnels, formulés par verbes d'action.

Règles :
- Chaque item commence par un verbe d'action (Utiliser, Maîtriser, Vérifier, Rédiger…)
- Précise toujours sur quoi ou avec quoi le savoir-faire s'exerce
- Les savoir-faire doivent être spécifiques et contextualisés, pas vagues ni génériques.
- Ne répète pas les tâches textuellement, déduis l'apprentissage concret nécessaire.
- Limite la réponse à 3 à 7 items maximum.
- Sortie attendue : liste à puces, une ligne par savoir-faire.

=== CONTEXTE ===
{context_activité}""",
    },
    {
        "id": "03",
        "title": "Proposer Savoirs",
        "page": "Page liste des activités (onglet Savoirs & SF)",
        "endpoint": "POST /propose_savoirs/propose",
        "file": "Code/routes/propose_savoirs.py",
        "desc": (
            "Propose 3 à 8 savoirs (connaissances théoriques) nécessaires pour tenir "
            "une activité. S'appuie sur le contexte de l'activité ET sur les savoir-faire "
            "déjà proposés à l'étape précédente. Priorité aux normes, référentiels et "
            "savoirs transverses (SST, RGPD, qualité…)."
        ),
        "system": "Tu es un assistant RH/formation, précis et concis. [+ instruction de langue]",
        "user": """\
Analyse les informations de l'activité ci-dessous ainsi que la liste des savoir-faire associés.
Propose uniquement des SAVOIRS (connaissances) nécessaires pour tenir l'activité.

Règles :
- Les savoirs sont des connaissances à acquérir (règles, normes, principes, bases techniques…).
  Ne les formule pas comme des verbes d'action.
- Distingue-toi des savoir-faire : connaissance sous-jacente, pas une action.
- Appuie-toi sur les éléments de l'activité ET sur les savoir-faire fournis.
- Complète par des savoirs TRANSVERSES (SST, RGPD, qualité/traçabilité, sécurité…).
- 3 à 8 items maximum.
- Sortie attendue : liste à puces, 1 ligne par savoir (formulation nominale).

=== CONTEXTE ACTIVITÉ ===
{context_activité}

=== SAVOIR-FAIRE ASSOCIÉS ===
{liste_savoir_faires}""",
    },
    {
        "id": "04",
        "title": "Proposer HSC (Habiletés Socio-Cognitives)",
        "page": "Page liste des activités (onglet HSC)",
        "endpoint": "POST /propose_softskills/propose",
        "file": "Code/routes/propose_softskills.py",
        "desc": (
            "Propose une combinatoire de 4 à 6 HSC essentielles (norme X50-766) "
            "pour une activité. Chaque HSC est sélectionnée par raisonnement en "
            "3 étapes : identification des résultats majeurs, sélection par essentiel, "
            "règle anti-générique. Retourne un tableau JSON avec habilete, niveau (1-4) "
            "et justification référencée aux tâches/contraintes/performances."
        ),
        "system": (
            "Tu es un assistant RH expert en habiletés sociocognitives X50-766. "
            "Tu DOIS répondre uniquement en JSON valide. "
            "Jamais de texte extérieur, jamais de markdown. [+ instruction de langue]"
        ),
        "user": """\
Tu es un expert en analyse du travail, en sciences cognitives et en ingénierie des compétences.
Tu appliques une logique OPTIQ : les HSC retenues doivent expliquer la tenue réelle de
l'activité au regard des RESULTATS attendus, des tâches, des contraintes et des performances.

Objectif : Proposer directement une COMBINAIRE de 4 à 6 HSC essentielles.

Activité : {activity_name}

Valeur(s) ajoutée(s) / Résultat(s) attendu(s) / Performances : {perf_text}
Tâches (T1..Tn) : {tasks_text}
Contraintes (C1..Cn) : {constraints_text}

Liste COMPLETE des HSC X50-766 (n'utilise QUE ces termes) :
Auto-évaluation, Auto-régulation, Auto-organisation, Auto-mobilisation,
Sensibilité sociale, Adaptation relationnelle, Coopération, Raisonnement logique,
Planification, Arbitrage, Traitement de l'information, Synthèse,
Conceptualisation, Flexibilité mentale, Projection, Approche globale

Niveaux : 1 (Aptitude) | 2 (Acquisition) | 3 (Maîtrise) | 4 (Excellence)

[Règles de raisonnement en 5 étapes + format JSON strict]
Format de sortie : tableau JSON — chaque entrée = { habilete, niveau, justification }""",
    },
    {
        "id": "05",
        "title": "Traduire Soft Skills → HSC",
        "page": "Page liste des activités (onglet HSC, bouton Traduire Soft Skills)",
        "endpoint": "POST /translate_softskills/translate",
        "file": "Code/routes/translate_softskills.py",
        "desc": (
            "Traduit un texte libre de soft skills saisi par l'utilisateur en une "
            "combinatoire de 4 à 6 HSC (X50-766), en tenant compte du contexte de "
            "l'activité. Ce n'est PAS un mapping 1-pour-1 : l'IA construit la "
            "combinatoire cohérente avec les tâches, contraintes et performances réelles."
        ),
        "system": (
            "Tu es un assistant spécialisé en habiletés socio-cognitives X50-766. "
            "Tu réponds UNIQUEMENT en JSON valide, sans markdown ni texte supplémentaire. "
            "[+ instruction de langue]"
        ),
        "user": """\
Tu es un expert des habiletés socio-cognitives (HSC) selon la norme X50-766.
Objectif : traduire les soft skills en langage naturel de l'utilisateur en
une COMBINAIRE de 4 à 6 HSC, cohérente avec la tenue réelle de l'activité.
Ce n'est PAS un mapping 1 soft skill -> 1 HSC.

Soft skills saisies par l'utilisateur : "{user_input}"

Activité : {activity_name}
Tâches (T1..Tn) : {tasks_text}
Contraintes (C1..Cn) : {constraints_text}
Performances attendues (P1..Pn) : {perf_text}

[Même liste HSC X50-766 + niveaux + 6 règles de raisonnement]
Format de sortie : tableau JSON — chaque entrée = { habilete, niveau, justification }""",
    },
    {
        "id": "06",
        "title": "Scoring Inclusion (Aptitudes)",
        "page": "Page liste des activités (onglet Aptitudes, bouton Proposer Aptitudes)",
        "endpoint": "POST /propose_aptitudes/propose",
        "file": "Code/routes/propose_aptitudes.py",
        "desc": (
            "Analyse l'accessibilité et les conditions de travail d'une activité "
            "selon 5 catégories (Vision, Auditif, Physique, Environnemental, "
            "Exposition/Risque). Retourne un scoring JSON avec niveau de contrainte "
            "(0-3), risque résumé et leviers d'adaptation inclusive pour chaque "
            "catégorie, ainsi que des profils valorisables."
        ),
        "system": (
            "Tu es un expert en analyse du travail, prevention sante/securite et inclusion. "
            "Tu reponds UNIQUEMENT en JSON valide, sans markdown ni texte supplementaire. "
            "[+ instruction de langue]"
        ),
        "user": """\
Tu es expert en analyse du travail, prevention sante/securite et inclusion.
Important : ne traite PAS les HSC (cognitif). Ici : accessibilite, prevention, conditions de travail.

Activite : {activity_name}
Resume activite (outils, delais, conformite, environnement) : {activity_summary}
Competences attendues : {competences_text}
Savoirs attendus : {savoirs_text}
Savoir-faire attendus : {savoir_faire_text}
HSC essentielles : {hsc_context}

Echelle : 0 (Aucune) | 1 (Faible) | 2 (Moderee) | 3 (Elevee)

Categories : Vision / Auditif / Physique / Environnemental / Exposition-Risque

[6 règles de concision, leviers adaptatifs, anti-générique, gestion du délai…]
Format : JSON brut — vision, auditif, physique, environnemental, exposition_risque,
         profils_valorisables""",
    },
    {
        "id": "07",
        "title": "Faisabilité Handicap (ICF/CIF)",
        "page": "Page liste des activités (onglet Aptitudes, étape 2 du scoring)",
        "endpoint": "POST /propose_aptitudes/feasibility",
        "file": "Code/routes/propose_aptitudes.py",
        "desc": (
            "Évalue la faisabilité d'adaptation d'une personne présentant des "
            "limitations fonctionnelles à une activité donnée. Basé sur la référence "
            "ICF/CIF (OMS). Distingue les mesures déjà en place, les ajouts recommandés "
            "et les points à instruire. Ne pose aucun diagnostic médical."
        ),
        "system": (
            "Tu es un expert prevention et inclusion. Tu n'etablis aucun diagnostic medical. "
            "Tu reponds UNIQUEMENT en JSON valide, sans markdown ni texte supplementaire. "
            "[+ instruction de langue]"
        ),
        "user": """\
Tu es expert prevention et inclusion. Tu n'etablis aucun diagnostic medical.
Objectif : evaluer la faisabilite d'adaptation d'une personne (limitations fonctionnelles)
a une activite, en tenant compte des aides/compensations deja en place.

Reference : description fonctionnelle inspiree ICF/CIF (OMS).

Activite : {activity_name}
Analyse exigences (JSON) : {inclusion_scoring_json}

Profil fonctionnel :
- Vision / Audition / Motricité fine / Mobilité-posture / Endurance / Sensibilité environnementale

Aides / compensations deja en place : {assistive_products}

[5 règles : statut, distinction mesures/ajouts/à ajuster, alignement exigences…]
Format JSON : statut, mesures_deja_en_place, ajouts_recommandes, a_ajuster,
              risque_residuel, points_a_instruire, commentaire""",
    },
    {
        "id": "08",
        "title": "Plan d'Onboarding HSC",
        "page": "Page Rôles (onglet Plan d'onboarding)",
        "endpoint": "POST /roles/<id>/onboarding/generate",
        "file": "Code/routes/onboarding.py",
        "desc": (
            "Génère un plan d'onboarding en 4 modules exclusivement centré sur le "
            "développement des HSC transmises par le client : Formation/entraînement "
            "(0,5-2 j par module, max 3 j), Retour d'Expérience (REX), Coaching d'équipe, "
            "et Parcours d'apprentissage autonome. Sauvegardé dans role.onboarding_plan."
        ),
        "system": "Vous êtes un assistant spécialisé en développement des HSC et en accompagnement professionnel.",
        "user": """\
Vous êtes un expert en développement des habiletés sociocognitives (HSC) et en
accompagnement professionnel. Votre mission est de générer un plan d'onboarding
exclusivement axé sur les HSC suivantes : {hsc_list}.

1) Module de formation/entraînement :
   - Formations courtes (0,5 à 2 j), total ≤ 3 j
   - Objectifs, durée, Méthode, critères d'évaluation objectifs

2) Retour d'Expérience (REX) :
   - Situations concrètes liées aux HSC cibles, outils de debriefing

3) Coaching d'Équipe :
   - Exercices collaboratifs ciblés sur les HSC, rôle du manager

4) Parcours d'Apprentissage Autonome :
   - Ressources, auto-évaluations, indicateurs de progression""",
    },
    {
        "id": "09",
        "title": "Chatbot Assistant OPTIQ",
        "page": "Icône chatbot (disponible sur toutes les pages activités)",
        "endpoint": "POST /api/chatbot/chat",
        "file": "Code/routes/chatbot.py",
        "desc": (
            "Assistant intervieweur rigoureux pour la saisie ou l'amélioration des "
            "tâches d'une activité OPTIQ. Deux modes : CRÉER (partir de zéro) et "
            "AMÉLIORER (réviser l'existant). Pose une seule question à la fois, "
            "retourne un JSON structuré avec message, statut, liste de tâches, "
            "suggestions et connexions sortantes. Utilise OpenAI GPT."
        ),
        "system": """\
Tu es \"Assistant OPTIQ — Saisie de tâches\".
Tu es un intervieweur rigoureux, bienveillant et orienté livrables.
Ton but : aider l'utilisateur à décrire les TÂCHES d'une activité OPTIQ.

=== DÉFINITIONS OPTIQ ===
- Activité : ensemble cohérent d'actions produisant 1 à 3 résultats / valeurs ajoutées.
- Tâche : \"QUE fait-on ?\" — action observable, résultat intermédiaire.
  Interdit : mode opératoire (clics, menus, micro-étapes).
- Outil : logiciel, formulaire, gabarit, machine, document de référence.

=== RÈGLES STRICTES ===
[8 règles : opérationnalité, nb tâches (5-8), verbes d'action, périmètre,
 enchaînement, conditions, contexte, outils]

=== FORMAT DE RÉPONSE ===
JSON : { assistant_message, status, tasks[], flags{}, suggestions[], outgoing_link,
         next_questions[], branches[] }

+ Mode CRÉER : questions d'exploration depuis zéro
+ Mode AMÉLIORER : révision critique de l'existant""",
        "user": "[Message utilisateur + contexte activité injecté en system]",
    },
    {
        "id": "10",
        "title": "Import IA — Matching non-mappés",
        "page": "Page Import (outil d'import Excel → base de données)",
        "endpoint": "POST /api/import-full/analyze (étape optionnelle)",
        "file": "Code/routes/import_full.py",
        "desc": (
            "Étape optionnelle de l'import Excel : si des groupes d'activités Excel "
            "n'ont pas pu être mappés automatiquement (matching exact/inclusion/fuzzy), "
            "l'IA tente un matching sémantique (synonymes, traductions FR/EN) avec les "
            "activités existantes en base. Retourne un JSON avec les résolutions et "
            "les éléments toujours non-mappés."
        ),
        "system": """\
Tu es un assistant d'import OPTIQ.
On t'envoie des groupes d'activités Excel qui N'ONT PAS pu être mappés automatiquement,
et la liste des activités de la base.

Pour chaque groupe non-mappé, essaie de trouver l'activité la plus proche dans la base
(matching sémantique, synonymes, traductions FR/EN).

Réponds UNIQUEMENT en JSON valide :
{
  "resolved": [
    {
      "activity_name_excel": "...",
      "activity_id": 42,
      "activity_name_db": "...",
      "confidence": "high|medium|low",
      "match_reason": "..."
    }
  ],
  "still_unmatched": ["nom excel", ...]
}""",
        "user": "[Payload JSON des groupes non-mappés + liste activités DB]",
    },
    {
        "id": "11",
        "title": "Changelog utilisateur",
        "page": "Page Changelog / Journal des modifications",
        "endpoint": "GET /api/changelog",
        "file": "Code/routes/changelog.py",
        "desc": (
            "Transforme les 30 derniers messages de commits git en notes de version "
            "positives et lisibles pour des utilisateurs non-techniques. "
            "Génère 3 à 5 points groupés par thème avec icône Font Awesome. "
            "Mis en cache 1 h (basé sur le hash du dernier commit). "
            "Fallback : fichier JSON curé si présent."
        ),
        "system": """\
Tu es le rédacteur des notes de version d'une application web professionnelle de
gestion de processus métier appelée OPTIQ.
Tu reçois des messages de commits git et tu les transformes en annonces concrètes
et positives pour des utilisateurs non-techniques.

RÈGLES :
- 3 à 5 points maximum, regroupés par thème
- Langue : français uniquement, ton positif et concret
- JAMAIS mentionner : ORM, SQL, CSS, hash, token, migration, backend, bug, refactoring
- Décris le bénéfice : "vous pouvez désormais…", "la page X affiche maintenant…"
- Chaque point : titre court (≤5 mots) + description (1-2 phrases)
- icon : une classe Font Awesome pertinente
- Réponds UNIQUEMENT en JSON strict :
  {"items": [{"icon":"fa-solid fa-...","title":"...","desc":"..."}, ...]}""",
        "user": "Commits récents :\n{commits_text}\n\nGénère le changelog utilisateur.",
    },
    {
        "id": "12",
        "title": "Plan de Compétences (Formation / Accompagnement / Maintien)",
        "page": "Page Compétences (bouton Générer le plan)",
        "endpoint": "POST /competences_plan/generate_plan",
        "file": "Code/routes/competences_plan.py",
        "desc": (
            "Génère un plan personnalisé en fonction des évaluations du manager. "
            "Décide automatiquement du type de plan : PLAN_DE_FORMATION (écarts S/SF/HSC), "
            "PLAN_D'ACCOMPAGNEMENT_COMPETENCE (S/SF/HSC OK mais compétence non verte), "
            "ou FEEDBACK_DE_MAINTIEN (tout vert). Modalités variées, échéancier 8 semaines "
            "avec jalons S2/S4/S8."
        ),
        "system": "(aucun rôle system séparé — tout dans le message user)",
        "user": """\
Analyse les informations du RÔLE et de l'ACTIVITÉ ci-dessous (performances standard et
spécifiques, Savoirs, Savoir-faire, HSC, évaluations et commentaires du manager).

Décide et produis UN SEUL livrable :
1) Écarts S/SF/HSC ⇒ PLAN_DE_FORMATION
2) S/SF/HSC OK mais compétence non verte ⇒ PLAN_D_ACCOMPAGNEMENT_COMPETENCE
3) Tout vert ⇒ FEEDBACK_DE_MAINTIEN

Règles :
- Base-toi sur les évaluations et commentaires, impacts sur performances.
- Regroupe par thèmes. Modalités variées (coaching, compagnonnage, atelier, micro-learning…).
- Chaque action : objectif, méthode, livrables, durée estimée, séquencement, critères de validation.
- Échéancier sur 8 semaines max avec jalons S2 / S4 / S8.
- Sortie strictement JSON selon le schéma communiqué.

=== CONTEXTE STRUCTURÉ ===
{payload_json}""",
    },
]

SECTION_GROUPS = [
    ("Page Liste des Activités", ["01", "02", "03", "04", "05", "06", "07"]),
    ("Rôles & Compétences", ["08", "12"]),
    ("Chatbot & Import", ["09", "10"]),
    ("Administration", ["11"]),
]


def escape_xml(text):
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;"))


def build_story(styles):
    story = []

    # ── Cover ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph("DevOPTIQ", styles["cover_title"]))
    story.append(Paragraph("Référentiel des Prompts IA", styles["cover_sub"]))
    story.append(Paragraph("Mai 2026", styles["cover_date"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="80%", thickness=2, color=PINK, hAlign='CENTER'))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        "Ce document recense l'ensemble des prompts envoyés à l'IA (OpenAI GPT-4o-mini / GPT-4) "
        "dans l'application DevOPTIQ. Pour chaque prompt : description fonctionnelle, "
        "endpoint concerné, fichier source, message system et message user.",
        ParagraphStyle("cover_body", fontName="Helvetica", fontSize=11,
                       textColor=GRAY, alignment=TA_CENTER, leading=16)
    ))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(
        f"<b>{len(PROMPTS)} prompts documentés</b>",
        ParagraphStyle("cover_count", fontName="Helvetica-Bold", fontSize=13,
                       textColor=PINK, alignment=TA_CENTER)
    ))
    story.append(PageBreak())

    # ── Table of contents ────────────────────────────────────────────────────
    story.append(Paragraph("Sommaire", styles["section_title"]))
    story.append(Spacer(1, 0.3*cm))
    for p in PROMPTS:
        story.append(Paragraph(
            f"<b>{p['id']}</b>  &nbsp; {escape_xml(p['title'])} "
            f"<font color='#6b7280' size='9'>— {escape_xml(p['page'])}</font>",
            styles["toc"]
        ))
    story.append(PageBreak())

    # ── Prompt cards ─────────────────────────────────────────────────────────
    for p in PROMPTS:
        card = []
        card.append(HRFlowable(width="100%", thickness=1, color=PINK))
        card.append(Spacer(1, 0.2*cm))
        card.append(Paragraph(
            f"<font color='#ec4899'>[{escape_xml(p['id'])}]</font>  {escape_xml(p['title'])}",
            styles["card_title"]
        ))
        card.append(Paragraph(
            f"<b>Page :</b> {escape_xml(p['page'])}",
            ParagraphStyle("meta", fontName="Helvetica", fontSize=9,
                           textColor=GRAY, spaceAfter=1)
        ))
        card.append(Paragraph(
            f"<b>Endpoint :</b> <font name='Courier'>{escape_xml(p['endpoint'])}</font>  "
            f"— <b>Fichier :</b> <font name='Courier'>{escape_xml(p['file'])}</font>",
            ParagraphStyle("meta2", fontName="Helvetica", fontSize=9,
                           textColor=GRAY, spaceAfter=6)
        ))
        card.append(Paragraph(escape_xml(p['desc']), styles["desc"]))

        card.append(Paragraph("SYSTEM", styles["label"]))
        card.append(Paragraph(
            f"<font name='Courier' size='8'>{escape_xml(p['system'])}</font>",
            ParagraphStyle("mono_inner", fontName="Courier", fontSize=8,
                           textColor=DARK, spaceAfter=4, leading=12,
                           backColor=LGRAY, borderPad=4,
                           leftIndent=6, rightIndent=6)
        ))
        card.append(Paragraph("USER", styles["label"]))
        card.append(Paragraph(
            f"<font name='Courier' size='8'>{escape_xml(p['user'])}</font>",
            ParagraphStyle("mono_inner2", fontName="Courier", fontSize=8,
                           textColor=DARK, spaceAfter=4, leading=12,
                           backColor=LGRAY, borderPad=4,
                           leftIndent=6, rightIndent=6)
        ))
        card.append(Spacer(1, 0.4*cm))

        story.append(KeepTogether(card[:6]))  # keep header + description together
        for item in card[6:]:
            story.append(item)

    return story


def main():
    out = "/home/user/DevOPTIQ/DevOPTIQ_Prompts_IA.pdf"
    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="DevOPTIQ — Référentiel des Prompts IA",
        author="AFDEC / Mael Girardin",
    )
    styles = make_styles()
    story  = build_story(styles)
    doc.build(story)
    print(f"PDF généré : {out}")


if __name__ == "__main__":
    main()
