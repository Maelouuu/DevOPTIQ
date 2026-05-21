#!/usr/bin/env python3
# tests/generate_report.py
"""
Génère un rapport HTML visuel depuis le fichier JUnit XML produit par pytest.
Usage :
    python tests/generate_report.py tests/results.xml tests/report_visuel.html
"""
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

PAGE_LABELS = {
    "test_01_auth":               "Authentification",
    "test_02_activities":         "Liste des Activités",
    "test_03_tasks":              "Tâches",
    "test_04_activity_features":  "Fonctionnalités Activité",
    "test_04_constraints":        "Contraintes",
    "test_05_aptitudes":          "Aptitudes",
    "test_06_softskills":         "HSC / Habiletés Socio-Cognitives",
    "test_07_performance":        "Performance / Connexions",
    "test_08_task_links":         "Drag & Drop Connexions→Tâches",
    "test_09_time":               "Gestion du Temps",
    "test_10_roles":              "Rôles",
    "test_11_tools":              "Gestion des Outils",
    "test_12_gestion_rh":         "Gestion RH",
    "test_13_competences":        "Compétences & Évaluations",
    "test_14_cartography_editor": "Éditeur OptiqCarto",
    "test_15_activities_map":     "Cartographie des Activités",
    "test_16_import_full":        "Import IA depuis Excel",
    "test_17_chatbot":            "Chatbot IA OPTIQ",
}


def fmt_test_name(name: str) -> str:
    """test_login_page_accessible → 'Login page accessible'"""
    n = re.sub(r'^test_', '', name)
    return n.replace("_", " ").capitalize()


def fmt_class_name(cls: str) -> str:
    """TestLoginPage → 'Login Page'"""
    n = re.sub(r'^Test', '', cls)
    return re.sub(r'([A-Z])', r' \1', n).strip()


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_xml(xml_path: str) -> dict:
    """Parse le XML JUnit et retourne un dict organisé par page."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    pages: dict = {}

    for tc in root.iter("testcase"):
        classname = tc.get("classname", "")
        name = tc.get("name", "")
        time_s = float(tc.get("time", "0"))

        parts = classname.split(".")
        module = next((p for p in parts if p.startswith("test_")), parts[-1] if parts else "unknown")
        cls = parts[-1] if (parts and not parts[-1].startswith("test_")) else ""

        page_label = PAGE_LABELS.get(module, module)
        if page_label not in pages:
            pages[page_label] = {
                "passed": [], "failed": [], "errors": [], "skipped": [],
                "total_time": 0.0,
            }

        pages[page_label]["total_time"] += time_s
        entry = {"name": name, "cls": cls, "time": time_s}

        failure = tc.find("failure")
        error   = tc.find("error")
        skipped = tc.find("skipped")

        if failure is not None:
            entry.update({"message": failure.get("message", ""), "detail": failure.text or ""})
            pages[page_label]["failed"].append(entry)
        elif error is not None:
            entry.update({"message": error.get("message", ""), "detail": error.text or ""})
            pages[page_label]["errors"].append(entry)
        elif skipped is not None:
            entry["reason"] = skipped.get("message", "")
            pages[page_label]["skipped"].append(entry)
        else:
            pages[page_label]["passed"].append(entry)

    return pages


def score_color(rate: float) -> str:
    if rate >= 0.95:
        return "#16a34a"
    if rate >= 0.80:
        return "#d97706"
    return "#dc2626"


def score_badge(rate: float) -> str:
    pct = int(rate * 100)
    color = score_color(rate)
    label = "Excellent" if rate >= 0.95 else ("Attention" if rate >= 0.80 else "Échec")
    return f'<span class="score-badge" style="background:{color};">{pct}% — {label}</span>'


def render_passed_section(passed: list) -> str:
    if not passed:
        return ""

    # Grouper par classe de test
    groups: dict = {}
    for t in passed:
        cls = t.get("cls", "")
        groups.setdefault(cls, []).append(t)

    rows = ""
    for cls, tests in groups.items():
        if cls:
            rows += f'<div class="test-group-header">{esc(fmt_class_name(cls))}</div>'
        for t in tests:
            ms = int(t["time"] * 1000)
            time_str = f"{ms}ms" if ms < 1000 else f'{t["time"]:.2f}s'
            rows += f"""
            <div class="test-row test-passed">
              <span class="test-icon">✓</span>
              <span class="test-name">{esc(fmt_test_name(t['name']))}</span>
              <span class="test-time">{time_str}</span>
            </div>"""

    nb = len(passed)
    return f"""
    <details class="tests-detail">
      <summary class="tests-summary passed-summary">
        <span>Tests validés ({nb})</span>
        <span class="summary-arrow">›</span>
      </summary>
      <div class="tests-list">{rows}</div>
    </details>"""


def render_skipped_section(skipped: list) -> str:
    if not skipped:
        return ""
    rows = ""
    for t in skipped:
        reason = t.get("reason", "")
        rows += f"""
        <div class="test-row test-skipped">
          <span class="test-icon">⊘</span>
          <span class="test-name">{esc(fmt_test_name(t['name']))}</span>
          {f'<span class="test-skip-reason">{esc(reason[:90])}</span>' if reason else ""}
        </div>"""
    nb = len(skipped)
    return f"""
    <details class="tests-detail">
      <summary class="tests-summary skipped-summary">
        <span>Tests ignorés ({nb})</span>
        <span class="summary-arrow">›</span>
      </summary>
      <div class="tests-list">{rows}</div>
    </details>"""


def render_failures_section(failed: list) -> str:
    if not failed:
        return ""
    html = ""
    for f in failed:
        detail = esc(f.get("detail", ""))[:700]
        html += f"""
        <div class="failure-block">
          <div class="failure-title">✗ {esc(fmt_test_name(f['name']))}</div>
          <div class="failure-message">{esc(f.get('message', ''))}</div>
          {f'<pre class="failure-detail">{detail}</pre>' if detail.strip() else ""}
        </div>"""
    return f'<div class="failures-section">{html}</div>'


def generate_html(pages: dict, output_path: str):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    total_passed  = sum(len(p["passed"]) for p in pages.values())
    total_failed  = sum(len(p["failed"]) + len(p["errors"]) for p in pages.values())
    total_skipped = sum(len(p["skipped"]) for p in pages.values())
    total_all     = total_passed + total_failed + total_skipped
    global_rate   = total_passed / total_all if total_all else 0

    cards_html = ""
    for page_label in sorted(
        pages.keys(),
        key=lambda k: list(PAGE_LABELS.values()).index(k) if k in PAGE_LABELS.values() else 99
    ):
        p = pages[page_label]
        nb_pass  = len(p["passed"])
        nb_fail  = len(p["failed"]) + len(p["errors"])
        nb_skip  = len(p["skipped"])
        nb_total = nb_pass + nb_fail + nb_skip
        rate     = nb_pass / nb_total if nb_total else 0
        color    = score_color(rate)
        bar_w    = int(rate * 100)

        all_failures = p["failed"] + p["errors"]

        skip_span = (
            f'<span class="stat-skip">⊘ {nb_skip} ignoré{"s" if nb_skip > 1 else ""}</span>'
            if nb_skip else ""
        )

        cards_html += f"""
        <div class="page-card" style="border-top-color:{color};">
          <div class="card-header">
            <h3 class="card-title">{esc(page_label)}</h3>
            {score_badge(rate)}
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="background:{color};width:{bar_w}%;"></div>
          </div>
          <div class="card-stats">
            <span class="stat-pass">✓ {nb_pass} passé{"s" if nb_pass > 1 else ""}</span>
            <span class="stat-fail">✗ {nb_fail} échoué{"s" if nb_fail > 1 else ""}</span>
            {skip_span}
            <span class="stat-time">⏱ {p['total_time']:.2f}s</span>
          </div>
          {render_failures_section(all_failures)}
          {render_passed_section(p["passed"])}
          {render_skipped_section(p["skipped"])}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DevOPTIQ — Rapport de tests</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #f1f5f9;
      color: #1e293b;
      padding: 28px 24px;
      max-width: 920px;
      margin: 0 auto;
    }}

    h1 {{ font-size: 1.65rem; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 24px; }}

    /* ── Global card ───────────────────────────────────── */
    .global-card {{
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: #fff;
      border-radius: 14px;
      padding: 28px;
      margin-bottom: 28px;
      box-shadow: 0 6px 24px rgba(102,126,234,0.3);
    }}
    .global-card h2 {{ font-size: 3rem; font-weight: 800; letter-spacing: -1px; margin-bottom: 4px; }}
    .global-card p  {{ opacity: 0.9; font-size: 0.95rem; margin-bottom: 18px; }}
    .stats {{ display: flex; gap: 12px; flex-wrap: wrap; }}
    .stat {{
      background: rgba(255,255,255,0.2);
      border-radius: 10px;
      padding: 12px 20px;
      text-align: center;
      min-width: 90px;
    }}
    .stat .val {{ font-size: 1.6rem; font-weight: 700; display: block; }}
    .stat .lbl {{ font-size: 0.75rem; opacity: 0.85; margin-top: 3px; display: block; }}

    /* ── Section title ─────────────────────────────────── */
    .section-title {{
      font-size: 0.78rem;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 600;
      margin-bottom: 14px;
    }}

    /* ── Page card ─────────────────────────────────────── */
    .page-card {{
      background: #fff;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 12px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.07);
      border-top: 4px solid;
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }}
    .card-title {{ font-size: 1rem; font-weight: 600; color: #1e293b; }}
    .score-badge {{
      color: #fff;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.78rem;
      font-weight: 700;
      white-space: nowrap;
    }}

    /* ── Progress bar ──────────────────────────────────── */
    .progress-bar-bg {{
      background: #f1f5f9;
      border-radius: 6px;
      height: 8px;
      overflow: hidden;
      margin-bottom: 12px;
    }}
    .progress-bar-fill {{ height: 100%; border-radius: 6px; }}

    /* ── Stats row ─────────────────────────────────────── */
    .card-stats {{
      display: flex;
      gap: 16px;
      font-size: 0.85rem;
      margin-bottom: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .stat-pass {{ color: #16a34a; font-weight: 600; }}
    .stat-fail {{ color: #dc2626; font-weight: 600; }}
    .stat-skip {{ color: #6b7280; }}
    .stat-time {{ color: #94a3b8; margin-left: auto; font-size: 0.78rem; }}

    /* ── Failures ──────────────────────────────────────── */
    .failures-section {{ margin-bottom: 8px; }}
    .failure-block {{
      background: #fef2f2;
      border-left: 3px solid #dc2626;
      padding: 10px 14px;
      margin-bottom: 8px;
      border-radius: 0 6px 6px 0;
    }}
    .failure-title   {{ font-weight: 600; font-size: 0.88rem; color: #991b1b; margin-bottom: 4px; }}
    .failure-message {{ font-size: 0.82rem; color: #7f1d1d; margin-bottom: 2px; }}
    .failure-detail  {{
      font-size: 0.73rem;
      color: #991b1b;
      white-space: pre-wrap;
      margin-top: 8px;
      background: rgba(0,0,0,0.04);
      padding: 8px;
      border-radius: 4px;
      line-height: 1.55;
      overflow-x: auto;
    }}

    /* ── Details accordion ─────────────────────────────── */
    .tests-detail {{ margin-top: 6px; }}
    .tests-detail + .tests-detail {{ margin-top: 4px; }}
    .tests-summary {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 12px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      list-style: none;
      user-select: none;
    }}
    .tests-summary::-webkit-details-marker {{ display: none; }}
    .passed-summary  {{ background: #f0fdf4; color: #166534; }}
    .passed-summary:hover {{ background: #dcfce7; }}
    .skipped-summary {{ background: #f9fafb; color: #6b7280; }}
    .skipped-summary:hover {{ background: #f1f5f9; }}
    .summary-arrow {{ font-size: 1rem; transition: transform 0.2s; }}
    details[open] .summary-arrow {{ transform: rotate(90deg); }}

    /* ── Test list ─────────────────────────────────────── */
    .tests-list {{ padding: 6px 0 2px; }}
    .test-group-header {{
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #94a3b8;
      font-weight: 700;
      padding: 10px 10px 4px;
      border-bottom: 1px solid #f1f5f9;
      margin-bottom: 2px;
    }}
    .test-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 5px 10px;
      border-radius: 6px;
      font-size: 0.83rem;
    }}
    .test-row:hover {{ background: #f8fafc; }}
    .test-passed {{ color: #374151; }}
    .test-skipped {{ color: #6b7280; }}
    .test-icon  {{ flex-shrink: 0; width: 16px; font-size: 0.82rem; }}
    .test-passed .test-icon  {{ color: #16a34a; }}
    .test-skipped .test-icon {{ color: #9ca3af; }}
    .test-name  {{ flex: 1; }}
    .test-time  {{ font-size: 0.73rem; color: #94a3b8; white-space: nowrap; }}
    .test-skip-reason {{ font-size: 0.73rem; color: #9ca3af; font-style: italic; }}

    /* ── Footer ────────────────────────────────────────── */
    .report-footer {{
      text-align: center;
      color: #cbd5e1;
      font-size: 0.75rem;
      margin-top: 36px;
      padding-bottom: 20px;
    }}
  </style>
</head>
<body>
  <h1>DevOPTIQ — Rapport de fiabilité</h1>
  <div class="subtitle">Généré le {now}</div>

  <div class="global-card">
    <h2>{int(global_rate * 100)}%</h2>
    <p>Taux de fiabilité global · {total_all} tests · {len(pages)} pages</p>
    <div class="stats">
      <div class="stat"><span class="val">{total_all}</span><span class="lbl">Tests totaux</span></div>
      <div class="stat"><span class="val">{total_passed}</span><span class="lbl">Passés ✓</span></div>
      <div class="stat"><span class="val">{total_failed}</span><span class="lbl">Échoués ✗</span></div>
      <div class="stat"><span class="val">{total_skipped}</span><span class="lbl">Ignorés ⊘</span></div>
      <div class="stat"><span class="val">{len(pages)}</span><span class="lbl">Pages testées</span></div>
    </div>
  </div>

  <div class="section-title">Résultats par page</div>

  {cards_html}

  <div class="report-footer">
    Rapport généré automatiquement · DevOPTIQ Test Suite · {now}
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
