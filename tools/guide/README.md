# Pipeline du guide utilisateur (`docs/guide.html`)

Régénère **automatiquement** toutes les captures d'écran et vidéos de manipulation
du guide, sur une base de démonstration réaliste — sans aucune capture manuelle.
À relancer après toute évolution visuelle notable de l'app.

## Prérequis

- Python + dépendances du projet (`pip install -r requirements.txt`) + `playwright`
- Chromium Playwright (env web : `/opt/pw-browsers/chromium`, sinon
  `CHROME_PATH=/chemin/vers/chrome`)
- ffmpeg pour la compression vidéo (env web : `/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux`)

## Étapes

```bash
# 0) (une fois, ou si la carto d'exemple change) extraire le JSON de carto
python3 -m http.server 8099 &            # servir la racine du repo
python tools/guide/extract_carto.py      # → tools/guide/example_diagram.json

# 1) démarrer l'app de démo seedée (bloquant — la laisser tourner)
python tools/guide/seed_demo.py          # sert sur http://127.0.0.1:5601

# 2) dans un autre terminal : captures d'écran (→ docs/assets/guide/*.png)
python tools/guide/capture_screens.py

# 3) vidéos de manipulation, curseur visible + bulles d'explication incrustées
#    (carte-titre d'ouverture, bandeau « Étape i/n », bulle ancrée par étape,
#    bulle ✓ de conclusion) → docs/assets/guide/flux-*.webm
python tools/guide/capture_videos.py

# 4) compression des vidéos + posters (2.6 s = la carte-titre est affichée)
cd docs/assets/guide
FF=/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux
for f in flux-*.webm; do
  $FF -y -i "$f" -c:v libvpx -b:v 450k -crf 22 -vf scale=1120:-2 -an "c_$f" && mv "c_$f" "$f"
  $FF -y -ss 2.6 -i "$f" -frames:v 1 "poster-${f%.webm}.png"
done
```

## Ce que fait la base de démo (`seed_demo.py`)

- Importe la cartographie `Code/example.vsdx` **via l'API de sauvegarde carto**
  (même chemin que l'éditeur) → 14 activités, 20 rôles et leurs liens réels ;
- Enrichit chaque activité : tâches, outils, compétences, savoirs/SF/aptitudes/HSC ;
- Crée 5 utilisateurs (admin manager + 4 collaborateurs affectés à des rôles
  porteurs d'activités) ;
- Enregistre des analyses de temps (projet, activité, rôle, faiblesse) via les
  mêmes API que l'interface.

Compte de démo : `demo@afdec.fr` / `Visual123!` — base SQLite jetable recréée à
chaque lancement (`tools/guide/demo_v2.db`).

⚠️ Les scripts n'écrivent que dans `docs/assets/guide/` et le fichier SQLite de
démo. Ils ne touchent jamais à une vraie base.
