from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
from Code.models.models import User
from Code.extensions import mail, db
from Code.security import hash_password, verify_password

auth_password_bp = Blueprint("auth_password", __name__)


def _find_user_by_email(email):
    """Recherche exacte puis insensible à la casse (les emails saisis avec des
    majuscules historiques ne doivent pas faire échouer silencieusement le reset)."""
    from sqlalchemy import func
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User.query.filter(func.lower(User.email) == (email or "").lower()).first()
    return user


@auth_password_bp.route("/forgot_password", methods=["POST"])
def forgot_password():
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        flash("Adresse email requise.", "error")
        return redirect(url_for("auth.login"))

    if not current_app.config.get("MAIL_CONFIGURED"):
        flash("L'envoi d'email n'est pas configuré sur cette instance. "
              "Contactez votre administrateur pour réinitialiser votre mot de passe.", "error")
        return redirect(url_for("auth.login"))

    user = _find_user_by_email(email)

    # Ne pas révéler si l'email existe ou non
    if user:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        token = serializer.dumps(email, salt="password-reset-salt")
        reset_link = url_for("auth_password.reset_password", token=token, _external=True)

        msg = Message(
            subject="Réinitialisation de votre mot de passe OptiqFluent",
            recipients=[email],
        )
        msg.body = (
            "Bonjour,\n\n"
            "Vous avez demande la reinitialisation de votre mot de passe OptiqFluent.\n\n"
            f"Cliquez sur ce lien pour choisir un nouveau mot de passe :\n{reset_link}\n\n"
            "Ce lien est valable 1 heure. Si vous n'etes pas a l'origine de cette demande, ignorez cet email.\n\n"
            "--- L'equipe OptiqFluent"
        )
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error("[MAIL] Erreur envoi reset password: %s", e)
            flash("Erreur lors de l'envoi de l'email. Reessayez dans quelques instants.", "error")
            return redirect(url_for("auth.login"))

    flash("Si cette adresse correspond a un compte, un email de reinitialisation a ete envoye.", "success")
    return redirect(url_for("auth.login"))


@auth_password_bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except SignatureExpired:
        flash("Ce lien a expire. Faites une nouvelle demande.", "error")
        return redirect(url_for("auth.login"))
    except BadSignature:
        flash("Lien invalide ou deja utilise.", "error")
        return redirect(url_for("auth.login"))

    error = None
    if request.method == "POST":
        new_password = (request.form.get("password") or "").strip()
        confirm      = (request.form.get("confirm_password") or "").strip()
        if len(new_password) < 6:
            error = "Le mot de passe doit contenir au moins 6 caracteres."
        elif new_password != confirm:
            error = "Les mots de passe ne correspondent pas."
        else:
            user = _find_user_by_email(email)
            if user:
                try:
                    user.password = hash_password(new_password)
                    flag_modified(user, "password")
                    db.session.add(user)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error("[RESET_PWD] Erreur commit: %s", e)
                    error = "Erreur serveur lors de la mise à jour. Réessayez."
                else:
                    # Vérification post-commit : relire le hash en base pour ne
                    # jamais annoncer un succès qui n'a pas été persisté.
                    stored = db.session.execute(
                        text("SELECT password FROM users WHERE id = :uid"), {"uid": user.id}
                    ).scalar()
                    if verify_password(stored, new_password):
                        flash("Mot de passe modifie avec succes. Vous pouvez vous connecter.", "success")
                        return redirect(url_for("auth.login"))
                    current_app.logger.error("[RESET_PWD] Hash non persisté pour user %s", user.id)
                    error = "La modification n'a pas été persistée. Réessayez ou contactez l'administrateur."
            else:
                flash("Utilisateur introuvable.", "error")
                return redirect(url_for("auth.login"))

    return render_template("reset_password.html", email=email, error=error)
