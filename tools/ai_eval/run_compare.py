"""Banc de comparaison OpenAI ↔ Claude sur les VRAIS prompts de l'application.

Objectif : mesurer, avant de basculer le fournisseur IA, que la qualité des
réponses est au moins équivalente — sur les critères objectivables :
  - validité du format (JSON exploitable par le front, clés attendues),
  - volumétrie (nombre d'items dans les fourchettes attendues par l'UI),
  - langue (réponse en français),
  - latence.
Le reste (pertinence métier fine) se juge à l'œil : le rapport HTML met les
réponses côte à côte, cas par cas.

Usage :
    OPENAI_API_KEY=sk-...  ANTHROPIC_API_KEY=sk-ant-...  \
        python tools/ai_eval/run_compare.py
    → tools/ai_eval/report.html + synthèse en console

Un seul des deux fournisseurs configuré → le banc tourne quand même (une
colonne). Modèles : gpt-4o-mini vs claude-haiku-4-5 (surchargables par
AI_EVAL_OPENAI_MODEL / AI_EVAL_ANTHROPIC_MODEL).
"""
import html
import json
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(BASE, '..', '..'))
sys.path.insert(0, REPO)

from Code.prompts import get_prompt  # noqa: E402

# ── Contexte d'activité réaliste, partagé par tous les cas ──────────────────
CTX = """# Activité
Analyse de faisabilité

# Description
Étudier la faisabilité technique et économique d'une demande client avant
l'établissement de l'offre : analyse du besoin, vérification des capacités
machines, estimation des coûts et des délais.

# Données entrantes
- Lancement de l'analyse de faisabilité (déclenchante)
- Liste des composants (nourrissante)
- REX des projets précédents (nourrissante)

# Données sortantes
- Lancement pré-projet
- Offre à réaliser

# Outils
- ERP OptiFab
- Banc de test labo

# Contraintes
- Répondre au client sous 5 jours ouvrés

# Tâches
- Analyser le besoin client
- Vérifier la capacité machines
- Estimer coûts et délais
"""

FR_HINT = re.compile(r"[àâéèêëîïôùûçœ]|\b(le|la|les|des|une|pour|avec|dans)\b", re.I)


def looks_french(text):
    return len(FR_HINT.findall(text or '')) >= 5


def parse_json(text):
    t = (text or '').strip()
    if t.startswith('```'):
        t = re.sub(r'^```[a-z]*\n?', '', t)
        t = re.sub(r'\n?```$', '', t)
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r'[\[{].*[\]}]', t, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


# ── Les cas : (nom, messages, json_mode, fonction de contrôle) ─────────────
def check_items_list(payload, key, lo, hi):
    def chk(data):
        if data is None:
            return 'JSON invalide'
        items = data.get(key) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return f'liste « {key} » absente'
        if not (lo <= len(items) <= hi):
            return f'{len(items)} items (attendu {lo}–{hi})'
        return None
    return chk


def build_cases():
    cases = []

    sysfr = get_prompt('propose.system.fr')

    cases.append(('Proposer des savoirs',
                  [{'role': 'system', 'content': sysfr},
                   {'role': 'user', 'content': get_prompt('propose.savoirs.header.fr') + '\n\n' + CTX}],
                  True, check_items_list, ('items', 3, 10)))

    cases.append(('Proposer des savoir-faire',
                  [{'role': 'system', 'content': sysfr},
                   {'role': 'user', 'content': get_prompt('propose.savoir_faires.header.fr') + '\n\n' + CTX}],
                  True, check_items_list, ('items', 3, 10)))

    cases.append(('Proposer des HSC (X50-766)',
                  [{'role': 'system', 'content': sysfr},
                   {'role': 'user', 'content': get_prompt('propose.softskills.header.fr')
                    + '\n\n' + get_prompt('referential.x50_766.fr') + '\n\n' + CTX}],
                  True, check_items_list, ('items', 3, 10)))

    cases.append(('Chatbot — créer une activité',
                  [{'role': 'system', 'content': get_prompt('chatbot.system.fr')},
                   {'role': 'user', 'content': get_prompt('chatbot.mode_creer.fr')
                    + "\n\nJe veux créer une activité « Contrôle qualité réception » "
                      "pour un site industriel : contrôler les pièces reçues des "
                      "fournisseurs avant mise en stock."}],
                  True, None, None))

    cases.append(('Traduire un texte libre en HSC',
                  [{'role': 'user', 'content': get_prompt('translate.hsc.fr',
                    texte="Il faut savoir garder son calme quand le client s'énerve, "
                          "bien expliquer les choses simplement, et être capable de "
                          "travailler avec l'atelier comme avec le commercial.")}],
                  True, None, None))

    cases.append(('Qualifier des sorties (RESULT/…)',
                  [{'role': 'system', 'content': get_prompt('qualify.system.fr')},
                   {'role': 'user', 'content': 'Activité : Analyse de faisabilité\n'
                    'Sorties à qualifier :\n- Lancement pré-projet\n- Offre à réaliser\n- Compte rendu mensuel'}],
                  True, None, None))

    return [c for c in cases if c[1][0]['content'] is not None]


PROVIDERS = {
    'openai': {
        'key': os.getenv('OPENAI_API_KEY'),
        'base': None,
        'model': os.getenv('AI_EVAL_OPENAI_MODEL', 'gpt-4o-mini'),
    },
    'anthropic': {
        'key': os.getenv('ANTHROPIC_API_KEY'),
        'base': 'https://api.anthropic.com/v1/',
        'model': os.getenv('AI_EVAL_ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001'),
    },
}


def run_provider(name, conf, cases):
    from openai import OpenAI
    kwargs = {'api_key': conf['key'], 'timeout': 90}
    if conf['base']:
        kwargs['base_url'] = conf['base']
    client = OpenAI(**kwargs)
    out = []
    for (title, messages, json_mode, chk, chk_args) in cases:
        t0 = time.time()
        try:
            req = {'model': conf['model'], 'messages': messages, 'temperature': 0.2}
            if json_mode:
                req['response_format'] = {'type': 'json_object'}
            resp = client.chat.completions.create(**req)
            text = resp.choices[0].message.content
            err = None
        except Exception as e:
            text, err = '', f'ERREUR APPEL : {e}'
        dt = time.time() - t0
        data = parse_json(text) if not err else None
        checks = []
        if not err:
            checks.append(('JSON exploitable', data is not None))
            if chk:
                verdict = chk(*chk_args)(data) if chk_args else chk(data)
                checks.append(('structure attendue' + (f' — {verdict}' if verdict else ''),
                               verdict is None))
            checks.append(('réponse en français', looks_french(text)))
        out.append({'title': title, 'model': conf['model'], 'latency': dt,
                    'text': text, 'error': err, 'checks': checks})
        state = 'OK' if not err and all(ok for _, ok in checks) else 'ÉCART'
        print(f'  [{name}] {title:<38} {dt:5.1f}s  {state}')
    return out


def main():
    cases = build_cases()
    if not cases:
        print('Prompts indisponibles (catalogue non déchiffré ?) — abandon.')
        sys.exit(2)
    results = {}
    for name, conf in PROVIDERS.items():
        if not conf['key']:
            print(f'· {name} : pas de clé ({name.upper()}_API_KEY) — ignoré')
            continue
        print(f'▶ {name} ({conf["model"]}) — {len(cases)} cas')
        results[name] = run_provider(name, conf, cases)

    if not results:
        print('Aucune clé fournie — rien à comparer.')
        sys.exit(2)

    # ── Rapport HTML côte à côte ──
    cols = list(results.keys())
    rows = []
    for i, (title, *_rest) in enumerate(cases):
        cells = ''
        for c in cols:
            r = results[c][i]
            badge = ''.join(
                f'<span class="b {"ok" if ok else "ko"}">{html.escape(lbl)}</span>'
                for lbl, ok in r['checks'])
            body = html.escape(r['error'] or r['text'] or '(vide)')
            cells += (f'<td><div class="meta">{r["model"]} · {r["latency"]:.1f}s {badge}</div>'
                      f'<pre>{body}</pre></td>')
        rows.append(f'<tr><th>{html.escape(title)}</th>{cells}</tr>')

    summary = ''
    for c in cols:
        n = len(results[c])
        ok = sum(1 for r in results[c] if not r['error'] and all(o for _, o in r['checks']))
        lat = sum(r['latency'] for r in results[c]) / max(n, 1)
        summary += (f'<tr><td>{c}</td><td>{results[c][0]["model"]}</td>'
                    f'<td>{ok}/{n}</td><td>{lat:.1f}s</td></tr>')
        print(f'► {c} : {ok}/{n} cas conformes, latence moyenne {lat:.1f}s')

    doc = f"""<!DOCTYPE html><html lang="fr"><meta charset="utf-8">
<title>Comparaison IA — OpenAI vs Claude</title>
<style>
body{{font-family:'DM Sans',system-ui,sans-serif;margin:24px;color:#0f172a;background:#f2f4f9}}
h1{{font-size:22px}} table{{border-collapse:collapse;width:100%;background:#fff}}
th,td{{border:1px solid #e2e8f0;padding:10px;vertical-align:top;text-align:left}}
pre{{white-space:pre-wrap;font-size:11.5px;max-height:340px;overflow:auto;margin:6px 0 0}}
.meta{{font-size:12px;color:#64748b}}
.b{{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11px;font-weight:600;margin-left:6px}}
.b.ok{{background:#dcfce7;color:#15803d}} .b.ko{{background:#fee2e2;color:#b91c1c}}
.sum td{{font-weight:600}}
</style>
<h1>Comparaison des fournisseurs IA sur les prompts réels de l'app</h1>
<p>Critères automatiques : JSON exploitable, structure/volumétrie attendue par
l'interface, réponse en français, latence. La pertinence métier se juge en
lisant les colonnes côte à côte.</p>
<table class="sum"><tr><th>Fournisseur</th><th>Modèle</th><th>Cas conformes</th><th>Latence moy.</th></tr>{summary}</table>
<br>
<table><tr><th>Cas</th>{''.join(f'<th>{c}</th>' for c in cols)}</tr>{''.join(rows)}</table>
</html>"""
    out = os.path.join(BASE, 'report.html')
    open(out, 'w', encoding='utf-8').write(doc)
    print('Rapport →', out)


if __name__ == '__main__':
    main()
