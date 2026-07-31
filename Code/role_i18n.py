# Code/role_i18n.py
# Affichage des noms de rôles selon la langue de l'interface.
#
# Principe : `Role.name` reste la saisie d'origine (jamais réécrite par la
# traduction). Les colonnes `name_fr` / `name_en` sont des caches d'affichage :
# - à la création / au renommage, le nom saisi est posé dans le cache de la
#   langue courante de l'interface (langue d'origine) et l'autre cache est vidé ;
# - à l'affichage dans l'autre langue, le cache manquant est rempli par IA
#   (gpt-4o-mini, comme les autres fonctions IA de l'app) puis persisté ;
# - sans clé OpenAI ou en cas d'échec, on affiche le nom d'origine tel quel
#   (jamais de texte inventé), sans mettre en cache.

import json

from flask import session

from Code.extensions import db

SUPPORTED_LANGS = ('fr', 'en')

_LANG_LABEL = {'fr': 'français', 'en': 'anglais'}


def current_lang():
    try:
        lang = session.get('lang', 'fr')
    except Exception:
        lang = 'fr'
    return lang if lang in SUPPORTED_LANGS else 'fr'


def on_role_name_saved(role, name=None, lang=None):
    """À appeler à la création ou au renommage d'un rôle.

    Le nom saisi devient la référence dans la langue courante ; le cache de
    l'autre langue est invalidé et sera retraduit au prochain affichage.
    """
    if name is not None:
        role.name = name
    lang = lang or current_lang()
    role.name_fr = None
    role.name_en = None
    setattr(role, 'name_' + lang, role.name)


def display_names(roles, lang=None):
    """Retourne {role_id: nom affiché} pour la langue demandée.

    Remplit (et persiste) les caches manquants via l'IA quand c'est possible ;
    sinon retombe sur le nom d'origine.
    """
    lang = lang or current_lang()
    result = {}
    missing = []
    for r in roles:
        cached = getattr(r, 'name_' + lang, None)
        if cached:
            result[r.id] = cached
        else:
            missing.append(r)

    if missing:
        translated = _translate_batch([r.name for r in missing], lang)
        if translated and len(translated) == len(missing):
            for r, tr in zip(missing, translated):
                tr = (str(tr or '')).strip() or r.name
                setattr(r, 'name_' + lang, tr[:200])
                result[r.id] = tr[:200]
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        else:
            for r in missing:
                result[r.id] = r.name
    return result


def display_name(role, lang=None):
    return display_names([role], lang).get(role.id, role.name)


def _translate_batch(names, lang):
    """Traduit une liste de noms de rôles vers `lang` via OpenAI.

    Retourne une liste de même longueur, ou None si l'IA est indisponible.
    Un nom déjà dans la langue cible doit revenir inchangé (consigne du prompt).
    """
    if not names:
        return []
    from Code.routes.propose_common import openai_client_or_none, ai_model
    client, _err = openai_client_or_none()
    if client is None:
        return None

    target = _LANG_LABEL.get(lang, lang)
    prompt = (
        "Tu traduis des intitulés de rôles professionnels d'une organisation "
        f"vers le {target}. Réponds UNIQUEMENT avec un objet JSON de la forme "
        '{"translations": ["...", "..."]} contenant exactement une traduction '
        "par intitulé, dans le même ordre. Règles :\n"
        f"- Si un intitulé est déjà en {target}, renvoie-le strictement inchangé.\n"
        "- Conserve les sigles, noms propres et codes tels quels.\n"
        "- Reste concis : un intitulé de poste, pas une phrase.\n\n"
        "Intitulés : " + json.dumps(names, ensure_ascii=False)
    )
    try:
        resp = client.chat.completions.create(
            model=ai_model(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(resp.choices[0].message.content)
        translations = data.get("translations")
        if isinstance(translations, list) and len(translations) == len(names):
            return translations
    except Exception:
        pass
    return None
