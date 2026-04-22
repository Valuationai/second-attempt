"""Main page — Financial Statement Analyser."""
import streamlit as st
from groq import Groq
import io, os, csv, json, re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Import shared helpers
import sys
sys.path.insert(0, os.path.dirname(__file__))
from utils import inject_styles, nav_bar, section_label

st.set_page_config(
    page_title="FinSight — Financial Statement Analyser",
    page_icon="",
    layout="wide",
)
inject_styles()
nav_bar("analyser")

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
    raw  = uploaded_file.read()
    if name.endswith(".pdf"):  return extract_text_from_pdf(raw)
    if name.endswith(".csv"):  return extract_text_from_csv(raw)
    return raw.decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a highly skilled financial analyst and forensic accountant based in New Zealand.
You will receive one or more financial statements (Income Statement, Balance Sheet, Cash Flow Statement) — they may be uploaded separately or combined.
Cross-reference all documents together to produce a single, unified, accurate analysis.
Return ONLY a valid JSON object — no markdown, no extra text.

The JSON must follow this exact schema:

{
  "company_name": "string or 'Unknown Company'",
  "period": "string e.g. 'FY 2023' or 'Not provided'",
  "documents_detected": ["list of statement types identified, e.g. 'Income Statement', 'Balance Sheet', 'Cash Flow Statement'"],
  "health_score": integer 1-10,
  "health_label": "Strong" | "Moderate" | "Weak",
  "health_summary": "2-3 sentence executive summary of financial health in NZ English",

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

  "investor_view": "3-4 sentence blunt investor-style interpretation in NZ English",

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
- If multiple documents are provided, synthesise them holistically — do not analyse each in isolation.
- Use NZ English spelling throughout (e.g. "analyse" not "analyze", "recognise" not "recognize", "favour" not "favor").
- Return ONLY the JSON object. No preamble, no explanation, no markdown fences.
"""


# ─────────────────────────────────────────────────────────────────────────────
# GROQ API CALL
# ─────────────────────────────────────────────────────────────────────────────

def analyse_financials(financial_text: str, api_key: str):
    client = Groq(api_key=api_key)

    # Allow a larger window so all 3 statements fit
    max_chars = 28000
    if len(financial_text) > max_chars:
        financial_text = financial_text[:max_chars] + "\n\n[Further content truncated due to length]"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=4096,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Analyse these financial statements:\n\n{financial_text}"},
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "",        raw).strip()

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

    label_map    = data.get("health_label", "Moderate")
    score        = data.get("health_score", 5)
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

    def centre():
        return Alignment(horizontal="center", vertical="center", wrap_text=True)

    def left_align(wrap=True):
        return Alignment(horizontal="left", vertical="center", wrap_text=wrap)

    def row_h(ws, row, h):
        ws.row_dimensions[row].height = h

    def mwrite(ws, rng, val, fnt, aln, fll=None, brd=None):
        ws.merge_cells(rng)
        c = ws[rng.split(":")[0]]
        c.value = val; c.font = fnt; c.alignment = aln
        if fll: c.fill = fll
        if brd: c.border = brd

    # ── Sheet 1: Executive Summary ────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Executive Summary"
    ws1.sheet_view.showGridLines = False
    for i, w in enumerate([2, 28, 22, 22, 22, 22, 2], 1):
        ws1.column_dimensions[get_column_letter(i)].width = w

    r = 1
    for ri in range(r, r+3):
        row_h(ws1, ri, 6 if ri != r+1 else 36)
        for ci in range(1, 8): ws1.cell(ri, ci).fill = fill(DARK_NAVY)
    mwrite(ws1, f"B{r+1}:F{r+1}", "FINANCIAL STATEMENT ANALYSIS — FINSIGHT",
           hdr_font(15, True, WHITE), centre(), fill(DARK_NAVY))
    r += 3

    for ri in range(r, r+4):
        row_h(ws1, ri, 6 if ri in (r, r+3) else 26)
        for ci in range(1, 8): ws1.cell(ri, ci).fill = fill(MID_NAVY)

    ws1.merge_cells(f"B{r+1}:C{r+1}")
    c = ws1[f"B{r+1}"]
    c.value = data.get("company_name", "Unknown Company")
    c.font = hdr_font(13, True, WHITE); c.alignment = left_align(False)

    ws1.cell(r+1, 4).value = data.get("period", "Not provided")
    ws1.cell(r+1, 4).font  = hdr_font(11, False, MID_GREY)
    ws1.cell(r+1, 4).alignment = centre()

    for ci, (val, col) in enumerate([(label_map, health_color), (f"Score: {score} / 10", health_color)], 5):
        c = ws1.cell(r+1, ci)
        c.value = val
        c.font  = Font(name="Arial", size=11, bold=True, color=col)
        c.fill  = fill(health_bg); c.alignment = centre(); c.border = thin_border()
    r += 4

    row_h(ws1, r, 6); r += 1
    row_h(ws1, r, 16)
    mwrite(ws1, f"B{r}:F{r}", "EXECUTIVE SUMMARY", hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
    r += 1

    for line in data.get("health_summary", "").split(". "):
        if not line.strip(): continue
        row_h(ws1, r, 30)
        ws1.merge_cells(f"B{r}:F{r}")
        c = ws1[f"B{r}"]
        c.value = line.strip().rstrip(".") + "."
        c.font = body_font(10); c.alignment = left_align()
        c.fill = fill(LIGHT_GREY); c.border = thin_border("bottom")
        r += 1

    row_h(ws1, r, 6); r += 1
    row_h(ws1, r, 16)
    mwrite(ws1, f"B{r}:F{r}", "INVESTOR VIEW", hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
    r += 1
    iv = data.get("investor_view", "")
    row_h(ws1, r, max(60, len(iv)//4))
    ws1.merge_cells(f"B{r}:F{r}")
    c = ws1[f"B{r}"]
    c.value = iv; c.font = body_font(10, bold=True, color="1A1A1A")
    c.alignment = left_align(); c.fill = fill(LIGHT_BLUE); c.border = thin_border()

    # ── Sheet 2: KPI Metrics ──────────────────────────────────────────────────
    ws2 = wb.create_sheet("KPI Metrics")
    ws2.sheet_view.showGridLines = False
    for i, w in enumerate([2, 30, 20, 35, 2], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    r = 1
    for ri in range(r, r+3):
        row_h(ws2, ri, 6 if ri != r+1 else 36)
        for ci in range(1, 6): ws2.cell(ri, ci).fill = fill(DARK_NAVY)
    mwrite(ws2, f"B{r+1}:D{r+1}", "KEY FINANCIAL METRICS", hdr_font(14, True, WHITE), centre(), fill(DARK_NAVY))
    r += 3

    row_h(ws2, r, 20)
    for ci, h in enumerate(["Metric", "Value", "Commentary"], 2):
        c = ws2.cell(r, ci); c.value = h
        c.font = hdr_font(10, True, WHITE); c.fill = fill(ACCENT_BLUE)
        c.alignment = centre(); c.border = thin_border()
    r += 1

    kpi_display = [
        ("revenue","Revenue"), ("net_profit","Net Profit"),
        ("gross_margin","Gross Margin"), ("net_margin","Net Margin"),
        ("ebitda","EBITDA"), ("operating_cashflow","Operating Cash Flow"),
        ("current_ratio","Current Ratio"), ("debt_to_equity","Debt / Equity Ratio"),
        ("working_capital","Working Capital"), ("total_debt","Total Debt"),
    ]
    kpis = data.get("kpis", {})
    for idx, (key, label) in enumerate(kpi_display):
        item = kpis.get(key, {})
        rf = fill(WHITE) if idx % 2 == 0 else fill(LIGHT_GREY)
        row_h(ws2, r, 22)
        c = ws2.cell(r, 2); c.value = label
        c.font = body_font(10, bold=True); c.fill = rf
        c.alignment = left_align(False); c.border = thin_border()
        c = ws2.cell(r, 3); c.value = item.get("value", "Not provided")
        c.font = Font(name="Arial", size=11, bold=True, color=ACCENT_BLUE)
        c.fill = rf; c.alignment = centre(); c.border = thin_border()
        c = ws2.cell(r, 4); c.value = item.get("note", "")
        c.font = body_font(9, color="444444")
        c.fill = rf; c.alignment = left_align(); c.border = thin_border()
        r += 1

    # ── Sheet 3: Performance Analysis ─────────────────────────────────────────
    ws3 = wb.create_sheet("Performance Analysis")
    ws3.sheet_view.showGridLines = False
    for i, w in enumerate([2, 26, 55, 2], 1):
        ws3.column_dimensions[get_column_letter(i)].width = w

    r = 1
    for ri in range(r, r+3):
        row_h(ws3, ri, 6 if ri != r+1 else 36)
        for ci in range(1, 5): ws3.cell(ri, ci).fill = fill(DARK_NAVY)
    mwrite(ws3, f"B{r+1}:C{r+1}", "PERFORMANCE ANALYSIS", hdr_font(14, True, WHITE), centre(), fill(DARK_NAVY))
    r += 3

    for sec_key, sec_label in [
        ("profitability","Profitability"), ("cash_health","Cash Health"),
        ("working_capital_analysis","Working Capital"), ("balance_sheet","Balance Sheet"),
    ]:
        sec = data.get(sec_key, {})
        row_h(ws3, r, 18)
        mwrite(ws3, f"B{r}:C{r}", sec_label.upper(), hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
        r += 1
        row_h(ws3, r, 28)
        ws3.merge_cells(f"B{r}:C{r}")
        c = ws3[f"B{r}"]; c.value = sec.get("headline","")
        c.font = body_font(10, bold=True, color="1A1A1A")
        c.fill = fill(LIGHT_BLUE); c.alignment = left_align(); c.border = thin_border()
        r += 1
        for i, pt in enumerate(sec.get("points", [])):
            row_h(ws3, r, 26)
            rf = fill(WHITE) if i % 2 == 0 else fill(LIGHT_GREY)
            bc = ws3.cell(r, 2); bc.value = "  ·"
            bc.font = body_font(12, bold=True, color=ACCENT_BLUE)
            bc.fill = rf; bc.alignment = centre(); bc.border = thin_border("left")
            tc = ws3.cell(r, 3); tc.value = pt
            tc.font = body_font(10); tc.fill = rf
            tc.alignment = left_align(); tc.border = thin_border("right,bottom,top")
            r += 1
        row_h(ws3, r, 8); r += 1

    # ── Sheet 4: Risks & Recommendations ─────────────────────────────────────
    ws4 = wb.create_sheet("Risks & Recommendations")
    ws4.sheet_view.showGridLines = False
    for i, w in enumerate([2, 22, 40, 40, 2], 1):
        ws4.column_dimensions[get_column_letter(i)].width = w

    r = 1
    for ri in range(r, r+3):
        row_h(ws4, ri, 6 if ri != r+1 else 36)
        for ci in range(1, 6): ws4.cell(ri, ci).fill = fill(DARK_NAVY)
    mwrite(ws4, f"B{r+1}:D{r+1}", "RISKS & RECOMMENDATIONS", hdr_font(14, True, WHITE), centre(), fill(DARK_NAVY))
    r += 3

    for section_data, title, hdrs, bg, fg_col in [
        (data.get("risks",[]),           "KEY RISKS & CONCERNS",  ["Risk","Detail","Suggested Action"], RED_BG,  RED_FG),
        (data.get("positives",[]),        "POSITIVE SIGNALS",      ["Signal","Detail",""],              GREEN_BG, GREEN_FG),
        (data.get("recommendations",[]), "RECOMMENDATIONS",        ["Action","Rationale",""],           LIGHT_BLUE, ACCENT_BLUE),
    ]:
        row_h(ws4, r, 18)
        mwrite(ws4, f"B{r}:D{r}", title, hdr_font(10, True, WHITE), left_align(False), fill(ACCENT_BLUE))
        r += 1
        row_h(ws4, r, 18)
        for ci, h in enumerate(hdrs, 2):
            c = ws4.cell(r, ci); c.value = h
            c.font = hdr_font(9, True, "1A1A1A"); c.fill = fill(bg)
            c.alignment = centre(); c.border = thin_border()
        r += 1
        for idx, item in enumerate(section_data):
            row_h(ws4, r, 40)
            rf = fill(WHITE) if idx % 2 == 0 else fill(LIGHT_GREY)
            keys = (["title","detail","fix"] if "fix" in item
                    else ["title","detail",""] if "detail" in item
                    else ["action","rationale",""])
            for ci, k in enumerate(keys, 2):
                val = item.get(k, "") if k else ""
                c = ws4.cell(r, ci); c.value = val
                c.font = body_font(10, bold=(ci==2), color=fg_col if ci==2 else "000000")
                c.fill = rf; c.alignment = left_align(); c.border = thin_border()
            r += 1
        row_h(ws4, r, 10); r += 1

    # ── Sheet 5: Health Scorecard ─────────────────────────────────────────────
    ws5 = wb.create_sheet("Health Scorecard")
    ws5.sheet_view.showGridLines = False
    for i, w in enumerate([2, 30, 20, 2], 1):
        ws5.column_dimensions[get_column_letter(i)].width = w

    r = 1
    for ri in range(r, r+3):
        row_h(ws5, ri, 6 if ri != r+1 else 40)
        for ci in range(1, 5): ws5.cell(ri, ci).fill = fill(DARK_NAVY)
    mwrite(ws5, f"B{r+1}:C{r+1}", "HEALTH SCORECARD", hdr_font(16, True, WHITE), centre(), fill(DARK_NAVY))
    r += 3

    row_h(ws5, r, 50)
    ws5.merge_cells(f"B{r}:B{r}")
    c = ws5[f"B{r}"]; c.value = f"Overall Health: {label_map}"
    c.font = Font(name="Arial", size=16, bold=True, color=health_color)
    c.fill = fill(health_bg); c.alignment = centre(); c.border = thin_border()
    ws5.merge_cells(f"C{r}:C{r}")
    c = ws5[f"C{r}"]; c.value = f"{score} / 10"
    c.font = Font(name="Arial", size=20, bold=True, color=health_color)
    c.fill = fill(health_bg); c.alignment = centre(); c.border = thin_border()
    r += 1

    row_h(ws5, r, 24)
    ws5.merge_cells(f"B{r}:C{r}")
    c = ws5[f"B{r}"]
    c.value = "█" * score + "░" * (10 - score)
    c.font = Font(name="Courier New", size=16, bold=True, color=health_color)
    c.alignment = centre(); c.fill = fill(MID_GREY)
    r += 2

    row_h(ws5, r, 18)
    for ci, h in enumerate(["Analysis Area", "Assessment"], 2):
        c = ws5.cell(r, ci); c.value = h
        c.font = hdr_font(10, True, WHITE); c.fill = fill(ACCENT_BLUE)
        c.alignment = centre(); c.border = thin_border()
    r += 1

    for idx, (sk, sl) in enumerate([
        ("profitability","Profitability"), ("cash_health","Cash Health"),
        ("working_capital_analysis","Working Capital"), ("balance_sheet","Balance Sheet"),
    ]):
        row_h(ws5, r, 32)
        rf = fill(WHITE) if idx % 2 == 0 else fill(LIGHT_GREY)
        c = ws5.cell(r, 2); c.value = sl
        c.font = body_font(10, bold=True); c.fill = rf
        c.alignment = left_align(False); c.border = thin_border()
        c = ws5.cell(r, 3); c.value = data.get(sk, {}).get("headline", "")
        c.font = body_font(10); c.fill = rf
        c.alignment = left_align(); c.border = thin_border()
        r += 1

    row_h(ws5, r+1, 18)
    ws5.merge_cells(f"B{r+1}:C{r+1}")
    c = ws5[f"B{r+1}"]
    c.value = "Note: This analysis is generated by AI for informational purposes only. Not financial advice."
    c.font = Font(name="Arial", size=8, italic=True, color="888888")
    c.alignment = centre()

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# UI RENDER HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def health_palette(label):
    if label == "Strong":   return "#0d2818", "#3fb950", "#238636"
    if label == "Moderate": return "#2d1f00", "#d4a017", "#9e6a03"
    return "#2d0f0f", "#f85149", "#b91c1c"


def render_health_banner(data):
    label   = data.get("health_label", "Moderate")
    score   = data.get("health_score", 5)
    summary = data.get("health_summary", "")
    company = data.get("company_name", "Company")
    period  = data.get("period", "")
    docs    = data.get("documents_detected", [])
    bg, fg, border = health_palette(label)
    bar = "█" * score + "░" * (10 - score)
    docs_html = ""
    if docs:
        tags = "".join(
            f"<span style='background:#21262d; color:#8b949e; border-radius:4px; "
            f"padding:0.1rem 0.5rem; font-size:0.72rem; margin-right:0.3rem;'>{d}</span>"
            for d in docs
        )
        docs_html = f"<div style='margin-top:0.5rem;'>{tags}</div>"

    st.markdown(f"""
    <div style="background:{bg}; border:1px solid {border}; border-radius:12px;
                padding:1.8rem 2rem; margin-bottom:1.5rem;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:1rem;">
            <div>
                <div style="color:#8b949e; font-size:0.7rem; font-weight:700; letter-spacing:1.5px; margin-bottom:0.4rem;">
                    OVERALL FINANCIAL HEALTH
                </div>
                <div style="font-size:1.9rem; font-weight:700; color:{fg}; line-height:1.1;">{label}</div>
                <div style="color:#8b949e; font-size:0.83rem; margin-top:0.3rem;">
                    {company}&nbsp;&nbsp;·&nbsp;&nbsp;{period}
                </div>
                {docs_html}
            </div>
            <div style="text-align:right;">
                <div style="color:#8b949e; font-size:0.7rem; font-weight:700; letter-spacing:1.5px;">HEALTH SCORE</div>
                <div style="font-size:2.4rem; font-weight:800; color:{fg}; line-height:1.1;">
                    {score}<span style="font-size:1rem; color:#8b949e; font-weight:400;">&thinsp;/ 10</span>
                </div>
                <div style="font-family:monospace; color:{fg}; font-size:0.95rem; letter-spacing:2px; margin-top:0.2rem;">{bar}</div>
            </div>
        </div>
        <div style="margin-top:1.1rem; padding-top:1.1rem; border-top:1px solid {border};
                    color:#c9d1d9; font-size:0.93rem; line-height:1.65;">
            {summary}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_kpis(kpis):
    section_label("KEY FINANCIAL METRICS")
    order = [
        ("revenue","Revenue"), ("net_profit","Net Profit"),
        ("gross_margin","Gross Margin"), ("net_margin","Net Margin"),
        ("ebitda","EBITDA"), ("operating_cashflow","Operating Cash Flow"),
        ("current_ratio","Current Ratio"), ("debt_to_equity","Debt / Equity"),
        ("working_capital","Working Capital"), ("total_debt","Total Debt"),
    ]
    for rs in range(0, len(order), 5):
        chunk = order[rs:rs+5]
        cols  = st.columns(len(chunk))
        for col, (key, label) in zip(cols, chunk):
            item  = kpis.get(key, {})
            value = item.get("value", "N/A")
            note  = item.get("note", "")
            dc = "inverse" if any(w in note.lower() for w in ["pressure","decline","high","weak","low"]) else "normal"
            with col:
                st.metric(label=label, value=value, delta=note if note else None, delta_color=dc)
        st.markdown("<div style='margin-bottom:0.4rem'></div>", unsafe_allow_html=True)


def render_analysis_card(title, section):
    headline = section.get("headline", "")
    points   = section.get("points", [])
    st.markdown(f"""
    <div style="background:#161b22; border:1px solid #30363d; border-radius:10px;
                padding:1.2rem 1.5rem; margin-bottom:0.5rem;">
        <div style="color:#f0f6fc; font-size:0.85rem; font-weight:700;
                    letter-spacing:0.5px; margin-bottom:0.5rem;">{title.upper()}</div>
        <div style="color:#8b949e; font-size:0.82rem; line-height:1.5;
                    border-left:3px solid #2e5eaa; padding-left:0.7rem;
                    font-style:italic;">{headline}</div>
    </div>
    """, unsafe_allow_html=True)
    for pt in points:
        st.markdown(
            f"<div style='color:#c9d1d9; font-size:0.84rem; padding:0.25rem 0 0.25rem 1rem; "
            f"border-left:2px solid #30363d; margin-bottom:0.3rem;'>{pt}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("")


def render_investor_view(text):
    section_label("INVESTOR VIEW — WHAT IS REALLY GOING ON")
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e); border:1px solid #4a4a8a;
                border-radius:10px; padding:1.4rem 1.8rem; color:#d0d0f0;
                font-size:0.95rem; line-height:1.7;">{text}</div>
    """, unsafe_allow_html=True)


def render_risks(risks):
    section_label("KEY RISKS & CONCERNS")
    for risk in risks:
        with st.expander(risk.get("title", "Risk")):
            st.markdown(f"**Issue:** {risk.get('detail', '')}")
            st.markdown(f"**Suggested Action:** {risk.get('fix', '')}")


def render_positives(positives):
    section_label("POSITIVE SIGNALS")
    for pos in positives:
        st.markdown(f"""
        <div style="background:#0d2818; border:1px solid #238636; border-radius:8px;
                    padding:0.9rem 1.1rem; margin-bottom:0.6rem;">
            <div style="color:#3fb950; font-weight:600; font-size:0.87rem;
                        margin-bottom:0.3rem;">{pos.get('title','')}</div>
            <div style="color:#8b949e; font-size:0.82rem;">{pos.get('detail','')}</div>
        </div>
        """, unsafe_allow_html=True)


def render_recommendations(recs):
    section_label("RECOMMENDATIONS")
    for i, rec in enumerate(recs, 1):
        st.markdown(f"""
        <div style="background:#161b22; border-left:4px solid #2e5eaa;
                    border-radius:0 8px 8px 0; padding:0.9rem 1.2rem; margin-bottom:0.7rem;">
            <div style="color:#58a6ff; font-weight:600; font-size:0.9rem;">
                {i}.&nbsp; {rec.get('action','')}
            </div>
            <div style="color:#8b949e; font-size:0.83rem; margin-top:0.3rem;">
                {rec.get('rationale','')}
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────────────────────────────────────

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding:2.5rem 1rem 1.5rem;">
    <div style="display:inline-block; background:rgba(46,94,170,0.15); color:#58a6ff;
                border:1px solid rgba(46,94,170,0.4); border-radius:20px;
                padding:0.25rem 1rem; font-size:0.72rem; font-weight:700;
                letter-spacing:1.5px; margin-bottom:0.9rem;">
        POWERED BY GROQ — FREE TO USE
    </div>
    <h1 style="font-size:2.3rem; font-weight:800; color:#f0f6fc;
               margin:0 0 0.5rem; letter-spacing:-0.5px;">
        Financial Statement Analyser
    </h1>
    <p style="color:#8b949e; font-size:0.97rem; margin:0;">
        Upload up to three statements — Income, Balance Sheet, Cash Flow — and get a full forensic analysis in seconds.
    </p>
</div>
""", unsafe_allow_html=True)

# ── API Key ───────────────────────────────────────────────────────────────────
api_key = os.getenv("GROQ_API_KEY", "")
if not api_key:
    with st.expander("Groq API Key  —  free at console.groq.com", expanded=True):
        api_key = st.text_input("Key", type="password", placeholder="gsk_...",
                                label_visibility="collapsed")
        st.caption("Get your free key at [console.groq.com](https://console.groq.com) → API Keys → Create Key")
    if not api_key:
        st.info("Enter your Groq API key above to get started.")

st.divider()

# ── Upload ────────────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2, gap="large")

with col_l:
    st.markdown(
        "<div style='color:#f0f6fc; font-size:0.9rem; font-weight:600; margin-bottom:0.4rem;'>"
        "Upload Financial Statements</div>",
        unsafe_allow_html=True,
    )
    st.caption("PDF, CSV or TXT — upload all three statements at once for the best results")
    uploaded_files = st.file_uploader(
        "files", type=["pdf","csv","txt"],
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
        "<div style='color:#f0f6fc; font-size:0.9rem; font-weight:600; margin-bottom:0.4rem;'>"
        "Or Paste Financial Data</div>",
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

# ── Run ───────────────────────────────────────────────────────────────────────
if go:
    if not api_key:
        st.error("Please enter your Groq API key.")
        st.stop()

    parts = []
    if uploaded_files:
        for uf in uploaded_files:
            uf.seek(0)
            extracted = extract_text(uf)
            parts.append(f"=== DOCUMENT: {uf.name} ===\n{extracted}")
    if pasted_text.strip():
        parts.append(f"=== PASTED DATA ===\n{pasted_text.strip()}")
    if not parts:
        st.warning("Please upload at least one file or paste financial data.")
        st.stop()

    combined = "\n\n".join(parts)

    with st.spinner(f"Analysing {len(parts)} document(s) with Groq AI..."):
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

    st.success("Analysis complete.")
    st.divider()

    render_health_banner(data)
    render_kpis(data.get("kpis", {}))
    st.divider()

    section_label("PERFORMANCE SUMMARY")
    left, right = st.columns(2, gap="large")
    with left:
        render_analysis_card("Profitability",  data.get("profitability", {}))
        render_analysis_card("Cash Health",    data.get("cash_health", {}))
    with right:
        render_analysis_card("Working Capital", data.get("working_capital_analysis", {}))
        render_analysis_card("Balance Sheet",   data.get("balance_sheet", {}))

    st.divider()
    render_investor_view(data.get("investor_view", ""))
    st.divider()

    rc, pc = st.columns(2, gap="large")
    with rc: render_risks(data.get("risks", []))
    with pc: render_positives(data.get("positives", []))

    st.divider()
    render_recommendations(data.get("recommendations", []))
    st.divider()

    # ── Downloads ─────────────────────────────────────────────────────────────
    section_label("DOWNLOAD REPORT")

    report_lines = [
        "FINANCIAL ANALYSIS REPORT — FINSIGHT", "=" * 60,
        f"Company : {data.get('company_name','N/A')}",
        f"Period  : {data.get('period','N/A')}",
        f"Health  : {data.get('health_label','N/A')}   Score: {data.get('health_score','N/A')} / 10",
        "", "EXECUTIVE SUMMARY", "-" * 40, data.get("health_summary",""),
        "", "INVESTOR VIEW", "-" * 40, data.get("investor_view",""),
        "", "KEY METRICS", "-" * 40,
    ]
    kpi_labels = {
        "revenue":"Revenue","net_profit":"Net Profit","gross_margin":"Gross Margin",
        "net_margin":"Net Margin","ebitda":"EBITDA","operating_cashflow":"Operating Cash Flow",
        "current_ratio":"Current Ratio","debt_to_equity":"Debt / Equity",
        "working_capital":"Working Capital","total_debt":"Total Debt",
    }
    kpis = data.get("kpis", {})
    for k, lbl in kpi_labels.items():
        v = kpis.get(k, {}).get("value", "N/A")
        n = kpis.get(k, {}).get("note", "")
        report_lines.append(f"  {lbl:<24} {v:<14} {n}")
    report_lines += ["", "KEY RISKS", "-" * 40]
    for r in data.get("risks", []):
        report_lines += [f"  Risk: {r.get('title','')}", f"        {r.get('detail','')}", f"  Fix:  {r.get('fix','')}", ""]
    report_lines += ["RECOMMENDATIONS", "-" * 40]
    for i, rec in enumerate(data.get("recommendations", []), 1):
        report_lines += [f"  {i}. {rec.get('action','')}", f"     {rec.get('rationale','')}", ""]

    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button("Download Report (.txt)", "\n".join(report_lines),
                           "financial_analysis.txt", "text/plain", use_container_width=True)
    with dl2:
        slug = re.sub(r"[^a-z0-9]", "_", data.get("company_name","report").lower())
        st.download_button("Download Report (.xlsx)", build_excel_report(data),
                           f"{slug}_financial_analysis.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    with dl3:
        st.download_button("Download Raw Data (.json)", json.dumps(data, indent=2),
                           "financial_analysis.json", "application/json",
                           use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center; color:#484f58; font-size:0.76rem;'>"
    "FinSight &nbsp;·&nbsp; Powered by Groq (LLaMA 3.3 70B) &nbsp;·&nbsp;"
    "For informational purposes only — not financial advice."
    "</p>",
    unsafe_allow_html=True,
)
