# Banc d'essai visuel OptiqCarto (`tests/carto/`)

Pilote le **vrai** éditeur (`static/optiqcarto/editor.js`) sur une carto d'import
VSDX, exécute l'agencement automatique réel (`_computeAutoLayout`) et rend le SVG
final — pour **valider chaque changement en capture avant de pousser**, au lieu de
juger à l'aveugle.

> **Carto de référence : `Code/hard.vsdx`** (165 formes, 243 flèches, 14 bandes,
> 19 losanges décoratifs, graphe dense et cyclique). C'est la carto sur laquelle on
> valide en priorité : si ça ne marche pas sur `hard.vsdx`, ce n'est pas bon.

## Prérequis

```bash
# 1) servir la racine du repo en HTTP
python3 -m http.server 8099

# 2) Playwright + Chromium (déjà présents dans l'environnement web)
```

## Lancer

```bash
# vue globale, agencement auto, hard.vsdx
node tests/carto/drive.mjs "" /tmp/full.png

# positions Visio brutes (avant agencement)
node tests/carto/drive.mjs "?route=0" /tmp/raw.png

# sans aération (align + declutter désactivés) — comparaison
node tests/carto/drive.mjs "?declutter=0" /tmp/nodeclutter.png

# zoom sur une région (coordonnées carto) — pour inspecter un détail
node tests/carto/drive.mjs "?cx=8089&cy=94&zw=1500&zh=1150" /tmp/group.png
```

Sortie console = JSON : `before`/`after` (croisements, nb de segments), `tips`
(pointes réellement pivotées : dernier segment rendu non aligné sur l'axe du port —
lit la même géométrie que le SVG, via `_alignPortApproach`), `fit`
(dimensions/échelle), `nbShapes`, `nbConns`.

Repères mesurés sur `hard.vsdx` (routeur interne, post-agencement) : ~350
croisements (inhérents à un graphe dense et cyclique — non réductibles à zéro par
un algo), **2 pointes pivotées à 3–4 px** (négligeable), 17/19 losanges décoratifs
seatés à ≤13 px d'une flèche. À working-zoom la carto est propre ; l'aspect
« spaghetti » n'apparaît qu'en vue d'ensemble (normal pour une swimlane de cette
densité).

## Paramètres d'URL (`harness.html`)

| Param | Rôle |
|-------|------|
| `vsdx=/Code/xxx.vsdx` | carto à charger (défaut `hard.vsdx`) |
| `route=0` | ne pas exécuter l'agencement auto (positions Visio brutes) |
| `declutter=0` | désactive align + declutter (garde le routage) |
| `cx,cy,zw,zh` | zoom sur une région (coordonnées carto) |

## Notes

- `harness.html` fournit un scaffold DOM minimal (`#canvas` + calques `g-*`) car
  `editor.js` lie ses refs SVG au chargement. `init()` (câblage des boutons) échoue
  proprement, sans bloquer `render()` / `_computeAutoLayout()`.
- Libavoid est **désactivé** dans le banc (`OPTIQCARTO_USE_LIBAVOID=false`) : sur les
  grosses cartos denses il time-out puis se replie sur le routeur interne — c'est ce
  routeur interne qu'on teste (celui qui ship réellement sur `hard.vsdx`).
- La mesure des croisements reconstruit les tracés depuis `userPts` (le rendu réel
  ajoute stubs/arrondis) : fiable pour comparer, indicatif en absolu. **La capture
  reste le juge de paix.**
- `jszip.min.js` est vendored ici (l'app le charge via CDN ; le banc en a besoin en
  local, hors ligne).
