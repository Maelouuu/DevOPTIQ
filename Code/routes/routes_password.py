"""« Mot de passe oublié » — la demande, et la pose du nouveau mot de passe.

Les règles ne vivent PAS ici : elles sont dans `Code/mot_de_passe.py` (la
politique, le jeton, le débit, la révocation des sessions), parce que la page
Comptes et l'assistant d'installation les appliquent aussi. Cette route ne
fait que l'enchaînement et les messages.

⚠️ **Un seul message de retour à une demande.** Qu'elle aboutisse ou non, la
réponse est `pwd.sent`. La version d'avant avait le bon message neutre… et un
`try/except` d'envoi À L'INTÉRIEUR du `if user:` — « Erreur lors de l'envoi »
ne pouvait donc apparaître que si le compte existait. Le message neutre était
annulé par son voisin.
"""

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app)
from flask_mail import Message

from Code import mot_de_passe as mdp
from Code.extensions import mail, db
from Code.models.models import User
from Code.translations import t

auth_password_bp = Blueprint("auth_password", __name__)


def _find_user_by_email(email):
    """Recherche exacte puis insensible à la casse (les adresses saisies avec
    des majuscules historiques ne doivent pas faire échouer le reset en
    silence)."""
    from sqlalchemy import func
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User.query.filter(func.lower(User.email) == (email or "").lower()).first()
    return user


def _ip_client():
    """L'adresse du demandeur, pas celle du répartiteur de charge.

    ⚠️ Derrière Cloud Run, `request.remote_addr` est l'IP du frontend Google :
    la prendre ferait compter TOUTES les demandes de tout le monde sur une
    seule adresse, et la limite par IP verrouillerait l'instance entière au
    dixième essai. Le vrai client est la première entrée de
    `X-Forwarded-For`.

    ⚠️ Cet en-tête est falsifiable : il ne sert QU'à la limitation de débit,
    jamais à une décision d'accès. La protection qui compte est celle par
    adresse e-mail, que le demandeur ne choisit pas librement.
    """
    xff = request.headers.get("X-Forwarded-For") or ""
    premier = xff.split(",")[0].strip()
    return premier or (request.remote_addr or "")


@auth_password_bp.route("/forgot_password", methods=["POST"])
def forgot_password():
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        flash(t("pwd.need_email"), "error")
        return redirect(url_for("auth.login"))

    if not current_app.config.get("MAIL_CONFIGURED"):
        flash(t("pwd.mail_off"), "error")
        return redirect(url_for("auth.login"))

    ip = _ip_client()
    if mdp.debit_depasse(email, ip):
        # Dire « trop de demandes » ne révèle rien : le compte est tenu sur
        # l'adresse SAISIE, qu'elle corresponde à un compte ou pas.
        flash(t("pwd.too_many"), "error")
        return redirect(url_for("auth.login"))

    user = _find_user_by_email(email)
    if user is None:
        # On trace quand même : sans cette ligne, la limitation par adresse ne
        # compterait que les adresses connues, et ne pas être ralenti
        # suffirait à déduire qu'une adresse est inconnue.
        mdp.tracer_demande(email, ip=ip)
    else:
        jeton = mdp.fabriquer_jeton(user, email, ip=ip)
        lien = url_for("auth_password.reset_password", token=jeton, _external=True)
        langue = getattr(user, "lang", None) or "en"
        message = Message(subject=t("pwd.mail_subject", langue), recipients=[user.email])
        # ⚠️ Le corps est dans la langue DU DESTINATAIRE (`user.lang`), pas
        # dans celle de la session : la demande part d'un écran de connexion,
        # où personne n'est identifié.
        message.body = t("pwd.mail_body", langue).replace("[[lien]]", lien)
        try:
            mail.send(message)
        except Exception as e:
            # Le message rendu est le même qu'en cas de succès — voir l'en-tête
            # du module. L'incident part au journal, pas à l'écran.
            current_app.logger.error("[MAIL] envoi reset impossible (user %s) : %s",
                                     user.id, e)

    flash(t("pwd.sent"), "success")
    return redirect(url_for("auth.login"))


@auth_password_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    # Un mappage explicite, pas une transformation de chaîne : une clé
    # fabriquée au vol s'affiche telle quelle quand elle n'existe pas, sans
    # qu'aucune erreur ne soit levée.
    MESSAGE = {"pwd_lien_expire":   "pwd.lien_expire",
               "pwd_lien_invalide": "pwd.lien_invalide",
               "pwd_lien_utilise":  "pwd.lien_utilise"}

    user, suite = mdp.lire_jeton(token)
    if user is None:
        flash(t(MESSAGE.get(suite, "pwd.lien_invalide")), "error")
        return redirect(url_for("auth.login"))
    ligne = suite

    error = None
    if request.method == "POST":
        nouveau = (request.form.get("password") or "").strip()
        confirme = (request.form.get("confirm_password") or "").strip()
        refus = mdp.valider(nouveau)
        if refus:
            error = t("reset_pwd.err_too_short")
        elif nouveau != confirme:
            error = t("reset_pwd.err_mismatch")
        else:
            try:
                enregistre = mdp.poser(user, nouveau)
            except Exception as e:
                db.session.rollback()
                current_app.logger.error("[RESET_PWD] commit impossible : %s", e)
                error = t("pwd.err_server")
            else:
                if enregistre:
                    # ⚠️ APRÈS l'écriture, jamais avant : consommer d'abord
                    # brûlerait le lien sur une erreur de saisie.
                    mdp.consommer(ligne)
                    flash(t("pwd.done"), "success")
                    return redirect(url_for("auth.login"))
                current_app.logger.error("[RESET_PWD] hash non persisté (user %s)", user.id)
                error = t("pwd.err_not_saved")

    return render_template("reset_password.html", email=user.email, error=error)
