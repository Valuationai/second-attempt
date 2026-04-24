"""DiligenceAI — pdf_export.py — PDF report builder using reportlab."""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

C_BG     = colors.HexColor("#080C14")
C_CARD   = colors.HexColor("#0F1620")
C_BLUE   = colors.HexColor("#4F8EF7")
C_TEAL   = colors.HexColor("#00D4AA")
C_PURPLE = colors.HexColor("#9B6DFF")
C_AMBER  = colors.HexColor("#F5A623")
C_RED    = colors.HexColor("#FF5C6A")
C_TEXT   = colors.HexColor("#F0F4FF")
C_SUB    = colors.HexColor("#8B9BC8")
C_MUTED  = colors.HexColor("#4A5578")
C_BORDER = colors.HexColor("#1A2340")


def _s(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10, textColor=C_TEXT, leading=14, spaceAfter=4)
    base.update(kw)
    return ParagraphStyle(name, **base)


def build_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    s_title  = _s("ti", fontSize=22, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
    s_sub    = _s("su", fontSize=11, textColor=C_SUB,   alignment=TA_CENTER, spaceAfter=16)
    s_label  = _s("lb", fontSize=7,  fontName="Helvetica-Bold", textColor=C_MUTED, spaceAfter=4)
    s_h2     = _s("h2", fontSize=13, fontName="Helvetica-Bold", textColor=C_BLUE, spaceBefore=14, spaceAfter=6)
    s_body   = _s("bo", fontSize=10, textColor=C_SUB,   leading=15, spaceAfter=6)
    s_footer = _s("ft", fontSize=8,  textColor=C_MUTED, alignment=TA_CENTER)

    lbl  = data.get("health_label", "Moderate")
    score = data.get("health_score", 5)
    hcol = {"Strong": C_TEAL, "Moderate": C_AMBER, "Weak": C_RED}.get(lbl, C_AMBER)
    div  = HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=10)

    story = []
    story.append(Paragraph("FINANCIAL STATEMENT ANALYSIS", s_title))
    story.append(Paragraph("DiligenceAI — AI-Powered Financial Analysis", s_sub))
    story.append(div)

    story.append(Paragraph(
        f"{data.get('company_name','Unknown')}  ·  {data.get('period','')}",
        _s("co", fontSize=14, fontName="Helvetica-Bold", spaceAfter=2)
    ))
    story.append(Paragraph(
        f"Financial Health: {lbl}  |  Score: {score} / 10",
        _s("hs", fontSize=12, fontName="Helvetica-Bold", textColor=hcol, spaceAfter=12)
    ))
    story.append(div)

    story.append(Paragraph("EXECUTIVE SUMMARY", s_label))
    story.append(Paragraph(data.get("health_summary", ""), s_body))
    story.append(Spacer(1, 6))
    story.append(Paragraph("INVESTOR VIEW", s_label))
    story.append(Paragraph(data.get("investor_view", ""), s_body))
    story.append(div)

    # KPI table
    story.append(Paragraph("KEY FINANCIAL METRICS", s_h2))
    kpi_keys = [
        ("revenue",            "Revenue"),
        ("net_profit",         "Net Profit"),
        ("gross_margin",       "Gross Margin"),
        ("net_margin",         "Net Margin"),
        ("ebitda",             "EBITDA"),
        ("operating_cashflow", "Operating Cash Flow"),
        ("current_ratio",      "Current Ratio"),
        ("debt_to_equity",     "Debt / Equity"),
        ("working_capital",    "Working Capital"),
        ("total_debt",         "Total Debt"),
    ]
    kpis = data.get("kpis", {})
    tdata = [["Metric", "Value", "Commentary"]]
    for key, label in kpi_keys:
        item = kpis.get(key, {})
        tdata.append([label, item.get("value", "N/A"), item.get("note", "")])

    t = Table(tdata, colWidths=[5*cm, 4*cm, 8*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",      (0, 0),  (-1, 0),  C_BLUE),
        ("TEXTCOLOR",       (0, 0),  (-1, 0),  colors.white),
        ("FONTNAME",        (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",        (0, 0),  (-1, -1), 9),
        ("ROWBACKGROUNDS",  (0, 1),  (-1, -1), [C_CARD, C_BG]),
        ("TEXTCOLOR",       (0, 1),  (-1, -1), C_SUB),
        ("TEXTCOLOR",       (1, 1),  (1,  -1), C_BLUE),
        ("FONTNAME",        (1, 1),  (1,  -1), "Helvetica-Bold"),
        ("GRID",            (0, 0),  (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING",      (0, 0),  (-1, -1), 5),
        ("BOTTOMPADDING",   (0, 0),  (-1, -1), 5),
        ("LEFTPADDING",     (0, 0),  (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))
    story.append(div)

    # Analysis sections
    for sec_key, sec_title, accent in [
        ("profitability",            "Profitability",   C_BLUE),
        ("cash_health",              "Cash Health",     C_TEAL),
        ("working_capital_analysis", "Working Capital", C_PURPLE),
        ("balance_sheet",            "Balance Sheet",   C_AMBER),
    ]:
        sec = data.get(sec_key, {})
        story.append(Paragraph(
            sec_title.upper(),
            _s(f"sh_{sec_key}", fontSize=13, fontName="Helvetica-Bold",
               textColor=accent, spaceBefore=14, spaceAfter=6)
        ))
        story.append(Paragraph(sec.get("headline", ""), s_body))
        for pt in sec.get("points", []):
            story.append(Paragraph(f"• {pt}", s_body))
        story.append(Spacer(1, 4))

    story.append(div)

    # Risks
    story.append(Paragraph(
        "KEY RISKS & CONCERNS",
        _s("rh", fontSize=13, fontName="Helvetica-Bold", textColor=C_RED, spaceBefore=6, spaceAfter=6)
    ))
    for risk in data.get("risks", []):
        story.append(Paragraph(f"<b>{risk.get('title','')}</b>",
                               _s("rt", fontSize=10, textColor=C_RED, spaceAfter=2)))
        story.append(Paragraph(f"Issue: {risk.get('detail','')}", s_body))
        story.append(Paragraph(f"Action: {risk.get('fix','')}",
                               _s("rf", fontSize=10, textColor=C_TEAL, leading=15, spaceAfter=6)))

    # Positives
    story.append(Paragraph(
        "POSITIVE SIGNALS",
        _s("ph", fontSize=13, fontName="Helvetica-Bold", textColor=C_TEAL, spaceBefore=6, spaceAfter=6)
    ))
    for pos in data.get("positives", []):
        story.append(Paragraph(f"<b>{pos.get('title','')}</b>",
                               _s("pt", fontSize=10, textColor=C_TEAL, spaceAfter=2)))
        story.append(Paragraph(pos.get("detail", ""), s_body))

    # Recommendations
    story.append(Paragraph("RECOMMENDATIONS", s_h2))
    for i, rec in enumerate(data.get("recommendations", []), 1):
        story.append(Paragraph(f"<b>{i}. {rec.get('action','')}</b>",
                               _s(f"rc{i}", fontSize=10, textColor=C_BLUE, spaceAfter=2)))
        story.append(Paragraph(rec.get("rationale", ""), s_body))

    story.append(div)
    story.append(Paragraph(
        "DiligenceAI  ·  For informational purposes only — not financial advice.",
        s_footer
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
