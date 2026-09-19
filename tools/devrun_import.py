"""Instance jetable pour mettre au point la fenêtre « Importer des données ».

    python tools/devrun_import.py      → http://127.0.0.1:8126/devrun/admin

Deux cartos (la carte RFQ FluidClip et sa copie « site Inde ») à un
administrateur, une troisième à un coordinateur — de quoi éprouver la PORTÉE.
Et des fichiers d'exemple, servis sous /devrun/fichier/<nom>, qui couvrent les
cas que l'écran doit savoir montrer : un fichier propre, un export RH
désordonné qu'il faut faire organiser, un csv, le tableau de tâches du client
avec ses cellules fusionnées, un classeur à plusieurs feuilles dont une
ambiguë et une illisible.

⚠️ L'IA est SIMULÉE (heuristiques sur les en-têtes et le contenu) : sans clé,
les écrans « organiser » et « rapprocher » ne s'afficheraient jamais. La
simulation vit ICI, jamais dans l'application.

Outil de mise au point AFDEC : `tools/` est exclu de l'image (.dockerignore).
"""
import io
import json
import os
import re
import sys
import tempfile
from difflib import SequenceMatcher

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = int(os.environ.get("PORT", "8126"))
CARTO = "tools/provisioning/carto/map_rfq_fluidclip.json"

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)
DOSSIER = tempfile.mkdtemp(prefix="imports-")

from Code.app import create_app                      # noqa: E402
from Code.extensions import db                       # noqa: E402

app = create_app(test_config={
    "TESTING": False,
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
    "SECRET_KEY": "dev-import",
    "WTF_CSRF_ENABLED": False,
    "MAIL_SUPPRESS_SEND": True,
    "TEMPLATES_AUTO_RELOAD": True,
    "SEND_FILE_MAX_AGE_DEFAULT": 0,
})
app.jinja_env.auto_reload = True


# ── Fichiers d'exemple ───────────────────────────────────────────────────
def _classeur(nom, *feuilles):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for titre, lignes in feuilles:
        ws = wb.create_sheet(titre)
        for l in lignes:
            ws.append(l)
    wb.save(os.path.join(DOSSIER, nom))


ROLES = [["Nom du rôle", "Mission"],
         ["Acheteur", "Négocier et passer les commandes fournisseurs"],
         ["Customer", "Le client, tel qu'il figure déjà sur la carte"],
         ["Responsable qualité fournisseur", "Garantir la conformité des pièces achetées"],
         ["Chef de projet", "Piloter le projet de la RFQ au démarrage série"],
         [None, "Une ligne sans nom"],
         ["acheteur", "Doublon de la première ligne"]]

TACHES = [["Semi Finish", "Task", "Tools", "Guarantor", "Doer", "Approver", "Skills"],
          ["Clarify RFQ Requirements", "Read the customer specification", "Teamcenter",
           "Sales & customer Relationship", "Sales engineer", "Sales manager",
           "No Special skills required"],
          [None, "List open technical questions", "Excel; -", None, "Sales engineer", None,
           "Technical reading"],
          ["Cost estimation", "Collect child-part prices", "SAP", "Administrative & Financial Management",
           "Cost engineer", "Finance manager", "Costing"],
          [None, "Build the cost breakdown", "SAP; Excel", None, "Cost engineer", None, "Costing"],
          ["Negociation", "Prepare the negotiation file", "Excel", "Negotiation & supplier Relations",
           "Buyer", None, "Negotiation"],
          ["Identify Part", "Identify the part family", "Teamcenter", "Product Design & Engineering",
           "Design engineer", "Engineering manager", "Product knowledge"],
          [None, "Check similar existing parts", "Teamcenter", None, "Design engineer", None, None],
          ["Plan the coffee break", "Order croissants", None, None, None, None, None]]

OUTILS = [["Outil", "Usage"], ["SAP", "ERP — achats et coûts"], ["Teamcenter", "PLM"],
          ["Excel", "Tableur"], ["CATIA", "CAO 3D"]]

COLLABS = [["Prénom", "Nom", "E-mail", "Statut", "Rôle"],
           ["Jean", "Dupont", "jean.dupont@exemple.fr", "Utilisateur", "Customer"],
           ["Léa", "Martin", "lea.martin@exemple.fr", "Champion", "Chef de projet"],
           ["Priya", "Bhivare", "priya.bhivare@exemple.in", "Coordinateur", ""],
           ["Déjà", "Là", "deja@test.local", "", ""]]

_classeur("roles.xlsx", ("Postes", ROLES))
_classeur("taches_rfq_client.xlsx", ("RFQ tasks", TACHES))
_classeur("outils.xlsx", ("Outils", OUTILS))
_classeur("export_sirh.xlsx", ("Export", [
    ["Export SIRH — 15/09/2026"], [None],
    ["Collaborateur", "Adresse", "Fonction", "Site"],
    ["DUPONT Jean", "jean.dupont@exemple.fr", "Chef de projet", "Lyon"],
    ["MARTIN Léa", "lea.martin@exemple.fr", "Acheteuse", "Lyon"],
    ["BHIVARE Priya", "priya.bhivare@exemple.in", "Sales engineer", "Pune"],
    ["DURAND Paul", "paul.durand@exemple", "Buyer", "Pune"],
    ["LÀ Déjà", "deja@test.local", "", ""]]))
_classeur("classeur_complet.xlsx",
          ("Rôles", ROLES[:5]), ("Collaborateurs", COLLABS), ("Outils", OUTILS),
          ("Tâches", TACHES[:6]),
          ("Feuil5", [["Nom", "Description"], ["Presse 250 t", "Presse à injecter"],
                      ["Moule M12", "Moule 4 empreintes"]]),
          ("Notes", [["Ce classeur regroupe les données du pilote."],
                     ["Contact : service RH"]]))
with open(os.path.join(DOSSIER, "utilisateurs.csv"), "w", encoding="cp1252", newline="") as f:
    for l in [["Prénom", "Nom", "E-mail", "Statut", "Rôle"],
              ["Jean", "Dupont", "jean.dupont@exemple.fr", "Utilisateur", "Customer"],
              ["Léa", "Martin", "lea.martin@exemple.fr", "Champion", "Chef de projet"],
              ["Priya", "Bhivare", "priya.bhivare@exemple.in", "Administrateur", ""],
              ["Tom", "Stage", "tom@exemple.fr", "Stagiaire", "Magasinier"],
              ["Sans", "Mail", "pas-un-mail", "", ""]]:
        f.write(";".join(l) + "\r\n")


# ── Base ─────────────────────────────────────────────────────────────────
with app.app_context():
    from Code.models.models import Entity, Tool, User
    from Code.routes.cartography_editor import _sync_carto_to_db
    from Code.security import hash_password

    db.drop_all()
    db.create_all()
    payload = json.load(open(CARTO, encoding="utf-8"))
    diagram = payload.get("diagram") if payload.get("format") == "optiqcarto/entity" else payload

    admin = User(first_name="Maël", last_name="Girardin", email="admin@test.local",
                 password=hash_password("Test1234!"), status="administrateur", lang="fr")
    coord = User(first_name="Camille", last_name="Fontaine", email="coord@test.local",
                 password=hash_password("Test1234!"), status="coordinateur", lang="fr")
    simple = User(first_name="Noé", last_name="Berthier", email="user@test.local",
                  password=hash_password("Test1234!"), status="user", lang="fr")
    deja = User(first_name="Déjà", last_name="Là", email="deja@test.local",
                password=hash_password("Test1234!"), status="user", lang="fr")
    db.session.add_all([admin, coord, simple, deja])
    db.session.commit()

    cartos = []
    for nom, proprio in (("RFQ FluidClip", admin), ("RFQ FluidClip — site Inde", admin),
                         ("Carto de Camille", coord)):
        e = Entity(name=nom, owner_id=proprio.id,
                   optiqcarto_data=json.dumps(diagram, ensure_ascii=False))
        db.session.add(e)
        db.session.commit()
        _sync_carto_to_db(e, diagram)
        cartos.append(e)
    db.session.add(Tool(name="SAP", entity_id=cartos[0].id, description="ERP"))
    db.session.commit()
    print(f"[devrun] base     : {db_path}")
    print(f"[devrun] fichiers : {DOSSIER}")
    for n in sorted(os.listdir(DOSSIER)):
        print(f"[devrun]   /devrun/fichier/{n}")
    print(f"[devrun] http://127.0.0.1:{PORT}/devrun/admin")


# ── IA simulée ───────────────────────────────────────────────────────────
from Code.routes import import_hub   # noqa: E402

_MOTS = {
    "email": ("mail", "adresse", "contact", "courriel"),
    "role": ("fonction", "poste", "metier", "role", "title"),
    "statut": ("statut", "profil"),
    "tache": ("etape", "action", "task"),
    "activite": ("process", "activite", "semi"),
    "nom": ("nom", "name", "outil", "libelle"),
    "mission": ("mission", "description"),
    "description": ("description", "usage", "detail"),
}


def _ia_simulee(systeme, contenu):
    if "unmatched" in contenu:                      # rapprocher des activités
        acts = contenu["db_activities"]
        resolus = []
        for u in contenu["unmatched"]:
            nom = u["activity_name_excel"].lower()
            meilleur = max(acts, key=lambda a: SequenceMatcher(None, nom, a["name"].lower()).ratio())
            score = SequenceMatcher(None, nom, meilleur["name"].lower()).ratio()
            if "identify" in nom:
                meilleur = next((a for a in acts if "Preliminary Technical" in a["name"]), meilleur)
                score = .8
            if score < .3:
                continue
            resolus.append({"activity_name_excel": u["activity_name_excel"],
                            "activity_id": meilleur["id"], "activity_name_db": meilleur["name"],
                            "confidence": "high" if score >= .6 else "low",
                            "match_reason": "IA simulée (devrun) : sens voisin"})
        return {"resolved": resolus}

    types = list(contenu["schemas"])
    lignes = contenu["lignes"]
    entete = next((l for l in lignes if len(l["cellules"]) >= 2), lignes[0])
    idx = entete["ligne"]
    data = [l for l in lignes if l["ligne"] > idx]
    cols = {}
    nom_complet = None
    for j, titre in entete["cellules"].items():
        t_ = import_hub._norm(titre)
        valeurs = [l["cellules"].get(j, "") for l in data]
        if valeurs and sum("@" in v for v in valeurs) >= len(valeurs) / 2:
            cols["email"] = int(j)
            continue
        if valeurs and sum(len(v.split()) == 2 for v in valeurs) >= len(valeurs) / 2 \
                and "users" in types and nom_complet is None and "@" not in "".join(valeurs):
            nom_complet = int(j)
            continue
        for champ, mots in _MOTS.items():
            if champ not in cols and any(m in t_ for m in mots):
                cols[champ] = int(j)
                break
    if not cols and nom_complet is None:
        return {"type": None, "remarque": "IA simulée : aucune donnée importable ici."}
    ty = "users" if ("email" in cols or nom_complet is not None) and "users" in types else types[0]
    return {"type": ty, "ligne_entete": idx, "colonnes": cols, "nom_complet": nom_complet,
            "ordre_nom": None, "confiance": "medium",
            "remarque": "IA simulée (devrun) : « Collaborateur » porte le nom complet, "
                        "« Adresse » l'e-mail, « Fonction » le rôle ; « Site » est ignoré."}


import_hub._appeler_ia = _ia_simulee
import_hub._ia_disponible = lambda: True


# ── Connexion en un clic ─────────────────────────────────────────────────
@app.before_request
def _toujours_connecte():
    from flask import redirect, request, session
    from Code.models.models import User
    if request.path.startswith("/devrun/"):
        return None
    if not session.get("user_id"):
        u = User.query.filter_by(email="admin@test.local").first()
        session.update(user_id=u.id, user_email=u.email, lang=u.lang or "fr")
    if request.path == "/":
        return redirect("/activities/map")
    return None


@app.route("/devrun/<qui>")
def _devrun(qui):
    from flask import redirect, request, session
    from Code.models.models import User
    u = User.query.filter_by(email=qui + "@test.local").first()
    if not u:
        return "compte inconnu", 404
    session.clear()
    session.update(user_id=u.id, user_email=u.email,
                   lang=request.args.get("lang") or u.lang or "fr")
    return redirect("/activities/map")


@app.route("/devrun/fichier/<nom>")
def _fichier(nom):
    from flask import send_from_directory
    return send_from_directory(DOSSIER, nom, as_attachment=True)


app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
