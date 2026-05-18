#!/usr/bin/env python3
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
    "test_01_auth":             "Authentification",
    "test_02_activities":       "Liste des Activités",
    "test_03_tasks":            "Tâches",
    "test_04_activity_features":"Fonctionnalités Activité",
    "test_04_constraints":      "Contraintes",
    "test_05_aptitudes":        "Aptitudes",
    "test_06_softskills":       "Soft Skills",
    "test_07_performance":      "Performance",
    "test_08_task_links":       "Connexions → Tâches",
    "test_09_time":             "Gestion du Temps",
    "test_10_roles":            "Rôles",
    "test_11_tools":            "Gestion des Outils",
    "test_12_gestion_rh":       "Gestion RH",
}


def fmt_test_name(name: str) -> str:
    n = re.sub(r"^test_", "", name)
    return n.replace("_", " ").capitalize()


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_xml(xml_path: str) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    pages: dict = {}

    for tc in root.iter("testcase"):
        classname = tc.get("classname", "")
        name = tc.get("name", "")
        time_s = float(tc.get("time", "0"))

        parts = classname.split(".")
        module = next((p for p in parts if p.startswith("test_")), parts[-1] if parts else "unknown")

        page_label = PAGE_LABELS.get(module, module.replace("_", " ").title())
        if page_label not in pages:
            pages[page_label] = {"passed": [], "failed": [], "errors": [], "skipped": [], "total_time": 0.0}

        pages[page_label]["total_time"] += time_s
        entry = {"name": name, "time": time_s}

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
    if rate >= 0.95: return "#16a34a"
    if rate >= 0.75: return "#d97706"
    return "#ec4899"


def generate_html(pages: dict, output_path: str):
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")

    total_passed  = sum(len(p["passed"]) for p in pages.values())
    total_failed  = sum(len(p["failed"]) + len(p["errors"]) for p in pages.values())
    total_skipped = sum(len(p["skipped"]) for p in pages.values())
    total_all     = total_passed + total_failed + total_skipped
    global_rate   = total_passed / total_all if total_all else 0
    global_pct    = int(global_rate * 100)

    # ── Sidebar nav ──────────────────────────────────────────────────────────
    nav_items = ""
    for label in sorted(pages.keys(), key=lambda k: list(PAGE_LABELS.values()).index(k) if k in PAGE_LABELS.values() else 99):
        p = pages[label]
        nb_pass  = len(p["passed"])
        nb_total = nb_pass + len(p["failed"]) + len(p["errors"]) + len(p["skipped"])
        rate     = nb_pass / nb_total if nb_total else 0
        pct      = int(rate * 100)
        color    = score_color(rate)
        anchor   = re.sub(r"[^a-z0-9]", "-", label.lower())
        dot = f'<span style="width:8px;height:8px;border-radius:50%;background:{color};display:inline-block;flex-shrink:0;margin-top:2px;"></span>'
        nav_items += f"""
        <a href="#{anchor}" class="nav-link">
          {dot}
          <span class="nav-label">{esc(label)}</span>
          <span class="nav-pct" style="color:{color};">{pct}%</span>
        </a>"""

    # ── Page cards ───────────────────────────────────────────────────────────
    cards_html = ""
    for label in sorted(pages.keys(), key=lambda k: list(PAGE_LABELS.values()).index(k) if k in PAGE_LABELS.values() else 99):
        p = pages[label]
        nb_pass  = len(p["passed"])
        nb_fail  = len(p["failed"]) + len(p["errors"])
        nb_skip  = len(p["skipped"])
        nb_total = nb_pass + nb_fail + nb_skip
        rate     = nb_pass / nb_total if nb_total else 0
        pct      = int(rate * 100)
        color    = score_color(rate)
        anchor   = re.sub(r"[^a-z0-9]", "-", label.lower())

        badge_label = "Excellent" if rate >= 0.95 else ("Partiel" if rate >= 0.75 else "Échecs")

        failures_html = ""
        for f in (p["failed"] + p["errors"]):
            detail = esc((f.get("detail") or "")[:600]).strip()
            failures_html += f"""
            <div class="failure-block">
              <div class="failure-name">✗ {esc(fmt_test_name(f['name']))}</div>
              <div class="failure-msg">{esc(f.get('message',''))}</div>
              {f'<pre class="failure-trace">{detail}</pre>' if detail else ""}
            </div>"""

        passed_rows = ""
        for t in p["passed"]:
            ms = int(t["time"] * 1000)
            t_str = f"{ms}ms" if ms < 1000 else f'{t["time"]:.2f}s'
            passed_rows += f"""
            <div class="test-row">
              <span class="test-ok">✓</span>
              <span class="test-name">{esc(fmt_test_name(t['name']))}</span>
              <span class="test-time">{t_str}</span>
            </div>"""

        passed_section = ""
        if p["passed"]:
            passed_section = f"""
            <details class="detail-block">
              <summary class="detail-summary green-summary">
                <span>✓ {nb_pass} test{"s" if nb_pass > 1 else ""} passé{"s" if nb_pass > 1 else ""}</span>
                <span class="chevron">›</span>
              </summary>
              <div class="tests-list">{passed_rows}</div>
            </details>"""

        cards_html += f"""
        <section class="page-card" id="{anchor}">
          <div class="card-top">
            <div>
              <div class="card-title">{esc(label)}</div>
              <div class="card-meta">{nb_total} test{"s" if nb_total != 1 else ""} · {p['total_time']:.2f}s</div>
            </div>
            <div class="card-badge" style="background:{color}15;color:{color};">{pct}% — {badge_label}</div>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width:{pct}%;background:{color};"></div>
          </div>
          <div class="card-stats">
            <span class="s-pass">✓ {nb_pass} passé{"s" if nb_pass != 1 else ""}</span>
            <span class="s-fail">✗ {nb_fail} échoué{"s" if nb_fail != 1 else ""}</span>
            {f'<span class="s-skip">⊘ {nb_skip} ignoré{"s" if nb_skip != 1 else ""}</span>' if nb_skip else ""}
          </div>
          {failures_html}
          {passed_section}
        </section>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DevOPTIQ — Panel de tests</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --pink:    #ec4899;
      --pink-dk: #be185d;
      --green:   #22c55e;
      --green-dk:#15803d;
      --sidebar: 240px;
      --border:  #e5e7eb;
      --bg:      #f9fafb;
      --text:    #111827;
    }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); display: flex; min-height: 100vh; }}

    nav#sidebar {{ width: var(--sidebar); flex-shrink: 0; background: #fff; border-right: 1.5px solid var(--border); position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto; display: flex; flex-direction: column; }}
    .sidebar-logo {{ padding: 20px 16px 16px; border-bottom: 1.5px solid var(--border); }}
    .logo-dot {{ width: 30px; height: 30px; border-radius: 8px; background: linear-gradient(135deg, var(--pink), var(--pink-dk)); display: inline-block; vertical-align: middle; margin-right: 8px; }}
    .logo-text {{ font-weight: 700; font-size: 0.95rem; vertical-align: middle; }}
    .logo-sub  {{ font-size: 0.72rem; color: #6b7280; margin-top: 2px; }}
    .nav-section {{ padding: 12px 10px 6px; font-size: 0.67rem; text-transform: uppercase; letter-spacing: 0.08em; color: #9ca3af; font-weight: 700; }}
    .nav-link {{ display: flex; align-items: flex-start; gap: 8px; padding: 7px 14px; font-size: 0.82rem; color: #374151; text-decoration: none; transition: background 0.15s; }}
    .nav-link:hover {{ background: #fdf2f8; color: var(--pink-dk); }}
    .nav-label {{ flex: 1; line-height: 1.3; }}
    .nav-pct   {{ font-size: 0.75rem; font-weight: 700; white-space: nowrap; margin-top: 1px; }}

    main {{ margin-left: var(--sidebar); flex: 1; padding: 32px 28px; max-width: 860px; }}

    .hero {{ background: linear-gradient(135deg, var(--pink-dk) 0%, var(--pink) 100%); border-radius: 16px; padding: 28px 32px; color: #fff; margin-bottom: 28px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }}
    .hero-score {{ font-size: 4rem; font-weight: 800; letter-spacing: -2px; line-height: 1; }}
    .hero-label {{ font-size: 0.95rem; opacity: 0.9; margin-top: 4px; }}
    .hero-stats {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .hero-stat {{ background: rgba(255,255,255,0.18); border-radius: 10px; padding: 10px 16px; text-align: center; min-width: 80px; }}
    .hero-stat .v {{ font-size: 1.5rem; font-weight: 700; display: block; }}
    .hero-stat .l {{ font-size: 0.72rem; opacity: 0.85; margin-top: 2px; display: block; }}

    .section-title {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: #9ca3af; font-weight: 700; margin-bottom: 12px; }}

    .page-card {{ background: #fff; border-radius: 12px; padding: 20px 22px; margin-bottom: 10px; border: 1.5px solid var(--border); box-shadow: 0 1px 4px rgba(0,0,0,0.04); scroll-margin-top: 20px; }}
    .card-top {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; gap: 12px; }}
    .card-title {{ font-size: 0.95rem; font-weight: 700; color: #111827; }}
    .card-meta  {{ font-size: 0.75rem; color: #9ca3af; margin-top: 2px; }}
    .card-badge {{ font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 20px; white-space: nowrap; flex-shrink: 0; }}

    .progress-track {{ background: #f3f4f6; border-radius: 6px; height: 6px; overflow: hidden; margin-bottom: 12px; }}
    .progress-fill  {{ height: 100%; border-radius: 6px; }}

    .card-stats {{ display: flex; gap: 16px; font-size: 0.82rem; margin-bottom: 10px; flex-wrap: wrap; }}
    .s-pass {{ color: #16a34a; font-weight: 600; }}
    .s-fail {{ color: #ec4899; font-weight: 600; }}
    .s-skip {{ color: #9ca3af; }}

    .failure-block {{ background: #fff7f9; border-left: 3px solid #ec4899; padding: 10px 14px; margin-bottom: 6px; border-radius: 0 8px 8px 0; }}
    .failure-name  {{ font-size: 0.85rem; font-weight: 600; color: #be185d; margin-bottom: 3px; }}
    .failure-msg   {{ font-size: 0.8rem; color: #9f1239; }}
    .failure-trace {{ font-size: 0.71rem; color: #be185d; white-space: pre-wrap; background: rgba(236,72,153,0.05); padding: 8px; border-radius: 4px; margin-top: 6px; overflow-x: auto; line-height: 1.5; }}

    .detail-block {{ margin-top: 8px; }}
    .detail-summary {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 0.82rem; font-weight: 600; list-style: none; user-select: none; }}
    .detail-summary::-webkit-details-marker {{ display: none; }}
    .green-summary {{ background: #f0fdf4; color: #15803d; }}
    .green-summary:hover {{ background: #dcfce7; }}
    .chevron {{ font-size: 1rem; transition: transform 0.2s; }}
    details[open] .chevron {{ transform: rotate(90deg); }}

    .tests-list {{ padding: 4px 0 0; }}
    .test-row {{ display: flex; align-items: center; gap: 8px; padding: 5px 10px; border-radius: 6px; font-size: 0.81rem; color: #374151; }}
    .test-row:hover {{ background: #f9fafb; }}
    .test-ok   {{ color: #16a34a; font-size: 0.8rem; flex-shrink: 0; }}
    .test-name {{ flex: 1; }}
    .test-time {{ font-size: 0.7rem; color: #9ca3af; white-space: nowrap; }}

    .footer {{ text-align: center; color: #d1d5db; font-size: 0.73rem; margin-top: 40px; padding-bottom: 24px; }}

    @media print {{
      nav#sidebar {{ display: none; }}
      main {{ margin-left: 0; }}
      .page-card {{ break-inside: avoid; }}
      details {{ display: block; }}
      details > summary {{ display: none; }}
      details > .tests-list {{ display: block; }}
    }}
  </style>
</head>
<body>
<nav id="sidebar">
  <div class="sidebar-logo">
    <span class="logo-dot"></span>
    <span class="logo-text">DevOPTIQ</span>
    <div class="logo-sub">Panel de tests · {now}</div>
  </div>
  <div class="nav-section">Pages testées</div>
  {nav_items}
</nav>
<main>
  <div class="hero">
    <div>
      <div class="hero-score">{global_pct}%</div>
      <div class="hero-label">Taux de fiabilité global · {len(pages)} pages testées</div>
    </div>
    <div class="hero-stats">
      <div class="hero-stat"><span class="v">{total_all}</span><span class="l">Total</span></div>
      <div class="hero-stat"><span class="v">{total_passed}</span><span class="l">Passés</span></div>
      <div class="hero-stat"><span class="v">{total_failed}</span><span class="l">Échoués</span></div>
      <div class="hero-stat"><span class="v">{total_skipped}</span><span class="l">Ignorés</span></div>
    </div>
  </div>
  <div class="section-title">Résultats par page</div>
  {cards_html}
  <div class="footer">DevOPTIQ Test Suite · Généré le {now} · <code>./run_tests.sh</code> pour relancer</div>
</main>
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
        print("Lance d'abord : ./run_tests.sh")
        sys.exit(1)
