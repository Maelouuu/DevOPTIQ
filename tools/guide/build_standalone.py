"""Construit docs/guide_standalone.html : le guide avec TOUTES les captures et
vidéos embarquées en base64 — un seul fichier, partageable par mail/USB, qui
fonctionne sans le dossier assets."""
import base64
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(BASE, '..', '..'))
SRC = os.path.join(REPO, 'docs', 'guide.html')
DST = os.path.join(REPO, 'docs', 'guide_standalone.html')
ASSETS = os.path.join(REPO, 'docs')

MIME = {'.png': 'image/png', '.webm': 'video/webm', '.jpg': 'image/jpeg'}

html = open(SRC, encoding='utf-8').read()

def embed(m):
    attr, path = m.group(1), m.group(2)
    full = os.path.join(ASSETS, path)
    if not os.path.exists(full):
        print('! introuvable :', path)
        return m.group(0)
    ext = os.path.splitext(path)[1].lower()
    data = base64.b64encode(open(full, 'rb').read()).decode()
    return f'{attr}="data:{MIME.get(ext, "application/octet-stream")};base64,{data}"'

html = re.sub(r'(src|poster)="(assets/guide/[^"]+)"', embed, html)
html = html.replace('<title>OPTIQ — Guide de prise en main</title>',
                    '<title>OPTIQ — Guide de prise en main (autonome)</title>')
open(DST, 'w', encoding='utf-8').write(html)
print(f'OK → {DST} ({os.path.getsize(DST) / 1e6:.1f} Mo)')
