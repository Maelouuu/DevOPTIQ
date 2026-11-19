import os
import sys
from vsdx import VisioFile

# Pour pouvoir importer Code.extensions et Code.models.models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from Code.extensions import db
from Code.models.models import Activities, Data, Link

# Calques Visio gérés
LAYER_MAPPING = {
    "1": "Activity",    # rectangle normal
    "9": "N link",      # ligne pointillée => nourrissante
    "10": "T link",     # ligne pleine => déclenchante
    "6": "Result",      # drapeau => activité de résultat
    "8": "Return"       # rond => retour
}

# Calques à ignorer
IGNORE_LAYERS = ["légende", "Color"]

# ------------------- Variables globales -------------------
# Elles sont utilisées par process_visio_file et print_summary
activity_mapping = {}
data_mapping = {}
return_mapping = {}  # retours

connectors_list = []  # On y stocke toutes les infos des connecteurs (déclenchants/nourrissants)

# Ces listes sont relues par print_summary()
link_summaries = []     # (data_name, data_type, source_name, target_name)
rename_summaries = []   # (old_name, new_name)

# Entité ciblée par l'import en cours. None = mode historique (script autonome,
# base mono-entité). Depuis la route, l'import est TOUJOURS borné à l'entité
# active : sans ce périmètre, il vidait la table `links` de toutes les entités
# et supprimait leurs activités issues d'un Visio.
_current_entity_id = None


def _scoped(query, model):
    if _current_entity_id is None:
        return query
    return query.filter(model.entity_id == _current_entity_id)


def _purge_links():
    if _current_entity_id is None:
        Link.query.delete()
        return
    act_ids = [a.id for a in Activities.query.filter_by(entity_id=_current_entity_id).all()]
    q = Link.query.filter(db.or_(
        Link.entity_id == _current_entity_id,
        Link.source_activity_id.in_(act_ids),
        Link.target_activity_id.in_(act_ids),
    ))
    q.delete(synchronize_session=False)


def create_app():
    """Exécuter ce script directement (standalone)."""
    from flask import Flask
    app = Flask(__name__)
    instance_path = os.path.abspath(os.path.join("Code", "instance"))
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
    db_path = os.path.join(instance_path, "optiq.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def process_visio_file(vsdx_path, entity_id=None):
    """
    1) Parcours toutes les pages / formes du VSDX
    2) Gère creation / maj / suppression de Activities/Data + fusion retours
    3) Vide la table 'links'
    4) Reconstruit tous les liens depuis 'connectors_list'
    5) Nettoie orphelins
    """
    if not os.path.exists(vsdx_path):
        print(f"ERREUR : Fichier Visio introuvable : {vsdx_path}")
        return

    print(f"INFO : Démarrage de l’import depuis {vsdx_path}")

    global _current_entity_id
    _current_entity_id = entity_id

    # Réinit des globales
    activity_mapping.clear()
    data_mapping.clear()
    return_mapping.clear()
    connectors_list.clear()
    link_summaries.clear()
    rename_summaries.clear()

    # Parcours du visio
    with VisioFile(vsdx_path) as visio:
        for page in visio.pages:
            print(f"INFO : Analyse de la page : {page.name}")
            for shape in page.all_shapes:
                process_shape(shape)

    # Suppression des activités et data obsolètes
    del_act_count = remove_activities_not_in_new_mapping()
    del_data_count = remove_data_not_in_new_mapping()

    # On vide la table 'links' (celle de l'entité ciblée)
    _purge_links()
    db.session.commit()
    print("INFO : Table 'links' vidée, on va la reconstruire à partir de connectors_list...")

    # Reconstruire la table des liens
    rebuild_links_from_connectors()

    # Nettoyage final orphelins
    cleanup_orphan_links()

    # Récap
    print("INFO : Import terminé.")
    print(f"      Activités ajoutées/mises à jour : {len(activity_mapping)} ; supprimées : {del_act_count}")
    print(f"      Data (connecteurs/retours) totaux : {len(data_mapping)+len(return_mapping)} ; supprimés : {del_data_count}")


def process_shape(shape):
    """Oriente selon le calque (Activity, Return, T link, N link, etc.)."""
    layer = get_layer(shape)
    if not layer:
        return
    if layer.lower() in [x.lower() for x in IGNORE_LAYERS]:
        return

    if layer == "Activity":
        add_or_update_activity(shape, is_result=False)
    elif layer == "Result":
        add_or_update_activity(shape, is_result=True)
    elif layer == "Return":
        add_or_update_return(shape)
    elif layer in ("T link", "N link"):
        store_connector_info(shape, layer)
    else:
        print(f"INFO : Calque '{layer}' non traité => forme '{shape.text or '??'}' ignorée.")


def add_or_update_activity(shape, is_result=False):
    key = standardize_id(shape.ID)
    txt = shape.text.strip() if shape.text else ("Résultat sans nom" if is_result else "Activité sans nom")

    fill = get_fill_pattern(shape)
    if fill and fill != "1":
        is_result = True

    act = _scoped(Activities.query.filter_by(shape_id=key), Activities).first()
    if act:
        changed = False
        old_name = act.name
        if old_name != txt:
            act.name = txt
            rename_summaries.append((old_name, txt))
            changed = True
        if act.is_result != is_result:
            act.is_result = is_result
            changed = True
        if changed:
            print(f"INFO : Activity (ID={act.id}) maj => name='{txt}', is_result={is_result}")
        else:
            print(f"INFO : Activity (ID={act.id}) déjà existante, pas de modif.")
    else:
        new_a = Activities(name=txt, is_result=is_result, shape_id=key,
                           entity_id=_current_entity_id)
        db.session.add(new_a)
        db.session.flush()
        print(f"INFO : Activity créée => '{txt}' (ID={new_a.id}, shape_id={key}, is_result={is_result})")
        act = new_a

    activity_mapping[key] = act.id
    db.session.commit()


def add_or_update_return(shape):
    """
    Gère une forme 'Return' => Data(type='Retour').
    1) Crée/MAJ
    2) Fusion si d’autres Retours ont le même nom
    """
    key = standardize_id(shape.ID)
    txt = (shape.text or "").strip() or "Retour sans nom"

    d = _scoped(Data.query.filter_by(shape_id=key, type="Retour"), Data).first()
    if d:
        old = d.name
        if old != txt:
            d.name = txt
            rename_summaries.append((old, txt))
            db.session.commit()
            print(f"INFO : Return (ID={d.id}) renommé '{old}' => '{txt}'")
    else:
        d = Data(name=txt, type="Retour", shape_id=key, entity_id=_current_entity_id)
        db.session.add(d)
        db.session.flush()
        print(f"INFO : Return créé => '{txt}' (ID={d.id}, shape_id={key})")

    return_mapping[key] = d.id
    db.session.commit()

    # Fusion
    unify_retours(d)


def unify_retours(d):
    """Si d’autres Data(type='Retour') ont le même .name, on supprime (sauf d)."""
    keeper_id = d.id
    duplicates = _scoped(Data.query.filter(
        Data.type == "Retour",
        Data.name == d.name,
        Data.id != keeper_id
    ), Data).all()
    for dupe in duplicates:
        print(f"INFO : Fusion retours => supprime Return ID={dupe.id} shape_id={dupe.shape_id}")
        db.session.delete(dupe)
    db.session.commit()


def store_connector_info(shape, layer):
    """
    On stocke en mémoire les connecteurs (data), 
    puis on créera les liens plus tard dans rebuild_links_from_connectors().
    """
    key = standardize_id(shape.ID)
    txt = (shape.text or "").strip() or "Donnée sans nom"
    data_type = "déclenchante" if layer == "T link" else "nourrissante"

    d = _scoped(Data.query.filter_by(shape_id=key, type=data_type), Data).first()
    if d:
        old = d.name
        if old != txt:
            d.name = txt
            rename_summaries.append((old, txt))
            db.session.commit()
            print(f"INFO : Connector rename: (ID={d.id}) '{old}' => '{txt}'")
    else:
        d = Data(name=txt, type=data_type, shape_id=key, layer=layer,
                 entity_id=_current_entity_id)
        db.session.add(d)
        db.session.flush()
        print(f"INFO : Connector créé => '{txt}' (ID={d.id}, shape_id={key})")

    data_mapping[key] = d.id
    db.session.commit()

    # Récupère from_id / to_id
    conns = analyze_connections(shape)
    from_id = conns.get("from_id")
    to_id = conns.get("to_id")

    connectors_list.append({
        "data_id": d.id,
        "data_name": d.name,
        "data_type": data_type,
        "from_raw": from_id,
        "to_raw": to_id
    })


def remove_activities_not_in_new_mapping():
    existing_acts = _scoped(Activities.query.filter(Activities.shape_id.isnot(None)), Activities).all()
    count = 0
    for act in existing_acts:
        if act.shape_id not in activity_mapping:
            print(f"INFO : Suppression Activity '{act.name}' (ID={act.id}, shape_id={act.shape_id})")
            db.session.delete(act)
            count += 1
    db.session.commit()
    return count


def remove_data_not_in_new_mapping():
    existing_data = _scoped(Data.query.filter(Data.shape_id.isnot(None)), Data).all()
    count = 0
    for d in existing_data:
        sid = d.shape_id
        if sid not in data_mapping and sid not in return_mapping:
            print(f"INFO : Suppression data '{d.name}' (ID={d.id}, type={d.type}, shape_id={sid})")
            db.session.delete(d)
            count += 1
    db.session.commit()
    return count


def rebuild_links_from_connectors():
    """
    Pour chaque connecteur stocké dans connectors_list, on crée un Link
    (source=..., target=..., description=data_name) 
    si from/to pointent vers des entités valides (Activity ou Data).
    """
    for c in connectors_list:
        data_id = c["data_id"]
        data_name = c["data_name"]
        data_type = c["data_type"]
        from_raw = c["from_raw"]
        to_raw = c["to_raw"]

        if not from_raw or not to_raw or (from_raw == to_raw):
            print(f"INFO : Connecteur partiel/boucle => '{data_name}', on ignore.")
            continue

        (skind, sid) = resolve_visio_id(from_raw)
        (tkind, tid) = resolve_visio_id(to_raw)

        if not sid or not tid or sid == tid:
            print(f"INFO : Connecteur impossible => '{data_name}' => on ignore")
            continue

        create_single_link(data_id, data_name, data_type, skind, sid, tkind, tid)


def create_single_link(data_id, data_name, data_type, skind, sid, tkind, tid):
    """
    Crée un Link reliant source(activity/data) => target(activity/data).
    """
    s_name = get_entity_name(sid, skind)
    t_name = get_entity_name(tid, tkind)

    new_link = Link(type=data_type, description=data_name, entity_id=_current_entity_id)

    if skind == 'activity':
        new_link.source_activity_id = sid
    else:
        new_link.source_data_id = sid

    if tkind == 'activity':
        new_link.target_activity_id = tid
    else:
        new_link.target_data_id = tid

    # Vérif duplication
    q = Link.query.filter_by(type=data_type, description=data_name)
    if new_link.source_activity_id:
        q = q.filter_by(source_activity_id=new_link.source_activity_id)
    else:
        q = q.filter_by(source_data_id=new_link.source_data_id)

    if new_link.target_activity_id:
        q = q.filter_by(target_activity_id=new_link.target_activity_id)
    else:
        q = q.filter_by(target_data_id=new_link.target_data_id)

    if q.first():
        print(f"INFO : Lien déjà existant => {s_name} -> {t_name} (data='{data_name}') => on ignore")
        return

    db.session.add(new_link)
    db.session.flush()

    link_summaries.append((data_name, data_type, s_name, t_name))
    print(f"INFO : Lien créé => {s_name} -> {t_name} (data='{data_name}')")


def cleanup_orphan_links():
    """
    Si un lien pointe sur un ID inexistant, on le supprime.
    """
    all_links = Link.query.all()
    removed = 0
    for lk in all_links:
        remove_this = False
        if lk.source_activity_id and not Activities.query.get(lk.source_activity_id):
            remove_this = True
        if lk.source_data_id and not Data.query.get(lk.source_data_id):
            remove_this = True
        if lk.target_activity_id and not Activities.query.get(lk.target_activity_id):
            remove_this = True
        if lk.target_data_id and not Data.query.get(lk.target_data_id):
            remove_this = True
        if remove_this:
            print(f"INFO : Suppression lien orphelin ID={lk.id}, desc='{lk.description}'")
            db.session.delete(lk)
            removed += 1

    if removed > 0:
        db.session.commit()
        print(f"INFO : {removed} lien(s) orphelin(s) supprimé(s).")


def get_layer(shape):
    cell = shape.xml.find(".//{*}Cell[@N='LayerMember']")
    if cell is not None:
        val = cell.get("V")
        return LAYER_MAPPING.get(val, val)
    return None


def get_fill_pattern(shape):
    cell = shape.xml.find(".//{*}Cell[@N='FillPattern']")
    if cell is not None:
        return cell.get("V")
    return None


def analyze_connections(shape):
    """Retourne {'from_id':..., 'to_id':...}"""
    conns = {"from_id": None, "to_id": None}
    for cell in shape.xml.findall(".//{*}Cell"):
        n = cell.get("N")
        f = cell.get("F")
        if n == "BeginX":
            conns["from_id"] = extract_shape_id(f)
        elif n == "EndX":
            conns["to_id"] = extract_shape_id(f)
    return conns


def extract_shape_id(f_val):
    if f_val and "Sheet." in f_val:
        try:
            return int(f_val.split("Sheet.")[1].split("!")[0])
        except:
            return None
    return None


def resolve_visio_id(raw_id):
    """
    Convertit l'int 'raw_id' en (kind, db_id).
    S'il s'agit d'un Return, on tente d'associer l'activité correspondante si possible.
    """
    if not raw_id:
        return (None, None)
    key = str(raw_id).lower()

    if key in activity_mapping:
        return ('activity', activity_mapping[key])
    if key in data_mapping:
        return ('data', data_mapping[key])
    if key in return_mapping:
        d_id = return_mapping[key]
        d = Data.query.get(d_id)
        if d and d.type.lower() == "retour":
            # Chercher l'activité portant le même nom
            same_act = _scoped(Activities.query.filter_by(name=d.name), Activities).first()
            if same_act:
                return ('activity', same_act.id)
        return ('data', d_id)

    return (None, None)


def get_entity_name(eid, kind):
    """Renvoie .name de l’activité ou du data pour logs."""
    if not eid:
        return "??"
    if kind == 'activity':
        a = Activities.query.get(eid)
        return a.name if a else "activité_inconnue"
    elif kind == 'data':
        dd = Data.query.get(eid)
        return dd.name if dd else "data_inconnue"
    return "inconnu"


def standardize_id(visio_id):
    """Convertit shape.ID en string stable."""
    try:
        return str(int(visio_id)).strip().lower()
    except:
        return str(visio_id).strip().lower()


def print_summary():
    """
    Affiche (print) un résumé des liens créés (link_summaries)
    et des renommages (rename_summaries).
    Cette fonction est appelée par activities.py
    dans la route /update-cartography (avec contextlib.redirect_stdout).
    """
    print("\n--- RÉSUMÉ DES LIENS ---")
    if link_summaries:
        for (data_name, data_type, s_name, t_name) in link_summaries:
            print(f"  - '{data_name}' ({data_type}) : {s_name} -> {t_name}")
    else:
        print("  Aucun lien créé")
    print("--- Fin du résumé ---\n")

    if rename_summaries:
        print("--- Renommages détectés ---")
        for (old, new) in rename_summaries:
            print(f"  * '{old}' => '{new}'")
        print("--- Fin des renommages ---\n")

    print("CONFIRMATION : toutes les opérations ont été effectuées avec succès.")


if __name__ == "__main__":
    from flask import Flask
    app = create_app()
    with app.app_context():
        vsdx_path = os.path.join("Code", "example.vsdx")
        process_visio_file(vsdx_path)
        print_summary()
