import streamlit as st
from groq import Groq
import io
import os
import csv
import json
import re
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter

# ─────────────────────────────────────────────────────────────────────────────
# FILE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
                for table in page.extract_tables():
                    for row in table:
                        parts.append(" | ".join(str(c).strip() if c else "" for c in row))
        return "\n".join(parts)
    except Exception as e:
        return f"[PDF error: {e}]"


def extract_text_from_csv(file_bytes: bytes) -> str:
    try:
        content = file_bytes.decode("utf-8", errors="replace")
        rows = [" | ".join(r) for r in csv.reader(io.StringIO(content))]
        return "\n".join(rows)
    except Exception as e:
        return f"[CSV error: {e}]"


def extract_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(raw)
    if name.endswith(".csv"):
        return extract_text_from_csv(raw)
    return raw.decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a highly skilled financial analyst and forensic accountant.
Analyse the provided financial statements and return ONLY a valid JSON object — no markdown, no extra text.

The JSON must follow this exact schema:

{
  "company_name": "string or 'Unknown Company'",
  "period": "string e.g. 'FY 2023' or 'Not provided'",
  "health_score": integer 1-10,
  "health_label": "Strong" | "Moderate" | "Weak",
  "health_summary": "2-3 sentence executive summary of financial health",

  "kpis": {
    "revenue":            {"value": "string", "note": "string"},
    "net_profit":         {"value": "string", "note": "string"},
    "gross_margin":       {"value": "string", "note": "string"},
    "net_margin":         {"value": "string", "note": "string"},
    "ebitda":             {"value": "string", "note": "string"},
    "operating_cashflow": {"value": "string", "note": "string"},
    "current_ratio":      {"value": "string", "note": "string"},
    "debt_to_equity":     {"value": "string", "note": "string"},
    "working_capital":    {"value": "string", "note": "string"},
    "total_debt":         {"value": "string", "note": "string"}
  },

  "profitability": {
    "headline": "string",
    "points": ["string", "string", "string"]
  },
  "cash_health": {
    "headline": "string",
    "points": ["string", "string", "string"]
  },
  "working_capital_analysis": {
    "headline": "string",
    "points": ["string", "string", "string"]
  },
  "balance_sheet": {
    "headline": "string",
    "points": ["string", "string", "string"]
  },

  "investor_view": "3-4 sentence blunt PE-investor style interpretation",

  "risks": [
    {"title": "string", "detail": "string", "fix": "string"},
    {"title": "string", "detail": "string", "fix": "string"},
    {"title": "string", "detail": "string", "fix": "string"}
  ],

  "positives": [
    {"title": "string", "detail": "string"},
    {"title": "string", "detail": "string"},
    {"title": "string", "detail": "string"}
  ],

  "recommendations": [
    {"action": "string", "rationale": "string"},
    {"action": "string", "rationale": "string"},
    {"action": "string", "rationale": "string"}
  ]
}

Rules:
- Use "Not provided" for any missing data — never invent numbers.
- All value strings should be formatted (e.g. "$12.4M", "18.3%", "2.1x").
- notes should be brief trend indicators (up to 8 words), e.g. "Strong growth trend", "Margin under pressure".
- health_score: 8-10 = Strong, 5-7 = Moderate, 1-4 = Weak.
- Return ONLY the JSON object. No preamble, no explanation, no markdown fences.
"""


# ─────────────────────────────────────────────────────────────────────────────
# GROQ API CALL
# ─────────────────────────────────────────────────────────────────────────────

def analyse_financials(financial_text: str, api_key: str):
    client = Groq(api_key=api_key)

    max_chars = 24000
    if len(financial_text) > max_chars:
        financial_text = financial_text[:max_chars] + "\n\n[Truncated]"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=4096,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyse these financial statements:\n\n{financial_text}"},
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group()), raw
            except Exception:
                pass
        return None, raw


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL REPORT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_excel_report(data: dict) -> bytes:
    wb = Workbook()

    # ── Shared styles ─────────────────────────────────────────────────────────
    DARK_NAVY   = "0D1B2A"
    MID_NAVY    = "1B2A3B"
    ACCENT_BLUE = "2E5EAA"
    LIGHT_BLUE  = "D6E4F7"
    WHITE       = "FFFFFF"
    LIGHT_GREY  = "F5F7FA"
    MID_GREY    = "C5CDD9"
    GREEN_BG    = "E6F4EA"
    GREEN_FG    = "1A6B2E"
    RED_BG      = "FDE8E8"
    RED_FG      = "9B1C1C"
    AMBER_BG    = "FFF3CD"
    AMBER_FG    = "7D5A00"

    label_map = data.get("health_label", "Moderate")
    score     = data.get("health_score", 5)
    health_color = {"Strong": GREEN_FG, "Moderate": AMBER_FG, "Weak": RED_FG}.get(label_map, AMBER_FG)
    health_bg    = {"Strong": GREEN_BG, "Moderate": AMBER_BG, "Weak": RED_BG}.get(label_map, AMBER_BG)

    def hdr_font(size=11, bold=True, color=WHITE):
        return Font(name="Arial", size=size, bold=bold, color=color)

    def body_font(size=10, bold=False, color="000000"):
        return Font(name="Arial", size=size, bold=bold, color=color)

    def fill(hex_color):
        return PatternFill("solid", fgColor=hex_color)

    def thin_border(sides="all"):
        s = Side(style="thin", color=MID_GREY)
        n = Side(style=None)
        b = s if "all" in sides or "bottom" in sides else n
        t = s if "all" in sides or "top"    in sides else n
        l = s if "all" in sides or "left"   in sides else n
        r = s if "all" in sides or "right"  in sides else n
        return Border(left=l, right=r, top=t, bottom=b)

    def center():
        return Alignment(horizontal="center", vertical="center", wrap_text=True)

    def left_align(wrap=True):
        return Alignment(horizontal="left", vertical="center", wrap_text=wrap)

    def set_row_height(ws, row, height):
        ws.row_dimensions[row].height = height

    def merge_write(ws, cell_range, value, fnt, aln, fll=None, brd=None):
        ws.merge_cells(cell_range)
        cell = ws[cell_range.split(":")[0]]
        cell.value = value
        cell.font = fnt
        cell.alignment = aln
        if fll:
            cell.fill = fll
        if brd:
            cell.border = brd

    # =========================================================================
    # SHEET 1 — EXECUTIVE SUMMARY
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Executive Summary"
    ws1.sheet_view.showGridLines = False

    # Set column widths
    col_widths = [2, 28, 22, 22, 22, 22, 2]
    for i, w in enumerate(col_widths, 1):
        ws1.column_dimensions[get_column_letter(i)].width = w

    row = 1

    # ── Title bar ──────────────────────────────────────────────────────────────
    for r in range(row, row + 3):
        set_row_height(ws1, r, 6 if r != row + 1 else 36)
        for c in range(1, 8):
            ws1.cell(r, c).fill = fill(DARK_NAVY)

    merge_write(ws1, f"B{row+1}:F{row+1}",
                "FINANCIAL STATEMENT ANALYSIS",
                hdr_font(16, True, WHITE), center(), fill(DARK_NAVY))
    row += 3

    # ── Company / Period / Score row ──────────────────────────────────────────
    set_row_height(ws1, row, 4)
    ws1.cell(row, 1).fill = fill(MID_NAVY)
    row += 1

    for r in range(row, row + 4):
        set_row_height(ws1, r, 6 if r in (row, row+3) else 26)
        for c in range(1, 8):
            ws1.cell(r, c).fill = fill(MID_NAVY)

    # Company name
    ws1.merge_cells(f"B{row+1}:C{row+1}")
    c = ws1[f"B{row+1}"]
    c.value = data.get("company_name", "Unknown Company")
    c.font = hdr_font(13, True, WHITE); c.alignment = left_align(False)

    # Period
    ws1.merge_cells(f"D{row+1}:D{row+1}")
    c = ws1[f"D{row+1}"]
    c.value = data.get("period", "Not provided")
    c.font = hdr_font(11, False, MID_GREY); c.alignment = center()

    # Health label
    ws1.merge_cells(f"E{row+1}:E{row+1}")
    c = ws1[f"E{row+1}"]
    c.value = label_map
    c.font = Font(name="Arial", size=12, bold=True, color=health_color)
    c.fill = fill(health_bg); c.alignment = center()
    c.border = thin_border()

    # Score
    ws1.merge_cells(f"F{row+1}:F{row+1}")
    c = ws1[f"F{row+1}"]
    c.value = f"Score: {score} / 10"
    c.font = Font(name="Arial", size=11, bold=True, color=health_color)
    c.fill = fill(health_bg); c.alignment = center()
    c.border = thin_border()

    row += 4

    # ── Executive Summary text ─────────────────────────────────────────────────
    set_row_height(ws1, row, 6); row += 1
    set_row_height(ws1, row, 16)
    merge_write(ws1, f"B{row}:F{row}", "EXECUTIVE SUMMARY",
                hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
    row += 1

    summary_lines = data.get("health_summary", "").split(". ")
    for line in summary_lines:
        if not line.strip():
            continue
        set_row_height(ws1, row, 30)
        ws1.merge_cells(f"B{row}:F{row}")
        c = ws1[f"B{row}"]
        c.value = line.strip().rstrip(".") + "."
        c.font = body_font(10); c.alignment = left_align()
        c.fill = fill(LIGHT_GREY); c.border = thin_border("bottom")
        row += 1

    # ── Investor View ──────────────────────────────────────────────────────────
    set_row_height(ws1, row, 6); row += 1
    set_row_height(ws1, row, 16)
    merge_write(ws1, f"B{row}:F{row}", "INVESTOR VIEW",
                hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
    row += 1

    iv_text = data.get("investor_view", "")
    set_row_height(ws1, row, max(60, len(iv_text) // 4))
    ws1.merge_cells(f"B{row}:F{row}")
    c = ws1[f"B{row}"]
    c.value = iv_text
    c.font = body_font(10, bold=True, color="1A1A1A")
    c.alignment = left_align(); c.fill = fill(LIGHT_BLUE)
    c.border = thin_border()
    row += 2

    # =========================================================================
    # SHEET 2 — KPI METRICS
    # =========================================================================
    ws2 = wb.create_sheet("KPI Metrics")
    ws2.sheet_view.showGridLines = False

    kpi_cols = [2, 30, 20, 35, 2]
    for i, w in enumerate(kpi_cols, 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    row = 1
    # Title
    for r in range(row, row + 3):
        set_row_height(ws2, r, 6 if r != row + 1 else 36)
        for c in range(1, 6):
            ws2.cell(r, c).fill = fill(DARK_NAVY)
    merge_write(ws2, f"B{row+1}:D{row+1}", "KEY FINANCIAL METRICS",
                hdr_font(14, True, WHITE), center(), fill(DARK_NAVY))
    row += 3

    # Column headers
    set_row_height(ws2, row, 20)
    headers = ["Metric", "Value", "Commentary"]
    for ci, h in enumerate(headers, 2):
        c = ws2.cell(row, ci)
        c.value = h
        c.font = hdr_font(10, True, WHITE)
        c.fill = fill(ACCENT_BLUE)
        c.alignment = center()
        c.border = thin_border()
    row += 1

    kpi_display = [
        ("revenue",            "Revenue"),
        ("net_profit",         "Net Profit"),
        ("gross_margin",       "Gross Margin"),
        ("net_margin",         "Net Margin"),
        ("ebitda",             "EBITDA"),
        ("operating_cashflow", "Operating Cash Flow"),
        ("current_ratio",      "Current Ratio"),
        ("debt_to_equity",     "Debt / Equity Ratio"),
        ("working_capital",    "Working Capital"),
        ("total_debt",         "Total Debt"),
    ]

    kpis = data.get("kpis", {})
    for idx, (key, label) in enumerate(kpi_display):
        item = kpis.get(key, {})
        row_fill = fill(WHITE) if idx % 2 == 0 else fill(LIGHT_GREY)
        set_row_height(ws2, row, 22)

        # Metric label
        c = ws2.cell(row, 2)
        c.value = label; c.font = body_font(10, bold=True)
        c.fill = row_fill; c.alignment = left_align(False); c.border = thin_border()

        # Value
        c = ws2.cell(row, 3)
        c.value = item.get("value", "Not provided")
        c.font = Font(name="Arial", size=11, bold=True, color=ACCENT_BLUE)
        c.fill = row_fill; c.alignment = center(); c.border = thin_border()

        # Note
        c = ws2.cell(row, 4)
        c.value = item.get("note", "")
        c.font = body_font(9, color="444444")
        c.fill = row_fill; c.alignment = left_align(); c.border = thin_border()

        row += 1

    # =========================================================================
    # SHEET 3 — PERFORMANCE ANALYSIS
    # =========================================================================
    ws3 = wb.create_sheet("Performance Analysis")
    ws3.sheet_view.showGridLines = False

    pa_cols = [2, 26, 55, 2]
    for i, w in enumerate(pa_cols, 1):
        ws3.column_dimensions[get_column_letter(i)].width = w

    row = 1
    for r in range(row, row + 3):
        set_row_height(ws3, r, 6 if r != row + 1 else 36)
        for c in range(1, 5):
            ws3.cell(r, c).fill = fill(DARK_NAVY)
    merge_write(ws3, f"B{row+1}:C{row+1}", "PERFORMANCE ANALYSIS",
                hdr_font(14, True, WHITE), center(), fill(DARK_NAVY))
    row += 3

    sections = [
        ("profitability",           "Profitability"),
        ("cash_health",             "Cash Health"),
        ("working_capital_analysis","Working Capital"),
        ("balance_sheet",           "Balance Sheet"),
    ]

    for sec_key, sec_label in sections:
        sec = data.get(sec_key, {})
        headline = sec.get("headline", "")
        points   = sec.get("points", [])

        # Section header
        set_row_height(ws3, row, 18)
        merge_write(ws3, f"B{row}:C{row}", sec_label.upper(),
                    hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
        row += 1

        # Headline
        set_row_height(ws3, row, 28)
        ws3.merge_cells(f"B{row}:C{row}")
        c = ws3[f"B{row}"]
        c.value = headline; c.font = body_font(10, bold=True, color="1A1A1A")
        c.fill = fill(LIGHT_BLUE); c.alignment = left_align(); c.border = thin_border()
        row += 1

        # Bullet points
        for i, pt in enumerate(points):
            set_row_height(ws3, row, 26)
            # Bullet col
            bc = ws3.cell(row, 2)
            bc.value = "  ·"; bc.font = body_font(12, bold=True, color=ACCENT_BLUE)
            bc.fill = fill(WHITE if i % 2 == 0 else LIGHT_GREY)
            bc.alignment = center(); bc.border = thin_border("left")

            tc = ws3.cell(row, 3)
            tc.value = pt; tc.font = body_font(10)
            tc.fill = fill(WHITE if i % 2 == 0 else LIGHT_GREY)
            tc.alignment = left_align(); tc.border = thin_border("right,bottom,top")
            row += 1

        set_row_height(ws3, row, 8); row += 1

    # =========================================================================
    # SHEET 4 — RISKS & RECOMMENDATIONS
    # =========================================================================
    ws4 = wb.create_sheet("Risks & Recommendations")
    ws4.sheet_view.showGridLines = False

    rr_cols = [2, 22, 40, 40, 2]
    for i, w in enumerate(rr_cols, 1):
        ws4.column_dimensions[get_column_letter(i)].width = w

    row = 1
    for r in range(row, row + 3):
        set_row_height(ws4, r, 6 if r != row + 1 else 36)
        for c in range(1, 6):
            ws4.cell(r, c).fill = fill(DARK_NAVY)
    merge_write(ws4, f"B{row+1}:D{row+1}", "RISKS & RECOMMENDATIONS",
                hdr_font(14, True, WHITE), center(), fill(DARK_NAVY))
    row += 3

    # ── Risks ──────────────────────────────────────────────────────────────────
    set_row_height(ws4, row, 18)
    merge_write(ws4, f"B{row}:D{row}", "KEY RISKS & CONCERNS",
                hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
    row += 1

    set_row_height(ws4, row, 18)
    for ci, hdr in enumerate(["Risk", "Detail", "Suggested Action"], 2):
        c = ws4.cell(row, ci)
        c.value = hdr; c.font = hdr_font(9, True, "1A1A1A")
        c.fill = fill(RED_BG); c.alignment = center(); c.border = thin_border()
    row += 1

    for i, risk in enumerate(data.get("risks", [])):
        set_row_height(ws4, row, 40)
        row_fill = fill(WHITE) if i % 2 == 0 else fill(LIGHT_GREY)

        c = ws4.cell(row, 2)
        c.value = risk.get("title", "")
        c.font = body_font(10, bold=True, color=RED_FG)
        c.fill = row_fill; c.alignment = left_align(); c.border = thin_border()

        c = ws4.cell(row, 3)
        c.value = risk.get("detail", "")
        c.font = body_font(10); c.fill = row_fill
        c.alignment = left_align(); c.border = thin_border()

        c = ws4.cell(row, 4)
        c.value = risk.get("fix", "")
        c.font = body_font(10, color=GREEN_FG); c.fill = row_fill
        c.alignment = left_align(); c.border = thin_border()
        row += 1

    set_row_height(ws4, row, 10); row += 1

    # ── Positives ──────────────────────────────────────────────────────────────
    set_row_height(ws4, row, 18)
    merge_write(ws4, f"B{row}:D{row}", "POSITIVE SIGNALS",
                hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
    row += 1

    set_row_height(ws4, row, 18)
    for ci, hdr in enumerate(["Signal", "Detail", ""], 2):
        c = ws4.cell(row, ci)
        c.value = hdr; c.font = hdr_font(9, True, "1A1A1A")
        c.fill = fill(GREEN_BG); c.alignment = center(); c.border = thin_border()
    row += 1

    for i, pos in enumerate(data.get("positives", [])):
        set_row_height(ws4, row, 34)
        row_fill = fill(WHITE) if i % 2 == 0 else fill(LIGHT_GREY)

        c = ws4.cell(row, 2)
        c.value = pos.get("title", "")
        c.font = body_font(10, bold=True, color=GREEN_FG)
        c.fill = row_fill; c.alignment = left_align(); c.border = thin_border()

        ws4.merge_cells(f"C{row}:D{row}")
        c = ws4[f"C{row}"]
        c.value = pos.get("detail", "")
        c.font = body_font(10); c.fill = row_fill
        c.alignment = left_align(); c.border = thin_border()
        row += 1

    set_row_height(ws4, row, 10); row += 1

    # ── Recommendations ────────────────────────────────────────────────────────
    set_row_height(ws4, row, 18)
    merge_write(ws4, f"B{row}:D{row}", "RECOMMENDATIONS",
                hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
    row += 1

    set_row_height(ws4, row, 18)
    for ci, hdr in enumerate(["Action", "Rationale", ""], 2):
        c = ws4.cell(row, ci)
        c.value = hdr; c.font = hdr_font(9, True, "1A1A1A")
        c.fill = fill(LIGHT_BLUE); c.alignment = center(); c.border = thin_border()
    row += 1

    for i, rec in enumerate(data.get("recommendations", [])):
        set_row_height(ws4, row, 36)
        row_fill = fill(WHITE) if i % 2 == 0 else fill(LIGHT_GREY)

        c = ws4.cell(row, 2)
        c.value = rec.get("action", "")
        c.font = body_font(10, bold=True, color=ACCENT_BLUE)
        c.fill = row_fill; c.alignment = left_align(); c.border = thin_border()

        ws4.merge_cells(f"C{row}:D{row}")
        c = ws4[f"C{row}"]
        c.value = rec.get("rationale", "")
        c.font = body_font(10); c.fill = row_fill
        c.alignment = left_align(); c.border = thin_border()
        row += 1

    # =========================================================================
    # SHEET 5 — SCORECARD
    # =========================================================================
    ws5 = wb.create_sheet("Health Scorecard")
    ws5.sheet_view.showGridLines = False

    sc_cols = [2, 30, 20, 2]
    for i, w in enumerate(sc_cols, 1):
        ws5.column_dimensions[get_column_letter(i)].width = w

    row = 1
    for r in range(row, row + 3):
        set_row_height(ws5, r, 6 if r != row + 1 else 40)
        for c in range(1, 5):
            ws5.cell(r, c).fill = fill(DARK_NAVY)
    merge_write(ws5, f"B{row+1}:C{row+1}", "HEALTH SCORECARD",
                hdr_font(16, True, WHITE), center(), fill(DARK_NAVY))
    row += 3

    # Health score block
    set_row_height(ws5, row, 50)
    ws5.merge_cells(f"B{row}:B{row}")
    c = ws5[f"B{row}"]
    c.value = f"Overall Health: {label_map}"
    c.font = Font(name="Arial", size=16, bold=True, color=health_color)
    c.fill = fill(health_bg); c.alignment = center(); c.border = thin_border()

    ws5.merge_cells(f"C{row}:C{row}")
    c = ws5[f"C{row}"]
    c.value = f"{score} / 10"
    c.font = Font(name="Arial", size=20, bold=True, color=health_color)
    c.fill = fill(health_bg); c.alignment = center(); c.border = thin_border()
    row += 1

    # Score bar visual (each block = 1 point)
    set_row_height(ws5, row, 24)
    for ci in range(2, 4):
        ws5.cell(row, ci).fill = fill(MID_GREY)

    ws5.merge_cells(f"B{row}:C{row}")
    bar_filled = "█" * score
    bar_empty  = "░" * (10 - score)
    c = ws5[f"B{row}"]
    c.value = bar_filled + bar_empty
    c.font = Font(name="Courier New", size=16, bold=True, color=health_color)
    c.alignment = center()
    row += 2

    # Section scores table header
    set_row_height(ws5, row, 18)
    for ci, hdr in enumerate(["Analysis Area", "Assessment"], 2):
        c = ws5.cell(row, ci)
        c.value = hdr; c.font = hdr_font(10, True, WHITE)
        c.fill = fill(ACCENT_BLUE); c.alignment = center(); c.border = thin_border()
    row += 1

    area_map = [
        ("profitability",           "Profitability"),
        ("cash_health",             "Cash Health"),
        ("working_capital_analysis","Working Capital"),
        ("balance_sheet",           "Balance Sheet"),
    ]

    for idx, (sec_key, sec_label) in enumerate(area_map):
        sec = data.get(sec_key, {})
        headline = sec.get("headline", "")
        set_row_height(ws5, row, 32)
        row_fill = fill(WHITE) if idx % 2 == 0 else fill(LIGHT_GREY)

        c = ws5.cell(row, 2)
        c.value = sec_label; c.font = body_font(10, bold=True)
        c.fill = row_fill; c.alignment = left_align(False); c.border = thin_border()

        c = ws5.cell(row, 3)
        c.value = headline; c.font = body_font(10)
        c.fill = row_fill; c.alignment = left_align(); c.border = thin_border()
        row += 1

    # Footer note
    row += 1
    set_row_height(ws5, row, 18)
    ws5.merge_cells(f"B{row}:C{row}")
    c = ws5[f"B{row}"]
    c.value = "Note: This analysis is generated by AI for informational purposes only. Not financial advice."
    c.font = Font(name="Arial", size=8, italic=True, color="888888")
    c.alignment = center()

    # ── Save to bytes ─────────────────────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# UI RENDER HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def health_palette(label: str):
    if label == "Strong":
        return "#0d2818", "#3fb950", "#238636"
    if label == "Moderate":
        return "#2d1f00", "#d4a017", "#9e6a03"
    return "#2d0f0f", "#f85149", "#b91c1c"


def render_health_banner(data: dict):
    label   = data.get("health_label", "Moderate")
    score   = data.get("health_score", 5)
    summary = data.get("health_summary", "")
    company = data.get("company_name", "Company")
    period  = data.get("period", "")
    bg, fg, border = health_palette(label)
    score_bar = "█" * score + "░" * (10 - score)

    st.markdown(f"""
    <div style="background:{bg}; border:1px solid {border}; border-radius:12px;
                padding:1.8rem 2rem; margin-bottom:1.5rem;">
        <div style="display:flex; justify-content:space-between;
                    align-items:flex-start; flex-wrap:wrap; gap:1rem;">
            <div>
                <div style="color:#8b949e; font-size:0.72rem; font-weight:700;
                            letter-spacing:1.5px; margin-bottom:0.4rem;">
                    OVERALL FINANCIAL HEALTH
                </div>
                <div style="font-size:1.9rem; font-weight:700; color:{fg}; line-height:1.1;">
                    {label}
                </div>
                <div style="color:#8b949e; font-size:0.83rem; margin-top:0.3rem;">
                    {company}&nbsp;&nbsp;·&nbsp;&nbsp;{period}
                </div>
            </div>
            <div style="text-align:right;">
                <div style="color:#8b949e; font-size:0.72rem; font-weight:700;
                            letter-spacing:1.5px;">HEALTH SCORE</div>
                <div style="font-size:2.4rem; font-weight:800; color:{fg}; line-height:1.1;">
                    {score}<span style="font-size:1rem; color:#8b949e; font-weight:400;">&thinsp;/ 10</span>
                </div>
                <div style="font-family:monospace; color:{fg}; font-size:0.95rem;
                            letter-spacing:2px; margin-top:0.2rem;">{score_bar}</div>
            </div>
        </div>
        <div style="margin-top:1.1rem; padding-top:1.1rem; border-top:1px solid {border};
                    color:#c9d1d9; font-size:0.93rem; line-height:1.65;">
            {summary}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_kpis(kpis: dict):
    st.markdown(
        "<div style='color:#8b949e; font-size:0.72rem; font-weight:700; "
        "letter-spacing:1.5px; margin-bottom:0.6rem;'>KEY FINANCIAL METRICS</div>",
        unsafe_allow_html=True,
    )
    kpi_order = [
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
    for row_start in range(0, len(kpi_order), 5):
        chunk = kpi_order[row_start:row_start + 5]
        cols  = st.columns(len(chunk))
        for col, (key, label) in zip(cols, chunk):
            item  = kpis.get(key, {})
            value = item.get("value", "N/A")
            note  = item.get("note", "")
            delta_color = "inverse" if any(w in note.lower() for w in ["pressure", "decline", "high", "weak", "low"]) else "normal"
            with col:
                st.metric(label=label, value=value,
                          delta=note if note else None,
                          delta_color=delta_color)
        st.markdown("<div style='margin-bottom:0.4rem'></div>", unsafe_allow_html=True)


def render_analysis_card(title: str, section: dict):
    headline = section.get("headline", "")
    points   = section.get("points", [])
    st.markdown(f"""
    <div style="background:#161b22; border:1px solid #30363d; border-radius:10px;
                padding:1.2rem 1.5rem; margin-bottom:0.9rem; height:100%;">
        <div style="color:#f0f6fc; font-size:0.9rem; font-weight:700;
                    letter-spacing:0.3px; margin-bottom:0.5rem;">{title.upper()}</div>
        <div style="color:#8b949e; font-size:0.83rem; line-height:1.5;
                    border-left:3px solid #2e5eaa; padding-left:0.7rem;
                    margin-bottom:0.7rem; font-style:italic;">{headline}</div>
    </div>
    """, unsafe_allow_html=True)
    for pt in points:
        st.markdown(
            f"<div style='color:#c9d1d9; font-size:0.85rem; padding:0.2rem 0 0.2rem 1rem; "
            f"border-left:2px solid #30363d; margin-bottom:0.3rem;'>{pt}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("")


def render_investor_view(text: str):
    st.markdown(
        "<div style='color:#8b949e; font-size:0.72rem; font-weight:700; "
        "letter-spacing:1.5px; margin-bottom:0.6rem;'>INVESTOR VIEW — WHAT IS REALLY GOING ON</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                border:1px solid #4a4a8a; border-radius:10px;
                padding:1.4rem 1.8rem; color:#d0d0f0;
                font-size:0.95rem; line-height:1.7;">
        {text}
    </div>
    """, unsafe_allow_html=True)


def render_risks(risks: list):
    st.markdown(
        "<div style='color:#8b949e; font-size:0.72rem; font-weight:700; "
        "letter-spacing:1.5px; margin-bottom:0.6rem;'>KEY RISKS & CONCERNS</div>",
        unsafe_allow_html=True,
    )
    for risk in risks:
        with st.expander(risk.get("title", "Risk")):
            st.markdown(f"**Issue:** {risk.get('detail', '')}")
            st.markdown(f"**Suggested Action:** {risk.get('fix', '')}")


def render_positives(positives: list):
    st.markdown(
        "<div style='color:#8b949e; font-size:0.72rem; font-weight:700; "
        "letter-spacing:1.5px; margin-bottom:0.6rem;'>POSITIVE SIGNALS</div>",
        unsafe_allow_html=True,
    )
    for pos in positives:
        st.markdown(f"""
        <div style="background:#0d2818; border:1px solid #238636; border-radius:8px;
                    padding:0.9rem 1.1rem; margin-bottom:0.6rem;">
            <div style="color:#3fb950; font-weight:600; font-size:0.88rem;
                        margin-bottom:0.3rem;">{pos.get('title', '')}</div>
            <div style="color:#8b949e; font-size:0.83rem;">{pos.get('detail', '')}</div>
        </div>
        """, unsafe_allow_html=True)


def render_recommendations(recs: list):
    st.markdown(
        "<div style='color:#8b949e; font-size:0.72rem; font-weight:700; "
        "letter-spacing:1.5px; margin-bottom:0.6rem;'>RECOMMENDATIONS</div>",
        unsafe_allow_html=True,
    )
    for i, rec in enumerate(recs, 1):
        st.markdown(f"""
        <div style="background:#161b22; border-left:4px solid #2e5eaa;
                    border-radius:0 8px 8px 0; padding:0.9rem 1.2rem;
                    margin-bottom:0.7rem;">
            <div style="color:#58a6ff; font-weight:600; font-size:0.9rem;">
                {i}.&nbsp; {rec.get('action', '')}
            </div>
            <div style="color:#8b949e; font-size:0.83rem; margin-top:0.3rem;">
                {rec.get('rationale', '')}
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Financial Statement Analyzer",
        page_icon="",
        layout="wide",
    )

    st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }

    [data-testid="metric-container"] {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 0.9rem 1rem;
    }
    [data-testid="metric-container"] label {
        color: #8b949e !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #f0f6fc !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricDelta"] {
        font-size: 0.75rem !important;
    }

    div[data-testid="stButton"] > button {
        background: #2e5eaa;
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 0.7rem 2rem;
        font-size: 0.95rem;
        font-weight: 600;
        width: 100%;
        letter-spacing: 0.3px;
        transition: background 0.2s;
    }
    div[data-testid="stButton"] > button:hover { background: #1a4a8a; }

    hr { border-color: #21262d !important; }

    [data-testid="stExpander"] {
        background: #161b22;
        border: 1px solid #30363d !important;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }

    [data-testid="stDownloadButton"] > button {
        background: #161b22 !important;
        color: #f0f6fc !important;
        border: 1px solid #30363d !important;
        border-radius: 8px;
        font-size: 0.88rem;
        font-weight: 500;
        width: 100%;
    }
    [data-testid="stDownloadButton"] > button:hover {
        border-color: #58a6ff !important;
        color: #58a6ff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center; padding:2rem 1rem 1.5rem;">
        <div style="display:inline-block; background:rgba(46,94,170,0.15);
                    color:#58a6ff; border:1px solid rgba(46,94,170,0.4);
                    border-radius:20px; padding:0.25rem 1rem; font-size:0.72rem;
                    font-weight:700; letter-spacing:1.5px; margin-bottom:0.9rem;">
            POWERED BY GROQ · FREE TO USE
        </div>
        <h1 style="font-size:2.3rem; font-weight:800; color:#f0f6fc;
                   margin:0 0 0.5rem; letter-spacing:-0.5px;">
            Financial Statement Analyzer
        </h1>
        <p style="color:#8b949e; font-size:0.97rem; margin:0;">
            Institutional-grade forensic analysis — structured dashboard output
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── API Key ───────────────────────────────────────────────────────────────
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        with st.expander("Groq API Key  —  free at console.groq.com", expanded=True):
            api_key = st.text_input("Key", type="password", placeholder="gsk_...",
                                    label_visibility="collapsed")
            st.caption("Get your free key at [console.groq.com](https://console.groq.com) → API Keys → Create Key")
        if not api_key:
            st.info("Enter your Groq API key above to get started.", icon="i")

    st.divider()

    # ── Upload + Paste ────────────────────────────────────────────────────────
    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        st.markdown(
            "<div style='color:#f0f6fc; font-size:0.9rem; font-weight:600; "
            "margin-bottom:0.5rem;'>Upload Financial Statements</div>",
            unsafe_allow_html=True,
        )
        st.caption("PDF, CSV, or TXT — one or more files")
        uploaded_files = st.file_uploader(
            "files", type=["pdf", "csv", "txt"],
            accept_multiple_files=True, label_visibility="collapsed",
        )
        if uploaded_files:
            for f in uploaded_files:
                kb = len(f.getvalue()) / 1024
                st.markdown(
                    f"<small style='color:#8b949e'>{f.name} — {kb:.1f} KB</small>",
                    unsafe_allow_html=True,
                )

    with col_r:
        st.markdown(
            "<div style='color:#f0f6fc; font-size:0.9rem; font-weight:600; "
            "margin-bottom:0.5rem;'>Or Paste Financial Data</div>",
            unsafe_allow_html=True,
        )
        st.caption("Paste raw text, numbers, or CSV rows directly")
        pasted_text = st.text_area("paste", height=155,
            placeholder="Revenue: $10.5M\nNet Profit: $1.8M\n...",
            label_visibility="collapsed")

    st.divider()

    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        go = st.button("Analyse Financial Statements", use_container_width=True)

    # ── Run analysis ──────────────────────────────────────────────────────────
    if go:
        if not api_key:
            st.error("Please enter your Groq API key.")
            st.stop()

        parts = []
        if uploaded_files:
            for uf in uploaded_files:
                uf.seek(0)
                parts.append(f"=== {uf.name} ===\n{extract_text(uf)}")
        if pasted_text.strip():
            parts.append(f"=== Pasted Data ===\n{pasted_text.strip()}")
        if not parts:
            st.warning("Please upload a file or paste financial data.")
            st.stop()

        combined = "\n\n".join(parts)

        with st.spinner("Analysing with Groq AI (LLaMA 3.3 70B)..."):
            try:
                data, raw = analyse_financials(combined, api_key)
            except Exception as e:
                err = str(e).lower()
                if "401" in err or "invalid api key" in err or "authentication" in err:
                    st.error("Invalid Groq API key — please check it and try again.")
                elif "429" in err or "rate limit" in err:
                    st.error("Rate limit reached — please wait a moment and retry.")
                else:
                    st.error(f"API error: {e}")
                st.stop()

        if not data:
            st.warning("Could not parse structured output. Raw response shown below.")
            st.text(raw)
            st.stop()

        st.success("Analysis complete.", icon="v")
        st.divider()

        # ── 1. Health Banner ──────────────────────────────────────────────────
        render_health_banner(data)

        # ── 2. KPI Cards ──────────────────────────────────────────────────────
        render_kpis(data.get("kpis", {}))

        st.divider()

        # ── 3. Performance Summary ────────────────────────────────────────────
        st.markdown(
            "<div style='color:#8b949e; font-size:0.72rem; font-weight:700; "
            "letter-spacing:1.5px; margin-bottom:0.8rem;'>PERFORMANCE SUMMARY</div>",
            unsafe_allow_html=True,
        )
        left, right = st.columns(2, gap="large")
        with left:
            render_analysis_card("Profitability",  data.get("profitability", {}))
            render_analysis_card("Cash Health",    data.get("cash_health", {}))
        with right:
            render_analysis_card("Working Capital", data.get("working_capital_analysis", {}))
            render_analysis_card("Balance Sheet",   data.get("balance_sheet", {}))

        st.divider()

        # ── 4. Investor View ──────────────────────────────────────────────────
        render_investor_view(data.get("investor_view", ""))

        st.divider()

        # ── 5. Risks & Positives ──────────────────────────────────────────────
        risk_col, pos_col = st.columns([1, 1], gap="large")
        with risk_col:
            render_risks(data.get("risks", []))
        with pos_col:
            render_positives(data.get("positives", []))

        st.divider()

        # ── 6. Recommendations ────────────────────────────────────────────────
        render_recommendations(data.get("recommendations", []))

        st.divider()

        # ── 7. Downloads ──────────────────────────────────────────────────────
        st.markdown(
            "<div style='color:#8b949e; font-size:0.72rem; font-weight:700; "
            "letter-spacing:1.5px; margin-bottom:0.8rem;'>DOWNLOAD REPORT</div>",
            unsafe_allow_html=True,
        )

        dl_col1, dl_col2, dl_col3 = st.columns([1, 1, 1])

        # TXT report
        report_lines = [
            "FINANCIAL ANALYSIS REPORT",
            "=" * 60,
            f"Company : {data.get('company_name', 'N/A')}",
            f"Period  : {data.get('period', 'N/A')}",
            f"Health  : {data.get('health_label', 'N/A')}   Score: {data.get('health_score', 'N/A')} / 10",
            "",
            "EXECUTIVE SUMMARY",
            "-" * 40,
            data.get("health_summary", ""),
            "",
            "INVESTOR VIEW",
            "-" * 40,
            data.get("investor_view", ""),
            "",
            "KEY METRICS",
            "-" * 40,
        ]
        kpis = data.get("kpis", {})
        kpi_labels = {
            "revenue": "Revenue", "net_profit": "Net Profit",
            "gross_margin": "Gross Margin", "net_margin": "Net Margin",
            "ebitda": "EBITDA", "operating_cashflow": "Operating Cash Flow",
            "current_ratio": "Current Ratio", "debt_to_equity": "Debt/Equity",
            "working_capital": "Working Capital", "total_debt": "Total Debt",
        }
        for k, lbl in kpi_labels.items():
            v = kpis.get(k, {}).get("value", "N/A")
            n = kpis.get(k, {}).get("note", "")
            report_lines.append(f"  {lbl:<22} {v:<14} {n}")
        report_lines += ["", "KEY RISKS", "-" * 40]
        for r in data.get("risks", []):
            report_lines += [
                f"  Risk: {r.get('title', '')}",
                f"        {r.get('detail', '')}",
                f"  Fix:  {r.get('fix', '')}",
                "",
            ]
        report_lines += ["RECOMMENDATIONS", "-" * 40]
        for i, rec in enumerate(data.get("recommendations", []), 1):
            report_lines += [
                f"  {i}. {rec.get('action', '')}",
                f"     {rec.get('rationale', '')}",
                "",
            ]

        with dl_col1:
            st.download_button(
                label="Download Report (.txt)",
                data="\n".join(report_lines),
                file_name="financial_analysis.txt",
                mime="text/plain",
                use_container_width=True,
            )

        # Excel report
        with dl_col2:
            excel_bytes = build_excel_report(data)
            company_slug = re.sub(r"[^a-z0-9]", "_", data.get("company_name", "report").lower())
            st.download_button(
                label="Download Report (.xlsx)",
                data=excel_bytes,
                file_name=f"{company_slug}_financial_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        # JSON (debug)
        with dl_col3:
            st.download_button(
                label="Download Raw Data (.json)",
                data=json.dumps(data, indent=2),
                file_name="financial_analysis.json",
                mime="application/json",
                use_container_width=True,
            )

        # Raw JSON expander
        with st.expander("Raw JSON output (debug)"):
            st.json(data)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<p style='text-align:center; color:#484f58; font-size:0.76rem;'>"
        "Financial Statement Analyzer &nbsp;·&nbsp; Powered by Groq (LLaMA 3.3 70B) &nbsp;·&nbsp;"
        " For analytical purposes only — not financial advice."
        "</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
