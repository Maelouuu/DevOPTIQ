"""
Couleur de synthèse des compétences d'un utilisateur.

Les notes d'évaluation sont catégorielles : 'red' < 'orange' < 'green' (vide =
non évaluée). On convertit en valeurs (1/2/3), on moyenne, puis on reconvertit
en couleur. Utilisé pour colorer un user selon ses évaluations (page Rôles,
page Gestion RH).

Rappel modèle : CompetencyEvaluation.eval_number contient soit l'évaluateur
('garant' | 'manager' | 'rh') pour les évaluations d'activité, soit '1'/'2'/'3'
pour les évaluations d'items.
"""

NOTE_VALUE  = {'red': 1, 'orange': 2, 'green': 3}
_VALUE_NOTE = {1: 'red', 2: 'orange', 3: 'green'}
COLOR_HEX   = {'red': '#ef4444', 'orange': '#f59e0b', 'green': '#22c55e'}


def user_competency_color(user_id, activity_ids=None, evaluator='manager'):
    """Retourne 'red' | 'orange' | 'green' (ou None si aucune note).

    - evaluator : évaluateur considéré (eval_number d'activité), 'manager' par défaut.
    - activity_ids : restreint le calcul à ces activités (None = toutes ;
      liste vide = None car rien à évaluer).
    """
    from Code.models.models import CompetencyEvaluation
    q = CompetencyEvaluation.query.filter_by(user_id=user_id, eval_number=evaluator)
    if activity_ids is not None:
        activity_ids = list(activity_ids)
        if not activity_ids:
            return None
        q = q.filter(CompetencyEvaluation.activity_id.in_(activity_ids))
    vals = [NOTE_VALUE[e.note] for e in q.all() if e.note in NOTE_VALUE]
    if not vals:
        return None
    avg = sum(vals) / len(vals)
    return _VALUE_NOTE[max(1, min(3, round(avg)))]


def user_competency_hex(user_id, activity_ids=None, evaluator='manager'):
    """Comme user_competency_color mais retourne le code hex (ou None)."""
    name = user_competency_color(user_id, activity_ids=activity_ids, evaluator=evaluator)
    return COLOR_HEX.get(name) if name else None
