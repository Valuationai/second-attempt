"""DiligenceAI — Financial Statement Analyser."""
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
    page_title="DiligenceAI — Financial Statement Analyser",
    page_icon="",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# DESIGN TOKENS
# ─────────────────────────────────────────────────────────────────────────────
# Primary gradient: deep navy → electric blue
# Accent: vivid teal #00D4AA, electric blue #4F8EF7
# Cards: glass-morphism on dark bg
# Status: emerald green / amber / coral red

STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

:root {
    --bg-base:       #080C14;
    --bg-card:       #0F1620;
    --bg-card-hover: #141E2E;
    --border:        rgba(255,255,255,0.07);
    --border-bright: rgba(79,142,247,0.35);
    --text-primary:  #F0F4FF;
    --text-secondary:#8B9BC8;
    --text-muted:    #4A5578;
    --accent-blue:   #4F8EF7;
    --accent-teal:   #00D4AA;
    --accent-purple: #9B6DFF;
    --success:       #10D47A;
    --warning:       #F5A623;
    --danger:        #FF5C6A;
    --nav-bg:        rgba(8,12,20,0.95);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: var(--bg-base) !important;
    color: var(--text-primary);
}

.block-container {
    padding-top: 0 !important;
    padding-bottom: 4rem;
    max-width: 1280px;
}

#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebarNav"], section[data-testid="stSidebar"] { display: none; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: #2A3450; border-radius: 3px; }

/* ── Nav buttons ── */
div[data-testid="stButton"] > button {
    background: rgba(255,255,255,0.04);
    color: var(--text-secondary) !important;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.4rem 0.6rem;
    font-size: 0.82rem;
    font-weight: 500;
    width: 100%;
    white-space: nowrap;
    overflow: hidden;
    transition: all 0.2s ease;
    letter-spacing: 0.2px;
    font-family: 'Inter', sans-serif;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(79,142,247,0.15) !important;
    color: var(--accent-blue) !important;
    border-color: rgba(79,142,247,0.4) !important;
    transform: translateY(-1px);
}

/* ── Primary CTA button ── */
div[data-testid="stButton"][data-key="analyse_btn"] > button {
    background: linear-gradient(135deg, #4F8EF7 0%, #00D4AA 100%) !important;
    color: #080C14 !important;
    border: none !important;
    font-size: 0.97rem !important;
    font-weight: 700 !important;
    padding: 0.75rem 2rem !important;
    border-radius: 10px !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 4px 24px rgba(79,142,247,0.35) !important;
}
div[data-testid="stButton"][data-key="analyse_btn"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px rgba(79,142,247,0.5) !important;
    color: #080C14 !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0F1620 0%, #111827 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.1rem;
    transition: border-color 0.2s;
}
[data-testid="metric-container"]:hover {
    border-color: var(--border-bright);
}
[data-testid="metric-container"] label {
    color: var(--text-muted) !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.3px;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 0.72rem !important;
}

/* ── Download buttons ── */
[data-testid="stDownloadButton"] > button {
    background: rgba(255,255,255,0.03) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px;
    font-size: 0.85rem;
    font-weight: 500;
    width: 100%;
    white-space: nowrap;
    padding: 0.6rem 1rem !important;
    transition: all 0.2s ease;
    font-family: 'Inter', sans-serif;
}
[data-testid="stDownloadButton"] > button:hover {
    background: rgba(79,142,247,0.1) !important;
    border-color: rgba(79,142,247,0.4) !important;
    color: var(--accent-blue) !important;
    transform: translateY(-1px);
}

/* ── Expanders ── */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px;
    margin-bottom: 0.5rem;
}
[data-testid="stExpander"]:hover {
    border-color: var(--border-bright) !important;
}

/* ── Inputs ── */
hr { border-color: rgba(255,255,255,0.06) !important; }
textarea, input[type="text"], input[type="password"], input[type="email"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
}
textarea:focus, input:focus {
    border-color: rgba(79,142,247,0.5) !important;
    box-shadow: 0 0 0 3px rgba(79,142,247,0.1) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px dashed rgba(79,142,247,0.3) !important;
    border-radius: 12px !important;
    padding: 0.5rem !important;
}

/* ── Radio ── */
[data-testid="stRadio"] label { color: var(--text-secondary) !important; }

/* ── Section divider ── */
.dai-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(79,142,247,0.2), transparent);
    margin: 1.5rem 0;
    border: none;
}
</style>
"""

st.markdown(STYLES, unsafe_allow_html=True)

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
# NAV BAR
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:rgba(8,12,20,0.97);border-bottom:1px solid rgba(255,255,255,0.06);
            padding:0 2.5rem;display:flex;align-items:center;height:60px;
            position:sticky;top:0;z-index:999;backdrop-filter:blur(20px);margin-bottom:0.5rem;">
    <div style="display:flex;align-items:center;gap:0.5rem;">
        <div style="width:28px;height:28px;background:linear-gradient(135deg,#4F8EF7,#00D4AA);
                    border-radius:7px;display:flex;align-items:center;justify-content:center;">
            <span style="color:#080C14;font-weight:900;font-size:0.85rem;">D</span>
        </div>
        <span style="font-size:1.05rem;font-weight:800;color:#F0F4FF;letter-spacing:-0.4px;">DiligenceAI</span>
    </div>
</div>
""", unsafe_allow_html=True)

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

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def section_label(text, accent="#4F8EF7"):
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:0.5rem;margin-bottom:0.8rem;'>"
        f"<div style='width:3px;height:14px;background:linear-gradient(180deg,{accent},transparent);border-radius:2px;'></div>"
        f"<span style='color:#8B9BC8;font-size:0.7rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;'>{text}</span>"
        f"</div>",
        unsafe_allow_html=True)

def card(content_html, glow=False, padding="1.4rem 1.6rem"):
    glow_style = "box-shadow:0 0 40px rgba(79,142,247,0.08);" if glow else ""
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#0F1620 0%,#111827 100%);"
        f"border:1px solid rgba(255,255,255,0.07);border-radius:14px;"
        f"padding:{padding};{glow_style}'>{content_html}</div>",
        unsafe_allow_html=True)

def gradient_badge(text, color1="#4F8EF7", color2="#00D4AA"):
    return (f"<span style='background:linear-gradient(135deg,{color1}22,{color2}22);"
            f"color:{color1};border:1px solid {color1}44;border-radius:20px;"
            f"padding:0.15rem 0.7rem;font-size:0.7rem;font-weight:700;letter-spacing:1px;'>{text}</span>")

def tick(t):
    return (f"<div style='display:flex;align-items:flex-start;gap:0.7rem;padding:0.6rem 0;"
            f"border-bottom:1px solid rgba(255,255,255,0.04);'>"
            f"<span style='color:#00D4AA;font-weight:700;font-size:0.85rem;margin-top:0.05rem;'>✓</span>"
            f"<span style='color:#C8D0E8;font-size:0.87rem;line-height:1.4;'>{t}</span></div>")

def cross(t):
    return (f"<div style='display:flex;align-items:flex-start;gap:0.7rem;padding:0.6rem 0;"
            f"border-bottom:1px solid rgba(255,255,255,0.04);'>"
            f"<span style='color:#4A5578;font-weight:700;font-size:0.85rem;margin-top:0.05rem;'>✕</span>"
            f"<span style='color:#4A5578;font-size:0.87rem;line-height:1.4;'>{t}</span></div>")

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
Cross-reference all documents together to produce a single unified analysis.
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
    "revenue":{"value":"string","note":"string"},"net_profit":{"value":"string","note":"string"},
    "gross_margin":{"value":"string","note":"string"},"net_margin":{"value":"string","note":"string"},
    "ebitda":{"value":"string","note":"string"},"operating_cashflow":{"value":"string","note":"string"},
    "current_ratio":{"value":"string","note":"string"},"debt_to_equity":{"value":"string","note":"string"},
    "working_capital":{"value":"string","note":"string"},"total_debt":{"value":"string","note":"string"}
  },
  "profitability":{"headline":"string","points":["string","string","string"]},
  "cash_health":{"headline":"string","points":["string","string","string"]},
  "working_capital_analysis":{"headline":"string","points":["string","string","string"]},
  "balance_sheet":{"headline":"string","points":["string","string","string"]},
  "investor_view":"3-4 sentence blunt investor-style interpretation in NZ English",
  "risks":[{"title":"string","detail":"string","fix":"string"},{"title":"string","detail":"string","fix":"string"},{"title":"string","detail":"string","fix":"string"}],
  "positives":[{"title":"string","detail":"string"},{"title":"string","detail":"string"},{"title":"string","detail":"string"}],
  "recommendations":[{"action":"string","rationale":"string"},{"action":"string","rationale":"string"},{"action":"string","rationale":"string"}]
}
Rules: "Not provided" for missing data. Never invent numbers. Format: "$12.4M","18.3%","2.1x". NZ English. Return ONLY JSON."""

# ─────────────────────────────────────────────────────────────────────────────
# GROQ API
# ─────────────────────────────────────────────────────────────────────────────
def call_groq(text, api_key):
    client = Groq(api_key=api_key)
    if len(text) > 28000: text = text[:28000] + "\n\n[Truncated]"
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
# REPORT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────
def build_txt(data):
    kpi_labels = {"revenue":"Revenue","net_profit":"Net Profit","gross_margin":"Gross Margin",
                  "net_margin":"Net Margin","ebitda":"EBITDA","operating_cashflow":"Operating Cash Flow",
                  "current_ratio":"Current Ratio","debt_to_equity":"Debt/Equity",
                  "working_capital":"Working Capital","total_debt":"Total Debt"}
    kpis = data.get("kpis",{})
    lines = ["FINANCIAL ANALYSIS REPORT — DiligenceAI","="*60,
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

def build_excel(data):
    wb = Workbook()
    DN="080C14"; AB="4F8EF7"; LB="0F2040"; WH="FFFFFF"; LG="F0F4FF"; MG="8B9BC8"
    GB="0A2018"; GF="00D4AA"; RB="200A0C"; RF="FF5C6A"; AMB="201408"; AMF="F5A623"; MN="0F1620"
    lbl=data.get("health_label","Moderate"); sc=data.get("health_score",5)
    hc={"Strong":GF,"Moderate":AMF,"Weak":RF}.get(lbl,AMF)
    hb={"Strong":GB,"Moderate":AMB,"Weak":RB}.get(lbl,AMB)
    def hf(sz=11,b=True,c=WH): return Font(name="Arial",size=sz,bold=b,color=c)
    def bf(sz=10,b=False,c="D0D8F0"): return Font(name="Arial",size=sz,bold=b,color=c)
    def fl(h): return PatternFill("solid",fgColor=h)
    def tb(s="all"):
        sd=Side(style="thin",color="1A2340"); n=Side(style=None)
        return Border(left=sd if "all" in s or "left" in s else n,right=sd if "all" in s or "right" in s else n,
                      top=sd if "all" in s or "top" in s else n,bottom=sd if "all" in s or "bottom" in s else n)
    def ca(): return Alignment(horizontal="center",vertical="center",wrap_text=True)
    def la(w=True): return Alignment(horizontal="left",vertical="center",wrap_text=w)
    def rh(ws,r,h): ws.row_dimensions[r].height=h
    def mw(ws,rng,v,fn,al,fl_=None):
        ws.merge_cells(rng); c=ws[rng.split(":")[0]]
        c.value=v; c.font=fn; c.alignment=al
        if fl_: c.fill=fl_

    ws=wb.active; ws.title="Executive Summary"; ws.sheet_view.showGridLines=False
    ws.sheet_view.tabSelected=True
    for i,w in enumerate([2,28,22,22,22,22,2],1): ws.column_dimensions[get_column_letter(i)].width=w
    r=1
    for ri in range(r,r+3):
        rh(ws,ri,6 if ri!=r+1 else 40)
        for ci in range(1,8): ws.cell(ri,ci).fill=fl(DN)
    mw(ws,f"B{r+1}:F{r+1}","FINANCIAL STATEMENT ANALYSIS — DiligenceAI",hf(15),ca(),fl(DN)); r+=3
    for ri in range(r,r+4):
        rh(ws,ri,6 if ri in(r,r+3) else 28)
        for ci in range(1,8): ws.cell(ri,ci).fill=fl(MN)
    ws.merge_cells(f"B{r+1}:C{r+1}")
    c=ws[f"B{r+1}"]; c.value=data.get("company_name","Unknown"); c.font=hf(13); c.alignment=la(False)
    ws.cell(r+1,4).value=data.get("period",""); ws.cell(r+1,4).font=hf(11,False,MG); ws.cell(r+1,4).alignment=ca()
    for ci,val in enumerate([lbl,f"Score: {sc}/10"],5):
        c=ws.cell(r+1,ci); c.value=val; c.font=Font(name="Arial",size=11,bold=True,color=hc)
        c.fill=fl(hb); c.alignment=ca(); c.border=tb()
    r+=4; rh(ws,r,6); r+=1; rh(ws,r,18)
    mw(ws,f"B{r}:F{r}","EXECUTIVE SUMMARY",hf(10),la(False),fl(AB)); r+=1
    for line in data.get("health_summary","").split(". "):
        if not line.strip(): continue
        rh(ws,r,32); ws.merge_cells(f"B{r}:F{r}"); c=ws[f"B{r}"]
        c.value=line.strip().rstrip(".")+"."; c.font=bf(10); c.alignment=la(); c.fill=fl(MN); c.border=tb("bottom"); r+=1
    rh(ws,r,6); r+=1; rh(ws,r,18)
    mw(ws,f"B{r}:F{r}","INVESTOR VIEW",hf(10),la(False),fl(AB)); r+=1
    iv=data.get("investor_view",""); rh(ws,r,max(60,len(iv)//4))
    ws.merge_cells(f"B{r}:F{r}"); c=ws[f"B{r}"]
    c.value=iv; c.font=bf(10,b=True,c="C8D0E8"); c.alignment=la(); c.fill=fl(LB); c.border=tb()

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
    r+=1; kpis=data.get("kpis",{})
    for idx,(key,label) in enumerate([("revenue","Revenue"),("net_profit","Net Profit"),("gross_margin","Gross Margin"),
        ("net_margin","Net Margin"),("ebitda","EBITDA"),("operating_cashflow","Operating Cash Flow"),
        ("current_ratio","Current Ratio"),("debt_to_equity","Debt/Equity"),("working_capital","Working Capital"),("total_debt","Total Debt")]):
        item=kpis.get(key,{}); rf=fl(MN) if idx%2==0 else fl(DN); rh(ws2,r,22)
        c=ws2.cell(r,2); c.value=label; c.font=bf(10,b=True,c="F0F4FF"); c.fill=rf; c.alignment=la(False); c.border=tb()
        c=ws2.cell(r,3); c.value=item.get("value","N/A"); c.font=Font(name="Arial",size=11,bold=True,color=AB); c.fill=rf; c.alignment=ca(); c.border=tb()
        c=ws2.cell(r,4); c.value=item.get("note",""); c.font=bf(9,c="8B9BC8"); c.fill=rf; c.alignment=la(); c.border=tb(); r+=1

    buf=io.BytesIO(); wb.save(buf); buf.seek(0); return buf.getvalue()

def build_docx(data):
    doc = DocxDocument()
    for section in doc.sections:
        section.top_margin=Inches(1); section.bottom_margin=Inches(1)
        section.left_margin=Inches(1.2); section.right_margin=Inches(1.2)

    def add_heading(text, level=1, colour=None):
        p = doc.add_paragraph()
        p.paragraph_format.space_before=Pt(14); p.paragraph_format.space_after=Pt(4)
        run = p.add_run(text)
        run.bold=True; run.font.name="Arial"
        run.font.size=Pt(16 if level==1 else 13 if level==2 else 11)
        if colour: run.font.color.rgb=RGBColor(*colour)
        return p

    def add_body(text, italic=False, colour=None):
        p = doc.add_paragraph()
        p.paragraph_format.space_after=Pt(4)
        run = p.add_run(text)
        run.font.name="Arial"; run.font.size=Pt(10); run.italic=italic
        if colour: run.font.color.rgb=RGBColor(*colour)
        return p

    def add_bullet(text):
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(text)
        run.font.name="Arial"; run.font.size=Pt(10)

    def add_divider():
        p = doc.add_paragraph()
        p.paragraph_format.space_before=Pt(4); p.paragraph_format.space_after=Pt(4)
        run = p.add_run("─"*60)
        run.font.color.rgb=RGBColor(42,52,80); run.font.size=Pt(8)

    lbl=data.get("health_label","Moderate"); score=data.get("health_score",5)
    hcolour={"Strong":(0,212,170),"Moderate":(245,166,35),"Weak":(255,92,106)}.get(lbl,(245,166,35))

    title=doc.add_paragraph(); title.alignment=WD_ALIGN_PARAGRAPH.CENTER
    tr=title.add_run("FINANCIAL STATEMENT ANALYSIS")
    tr.bold=True; tr.font.name="Arial"; tr.font.size=Pt(20)

    sub=doc.add_paragraph(); sub.alignment=WD_ALIGN_PARAGRAPH.CENTER
    sr=sub.add_run("DiligenceAI — AI-Powered Financial Analysis")
    sr.font.name="Arial"; sr.font.size=Pt(11); sr.font.color.rgb=RGBColor(139,155,200)

    add_divider()
    doc.add_paragraph()
    cp=doc.add_paragraph()
    cr_=cp.add_run(f"{data.get('company_name','Unknown Company')}  ·  {data.get('period','')}")
    cr_.bold=True; cr_.font.name="Arial"; cr_.font.size=Pt(13)
    hp=doc.add_paragraph()
    hr_=hp.add_run(f"Financial Health: {lbl}   |   Score: {score} / 10")
    hr_.bold=True; hr_.font.name="Arial"; hr_.font.size=Pt(12); hr_.font.color.rgb=RGBColor(*hcolour)
    add_divider()

    add_heading("Executive Summary",2,(79,142,247))
    add_body(data.get("health_summary",""))
    add_heading("Investor View",2,(79,142,247))
    add_body(data.get("investor_view",""),italic=True)
    add_divider()

    add_heading("Key Financial Metrics",2,(79,142,247))
    kpi_labels=[("revenue","Revenue"),("net_profit","Net Profit"),("gross_margin","Gross Margin"),
                ("net_margin","Net Margin"),("ebitda","EBITDA"),("operating_cashflow","Operating Cash Flow"),
                ("current_ratio","Current Ratio"),("debt_to_equity","Debt / Equity"),
                ("working_capital","Working Capital"),("total_debt","Total Debt")]
    kpis=data.get("kpis",{})
    table=doc.add_table(rows=1,cols=3); table.style="Table Grid"
    hdr=table.rows[0].cells
    for i,h in enumerate(["Metric","Value","Commentary"]):
        hdr[i].text=h; run=hdr[i].paragraphs[0].runs[0]
        run.bold=True; run.font.name="Arial"; run.font.size=Pt(10)
    for key,label in kpi_labels:
        item=kpis.get(key,{}); row=table.add_row().cells
        row[0].text=label; row[1].text=item.get("value","N/A"); row[2].text=item.get("note","")
        for cell in row:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.name="Arial"; run.font.size=Pt(10)
    add_divider()

    for sk,sl in [("profitability","Profitability"),("cash_health","Cash Health"),
                  ("working_capital_analysis","Working Capital"),("balance_sheet","Balance Sheet")]:
        sec=data.get(sk,{}); add_heading(sl,2,(79,142,247))
        add_body(sec.get("headline",""),italic=True,colour=(139,155,200))
        for pt in sec.get("points",[]): add_bullet(pt)
    add_divider()

    add_heading("Key Risks & Concerns",2,(255,92,106))
    for risk in data.get("risks",[]):
        rp=doc.add_paragraph(); rr=rp.add_run(risk.get("title",""))
        rr.bold=True; rr.font.name="Arial"; rr.font.size=Pt(10); rr.font.color.rgb=RGBColor(255,92,106)
        add_body(f"Issue: {risk.get('detail','')}"); add_body(f"Suggested Action: {risk.get('fix','')}",colour=(0,212,170))

    add_heading("Positive Signals",2,(0,212,170))
    for pos in data.get("positives",[]):
        pp=doc.add_paragraph(); pr=pp.add_run(pos.get("title",""))
        pr.bold=True; pr.font.name="Arial"; pr.font.size=Pt(10); pr.font.color.rgb=RGBColor(0,212,170)
        add_body(pos.get("detail",""))

    add_heading("Recommendations",2,(79,142,247))
    for i,rec in enumerate(data.get("recommendations",[]),1):
        rp=doc.add_paragraph(); rr=rp.add_run(f"{i}. {rec.get('action','')}")
        rr.bold=True; rr.font.name="Arial"; rr.font.size=Pt(10); rr.font.color.rgb=RGBColor(79,142,247)
        add_body(rec.get("rationale",""),colour=(139,155,200))

    add_divider()
    fn=doc.add_paragraph(); fn.alignment=WD_ALIGN_PARAGRAPH.CENTER
    fr_=fn.add_run("DiligenceAI  ·  For informational purposes only — not financial advice.")
    fr_.font.name="Arial"; fr_.font.size=Pt(8); fr_.font.color.rgb=RGBColor(74,85,120)

    buf=io.BytesIO(); doc.save(buf); buf.seek(0); return buf.getvalue()

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS RENDER HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def render_banner(data):
    label=data.get("health_label","Moderate"); score=data.get("health_score",5)
    summary=data.get("health_summary",""); company=data.get("company_name","")
    period=data.get("period",""); docs=data.get("documents_detected",[])
    colours={"Strong":("rgba(0,212,170,0.08)","#00D4AA","rgba(0,212,170,0.25)"),
             "Moderate":("rgba(245,166,35,0.08)","#F5A623","rgba(245,166,35,0.25)"),
             "Weak":("rgba(255,92,106,0.08)","#FF5C6A","rgba(255,92,106,0.25)")}
    bg,fg,border=colours.get(label,colours["Moderate"])
    bar_filled=int((score/10)*20)
    bar_parts=[]
    for i in range(20):
        bar_col = fg if i < bar_filled else "rgba(255,255,255,0.08)"
        bar_parts.append("<span style='display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:3px;background:" + bar_col + ";'></span>")
    bar_html = "".join(bar_parts)
    tags="".join(f"<span style='background:rgba(79,142,247,0.1);color:#4F8EF7;border:1px solid rgba(79,142,247,0.25);border-radius:6px;padding:0.15rem 0.6rem;font-size:0.68rem;font-weight:600;margin-right:0.3rem;letter-spacing:0.5px;'>{d}</span>" for d in docs)
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {border};border-radius:16px;padding:2rem 2.2rem;margin-bottom:1.5rem;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;right:0;width:200px;height:200px;
                    background:radial-gradient(circle,{fg}08,transparent 70%);pointer-events:none;"></div>
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem;position:relative;">
            <div>
                <div style="color:#8B9BC8;font-size:0.68rem;font-weight:700;letter-spacing:2px;margin-bottom:0.5rem;">OVERALL FINANCIAL HEALTH</div>
                <div style="font-size:2.2rem;font-weight:800;color:{fg};line-height:1;letter-spacing:-0.5px;margin-bottom:0.4rem;">{label}</div>
                <div style="color:#8B9BC8;font-size:0.85rem;margin-bottom:0.6rem;">{company}&nbsp;&nbsp;·&nbsp;&nbsp;{period}</div>
                <div>{tags}</div>
            </div>
            <div style="text-align:right;">
                <div style="color:#8B9BC8;font-size:0.68rem;font-weight:700;letter-spacing:2px;margin-bottom:0.3rem;">HEALTH SCORE</div>
                <div style="font-size:3rem;font-weight:900;color:{fg};line-height:1;letter-spacing:-1px;">{score}<span style="font-size:1.2rem;color:#4A5578;font-weight:400;">/10</span></div>
                <div style="margin-top:0.5rem;">{bar_html}</div>
            </div>
        </div>
        <div style="margin-top:1.2rem;padding-top:1.2rem;border-top:1px solid {border};color:#C8D0E8;font-size:0.93rem;line-height:1.7;">{summary}</div>
    </div>""", unsafe_allow_html=True)

def render_kpis(kpis):
    section_label("KEY FINANCIAL METRICS")
    order=[("revenue","Revenue"),("net_profit","Net Profit"),("gross_margin","Gross Margin"),("net_margin","Net Margin"),("ebitda","EBITDA"),
           ("operating_cashflow","Operating Cash Flow"),("current_ratio","Current Ratio"),("debt_to_equity","Debt / Equity"),("working_capital","Working Capital"),("total_debt","Total Debt")]
    for rs in range(0,len(order),5):
        chunk=order[rs:rs+5]; cols=st.columns(len(chunk))
        for col,(key,label) in zip(cols,chunk):
            item=kpis.get(key,{}); value=item.get("value","N/A"); note=item.get("note","")
            dc="inverse" if any(w in note.lower() for w in ["pressure","decline","weak","low","risk"]) else "normal"
            with col: st.metric(label=label,value=value,delta=note if note else None,delta_color=dc)
        st.markdown("<div style='margin-bottom:0.5rem'></div>",unsafe_allow_html=True)

def render_card(title, section, accent="#4F8EF7"):
    headline=section.get("headline",""); points=section.get("points",[])
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0F1620,#111827);border:1px solid rgba(255,255,255,0.07);
                border-radius:14px;padding:1.4rem 1.6rem;margin-bottom:0.8rem;
                border-top:2px solid {accent}22;transition:border-color 0.2s;">
        <div style="color:#F0F4FF;font-size:0.82rem;font-weight:700;letter-spacing:1px;
                    text-transform:uppercase;margin-bottom:0.6rem;">{title}</div>
        <div style="color:#8B9BC8;font-size:0.85rem;line-height:1.55;
                    border-left:2px solid {accent};padding-left:0.8rem;font-style:italic;margin-bottom:0.8rem;">{headline}</div>
    </div>""", unsafe_allow_html=True)
    for pt in points:
        st.markdown(f"<div style='color:#C8D0E8;font-size:0.84rem;padding:0.3rem 0 0.3rem 1.1rem;"
                    f"border-left:2px solid rgba(255,255,255,0.06);margin-bottom:0.3rem;'>{pt}</div>",
                    unsafe_allow_html=True)
    st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: LOGIN
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.page == "login":
    _, lc, _ = st.columns([1,1.5,1])
    with lc:
        st.markdown("""
        <div style="text-align:center;padding:1rem 0 2rem;">
            <div style="display:inline-flex;align-items:center;justify-content:center;
                        width:52px;height:52px;background:linear-gradient(135deg,#4F8EF7,#00D4AA);
                        border-radius:14px;margin-bottom:1rem;">
                <span style="color:#080C14;font-weight:900;font-size:1.4rem;">D</span>
            </div>
            <h2 style="color:#F0F4FF;font-weight:700;margin:0 0 0.3rem;">Welcome back</h2>
            <p style="color:#8B9BC8;font-size:0.9rem;margin:0;">Log in to access your reports and downloads.</p>
        </div>""", unsafe_allow_html=True)

        email    = st.text_input("Email address", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Log In", key="login_submit", use_container_width=True):
            if email and password:
                st.session_state.logged_in=True; st.session_state.user_email=email
                st.session_state.is_pro="pro" in email.lower()
                st.session_state.page="analyser"; st.rerun()
            else:
                st.error("Please enter your email and password.")
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Create an account instead", key="go_signup", use_container_width=True):
            st.session_state.page="signup"; st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: SIGN UP
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "signup":
    _, sc, _ = st.columns([1,1.5,1])
    with sc:
        st.markdown("""
        <div style="text-align:center;padding:1rem 0 2rem;">
            <div style="display:inline-flex;align-items:center;justify-content:center;
                        width:52px;height:52px;background:linear-gradient(135deg,#4F8EF7,#00D4AA);
                        border-radius:14px;margin-bottom:1rem;">
                <span style="color:#080C14;font-weight:900;font-size:1.4rem;">D</span>
            </div>
            <h2 style="color:#F0F4FF;font-weight:700;margin:0 0 0.3rem;">Create your account</h2>
            <p style="color:#8B9BC8;font-size:0.9rem;margin:0;">Sign up to download reports and access Pro features.</p>
        </div>""", unsafe_allow_html=True)

        email    = st.text_input("Email address", placeholder="you@example.com", key="su_email")
        password = st.text_input("Password", type="password", placeholder="Choose a password", key="su_pw")
        confirm  = st.text_input("Confirm password", type="password", placeholder="Repeat password", key="su_cp")
        plan     = st.radio("Choose your plan", ["Free — 5 analyses/month", "Pro — $10/month (unlimited)"], key="signup_plan")
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        if st.button("Create Account", key="signup_submit", use_container_width=True):
            if not email or not password:
                st.error("Please fill in all fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                st.session_state.logged_in=True; st.session_state.user_email=email
                st.session_state.is_pro="Pro" in plan
                st.session_state.page="analyser"; st.rerun()

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Already have an account? Log in", key="go_login", use_container_width=True):
            st.session_state.page="login"; st.rerun()

        if "Pro" in plan:
            st.markdown("""
            <div style="background:rgba(79,142,247,0.08);border:1px solid rgba(79,142,247,0.25);
                        border-radius:10px;padding:1rem;margin-top:1rem;text-align:center;">
                <div style="color:#4F8EF7;font-size:0.85rem;font-weight:600;margin-bottom:0.25rem;">Pro Plan — $10/month</div>
                <div style="color:#8B9BC8;font-size:0.82rem;">Payments coming soon. Your Pro access will be activated at launch.</div>
            </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: ANALYSER
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "analyser":

    # Hero
    st.markdown("""
    <div style="text-align:center;padding:2.5rem 1rem 2rem;position:relative;">
        <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);
                    width:600px;height:200px;
                    background:radial-gradient(ellipse,rgba(79,142,247,0.12) 0%,transparent 70%);
                    pointer-events:none;"></div>
        <div style="position:relative;">
            <div style="display:inline-block;margin-bottom:1rem;">
                <span style="background:linear-gradient(135deg,rgba(79,142,247,0.15),rgba(0,212,170,0.15));
                             color:#4F8EF7;border:1px solid rgba(79,142,247,0.3);border-radius:20px;
                             padding:0.3rem 1rem;font-size:0.72rem;font-weight:700;letter-spacing:1.5px;">
                    AI-POWERED · INSTITUTIONAL GRADE · FREE TO START
                </span>
            </div>
            <h1 style="font-size:2.8rem;font-weight:900;line-height:1.1;letter-spacing:-1px;margin:0 0 1rem;">
                <span style="color:#F0F4FF;">Financial Analysis</span><br>
                <span style="background:linear-gradient(135deg,#4F8EF7,#00D4AA);
                             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                             background-clip:text;">in seconds, not hours.</span>
            </h1>
            <p style="color:#8B9BC8;font-size:1.05rem;max-width:560px;margin:0 auto;line-height:1.7;">
                Upload your Income Statement, Balance Sheet, and Cash Flow Statement.
                Get a complete forensic analysis — the same quality a private equity firm would produce.
            </p>
        </div>
    </div>""", unsafe_allow_html=True)

    if st.session_state.logged_in:
        plan_badge = "PRO PLAN" if st.session_state.is_pro else "FREE PLAN"
        badge_col  = "#00D4AA" if st.session_state.is_pro else "#8B9BC8"
        st.markdown(f"<div style='text-align:center;margin-bottom:1rem;'>"
                    f"<span style='background:rgba(0,212,170,0.1);color:{badge_col};"
                    f"border:1px solid {badge_col}33;font-size:0.68rem;font-weight:700;"
                    f"letter-spacing:1.5px;padding:0.2rem 0.8rem;border-radius:20px;'>{plan_badge}</span></div>",
                    unsafe_allow_html=True)

    # API Key
    api_key = os.getenv("GROQ_API_KEY","")
    if not api_key:
        with st.expander("Enter Groq API Key  —  free at console.groq.com"):
            api_key = st.text_input("Key", type="password", placeholder="gsk_...", label_visibility="collapsed")
            st.caption("Get your free key at [console.groq.com](https://console.groq.com) → API Keys → Create Key")
        if not api_key:
            st.info("Enter your Groq API key above to get started.")

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

    # Upload area
    cl, cr = st.columns(2, gap="large")
    with cl:
        st.markdown("""
        <div style="margin-bottom:0.6rem;">
            <span style="color:#F0F4FF;font-size:0.9rem;font-weight:600;">Upload Financial Statements</span>
            <span style="color:#4A5578;font-size:0.8rem;"> — PDF, CSV or TXT</span>
        </div>""", unsafe_allow_html=True)
        st.caption("Upload all three statements at once for the best results")
        uploaded_files = st.file_uploader("files", type=["pdf","csv","txt"], accept_multiple_files=True, label_visibility="collapsed")
        if uploaded_files:
            for f in uploaded_files:
                kb=len(f.getvalue())/1024
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:0.5rem;padding:0.35rem 0.6rem;
                            background:rgba(79,142,247,0.06);border:1px solid rgba(79,142,247,0.15);
                            border-radius:6px;margin-top:0.3rem;">
                    <span style="color:#4F8EF7;font-size:0.75rem;">PDF</span>
                    <span style="color:#C8D0E8;font-size:0.82rem;">{f.name}</span>
                    <span style="color:#4A5578;font-size:0.75rem;margin-left:auto;">{kb:.1f} KB</span>
                </div>""", unsafe_allow_html=True)

    with cr:
        st.markdown("""
        <div style="margin-bottom:0.6rem;">
            <span style="color:#F0F4FF;font-size:0.9rem;font-weight:600;">Or Paste Financial Data</span>
            <span style="color:#4A5578;font-size:0.8rem;"> — any format</span>
        </div>""", unsafe_allow_html=True)
        st.caption("Paste raw text, CSV rows, or numbers directly into the box")
        pasted = st.text_area("paste", height=155, placeholder="Revenue: $10.5M\nNet Profit: $1.8M\nTotal Assets: $28M\n...", label_visibility="collapsed")

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)
    _, bc, _ = st.columns([1,2,1])
    with bc:
        go = st.button("Analyse Financial Statements", key="analyse_btn", use_container_width=True)

    # Stats row
    st.markdown("""
    <div style="display:flex;justify-content:center;gap:3rem;padding:1.2rem 0;margin-bottom:0.5rem;">
        <div style="text-align:center;">
            <div style="color:#F0F4FF;font-size:1.1rem;font-weight:700;">30s</div>
            <div style="color:#4A5578;font-size:0.72rem;letter-spacing:0.5px;">AVERAGE ANALYSIS TIME</div>
        </div>
        <div style="text-align:center;">
            <div style="color:#F0F4FF;font-size:1.1rem;font-weight:700;">10+</div>
            <div style="color:#4A5578;font-size:0.72rem;letter-spacing:0.5px;">KEY METRICS EXTRACTED</div>
        </div>
        <div style="text-align:center;">
            <div style="color:#F0F4FF;font-size:1.1rem;font-weight:700;">3</div>
            <div style="color:#4A5578;font-size:0.72rem;letter-spacing:0.5px;">STATEMENTS CROSS-REFERENCED</div>
        </div>
        <div style="text-align:center;">
            <div style="color:#F0F4FF;font-size:1.1rem;font-weight:700;">Free</div>
            <div style="color:#4A5578;font-size:0.72rem;letter-spacing:0.5px;">TO GET STARTED</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # Run analysis
    if go:
        if not api_key:
            st.error("Please enter your Groq API key."); st.stop()
        parts=[]
        if uploaded_files:
            for uf in uploaded_files:
                uf.seek(0); parts.append(f"=== DOCUMENT: {uf.name} ===\n{extract_file(uf)}")
        if pasted.strip(): parts.append(f"=== PASTED DATA ===\n{pasted.strip()}")
        if not parts: st.warning("Please upload at least one file or paste financial data."); st.stop()

        with st.spinner(f"Analysing {len(parts)} document(s) with DiligenceAI..."):
            try: data, raw = call_groq("\n\n".join(parts), api_key)
            except Exception as e:
                err=str(e).lower()
                if "401" in err or "invalid api key" in err: st.error("Invalid Groq API key — please check it.")
                elif "429" in err or "rate limit" in err:   st.error("Rate limit reached — please wait and retry.")
                else: st.error(f"API error: {e}")
                st.stop()

        if not data: st.warning("Could not parse output."); st.text(raw); st.stop()

        st.session_state.analysis_data=data

        st.markdown("""
        <div style="background:rgba(0,212,170,0.08);border:1px solid rgba(0,212,170,0.25);
                    border-radius:10px;padding:0.8rem 1.2rem;margin:1rem 0;display:flex;align-items:center;gap:0.7rem;">
            <span style="color:#00D4AA;font-size:1rem;">✓</span>
            <span style="color:#00D4AA;font-size:0.9rem;font-weight:600;">Analysis complete</span>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)
        render_banner(data)
        render_kpis(data.get("kpis",{}))
        st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

        section_label("PERFORMANCE SUMMARY")
        l, r_col = st.columns(2, gap="large")
        with l:
            render_card("Profitability",   data.get("profitability",{}), "#4F8EF7")
            render_card("Cash Health",     data.get("cash_health",{}),   "#00D4AA")
        with r_col:
            render_card("Working Capital", data.get("working_capital_analysis",{}), "#9B6DFF")
            render_card("Balance Sheet",   data.get("balance_sheet",{}), "#F5A623")
        st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

        section_label("INVESTOR VIEW")
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,rgba(79,142,247,0.06),rgba(155,109,255,0.06));
                    border:1px solid rgba(79,142,247,0.2);border-radius:14px;
                    padding:1.6rem 2rem;color:#C8D0E8;font-size:0.97rem;line-height:1.75;
                    border-left:3px solid #4F8EF7;">
            {data.get("investor_view","")}
        </div>""", unsafe_allow_html=True)
        st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

        rc_col, pc_col = st.columns(2, gap="large")
        with rc_col:
            section_label("KEY RISKS & CONCERNS", "#FF5C6A")
            for risk in data.get("risks",[]):
                with st.expander(risk.get("title","Risk")):
                    st.markdown(f"**Issue:** {risk.get('detail','')}")
                    st.markdown(f"**Suggested Action:** {risk.get('fix','')}")
        with pc_col:
            section_label("POSITIVE SIGNALS", "#00D4AA")
            for pos in data.get("positives",[]):
                st.markdown(f"""
                <div style="background:rgba(0,212,170,0.06);border:1px solid rgba(0,212,170,0.2);
                            border-radius:10px;padding:0.9rem 1.1rem;margin-bottom:0.6rem;">
                    <div style="color:#00D4AA;font-weight:600;font-size:0.87rem;margin-bottom:0.3rem;">{pos.get('title','')}</div>
                    <div style="color:#8B9BC8;font-size:0.83rem;">{pos.get('detail','')}</div>
                </div>""", unsafe_allow_html=True)
        st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

        section_label("RECOMMENDATIONS")
        for i,rec in enumerate(data.get("recommendations",[]),1):
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#0F1620,#111827);
                        border:1px solid rgba(255,255,255,0.07);border-left:3px solid #4F8EF7;
                        border-radius:0 12px 12px 0;padding:1rem 1.4rem;margin-bottom:0.7rem;">
                <div style="color:#4F8EF7;font-weight:700;font-size:0.9rem;margin-bottom:0.3rem;">
                    {i}.&nbsp; {rec.get('action','')}
                </div>
                <div style="color:#8B9BC8;font-size:0.84rem;line-height:1.55;">{rec.get('rationale','')}</div>
            </div>""", unsafe_allow_html=True)
        st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

        # Downloads
        section_label("DOWNLOAD REPORT")
        if not st.session_state.logged_in:
            st.markdown("""
            <div style="background:linear-gradient(135deg,rgba(79,142,247,0.08),rgba(0,212,170,0.05));
                        border:1px solid rgba(79,142,247,0.2);border-radius:14px;
                        padding:1.5rem 2rem;text-align:center;">
                <div style="color:#F0F4FF;font-size:1rem;font-weight:700;margin-bottom:0.4rem;">
                    Log in to download your report</div>
                <div style="color:#8B9BC8;font-size:0.88rem;margin-bottom:1rem;">
                    Free accounts download as TXT. Pro accounts get Excel and Word.</div>
            </div>""", unsafe_allow_html=True)
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            lc2, rc2 = st.columns(2)
            with lc2:
                if st.button("Log In to Download", key="dl_login", use_container_width=True):
                    st.session_state.page="login"; st.rerun()
            with rc2:
                if st.button("Create Free Account", key="dl_signup", use_container_width=True):
                    st.session_state.page="signup"; st.rerun()
        else:
            slug=re.sub(r"[^a-z0-9]","_",data.get("company_name","report").lower())
            d1,d2,d3=st.columns(3)
            with d1:
                st.download_button("Download Report (.txt)", build_txt(data), f"{slug}_analysis.txt","text/plain",use_container_width=True)
            with d2:
                if st.session_state.is_pro:
                    st.download_button("Download Report (.xlsx)", build_excel(data), f"{slug}_analysis.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
                else:
                    st.markdown("<div style='background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:0.55rem;text-align:center;color:#4A5578;font-size:0.82rem;'>Excel — Pro only</div>", unsafe_allow_html=True)
                    if st.button("Upgrade to Pro", key="up_excel", use_container_width=True):
                        st.session_state.page="pricing"; st.rerun()
            with d3:
                if st.session_state.is_pro:
                    st.download_button("Download Report (.docx)", build_docx(data), f"{slug}_analysis.docx",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)
                else:
                    st.markdown("<div style='background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:0.55rem;text-align:center;color:#4A5578;font-size:0.82rem;'>Word Doc — Pro only</div>", unsafe_allow_html=True)
                    if st.button("Upgrade to Pro", key="up_word", use_container_width=True):
                        st.session_state.page="pricing"; st.rerun()

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#4A5578;font-size:0.76rem;'>DiligenceAI &nbsp;·&nbsp; Powered by Groq (LLaMA 3.3 70B) &nbsp;·&nbsp; For informational purposes only — not financial advice.</p>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: FEATURES
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "features":
    st.markdown("""
    <div style="text-align:center;padding:2.5rem 1rem 2rem;position:relative;">
        <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);width:500px;height:160px;
                    background:radial-gradient(ellipse,rgba(155,109,255,0.1),transparent 70%);pointer-events:none;"></div>
        <div style="position:relative;">
            <div style="display:inline-block;margin-bottom:1rem;">
                <span style="background:linear-gradient(135deg,rgba(155,109,255,0.15),rgba(79,142,247,0.15));
                             color:#9B6DFF;border:1px solid rgba(155,109,255,0.3);border-radius:20px;
                             padding:0.3rem 1rem;font-size:0.72rem;font-weight:700;letter-spacing:1.5px;">
                    WHAT DILIGENCEAI CAN DO
                </span>
            </div>
            <h1 style="font-size:2.5rem;font-weight:900;line-height:1.1;letter-spacing:-0.8px;margin:0 0 1rem;color:#F0F4FF;">
                Institutional-grade analysis.<br>
                <span style="background:linear-gradient(135deg,#9B6DFF,#4F8EF7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
                Available to everyone.
                </span>
            </h1>
            <p style="color:#8B9BC8;font-size:1rem;max-width:600px;margin:0 auto;line-height:1.7;">
                DiligenceAI reads your financial statements the same way a chartered accountant or private equity analyst would —
                pulling out what actually matters and explaining it in plain language.
            </p>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

    section_label("WHAT IS DILIGENCEAI")
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0F1620,#111827);border:1px solid rgba(255,255,255,0.07);
                border-radius:16px;padding:2rem 2.2rem;margin-bottom:1.5rem;">
        <p style="color:#C8D0E8;font-size:0.97rem;line-height:1.8;margin:0 0 1rem;">
            DiligenceAI is an AI-powered financial analysis tool built for business owners, accountants, investors, and finance
            students who want to understand what is really going on inside a company's numbers. Instead of spending hours
            reading through spreadsheets, you upload your financial statements and get a structured, professional-grade
            analysis in under 30 seconds.
        </p>
        <p style="color:#8B9BC8;font-size:0.93rem;line-height:1.8;margin:0;">
            It works across any industry, any currency, and any company size. Whether you are reviewing your own business,
            assessing a potential investment, or studying financial statements for the first time — DiligenceAI gives you the
            same analysis a seasoned analyst would produce.
        </p>
    </div>""", unsafe_allow_html=True)

    section_label("WHO IS IT FOR")
    c1,c2,c3,c4=st.columns(4,gap="medium")
    for col,(title,desc,colour) in zip([c1,c2,c3,c4],[
        ("Business Owners","Understand your own financials without needing a finance background. Know exactly where your business stands.","#4F8EF7"),
        ("Accountants","Generate structured analysis for clients in seconds. Use it as a starting point or a fast second opinion on accounts.","#00D4AA"),
        ("Investors","Assess any company's financial health before making a decision. Focus on what actually matters.","#9B6DFF"),
        ("Finance Students","See how professional analysis is structured. Upload real statements and learn by doing.","#F5A623"),
    ]):
        with col:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#0F1620,#111827);border:1px solid rgba(255,255,255,0.07);
                        border-radius:12px;padding:1.4rem;margin-bottom:0.8rem;border-top:2px solid {colour}33;">
                <div style="color:{colour};font-size:0.85rem;font-weight:700;margin-bottom:0.5rem;">{title}</div>
                <div style="color:#8B9BC8;font-size:0.83rem;line-height:1.6;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)
    section_label("HOW IT WORKS")
    s1,s2,s3,s4=st.columns(4,gap="medium")
    for col,(num,title,desc) in zip([s1,s2,s3,s4],[
        ("01","Get your statements","Gather your Income Statement, Balance Sheet, and Cash Flow Statement from your accountant or export from Xero, MYOB, or QuickBooks."),
        ("02","Upload the files","Select your files on the Analyser page. PDF, CSV, and TXT are all supported. Upload all three at once."),
        ("03","Click Analyse","DiligenceAI cross-references all documents and builds a unified analysis in 20–30 seconds."),
        ("04","Review and download","Scroll through your dashboard and download the report. Free users get TXT. Pro users get Excel and Word."),
    ]):
        with col:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#0F1620,#111827);border:1px solid rgba(255,255,255,0.07);
                        border-radius:12px;padding:1.4rem;margin-bottom:0.8rem;">
                <div style="background:linear-gradient(135deg,#4F8EF7,#00D4AA);-webkit-background-clip:text;
                            -webkit-text-fill-color:transparent;background-clip:text;
                            font-size:1.8rem;font-weight:900;margin-bottom:0.4rem;">{num}</div>
                <div style="color:#F0F4FF;font-size:0.88rem;font-weight:700;margin-bottom:0.4rem;">{title}</div>
                <div style="color:#8B9BC8;font-size:0.82rem;line-height:1.6;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)
    section_label("WHAT YOU GET IN EVERY ANALYSIS")
    fl_col,fr_col=st.columns(2,gap="large")
    def frow(t,d,c="#4F8EF7"):
        return (f"<div style='padding:1rem 0;border-bottom:1px solid rgba(255,255,255,0.05);'>"
                f"<div style='display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem;'>"
                f"<div style='width:6px;height:6px;border-radius:50%;background:{c};'></div>"
                f"<div style='color:#F0F4FF;font-size:0.88rem;font-weight:600;'>{t}</div></div>"
                f"<div style='color:#8B9BC8;font-size:0.83rem;line-height:1.55;padding-left:1rem;'>{d}</div></div>")
    with fl_col:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0F1620,#111827);border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:1.5rem 1.8rem;">
            {frow("Financial Health Score","Score out of 10 with Strong / Moderate / Weak rating and a plain-English executive summary.","#4F8EF7")}
            {frow("10 Key Financial Metrics","Revenue, net profit, margins, EBITDA, operating cash flow, current ratio, debt/equity, working capital, total debt.","#00D4AA")}
            {frow("Profitability Analysis","Is profit real or accounting-driven? Are margins holding up?","#9B6DFF")}
            {frow("Cash Health","Is the business generating cash or reliant on external funding?","#F5A623")}
        </div>""", unsafe_allow_html=True)
    with fr_col:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0F1620,#111827);border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:1.5rem 1.8rem;">
            {frow("Working Capital Analysis","Is cash being tied up in receivables or inventory?","#4F8EF7")}
            {frow("Balance Sheet Review","Debt levels, liquidity, and overall financial risk on the books.","#00D4AA")}
            {frow("Investor View","Blunt private-equity style interpretation of the business.","#9B6DFF")}
            {frow("Risks, Positives & Recommendations","Top 3 risks with fixes, positives, and 3 actionable recommendations.","#F5A623")}
        </div>""", unsafe_allow_html=True)

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#4A5578;font-size:0.76rem;'>DiligenceAI &nbsp;·&nbsp; For informational purposes only — not financial advice.</p>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: PRICING
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.page == "pricing":
    st.markdown("""
    <div style="text-align:center;padding:2.5rem 1rem 2rem;position:relative;">
        <div style="position:absolute;top:0;left:50%;transform:translateX(-50%);width:500px;height:160px;
                    background:radial-gradient(ellipse,rgba(0,212,170,0.1),transparent 70%);pointer-events:none;"></div>
        <div style="position:relative;">
            <div style="display:inline-block;margin-bottom:1rem;">
                <span style="background:linear-gradient(135deg,rgba(0,212,170,0.15),rgba(79,142,247,0.15));
                             color:#00D4AA;border:1px solid rgba(0,212,170,0.3);border-radius:20px;
                             padding:0.3rem 1rem;font-size:0.72rem;font-weight:700;letter-spacing:1.5px;">
                    SIMPLE, TRANSPARENT PRICING
                </span>
            </div>
            <h1 style="font-size:2.5rem;font-weight:900;color:#F0F4FF;margin:0 0 0.8rem;letter-spacing:-0.8px;">
                Start free. Scale when ready.</h1>
            <p style="color:#8B9BC8;font-size:1rem;max-width:440px;margin:0 auto;">
                No hidden fees. No lock-in contracts. Upgrade or cancel any time.
            </p>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

    _,cf,cp,_=st.columns([1,2,2,1],gap="large")

    with cf:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0F1620,#111827);border:1px solid rgba(255,255,255,0.07);
                    border-radius:18px;padding:2rem 1.8rem;">
            <div style="color:#8B9BC8;font-size:0.68rem;font-weight:700;letter-spacing:2px;margin-bottom:0.7rem;">FREE PLAN</div>
            <div style="margin-bottom:0.4rem;">
                <span style="font-size:3rem;font-weight:900;color:#F0F4FF;letter-spacing:-1px;">$0</span>
            </div>
            <div style="color:#4A5578;font-size:0.87rem;margin-bottom:1.8rem;">No credit card required</div>
            <div style="margin-bottom:2rem;">
                {tick("5 analyses per month")}
                {tick("Upload up to 2 documents")}
                {tick("Full dashboard output")}
                {tick("Download as TXT")}
                {cross("Excel download")}
                {cross("Word document download")}
                {cross("Unlimited analyses")}
            </div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Get Started Free", key="cta_free", use_container_width=True):
            st.session_state.page="signup"; st.rerun()

    with cp:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,rgba(79,142,247,0.08),rgba(0,212,170,0.05));
                    border:2px solid rgba(79,142,247,0.35);border-radius:18px;padding:2rem 1.8rem;position:relative;">
            <div style="position:absolute;top:-13px;left:50%;transform:translateX(-50%);
                        background:linear-gradient(135deg,#4F8EF7,#00D4AA);color:#080C14;
                        font-size:0.68rem;font-weight:800;letter-spacing:1.5px;
                        padding:0.25rem 1rem;border-radius:20px;white-space:nowrap;">
                BEST VALUE
            </div>
            <div style="color:#4F8EF7;font-size:0.68rem;font-weight:700;letter-spacing:2px;margin-bottom:0.7rem;">PRO PLAN</div>
            <div style="margin-bottom:0.2rem;">
                <span style="color:#4A5578;font-size:1.2rem;font-weight:500;text-decoration:line-through;margin-right:0.4rem;">$15</span>
                <span style="font-size:3rem;font-weight:900;letter-spacing:-1px;background:linear-gradient(135deg,#4F8EF7,#00D4AA);
                             -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">$10</span>
                <span style="color:#8B9BC8;font-size:0.9rem;"> / month</span>
            </div>
            <div style="display:inline-block;background:rgba(0,212,170,0.12);color:#00D4AA;border:1px solid rgba(0,212,170,0.3);border-radius:6px;padding:0.15rem 0.6rem;font-size:0.72rem;font-weight:700;letter-spacing:0.5px;margin-bottom:0.8rem;">33% OFF — LIMITED TIME</div>
            <div style="color:#4A5578;font-size:0.87rem;margin-bottom:1rem;">Cancel any time. No lock-in.</div>
            <div style="margin-bottom:2rem;">
                {tick("Unlimited analyses")}
                {tick("Upload all 3 statements")}
                {tick("Full dashboard output")}
                {tick("Download as TXT")}
                {tick("Download as Excel (.xlsx)")}
                {tick("Download as Word (.docx)")}
                {tick("Priority processing")}
            </div>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Sign Up for Pro", key="cta_pro", use_container_width=True):
            st.session_state.page="signup"; st.rerun()

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center;padding:0.5rem 0 1.2rem;">
        <h2 style="color:#F0F4FF;font-size:1.4rem;font-weight:700;margin:0 0 0.4rem;">Join the Pro waitlist</h2>
        <p style="color:#8B9BC8;font-size:0.9rem;margin:0;">Payments are coming soon. Leave your email and we will notify you the moment Pro launches.</p>
    </div>""", unsafe_allow_html=True)
    _,wl,_=st.columns([1,2,1])
    with wl:
        email=st.text_input("Email",placeholder="you@example.com",label_visibility="collapsed",key="wl_email")
        if st.button("Notify me when Pro launches",key="wl_btn",use_container_width=True):
            if email and "@" in email: st.success(f"Thanks! We will be in touch at {email} when Pro goes live.")
            else: st.error("Please enter a valid email address.")

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)
    st.markdown("""<div style="text-align:center;padding:0.5rem 0 1.2rem;">
        <div style="color:#4A5578;font-size:0.68rem;font-weight:700;letter-spacing:2px;margin-bottom:0.5rem;">FAQ</div>
        <h2 style="color:#F0F4FF;font-size:1.4rem;font-weight:700;margin:0;">Common questions</h2>
    </div>""", unsafe_allow_html=True)
    _,faq,_=st.columns([1,3,1])
    with faq:
        for q,a in [
            ("Do I need a credit card for the free plan?","No. The free plan requires no payment details at all."),
            ("What counts as one analysis?","Each time you click Analyse, that counts as one. Uploading three statements at once is still a single analysis."),
            ("Can I cancel the Pro plan at any time?","Yes. No lock-in contracts. Cancel at any time and retain access until the end of your billing period."),
            ("Is my financial data kept private?","Documents are processed securely and not stored beyond the current session."),
            ("What currencies are supported?","Any currency in your documents — NZD, AUD, USD, GBP, and others are handled automatically."),
        ]:
            with st.expander(q):
                st.markdown(f"<div style='color:#C8D0E8;font-size:0.9rem;line-height:1.65;'>{a}</div>",unsafe_allow_html=True)

    st.markdown("<div class='dai-divider'></div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#4A5578;font-size:0.76rem;'>DiligenceAI &nbsp;·&nbsp; For informational purposes only — not financial advice.</p>",unsafe_allow_html=True)
