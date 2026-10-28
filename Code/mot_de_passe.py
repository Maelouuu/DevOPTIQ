# Code/mot_de_passe.py
"""Tout ce qui encadre un mot de passe : la politique, le jeton de
réinitialisation, la limitation de débit, la révocation des sessions.

⚠️ **Source UNIQUE, et c'est le point.** La politique était écrite à CINQ
endroits (quatre à six caractères, un à huit), et le jeton ne vivait que dans
sa route. Une règle de sécurité répartie finit par ne plus dire la même chose
d'un écran à l'autre, et personne ne s'en aperçoit : rien ne lève d'erreur.

⚠️ **Rien de ce module ne dépend du canal d'envoi.** Le même code sert
l'instance hébergée par AFDEC et l'installation chez le client : seules les
variables `MAIL_*` changent, et elles sont lues par `create_app`.
"""

import hashlib
import hmac
from datetime import datetime, timedelta

from flask import current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified

from Code.extensions import db
from Code.security import hash_password, verify_password

# ── La politique ────────────────────────────────────────────────────────────
#
# ⚠️ Huit, et non six. Six était la valeur de quatre des cinq sites d'appel ;
# l'assistant d'installation, lui, exigeait déjà huit. On aligne vers le HAUT :
# aligner vers le bas aurait affaibli le seul endroit qui était correct.
MIN_LONGUEUR = 8

# ── Le jeton ────────────────────────────────────────────────────────────────
SEL = "password-reset-salt"
VALIDITE_S = 3600                 # une heure, comme avant

# ── La limitation de débit ──────────────────────────────────────────────────
#
# ⚠️ Comptée EN BASE, pas en mémoire. Le motif en mémoire existe déjà dans
# `hub/app.py` (8 essais / 15 min dans un dictionnaire) et il ne tient pas
# ici : Cloud Run redescend à zéro instance et en relance plusieurs, chacune
# avec son propre dictionnaire — le compteur repart à zéro à volonté.
FENETRE_S = 900
MAX_PAR_ADRESSE = 3
MAX_PAR_IP = 10


def _norm(email):
    return (email or "").strip().lower()


def _sha(valeur):
    return hashlib.sha256((valeur or "").encode("utf-8")).hexdigest()


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def empreinte(hash_stocke):
    """Une signature courte du hash COURANT du mot de passe.

    C'est elle qui rend un lien caduc dès que le mot de passe change — par
    quelque chemin que ce soit, y compris une réinitialisation posée par un
    administrateur depuis la page Comptes.
    """
    return _sha(hash_stocke)[:16]


# ══════════════════════════════════════════════════════════════════════════
#  La politique
# ══════════════════════════════════════════════════════════════════════════

def valider(mot_de_passe):
    """Rend None si le mot de passe est acceptable, sinon un code de refus."""
    if len(mot_de_passe or "") < MIN_LONGUEUR:
        return "pwd_trop_court"
    return None


# ══════════════════════════════════════════════════════════════════════════
#  Écrire un mot de passe
# ══════════════════════════════════════════════════════════════════════════

def poser(user, clair):
    """Écrit le hash, horodate le changement, puis RELIT la base.

    Rend True seulement si le nouveau mot de passe est bien celui qui se
    trouve en base après le commit.

    ⚠️ La relecture n'est pas une précaution de confort : un UPDATE peut
    échouer sans lever (colonne trop étroite — c'est arrivé en production avec
    les hashes scrypt), et annoncer un succès qui n'a pas été persisté laisse
    quelqu'un dehors avec un mot de passe qu'il croit avoir changé.

    ⚠️ `password_changed_at` est ce qui ferme les sessions ouvertes ailleurs.
    Il ne se pose QUE lorsque la valeur du mot de passe change — jamais lors du
    re-hachage transparent du login, qui déconnecterait tout le monde à sa
    propre connexion.
    """
    user.password = hash_password(clair)
    flag_modified(user, "password")
    user.password_changed_at = datetime.utcnow()
    db.session.add(user)
    db.session.commit()
    stocke = db.session.execute(
        text("SELECT password FROM users WHERE id = :u"), {"u": user.id}
    ).scalar()
    return verify_password(stocke, clair)


# ══════════════════════════════════════════════════════════════════════════
#  Les sessions
# ══════════════════════════════════════════════════════════════════════════

def empreinte_session(user):
    """Ce que le login pose en session pour qu'un changement de mot de passe
    ferme les sessions restées ouvertes ailleurs."""
    at = getattr(user, "password_changed_at", None)
    return at.isoformat() if at else None


def regle_session_perimee(user, valeur_en_session):
    """La session en cours a-t-elle été ouverte avant le dernier changement ?

    ⚠️ Une session SANS empreinte est ACCEPTÉE tant que le compte n'a jamais
    changé de mot de passe depuis la livraison : sinon la mise en service
    déconnecterait tout le monde d'un coup, sans que personne comprenne
    pourquoi. Dès le premier changement, l'absence devient une péremption —
    et c'est exactement le moment où elle doit l'être.
    """
    attendu = empreinte_session(user)
    if attendu is None:
        return False
    return (valeur_en_session or "") != attendu


# ⚠️ Le nom que la porte de `create_app` appelle. Il est séparé de la RÈGLE
# ci-dessus pour une raison précise : le décor de tests remplace celui-ci (une
# trentaine de fichiers posent `session['user_id']` à la main, sans empreinte
# — voir `tests/conftest.py`), et la règle doit rester éprouvable telle
# qu'elle tourne en production. Ne jamais appeler `regle_session_perimee`
# depuis l'application : le décor ne pourrait plus rien tolérer.
session_perimee = regle_session_perimee


# ══════════════════════════════════════════════════════════════════════════
#  Le débit
# ══════════════════════════════════════════════════════════════════════════

def debit_depasse(email, ip=None):
    """Trop de demandes pour cette adresse, ou depuis cette adresse IP ?

    ⚠️ Le compte par ADRESSE porte sur l'adresse SAISIE, qu'elle corresponde
    ou non à un compte : compter seulement les envois réels dirait, par le
    simple fait de ne pas compter, que l'adresse est inconnue.
    """
    from Code.models.models import PasswordReset
    depuis = datetime.utcnow() - timedelta(seconds=FENETRE_S)
    recentes = PasswordReset.query.filter(PasswordReset.cree_le >= depuis)
    if recentes.filter_by(email_hash=_sha(_norm(email))).count() >= MAX_PAR_ADRESSE:
        return True
    if ip and recentes.filter_by(ip_hash=_sha(ip)).count() >= MAX_PAR_IP:
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════
#  Le jeton de réinitialisation
# ══════════════════════════════════════════════════════════════════════════

def tracer_demande(email, ip=None, user=None, jeton=None):
    """Une ligne par demande — connue ou non, envoyée ou non.

    C'est elle qui porte à la fois la limitation de débit et la trace d'audit
    (« qui a demandé une réinitialisation, quand, et l'a-t-il utilisée »).
    """
    from Code.models.models import PasswordReset
    ligne = PasswordReset(
        user_id=user.id if user is not None else None,
        email_hash=_sha(_norm(email)),
        jeton_hash=_sha(jeton) if jeton else None,
        ip_hash=_sha(ip) if ip else None,
        expire_le=(datetime.utcnow() + timedelta(seconds=VALIDITE_S)) if jeton else None,
    )
    db.session.add(ligne)
    db.session.commit()
    return ligne


def fabriquer_jeton(user, email, ip=None):
    """Le lien de réinitialisation, et sa ligne en base."""
    jeton = _serializer().dumps({"u": user.id, "e": empreinte(user.password)}, salt=SEL)
    tracer_demande(email, ip=ip, user=user, jeton=jeton)
    return jeton


def lire_jeton(jeton):
    """Rend `(user, ligne)` si le lien est bon, sinon `(None, code_de_refus)`.

    **Trois verrous — et il faut dire lequel fait quoi**, parce que le banc
    de cliquets l'a corrigé : en retirant le verrou 3, aucun test de rejeu ne
    rougissait.

    1. la signature et l'âge — c'est tout ce que faisait la version d'avant ;
    2. l'empreinte du mot de passe COURANT. **C'est LUI qui interdit le
       rejeu**, et il le fait seul : chaque écriture re-sale le hash, donc
       même reposer le MÊME mot de passe change l'empreinte. Il couvre aussi
       le changement par un autre chemin (un administrateur depuis la page
       Comptes) et vaut même si la ligne en base a disparu ;
    3. la ligne en base. Elle n'est pas un second verrou contre le rejeu :
       elle exige qu'une demande ait été **réellement enregistrée** — un
       jeton ressorti après la purge, ou fabriqué par un autre chemin de
       code, ne passe pas — et c'est elle qui porte la limitation de débit et
       la trace d'audit (`utilise_le`).

    ⚠️ Un jeton de l'ancien format (sa charge était l'adresse e-mail, en
    clair) est refusé. C'est voulu, et sans conséquence : l'envoi d'e-mail n'a
    jamais été configuré, personne n'en détient un.
    """
    from Code.models.models import PasswordReset, User
    try:
        charge = _serializer().loads(jeton, salt=SEL, max_age=VALIDITE_S)
    except SignatureExpired:
        return None, "pwd_lien_expire"
    except BadSignature:
        return None, "pwd_lien_invalide"

    if not isinstance(charge, dict):
        return None, "pwd_lien_invalide"
    user = db.session.get(User, int(charge.get("u") or 0))
    if user is None:
        return None, "pwd_lien_invalide"

    if not hmac.compare_digest(str(charge.get("e") or ""), empreinte(user.password)):
        return None, "pwd_lien_utilise"

    ligne = PasswordReset.query.filter_by(jeton_hash=_sha(jeton)).first()
    if ligne is None:
        return None, "pwd_lien_invalide"
    if ligne.utilise_le is not None:
        return None, "pwd_lien_utilise"
    if ligne.expire_le and ligne.expire_le < datetime.utcnow():
        return None, "pwd_lien_expire"
    return user, ligne


def consommer(ligne):
    """Marque la demande comme utilisée. Appelé APRÈS l'écriture réussie."""
    ligne.utilise_le = datetime.utcnow()
    db.session.add(ligne)
    db.session.commit()


def purger(jours=90):
    """Les demandes anciennes n'ont plus d'usage : ni débit, ni audit utile.

    Appelé au démarrage, comme les purges d'OptiqPulse. Toute erreur est
    avalée : une purge n'empêche pas une application de démarrer.
    """
    from Code.models.models import PasswordReset
    try:
        limite = datetime.utcnow() - timedelta(days=jours)
        n = PasswordReset.query.filter(PasswordReset.cree_le < limite).delete()
        db.session.commit()
        return n
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return 0
