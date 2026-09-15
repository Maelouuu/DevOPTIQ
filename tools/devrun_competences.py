"""Instance jetable pour mettre au point la PAGE COMPÉTENCES.

    python tools/devrun_competences.py    → http://127.0.0.1:8125/devrun/as/dev@test.local

Un développeur de compétences, trois collaborateurs, un rôle de six activités —
et surtout les états que la page doit savoir montrer, tous présents en même
temps : activité pas encore configurée, configurée mais pas évaluée, évaluation
partielle, écart, niveau tenu, écart de technicité. Sans ça on ne regarde jamais
que le cas heureux.

Outil de mise au point AFDEC : `tools/` est exclu de l'image (.dockerignore).
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = int(os.environ.get("PORT", "8125"))

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)

from Code.app import create_app                      # noqa: E402
from Code.extensions import db                       # noqa: E402

app = create_app(test_config={
    "TESTING": False,
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
    "SECRET_KEY": "dev-competences",
    "WTF_CSRF_ENABLED": False,
    "MAIL_SUPPRESS_SEND": True,
    # Sinon Jinja garde le gabarit compilé en mémoire et le navigateur garde les
    # fichiers statiques : on retouche le CSS et rien ne bouge à l'écran.
    "TEMPLATES_AUTO_RELOAD": True,
    "SEND_FILE_MAX_AGE_DEFAULT": 0,
})
app.jinja_env.auto_reload = True

# (nom, compétence principale, [(résultat, standard minimal)], requis, {index résultat: niveau})
PLAN = [
    ("Analyser la demande client",
     "Traduire une demande client en exigences techniques exploitables par le bureau d'études.",
     [("Cahier des charges validé", "Toutes les exigences tracées et validées par le client."),
      ("Fiche de faisabilité", "Un avis argumenté sous 5 jours ouvrés.")],
     3, {0: 3, 1: 2}),
    ("Chiffrer l'offre",
     "Construire un chiffrage complet et défendable à partir des exigences retenues.",
     [("Devis chiffré", "Écart de marge inférieur à 3 % au réalisé."),
      ("Hypothèses de coût", "Chaque poste supérieur à 5 k€ documenté.")],
     3, {0: 2, 1: 1}),
    ("Concevoir la solution préliminaire",
     "Proposer une architecture produit conforme aux exigences et industrialisable.",
     [("Schéma de principe", "Revu et accepté en revue de conception.")],
     2, {0: 2}),
    ("Valider le prototype",
     "Conduire la campagne d'essais et prononcer la validation du prototype.",
     [("Rapport d'essais", "Plan d'essais couvert à 100 %."),
      ("Procès-verbal de validation", "Signé avant le jalon de lancement.")],
     3, {0: None, 1: None}),
    ("Industrialiser la piece", None, [], 2, {}),
    ("Suivre la performance série",
     "Piloter les indicateurs de la vie série et déclencher les actions correctives.",
     [("Tableau de bord mensuel", "Diffusé avant le 5 du mois.")],
     2, {0: 4}),
]

with app.app_context():
    from Code.models.models import (Activities, Competency, CompetencyEvaluation, Data,
                                    Entity, Role, User, UserRole, activity_roles)
    from Code.roles_permanents import role_dev_competences
    from Code.security import hash_password

    db.drop_all()
    db.create_all()

    dev = User(first_name="Mael", last_name="Girardin", email="dev@test.local",
               password=hash_password("Test1234!"), status="administrateur", lang="fr")
    noe = User(first_name="Noe", last_name="Berthier", email="noe@test.local",
               password=hash_password("Test1234!"), status="user", lang="fr")
    lina = User(first_name="Lina", last_name="Moreau", email="lina@test.local",
                password=hash_password("Test1234!"), status="champion", lang="fr")
    theo = User(first_name="Theo", last_name="Vasseur", email="theo@test.local",
                password=hash_password("Test1234!"), status="user", lang="fr")
    # Rattache a personne, n'encadre personne : l'etat ou la page n'a rien a
    # montrer. Il doit s'EXPLIQUER, pas jeter un message d'erreur.
    seul = User(first_name="Jules", last_name="Petit", email="seul@test.local",
                password=hash_password("Test1234!"), status="user", lang="fr")
    db.session.add_all([dev, noe, lina, theo, seul])
    db.session.commit()

    ent = Entity(name="Bureau d'etudes", description="entite de mise au point",
                 owner_id=dev.id, is_active=True)
    db.session.add(ent)
    db.session.commit()

    role_dev_competences(ent.id)                       # le role permanent
    metier = Role(name="Charge d'affaires", entity_id=ent.id)
    autre = Role(name="Technicien essais", entity_id=ent.id)
    db.session.add_all([metier, autre])
    db.session.commit()

    for u in (noe, lina, theo):
        u.manager_id = dev.id
        db.session.add(UserRole(user_id=u.id, role_id=metier.id, manager_id=dev.id))
    db.session.add(UserRole(user_id=noe.id, role_id=autre.id, manager_id=dev.id))
    db.session.commit()

    now = datetime.utcnow()
    for i, (nom, comp, sorties, requis, notes) in enumerate(PLAN):
        act = Activities(name=nom, entity_id=ent.id, shape_id="dev-%d" % i)
        db.session.add(act)
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=metier.id, status="Garant",
            required_mastery_level=requis))
        if comp:
            db.session.add(Competency(description=comp, activity_id=act.id))
        for j, (sortie, standard) in enumerate(sorties):
            d = Data(entity_id=ent.id, name=sortie, type="flux",
                     producer_activity_id=act.id, semantic_nature="RESULT",
                     minimum_performance_text=standard, qualification_source="MANUAL",
                     qualification_updated_at=now)
            db.session.add(d)
            db.session.commit()
            niveau = notes.get(j)
            if niveau is not None:
                db.session.add(CompetencyEvaluation(
                    user_id=noe.id, activity_id=act.id, item_id=d.id,
                    item_type="activity_results", eval_number="2", note="green",
                    mastery_level=niveau, evaluated_at=now - timedelta(days=3 * i),
                    evaluator_user_id=dev.id))
            if i == 0 and j == 0:           # une auto-evaluation, pour la ligne « reference »
                db.session.add(CompetencyEvaluation(
                    user_id=noe.id, activity_id=act.id, item_id=d.id,
                    item_type="activity_results", eval_number="0", note="grey",
                    mastery_level=2, evaluated_at=now))
        db.session.commit()

    # L'activite « a configurer » doit avoir de VRAIES connexions sortantes :
    # une donnee de sortie EST une connexion sortante de la carto, et sans elles
    # l'ecran de qualification repond « aucune donnee de sortie ».
    from Code.models.models import Link
    actes = Activities.query.order_by(Activities.id).all()
    a_configurer = next(a for a in actes if a.name == "Industrialiser la piece")
    for cible, libelle in ((actes[5], "Gamme de fabrication"), (actes[0], "Dossier d'industrialisation")):
        db.session.add(Link(entity_id=ent.id, source_activity_id=a_configurer.id,
                            target_activity_id=cible.id, type="flux", description=libelle))
    db.session.commit()

    # Un domaine technique en ecart, pour que la colonne Technicite ne soit pas vide.
    try:
        from Code.models.models import (TechnicalDomain, ActivityTechnicalDomain,
                                                   RoleActivityDomainRequirement, UserDomainLevel)
        acts = Activities.query.order_by(Activities.id).all()
        dom = TechnicalDomain(entity_id=ent.id, name_fr="Plastique", name_en="Plastic")
        db.session.add(dom)
        db.session.commit()
        db.session.add(ActivityTechnicalDomain(activity_id=acts[0].id, domain_id=dom.id))
        db.session.add(RoleActivityDomainRequirement(
            role_id=metier.id, activity_id=acts[0].id, domain_id=dom.id, required_level=3))
        db.session.add(UserDomainLevel(user_id=noe.id, domain_id=dom.id, demonstrated_level=1))
        db.session.commit()
    except Exception as e:                  # le module bouge, l'outil ne doit pas bloquer
        print("[devrun] technicite sautee : %s" % e)

    print("[devrun] base   : %s" % db_path)
    print("[devrun] dev    : dev@test.local / Test1234!  (developpeur de competences)")
    print("[devrun] collab : Noe (evalue), Lina, Theo")
    print("[devrun] http://127.0.0.1:%d/devrun/as/dev@test.local" % PORT)


@app.before_request
def _devrun_toujours_connecte():
    """On arrive toujours connecté : l'outil sert à REGARDER la page, pas à
    rejouer un formulaire de connexion à chaque rechargement. `/devrun/<qui>`
    change de compte."""
    from flask import redirect, request, session
    from Code.models.models import User

    if request.path.startswith("/devrun/"):
        return None
    if not session.get("user_id"):
        u = User.query.filter_by(email="dev@test.local").first()
        if u:
            session["user_email"] = u.email
            session["user_id"] = u.id
            session["lang"] = u.lang or "fr"
    if request.path == "/":
        return redirect("/competences/view")
    return None


@app.route("/devrun/<qui>")
def _devrun_court(qui):
    """Raccourci : /devrun/dev, /devrun/noe… (une adresse complète dans l'URL,
    avec son « @ », se fait manger par certains navigateurs d'aperçu)."""
    return _devrun_as(qui + "@test.local")


@app.route("/devrun/as/<email>")
def _devrun_as(email):
    """Bascule de compte en un clic. Vit dans l'OUTIL, jamais dans l'image."""
    from flask import redirect, session
    from Code.models.models import User

    u = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if not u:
        return "compte inconnu : %s" % email, 404
    session.clear()
    session["user_email"] = u.email
    session["user_id"] = u.id
    session["lang"] = u.lang or "fr"
    return redirect("/competences/view")


app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
