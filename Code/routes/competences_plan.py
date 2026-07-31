# Code/routes/competences_plan.py
import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from Code.ai_key import get_openai_key
from Code.prompts import get_prompt, prompts_available
from sqlalchemy import text
from Code.extensions import db

competences_plan_bp = Blueprint(
    "competences_plan", __name__, url_prefix="/competences_plan"
)

# ==================== PROMPT ====================




# ==================== Helpers ====================

def _ensure_tables_exist():
    """
    S'assure que les tables nécessaires existent.
    Crée les tables si elles n'existent pas.
    """
    try:
        # Vérifier si la table training_plan existe
        result = db.session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'training_plan'
            )
        """)).scalar()
        
        if not result:
            # Créer la table training_plan pour PostgreSQL
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS training_plan (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    activity_id INTEGER NOT NULL,
                    plan_type VARCHAR(100),
                    plan_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        # Essayer la syntaxe SQLite si PostgreSQL échoue
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS training_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    activity_id INTEGER NOT NULL,
                    plan_type TEXT,
                    plan_json TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """))
            db.session.commit()
        except Exception as e2:
            db.session.rollback()
            print(f"Erreur création table training_plan: {e2}")
    
    try:
        # Vérifier si la table prerequis_comment existe
        result = db.session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'prerequis_comment'
            )
        """)).scalar()
        
        if not result:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS prerequis_comment (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    activity_id INTEGER NOT NULL,
                    item_type VARCHAR(100),
                    item_id INTEGER,
                    comment TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS prerequis_comment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    activity_id INTEGER NOT NULL,
                    item_type TEXT,
                    item_id INTEGER,
                    comment TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """))
            db.session.commit()
        except Exception as e2:
            db.session.rollback()
            print(f"Erreur création table prerequis_comment: {e2}")


def _dummy_plan():
    """Plan de secours pour dev/test sans clé API ou en cas d'erreur SDK."""
    return {
        "type": "PLAN_DE_FORMATION",
        "contexte_synthetique": {
            "activite": "Activité (démo)",
            "performances_cibles": ["Qualité", "Délais"],
            "hypotheses": []
        },
        "axes": [
            {
                "intitule": "Mise à niveau Savoirs",
                "justification": "Écarts détectés sur certains savoirs / commentaires manager",
                "objectifs_pedagogiques": ["Assimiler les concepts clés"],
                "parcours": [{
                    "option": "Judicieuse",
                    "methodes": ["micro-learning", "atelier pratique"],
                    "contenus_recommandes": ["Module interne A", "Cas d'exercice"],
                    "prerequis": [],
                    "duree_estimee_heures": 6,
                    "livrables_attendus": ["Checklist appliquée"],
                    "criteres_de_validation": ["0 erreur sur cas test"]
                }],
                "jalons": [
                    {"semaine": 2, "verif": "mini-évaluation"},
                    {"semaine": 4, "verif": "KPI intermédiaires"},
                    {"semaine": 8, "verif": "KPI finaux"}
                ]
            }
        ],
        "synthese_charge": {
            "duree_totale_estimee_heures": 6,
            "impact_organisation": "modéré",
            "recommandation_globale": "Lancer un micro-parcours de 2 semaines."
        },
        "meta": {"source": "dummy_fallback"}
    }

def _call_llm_or_dummy(prompt: str):
    """
    Version compatible openai>=1.0.0.
    - Utilise from openai import OpenAI ; client = OpenAI()
    - Renvoie un dict JSON.
    - En cas d'indispo clé/API/SDK ⇒ plan dummy.
    """
    api_key = get_openai_key()
    if not api_key:
        return _dummy_plan()

    try:
        from Code.ai_client import make_ai_client
        client, model, _err = make_ai_client()
        model = os.environ.get("OPENAI_MODEL") or model
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content or ""
        # On attend du JSON strict ; tente un parse direct
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Si le modèle a rajouté du texte, on essaie d'extraire le JSON
            import re
            m = re.search(r"\{[\s\S]*\}\s*$", content)
            if m:
                return json.loads(m.group(0))
            # Dernier recours : dummy
            fallback = _dummy_plan()
            fallback["meta"] = {"source": "fallback_parse_error", "raw": content[:4000]}
            return fallback

    except Exception as e:
        # Au lieu d'échouer côté front, on renvoie un plan dummy annoté de l'erreur
        fallback = _dummy_plan()
        fallback["meta"] = {"source": "fallback_exception", "error": str(e)}
        return fallback

# ==================== ROUTES ====================

@competences_plan_bp.route("/save_prerequis", methods=["POST"])
def save_prerequis():
    """
    Body:
    { user_id, activity_id, comments: [{item_type, item_id, comment}] }
    Stratégie 'upsert simple' : on efface l'existant de (user, activity) puis on réinsère.
    """
    _ensure_tables_exist()
    
    data = request.get_json(force=True)
    user_id = int(data["user_id"])
    activity_id = int(data["activity_id"])
    comments = data.get("comments", [])

    db.session.execute(
        text("DELETE FROM prerequis_comment WHERE user_id=:u AND activity_id=:a"),
        {"u": user_id, "a": activity_id},
    )
    now = datetime.utcnow().isoformat()
    for c in comments:
        db.session.execute(
            text("""
                INSERT INTO prerequis_comment(user_id, activity_id, item_type, item_id, comment, updated_at)
                VALUES(:u, :a, :t, :i, :c, :now)
            """),
            {
                "u": user_id,
                "a": activity_id,
                "t": c["item_type"],
                "i": int(c["item_id"]),
                "c": c.get("comment", ""),
                "now": now
            }
        )
    db.session.commit()
    return jsonify({"ok": True})

@competences_plan_bp.route("/get_prerequis/<int:user_id>/<int:activity_id>", methods=["GET"])
def get_prerequis(user_id: int, activity_id: int):
    """
    Renvoie la liste des commentaires existants pour (user, activity):
    [{item_type, item_id, comment}]
    """
    _ensure_tables_exist()
    
    rows = db.session.execute(
        text("""
            SELECT item_type, item_id, comment
            FROM prerequis_comment
            WHERE user_id=:u AND activity_id=:a
        """),
        {"u": user_id, "a": activity_id}
    ).mappings().all()

    return jsonify([dict(r) for r in rows])

@competences_plan_bp.route("/generate_plan", methods=["POST"])
def generate_plan():
    """
    Body:
    {
      user_id, role_id, activity_id,
      payload_contexte: { role:{...}, activity:{...}, evaluations:{...}, prerequis_comments:[...] }
    }
    Sauvegarde le plan (réel ou dummy) et renvoie {ok:True, plan}
    """
    _ensure_tables_exist()
    
    try:
        data = request.get_json(force=True)
        user_id = int(data["user_id"])
        role_id = int(data["role_id"])
        activity_id = int(data["activity_id"])
        payload = data.get("payload_contexte", {})

        lang = session.get('lang', 'fr')
        header = get_prompt(f"competences_plan.header.{'en' if lang == 'en' else 'fr'}")
        if header is None:
            return jsonify({"ok": False, "error": "Prompts IA non chargés sur cette instance."}), 503
        ctx_label = "STRUCTURED CONTEXT" if lang == 'en' else "CONTEXTE STRUCTURÉ"
        end_label = "END CONTEXT" if lang == 'en' else "FIN CONTEXTE"
        prompt = f"{header}\n\n=== {ctx_label} ===\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n=== {end_label} ==="

        # Appel LLM (ou fallback)
        plan = _call_llm_or_dummy(prompt)

        # Sauvegarde
        plan_type = plan.get("type", "PLAN")
        db.session.execute(
            text("""
                INSERT INTO training_plan(user_id, role_id, activity_id, plan_type, plan_json)
                VALUES(:u, :r, :a, :pt, :pj)
            """),
            {
                "u": user_id,
                "r": role_id,
                "a": activity_id,
                "pt": plan_type,
                "pj": json.dumps(plan, ensure_ascii=False)
            }
        )
        db.session.commit()

        return jsonify({"ok": True, "plan": plan})
        
    except Exception as e:
        db.session.rollback()
        # Retourner un plan dummy même en cas d'erreur pour éviter le 500
        fallback = _dummy_plan()
        fallback["meta"] = {"source": "error_fallback", "error": str(e)}
        return jsonify({"ok": True, "plan": fallback, "warning": str(e)})