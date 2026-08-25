"""Provisionnement d'une instance client OptiqFluent (comptes + entité + carto).

Applique un « plan » JSON (tools/provisioning/plans/*.json) sur la base d'une
instance : création des comptes, création de l'entité et injection de sa
cartographie — via la MÊME logique que l'éditeur (`_sync_carto_to_db`), donc
activités, rôles et connexions sont dérivés de la carte exactement comme après
un import Visio dans l'interface.

Le script est idempotent : le rejouer ne duplique rien (comptes retrouvés par
e-mail, entité par nom + propriétaire, carto ré-synchronisée par shape_id/nom).

Usage :
    export DATABASE_URL="postgresql://…"        # base de l'instance cible
    python tools/provisioning/provision.py --plan tools/provisioning/plans/araymond.json --dry-run
    python tools/provisioning/provision.py --plan tools/provisioning/plans/araymond.json

Options :
    --database-url URL   au lieu de $DATABASE_URL (défaut : SQLite locale)
    --dry-run            affiche ce qui serait fait, sans rien écrire
    --force-password     réinitialise aussi le mot de passe des comptes existants

⚠️ tools/ est exclu de l'image client (.dockerignore) : c'est un outil AFDEC,
qui s'exécute depuis un poste ayant accès à la base de l'instance.
"""
import argparse
import io
import json
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(BASE, '..', '..'))
sys.path.insert(0, REPO)

# Variables d'environnement à effet de bord au démarrage de l'app.
_BOOT_SIDE_EFFECTS = ("ADMIN_EMAIL", "ADMIN_PASSWORD", "DEMO_SEED",
                      "REQUIRE_LICENSE", "SETUP_WIZARD")


def import_create_app():
    """Importe create_app SANS déclencher de boot sur la base cible.

    Code/app.py se termine par `app = create_app()` (point d'entrée gunicorn) :
    un simple import lance donc un démarrage COMPLET — migrations ALTER,
    create_all, bootstrap du compte admin — sur la base désignée par
    DATABASE_URL, c'est-à-dire celle du client. On confine cet import à une
    SQLite temporaire, variables à effet de bord neutralisées ; l'app
    réellement utilisée est construite ensuite via create_app(test_config).
    """
    saved = {k: os.environ.pop(k, None) for k in _BOOT_SIDE_EFFECTS}
    saved["DATABASE_URL"] = os.environ.get("DATABASE_URL")
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db.close()
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db.name}"

    out, err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()  # boot bruyant : [DB], [BOOTSTRAP]…
    try:
        from Code.app import create_app
    finally:
        sys.stdout, sys.stderr = out, err
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            os.unlink(tmp_db.name)
        except OSError:
            pass
    return create_app


def build_app(database_url):
    """App Flask branchée sur la base cible.

    test_config court-circuite le bloc d'init du boot (migrations ALTER,
    bootstrap admin, seed) : le provisionnement ne doit pas rejouer le
    démarrage de l'instance, seulement écrire ses données.
    """
    create_app = import_create_app()
    cfg = {"TESTING": False, "SECRET_KEY": "provisioning"}
    if database_url:
        url = database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        cfg["SQLALCHEMY_DATABASE_URI"] = url
        if url.startswith("sqlite"):
            cfg["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"check_same_thread": False}}
    return create_app(test_config=cfg)


def ensure_user(spec, report, force_password=False):
    """Compte retrouvé par e-mail (unique en base) ou créé."""
    from Code.extensions import db
    from Code.models.models import User
    from Code.security import hash_password

    email = spec["email"].strip().lower()
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user:
        changes = []
        for field in ("first_name", "last_name", "status"):
            if spec.get(field) and getattr(user, field) != spec[field]:
                setattr(user, field, spec[field])
                changes.append(field)
        if force_password and spec.get("password"):
            user.password = hash_password(spec["password"])
            changes.append("mot de passe")
        report.append(f"  ~ compte existant {email}"
                      + (f" — mis à jour ({', '.join(changes)})" if changes else " — inchangé"))
        return user

    user = User(
        first_name=spec.get("first_name", ""),
        last_name=spec.get("last_name", ""),
        email=spec["email"].strip(),
        password=hash_password(spec["password"]),
        status=spec.get("status", "user"),
    )
    db.session.add(user)
    db.session.flush()
    report.append(f"  + compte créé {user.email} (statut « {user.status} »)")
    return user


def ensure_entity(spec, owner, report):
    """Entité retrouvée par nom pour ce propriétaire, ou créée.

    owner_id est obligatoire : Entity.get_active() est STRICT — une entité
    sans propriétaire (ou appartenant à un autre) reste invisible dans l'app.
    """
    from Code.extensions import db
    from Code.models.models import Entity

    name = spec["name"].strip()
    entity = Entity.query.filter_by(name=name, owner_id=owner.id).first()
    if entity:
        report.append(f"  ~ entité existante « {name} » (id={entity.id})")
    else:
        entity = Entity(name=name, description=spec.get("description"), owner_id=owner.id)
        db.session.add(entity)
        db.session.flush()
        report.append(f"  + entité créée « {name} » (id={entity.id}, propriétaire {owner.email})")
    if spec.get("vsdx_filename"):
        entity.vsdx_filename = spec["vsdx_filename"]
    return entity


def apply_carto(entity, carto_path, report):
    """Injecte la carte puis dérive activités / rôles / connexions."""
    from Code.extensions import db
    from Code.models.models import Activities, Link, Role
    from Code.routes.cartography_editor import _sync_carto_to_db

    diagram = json.load(open(carto_path, encoding='utf-8'))
    entity.optiqcarto_data = json.dumps(diagram, ensure_ascii=False)
    db.session.flush()
    _sync_carto_to_db(entity, diagram)
    db.session.flush()

    acts = Activities.query.filter_by(entity_id=entity.id).count()
    roles = Role.query.filter_by(entity_id=entity.id).count()
    links = Link.query.filter_by(entity_id=entity.id).count()
    report.append(f"  → carto synchronisée : {acts} activités, {roles} rôles, {links} connexions "
                  f"(source : {len(diagram.get('shapes', []))} formes, "
                  f"{len(diagram.get('bands', []))} bandes)")


def wire_manager(entity, manager, report):
    """Rattache les autres comptes de l'entité à ce manager.

    Dans OPTIQ, « être manager » n'est pas un statut : c'est être désigné
    comme manager par d'autres comptes (users.manager_id / user_roles.manager_id).
    C'est ce lien que lit la page Compétences pour ouvrir la vue manager.
    """
    from Code.models.models import User, UserRole

    others = User.query.filter(User.entity_id == entity.id, User.id != manager.id).all()
    attached = 0
    for u in others:
        if u.manager_id != manager.id:
            u.manager_id = manager.id
            attached += 1
    for ur in UserRole.query.join(User, UserRole.user_id == User.id).filter(
            User.entity_id == entity.id, UserRole.user_id != manager.id).all():
        ur.manager_id = manager.id

    if attached:
        report.append(f"  → {manager.email} devient manager de {attached} collaborateur(s)")
    else:
        report.append(f"  → {manager.email} : aucun collaborateur à rattacher pour l'instant "
                      f"(la vue manager s'activera dès qu'un compte lui sera rattaché)")


def run(plan_path, database_url, dry_run, force_password):
    plan = json.load(open(plan_path, encoding='utf-8'))
    plan_dir = os.path.dirname(os.path.abspath(plan_path))
    report = []

    app = build_app(database_url)
    from Code.extensions import db
    from Code.models.models import User

    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        print(f"Plan   : {plan.get('label', os.path.basename(plan_path))}")
        print(f"Base   : {uri.split('@')[-1] if '@' in uri else uri}")
        print(f"Mode   : {'SIMULATION (aucune écriture)' if dry_run else 'APPLICATION'}\n")

        try:
            db.create_all()  # ne crée que les tables absentes — jamais destructif
        except Exception as exc:
            print(f"[!] create_all : {exc}")

        for spec in plan.get("users", []):
            ensure_user(spec, report, force_password)

        for ent_spec in plan.get("entities", []):
            owner = User.query.filter(
                db.func.lower(User.email) == ent_spec["owner_email"].strip().lower()).first()
            if not owner:
                report.append(f"  ! entité « {ent_spec['name']} » ignorée : "
                              f"propriétaire {ent_spec['owner_email']} introuvable")
                continue
            entity = ensure_entity(ent_spec, owner, report)
            # entity_id des comptes du plan rattachés à cette entité
            for spec in plan.get("users", []):
                if spec.get("entity") == ent_spec["name"]:
                    u = User.query.filter(
                        db.func.lower(User.email) == spec["email"].strip().lower()).first()
                    if u and u.entity_id != entity.id:
                        u.entity_id = entity.id
                        report.append(f"  → {u.email} rattaché à « {entity.name} »")
            if ent_spec.get("carto"):
                apply_carto(entity, os.path.join(plan_dir, ent_spec["carto"]), report)
            for email in ent_spec.get("managers", []):
                mgr = User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()
                if mgr:
                    wire_manager(entity, mgr, report)

        print("\n".join(report))
        if dry_run:
            db.session.rollback()
            print("\nSIMULATION — rien n'a été écrit.")
        else:
            db.session.commit()
            print("\n✓ Provisionnement appliqué.")


def main():
    ap = argparse.ArgumentParser(description="Provisionne une instance client OptiqFluent.")
    ap.add_argument("--plan", required=True, help="fichier de plan JSON")
    ap.add_argument("--database-url", default=os.getenv("DATABASE_URL"),
                    help="base cible (défaut : $DATABASE_URL, sinon SQLite locale)")
    ap.add_argument("--dry-run", action="store_true", help="simule sans écrire")
    ap.add_argument("--force-password", action="store_true",
                    help="réinitialise le mot de passe des comptes déjà existants")
    args = ap.parse_args()
    run(args.plan, args.database_url, args.dry_run, args.force_password)


if __name__ == "__main__":
    main()
