"""FinSight — single-file Streamlit app."""
import streamlit as st
from groq import Groq
import io, os, csv, json, re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

st.set_page_config(
    page_title="FinSight — Financial Statement Analyser",
    page_icon="",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STYLES
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 0.5rem !important; padding-bottom: 3rem; max-width: 1200px; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebarNav"], section[data-testid="stSidebar"] { display: none; }

/* ── Nav buttons — fixed single-line width ── */
div[data-testid="stButton"] > button {
    background: #1e2736;
    color: #c9d1d9 !important;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.45rem 0.5rem;
    font-size: 0.85rem;
    font-weight: 500;
    width: 100%;
    white-space: nowrap;
    overflow: hidden;
    transition: background 0.15s, color 0.15s;
    line-height: 1.2;
}
div[data-testid="stButton"] > button:hover {
    background: #2e5eaa; color: white !important; border-color: #2e5eaa;
}

/* ── Analyse button override ── */
div[data-testid="stButton"][data-key="analyse_btn"] > button,
button[kind="primary"] {
    background: #2e5eaa !important; color: white !important;
    border: none !important; font-size: 0.95rem !important;
    font-weight: 600 !important; padding: 0.7rem 2rem !important;
}

[data-testid="metric-container"] {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 10px; padding: 0.9rem 1rem;
}
[data-testid="metric-container"] label {
    color: #8b949e !important; font-size: 0.72rem !important;
    font-weight: 700 !important; letter-spacing: 0.8px; text-transform: uppercase;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f0f6fc !important; font-size: 1.2rem !important; font-weight: 700 !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }

[data-testid="stDownloadButton"] > button {
    background: #161b22 !important; color: #f0f6fc !important;
    border: 1px solid #30363d !important; border-radius: 8px;
    font-size: 0.88rem; font-weight: 500; width: 100%;
    white-space: nowrap;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: #58a6ff !important; color: #58a6ff !important;
}
[data-testid="stExpander"] {
    background: #161b22; border: 1px solid #30363d !important;
    border-radius: 8px; margin-bottom: 0.5rem;
}
hr { border-color: #21262d !important; }
textarea {
    background: #0d1117 !important; border: 1px solid #30363d !important;
    color: #c9d1d9 !important; border-radius: 8px !important;
}
input[type="text"], input[type="password"], input[type="email"] {
    background: #0d1117 !important; border: 1px solid #30363d !important;
    color: #c9d1d9 !important; border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for key, default in [
    ("page", "analyser"),
    ("logged_in", False),
    ("user_email", ""),
    ("is_pro", False),
    ("analysis_data", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─────────────────────────────────────────────────────────────────────────────
# NAV BAR — centred, single-line buttons
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:#0d1117;border-bottom:1px solid #21262d;
            padding:0.6rem 2rem;display:flex;align-items:center;
            justify-content:space-between;margin-bottom:0.5rem;">
    <span style="font-size:1.15rem;font-weight:800;color:#f0f6fc;letter-spacing:-0.3px;">FinSight</span>
</div>
""", unsafe_allow_html=True)

# Centre nav using columns
pad_l, n1, n2, n3, n4, n5, pad_r = st.columns([2, 1, 1, 1, 1, 1, 2])
with n1:
    if st.button("Analyser", key="nb_a", use_container_width=True):
        st.session_state.page = "analyser"; st.rerun()
with n2:
    if st.button("Features", key="nb_f", use_container_width=True):
        st.session_state.page = "features"; st.rerun()
with n3:
    if st.button("Pricing", key="nb_p", use_container_width=True):
        st.session_state.page = "pricing"; st.rerun()
with n4:
    lbl = st.session_state.user_email.split("@")[0] if st.session_state.logged_in else "Log In"
    if st.button(lbl, key="nb_l", use_container_width=True):
        st.session_state.page = "login"; st.rerun()
with n5:
    if st.session_state.logged_in:
        if st.button("Log Out", key="nb_lo", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.is_pro = False
            st.session_state.page = "analyser"
            st.rerun()
    else:
        if st.button("Sign Up", key="nb_s", use_container_width=True):
            st.session_state.page = "signup"; st.rerun()

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def section_label(text):
    st.markdown(
        f"<div style='color:#8b949e;font-size:0.72rem;font-weight:700;"
        f"letter-spacing:1.5px;margin-bottom:0.6rem;'>{text}</div>",
        unsafe_allow_html=True)

def tick(t):
    return (f"<div style='display:flex;align-items:flex-start;gap:0.6rem;padding:0.55rem 0;"
            f"border-bottom:1px solid #21262d;'>"
            f"<span style='color:#3fb950;font-weight:700;font-size:0.9rem;'>+</span>"
            f"<span style='color:#c9d1d9;font-size:0.88rem;line-height:1.4;'>{t}</span></div>")

def cross(t):
    return (f"<div style='display:flex;align-items:flex-start;gap:0.6rem;padding:0.55rem 0;"
            f"border-bottom:1px solid #21262d;'>"
            f"<span style='color:#484f58;font-weight:700;font-size:0.9rem;'>-</span>"
            f"<span style='color:#484f58;font-size:0.88rem;line-height:1.4;'>{t}</span></div>")

def login_wall():
    """Show a prompt to log in before downloading."""
    st.warning("Please log in to download your report. Use the Log In button in the nav bar.")

def pro_wall():
    """Show upgrade prompt for pro-only features."""
    st.info("This download is available on the Pro plan ($10/month). Go to Pricing to upgrade.")


# ─────────────────────────────────────────────────────────────────────────────
# FILE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
def extract_pdf(file_bytes):
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t: parts.append(t)
                for table in page.extract_tables():
                    for row in table:
                        parts.append(" | ".join(str(c).strip() if c else "" for c in row))
        return "\n".join(parts)
    except Exception as e:
        return f"[PDF error: {e}]"

def extract_csv_text(file_bytes):
    try:
        content = file_bytes.decode("utf-8", errors="replace")
        return "\n".join(" | ".join(r) for r in csv.reader(io.StringIO(content)))
    except Exception as e:
        return f"[CSV error: {e}]"

def extract_file(uf):
    name = uf.name.lower(); raw = uf.read()
    if name.endswith(".pdf"): return extract_pdf(raw)
    if name.endswith(".csv"): return extract_csv_text(raw)
    return raw.decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a highly skilled financial analyst and forensic accountant based in New Zealand.
You will receive one or more financial statements. Cross-reference all documents together to produce a single unified analysis.
Return ONLY a valid JSON object — no markdown, no extra text.

Schema:
{
  "company_name": "string or 'Unknown Company'",
  "period": "string e.g. 'FY 2023' or 'Not provided'",
  "documents_detected": ["list of statement types found"],
  "health_score": 1-10,
  "health_label": "Strong" | "Moderate" | "Weak",
  "health_summary": "2-3 sentence executive summary in NZ English",
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
  "profitability":            {"headline": "string", "points": ["string","string","string"]},
  "cash_health":              {"headline": "string", "points": ["string","string","string"]},
  "working_capital_analysis": {"headline": "string", "points": ["string","string","string"]},
  "balance_sheet":            {"headline": "string", "points": ["string","string","string"]},
  "investor_view": "3-4 sentence blunt investor-style interpretation in NZ English",
  "risks":           [{"title":"string","detail":"string","fix":"string"},{"title":"string","detail":"string","fix":"string"},{"title":"string","detail":"string","fix":"string"}],
  "positives":       [{"title":"string","detail":"string"},{"title":"string","detail":"string"},{"title":"string","detail":"string"}],
  "recommendations": [{"action":"string","rationale":"string"},{"action":"string","rationale":"string"},{"action":"string","rationale":"string"}]
}
Rules: "Not provided" for missing data. Never invent numbers. Format values: "$12.4M","18.3%","2.1x". Notes max 8 words. NZ English. Return ONLY the JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# GROQ API
# ─────────────────────────────────────────────────────────────────────────────
def call_groq(text, api_key):
    client = Groq(api_key=api_key)
    if len(text) > 28000:
        text = text[:28000] + "\n\n[Truncated]"
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile", max_tokens=4096, temperature=0.1,
        messages=[{"role":"system","content":SYSTEM_PROMPT},
                  {"role":"user","content":f"Analyse these financial statements:\n\n{text}"}])
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?","",raw).strip()
    raw = re.sub(r"```$","",raw).strip()
    try: return json.loads(raw), raw
    except Exception:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try: return json.loads(m.group()), raw
            except Exception: pass
    return None, raw


# ─────────────────────────────────────────────────────────────────────────────
# TXT REPORT BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def build_txt(data):
    kpi_labels = {"revenue":"Revenue","net_profit":"Net Profit","gross_margin":"Gross Margin",
                  "net_margin":"Net Margin","ebitda":"EBITDA","operating_cashflow":"Operating Cash Flow",
                  "current_ratio":"Current Ratio","debt_to_equity":"Debt/Equity",
                  "working_capital":"Working Capital","total_debt":"Total Debt"}
    kpis = data.get("kpis",{})
    lines = ["FINANCIAL ANALYSIS REPORT — FINSIGHT","="*60,
             f"Company : {data.get('company_name','N/A')}",
             f"Period  : {data.get('period','N/A')}",
             f"Health  : {data.get('health_label','N/A')}   Score: {data.get('health_score','N/A')}/10",
             "","EXECUTIVE SUMMARY","-"*40,data.get("health_summary",""),
             "","INVESTOR VIEW","-"*40,data.get("investor_view",""),
             "","KEY METRICS","-"*40]
    for k,lb in kpi_labels.items():
        v=kpis.get(k,{}).get("value","N/A"); n=kpis.get(k,{}).get("note","")
        lines.append(f"  {lb:<24} {v:<14} {n}")
    lines+=["","KEY RISKS","-"*40]
    for rv in data.get("risks",[]):
        lines+=[f"  Risk: {rv.get('title','')}",f"        {rv.get('detail','')}",f"  Fix:  {rv.get('fix','')}",""]
    lines+=["RECOMMENDATIONS","-"*40]
    for i,rec in enumerate(data.get("recommendations",[]),1):
        lines+=[f"  {i}. {rec.get('action','')}",f"     {rec.get('rationale','')}",""]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL REPORT BUILDER (Pro only)
# ─────────────────────────────────────────────────────────────────────────────
def build_excel(data):
    wb = Workbook()
    DN="0D1B2A"; AB="2E5EAA"; LB="D6E4F7"; WH="FFFFFF"; LG="F5F7FA"; MG="C5CDD9"
    GB="E6F4EA"; GF="1A6B2E"; RB="FDE8E8"; RF="9B1C1C"; AMB="FFF3CD"; AMF="7D5A00"; MN="1B2A3B"
    lbl=data.get("health_label","Moderate"); sc=data.get("health_score",5)
    hc={"Strong":GF,"Moderate":AMF,"Weak":RF}.get(lbl,AMF)
    hb={"Strong":GB,"Moderate":AMB,"Weak":RB}.get(lbl,AMB)
    def hf(sz=11,b=True,c=WH): return Font(name="Arial",size=sz,bold=b,color=c)
    def bf(sz=10,b=False,c="000000"): return Font(name="Arial",size=sz,bold=b,color=c)
    def fl(h): return PatternFill("solid",fgColor=h)
    def tb(s="all"):
        sd=Side(style="thin",color=MG); n=Side(style=None)
        return Border(left=sd if "all" in s or "left" in s else n,
                      right=sd if "all" in s or "right" in s else n,
                      top=sd if "all" in s or "top" in s else n,
                      bottom=sd if "all" in s or "bottom" in s else n)
    def ca(): return Alignment(horizontal="center",vertical="center",wrap_text=True)
    def la(w=True): return Alignment(horizontal="left",vertical="center",wrap_text=w)
    def rh(ws,r,h): ws.row_dimensions[r].height=h
    def mw(ws,rng,v,fn,al,fl_=None):
        ws.merge_cells(rng); c=ws[rng.split(":")[0]]
        c.value=v; c.font=fn; c.alignment=al
        if fl_: c.fill=fl_

    ws=wb.active; ws.title="Executive Summary"; ws.sheet_view.showGridLines=False
    for i,w in enumerate([2,28,22,22,22,22,2],1): ws.column_dimensions[get_column_letter(i)].width=w
    r=1
    for ri in range(r,r+3):
        rh(ws,ri,6 if ri!=r+1 else 36)
        for ci in range(1,8): ws.cell(ri,ci).fill=fl(DN)
    mw(ws,f"B{r+1}:F{r+1}","FINANCIAL STATEMENT ANALYSIS — FINSIGHT",hf(15),ca(),fl(DN)); r+=3
    for ri in range(r,r+4):
        rh(ws,ri,6 if ri in(r,r+3) else 26)
        for ci in range(1,8): ws.cell(ri,ci).fill=fl(MN)
    ws.merge_cells(f"B{r+1}:C{r+1}")
    c=ws[f"B{r+1}"]; c.value=data.get("company_name","Unknown"); c.font=hf(13); c.alignment=la(False)
    ws.cell(r+1,4).value=data.get("period",""); ws.cell(r+1,4).font=hf(11,False,MG); ws.cell(r+1,4).alignment=ca()
    for ci,val in enumerate([lbl,f"Score: {sc}/10"],5):
        c=ws.cell(r+1,ci); c.value=val; c.font=Font(name="Arial",size=11,bold=True,color=hc)
        c.fill=fl(hb); c.alignment=ca(); c.border=tb()
    r+=4; rh(ws,r,6); r+=1; rh(ws,r,16)
    mw(ws,f"B{r}:F{r}","EXECUTIVE SUMMARY",hf(10),la(False),fl(AB)); r+=1
    for line in data.get("health_summary","").split(". "):
        if not line.strip(): continue
        rh(ws,r,30); ws.merge_cells(f"B{r}:F{r}"); c=ws[f"B{r}"]
        c.value=line.strip().rstrip(".")+"."; c.font=bf(10); c.alignment=la(); c.fill=fl(LG); c.border=tb("bottom"); r+=1
    rh(ws,r,6); r+=1; rh(ws,r,16)
    mw(ws,f"B{r}:F{r}","INVESTOR VIEW",hf(10),la(False),fl(AB)); r+=1
    iv=data.get("investor_view",""); rh(ws,r,max(60,len(iv)//4))
    ws.merge_cells(f"B{r}:F{r}"); c=ws[f"B{r}"]
    c.value=iv; c.font=bf(10,b=True,c="1A1A1A"); c.alignment=la(); c.fill=fl(LB); c.border=tb()

    ws2=wb.create_sheet("KPI Metrics"); ws2.sheet_view.showGridLines=False
    for i,w in enumerate([2,30,20,35,2],1): ws2.column_dimensions[get_column_letter(i)].width=w
    r=1
    for ri in range(r,r+3):
        rh(ws2,ri,6 if ri!=r+1 else 36)
        for ci in range(1,6): ws2.cell(ri,ci).fill=fl(DN)
    mw(ws2,f"B{r+1}:D{r+1}","KEY FINANCIAL METRICS",hf(14),ca(),fl(DN)); r+=3
    rh(ws2,r,20)
    for ci,h in enumerate(["Metric","Value","Commentary"],2):
        c=ws2.cell(r,ci); c.value=h; c.font=hf(10); c.fill=fl(AB); c.alignment=ca(); c.border=tb()
    r+=1
    kpis=data.get("kpis",{})
    for idx,(key,label) in enumerate([("revenue","Revenue"),("net_profit","Net Profit"),("gross_margin","Gross Margin"),
        ("net_margin","Net Margin"),("ebitda","EBITDA"),("operating_cashflow","Operating Cash Flow"),
        ("current_ratio","Current Ratio"),("debt_to_equity","Debt/Equity"),("working_capital","Working Capital"),("total_debt","Total Debt")]):
        item=kpis.get(key,{}); rf=fl(WH) if idx%2==0 else fl(LG); rh(ws2,r,22)
        c=ws2.cell(r,2); c.value=label; c.font=bf(10,b=True); c.fill=rf; c.alignment=la(False); c.border=tb()
        c=ws2.cell(r,3); c.value=item.get("value","N/A"); c.font=Font(name="Arial",size=11,bold=True,color=AB); c.fill=rf; c.alignment=ca(); c.border=tb()
        c=ws2.cell(r,4); c.value=item.get("note",""); c.font=bf(9,c="444444"); c.fill=rf; c.alignment=la(); c.border=tb(); r+=1

    buf=io.BytesIO(); wb.save(buf); buf.seek(0); return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# WORD DOC BUILDER (Pro only)
# ─────────────────────────────────────────────────────────────────────────────
def build_docx(data):
    doc = DocxDocument()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin   = Inches(1.2)
        section.right_margin  = Inches(1.2)

    def add_heading(text, level=1, colour=None):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after  = Pt(4)
        run = p.add_run(text)
        run.bold = True
        run.font.name = "Arial"
        run.font.size = Pt(16 if level==1 else 13 if level==2 else 11)
        if colour:
            run.font.color.rgb = RGBColor(*colour)
        return p

    def add_body(text, italic=False, colour=None):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(10)
        run.italic = italic
        if colour:
            run.font.color.rgb = RGBColor(*colour)
        return p

    def add_bullet(text):
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(10)

    def add_divider():
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after  = Pt(4)
        run = p.add_run("─" * 60)
        run.font.color.rgb = RGBColor(48,54,61)
        run.font.size = Pt(8)

    lbl   = data.get("health_label","Moderate")
    score = data.get("health_score",5)
    colour_map = {"Strong":(63,185,80),"Moderate":(212,160,23),"Weak":(248,81,73)}
    hcolour = colour_map.get(lbl,(212,160,23))

    # Title
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = title.add_run("FINANCIAL STATEMENT ANALYSIS")
    tr.bold = True; tr.font.name = "Arial"; tr.font.size = Pt(20)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub.add_run("FinSight — AI-Powered Financial Analysis")
    sr.font.name = "Arial"; sr.font.size = Pt(11); sr.font.color.rgb = RGBColor(139,148,158)

    add_divider()

    # Company / Health block
    doc.add_paragraph()
    cp = doc.add_paragraph()
    cr_ = cp.add_run(f"{data.get('company_name','Unknown Company')}  ·  {data.get('period','')}")
    cr_.bold = True; cr_.font.name = "Arial"; cr_.font.size = Pt(13)

    hp = doc.add_paragraph()
    hr_ = hp.add_run(f"Financial Health: {lbl}   |   Score: {score} / 10")
    hr_.bold = True; hr_.font.name = "Arial"; hr_.font.size = Pt(12)
    hr_.font.color.rgb = RGBColor(*hcolour)

    add_divider()

    # Executive Summary
    add_heading("Executive Summary", 2, (46,94,170))
    add_body(data.get("health_summary",""))

    # Investor View
    add_heading("Investor View", 2, (46,94,170))
    add_body(data.get("investor_view",""), italic=True)

    add_divider()

    # KPI table
    add_heading("Key Financial Metrics", 2, (46,94,170))
    kpi_labels = [("revenue","Revenue"),("net_profit","Net Profit"),("gross_margin","Gross Margin"),
                  ("net_margin","Net Margin"),("ebitda","EBITDA"),("operating_cashflow","Operating Cash Flow"),
                  ("current_ratio","Current Ratio"),("debt_to_equity","Debt / Equity"),
                  ("working_capital","Working Capital"),("total_debt","Total Debt")]
    kpis = data.get("kpis",{})
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i,h in enumerate(["Metric","Value","Commentary"]):
        hdr[i].text = h
        run = hdr[i].paragraphs[0].runs[0]
        run.bold = True; run.font.name = "Arial"; run.font.size = Pt(10)
    for key, label in kpi_labels:
        item = kpis.get(key,{})
        row = table.add_row().cells
        row[0].text = label
        row[1].text = item.get("value","N/A")
        row[2].text = item.get("note","")
        for cell in row:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.name = "Arial"; run.font.size = Pt(10)

    add_divider()

    # Performance sections
    for sec_key, sec_label in [("profitability","Profitability"),("cash_health","Cash Health"),
                                ("working_capital_analysis","Working Capital"),("balance_sheet","Balance Sheet")]:
        sec = data.get(sec_key,{})
        add_heading(sec_label, 2, (46,94,170))
        add_body(sec.get("headline",""), italic=True, colour=(139,148,158))
        for pt in sec.get("points",[]):
            add_bullet(pt)

    add_divider()

    # Risks
    add_heading("Key Risks & Concerns", 2, (248,81,73))
    for risk in data.get("risks",[]):
        rp = doc.add_paragraph()
        rp.paragraph_format.space_after = Pt(2)
        rr = rp.add_run(risk.get("title",""))
        rr.bold = True; rr.font.name = "Arial"; rr.font.size = Pt(10)
        rr.font.color.rgb = RGBColor(248,81,73)
        add_body(f"Issue: {risk.get('detail','')}")
        add_body(f"Suggested Action: {risk.get('fix','')}", colour=(63,185,80))

    # Positives
    add_heading("Positive Signals", 2, (63,185,80))
    for pos in data.get("positives",[]):
        pp = doc.add_paragraph()
        pr = pp.add_run(pos.get("title",""))
        pr.bold = True; pr.font.name = "Arial"; pr.font.size = Pt(10)
        pr.font.color.rgb = RGBColor(63,185,80)
        add_body(pos.get("detail",""))

    # Recommendations
    add_heading("Recommendations", 2, (46,94,170))
    for i, rec in enumerate(data.get("recommendations",[]),1):
        rp = doc.add_paragraph()
        rr = rp.add_run(f"{i}. {rec.get('action','')}")
        rr.bold = True; rr.font.name = "Arial"; rr.font.size = Pt(10)
        rr.font.color.rgb = RGBColor(88,166,255)
        add_body(rec.get("rationale",""), colour=(139,148,158))

    add_divider()
    fn = doc.add_paragraph()
    fn.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr_ = fn.add_run("FinSight  ·  For informational purposes only — not financial advice.")
    fr_.font.name = "Arial"; fr_.font.size = Pt(8); fr_.font.color.rgb = RGBColor(72,79,88)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def hp_colours(label):
    if label=="Strong":   return "#0d2818","#3fb950","#238636"
    if label=="Moderate": return "#2d1f00","#d4a017","#9e6a03"
    return "#2d0f0f","#f85149","#b91c1c"

def render_banner(data):
    label=data.get("health_label","Moderate"); score=data.get("health_score",5)
    summary=data.get("health_summary",""); company=data.get("company_name","")
    period=data.get("period",""); docs=data.get("documents_detected",[])
    bg,fg,border=hp_colours(label); bar="█"*score+"░"*(10-score)
    tags="".join(f"<span style='background:#21262d;color:#8b949e;border-radius:4px;padding:0.1rem 0.5rem;font-size:0.72rem;margin-right:0.3rem;'>{d}</span>" for d in docs)
    dh=f"<div style='margin-top:0.5rem;'>{tags}</div>" if docs else ""
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {border};border-radius:12px;padding:1.8rem 2rem;margin-bottom:1.5rem;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem;">
            <div>
                <div style="color:#8b949e;font-size:0.7rem;font-weight:700;letter-spacing:1.5px;margin-bottom:0.4rem;">OVERALL FINANCIAL HEALTH</div>
                <div style="font-size:1.9rem;font-weight:700;color:{fg};line-height:1.1;">{label}</div>
                <div style="color:#8b949e;font-size:0.83rem;margin-top:0.3rem;">{company}&nbsp;&nbsp;·&nbsp;&nbsp;{period}</div>{dh}
            </div>
            <div style="text-align:right;">
                <div style="color:#8b949e;font-size:0.7rem;font-weight:700;letter-spacing:1.5px;">HEALTH SCORE</div>
                <div style="font-size:2.4rem;font-weight:800;color:{fg};line-height:1.1;">{score}<span style="font-size:1rem;color:#8b949e;">&thinsp;/ 10</span></div>
                <div style="font-family:monospace;color:{fg};font-size:0.95rem;letter-spacing:2px;">{bar}</div>
            </div>
        </div>
        <div style="margin-top:1.1rem;padding-top:1.1rem;border-top:1px solid {border};color:#c9d1d9;font-size:0.93rem;line-height:1.65;">{summary}</div>
    </div>""", unsafe_allow_html=True)

def render_kpis(kpis):
    section_label("KEY FINANCIAL METRICS")
    order=[("revenue","Revenue"),("net_profit","Net Profit"),("gross_margin","Gross Margin"),("net_margin","Net Margin"),("ebitda","EBITDA"),
           ("operating_cashflow","Operating Cash Flow"),("current_ratio","Current Ratio"),("debt_to_equity","Debt / Equity"),("working_capital","Working Capital"),("total_debt","Total Debt")]
    for rs in range(0,len(order),5):
        chunk=order[rs:rs+5]; cols=st.columns(len(chunk))
        for col,(key,label) in zip(cols,chunk):
            item=kpis.get(key,{}); value=item.get("value","N/A"); note=item.get("note","")
            dc="inverse" if any(w in note.lower() for w in ["pressure","decline","high","weak","low"]) else "normal"
            with col: st.metric(label=label,value=value,delta=note if note else None,delta_color=dc)
        st.markdown("<div style='margin-bottom:0.4rem'></div>",unsafe_allow_html=True)

def render_card(title, section):
    headline=section.get("headline",""); points=section.get("points",[])
    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:1.2rem 1.5rem;margin-bottom:0.5rem;">
        <div style="color:#f0f6fc;font-size:0.85rem;font-weight:700;letter-spacing:0.5px;margin-bottom:0.5rem;">{title.upper()}</div>
        <div style="color:#8b949e;font-size:0.82rem;line-height:1.5;border-left:3px solid #2e5eaa;padding-left:0.7rem;font-style:italic;">{headline}</div>
    </div>""", unsafe_allow_html=True)
    for pt in points:
        st.markdown(f"<div style='color:#c9d1d9;font-size:0.84rem;padding:0.25rem 0 0.25rem 1rem;border-left:2px solid #30363d;margin-bottom:0.3rem;'>{pt}</div>", unsafe_allow_html=True)
    st.markdown("")


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════  LOGIN PAGE  ═════════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.page == "login":
    _, lc, _ = st.columns([1,2,1])
    with lc:
        st.markdown("<h2 style='color:#f0f6fc;font-weight:700;margin-bottom:0.2rem;'>Log In</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#8b949e;font-size:0.9rem;margin-bottom:1.5rem;'>Welcome back. Log in to access your downloads.</p>", unsafe_allow_html=True)
        email    = st.text_input("Email address", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
        if st.button("Log In", key="login_submit", use_container_width=True):
            if email and password:
                # Simulated auth — in production connect to a real auth system
                st.session_state.logged_in  = True
                st.session_state.user_email = email
                # Demo: emails containing "pro" get pro access
                st.session_state.is_pro = "pro" in email.lower()
                st.session_state.page = "analyser"
                st.rerun()
            else:
                st.error("Please enter your email and password.")
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        st.markdown("<p style='color:#8b949e;font-size:0.85rem;text-align:center;'>Don't have an account? <a href='#' style='color:#58a6ff;'>Sign up</a></p>", unsafe_allow_html=True)
        if st.button("Create an account instead", key="go_signup", use_container_width=True):
            st.session_state.page = "signup"; st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════  SIGN UP PAGE  ═══════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "signup":
    _, sc, _ = st.columns([1,2,1])
    with sc:
        st.markdown("<h2 style='color:#f0f6fc;font-weight:700;margin-bottom:0.2rem;'>Create Account</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#8b949e;font-size:0.9rem;margin-bottom:1.5rem;'>Sign up to download your reports and access Pro features.</p>", unsafe_allow_html=True)
        email    = st.text_input("Email address", placeholder="you@example.com", key="su_email")
        password = st.text_input("Password", type="password", placeholder="Choose a password", key="su_pw")
        confirm  = st.text_input("Confirm password", type="password", placeholder="Repeat password", key="su_cp")
        st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

        plan = st.radio("Choose your plan", ["Free — 5 analyses/month", "Pro — $10/month (unlimited)"],
                        key="signup_plan")

        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
        if st.button("Create Account", key="signup_submit", use_container_width=True):
            if not email or not password:
                st.error("Please fill in all fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                st.session_state.logged_in  = True
                st.session_state.user_email = email
                st.session_state.is_pro     = "Pro" in plan
                st.session_state.page = "analyser"
                st.success("Account created! Welcome to FinSight.")
                st.rerun()

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Already have an account? Log in", key="go_login", use_container_width=True):
            st.session_state.page = "login"; st.rerun()

        if "Pro" in plan if "plan" in dir() else False:
            st.markdown("""
            <div style="background:#161b22;border:1px solid #2e5eaa;border-radius:10px;padding:1rem;margin-top:1rem;">
                <div style="color:#58a6ff;font-size:0.85rem;font-weight:600;margin-bottom:0.3rem;">Pro Plan — $10/month</div>
                <div style="color:#8b949e;font-size:0.82rem;">Payments are coming soon. Your Pro access will be activated when billing launches.</div>
            </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════  ANALYSER PAGE  ══════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "analyser":

    st.markdown("""
    <div style="text-align:center;padding:1.5rem 1rem 1rem;">
        <h1 style="font-size:2.2rem;font-weight:800;color:#f0f6fc;margin:0 0 0.5rem;letter-spacing:-0.5px;">Financial Statement Analyser</h1>
        <p style="color:#8b949e;font-size:0.97rem;margin:0;">Upload your Income Statement, Balance Sheet and Cash Flow Statement for a complete forensic analysis.</p>
    </div>""", unsafe_allow_html=True)

    if st.session_state.logged_in:
        plan_badge = "Pro" if st.session_state.is_pro else "Free"
        badge_col  = "#2e5eaa" if st.session_state.is_pro else "#484f58"
        st.markdown(f"<div style='text-align:center;margin-bottom:0.5rem;'>"
                    f"<span style='background:{badge_col};color:#fff;font-size:0.72rem;font-weight:700;"
                    f"letter-spacing:1px;padding:0.2rem 0.8rem;border-radius:20px;'>{plan_badge} PLAN</span></div>",
                    unsafe_allow_html=True)

    api_key = os.getenv("GROQ_API_KEY","")
    if not api_key:
        with st.expander("Groq API Key  —  free at console.groq.com", expanded=True):
            api_key = st.text_input("Key", type="password", placeholder="gsk_...", label_visibility="collapsed")
            st.caption("Get your free key at [console.groq.com](https://console.groq.com) → API Keys → Create Key")
        if not api_key:
            st.info("Enter your Groq API key above to get started.")

    st.divider()

    cl, cr = st.columns(2, gap="large")
    with cl:
        st.markdown("<div style='color:#f0f6fc;font-size:0.9rem;font-weight:600;margin-bottom:0.4rem;'>Upload Financial Statements</div>", unsafe_allow_html=True)
        st.caption("PDF, CSV or TXT — upload all three statements at once for the best results")
        uploaded_files = st.file_uploader("files", type=["pdf","csv","txt"], accept_multiple_files=True, label_visibility="collapsed")
        if uploaded_files:
            for f in uploaded_files:
                st.markdown(f"<small style='color:#8b949e'>{f.name} — {len(f.getvalue())/1024:.1f} KB</small>", unsafe_allow_html=True)
    with cr:
        st.markdown("<div style='color:#f0f6fc;font-size:0.9rem;font-weight:600;margin-bottom:0.4rem;'>Or Paste Financial Data</div>", unsafe_allow_html=True)
        st.caption("Paste raw text, numbers, or CSV rows directly")
        pasted = st.text_area("paste", height=155, placeholder="Revenue: $10.5M\nNet Profit: $1.8M\n...", label_visibility="collapsed")

    st.divider()
    _, bc, _ = st.columns([1,2,1])
    with bc:
        go = st.button("Analyse Financial Statements", key="analyse_btn", use_container_width=True)

    if go:
        if not api_key:
            st.error("Please enter your Groq API key."); st.stop()
        parts = []
        if uploaded_files:
            for uf in uploaded_files:
                uf.seek(0)
                parts.append(f"=== DOCUMENT: {uf.name} ===\n{extract_file(uf)}")
        if pasted.strip():
            parts.append(f"=== PASTED DATA ===\n{pasted.strip()}")
        if not parts:
            st.warning("Please upload at least one file or paste financial data."); st.stop()

        with st.spinner(f"Analysing {len(parts)} document(s)..."):
            try:
                data, raw = call_groq("\n\n".join(parts), api_key)
            except Exception as e:
                err=str(e).lower()
                if "401" in err or "invalid api key" in err: st.error("Invalid Groq API key — please check it.")
                elif "429" in err or "rate limit" in err:   st.error("Rate limit reached — please wait and retry.")
                else: st.error(f"API error: {e}")
                st.stop()

        if not data:
            st.warning("Could not parse output."); st.text(raw); st.stop()

        st.session_state.analysis_data = data
        st.success("Analysis complete.")
        st.divider()

        render_banner(data)
        render_kpis(data.get("kpis",{}))
        st.divider()

        section_label("PERFORMANCE SUMMARY")
        l, r_col = st.columns(2, gap="large")
        with l:
            render_card("Profitability",   data.get("profitability",{}))
            render_card("Cash Health",     data.get("cash_health",{}))
        with r_col:
            render_card("Working Capital", data.get("working_capital_analysis",{}))
            render_card("Balance Sheet",   data.get("balance_sheet",{}))
        st.divider()

        section_label("INVESTOR VIEW — WHAT IS REALLY GOING ON")
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #4a4a8a;
                    border-radius:10px;padding:1.4rem 1.8rem;color:#d0d0f0;font-size:0.95rem;line-height:1.7;">
            {data.get("investor_view","")}
        </div>""", unsafe_allow_html=True)
        st.divider()

        rc_col, pc_col = st.columns(2, gap="large")
        with rc_col:
            section_label("KEY RISKS & CONCERNS")
            for risk in data.get("risks",[]):
                with st.expander(risk.get("title","Risk")):
                    st.markdown(f"**Issue:** {risk.get('detail','')}")
                    st.markdown(f"**Suggested Action:** {risk.get('fix','')}")
        with pc_col:
            section_label("POSITIVE SIGNALS")
            for pos in data.get("positives",[]):
                st.markdown(f"""
                <div style="background:#0d2818;border:1px solid #238636;border-radius:8px;padding:0.9rem 1.1rem;margin-bottom:0.6rem;">
                    <div style="color:#3fb950;font-weight:600;font-size:0.87rem;margin-bottom:0.3rem;">{pos.get('title','')}</div>
                    <div style="color:#8b949e;font-size:0.82rem;">{pos.get('detail','')}</div>
                </div>""", unsafe_allow_html=True)
        st.divider()

        section_label("RECOMMENDATIONS")
        for i, rec in enumerate(data.get("recommendations",[]),1):
            st.markdown(f"""
            <div style="background:#161b22;border-left:4px solid #2e5eaa;border-radius:0 8px 8px 0;padding:0.9rem 1.2rem;margin-bottom:0.7rem;">
                <div style="color:#58a6ff;font-weight:600;font-size:0.9rem;">{i}.&nbsp;{rec.get('action','')}</div>
                <div style="color:#8b949e;font-size:0.83rem;margin-top:0.3rem;">{rec.get('rationale','')}</div>
            </div>""", unsafe_allow_html=True)
        st.divider()

        # ── Downloads ─────────────────────────────────────────────────────────
        section_label("DOWNLOAD REPORT")

        if not st.session_state.logged_in:
            st.markdown("""
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;
                        padding:1.2rem 1.5rem;text-align:center;">
                <div style="color:#f0f6fc;font-size:0.95rem;font-weight:600;margin-bottom:0.4rem;">
                    Log in to download your report</div>
                <div style="color:#8b949e;font-size:0.85rem;">
                    Create a free account to download reports as TXT. Upgrade to Pro for Excel and Word.</div>
            </div>""", unsafe_allow_html=True)
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            lc2, rc2 = st.columns(2)
            with lc2:
                if st.button("Log In to Download", key="dl_login", use_container_width=True):
                    st.session_state.page = "login"; st.rerun()
            with rc2:
                if st.button("Create Free Account", key="dl_signup", use_container_width=True):
                    st.session_state.page = "signup"; st.rerun()
        else:
            slug = re.sub(r"[^a-z0-9]","_",data.get("company_name","report").lower())

            # TXT — free + pro
            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button(
                    "Download Report (.txt)",
                    build_txt(data),
                    f"{slug}_analysis.txt",
                    "text/plain",
                    use_container_width=True
                )

            # Excel — pro only
            with d2:
                if st.session_state.is_pro:
                    st.download_button(
                        "Download Report (.xlsx)",
                        build_excel(data),
                        f"{slug}_analysis.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.markdown("""
                    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                                padding:0.6rem;text-align:center;color:#484f58;font-size:0.82rem;">
                        Excel — Pro only
                    </div>""", unsafe_allow_html=True)
                    if st.button("Upgrade to Pro", key="up_excel", use_container_width=True):
                        st.session_state.page = "pricing"; st.rerun()

            # Word — pro only
            with d3:
                if st.session_state.is_pro:
                    st.download_button(
                        "Download Report (.docx)",
                        build_docx(data),
                        f"{slug}_analysis.docx",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                else:
                    st.markdown("""
                    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                                padding:0.6rem;text-align:center;color:#484f58;font-size:0.82rem;">
                        Word Doc — Pro only
                    </div>""", unsafe_allow_html=True)
                    if st.button("Upgrade to Pro", key="up_word", use_container_width=True):
                        st.session_state.page = "pricing"; st.rerun()

    st.divider()
    st.markdown("<p style='text-align:center;color:#484f58;font-size:0.76rem;'>FinSight &nbsp;·&nbsp; Powered by Groq (LLaMA 3.3 70B) &nbsp;·&nbsp; For informational purposes only — not financial advice.</p>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════  FEATURES PAGE  ══════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "features":

    st.markdown("""
    <div style="text-align:center;padding:1.5rem 1rem 1.5rem;">
        <h1 style="font-size:2.3rem;font-weight:800;color:#f0f6fc;margin:0 0 0.8rem;letter-spacing:-0.5px;line-height:1.2;">
            Understand your financials like a professional investor</h1>
        <p style="color:#8b949e;font-size:1rem;max-width:620px;margin:0 auto;line-height:1.7;">
            FinSight reads your financial statements the same way a chartered accountant or private equity analyst would —
            extracting what actually matters and explaining it in plain language.
        </p>
    </div>""", unsafe_allow_html=True)
    st.divider()

    section_label("WHAT IS FINSIGHT")
    st.markdown("""
    <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:1.8rem 2rem;margin-bottom:1.5rem;">
        <p style="color:#c9d1d9;font-size:0.97rem;line-height:1.75;margin:0;">
            FinSight is an AI-powered financial analysis tool built for business owners, accountants, investors, and finance
            students who want to understand what is really going on inside a company's numbers. Instead of spending hours
            reading through spreadsheets, you upload your financial statements and get a structured, professional-grade
            analysis in under 30 seconds.
        </p>
        <p style="color:#8b949e;font-size:0.93rem;line-height:1.75;margin:1rem 0 0;">
            It works across any industry, any currency, and any company size. Whether you are reviewing your own business,
            assessing a potential investment, or studying financial statements for the first time — FinSight gives you the
            same analysis a seasoned analyst would produce.
        </p>
    </div>""", unsafe_allow_html=True)

    section_label("WHO IS IT FOR")
    c1,c2,c3,c4 = st.columns(4, gap="medium")
    for col,title,desc in [
        (c1,"Business Owners","Understand your own financials without needing a finance background. Get a clear picture of where your business stands."),
        (c2,"Accountants & Advisers","Quickly generate structured analysis for clients. Use it as a starting point or a fast second opinion."),
        (c3,"Investors","Assess any company's financial health before making a decision. Focus on what a sophisticated investor actually cares about."),
        (c4,"Finance Students","See how professional analysis is structured. Upload real statements and learn by doing."),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:1.3rem;margin-bottom:1rem;">
                <div style="color:#58a6ff;font-size:0.88rem;font-weight:700;margin-bottom:0.5rem;">{title}</div>
                <div style="color:#8b949e;font-size:0.83rem;line-height:1.6;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.divider()
    section_label("HOW TO USE IT")
    s1,s2,s3,s4 = st.columns(4, gap="medium")
    for col,num,title,desc in [
        (s1,"01","Get your statements","Gather your Income Statement, Balance Sheet, and Cash Flow Statement from your accountant or export from Xero, MYOB, or QuickBooks."),
        (s2,"02","Upload the files","Select your files on the Analyser page. PDF, CSV, and TXT are all supported. Upload all three at once."),
        (s3,"03","Click Analyse","FinSight reads all documents together and builds a unified analysis in around 20–30 seconds."),
        (s4,"04","Review and download","Scroll through your dashboard and download the report. Free users get TXT. Pro users get Excel and Word."),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:1.3rem;margin-bottom:1rem;">
                <div style="color:#2e5eaa;font-size:1.6rem;font-weight:800;margin-bottom:0.4rem;">{num}</div>
                <div style="color:#f0f6fc;font-size:0.88rem;font-weight:700;margin-bottom:0.4rem;">{title}</div>
                <div style="color:#8b949e;font-size:0.82rem;line-height:1.6;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.divider()
    section_label("WHAT YOU GET IN EVERY ANALYSIS")
    fl_col, fr_col = st.columns(2, gap="large")
    def frow(t,d):
        return f"<div style='border-bottom:1px solid #21262d;padding:0.9rem 0;'><div style='color:#f0f6fc;font-size:0.88rem;font-weight:600;margin-bottom:0.2rem;'>{t}</div><div style='color:#8b949e;font-size:0.83rem;line-height:1.55;'>{d}</div></div>"
    with fl_col:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:1.5rem;">
            {frow("Financial Health Score","Score out of 10 with Strong / Moderate / Weak rating and plain-English executive summary.")}
            {frow("10 Key Financial Metrics","Revenue, net profit, margins, EBITDA, operating cash flow, current ratio, debt/equity, working capital, total debt.")}
            {frow("Profitability Analysis","Is profit real or accounting-driven? Are margins holding up?")}
            {frow("Cash Health","Is the business generating cash or reliant on borrowing to survive?")}
        </div>""", unsafe_allow_html=True)
    with fr_col:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:1.5rem;">
            {frow("Working Capital Analysis","Is cash being tied up in receivables or inventory?")}
            {frow("Balance Sheet Review","Debt levels, liquidity, and overall financial risk.")}
            {frow("Investor View","Blunt private-equity style interpretation of the business.")}
            {frow("Risks, Positives & Recommendations","Top 3 risks with fixes, positives, and 3 actionable recommendations.")}
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("<p style='text-align:center;color:#484f58;font-size:0.76rem;'>FinSight &nbsp;·&nbsp; For informational purposes only — not financial advice.</p>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ══════════════════════════  PRICING PAGE  ═══════════════════════════════════
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "pricing":

    st.markdown("""
    <div style="text-align:center;padding:1.5rem 1rem 1.5rem;">
        <h1 style="font-size:2.3rem;font-weight:800;color:#f0f6fc;margin:0 0 0.8rem;letter-spacing:-0.5px;">
            Simple, honest pricing</h1>
        <p style="color:#8b949e;font-size:1rem;max-width:440px;margin:0 auto;">
            Start free. Upgrade when you need unlimited access. No hidden fees, no lock-in contracts.
        </p>
    </div>""", unsafe_allow_html=True)
    st.divider()

    _, cf, cp, _ = st.columns([1,2,2,1], gap="large")

    with cf:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:16px;padding:2rem 1.8rem;">
            <div style="color:#8b949e;font-size:0.72rem;font-weight:700;letter-spacing:1.5px;margin-bottom:0.6rem;">FREE</div>
            <div style="font-size:2.8rem;font-weight:800;color:#f0f6fc;line-height:1;margin-bottom:0.3rem;">$0</div>
            <div style="color:#8b949e;font-size:0.88rem;margin-bottom:1.5rem;">No credit card required</div>
            <div style="margin-bottom:1.8rem;">
                {tick("5 analyses per month")}
                {tick("Upload up to 2 documents per analysis")}
                {tick("Full dashboard — health score, metrics, analysis")}
                {tick("Download reports as TXT")}
                {cross("Excel report download")}
                {cross("Word document download")}
                {cross("Unlimited analyses")}
            </div>
            <div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:0.8rem;text-align:center;color:#8b949e;font-size:0.88rem;font-weight:500;">
                Free Plan
            </div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Get Started Free", key="cta_free", use_container_width=True):
            st.session_state.page = "signup"; st.rerun()

    with cp:
        st.markdown(f"""
        <div style="background:#161b22;border:2px solid #2e5eaa;border-radius:16px;padding:2rem 1.8rem;position:relative;">
            <div style="position:absolute;top:-13px;left:50%;transform:translateX(-50%);background:#2e5eaa;color:#fff;
                        font-size:0.7rem;font-weight:700;letter-spacing:1px;padding:0.22rem 1rem;border-radius:20px;white-space:nowrap;">
                BEST VALUE
            </div>
            <div style="color:#58a6ff;font-size:0.72rem;font-weight:700;letter-spacing:1.5px;margin-bottom:0.6rem;">PRO</div>
            <div style="line-height:1;margin-bottom:0.3rem;">
                <span style="font-size:2.8rem;font-weight:800;color:#f0f6fc;">$10</span>
                <span style="color:#8b949e;font-size:0.9rem;"> / month</span>
            </div>
            <div style="color:#8b949e;font-size:0.83rem;margin-bottom:1.5rem;">Cancel any time. No lock-in.</div>
            <div style="margin-bottom:1.8rem;">
                {tick("Unlimited analyses")}
                {tick("Upload all 3 statements per analysis")}
                {tick("Full dashboard — health score, metrics, analysis")}
                {tick("Download reports as TXT")}
                {tick("Download reports as Excel (.xlsx)")}
                {tick("Download reports as Word (.docx)")}
                {tick("Priority processing")}
            </div>
            <div style="background:#2e5eaa;border-radius:8px;padding:0.8rem;text-align:center;color:#fff;font-size:0.92rem;font-weight:600;">
                Get Pro Access
            </div>
            <div style="text-align:center;color:#484f58;font-size:0.75rem;margin-top:0.7rem;">Payments coming soon — join the waitlist below</div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Sign Up for Pro", key="cta_pro", use_container_width=True):
            st.session_state.page = "signup"; st.rerun()

    st.divider()

    st.markdown("""
    <div style="text-align:center;padding:0.5rem 0 1rem;">
        <h2 style="color:#f0f6fc;font-size:1.4rem;font-weight:700;margin:0 0 0.4rem;">Join the Pro waitlist</h2>
        <p style="color:#8b949e;font-size:0.9rem;margin:0;">
            Payments are coming soon. Leave your email and we will notify you the moment Pro launches.
        </p>
    </div>""", unsafe_allow_html=True)
    _, wl, _ = st.columns([1,2,1])
    with wl:
        email = st.text_input("Email", placeholder="you@example.com", label_visibility="collapsed", key="wl_email")
        if st.button("Notify me when Pro launches", key="wl_btn", use_container_width=True):
            if email and "@" in email:
                st.success(f"Thanks! We will be in touch at {email} when Pro goes live.")
            else:
                st.error("Please enter a valid email address.")

    st.divider()
    st.markdown("""
    <div style="text-align:center;padding:0.5rem 0 1.2rem;">
        <div style="color:#8b949e;font-size:0.72rem;font-weight:700;letter-spacing:1.5px;margin-bottom:0.4rem;">FAQ</div>
        <h2 style="color:#f0f6fc;font-size:1.4rem;font-weight:700;margin:0;">Common questions</h2>
    </div>""", unsafe_allow_html=True)
    _, faq, _ = st.columns([1,3,1])
    with faq:
        for q,a in [
            ("Do I need a credit card for the free plan?","No. The free plan requires no payment details at all. Just sign up and start using it."),
            ("What counts as one analysis?","Each time you upload files and click Analyse, that counts as one analysis. Uploading three statements at once still counts as a single analysis."),
            ("Can I cancel the Pro plan at any time?","Yes. No lock-in contracts. Cancel at any time and retain access until the end of your billing period."),
            ("Is my financial data kept private?","Your documents are processed securely and are not stored beyond the current session."),
            ("What currencies are supported?","Any currency in your documents — NZD, AUD, USD, GBP, and others are all handled automatically."),
        ]:
            with st.expander(q):
                st.markdown(f"<div style='color:#c9d1d9;font-size:0.9rem;line-height:1.65;'>{a}</div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("<p style='text-align:center;color:#484f58;font-size:0.76rem;'>FinSight &nbsp;·&nbsp; For informational purposes only — not financial advice.</p>", unsafe_allow_html=True)
