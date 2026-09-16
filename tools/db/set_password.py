"""Pose (ou crée) un compte avec un mot de passe connu, sur une base donnée.

    DATABASE_URL="postgresql://…" python tools/db/set_password.py \
        --email mael.pierre.girardin@icloud.com --password testtest --admin

Sert après une restauration : les comptes reviennent avec le mot de passe
qu'ils avaient au moment de la sauvegarde, que personne ne connaît forcément.

Deux précautions qui ont leur histoire :

  * le hachage passe par `Code/security.py` — jamais `generate_password_hash`
    en direct : c'est là que vit la politique (PBKDF2-SHA256, 600 000 tours) ;
  * le mot de passe est **relu depuis la base après le commit** et vérifié.
    Une colonne trop étroite tronquait silencieusement le hash : l'écriture
    « réussissait » et l'ancien mot de passe restait actif. Un faux succès sur
    un mot de passe est pire que pas de mot de passe du tout.
"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("DATABASE_URL"),
                    help="chaîne de connexion (défaut : $DATABASE_URL)")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--admin", action="store_true",
                    help="force le statut administrateur")
    ap.add_argument("--lang", default=None, help="fr | en")
    args = ap.parse_args()
    if not args.url:
        ap.error("aucune URL : passez --url ou définissez DATABASE_URL")

    os.environ["DATABASE_URL"] = args.url
    sys.path.insert(0, os.getcwd())

    from Code.app import create_app
    from Code.extensions import db
    from Code.models.models import User, default_lang_for
    from Code.security import hash_password, verify_password

    email = args.email.strip().lower()
    app = create_app()
    with app.app_context():
        u = User.query.filter(db.func.lower(User.email) == email).first()
        if u is None:
            prenom, _, nom = args.email.partition("@")[0].partition(".")[0], None, ""
            u = User(first_name=prenom.capitalize() or "Compte", last_name=nom or "",
                     email=args.email.strip(),
                     status="administrateur" if args.admin else "user",
                     lang=args.lang or default_lang_for(email))
            db.session.add(u)
            action = "créé"
        else:
            action = "mis à jour"
            if args.admin:
                u.status = "administrateur"
            if args.lang:
                u.lang = args.lang
        u.password = hash_password(args.password)
        db.session.commit()

        relu = User.query.filter(db.func.lower(User.email) == email).first()
        ok = verify_password(relu.password, args.password)
        print("compte %s : %s (id=%s, statut « %s », langue %s)"
              % (action, relu.email, relu.id, relu.status, relu.lang))
        print("mot de passe relu en base et vérifié : %s" % ("OUI" if ok else "NON"))
        if not ok:
            raise SystemExit("le hash enregistré ne valide pas le mot de passe — "
                             "colonne trop étroite ?")


if __name__ == "__main__":
    sys.exit(main())
