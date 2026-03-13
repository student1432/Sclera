"""
report_generator.py — Phase 2: Beautiful PDF Report Generation
Backend: xhtml2pdf (pure Python, no system libraries needed — works on Windows/Mac/Linux)
Install: pip install xhtml2pdf

Charts are rendered as inline SVG so no matplotlib/pillow dependencies.
"""
from __future__ import annotations

import io
import math
from datetime import datetime, timedelta, date

try:
    from xhtml2pdf import pisa
    import logging
    # Suppress pdfminer font warnings (harmless)
    logging.getLogger("pdfminer.pdffont").setLevel(logging.ERROR)
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# SVG / Chart helpers
# ──────────────────────────────────────────────────────────────────────────────

def _donut_svg(pct: float, color: str = "#22c55e", size: int = 70) -> str:
    pct = max(0.0, min(100.0, float(pct)))
    r = 24
    circumference = 2 * math.pi * r
    filled = (pct / 100) * circumference
    cx = cy = size // 2
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#e5e7eb" stroke-width="7"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="7" '
        f'stroke-dasharray="{filled:.2f} {circumference:.2f}" '
        f'stroke-dashoffset="{circumference / 4:.2f}" stroke-linecap="round"/>'
        f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
        f'font-size="10" font-weight="bold" fill="#111827">{pct:.0f}%</text>'
        f'</svg>'
    )


def _bar_chart_svg(values: list, labels: list,
                   color: str = "#22c55e",
                   width: int = 460, height: int = 120) -> str:
    if not values or not any(v > 0 for v in values):
        return ""
    n = len(values)
    max_val = max(values) or 1
    bar_area_h = height - 26
    bar_w = max(12, (width - (n + 1) * 8) // n)
    gap = max(6, (width - n * bar_w) // (n + 1))
    parts = []
    for i, (v, lbl) in enumerate(zip(values, labels)):
        bh = int((float(v) / max_val) * bar_area_h)
        x = gap + i * (bar_w + gap)
        y = bar_area_h - bh
        parts.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{color}" rx="3"/>'
            f'<text x="{x + bar_w // 2}" y="{height - 6}" '
            f'text-anchor="middle" font-size="9" fill="#6b7280">{lbl}</text>'
        )
        if v > 0:
            parts.append(
                f'<text x="{x + bar_w // 2}" y="{y - 3}" '
                f'text-anchor="middle" font-size="8" fill="{color}">{int(v)}</text>'
            )
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'
    )


def _heatmap_html(heatmap_data: dict) -> str:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    max_val = max(heatmap_data.values(), default=1) or 1
    hour_headers = '<td style="width:28px"></td>' + "".join(
        f'<td style="font-size:7px;color:#9ca3af;text-align:center;padding:1px 1px">{h}</td>'
        for h in range(0, 24, 2)
    )
    rows = [f'<tr>{hour_headers}</tr>']
    for d_idx, day in enumerate(days):
        cells = [f'<td style="font-size:8px;font-weight:bold;color:#374151;padding:1px 2px;white-space:nowrap">{day}</td>']
        for h in range(0, 24, 2):
            count = (heatmap_data.get(f"{d_idx}-{h}", 0)
                     + heatmap_data.get(f"{d_idx}-{h+1}", 0))
            intensity = min(1.0, count / max_val)
            g_val = int(197 + (255 - 197) * (1 - intensity))
            bg = f"rgb(34,{g_val},94)" if count else "#f3f4f6"
            cells.append(
                f'<td style="width:13px;height:13px;background:{bg};'
                f'border-radius:2px;padding:0;font-size:1px">&nbsp;</td>'
            )
        rows.append(f'<tr>{"".join(cells)}</tr>')
    return (
        '<table style="border-collapse:separate;border-spacing:2px;margin:0">'
        + "".join(rows) + '</table>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# Shared print CSS
# ──────────────────────────────────────────────────────────────────────────────

_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 12px;
       line-height: 1.5; color: #111827; background: #fff; }
h1 { font-size: 20px; font-weight: bold; color: #111827; margin-bottom: 3px; }
h2 { font-size: 13px; font-weight: bold; color: #111827;
     border-left: 4px solid #22c55e; padding-left: 8px;
     margin: 16px 0 7px; }
h3 { font-size: 11px; font-weight: bold; color: #374151; margin-bottom: 4px; }
p  { margin-bottom: 4px; font-size: 11px; }

.rpt-header-left  { font-size: 12px; }
.rpt-header-right { font-size: 10px; color: #6b7280; text-align: right; }

.stat-num { font-size: 24px; font-weight: bold; color: #22c55e; }
.stat-num-red { color: #ef4444; }
.stat-lbl { font-size: 8px; color: #6b7280; text-transform: uppercase; letter-spacing: .4px; }

.card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px;
        padding: 10px; margin-bottom: 10px; }

table.dt { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 11px; }
table.dt th { background: #f3f4f6; padding: 6px 8px; text-align: left;
              font-weight: bold; color: #6b7280; font-size: 8px;
              text-transform: uppercase; border-bottom: 1px solid #e5e7eb; }
table.dt td { padding: 5px 8px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
table.dt tr:last-child td { border-bottom: none; }

.pb-track { background: #e5e7eb; border-radius: 3px; height: 6px; }
.pb-fill   { background: #22c55e; border-radius: 3px; height: 6px; }

.badge { display: inline; padding: 2px 7px; border-radius: 10px;
         font-size: 9px; font-weight: bold; }
.bg-green  { background: #dcfce7; color: #166534; }
.bg-red    { background: #fee2e2; color: #991b1b; }
.bg-yellow { background: #fef9c3; color: #854d0e; }
.bg-gray   { background: #f3f4f6; color: #374151; }
.bg-blue   { background: #dbeafe; color: #1e40af; }

.footer { margin-top: 20px; padding-top: 7px; border-top: 1px solid #e5e7eb;
          font-size: 8px; color: #9ca3af; text-align: center; }
"""


# ──────────────────────────────────────────────────────────────────────────────
# HTML builders
# ──────────────────────────────────────────────────────────────────────────────

def _class_report_html(class_data, teacher_name, institution_name,
                       students, at_risk, heatmap_data, clusters, generated_on):
    avg_prog = round(
        sum(s.get("progress_overall", 0) for s in students) / max(len(students), 1), 1
    )

    at_risk_rows = ""
    for s in at_risk:
        prog = s.get("progress_overall", 0)
        status = s.get("status", s.get("risk_level", "stagnating"))
        bcls = "bg-red" if status in ("critical", "at_risk") else "bg-yellow"
        note = (s.get("explanation") or "")[:80]
        at_risk_rows += (
            f'<tr>'
            f'<td><strong>{s.get("name","")}</strong></td>'
            f'<td><span class="badge {bcls}">{status.replace("_"," ").title()}</span></td>'
            f'<td><div class="pb-track"><div class="pb-fill" style="width:{prog}%"></div></div>'
            f'<span style="font-size:8px;color:#6b7280">{prog}%</span></td>'
            f'<td style="font-size:9px">{s.get("readiness_score") or "—"}{"%" if s.get("readiness_score") else ""}</td>'
            f'<td style="font-size:9px;color:#6b7280">{note}{"…" if len(s.get("explanation","")) > 80 else ""}</td>'
            f'</tr>'
        )
    if not at_risk_rows:
        at_risk_rows = '<tr><td colspan="5" style="text-align:center;color:#6b7280;padding:12px">No at-risk students detected</td></tr>'

    all_rows = ""
    for s in students:
        prog = s.get("progress_overall", 0)
        avg_ex = s.get("avg_exam_score", 0)
        days = s.get("days_inactive", 999)
        risk = s.get("risk_level", "healthy")
        bcls = "bg-red" if risk in ("critical","at_risk") else ("bg-yellow" if risk in ("stagnating","declining") else "bg-green")
        last_txt = "Today" if days == 0 else ("Never" if days == 999 else f"{days}d ago")
        all_rows += (
            f'<tr>'
            f'<td>{s.get("name","Unknown")}</td>'
            f'<td><div class="pb-track"><div class="pb-fill" style="width:{prog}%"></div></div>'
            f'<span style="font-size:8px;color:#6b7280">{prog}%</span></td>'
            f'<td style="font-size:10px">{"—" if not avg_ex else f"{avg_ex}%"}</td>'
            f'<td style="font-size:9px;color:#6b7280">{last_txt}</td>'
            f'<td><span class="badge {bcls}">{risk.replace("_"," ").title()}</span></td>'
            f'</tr>'
        )

    cluster_html = ""
    if clusters:
        for cl in clusters:
            cluster_html += (
                f'<div class="card" style="margin-bottom:8px">'
                f'<h3>{cl.get("label","Cluster")}</h3>'
                f'<p style="color:#6b7280">{cl.get("description","")}</p>'
                f'<p style="margin-top:3px"><strong>{cl.get("student_count",0)}</strong> students</p>'
                f'</div>'
            )

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>{_CSS}</style></head><body>

<table width="100%" style="border-bottom:2px solid #22c55e;padding-bottom:10px;margin-bottom:16px">
  <tr>
    <td class="rpt-header-left">
      <h1>{class_data.get("name","Class")}</h1>
      <p style="color:#6b7280">Class Report &mdash; {teacher_name}</p>
    </td>
    <td class="rpt-header-right">
      <strong>Generated</strong><br>{generated_on}<br>
      <span class="badge bg-gray">{institution_name}</span>
    </td>
  </tr>
</table>

<table width="100%" style="margin-bottom:16px">
  <tr>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <div class="stat-num">{len(students)}</div><div class="stat-lbl">Students</div>
    </td>
    <td width="4%"></td>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <div class="stat-num">{avg_prog}%</div><div class="stat-lbl">Avg Progress</div>
    </td>
    <td width="4%"></td>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <div class="stat-num stat-num-red">{len(at_risk)}</div><div class="stat-lbl">At-Risk</div>
    </td>
  </tr>
</table>

<h2>Study Activity Heatmap (Last 30 Days)</h2>
<div class="card" style="overflow:hidden">{_heatmap_html(heatmap_data)}</div>

<h2>At-Risk Students</h2>
<table class="dt">
  <thead><tr><th>Name</th><th>Status</th><th>Progress</th><th>Readiness</th><th>Notes</th></tr></thead>
  <tbody>{at_risk_rows}</tbody>
</table>

{"<h2>Study Pattern Clusters</h2>" + cluster_html if clusters else ""}

<h2>All Students</h2>
<table class="dt">
  <thead><tr><th>Name</th><th>Progress</th><th>Avg Exam</th><th>Last Active</th><th>Risk</th></tr></thead>
  <tbody>{all_rows}</tbody>
</table>

<div class="footer">Sclera Academic &mdash; Confidential Teacher Report &mdash; {generated_on}</div>
</body></html>"""


def _student_report_html(student_data, progress_data, recent_results,
                          sessions, class_name, risk_info, generated_on):
    by_subject = progress_data.get("by_subject", {})
    overall = progress_data.get("overall", 0)
    momentum = progress_data.get("momentum", 0)
    readiness_score = risk_info.get("readiness_score", 0)
    readiness_summary = risk_info.get("readiness_summary", "")
    risk_level = risk_info.get("risk_level", "healthy")
    risk_explanation = risk_info.get("explanation", "")

    results = student_data.get("exam_results", [])
    pcts = []
    for r in results:
        try:
            sc = float(r.get("score", 0)); mx = float(r.get("max_score", 100))
            if mx: pcts.append((sc / mx) * 100)
        except Exception:
            pass
    avg_exam = round(sum(pcts) / len(pcts), 1) if pcts else 0

    # Subject donuts — HTML table of SVGs
    donut_cells = ""
    for subj, pct in by_subject.items():
        color = "#22c55e" if pct >= 70 else ("#f59e0b" if pct >= 40 else "#ef4444")
        donut_cells += (
            f'<td style="text-align:center;padding:5px 6px;vertical-align:top">'
            f'{_donut_svg(float(pct), color=color)}'
            f'<div style="font-size:8px;font-weight:bold;color:#374151;margin-top:3px">'
            f'{subj[:16]}</div></td>'
        )
    donut_html = (
        f'<table width="100%" style="border-collapse:collapse"><tr>{donut_cells}</tr></table>'
        if donut_cells else "<p style='color:#6b7280'>No subjects tracked.</p>"
    )

    # 7-day chart
    today = date.today()
    day_labels = [(today - timedelta(days=i)).strftime("%a") for i in range(6, -1, -1)]
    day_buckets = {l: 0 for l in day_labels}
    for s in sessions:
        try:
            sd = datetime.fromisoformat(s.get("start_time","")).date()
            delta = (today - sd).days
            if 0 <= delta <= 6:
                lbl = sd.strftime("%a")
                day_buckets[lbl] = day_buckets.get(lbl, 0) + s.get("duration_seconds", 0) // 60
        except Exception:
            pass
    study_vals = [day_buckets.get(l, 0) for l in day_labels]
    study_chart = _bar_chart_svg(study_vals, day_labels) if any(v > 0 for v in study_vals) else ""

    # Exam rows
    exam_rows = ""
    for r in recent_results:
        sc = r.get("score", 0); mx = r.get("max_score", 100)
        pct_val = round((float(sc) / float(mx)) * 100, 1) if mx else 0
        exam_rows += (
            f'<tr>'
            f'<td>{r.get("test_type","Exam")}</td>'
            f'<td>{r.get("subject","—")}</td>'
            f'<td>{sc}/{mx}</td>'
            f'<td><div class="pb-track"><div class="pb-fill" style="width:{pct_val}%"></div></div>'
            f'<span style="font-size:8px;color:#6b7280">{pct_val}%</span></td>'
            f'<td style="font-size:9px;color:#6b7280">{str(r.get("date",""))[:10]}</td>'
            f'</tr>'
        )
    if not exam_rows:
        exam_rows = '<tr><td colspan="5" style="text-align:center;color:#6b7280;padding:10px">No exam results recorded.</td></tr>'

    risk_bcls = "bg-red" if risk_level in ("critical","at_risk") else ("bg-yellow" if risk_level in ("stagnating","declining") else "bg-green")
    mom_color = "#22c55e" if momentum >= 0 else "#ef4444"
    mom_sign = "+" if momentum > 0 else ""

    ai_section = ""
    if readiness_score or risk_level not in ("healthy",):
        ai_section = f"""
<h2>AI Insights</h2>
<table width="100%" style="margin-bottom:12px">
  <tr>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <div class="stat-num" style="color:{mom_color}">{mom_sign}{momentum}</div><div class="stat-lbl">Momentum</div>
    </td>
    <td width="4%"></td>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <div class="stat-num" style="color:#3b82f6">{readiness_score or "—"}{"%" if readiness_score else ""}</div><div class="stat-lbl">Readiness</div>
    </td>
    <td width="4%"></td>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <span class="badge {risk_bcls}" style="font-size:11px">{risk_level.replace("_"," ").title()}</span>
      <div class="stat-lbl" style="margin-top:5px">Risk Level</div>
    </td>
  </tr>
</table>
{"<div class='card' style='border-left:4px solid #3b82f6;margin-bottom:8px'><strong style='font-size:9px;color:#3b82f6'>AI READINESS SUMMARY</strong><p style='margin-top:3px'>" + readiness_summary + "</p></div>" if readiness_summary else ""}
{"<div class='card' style='border-left:4px solid #ef4444'><strong style='font-size:9px;color:#ef4444'>RISK EXPLANATION</strong><p style='margin-top:3px'>" + risk_explanation + "</p></div>" if risk_explanation else ""}
"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>{_CSS}</style></head><body>

<table width="100%" style="border-bottom:2px solid #22c55e;padding-bottom:10px;margin-bottom:16px">
  <tr>
    <td class="rpt-header-left">
      <h1>{student_data.get("name","Student")}</h1>
      <p style="color:#6b7280">{student_data.get("email","")}</p>
    </td>
    <td class="rpt-header-right">
      <strong>Generated</strong><br>{generated_on}<br>
      {"<span class='badge bg-gray'>" + class_name + "</span>" if class_name else ""}
    </td>
  </tr>
</table>

<table width="100%" style="margin-bottom:14px">
  <tr>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <div class="stat-num">{overall}%</div><div class="stat-lbl">Overall Progress</div>
    </td>
    <td width="4%"></td>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <div class="stat-num">{"—" if not avg_exam else f"{avg_exam}%"}</div><div class="stat-lbl">Avg Exam Score</div>
    </td>
    <td width="4%"></td>
    <td width="33%" style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;text-align:center;padding:10px 4px">
      <div class="stat-num">{student_data.get("login_streak",0)}</div><div class="stat-lbl">Day Streak</div>
    </td>
  </tr>
</table>

{ai_section}

<h2>Subject Progress</h2>
<div class="card">{donut_html}</div>

<h2>Recent Exam Results</h2>
<table class="dt">
  <thead><tr><th>Test Type</th><th>Subject</th><th>Score</th><th>Percentage</th><th>Date</th></tr></thead>
  <tbody>{exam_rows}</tbody>
</table>

{"<h2>Study Time — Last 7 Days (minutes)</h2><div class='card'>" + study_chart + "</div>" if study_chart else ""}

<div class="footer">Sclera Academic &mdash; Confidential Teacher Report &mdash; {generated_on}</div>
</body></html>"""


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def _html_to_pdf(html: str) -> bytes:
    if not XHTML2PDF_AVAILABLE:
        raise RuntimeError(
            "xhtml2pdf is not installed.\n"
            "Run:  pip install xhtml2pdf\n"
            "No system libraries required — works on Windows, Mac, and Linux."
        )
    buf = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html), dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError(f"xhtml2pdf error (code {result.err}) — check HTML for invalid tags.")
    return buf.getvalue()


def generate_class_report_pdf(
    class_data: dict,
    teacher_name: str,
    institution_name: str,
    students: list,
    at_risk: list,
    heatmap_data: dict,
    clusters: list | None = None,
) -> bytes:
    html = _class_report_html(
        class_data=class_data,
        teacher_name=teacher_name,
        institution_name=institution_name,
        students=students,
        at_risk=at_risk,
        heatmap_data=heatmap_data,
        clusters=clusters or [],
        generated_on=datetime.utcnow().strftime("%d %B %Y, %H:%M UTC"),
    )
    return _html_to_pdf(html)


def generate_student_report_pdf(
    student_data: dict,
    student_uid: str,
    progress_data: dict,
    recent_results: list,
    sessions: list,
    class_name: str = "",
    risk_info: dict | None = None,
) -> bytes:
    html = _student_report_html(
        student_data=student_data,
        progress_data=progress_data,
        recent_results=recent_results,
        sessions=sessions,
        class_name=class_name,
        risk_info=risk_info or {},
        generated_on=datetime.utcnow().strftime("%d %B %Y, %H:%M UTC"),
    )
    return _html_to_pdf(html)
