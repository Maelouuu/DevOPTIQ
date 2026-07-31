# Bascule du fournisseur IA : OpenAI → Claude (Anthropic)

L'app parle désormais à son fournisseur IA via **un client unique**
(`Code/ai_client.py`) : même interface OpenAI `chat.completions` partout,
mais le fournisseur est interchangeable — Claude passe par le **point d'accès
compatible OpenAI d'Anthropic** (aucune dépendance nouvelle).

## Comment basculer (et revenir en arrière)

| Réglage | Effet |
|---|---|
| *(rien)* | Comportement historique : OpenAI + `gpt-4o-mini`. |
| `ANTHROPIC_API_KEY=sk-ant-…` (env) ou clé en base | **Bascule sur Claude** (`claude-haiku-4-5-20251001`, même gamme coût/latence que 4o-mini). |
| `AI_PROVIDER=openai` / `anthropic` | Force un fournisseur (sinon `auto`). |
| `AI_MODEL=…` | Force un modèle précis (ex. `claude-sonnet-5` pour monter en qualité). |

Retirer la clé (ou `AI_PROVIDER=openai`) = retour immédiat à l'existant.

## Mesurer AVANT de basculer : `run_compare.py`

Le banc rejoue les **vrais prompts de l'app** (propositions savoirs /
savoir-faire / HSC X50-766, chatbot création d'activité, traduction HSC,
qualification des sorties) sur les deux fournisseurs et vérifie ce qui est
objectivable :

- **JSON exploitable** par le front (parse + clés attendues) ;
- **volumétrie** (nombre d'items dans les fourchettes que l'UI affiche) ;
- **langue** (réponse en français) ;
- **latence** par appel.

```bash
OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-... \
    python tools/ai_eval/run_compare.py
```

Sortie : synthèse en console + **`tools/ai_eval/report.html`** avec toutes les
réponses **côte à côte**, cas par cas — c'est là que se juge la pertinence
métier fine (l'œil humain reste le juge de paix).

## Si la qualité ne suffit pas

Deux curseurs, sans toucher au code :
1. `AI_MODEL=claude-sonnet-5` — modèle plus capable (coût supérieur) ;
2. ajuster le prompt concerné dans `Code/prompts/catalog.py` (les prompts
   sont centralisés — jamais en dur dans les routes).

Relancer le banc après chaque ajustement pour objectiver le gain.
