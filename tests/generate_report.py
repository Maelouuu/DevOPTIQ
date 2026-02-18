#!/usr/bin/env python3
# tests/generate_report.py
"""
Génère un rapport HTML visuel depuis le fichier JUnit XML produit par pytest.
Usage :
    python tests/generate_report.py tests/results.xml tests/report_visuel.html
"""
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

PAGE_LABELS = {
    "test_01_auth":        "Authentification",
    "test_02_activities":  "Liste des Activités",
    "test_03_tasks":       "Tâches",
    "test_04_constraints": "Contraintes",
    "test_05_aptitudes":   "Aptitudes",
    "test_06_softskills":  "HSC / Habiletés Socio-Cognitives",
    "test_07_performance": "Performance / Connexions",
    "test_08_task_links":  "Drag & Drop Connexions→Tâches",
    "test_09_time":        "Gestion du Temps",
    "test_10_roles":       "Rôles",
}


def parse_xml(xml_path: str) -> dict:
    """Parse le XML JUnit et retourne un dict organisé par page."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    pages: dict[str, dict] = {}

    for tc in root.iter("testcase"):
        classname = tc.get("classname", "")
        name = tc.get("name", "")
        time_s = float(tc.get("time", "0"))

        # Extraire le module (test_XX_...)
        parts = classname.split(".")
        module = next((p for p in parts if p.startswith("test_")), parts[-1] if parts else "unknown")

        page_label = PAGE_LABELS.get(module, module)
        if page_label not in pages:
            pages[page_label] = {"passed": [], "failed": [], "errors": [], "skipped": [], "total_time": 0.0}

        pages[page_label]["total_time"] += time_s

        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")

        if failure is not None:
            pages[page_label]["failed"].append({
                "name": name,
                "message": failure.get("message", ""),
                "detail": failure.text or "",
            })
        elif error is not None:
            pages[page_label]["errors"].append({
                "name": name,
                "message": error.get("message", ""),
                "detail": error.text or "",
            })
        elif skipped is not None:
            pages[page_label]["skipped"].append({"name": name})
        else:
            pages[page_label]["passed"].append({"name": name})

    return pages


def score_color(rate: float) -> str:
    if rate >= 0.95:
        return "#16a34a"  # vert
    if rate >= 0.80:
        return "#d97706"  # orange
    return "#dc2626"  # rouge


def score_badge(rate: float) -> str:
    pct = int(rate * 100)
    color = score_color(rate)
    label = "Excellent" if rate >= 0.95 else ("Attention" if rate >= 0.80 else "Échec")
    return f'<span style="background:{color};color:#fff;padding:3px 10px;border-radius:12px;font-size:0.8rem;font-weight:700;">{pct}% — {label}</span>'


def generate_html(pages: dict, output_path: str):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    total_passed = sum(len(p["passed"]) for p in pages.values())
    total_failed = sum(len(p["failed"]) + len(p["errors"]) for p in pages.values())
    total_skipped = sum(len(p["skipped"]) for p in pages.values())
    total_all = total_passed + total_failed + total_skipped
    global_rate = total_passed / total_all if total_all else 0

    cards_html = ""
    for page_label in sorted(pages.keys(), key=lambda k: list(PAGE_LABELS.values()).index(k) if k in PAGE_LABELS.values() else 99):
        p = pages[page_label]
        nb_pass = len(p["passed"])
        nb_fail = len(p["failed"]) + len(p["errors"])
        nb_skip = len(p["skipped"])
        nb_total = nb_pass + nb_fail + nb_skip
        rate = nb_pass / nb_total if nb_total else 0
        color = score_color(rate)

        failures_html = ""
        for f in p["failed"] + p["errors"]:
            detail_escaped = f["detail"].replace("<", "&lt;").replace(">", "&gt;")[:400]
            failures_html += f"""
            <div style="background:#fef2f2;border-left:3px solid #dc2626;padding:8px 12px;margin-top:8px;border-radius:4px;font-size:0.8rem;">
              <strong>✗ {f['name']}</strong><br>
              <span style="color:#7f1d1d;">{f['message']}</span>
              {"<pre style='margin:4px 0 0 0;font-size:0.75rem;color:#991b1b;white-space:pre-wrap;'>" + detail_escaped + "</pre>" if detail_escaped.strip() else ""}
            </div>"""

        skipped_html = ""
        if p["skipped"]:
            skipped_html = f'<div style="color:#6b7280;font-size:0.8rem;margin-top:6px;">⚠ {nb_skip} test(s) ignoré(s)</div>'

        bar_width = int(rate * 100)
        bar_color = color

        cards_html += f"""
        <div style="background:#fff;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,0.1);border-top:4px solid {color};">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <h3 style="margin:0;font-size:1rem;color:#1e293b;">{page_label}</h3>
            {score_badge(rate)}
          </div>
          <div style="display:flex;gap:16px;margin-bottom:10px;">
            <span style="color:#16a34a;font-size:0.9rem;font-weight:600;">✓ {nb_pass} passé(s)</span>
            <span style="color:#dc2626;font-size:0.9rem;font-weight:600;">✗ {nb_fail} échoué(s)</span>
            {'<span style="color:#6b7280;font-size:0.9rem;">⊘ ' + str(nb_skip) + ' ignoré(s)</span>' if nb_skip else ''}
          </div>
          <div style="background:#f1f5f9;border-radius:4px;height:8px;overflow:hidden;margin-bottom:6px;">
            <div style="background:{bar_color};width:{bar_width}%;height:100%;transition:width 0.5s;"></div>
          </div>
          <div style="font-size:0.75rem;color:#94a3b8;">{nb_pass}/{nb_total} tests passés — {p['total_time']:.2f}s</div>
          {failures_html}
          {skipped_html}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DevOPTIQ — Rapport de tests</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', sans-serif; background: #f8fafc; color: #1e293b; padding: 24px; }}
    h1 {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 24px; }}
    .global-card {{ background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; border-radius: 12px; padding: 24px; margin-bottom: 28px; }}
    .global-card h2 {{ font-size: 2.5rem; font-weight: 800; margin-bottom: 4px; }}
    .global-card p {{ opacity: 0.9; font-size: 0.95rem; }}
    .stats {{ display: flex; gap: 20px; margin-top: 16px; flex-wrap: wrap; }}
    .stat {{ background: rgba(255,255,255,0.2); border-radius: 8px; padding: 10px 18px; text-align: center; }}
    .stat .val {{ font-size: 1.5rem; font-weight: 700; display: block; }}
    .stat .lbl {{ font-size: 0.8rem; opacity: 0.85; }}
  </style>
</head>
<body>
  <h1>DevOPTIQ — Rapport de fiabilité</h1>
  <div class="subtitle">Généré le {now}</div>

  <div class="global-card">
    <h2>{int(global_rate * 100)}%</h2>
    <p>Taux de fiabilité global</p>
    <div class="stats">
      <div class="stat"><span class="val">{total_all}</span><span class="lbl">Tests totaux</span></div>
      <div class="stat"><span class="val">{total_passed}</span><span class="lbl">Passés ✓</span></div>
      <div class="stat"><span class="val">{total_failed}</span><span class="lbl">Échoués ✗</span></div>
      <div class="stat"><span class="val">{total_skipped}</span><span class="lbl">Ignorés ⊘</span></div>
      <div class="stat"><span class="val">{len(pages)}</span><span class="lbl">Pages testées</span></div>
    </div>
  </div>

  <h2 style="font-size:1rem;color:#64748b;margin-bottom:14px;text-transform:uppercase;letter-spacing:0.05em;">Résultats par page</h2>

  {cards_html}

  <div style="text-align:center;color:#94a3b8;font-size:0.8rem;margin-top:24px;">
    Rapport généré automatiquement par DevOPTIQ Test Suite
  </div>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✓ Rapport généré : {output_path}")


if __name__ == "__main__":
    xml_path = sys.argv[1] if len(sys.argv) > 1 else "tests/results.xml"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "tests/report_visuel.html"

    try:
        pages = parse_xml(xml_path)
        generate_html(pages, out_path)
    except FileNotFoundError:
        print(f"Erreur : fichier XML introuvable : {xml_path}")
        print("Lancez d'abord : pytest --junitxml=tests/results.xml")
        sys.exit(1)
