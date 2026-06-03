"""Blueprint OptiqCarto — éditeur de cartographie intégré à DevOPTIQ.

La carto JSON de chaque entité est stockée en base de données (colonne
Entity.optiqcarto_data) pour survivre aux redémarrages Cloud Run.
Le fichier VSDX reste sur disque (upload ponctuel, non critique).
"""
import json
import os
import tempfile

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from Code.extensions import db
from Code.models.models import (
    Activities, CartoCalque, CompetencyEvaluation, CrossCartoLiaison,
    Entity, Link, Role, TimeAnalysis, TimeProjectLine, TimeRoleLine,
    TimeRoleAnalysis, TimeWeakness, UserRole, activity_roles, task_roles,
)

cartography_editor_bp = Blueprint("cartography_editor", __name__, url_prefix="/cartography")

# Répertoire de base des entités (pour les fichiers VSDX uploadés)
_ENTITIES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "Code", "static", "entities"
)


def _require_auth():
    return bool(session.get("user_email"))


def _get_active_entity():
    user_id = session.get("user_id")
    entity_id = session.get("active_entity_id")
    if not user_id:
        return None
    if entity_id:
        e = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
        if e:
            return e
    return Entity.query.filter_by(owner_id=user_id).order_by(Entity.id.desc()).first()


def _has_carto(entity) -> bool:
    """Retourne True si l'entité a une carto OptiqCarto enregistrée en base."""
    return bool(entity and entity.optiqcarto_data)


def _vsdx_path(entity):
    if not entity.vsdx_filename:
        return None
    candidates = [
        os.path.join(_ENTITIES_DIR, f"entity_{entity.id}", "connections.vsdx"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                     "Code", entity.vsdx_filename),
        entity.vsdx_filename,
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


# ─────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────

@cartography_editor_bp.route("/viewer")
def viewer():
    if not _require_auth():
        return ("", 403)

    # Paramètre optionnel pour prévisualiser la carto d'une autre entité
    preview_entity_id = request.args.get('entity_id', type=int)
    if preview_entity_id:
        entity = Entity.query.get(preview_entity_id)
    else:
        entity = _get_active_entity()

    has_optiqcarto = _has_carto(entity)
    has_vsdx = bool(entity and _vsdx_path(entity))
    entity_name = entity.name if entity else ""

    active_calque_id   = None
    active_calque_name = ''
    if not preview_entity_id:
        active_calque_id   = session.get('active_calque_id')
        active_calque_name = session.get('active_calque_name', '')
        if active_calque_id and entity:
            cal = CartoCalque.query.filter_by(id=active_calque_id, entity_id=entity.id).first()
            if not cal:
                active_calque_id = None
                active_calque_name = ''

    return render_template(
        "cartography_viewer.html",
        entity_name=entity_name,
        entity_id=entity.id if entity else None,
        has_optiqcarto=has_optiqcarto,
        has_vsdx=has_vsdx,
        active_calque_id=active_calque_id,
        active_calque_name=active_calque_name,
    )


@cartography_editor_bp.route("/editor")
def editor():
    if not _require_auth():
        return redirect(url_for("auth.login"))

    entity = _get_active_entity()
    has_vsdx = False
    has_optiqcarto = False
    entity_name = ""
    entity_id = None

    if entity:
        entity_id = entity.id
        entity_name = entity.name or ""
        has_vsdx = bool(_vsdx_path(entity))
        has_optiqcarto = _has_carto(entity)

    active_calque_id = session.get('active_calque_id')
    if active_calque_id and entity:
        from Code.models.models import CartoCalque
        cal = CartoCalque.query.filter_by(id=active_calque_id, entity_id=entity.id).first()
        if not cal:
            active_calque_id = None

    from Code.translations import TRANSLATIONS
    lang = session.get('lang', 'fr')
    i18n_data = TRANSLATIONS.get(lang, TRANSLATIONS['fr'])

    return render_template(
        "cartography_editor.html",
        entity_name=entity_name,
        entity_id=entity_id,
        has_vsdx=has_vsdx,
        has_optiqcarto=has_optiqcarto,
        active_calque_id=active_calque_id,
        i18n_data=i18n_data,
    )


# ─────────────────────────────────────────────
# CARTO → DB SYNC HELPERS
# ─────────────────────────────────────────────

_ACTIVITY_TYPES = {'process', 'special'}  # 'start-end' (renvois) = cercles visuels, pas des activités
_BANDS_START_Y  = -200  # matches editor.js getBandForY()


def _get_band_for_y(bands, mid_y):
    """Return the band dict that contains mid_y, or None."""
    y = _BANDS_START_Y
    for band in bands:
        h = band.get('height', 180)
        if y <= mid_y < y + h:
            return band
        y += h
    return None


def _compute_removals(entity, new_diagram):
    """Dry-run: return names that would be deleted if new_diagram is saved."""
    new_shapes = new_diagram.get('shapes', [])
    new_bands  = new_diagram.get('bands',  [])

    act_shapes = [s for s in new_shapes if s.get('type') in _ACTIVITY_TYPES]
    renvoi_sids_cr = {str(s['id']) for s in new_shapes if s.get('type') == 'start-end'}
    new_shape_ids = {str(s['id']) for s in act_shapes}
    new_labels    = {(s.get('label') or '').strip() or f"Activité {s['id']}" for s in act_shapes}
    new_band_names = {(b.get('label') or '').strip() for b in new_bands}

    existing_acts  = Activities.query.filter_by(entity_id=entity.id).filter(
        Activities.shape_id.isnot(None)
    ).all()
    existing_roles = Role.query.filter_by(entity_id=entity.id).all()

    # Cohérent avec _do_sync : une activité est supprimée seulement si
    # ni son shape_id ni son nom ne sont dans la nouvelle carto, ou si
    # elle était classée comme renvoi et une vraie activité du même nom existe.
    removed_activities = [a.name for a in existing_acts
                          if (a.shape_id not in new_shape_ids and a.name not in new_labels)
                          or (a.shape_id in renvoi_sids_cr and a.name in new_labels)]
    removed_roles      = [r.name for r in existing_roles if r.name not in new_band_names]
    return {'removed_activities': removed_activities, 'removed_roles': removed_roles}


def _sync_carto_to_db(entity, diagram):
    """Full re-extraction: upsert activities, roles, links from the carto diagram."""
    try:
        _do_sync(entity, diagram)
    except Exception:
        db.session.rollback()
        raise


def _do_sync(entity, diagram):
    shapes      = diagram.get('shapes',      [])
    bands       = diagram.get('bands',       [])
    connections = diagram.get('connections', [])

    # Renvois (circles, type 'start-end') are NOT activities — they are visual
    # redirects that reference an existing activity by name to avoid back-arrows.
    act_shapes    = [s for s in shapes if s.get('type') in _ACTIVITY_TYPES]
    renvoi_shapes = [s for s in shapes if s.get('type') == 'start-end']
    renvoi_sids   = {str(s['id']) for s in renvoi_shapes}
    # Labels of real activities (used to safely clean up mis-classified renvois)
    proper_labels = {(s.get('label') or '').strip() for s in act_shapes if s.get('label')}

    # ── Activities — préservation des données par correspondance nom+shape_id ──
    # Stratégie : shape_id en priorité (même shape modifiée), puis nom (ré-import
    # VSDX avec nouveaux IDs). Les activités matchées gardent toutes leurs données
    # liées (compétences, savoirs, HSC, évaluations…) car on ne détruit pas la
    # ligne DB — on met juste à jour shape_id et/ou name si besoin.
    existing_carto = Activities.query.filter_by(entity_id=entity.id).filter(
        Activities.shape_id.isnot(None)
    ).all()
    # Prefer real (non-renvoi) activities when multiple entries share the same name
    existing_by_sid  = {a.shape_id: a for a in existing_carto}
    existing_by_name = {}
    for a in existing_carto:
        name = a.name or ''
        if name not in existing_by_name or a.shape_id not in renvoi_sids:
            existing_by_name[name] = a

    new_shape_ids = {str(s['id']) for s in act_shapes}
    new_labels    = set()
    shape_to_act  = {}

    for s in act_shapes:
        sid       = str(s['id'])
        label     = (s.get('label') or '').strip() or f"Activité {sid}"
        is_result = s.get('type') == 'special'
        subtype   = s.get('subtype') or 'normal'
        new_labels.add(label)

        if sid in existing_by_sid:
            act = existing_by_sid[sid]
            if act.name != label:                  act.name          = label
            if act.is_result != is_result:         act.is_result     = is_result
            if act.shape_subtype != subtype:       act.shape_subtype = subtype
        elif label in existing_by_name:
            act = existing_by_name[label]
            act.shape_id     = sid
            act.shape_subtype = subtype
            if act.is_result != is_result:         act.is_result     = is_result
        else:
            act = Activities(entity_id=entity.id, shape_id=sid,
                             name=label, is_result=is_result, shape_subtype=subtype)
            db.session.add(act)
        shape_to_act[sid] = act

    # Supprimer : absentes du shape_id ET du nom, OU anciennement classées comme renvoi
    # (shape_id correspond à un renvoi mais une vraie activité du même nom existe)
    acts_to_remove = [a for a in existing_carto
                      if (a.shape_id not in new_shape_ids and a.name not in new_labels)
                      or (a.shape_id in renvoi_sids and (a.name or '').strip() in proper_labels)]
    if acts_to_remove:
        remove_ids = [a.id for a in acts_to_remove if a.id]
        if remove_ids:
            # Supprimer les associations many-to-many
            db.session.execute(
                activity_roles.delete().where(activity_roles.c.activity_id.in_(remove_ids))
            )
            # Supprimer les enregistrements non couverts par le cascade ORM
            CompetencyEvaluation.query.filter(
                CompetencyEvaluation.activity_id.in_(remove_ids)
            ).delete(synchronize_session=False)
            TimeProjectLine.query.filter(
                TimeProjectLine.activity_id.in_(remove_ids)
            ).delete(synchronize_session=False)
            TimeRoleLine.query.filter(
                TimeRoleLine.activity_id.in_(remove_ids)
            ).delete(synchronize_session=False)
            TimeWeakness.query.filter(
                TimeWeakness.activity_id.in_(remove_ids)
            ).delete(synchronize_session=False)
            CrossCartoLiaison.query.filter(
                (CrossCartoLiaison.extco_activity_id.in_(remove_ids)) |
                (CrossCartoLiaison.origin_activity_id.in_(remove_ids))
            ).delete(synchronize_session=False)
            # Nullifier les FK optionnelles
            TimeAnalysis.query.filter(
                TimeAnalysis.activity_id.in_(remove_ids)
            ).update({TimeAnalysis.activity_id: None}, synchronize_session=False)
            Link.query.filter(
                Link.source_activity_id.in_(remove_ids)
            ).update({Link.source_activity_id: None}, synchronize_session=False)
            Link.query.filter(
                Link.target_activity_id.in_(remove_ids)
            ).update({Link.target_activity_id: None}, synchronize_session=False)
    for act in acts_to_remove:
        db.session.delete(act)

    db.session.flush()  # obtenir les IDs des nouvelles activités

    # ── Roles (bands) — upsert ───────────────────────────────────────────────
    existing_roles = {r.name: r for r in Role.query.filter_by(entity_id=entity.id).all()}
    new_band_names = {(b.get('label') or '').strip() for b in bands}
    band_to_role   = {}

    for band in bands:
        name = (band.get('label') or '').strip()
        if not name:
            continue
        if name in existing_roles:
            role = existing_roles[name]
        else:
            role = Role(entity_id=entity.id, name=name)
            db.session.add(role)
        band_to_role[band['id']] = role

    roles_to_remove = [role for name, role in existing_roles.items() if name not in new_band_names]
    if roles_to_remove:
        remove_role_ids = [r.id for r in roles_to_remove if r.id]
        if remove_role_ids:
            db.session.execute(
                activity_roles.delete().where(activity_roles.c.role_id.in_(remove_role_ids))
            )
            db.session.execute(
                task_roles.delete().where(task_roles.c.role_id.in_(remove_role_ids))
            )
            UserRole.query.filter(
                UserRole.role_id.in_(remove_role_ids)
            ).delete(synchronize_session=False)
            TimeRoleAnalysis.query.filter(
                TimeRoleAnalysis.role_id.in_(remove_role_ids)
            ).delete(synchronize_session=False)
            TimeAnalysis.query.filter(
                TimeAnalysis.role_id.in_(remove_role_ids)
            ).update({TimeAnalysis.role_id: None}, synchronize_session=False)
    for role in roles_to_remove:
        db.session.delete(role)

    db.session.flush()

    # ── Activity-Role associations — diff (pas de delete-all + insert-all) ───
    act_ids = [a.id for a in shape_to_act.values() if a.id]
    # Lire l'état actuel une seule fois
    cur_ar = {}
    if act_ids:
        rows = db.session.execute(
            activity_roles.select().where(activity_roles.c.activity_id.in_(act_ids))
        ).fetchall()
        for row in rows:
            cur_ar[row.activity_id] = row.role_id

    # Calculer le nouvel état
    new_ar = {}
    for s in act_shapes:
        sid = str(s['id'])
        act = shape_to_act.get(sid)
        if not act or not act.id:
            continue
        mid_y = s.get('y', 0) + s.get('h', 0) / 2
        band  = _get_band_for_y(bands, mid_y)
        if not band:
            continue
        role = band_to_role.get(band['id'])
        if role and role.id:
            new_ar[act.id] = role.id

    # Supprimer uniquement les associations supprimées ou modifiées
    to_delete_ar = [aid for aid, rid in cur_ar.items()
                    if aid not in new_ar or new_ar[aid] != rid]
    if to_delete_ar:
        db.session.execute(
            activity_roles.delete().where(activity_roles.c.activity_id.in_(to_delete_ar))
        )
    # Insérer uniquement les nouvelles associations ou celles qui ont changé
    for aid, rid in new_ar.items():
        if aid not in cur_ar or cur_ar[aid] != rid:
            db.session.execute(
                activity_roles.insert().values(activity_id=aid, role_id=rid, status='garant')
            )

    # ── Links — diff (pas de delete-all + insert-all) ────────────────────────
    existing_links = {
        (lk.source_activity_id, lk.target_activity_id): lk
        for lk in Link.query.filter_by(entity_id=entity.id).filter(
            Link.source_activity_id.isnot(None),
            Link.target_activity_id.isnot(None),
            Link.cross_carto_liaison_id.is_(None),
        ).all()
    }

    # Résolution renvoi → activité réelle (par correspondance de label)
    # Un renvoi partage exactement le même nom que l'activité qu'il référence.
    renvoi_to_act = {}
    for s in renvoi_shapes:
        label = (s.get('label') or '').strip()
        if label:
            real_act = next((act for act in shape_to_act.values() if act.name == label), None)
            if real_act:
                renvoi_to_act[str(s['id'])] = real_act

    # Lookup combiné : shape_id → activité (inclut la résolution des renvois)
    sid_to_act = {**shape_to_act, **renvoi_to_act}

    # Map decision shape_id → upstream activity (for diamond Oui/Non routing)
    shape_by_sid = {str(s['id']): s for s in shapes}
    decision_upstream = {}
    for conn in connections:
        to_sid = str(conn.get('toId', ''))
        to_shape = shape_by_sid.get(to_sid)
        if to_shape and to_shape.get('type') == 'decision':
            from_act = sid_to_act.get(str(conn.get('fromId', '')))
            if from_act and from_act.id:
                decision_upstream[to_sid] = from_act

    # new_links maps (src_id, tgt_id) → (description, choice_label)
    new_links = {}
    for conn in connections:
        from_sid = str(conn.get('fromId', ''))
        to_sid   = str(conn.get('toId',   ''))
        from_shape = shape_by_sid.get(from_sid)
        to_shape   = shape_by_sid.get(to_sid)

        if from_shape and from_shape.get('type') == 'decision':
            # Outgoing from decision diamond → trace back to upstream activity
            from_act = decision_upstream.get(from_sid)
            to_act   = sid_to_act.get(to_sid)
        elif to_shape and to_shape.get('type') == 'decision':
            # Incoming to decision diamond → handled via outgoing, skip here
            continue
        else:
            from_act = sid_to_act.get(from_sid)
            to_act   = sid_to_act.get(to_sid)

        if not from_act or not to_act or not from_act.id or not to_act.id:
            continue
        if from_act.id == to_act.id:
            continue

        label       = (conn.get('label') or '').strip() or None
        choice_raw  = conn.get('choiceLabel') or None
        # Normalise VSDX labels ('Oui'/'Non'/'Yes'/'No') into canonical form
        _CHOICE_MAP = {'oui': 'Oui', 'non': 'Non', 'yes': 'Oui', 'no': 'Non'}
        if choice_raw:
            choice_label = _CHOICE_MAP.get(choice_raw.strip().lower(), choice_raw)
        elif from_shape and from_shape.get('type') == 'decision' and label:
            choice_label = _CHOICE_MAP.get(label.strip().lower())
            if choice_label:
                label = None  # absorbed into choice_label
        else:
            choice_label = None

        new_links[(from_act.id, to_act.id)] = (label, choice_label)

    for key, lk in existing_links.items():
        if key not in new_links:
            db.session.delete(lk)
        else:
            label, choice_label = new_links[key]
            if lk.description != label:
                lk.description = label
            if getattr(lk, 'choice_label', None) != choice_label:
                lk.choice_label = choice_label

    for key, (label, choice_label) in new_links.items():
        if key not in existing_links:
            db.session.add(Link(
                entity_id=entity.id,
                source_activity_id=key[0],
                target_activity_id=key[1],
                type='flux',
                description=label,
                choice_label=choice_label,
            ))

    # ── Cross-carto liaison propagation ──────────────────────────────────────
    # Pour chaque activité hachurée (extco) ayant une liaison officialisée,
    # on reporte ses connexions vers l'activité d'origine dans l'autre entité.
    extco_act_ids = {a.id for a in shape_to_act.values()
                     if a.shape_subtype == 'extco' and a.id}
    if extco_act_ids:
        liaisons = CrossCartoLiaison.query.filter(
            CrossCartoLiaison.extco_activity_id.in_(list(extco_act_ids)),
            CrossCartoLiaison.extco_entity_id == entity.id,
            CrossCartoLiaison.is_active.is_(True)
        ).all()
        if liaisons:
            db.session.flush()  # ensure new links are in DB before propagation
            act_id_to_name = {a.id: a.name for a in shape_to_act.values() if a.id}
            active_entity_name = entity.name or "Entité liée"
            for liaison in liaisons:
                # Delete previously propagated links for this liaison
                Link.query.filter_by(
                    entity_id=liaison.origin_entity_id,
                    cross_carto_liaison_id=liaison.id
                ).delete()
                # Re-create from current carto state
                extco_id = liaison.extco_activity_id
                for (src_id, tgt_id), (label, _cl) in new_links.items():
                    if src_id == extco_id:
                        other_name = act_id_to_name.get(tgt_id, label or "?")
                        db.session.add(Link(
                            entity_id=liaison.origin_entity_id,
                            source_activity_id=liaison.origin_activity_id,
                            target_activity_id=None,
                            type='flux',
                            description=other_name,
                            cross_carto_liaison_id=liaison.id,
                            cross_carto_label=active_entity_name
                        ))
                    elif tgt_id == extco_id:
                        other_name = act_id_to_name.get(src_id, label or "?")
                        db.session.add(Link(
                            entity_id=liaison.origin_entity_id,
                            source_activity_id=None,
                            target_activity_id=liaison.origin_activity_id,
                            type='flux',
                            description=other_name,
                            cross_carto_liaison_id=liaison.id,
                            cross_carto_label=active_entity_name
                        ))

    db.session.commit()


# ─────────────────────────────────────────────
# API SAVE / LOAD / LIST / DELETE
# ─────────────────────────────────────────────

@cartography_editor_bp.route("/api/save", methods=["POST"])
def api_save():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    data    = request.get_json(force=True)
    diagram = data.get("diagram", data)  # accepte {diagram: ...} ou le state direct

    entity.optiqcarto_data = json.dumps(diagram, ensure_ascii=False)
    db.session.commit()

    # Re-extract activities / roles / links from the saved diagram
    sync_error = None
    try:
        _sync_carto_to_db(entity, diagram)
    except Exception as exc:
        import traceback
        sync_error = str(exc)
        traceback.print_exc()

    resp = {"ok": True, "name": entity.name or f"entity_{entity.id}"}
    if sync_error:
        resp["sync_warning"] = sync_error
    return jsonify(resp)


@cartography_editor_bp.route("/api/resync/<int:entity_id>", methods=["POST"])
def api_resync(entity_id):
    """Force re-sync d'une entité depuis sa carto stockée (nettoyage doublons, renvois…)."""
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403
    user_id = session.get("user_id")
    entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
    if not entity:
        return jsonify({"error": "Entité introuvable"}), 404
    if not entity.optiqcarto_data:
        return jsonify({"error": "Aucune cartographie stockée pour cette entité"}), 400
    try:
        diagram = json.loads(entity.optiqcarto_data)
        _sync_carto_to_db(entity, diagram)
        return jsonify({"ok": True, "entity": entity.name})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@cartography_editor_bp.route("/api/save-diff", methods=["POST"])
def api_save_diff():
    """Return what would be removed if the given diagram is saved (no commit)."""
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    if not entity.optiqcarto_data:
        return jsonify({"removed_activities": [], "removed_roles": []})

    data    = request.get_json(force=True)
    diagram = data.get("diagram", data)
    return jsonify(_compute_removals(entity, diagram))


@cartography_editor_bp.route("/api/load/<name>")
def api_load(name):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    # Chercher l'entité par nom d'abord (permet le preview inter-entités),
    # puis fallback sur l'entité active de la session.
    user_id = session.get("user_id")
    entity = None
    if user_id and name:
        entity = Entity.query.filter_by(name=name, owner_id=user_id).first()
    if not entity:
        entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    if not entity.optiqcarto_data:
        return jsonify({"error": "Introuvable"}), 404

    return jsonify(json.loads(entity.optiqcarto_data))


# ─────────────────────────────────────────────
# CALQUES
# ─────────────────────────────────────────────

@cartography_editor_bp.route("/api/calques")
def api_calques_list():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403
    entity = _get_active_entity()
    if not entity:
        return jsonify([])
    calques = CartoCalque.query.filter_by(entity_id=entity.id).order_by(CartoCalque.created_at).all()
    return jsonify([{"id": c.id, "name": c.name} for c in calques])


@cartography_editor_bp.route("/api/calques", methods=["POST"])
def api_calques_create():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403
    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Nom requis"}), 400
    state = data.get("state")
    if not state:
        return jsonify({"error": "État requis"}), 400
    cal = CartoCalque(entity_id=entity.id, name=name, state_json=json.dumps(state, ensure_ascii=False))
    db.session.add(cal)
    db.session.commit()
    return jsonify({"ok": True, "id": cal.id, "name": cal.name})


@cartography_editor_bp.route("/api/calques/<int:cal_id>")
def api_calques_load(cal_id):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403
    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Non autorisé"}), 403
    cal = CartoCalque.query.filter_by(id=cal_id, entity_id=entity.id).first()
    if not cal:
        return jsonify({"error": "Introuvable"}), 404
    return jsonify(json.loads(cal.state_json))


@cartography_editor_bp.route("/api/calques/<int:cal_id>", methods=["PUT"])
def api_calques_update(cal_id):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403
    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400
    cal = CartoCalque.query.filter_by(id=cal_id, entity_id=entity.id).first()
    if not cal:
        return jsonify({"error": "Introuvable"}), 404
    data = request.get_json(force=True)
    if "name" in data and data["name"].strip():
        cal.name = data["name"].strip()
    if "state" in data:
        cal.state_json = json.dumps(data["state"], ensure_ascii=False)
    db.session.commit()
    return jsonify({"ok": True})


@cartography_editor_bp.route("/api/calques/<int:cal_id>", methods=["DELETE"])
def api_calques_delete(cal_id):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403
    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Non autorisé"}), 403
    cal = CartoCalque.query.filter_by(id=cal_id, entity_id=entity.id).first()
    if not cal:
        return jsonify({"error": "Introuvable"}), 404
    db.session.delete(cal)
    db.session.commit()
    return jsonify({"ok": True})


@cartography_editor_bp.route("/api/calques/<int:cal_id>/apply", methods=["POST"])
def api_calques_apply(cal_id):
    """Active un calque : sync DB avec l'état du calque + stocke en session."""
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403
    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Non autorisé"}), 403
    cal = CartoCalque.query.filter_by(id=cal_id, entity_id=entity.id).first()
    if not cal:
        return jsonify({"error": "Introuvable"}), 404
    try:
        diagram = json.loads(cal.state_json)
        _sync_carto_to_db(entity, diagram)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    session['active_calque_id']   = cal.id
    session['active_calque_name'] = cal.name
    return jsonify({"ok": True})


@cartography_editor_bp.route("/api/calques/deactivate", methods=["POST"])
def api_calques_deactivate():
    """Désactive le calque actif : resync DB avec la carto de base."""
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403
    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Non autorisé"}), 403
    session.pop('active_calque_id',   None)
    session.pop('active_calque_name', None)
    if entity.optiqcarto_data:
        try:
            diagram = json.loads(entity.optiqcarto_data)
            _sync_carto_to_db(entity, diagram)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
    return jsonify({"ok": True})


@cartography_editor_bp.route("/api/list")
def api_list():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify([])

    if entity.optiqcarto_data:
        return jsonify([entity.name or f"entity_{entity.id}"])
    return jsonify([])


@cartography_editor_bp.route("/api/delete/<name>", methods=["DELETE"])
def api_delete(name):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    entity.optiqcarto_data = None
    db.session.commit()

    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# SERVIR LE VSDX EXISTANT (pour auto-import migration)
# ─────────────────────────────────────────────

@cartography_editor_bp.route("/api/vsdx")
def api_vsdx():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    path = _vsdx_path(entity)
    if not path:
        return jsonify({"error": "Aucun fichier VSDX"}), 404

    return send_file(path, mimetype="application/octet-stream",
                     download_name="connections.vsdx")


@cartography_editor_bp.route("/api/vsdx-compare", methods=["POST"])
def api_vsdx_compare():
    """Compare un fichier VSDX uploadé avec la carto sauvegardée dans notre outil."""
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    if not entity.optiqcarto_data:
        return jsonify({"error": "Aucune cartographie sauvegardée pour cette entité"}), 404

    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".vsdx"):
        return jsonify({"error": "Format invalide (attendu .vsdx)"}), 400

    tmp = tempfile.NamedTemporaryFile(suffix=".vsdx", delete=False)
    try:
        f.save(tmp.name)
        tmp.close()

        from Code.routes.vsdx_conection_parser import (
            VsdxConnectionParser,
            normalize_activity_name,
        )

        parser = VsdxConnectionParser(tmp.name)
        connections, errors = parser.parse()

        vsdx_activities = set(
            normalize_activity_name(a) for a in parser.get_unique_activities()
        )
        vsdx_connections = set(
            (normalize_activity_name(c["source_name"]), normalize_activity_name(c["target_name"]))
            for c in connections
        )

        carto = json.loads(entity.optiqcarto_data)
        carto_shapes = carto.get("shapes", [])
        carto_conns = carto.get("connections", [])

        shape_labels = {s["id"]: (s.get("label") or "").strip() for s in carto_shapes}

        # Map norm_label → type pour les activités (pour diagnostic des écarts)
        norm_to_type = {}
        for s in carto_shapes:
            if s.get("type") != "decision" and (s.get("label") or "").strip():
                norm = normalize_activity_name(s.get("label", ""))
                # Si la même étiquette existe en process et start-end, on garde process
                existing = norm_to_type.get(norm)
                if not existing or s.get("type") == "process":
                    norm_to_type[norm] = s.get("type", "process")

        carto_activities = set(norm_to_type.keys())

        carto_connections = set()
        for c in carto_conns:
            fl = shape_labels.get(c.get("fromId"), "")
            tl = shape_labels.get(c.get("toId"), "")
            if fl and tl:
                carto_connections.add((normalize_activity_name(fl), normalize_activity_name(tl)))

        matched_act = carto_activities & vsdx_activities
        only_carto_act = sorted(carto_activities - vsdx_activities)
        only_vsdx_act = sorted(vsdx_activities - carto_activities)

        # Comptage par type des shapes de notre carto pour expliquer l'écart avec le VSDX
        type_counts = {}
        for s in carto_shapes:
            t = s.get("type", "process")
            type_counts[t] = type_counts.get(t, 0) + 1

        matched_conn = carto_connections & vsdx_connections
        only_carto_conn = sorted(carto_connections - vsdx_connections)
        only_vsdx_conn = sorted(vsdx_connections - carto_connections)

        # Bidirectional: extra activities/connections in carto also reduce compatibility
        ref_act = max(len(vsdx_activities), len(carto_activities), 1)
        ref_conn = max(len(vsdx_connections), len(carto_connections), 1)
        compat_act = round(len(matched_act) / ref_act * 100)
        compat_conn = round(len(matched_conn) / ref_conn * 100)
        compat_global = round(
            (len(matched_act) + len(matched_conn))
            / max(ref_act + ref_conn, 1)
            * 100
        )

        return jsonify({
            "compatibility": {
                "global": compat_global,
                "activities": compat_act,
                "connections": compat_conn,
            },
            "counts": {
                "vsdx_activities": len(vsdx_activities),
                "carto_activities": len(carto_activities),
                "matched_activities": len(matched_act),
                "extra_activities": len(only_carto_act),   # in carto but not in VSDX
                "missing_activities": len(only_vsdx_act),  # in VSDX but not in carto
                "vsdx_connections": len(vsdx_connections),
                "carto_connections": len(carto_connections),
                "matched_connections": len(matched_conn),
                "extra_connections": len(only_carto_conn),
                "missing_connections": len(only_vsdx_conn),
                # Détail par type des shapes dans notre carto (aide à expliquer l'écart)
                "carto_shapes_by_type": type_counts,
            },
            "differences": {
                "activities_only_in_carto": [
                    {"label": lbl, "type": norm_to_type.get(lbl, "process")}
                    for lbl in only_carto_act
                ],
                "activities_only_in_vsdx": only_vsdx_act,
                "connections_only_in_carto": [[a, b] for a, b in only_carto_conn],
                "connections_only_in_vsdx": [[a, b] for a, b in only_vsdx_conn],
            },
            "parse_errors": errors,
        })
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@cartography_editor_bp.route("/api/architect", methods=["POST"])
def api_architect():
    """Réorganise les formes via IA (OpenAI ou Anthropic Claude) et retourne les nouvelles positions."""
    data = request.get_json(silent=True) or {}
    state = data.get("state", {})
    shapes = state.get("shapes", [])
    bands = state.get("bands", [])
    connections = state.get("connections", [])

    if not shapes:
        return jsonify({"error": "Aucune forme à organiser"}), 400

    # Construire un résumé compact pour le prompt
    band_summary = [
        {"id": b.get("id"), "label": b.get("label", ""), "height": b.get("height", 220)}
        for b in bands
    ]
    shape_summary = [
        {
            "id": s.get("id"),
            "label": s.get("label", ""),
            "type": s.get("type", "process"),
            "w": s.get("w", 170),
            "h": s.get("h", 70),
            "band_label": next(
                (b["label"] for b in band_summary if b["id"] == _get_band_for_y(bands, s.get("y", 0) + s.get("h", 70) / 2)),
                "?"
            ),
        }
        for s in shapes
    ]
    conn_summary = [
        {
            "from": next((s["label"] for s in shape_summary if s["id"] == c.get("fromId")), "?"),
            "to":   next((s["label"] for s in shape_summary if s["id"] == c.get("toId")),   "?"),
        }
        for c in connections
    ]

    BAND_Y0 = -200
    INDEX_W = 140
    band_y_info = []
    y = BAND_Y0
    for b in bands:
        band_y_info.append({"label": b.get("label", ""), "y_start": y, "y_end": y + b.get("height", 220)})
        y += b.get("height", 220)

    system_prompt = (
        "Tu es un expert en architecture de processus métier. "
        "Tu dois repositionner les formes d'un diagramme de flux pour maximiser la lisibilité : "
        "pas de chevauchement, connexions courtes, alignement logique gauche→droite dans chaque bande. "
        "Réponds UNIQUEMENT avec un JSON valide : {\"positions\": [{\"id\": <int>, \"x\": <int>, \"y\": <int>}, ...]}. "
        "Aucun texte avant ou après le JSON."
    )

    user_prompt = (
        f"Bandes (horizontal swimlanes, y croissant) :\n{json.dumps(band_y_info, ensure_ascii=False)}\n\n"
        f"Contraintes : x minimum = {INDEX_W + 4} (réservé à l'index), "
        f"x maximum indicatif = 3000. Les formes doivent rester dans leur bande (y_start..y_end). "
        f"Laisse au moins 20px de marge avec les bords de la bande verticalement.\n\n"
        f"Formes à positionner :\n{json.dumps(shape_summary, ensure_ascii=False)}\n\n"
        f"Connexions (pour guider le flux gauche→droite) :\n{json.dumps(conn_summary, ensure_ascii=False)}\n\n"
        "Retourne les nouvelles coordonnées (x, y) pour chaque forme. "
        "Utilise les id numériques du tableau formes."
    )

    def _extract_json(raw):
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    # Essai 1 : OpenAI (utilise OPENAI_API_KEY depuis l'environnement, comme chatbot.py)
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI as _OAI
            client = _OAI()  # lit OPENAI_API_KEY automatiquement
            response = client.chat.completions.create(
                model=os.environ.get("OPENAI_CHATBOT_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            return jsonify(_extract_json(response.choices[0].message.content))
        except Exception as e:
            return jsonify({"error": f"Erreur OpenAI : {e}"}), 500

    # Essai 2 : Anthropic Claude (ANTHROPIC_API_KEY ou ANTHROPIC_KEY)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_KEY")
    if anthropic_key:
        try:
            import anthropic as _ant
            client = _ant.Anthropic(api_key=anthropic_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return jsonify(_extract_json(msg.content[0].text))
        except Exception as e:
            return jsonify({"error": f"Erreur Anthropic : {e}"}), 500

    return jsonify({"error": "Aucune clé IA configurée (OPENAI_API_KEY ou ANTHROPIC_KEY)"}), 500


@cartography_editor_bp.route("/api/liaisons", methods=["GET"])
def get_liaisons():
    """Retourne les liaisons cross-carto actives pour l'entité courante.
    Accepte ?entity_id=X pour le viewer en lecture seule."""
    user_id = session.get("user_id")
    entity_id = request.args.get("entity_id", type=int) or session.get("active_entity_id")
    if not entity_id or not user_id:
        return jsonify([])
    # Auth: entity must belong to current user
    if not Entity.query.filter_by(id=entity_id, owner_id=user_id).first():
        return jsonify([])
    liaisons = CrossCartoLiaison.query.filter_by(
        extco_entity_id=entity_id, is_active=True
    ).all()
    result = []
    for l in liaisons:
        origin_entity = Entity.query.get(l.origin_entity_id)
        extco_act = Activities.query.get(l.extco_activity_id)
        result.append({
            "id": l.id,
            "extco_activity_id": l.extco_activity_id,
            "extco_shape_id": extco_act.shape_id if extco_act else None,
            "extco_activity_name": extco_act.name if extco_act else None,
            "origin_entity_id": l.origin_entity_id,
            "origin_entity_name": origin_entity.name if origin_entity else None,
            "display_label": l.display_label,
        })
    return jsonify(result)


@cartography_editor_bp.route("/api/liaisons/<int:liaison_id>", methods=["PATCH"])
def patch_liaison(liaison_id):
    """Met à jour le display_label d'une liaison."""
    entity_id = session.get("active_entity_id")
    user_id = session.get("user_id")
    if not entity_id or not user_id:
        return jsonify({"error": "Non autorisé"}), 403
    liaison = CrossCartoLiaison.query.filter_by(
        id=liaison_id, extco_entity_id=entity_id, is_active=True
    ).first()
    if not liaison:
        return jsonify({"error": "Liaison introuvable"}), 404
    data = request.get_json(force=True) or {}
    liaison.display_label = data.get("display_label") or None
    db.session.commit()
    return jsonify({"ok": True, "display_label": liaison.display_label})
