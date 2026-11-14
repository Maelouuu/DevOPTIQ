# -*- coding: utf-8 -*-
"""LE CALENDRIER PARTAGÉ — ce qui occupe le temps, et ce qui se mesure.

Deux sources sur une même grille : les séances d'évaluation (page
Compétences) et les activités de la carto (page Temps). On les allume et on
les éteint ; on arrive avec celle de la page d'où l'on vient.

⚠️⚠️ LA DÉCISION DE CET ÉCRAN : une activité N'A PAS DE DATE. Elle a un
CRÉNEAU — une récurrence et une fréquence. Lui inventer un jour serait pire
que de ne rien montrer : un calendrier qui annonce « Chiffrer l'offre,
mardi 17 » alors que rien, nulle part, ne dit mardi, fabrique un rendez-vous
auquel personne ne s'est engagé. Chaque rythme se pose donc sur l'étendue
qu'il occupe VRAIMENT :

    séance d'évaluation      →  SON jour (elle en a un, c'est un rendez-vous)
    activité journalière     →  chaque jour ouvré
    activité hebdomadaire    →  la BANDE de la semaine
    mensuel / trimestriel / annuel → la BANDE du mois

Rien ne prétend à un jour qu'il ne tient pas.

⚠️ Réservé à l'ADMINISTRATEUR pour ce premier jet. Le masquage n'est pas une
sécurité : la page redirige et l'API refuse.
"""
from datetime import date

from flask import (Blueprint, jsonify, redirect, render_template,
                   session as flask_session, url_for)

from Code.models.models import (Activities, Role, TimeAnalysis, User, UserRole,
                                activity_roles)
from Code.extensions import db
from Code.permissions import is_admin

calendrier_bp = Blueprint("calendrier", __name__, url_prefix="/calendrier")

# Où se pose chaque récurrence. ⚠️ La clé est le PRÉFIXE : `recurrence` est du
# texte libre écrit par plusieurs écrans (« journalier », « Journalier »…).
REGISTRES = (
    ("jour", ("jour",)),
    ("semaine", ("hebdo",)),
    ("mois", ("mens", "trimestr", "ann")),
)


def _registre(recurrence):
    r = (recurrence or "").strip().lower()
    for nom, prefixes in REGISTRES:
        if any(r.startswith(p) for p in prefixes):
            return nom
    # ⚠️ Une récurrence inconnue tombe dans la bande du MOIS, pas dans les
    # jours : la poser sur chaque jour ouvré multiplierait par vingt une
    # charge dont on ne sait rien.
    return "mois"


def _utilisateur():
    uid = flask_session.get("user_id")
    return db.session.get(User, uid) if uid else None


def _qui_tient_quoi(ids_activites):
    """Pour chaque activité : ses rôles, et les comptes qui tiennent ces rôles.

    ⚠️ En TROIS requêtes pour toute la carto, jamais une par activité : cet
    écran s'ouvre d'un clic et une carto porte des centaines d'activités.
    """
    if not ids_activites:
        return {}, {}, []
    liens = db.session.execute(
        activity_roles.select().where(
            activity_roles.c.activity_id.in_(ids_activites))).fetchall()
    par_activite = {}
    ids_roles = set()
    for ligne in liens:
        par_activite.setdefault(ligne.activity_id, []).append(ligne.role_id)
        ids_roles.add(ligne.role_id)

    titulaires = {}
    if ids_roles:
        for ur in UserRole.query.filter(UserRole.role_id.in_(ids_roles)).all():
            titulaires.setdefault(ur.role_id, []).append(ur.user_id)
    roles = (Role.query.filter(Role.id.in_(ids_roles)).order_by(Role.name.asc()).all()
             if ids_roles else [])
    return par_activite, titulaires, roles


def donnees_du_calendrier(acteur, lang):
    """Les deux sources, et de quoi filtrer. Lisible par un administrateur."""
    from Code.role_i18n import nom_affiche
    from Code.routes.paliers_routes import _nommer, _sessions_lisibles
    from Code.paliers import json_session

    # ── Les séances : elles ONT une date ───────────────────────────────
    seances = []
    sessions = _sessions_lisibles(acteur)
    gens, roles_seance, nommer = _nommer(sessions, lang)
    for s in sessions:
        j = json_session(s, 0)
        qui = gens.get(s.user_id)
        r = roles_seance.get(s.role_id)
        j["nom"] = ("%s %s" % (qui.first_name, qui.last_name)) if qui else ""
        j["role"] = nommer(r, lang) if r else ""
        j["role_id"] = s.role_id
        j["user_id"] = s.user_id
        seances.append(j)
    seances.sort(key=lambda x: (x["date_prevue"] or "", x["id"]))

    # ── Les activités : elles ont un CRÉNEAU ───────────────────────────
    activites = Activities.for_active_entity().order_by(Activities.name.asc()).all()
    noms = {a.id: a.name for a in activites}
    par_activite, titulaires, roles = _qui_tient_quoi(list(noms.keys()))

    creneaux = {"jour": [], "semaine": [], "mois": []}
    if noms:
        for x in (TimeAnalysis.query
                  .filter_by(type="activity")
                  .filter(TimeAnalysis.activity_id.in_(list(noms.keys())))
                  .order_by(TimeAnalysis.id.desc()).all()):
            # ⚠️ La MÊME expression que `api_tableau_de_bord` : ce qu'une
            # occurrence de la période coûte. On n'annualise pas ici — on
            # montre ce qui revient, pas ce que ça pèse sur l'année.
            par_periode = (float(x.duration or 0)
                           * max(1, int(x.frequency or 1))
                           * max(1, int(x.nb_people or 1)))
            ids_roles = par_activite.get(x.activity_id, [])
            gens_ids = sorted({u for rid in ids_roles
                               for u in titulaires.get(rid, [])})
            creneaux[_registre(x.recurrence)].append({
                "id": x.id,
                "activity_id": x.activity_id,
                "activite": noms.get(x.activity_id, ""),
                "recurrence": (x.recurrence or "").strip().lower(),
                "frequence": max(1, int(x.frequency or 1)),
                "minutes": par_periode,
                "roles": ids_roles,
                "users": gens_ids,
            })

    # ── De quoi filtrer : les rôles de la carto, les comptes qui les tiennent
    gens_vus = {}
    for u in User.query.filter(
            User.id.in_({s["user_id"] for s in seances if s["user_id"]}
                        | {u for v in titulaires.values() for u in v} or {0})).all():
        gens_vus[u.id] = "%s %s" % (u.first_name, u.last_name)
    tous_roles = {r.id: nom_affiche(r, lang) for r in roles}
    for s in seances:
        if s["role_id"] and s["role_id"] not in tous_roles:
            tous_roles[s["role_id"]] = s["role"]

    return {
        "ok": True,
        "aujourdhui": date.today().isoformat(),
        "seances": seances,
        "creneaux": creneaux,
        "roles": [{"id": i, "nom": n} for i, n in
                  sorted(tous_roles.items(), key=lambda kv: (kv[1] or "").lower())],
        "gens": [{"id": i, "nom": n} for i, n in
                 sorted(gens_vus.items(), key=lambda kv: (kv[1] or "").lower())],
    }


@calendrier_bp.route("/", methods=["GET"])
def page():
    if not flask_session.get("user_id"):
        return redirect(url_for("auth.login"))
    acteur = _utilisateur()
    # ⚠️ Premier jet : l'administrateur seul. Le masquage n'est pas une
    # sécurité — l'API refuse de son côté.
    if not is_admin(acteur):
        return redirect(url_for("time_view.page"))
    return render_template("calendrier.html")


@calendrier_bp.route("/api/donnees", methods=["GET"])
def api_donnees():
    acteur = _utilisateur()
    if acteur is None:
        return jsonify({"error": "not_logged_in"}), 401
    if not is_admin(acteur):
        return jsonify({"ok": False, "code": "reserve_admin"}), 403
    return jsonify(donnees_du_calendrier(
        acteur, flask_session.get("lang", "en"))), 200
