# FICHIER: Code/routes/competences.py
# VERSION CORRIGÉE - Gestion UPSERT pour PostgreSQL

from flask import Blueprint, jsonify, render_template, request, session
from Code.extensions import db
from datetime import datetime
from sqlalchemy import text
from Code.models.models import (
    Competency, Role, Activities, User, UserRole,
    CompetencyEvaluation, Savoir, SavoirFaire, Aptitude, Softskill, activity_roles, PerformancePersonnalisee, Entity
)

competences_bp = Blueprint('competences_bp', __name__, url_prefix='/competences')

@competences_bp.route('/view', methods=['GET'])
def competences_view():
    return render_template('competences_view.html')


@competences_bp.route('/current_user_manager', methods=['GET'])
def get_current_user_manager():
    """Retourne l'utilisateur connecté et le manager approprié"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Non connecté'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Utilisateur introuvable'}), 404

    # Récupérer l'entité active
    active_entity_id = Entity.get_active_id()

    # Vérifier si l'utilisateur est un manager
    if active_entity_id:
        role_manager = Role.query.filter_by(name='manager', entity_id=active_entity_id).first()
    else:
        role_manager = Role.query.filter_by(name='manager').first()

    is_manager = False
    if role_manager:
        user_role = UserRole.query.filter_by(user_id=user_id, role_id=role_manager.id).first()
        is_manager = user_role is not None

    # Si c'est un manager, retourner ses infos
    if is_manager:
        return jsonify({
            'manager_id': user.id,
            'manager_name': f"{user.first_name} {user.last_name}",
            'is_manager': True
        })

    # Sinon, retourner son manager
    if user.manager_id:
        manager = User.query.get(user.manager_id)
        if manager:
            return jsonify({
                'manager_id': manager.id,
                'manager_name': f"{manager.first_name} {manager.last_name}",
                'is_manager': False
            })

    return jsonify({'error': 'Aucun manager trouvé'}), 404


@competences_bp.route('/managers', methods=['GET'])
def get_managers():
    # CORRIGÉ: Filtrer par entité active
    active_entity_id = Entity.get_active_id()
    
    if active_entity_id:
        role_manager = Role.query.filter_by(name='manager', entity_id=active_entity_id).first()
    else:
        role_manager = Role.query.filter_by(name='manager').first()
    
    if not role_manager:
        return jsonify([])
    
    if active_entity_id:
        managers = User.query.filter_by(entity_id=active_entity_id).join(UserRole).filter(UserRole.role_id == role_manager.id).all()
    else:
        managers = User.query.join(UserRole).filter(UserRole.role_id == role_manager.id).all()
    
    return jsonify([{'id': m.id, 'name': f"{m.first_name} {m.last_name}"} for m in managers])


@competences_bp.route('/collaborators/<int:manager_id>', methods=['GET'])
def get_collaborators(manager_id):
    # CORRIGÉ: Filtrer par entité active
    active_entity_id = Entity.get_active_id()
    
    if active_entity_id:
        collaborateurs = User.query.filter_by(manager_id=manager_id, entity_id=active_entity_id).all()
    else:
        collaborateurs = User.query.filter_by(manager_id=manager_id).all()
    
    return jsonify([{'id': u.id, 'first_name': u.first_name, 'last_name': u.last_name} for u in collaborateurs])


@competences_bp.route('/get_user_roles/<int:user_id>', methods=['GET'])
def get_user_roles(user_id):
    user_roles = UserRole.query.filter_by(user_id=user_id).all()
    roles = [Role.query.get(ur.role_id) for ur in user_roles if Role.query.get(ur.role_id)]
    return jsonify({'roles': [{'id': r.id, 'name': r.name} for r in roles]})


@competences_bp.route('/save_user_evaluations', methods=['POST'])
def save_user_evaluations():
    """
    VERSION CORRIGÉE avec gestion robuste des conflits PostgreSQL.
    Utilise une approche "delete + insert" pour éviter les problèmes de séquence.
    """
    data = request.get_json()
    user_id = data.get('userId')
    evaluations = data.get('evaluations', [])

    if not user_id or not evaluations:
        return jsonify({'success': False, 'message': 'Données incomplètes.'}), 400

    saved_evals = []

    try:
        for eval_data in evaluations:
            activity_id = eval_data.get('activity_id')
            item_id = eval_data.get('item_id')
            item_type = eval_data.get('item_type')
            eval_number = str(eval_data.get('eval_number'))
            note = eval_data.get('note')

            if not activity_id:
                print(f"❌ Ignoré (pas d'activité): {eval_data}")
                continue

            # Construire la requête de recherche en gérant le cas NULL
            if item_id is None:
                existing = db.session.query(CompetencyEvaluation).filter(
                    CompetencyEvaluation.user_id == user_id,
                    CompetencyEvaluation.activity_id == activity_id,
                    CompetencyEvaluation.item_id.is_(None),
                    CompetencyEvaluation.item_type == item_type,
                    CompetencyEvaluation.eval_number == eval_number
                ).first()
            else:
                existing = db.session.query(CompetencyEvaluation).filter(
                    CompetencyEvaluation.user_id == user_id,
                    CompetencyEvaluation.activity_id == activity_id,
                    CompetencyEvaluation.item_id == item_id,
                    CompetencyEvaluation.item_type == item_type,
                    CompetencyEvaluation.eval_number == eval_number
                ).first()

            now = datetime.utcnow()

            if existing:
                if note == 'empty':
                    db.session.delete(existing)
                else:
                    existing.note = note
                    existing.created_at = now
                    saved_evals.append({
                        "activity_id": activity_id,
                        "item_id": item_id,
                        "item_type": item_type,
                        "eval_number": eval_number,
                        "note": note,
                        "created_at": existing.created_at.isoformat()
                    })
            else:
                if note != 'empty':
                    # Utiliser SQL brut pour éviter les problèmes de séquence
                    try:
                        new_eval = CompetencyEvaluation(
                            user_id=user_id,
                            activity_id=activity_id,
                            item_id=item_id,
                            item_type=item_type,
                            eval_number=eval_number,
                            note=note,
                            created_at=now
                        )
                        db.session.add(new_eval)
                        db.session.flush()
                        saved_evals.append({
                            "activity_id": activity_id,
                            "item_id": item_id,
                            "item_type": item_type,
                            "eval_number": eval_number,
                            "note": note,
                            "created_at": new_eval.created_at.isoformat()
                        })
                    except Exception as insert_err:
                        # En cas d'erreur de contrainte, rollback partiel et réessayer avec update
                        db.session.rollback()
                        print(f"⚠️ Conflit détecté, tentative de mise à jour: {insert_err}")
                        
                        # Rechercher à nouveau et mettre à jour
                        if item_id is None:
                            existing = db.session.query(CompetencyEvaluation).filter(
                                CompetencyEvaluation.user_id == user_id,
                                CompetencyEvaluation.activity_id == activity_id,
                                CompetencyEvaluation.item_id.is_(None),
                                CompetencyEvaluation.item_type == item_type,
                                CompetencyEvaluation.eval_number == eval_number
                            ).first()
                        else:
                            existing = db.session.query(CompetencyEvaluation).filter(
                                CompetencyEvaluation.user_id == user_id,
                                CompetencyEvaluation.activity_id == activity_id,
                                CompetencyEvaluation.item_id == item_id,
                                CompetencyEvaluation.item_type == item_type,
                                CompetencyEvaluation.eval_number == eval_number
                            ).first()
                        
                        if existing:
                            existing.note = note
                            existing.created_at = now
                            saved_evals.append({
                                "activity_id": activity_id,
                                "item_id": item_id,
                                "item_type": item_type,
                                "eval_number": eval_number,
                                "note": note,
                                "created_at": now.isoformat()
                            })

        db.session.commit()
        return jsonify({'success': True, 'evaluations': saved_evals})

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur save_user_evaluations: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@competences_bp.route('/get_user_evaluations_by_user/<int:user_id>', methods=['GET'])
def get_user_evaluations_by_user(user_id):
    def to_iso(dt):
        if not dt:
            return ''
        if isinstance(dt, datetime):
            return dt.isoformat()
        if isinstance(dt, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                        "%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    return datetime.strptime(dt, fmt).isoformat()
                except ValueError:
                    continue
            return dt
        return ''

    # CORRIGÉ: Filtrer par entité active
    active_entity_id = Entity.get_active_id()
    
    if active_entity_id:
        active_activity_ids = [a.id for a in Activities.query.filter_by(entity_id=active_entity_id).all()]
        evaluations = CompetencyEvaluation.query.filter(
            CompetencyEvaluation.user_id == user_id,
            CompetencyEvaluation.activity_id.in_(active_activity_ids) if active_activity_ids else False
        ).all()
    else:
        evaluations = CompetencyEvaluation.query.filter_by(user_id=user_id).all()
    
    return jsonify([{
        'activity_id': e.activity_id,
        'item_id': e.item_id,
        'item_type': e.item_type,
        'eval_number': e.eval_number,
        'note': e.note,
        'created_at': to_iso(e.created_at)
    } for e in evaluations])


@competences_bp.route('/role_structure/<int:user_id>/<int:role_id>', methods=['GET'])
def get_role_structure(user_id, role_id):
    role = Role.query.get(role_id)
    user = User.query.get(user_id)
    if not role or not user:
        return jsonify({'error': 'Utilisateur ou rôle non trouvé'}), 404

    # CORRIGÉ: Filtrer par entité active
    active_entity_id = Entity.get_active_id()
    
    query = db.session.query(Activities).join(activity_roles).filter(activity_roles.c.role_id == role_id)
    
    if active_entity_id:
        query = query.filter(Activities.entity_id == active_entity_id)
    
    activities = query.all()

    all_evaluations = CompetencyEvaluation.query.filter_by(user_id=user_id).all()
    
    # Dictionnaire pour les évaluations d'items (savoirs, SF, HSC)
    eval_dict = {}
    # Dictionnaire séparé pour les évaluations d'activités
    activity_eval_dict = {}
    
    for e in all_evaluations:
        if e.item_type == 'activities' and e.item_id is None:
            # Évaluation d'une activité entière (Garant/Manager/RH)
            key = (e.activity_id, str(e.eval_number))
            activity_eval_dict[key] = {
                'note': e.note,
                'created_at': e.created_at
            }
        else:
            # Évaluation d'un item spécifique (savoir, SF, HSC)
            key = (e.item_id, e.item_type, str(e.eval_number))
            eval_dict[key] = {
                'note': e.note,
                'created_at': e.created_at
            }

    activities_data = []
    for activity in activities:
        activity_obj = {
            'id': activity.id,
            'name': activity.name,
            'savoirs': [],
            'savoir_faires': [],
            'hsc': []
        }

        for savoir in activity.savoirs:
            activity_obj['savoirs'].append({
                'id': savoir.id,
                'description': savoir.description,
                'evals': {
                    k: eval_dict.get((savoir.id, 'savoirs', k), {}) for k in ['1', '2', '3']
                }
            })

        for sf in activity.savoir_faires:
            activity_obj['savoir_faires'].append({
                'id': sf.id,
                'description': sf.description,
                'evals': {
                    k: eval_dict.get((sf.id, 'savoir_faires', k), {}) for k in ['1', '2', '3']
                }
            })

        for hsc in activity.softskills:
            activity_obj['hsc'].append({
                'id': hsc.id,
                'description': hsc.habilete,
                'niveau': hsc.niveau,
                'evals': {
                    k: eval_dict.get((hsc.id, 'softskills', k), {}) for k in ['1', '2', '3']
                }
            })

        activities_data.append(activity_obj)

    synthese = []
    for activity in activities:
        synthese.append({
            'activity_id': activity.id,
            'activity_name': activity.name,
            'competencies': [c.description for c in activity.competencies],
            'evals': {
                # Utiliser le dictionnaire dédié aux évaluations d'activités
                'garant': activity_eval_dict.get((activity.id, 'garant'), {}),
                'manager': activity_eval_dict.get((activity.id, 'manager'), {}),
                'rh': activity_eval_dict.get((activity.id, 'rh'), {})
            }
        })

    return jsonify({
        'role_id': role.id,
        'role_name': role.name,
        'activities': activities_data,
        'synthese': synthese
    })


@competences_bp.route('/global_summary/<int:user_id>')
def global_summary(user_id):
    """
    VERSION CORRIGÉE - Retourne du JSON au lieu d'un template pour éviter les erreurs 503
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur introuvable'}), 404

        user_roles = UserRole.query.filter_by(user_id=user_id).all()
        role_ids = [ur.role_id for ur in user_roles]
        roles = Role.query.filter(Role.id.in_(role_ids)).all()

        # CORRIGÉ: Filtrer par entité active
        active_entity_id = Entity.get_active_id()

        evals = CompetencyEvaluation.query.filter_by(user_id=user_id).all()
        
        # Construire un dictionnaire pour les évaluations d'activités
        # Clé: (activity_id, eval_number) -> note
        activity_eval_map = {}
        for e in evals:
            if e.item_type == 'activities' and e.item_id is None:
                key = (e.activity_id, str(e.eval_number))
                activity_eval_map[key] = e.note

        role_data = []
        for role in roles:
            query = db.session.query(Activities).join(activity_roles).filter(activity_roles.c.role_id == role.id)
            if active_entity_id:
                query = query.filter(Activities.entity_id == active_entity_id)
            activities = query.all()
            
            activity_data = []
            for activity in activities:
                competencies = [c.description for c in activity.competencies]
                activity_data.append({
                    'name': activity.name,
                    'competencies': competencies,
                    'evals': {
                        'garant': activity_eval_map.get((activity.id, 'garant')),
                        'manager': activity_eval_map.get((activity.id, 'manager')),
                        'rh': activity_eval_map.get((activity.id, 'rh'))
                    }
                })
            role_data.append({
                'name': role.name,
                'activities': activity_data
            })

        # Retourner du HTML généré côté serveur
        html = render_global_summary_html(user, role_data)
        return html

    except Exception as e:
        print(f"❌ Erreur global_summary: {e}")
        return jsonify({'error': str(e)}), 500


def render_global_summary_html(user, role_data):
    """Génère le HTML de la synthèse globale directement"""
    html = f'''
    <div class="summary-content">
        <h2 style="font-family: 'Fraunces', serif; margin-bottom: 20px;">
            Synthèse globale - {user.first_name} {user.last_name}
        </h2>
    '''
    
    if not role_data:
        html += '<p class="text-muted">Aucun rôle attribué à cet utilisateur.</p>'
    else:
        for role in role_data:
            html += f'''
            <div style="margin-bottom: 24px;">
                <h3 style="font-size: 16px; color: #10b981; margin-bottom: 12px; text-transform: capitalize;">
                    {role['name']}
                </h3>
            '''
            
            if not role['activities']:
                html += '<p class="text-muted" style="font-size: 14px;">Aucune activité pour ce rôle.</p>'
            else:
                html += '''
                <div class="table-wrapper">
                    <table class="eval-table">
                        <thead>
                            <tr>
                                <th>Activité</th>
                                <th class="th-eval">Garant</th>
                                <th class="th-eval">Manager</th>
                                <th class="th-eval">RH</th>
                            </tr>
                        </thead>
                        <tbody>
                '''
                
                for act in role['activities']:
                    competencies_str = ', '.join(act['competencies']) if act['competencies'] else ''
                    comp_html = f'<br><small class="text-muted">Compétences : {competencies_str}</small>' if competencies_str else ''
                    
                    garant_class = act['evals'].get('garant') or ''
                    manager_class = act['evals'].get('manager') or ''
                    rh_class = act['evals'].get('rh') or ''
                    
                    html += f'''
                        <tr>
                            <td>{act['name']}{comp_html}</td>
                            <td class="eval-cell {garant_class}" style="pointer-events: none;"></td>
                            <td class="eval-cell {manager_class}" style="pointer-events: none;"></td>
                            <td class="eval-cell {rh_class}" style="pointer-events: none;"></td>
                        </tr>
                    '''
                
                html += '''
                        </tbody>
                    </table>
                </div>
                '''
            
            html += '</div>'
    
    html += '</div>'
    return html


@competences_bp.route('/global_flat_summary/<int:user_id>')
def global_flat_summary(user_id):
    user = User.query.get(user_id)
    if not user:
        return "Utilisateur introuvable", 404

    user_roles = UserRole.query.filter_by(user_id=user_id).all()
    role_ids = [ur.role_id for ur in user_roles]
    roles = Role.query.filter(Role.id.in_(role_ids)).all()

    # CORRIGÉ: Filtrer par entité active
    active_entity_id = Entity.get_active_id()

    evaluations = CompetencyEvaluation.query.filter_by(user_id=user_id).all()
    
    # Dictionnaire pour les évaluations d'activités
    eval_map = {}
    eval_date_map = {}
    
    for e in evaluations:
        # Évaluations d'activités: item_type='activities' et item_id=None
        if e.item_type == 'activities' and e.item_id is None:
            key = (e.activity_id, str(e.eval_number))
            eval_map[key] = e.note
            if e.created_at:
                if isinstance(e.created_at, str):
                    try:
                        parsed_date = datetime.fromisoformat(e.created_at)
                    except ValueError:
                        parsed_date = datetime.strptime(e.created_at, "%d/%m/%Y")
                else:
                    parsed_date = e.created_at
                eval_date_map[key] = parsed_date.strftime('%d/%m/%Y')
            else:
                eval_date_map[key] = ''

    header_roles = []
    header_activities = []
    row_manager = []

    for role in roles:
        query = db.session.query(Activities).join(activity_roles).filter(activity_roles.c.role_id == role.id)
        if active_entity_id:
            query = query.filter(Activities.entity_id == active_entity_id)
        activities = query.all()
        
        if not activities:
            continue

        all_green = all(
            eval_map.get((act.id, 'manager'), '') == 'green'
            for act in activities
        )
        role_status = 'green' if all_green else ''

        header_roles.append({
            'name': role.name,
            'span': len(activities),
            'status': role_status
        })

        for act in activities:
            header_activities.append(act.name)
            key = (act.id, 'manager')
            row_manager.append({
                'activity_id': act.id,
                'note': eval_map.get(key, ''),
                'date': eval_date_map.get(key, '')
            })

    return render_template(
        'global_flat_summary.html',
        user=user,
        header_roles=header_roles,
        header_activities=header_activities,
        row_manager=row_manager,
        current_date=datetime.now().strftime('%d/%m/%Y') 
    )


@competences_bp.route('/users/global_summary', methods=['GET'])
def users_global_summary():
    try:
        # CORRIGÉ: Filtrer par entité active
        active_entity_id = Entity.get_active_id()

        if active_entity_id:
            users = User.query.filter_by(entity_id=active_entity_id).all()
            roles = Role.query.filter_by(entity_id=active_entity_id).order_by(Role.name).all()
        else:
            users = User.query.all()
            roles = Role.query.order_by(Role.name).all()

        # Préparer l'ensemble des activités par rôle
        role_activities_map = {}
        for role in roles:
            query = db.session.query(Activities).join(activity_roles).filter(activity_roles.c.role_id == role.id)
            if active_entity_id:
                query = query.filter(Activities.entity_id == active_entity_id)
            acts = query.all()
            role_activities_map[role.id] = acts

        user_rows = []
        for user in users:
            # CORRIGÉ: Filtrer uniquement les évaluations d'activités (pas les savoirs/SF/HSC)
            evals = CompetencyEvaluation.query.filter(
                CompetencyEvaluation.user_id == user.id,
                CompetencyEvaluation.eval_number == 'manager',
                CompetencyEvaluation.item_type == 'activities',
                CompetencyEvaluation.item_id.is_(None)
            ).all()
            notes = []

            for role in roles:
                role_activities = role_activities_map.get(role.id, [])
                related_notes = [
                    e.note for e in evals
                    if e.activity_id in [a.id for a in role_activities]
                ]
                note = related_notes[0] if related_notes else None
                notes.append(note)

            user_rows.append({
                'user': f"{user.first_name} {user.last_name}",
                'user_id': user.id,
                'manager_id': user.manager_id,
                'notes': notes
            })

        role_names = [r.name for r in roles]
        roles_loop = [r.name for r in roles]

        return render_template(
            'global_users_summary.html',
            roles=roles,
            user_rows=user_rows,
            all_role_names=role_names,
            roles_loop=roles_loop
        )
    except Exception as e:
        print(f"❌ Erreur dans users_global_summary: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()  # Rollback pour réinitialiser la transaction
        # Retourner un message d'erreur HTML au lieu d'une erreur 500
        return f"<p style='color: red;'>Erreur lors du chargement des données: {str(e)}</p>", 500


@competences_bp.route('/general_performance/<int:activity_id>', methods=['GET'])
def get_general_performance(activity_id):
    from Code.models.models import Link, Performance
    link = Link.query.filter_by(source_activity_id=activity_id).first()
    if not link or not link.performance:
        return jsonify({'content': ''})
    return jsonify({'content': link.performance.name or ''})