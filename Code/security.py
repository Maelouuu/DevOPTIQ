# Code/security.py
# Politique de hachage des mots de passe OptiqFluent.
#
# Standard : PBKDF2-HMAC-SHA256, 600 000 itérations (recommandation OWASP).
# Le hash produit (~102 caractères) tient dans toutes les variantes historiques
# de la colonne users.password, contrairement au scrypt par défaut de
# Werkzeug 3 (~162 caractères) qui dépasse une colonne VARCHAR trop étroite
# créée avant l'agrandissement du modèle — l'UPDATE échoue alors en PostgreSQL
# et l'ancien mot de passe reste actif.
#
# verify_password() accepte tous les formats historiques gérés par Werkzeug
# (scrypt, pbkdf2…) ; needs_rehash() permet de migrer les anciens hashes vers
# le standard au fil des connexions réussies.

from werkzeug.security import generate_password_hash, check_password_hash

PASSWORD_HASH_METHOD = "pbkdf2:sha256:600000"


def hash_password(password: str) -> str:
    return generate_password_hash(password, method=PASSWORD_HASH_METHOD)


def verify_password(stored_hash: str, password: str) -> bool:
    if not stored_hash or not password:
        return False
    try:
        return check_password_hash(stored_hash, password)
    except Exception:
        return False


def needs_rehash(stored_hash: str) -> bool:
    return not (stored_hash or "").startswith(PASSWORD_HASH_METHOD + "$")
