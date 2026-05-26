from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_mail import Message
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app
from sqlalchemy.orm.attributes import flag_modified
from Code.models.models import User
from Code.extensions import mail, db

auth_password_bp = Blueprint("auth_password", __name__)


@auth_password_bp.route("/forgot_password", methods=["POST"])
def forgot_password():
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        flash("Adresse email requise.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()

    # Ne pas révéler si l'email existe ou non
    if user:
        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
        token = serializer.dumps(email, salt="password-reset-salt")
        reset_link = url_for("auth_password.reset_password", token=token, _external=True)

        msg = Message(
            subject="Réinitialisation de votre mot de passe DevOPTIQ",
            recipients=[email],
        )
        msg.body = (
            "Bonjour,\n\n"
            "Vous avez demande la reinitialisation de votre mot de passe DevOPTIQ.\n\n"
            f"Cliquez sur ce lien pour choisir un nouveau mot de passe :\n{reset_link}\n\n"
            "Ce lien est valable 1 heure. Si vous n'etes pas a l'origine de cette demande, ignorez cet email.\n\n"
            "--- L'equipe DevOPTIQ"
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
        new_password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(new_password) < 6:
            error = "Le mot de passe doit contenir au moins 6 caracteres."
        elif new_password != confirm:
            error = "Les mots de passe ne correspondent pas."
        else:
            user = User.query.filter_by(email=email).first()
            if user:
                user.password = generate_password_hash(new_password, method="pbkdf2:sha256")
                flag_modified(user, "password")
                db.session.add(user)
                db.session.commit()
                flash("Mot de passe modifie avec succes. Vous pouvez vous connecter.", "success")
                return redirect(url_for("auth.login"))
            else:
                flash("Utilisateur introuvable.", "error")
                return redirect(url_for("auth.login"))

    return render_template("reset_password.html", email=email, error=error)
