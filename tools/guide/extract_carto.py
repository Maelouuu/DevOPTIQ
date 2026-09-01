"""Extrait le JSON de cartographie d'un fichier .vsdx via le banc tests/carto.

Prérequis :  lancé à la racine du repo.
Usage : python tools/guide/extract_carto.py [Code/example.vsdx]
Produit : tools/guide/example_diagram.json (consommé par seed_demo.py)
"""
import os
import sys
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
vsdx = '/' + (sys.argv[1] if len(sys.argv) > 1 else 'Code/example.vsdx').lstrip('/')

with sync_playwright() as p:
    b = p.chromium.launch(**({'executable_path': os.environ['CHROME_PATH']} if os.environ.get('CHROME_PATH') else {}))
    pg = b.new_page(viewport={'width': 1750, 'height': 1300})
    pg.goto(f'http://localhost:8099/tests/carto/harness.html?vsdx={vsdx}', wait_until='load', timeout=30000)
    pg.wait_for_function('document.title === "DONE"', timeout=120000)
    diag = pg.evaluate('JSON.stringify(state)')
    open(os.path.join(BASE, 'example_diagram.json'), 'w').write(diag)
    print('example_diagram.json écrit —', pg.evaluate('state.shapes.length'), 'formes')
    b.close()
