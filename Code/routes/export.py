# Code/routes/export.py
"""
Export des données d'une entité vers Excel ou HTML.
Upload-file  : sauvegarde le fichier en base de données (LargeBinary) — persistant sur cloud.
Serve-file   : sert le fichier depuis la DB (ou chemin local en dev).
"""
import os
import io
import mimetypes
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from Code.extensions import db
from Code.models.models import (
    Activities, Task, Link, Data, Role, Constraint,
    activity_roles, task_tools, Tool, Entity, FileBlob
)

export_bp = Blueprint("export", __name__)


# ──────────────────────────────────────────────
# Route : uploader un fichier → stocké en DB
# ──────────────────────────────────────────────
@export_bp.route("/utils/upload-file", methods=["POST"])
def upload_file():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    filename = secure_filename(f.filename) or "fichier"
    mime = f.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    data = f.read()

    blob = FileBlob(filename=filename, mimetype=mime, data=data)
    db.session.add(blob)
    db.session.commit()

    return jsonify({
        "path": f"/utils/file/{blob.id}",
        "original_name": f.filename
    }), 201


# ──────────────────────────────────────────────
# Route : servir un fichier depuis la DB
# ──────────────────────────────────────────────
@export_bp.route("/utils/file/<int:file_id>")
def serve_db_file(file_id):
    blob = FileBlob.query.get(file_id)
    if not blob:
        return jsonify({"error": "Fichier introuvable"}), 404
    return Response(
        blob.data,
        mimetype=blob.mimetype,
        headers={"Content-Disposition": f'inline; filename="{blob.filename}"'}
    )


# ──────────────────────────────────────────────
# Route : serve-file (point d'entrée universel)
#   - /utils/file/123       → DB
#   - chemin absolu local   → filesystem (dev local uniquement)
# ──────────────────────────────────────────────
@export_bp.route("/utils/serve-file")
def serve_local_file():
    path = request.args.get("path", "").strip()
    if not path:
        return jsonify({"error": "Chemin manquant"}), 400

    # Fichier DB (nouvelle méthode)
    if path.startswith("/utils/file/"):
        try:
            file_id = int(path.rsplit("/", 1)[-1])
        except ValueError:
            return jsonify({"error": "ID de fichier invalide"}), 400
        blob = FileBlob.query.get(file_id)
        if not blob:
            return jsonify({"error": "Fichier introuvable en base"}), 404
        return Response(
            blob.data,
            mimetype=blob.mimetype,
            headers={"Content-Disposition": f'inline; filename="{blob.filename}"'}
        )

    # Fichier local absolu (dev local uniquement — ne fonctionne pas sur cloud)
    if os.path.exists(path):
        mime, _ = mimetypes.guess_type(path)
        return send_file(path, mimetype=mime or "application/octet-stream",
                         as_attachment=False, download_name=os.path.basename(path))

    return jsonify({"error": "Fichier introuvable (chemin local inaccessible sur cet environnement)"}), 404


# ──────────────────────────────────────────────
# Collecte de toutes les données d'une entité
# ──────────────────────────────────────────────
def _collect_entity_data(entity_id, role_id=None):
    entity = Entity.query.get(entity_id)
    if not entity:
        return None

    activities_q = Activities.query.filter_by(entity_id=entity_id)
    if role_id:
        activities_q = activities_q.join(
            activity_roles, activity_roles.c.activity_id == Activities.id
        ).filter(activity_roles.c.role_id == role_id)
    activities = activities_q.order_by(Activities.name).all()

    roles = Role.query.filter_by(entity_id=entity_id).order_by(Role.name).all()

    data = {
        "entity": entity,
        "roles": roles,
        "activities": []
    }

    for act in activities:
        tasks = Task.query.filter_by(activity_id=act.id).order_by(Task.order).all()

        # Contraintes
        constraints = Constraint.query.filter_by(activity_id=act.id).all()

        # Outils via les tâches
        tools_set = {}
        for t in tasks:
            for tool in t.tools:
                tools_set[tool.id] = tool

        # Rôles liés
        act_roles = db.session.query(Role).join(
            activity_roles, activity_roles.c.role_id == Role.id
        ).filter(activity_roles.c.activity_id == act.id).all()

        # Connexions
        in_links = db.session.query(Link).filter(
            or_(Link.target_activity_id == act.id,
                Link.target_data_id == act.id)
        ).all()
        out_links = db.session.query(Link).filter(
            Link.source_activity_id == act.id
        ).all()

        data["activities"].append({
            "activity": act,
            "tasks": tasks,
            "constraints": constraints,
            "tools": list(tools_set.values()),
            "roles": act_roles,
            "incoming": in_links,
            "outgoing": out_links,
        })

    return data


# ──────────────────────────────────────────────
# Export Excel
# ──────────────────────────────────────────────
PURPLE     = "5B21B6"
PURPLE_MID = "7C3AED"
INDIGO     = "4338CA"
VIOLET_LT  = "EDE9FE"
VIOLET_MID = "DDD6FE"
WHITE      = "FFFFFF"
GRAY_LT    = "F5F3FF"

def _hdr_fill(hex_color): return PatternFill("solid", fgColor=hex_color)
def _border():
    s = Side(border_style="thin", color="C4B5FD")
    return Border(left=s, right=s, top=s, bottom=s)

def _make_excel(data, role_label=None):
    wb = Workbook()

    # ── Feuille 1 : Résumé ──────────────────────────────────
    ws = wb.active
    ws.title = "Résumé"

    entity = data["entity"]
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 50

    def write_section_title(ws, row, title):
        cell = ws.cell(row=row, column=1, value=title)
        cell.font = Font(bold=True, color=WHITE, size=12)
        cell.fill = _hdr_fill(PURPLE)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        ws.row_dimensions[row].height = 22
        return row + 1

    def write_kv(ws, row, key, value):
        k = ws.cell(row=row, column=1, value=key)
        k.font = Font(bold=True, color=PURPLE)
        k.fill = _hdr_fill(GRAY_LT)
        k.border = _border()
        v = ws.cell(row=row, column=2, value=str(value or ""))
        v.border = _border()
        v.alignment = Alignment(wrap_text=True)
        return row + 1

    r = 1
    r = write_section_title(ws, r, "Informations de l'entité")
    r = write_kv(ws, r, "Entité", entity.name)
    r = write_kv(ws, r, "Description", entity.description or "—")
    if role_label:
        r = write_kv(ws, r, "Filtre rôle", role_label)
    r = write_kv(ws, r, "Date d'export", datetime.now().strftime("%d/%m/%Y %H:%M"))
    r += 1
    r = write_section_title(ws, r, "Statistiques")
    r = write_kv(ws, r, "Nombre d'activités", len(data["activities"]))
    r = write_kv(ws, r, "Nombre de rôles", len(data["roles"]))
    total_tasks = sum(len(a["tasks"]) for a in data["activities"])
    r = write_kv(ws, r, "Nombre de tâches", total_tasks)
    total_constraints = sum(len(a["constraints"]) for a in data["activities"])
    r = write_kv(ws, r, "Nombre de contraintes", total_constraints)

    # ── Feuille 2 : Activités ────────────────────────────────
    ws2 = wb.create_sheet("Activités")
    headers = ["Activité", "Description", "Rôles", "Contraintes", "Outils", "Nb tâches"]
    col_widths = [30, 45, 25, 40, 35, 12]
    for i, (h, w) in enumerate(zip(headers, col_widths), 1):
        c = ws2.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color=WHITE, size=11)
        c.fill = _hdr_fill(INDIGO)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = _border()
        ws2.column_dimensions[get_column_letter(i)].width = w
    ws2.row_dimensions[1].height = 22
    ws2.freeze_panes = "A2"

    for row_i, a in enumerate(data["activities"], 2):
        act = a["activity"]
        roles_str  = ", ".join(r.name for r in a["roles"]) or "—"
        constr_str = "\n".join(c.description for c in a["constraints"]) or "—"
        tools_str  = ", ".join(t.name for t in a["tools"]) or "—"
        values = [act.name, act.description or "—", roles_str, constr_str, tools_str, len(a["tasks"])]
        fill = _hdr_fill(VIOLET_LT) if row_i % 2 == 0 else _hdr_fill(WHITE)
        for col_i, val in enumerate(values, 1):
            c = ws2.cell(row=row_i, column=col_i, value=val)
            c.fill = fill
            c.border = _border()
            c.alignment = Alignment(wrap_text=True, vertical="top")

    # ── Feuille 3 : Tâches ──────────────────────────────────
    ws3 = wb.create_sheet("Tâches")
    headers3 = ["Activité", "Tâche", "Description", "Durée (min)", "Délai (min)", "Outils"]
    widths3   = [28, 32, 45, 14, 14, 35]
    for i, (h, w) in enumerate(zip(headers3, widths3), 1):
        c = ws3.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color=WHITE)
        c.fill = _hdr_fill(PURPLE_MID)
        c.border = _border()
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws3.column_dimensions[get_column_letter(i)].width = w
    ws3.freeze_panes = "A2"

    row3 = 2
    for a in data["activities"]:
        act = a["activity"]
        for t in a["tasks"]:
            tool_names = ", ".join(tl.name for tl in t.tools) or "—"
            vals = [act.name, t.name, t.description or "—",
                    t.duration_minutes or "—", t.delay_minutes or "—", tool_names]
            fill = _hdr_fill(VIOLET_LT) if row3 % 2 == 0 else _hdr_fill(WHITE)
            for ci, v in enumerate(vals, 1):
                c = ws3.cell(row=row3, column=ci, value=v)
                c.fill = fill
                c.border = _border()
                c.alignment = Alignment(wrap_text=True, vertical="top")
            row3 += 1

    # ── Feuille 4 : Contraintes ─────────────────────────────
    ws4 = wb.create_sheet("Contraintes")
    headers4 = ["Activité", "Contrainte", "Fichier lié"]
    widths4   = [30, 55, 45]
    for i, (h, w) in enumerate(zip(headers4, widths4), 1):
        c = ws4.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color=WHITE)
        c.fill = _hdr_fill(PURPLE)
        c.border = _border()
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws4.column_dimensions[get_column_letter(i)].width = w
    ws4.freeze_panes = "A2"

    row4 = 2
    for a in data["activities"]:
        act = a["activity"]
        for con in a["constraints"]:
            vals = [act.name, con.description, con.file_path or "—"]
            fill = _hdr_fill(VIOLET_LT) if row4 % 2 == 0 else _hdr_fill(WHITE)
            for ci, v in enumerate(vals, 1):
                c = ws4.cell(row=row4, column=ci, value=v)
                c.fill = fill
                c.border = _border()
                c.alignment = Alignment(wrap_text=True, vertical="top")
            row4 += 1

    # ── Feuille 5 : Rôles ────────────────────────────────────
    ws5 = wb.create_sheet("Rôles")
    headers5 = ["Rôle", "Activités associées"]
    widths5   = [30, 70]
    for i, (h, w) in enumerate(zip(headers5, widths5), 1):
        c = ws5.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color=WHITE)
        c.fill = _hdr_fill(INDIGO)
        c.border = _border()
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws5.column_dimensions[get_column_letter(i)].width = w
    ws5.freeze_panes = "A2"

    for ri, role in enumerate(data["roles"], 2):
        acts_for_role = [a["activity"].name for a in data["activities"] if role in a["roles"]]
        vals = [role.name, "\n".join(acts_for_role) or "—"]
        fill = _hdr_fill(VIOLET_LT) if ri % 2 == 0 else _hdr_fill(WHITE)
        for ci, v in enumerate(vals, 1):
            c = ws5.cell(row=ri, column=ci, value=v)
            c.fill = fill
            c.border = _border()
            c.alignment = Alignment(wrap_text=True, vertical="top")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────
# Export HTML
# ──────────────────────────────────────────────
def _make_html(data, role_label=None):
    entity = data["entity"]
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")

    def esc(s):
        if not s:
            return "—"
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ── Blocs activités ─────────────────────────────────────
    act_blocks = []
    for i, a in enumerate(data["activities"]):
        act = a["activity"]
        roles_html = "".join(f'<span class="tag">{esc(r.name)}</span>' for r in a["roles"]) or "<em>—</em>"
        tools_html = "".join(f'<span class="tag tag-tool"><i>🔧</i> {esc(t.name)}</span>' for t in a["tools"]) or "<em>—</em>"

        tasks_rows = "".join(
            f"""<tr>
              <td>{esc(t.name)}</td>
              <td>{esc(t.description)}</td>
              <td>{t.duration_minutes or "—"}</td>
              <td>{t.delay_minutes or "—"}</td>
              <td>{esc(", ".join(tl.name for tl in t.tools)) if t.tools else "—"}</td>
            </tr>""" for t in a["tasks"]
        ) or '<tr><td colspan="5" class="empty">Aucune tâche</td></tr>'

        constr_rows = "".join(
            f"""<tr>
              <td>{esc(c.description)}</td>
              <td>{"<span class='file-chip'>📎 " + esc(c.file_path) + "</span>" if c.file_path else "—"}</td>
            </tr>""" for c in a["constraints"]
        ) or '<tr><td colspan="2" class="empty">Aucune contrainte</td></tr>'

        color_idx = i % 4
        accent = ["#6d28d9", "#4338ca", "#7c3aed", "#5b21b6"][color_idx]

        act_blocks.append(f"""
        <div class="act-card" style="--accent:{accent};">
          <div class="act-header">
            <span class="act-num">{i+1:02d}</span>
            <h2 class="act-title">{esc(act.name)}</h2>
          </div>
          <div class="act-body">
            {"<p class='act-desc'>" + esc(act.description) + "</p>" if act.description else ""}
            <div class="meta-row">
              <div class="meta-block"><span class="meta-label">Rôles</span><div>{roles_html}</div></div>
              <div class="meta-block"><span class="meta-label">Outils</span><div>{tools_html}</div></div>
            </div>

            {"<h3 class='section-h'>Tâches</h3><div class='table-wrap'><table><thead><tr><th>Tâche</th><th>Description</th><th>Durée (h)</th><th>Délai (h)</th><th>Outils</th></tr></thead><tbody>" + tasks_rows + "</tbody></table></div>" if a["tasks"] else ""}

            {"<h3 class='section-h'>Contraintes</h3><div class='table-wrap'><table><thead><tr><th>Description</th><th>Fichier lié</th></tr></thead><tbody>" + constr_rows + "</tbody></table></div>" if a["constraints"] else ""}
          </div>
        </div>""")

    acts_html = "\n".join(act_blocks) if act_blocks else '<p class="no-data">Aucune activité.</p>'

    # ── Tableau rôles ────────────────────────────────────────
    roles_rows = "".join(
        f"""<tr>
          <td><strong>{esc(r.name)}</strong></td>
          <td>{esc(", ".join(a["activity"].name for a in data["activities"] if r in a["roles"])) or "—"}</td>
        </tr>""" for r in data["roles"]
    ) or '<tr><td colspan="2" class="empty">Aucun rôle</td></tr>'

    filter_badge = f'<span class="filter-badge"><i class="icon">🎯</i> Filtre rôle : {esc(role_label)}</span>' if role_label else ""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Export — {esc(entity.name)}</title>
<style>
  :root {{
    --purple: #5b21b6; --indigo: #4338ca; --violet: #7c3aed;
    --violet-lt: #ede9fe; --violet-mid: #ddd6fe;
    --white: #ffffff; --gray: #f5f3ff; --text: #1e1040; --muted: #6b7280;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #f0ebff; color: var(--text); }}

  /* ── Hero ── */
  .hero {{
    background: linear-gradient(155deg, #12053d 0%, #2e0f6b 35%, #4c1d95 65%, #4338ca 100%);
    padding: 48px 40px 40px; position: relative; overflow: hidden;
  }}
  .hero::before {{
    content:''; position:absolute; top:-60px; right:-60px; width:260px; height:260px;
    background:radial-gradient(circle, rgba(216,180,254,.4) 0%, transparent 70%); border-radius:50%;
  }}
  .hero-brand {{ display:flex; align-items:center; gap:10px; margin-bottom:20px; }}
  .hero-logo {{ width:38px;height:38px;background:rgba(255,255,255,.15);border:1.5px solid rgba(255,255,255,.3);
    border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;color:#e9d5ff;font-weight:900; }}
  .hero-name {{ font-size:14px;font-weight:800;color:rgba(255,255,255,.8);letter-spacing:2px;text-transform:uppercase; }}
  .hero-title {{ font-size:30px;font-weight:800;color:#fff;line-height:1.2;margin-bottom:8px; }}
  .hero-sub {{ font-size:14px;color:rgba(221,214,254,.75); }}
  .hero-meta {{ display:flex;flex-wrap:wrap;gap:10px;margin-top:18px; }}
  .meta-pill {{ background:rgba(255,255,255,.1);border:1px solid rgba(196,181,253,.35);border-radius:20px;
    padding:5px 14px;font-size:12px;color:#e9d5ff;font-weight:600; }}
  .filter-badge {{ background:rgba(74,222,128,.15);border:1px solid rgba(74,222,128,.4);border-radius:20px;
    padding:5px 14px;font-size:12px;color:#86efac;font-weight:600; }}

  /* ── Contenu ── */
  .container {{ max-width:1100px;margin:0 auto;padding:36px 24px; }}
  .section-title {{ font-size:20px;font-weight:800;color:var(--purple);margin:36px 0 16px;
    display:flex;align-items:center;gap:10px; }}
  .section-title::after {{ content:'';flex:1;height:2px;background:linear-gradient(to right,var(--violet-mid),transparent); }}

  /* ── Carte activité ── */
  .act-card {{ background:#fff;border-radius:18px;border:1px solid var(--violet-mid);
    box-shadow:0 4px 20px rgba(109,40,217,.08);margin-bottom:20px;overflow:hidden;
    border-left:4px solid var(--accent,#7c3aed); }}
  .act-header {{ display:flex;align-items:center;gap:14px;padding:16px 24px;
    background:linear-gradient(to right,var(--gray),#fff); }}
  .act-num {{ width:36px;height:36px;background:var(--accent,#7c3aed);border-radius:10px;
    display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;color:#fff;flex-shrink:0; }}
  .act-title {{ font-size:17px;font-weight:700;color:var(--text); }}
  .act-body {{ padding:16px 24px 20px; }}
  .act-desc {{ color:var(--muted);font-size:13.5px;line-height:1.6;margin-bottom:14px; }}

  /* ── Meta row ── */
  .meta-row {{ display:flex;flex-wrap:wrap;gap:16px;margin-bottom:16px; }}
  .meta-block {{ flex:1;min-width:180px; }}
  .meta-label {{ font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
    color:var(--muted);display:block;margin-bottom:6px; }}
  .tag {{ display:inline-flex;align-items:center;gap:4px;background:var(--violet-lt);
    border:1px solid var(--violet-mid);border-radius:20px;padding:3px 10px;
    font-size:12px;font-weight:600;color:var(--purple);margin:2px; }}
  .tag-tool {{ background:#fef3c7;border-color:#fde68a;color:#92400e; }}

  /* ── Tables ── */
  .section-h {{ font-size:13px;font-weight:700;color:var(--indigo);text-transform:uppercase;
    letter-spacing:.5px;margin:16px 0 8px;display:flex;align-items:center;gap:6px; }}
  .section-h::before {{ content:'';width:3px;height:14px;background:var(--accent,#7c3aed);border-radius:2px;flex-shrink:0; }}
  .table-wrap {{ overflow-x:auto;border-radius:10px;border:1px solid var(--violet-mid); }}
  table {{ width:100%;border-collapse:collapse;font-size:13px; }}
  thead {{ background:linear-gradient(to right,#4c1d95,#4338ca); }}
  thead th {{ color:#fff;padding:10px 14px;text-align:left;font-weight:700;font-size:12px; }}
  tbody tr:nth-child(even) {{ background:var(--gray); }}
  tbody tr:nth-child(odd) {{ background:#fff; }}
  tbody td {{ padding:9px 14px;border-top:1px solid var(--violet-lt);vertical-align:top;line-height:1.5; }}
  .empty {{ color:var(--muted);font-style:italic;text-align:center; }}
  .file-chip {{ display:inline-block;background:#fdf4ff;border:1px solid #f0abfc;border-radius:6px;
    padding:2px 8px;font-size:11px;color:#7e22ce;word-break:break-all; }}

  /* ── Tableau rôles ── */
  .roles-table {{ background:#fff;border-radius:14px;border:1px solid var(--violet-mid);overflow:hidden; }}

  /* ── Footer ── */
  .footer {{ text-align:center;padding:32px;color:var(--muted);font-size:12px; }}
  .footer strong {{ color:var(--purple); }}

  @media print {{
    body {{ background:#fff; }}
    .hero {{ -webkit-print-color-adjust:exact;print-color-adjust:exact; }}
    .act-card {{ break-inside:avoid; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-brand">
    <div class="hero-logo">◉</div>
    <span class="hero-name">OPTIQ</span>
  </div>
  <h1 class="hero-title">{esc(entity.name)}</h1>
  <p class="hero-sub">{esc(entity.description) if entity.description else "Export des activités et données métier"}</p>
  <div class="hero-meta">
    <span class="meta-pill">📋 {len(data["activities"])} activité{"s" if len(data["activities"]) > 1 else ""}</span>
    <span class="meta-pill">👥 {len(data["roles"])} rôle{"s" if len(data["roles"]) > 1 else ""}</span>
    <span class="meta-pill">🗓 Exporté le {now}</span>
    {filter_badge}
  </div>
</div>

<div class="container">

  {"<h2 class='section-title'>Rôles</h2><div class='roles-table table-wrap'><table><thead><tr><th>Rôle</th><th>Activités associées</th></tr></thead><tbody>" + roles_rows + "</tbody></table></div>" if data["roles"] else ""}

  <h2 class="section-title">Activités</h2>
  {acts_html}

</div>

<div class="footer">
  Généré par <strong>OPTIQ</strong> · {now}
</div>

</body>
</html>"""

    return html


# ──────────────────────────────────────────────
# Routes d'export
# ──────────────────────────────────────────────
@export_bp.route("/export/entity")
def export_entity():
    entity_id = request.args.get("entity_id", type=int)
    role_id   = request.args.get("role_id",   type=int) or None
    fmt       = request.args.get("format", "excel").lower()

    if not entity_id:
        return jsonify({"error": "entity_id requis"}), 400

    data = _collect_entity_data(entity_id, role_id)
    if not data:
        return jsonify({"error": "Entité introuvable"}), 404

    role_label = None
    if role_id:
        role = Role.query.get(role_id)
        role_label = role.name if role else None

    entity_name = data["entity"].name
    date_str    = datetime.now().strftime("%Y%m%d")
    role_suffix = f"_{role_label.replace(' ', '_')}" if role_label else ""

    if fmt == "html":
        html_content = _make_html(data, role_label)
        filename = f"export_{entity_name}{role_suffix}_{date_str}.html"
        return Response(
            html_content,
            mimetype="text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    else:
        buf = _make_excel(data, role_label)
        filename = f"export_{entity_name}{role_suffix}_{date_str}.xlsx"
        return send_file(
            buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True, download_name=filename
        )
