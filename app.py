"""FinSight — Financial Statement Analyser (main page)."""
import streamlit as st
from groq import Groq
import io, os, csv, json, re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

st.set_page_config(
    page_title="FinSight — Financial Statement Analyser",
    page_icon="",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# SHARED STYLES & NAV
# ─────────────────────────────────────────────────────────────────────────────

def inject_styles():
    st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 0 !important; padding-bottom: 3rem; }
    #MainMenu, footer, header { visibility: hidden; }

    .topnav {
        background: #0d1117;
        border-bottom: 1px solid #21262d;
        padding: 0 2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 56px;
        position: sticky;
        top: 0;
        z-index: 999;
    }
    .topnav-brand {
        color: #f0f6fc;
        font-size: 1rem;
        font-weight: 700;
        letter-spacing: -0.3px;
        text-decoration: none;
    }
    .topnav-links { display: flex; gap: 0.25rem; align-items: center; }
    .topnav-links a {
        color: #8b949e;
        font-size: 0.87rem;
        font-weight: 500;
        text-decoration: none;
        padding: 0.35rem 0.85rem;
        border-radius: 6px;
        transition: background 0.15s, color 0.15s;
    }
    .topnav-links a:hover { background: #161b22; color: #f0f6fc; }
    .topnav-links a.active { color: #f0f6fc; background: #161b22; }
    .topnav-cta {
        background: #2e5eaa !important;
        color: #fff !important;
        font-weight: 600 !important;
    }
    .topnav-cta:hover { background: #1a4a8a !important; }

    [data-testid="metric-container"] {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 0.9rem 1rem;
    }
    [data-testid="metric-container"] label {
        color: #8b949e !important;
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #f0f6fc !important;
        font-size: 1.2rem !important;
        font-weight: 700 !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricDelta"] {
        font-size: 0.72rem !important;
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
        transition: background 0.2s;
    }
    div[data-testid="stButton"] > button:hover { background: #1a4a8a; }
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
    [data-testid="stExpander"] {
        background: #161b22;
        border: 1px solid #30363d !important;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }
    hr { border-color: #21262d !important; }
    textarea {
        background: #0d1117 !important;
        border: 1px solid #30363d !important;
        color: #c9d1d9 !important;
        border-radius: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)


def nav_bar(active="analyser"):
    links = {
        "analyser": ("Analyser",  "/"),
        "features": ("Features",  "/1_Features"),
        "pricing":  ("Pricing",   "/2_Pricing"),
    }
    html = ""
    for key, (label, href) in links.items():
        cls = "active" if key == active else ""
        if key == "analyser":
            cls = (cls + " topnav-cta").strip()
        html += f'<a href="{href}" class="{cls}" target="_self">{label}</a>'
    st.markdown(f"""
    <div class="topnav">
        <span class="topnav-brand">FinSight</span>
        <div class="topnav-links">{html}</div>
    </div>
    """, unsafe_allow_html=True)


def section_label(text):
    st.markdown(
        f"<div style='color:#8b949e; font-size:0.72rem; font-weight:700; "
        f"letter-spacing:1.5px; margin-bottom:0.6rem;'>{text}</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# FILE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes):
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


def extract_text_from_csv(file_bytes):
    try:
        content = file_bytes.decode("utf-8", errors="replace")
        return "\n".join(" | ".join(r) for r in csv.reader(io.StringIO(content)))
    except Exception as e:
        return f"[CSV error: {e}]"


def extract_text(uploaded_file):
    name = uploaded_file.name.lower()
    raw  = uploaded_file.read()
    if name.endswith(".pdf"): return extract_text_from_pdf(raw)
    if name.endswith(".csv"): return extract_text_from_csv(raw)
    return raw.decode("utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a highly skilled financial analyst and forensic accountant based in New Zealand.
You will receive one or more financial statements (Income Statement, Balance Sheet, Cash Flow Statement).
Cross-reference all documents together to produce a single unified analysis.
Return ONLY a valid JSON object — no markdown, no extra text.

Schema:
{
  "company_name": "string or 'Unknown Company'",
  "period": "string e.g. 'FY 2023' or 'Not provided'",
  "documents_detected": ["Income Statement", "Balance Sheet", "Cash Flow Statement"],
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
  "profitability":           {"headline": "string", "points": ["string","string","string"]},
  "cash_health":             {"headline": "string", "points": ["string","string","string"]},
  "working_capital_analysis":{"headline": "string", "points": ["string","string","string"]},
  "balance_sheet":           {"headline": "string", "points": ["string","string","string"]},
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
- "Not provided" for missing data. Never invent numbers.
- Format values: "$12.4M", "18.3%", "2.1x".
- Notes: brief trend, max 8 words.
- health_score: 8-10=Strong, 5-7=Moderate, 1-4=Weak.
- Synthesise all documents together, do not analyse in isolation.
- NZ English throughout (analyse, recognise, favour, etc).
- Return ONLY the JSON object.
"""


# ─────────────────────────────────────────────────────────────────────────────
# GROQ API
# ─────────────────────────────────────────────────────────────────────────────

def analyse_financials(financial_text, api_key):
    client = Groq(api_key=api_key)
    if len(financial_text) > 28000:
        financial_text = financial_text[:28000] + "\n\n[Further content truncated]"

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
    raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try: return json.loads(m.group()), raw
            except Exception: pass
        return None, raw


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_excel_report(data):
    wb = Workbook()
    DN = "0D1B2A"; MN = "1B2A3B"; AB = "2E5EAA"; LB = "D6E4F7"
    WH = "FFFFFF"; LG = "F5F7FA"; MG = "C5CDD9"
    GB = "E6F4EA"; GF = "1A6B2E"; RB = "FDE8E8"; RF = "9B1C1C"
    AMB = "FFF3CD"; AMF = "7D5A00"

    lbl = data.get("health_label","Moderate"); sc = data.get("health_score",5)
    hc = {" Strong":GF,"Moderate":AMF,"Weak":RF}.get(lbl,AMF)
    hb = {"Strong":GB,"Moderate":AMB,"Weak":RB}.get(lbl,AMB)

    def hf(sz=11,b=True,c=WH): return Font(name="Arial",size=sz,bold=b,color=c)
    def bf(sz=10,b=False,c="000000"): return Font(name="Arial",size=sz,bold=b,color=c)
    def fl(h): return PatternFill("solid",fgColor=h)
    def tb(sides="all"):
        s=Side(style="thin",color=MG); n=Side(style=None)
        return Border(
            left  =s if "all" in sides or "left"   in sides else n,
            right =s if "all" in sides or "right"  in sides else n,
            top   =s if "all" in sides or "top"    in sides else n,
            bottom=s if "all" in sides or "bottom" in sides else n,
        )
    def ca(): return Alignment(horizontal="center",vertical="center",wrap_text=True)
    def la(w=True): return Alignment(horizontal="left",vertical="center",wrap_text=w)
    def rh(ws,r,h): ws.row_dimensions[r].height=h
    def mw(ws,rng,v,fn,al,fl_=None,br=None):
        ws.merge_cells(rng); c=ws[rng.split(":")[0]]
        c.value=v; c.font=fn; c.alignment=al
        if fl_: c.fill=fl_
        if br:  c.border=br

    # Sheet 1 — Executive Summary
    ws=wb.active; ws.title="Executive Summary"; ws.sheet_view.showGridLines=False
    for i,w in enumerate([2,28,22,22,22,22,2],1):
        ws.column_dimensions[get_column_letter(i)].width=w
    r=1
    for ri in range(r,r+3):
        rh(ws,ri,6 if ri!=r+1 else 36)
        for ci in range(1,8): ws.cell(ri,ci).fill=fl(DN)
    mw(ws,f"B{r+1}:F{r+1}","FINANCIAL STATEMENT ANALYSIS — FINSIGHT",hf(15,True,WH),ca(),fl(DN))
    r+=3
    for ri in range(r,r+4):
        rh(ws,ri,6 if ri in(r,r+3) else 26)
        for ci in range(1,8): ws.cell(ri,ci).fill=fl(MN)
    ws.merge_cells(f"B{r+1}:C{r+1}")
    c=ws[f"B{r+1}"]; c.value=data.get("company_name","Unknown"); c.font=hf(13,True,WH); c.alignment=la(False)
    ws.cell(r+1,4).value=data.get("period",""); ws.cell(r+1,4).font=hf(11,False,MG); ws.cell(r+1,4).alignment=ca()
    for ci,val in enumerate([lbl,f"Score: {sc} / 10"],5):
        c=ws.cell(r+1,ci); c.value=val
        c.font=Font(name="Arial",size=11,bold=True,color=hc)
        c.fill=fl(hb); c.alignment=ca(); c.border=tb()
    r+=4; rh(ws,r,6); r+=1; rh(ws,r,16)
    mw(ws,f"B{r}:F{r}","EXECUTIVE SUMMARY",hf(10,True,WH),la(False),fl(AB)); r+=1
    for line in data.get("health_summary","").split(". "):
        if not line.strip(): continue
        rh(ws,r,30); ws.merge_cells(f"B{r}:F{r}"); c=ws[f"B{r}"]
        c.value=line.strip().rstrip(".")+"."
        c.font=bf(10); c.alignment=la(); c.fill=fl(LG); c.border=tb("bottom"); r+=1
    rh(ws,r,6); r+=1; rh(ws,r,16)
    mw(ws,f"B{r}:F{r}","INVESTOR VIEW",hf(10,True,WH),la(False),fl(AB)); r+=1
    iv=data.get("investor_view",""); rh(ws,r,max(60,len(iv)//4))
    ws.merge_cells(f"B{r}:F{r}"); c=ws[f"B{r}"]
    c.value=iv; c.font=bf(10,bold=True,c="1A1A1A"); c.alignment=la(); c.fill=fl(LB); c.border=tb()

    # Sheet 2 — KPI Metrics
    ws2=wb.create_sheet("KPI Metrics"); ws2.sheet_view.showGridLines=False
    for i,w in enumerate([2,30,20,35,2],1): ws2.column_dimensions[get_column_letter(i)].width=w
    r=1
    for ri in range(r,r+3):
        rh(ws2,ri,6 if ri!=r+1 else 36)
        for ci in range(1,6): ws2.cell(ri,ci).fill=fl(DN)
    mw(ws2,f"B{r+1}:D{r+1}","KEY FINANCIAL METRICS",hf(14,True,WH),ca(),fl(DN)); r+=3
    rh(ws2,r,20)
    for ci,h in enumerate(["Metric","Value","Commentary"],2):
        c=ws2.cell(r,ci); c.value=h; c.font=hf(10,True,WH); c.fill=fl(AB); c.alignment=ca(); c.border=tb()
    r+=1
    kpis=data.get("kpis",{})
    for idx,(key,label) in enumerate([
        ("revenue","Revenue"),("net_profit","Net Profit"),("gross_margin","Gross Margin"),
        ("net_margin","Net Margin"),("ebitda","EBITDA"),("operating_cashflow","Operating Cash Flow"),
        ("current_ratio","Current Ratio"),("debt_to_equity","Debt / Equity"),
        ("working_capital","Working Capital"),("total_debt","Total Debt"),
    ]):
        item=kpis.get(key,{}); rf=fl(WH) if idx%2==0 else fl(LG); rh(ws2,r,22)
        c=ws2.cell(r,2); c.value=label; c.font=bf(10,b=True); c.fill=rf; c.alignment=la(False); c.border=tb()
        c=ws2.cell(r,3); c.value=item.get("value","Not provided")
        c.font=Font(name="Arial",size=11,bold=True,color=AB); c.fill=rf; c.alignment=ca(); c.border=tb()
        c=ws2.cell(r,4); c.value=item.get("note",""); c.font=bf(9,c="444444"); c.fill=rf; c.alignment=la(); c.border=tb()
        r+=1

    # Sheet 3 — Performance Analysis
    ws3=wb.create_sheet("Performance Analysis"); ws3.sheet_view.showGridLines=False
    for i,w in enumerate([2,26,55,2],1): ws3.column_dimensions[get_column_letter(i)].width=w
    r=1
    for ri in range(r,r+3):
        rh(ws3,ri,6 if ri!=r+1 else 36)
        for ci in range(1,5): ws3.cell(ri,ci).fill=fl(DN)
    mw(ws3,f"B{r+1}:C{r+1}","PERFORMANCE ANALYSIS",hf(14,True,WH),ca(),fl(DN)); r+=3
    for sk,sl in [("profitability","Profitability"),("cash_health","Cash Health"),
                  ("working_capital_analysis","Working Capital"),("balance_sheet","Balance Sheet")]:
        sec=data.get(sk,{}); rh(ws3,r,18)
        mw(ws3,f"B{r}:C{r}",sl.upper(),hf(10,True,WH),la(False),fl(AB)); r+=1
        rh(ws3,r,28); ws3.merge_cells(f"B{r}:C{r}"); c=ws3[f"B{r}"]
        c.value=sec.get("headline",""); c.font=bf(10,b=True,c="1A1A1A"); c.fill=fl(LB); c.alignment=la(); c.border=tb(); r+=1
        for i,pt in enumerate(sec.get("points",[])):
            rh(ws3,r,26); rf=fl(WH) if i%2==0 else fl(LG)
            bc=ws3.cell(r,2); bc.value="  ·"; bc.font=bf(12,b=True,c=AB); bc.fill=rf; bc.alignment=ca(); bc.border=tb("left")
            tc=ws3.cell(r,3); tc.value=pt; tc.font=bf(10); tc.fill=rf; tc.alignment=la(); tc.border=tb("right,bottom,top"); r+=1
        rh(ws3,r,8); r+=1

    # Sheet 4 — Risks & Recommendations
    ws4=wb.create_sheet("Risks & Recommendations"); ws4.sheet_view.showGridLines=False
    for i,w in enumerate([2,22,40,40,2],1): ws4.column_dimensions[get_column_letter(i)].width=w
    r=1
    for ri in range(r,r+3):
        rh(ws4,ri,6 if ri!=r+1 else 36)
        for ci in range(1,6): ws4.cell(ri,ci).fill=fl(DN)
    mw(ws4,f"B{r+1}:D{r+1}","RISKS & RECOMMENDATIONS",hf(14,True,WH),ca(),fl(DN)); r+=3
    for sec_data,title,hdrs,bg,fg in [
        (data.get("risks",[]),"KEY RISKS & CONCERNS",["Risk","Detail","Suggested Action"],RB,RF),
        (data.get("positives",[]),"POSITIVE SIGNALS",["Signal","Detail",""],GB,GF),
        (data.get("recommendations",[]),"RECOMMENDATIONS",["Action","Rationale",""],LB,AB),
    ]:
        rh(ws4,r,18); mw(ws4,f"B{r}:D{r}",title,hf(10,True,WH),la(False),fl(AB)); r+=1
        rh(ws4,r,18)
        for ci,h in enumerate(hdrs,2):
            c=ws4.cell(r,ci); c.value=h; c.font=hf(9,True,"1A1A1A"); c.fill=fl(bg); c.alignment=ca(); c.border=tb()
        r+=1
        for idx,item in enumerate(sec_data):
            rh(ws4,r,40); rf=fl(WH) if idx%2==0 else fl(LG)
            keys=(["title","detail","fix"] if "fix" in item else ["title","detail",""] if "detail" in item else ["action","rationale",""])
            for ci,k in enumerate(keys,2):
                val=item.get(k,"") if k else ""
                c=ws4.cell(r,ci); c.value=val
                c.font=bf(10,b=(ci==2),c=fg if ci==2 else "000000")
                c.fill=rf; c.alignment=la(); c.border=tb(); r+=1
        rh(ws4,r,10); r+=1

    # Sheet 5 — Scorecard
    ws5=wb.create_sheet("Health Scorecard"); ws5.sheet_view.showGridLines=False
    for i,w in enumerate([2,30,20,2],1): ws5.column_dimensions[get_column_letter(i)].width=w
    r=1
    for ri in range(r,r+3):
        rh(ws5,ri,6 if ri!=r+1 else 40)
        for ci in range(1,5): ws5.cell(ri,ci).fill=fl(DN)
    mw(ws5,f"B{r+1}:C{r+1}","HEALTH SCORECARD",hf(16,True,WH),ca(),fl(DN)); r+=3
    rh(ws5,r,50)
    ws5.merge_cells(f"B{r}:B{r}"); c=ws5[f"B{r}"]
    c.value=f"Overall Health: {lbl}"; c.font=Font(name="Arial",size=16,bold=True,color=hc)
    c.fill=fl(hb); c.alignment=ca(); c.border=tb()
    ws5.merge_cells(f"C{r}:C{r}"); c=ws5[f"C{r}"]
    c.value=f"{sc} / 10"; c.font=Font(name="Arial",size=20,bold=True,color=hc)
    c.fill=fl(hb); c.alignment=ca(); c.border=tb(); r+=1
    rh(ws5,r,24); ws5.merge_cells(f"B{r}:C{r}"); c=ws5[f"B{r}"]
    c.value="█"*sc+"░"*(10-sc); c.font=Font(name="Courier New",size=16,bold=True,color=hc)
    c.alignment=ca(); c.fill=fl(MG); r+=2
    rh(ws5,r,18)
    for ci,h in enumerate(["Analysis Area","Assessment"],2):
        c=ws5.cell(r,ci); c.value=h; c.font=hf(10,True,WH); c.fill=fl(AB); c.alignment=ca(); c.border=tb()
    r+=1
    for idx,(sk,sl) in enumerate([("profitability","Profitability"),("cash_health","Cash Health"),
                                   ("working_capital_analysis","Working Capital"),("balance_sheet","Balance Sheet")]):
        rh(ws5,r,32); rf=fl(WH) if idx%2==0 else fl(LG)
        c=ws5.cell(r,2); c.value=sl; c.font=bf(10,b=True); c.fill=rf; c.alignment=la(False); c.border=tb()
        c=ws5.cell(r,3); c.value=data.get(sk,{}).get("headline",""); c.font=bf(10); c.fill=rf; c.alignment=la(); c.border=tb(); r+=1
    rh(ws5,r+1,18); ws5.merge_cells(f"B{r+1}:C{r+1}"); c=ws5[f"B{r+1}"]
    c.value="Note: AI-generated analysis for informational purposes only. Not financial advice."
    c.font=Font(name="Arial",size=8,italic=True,color="888888"); c.alignment=ca()

    buf=io.BytesIO(); wb.save(buf); buf.seek(0); return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def health_palette(label):
    if label=="Strong":   return "#0d2818","#3fb950","#238636"
    if label=="Moderate": return "#2d1f00","#d4a017","#9e6a03"
    return "#2d0f0f","#f85149","#b91c1c"


def render_health_banner(data):
    label=data.get("health_label","Moderate"); score=data.get("health_score",5)
    summary=data.get("health_summary",""); company=data.get("company_name","Company")
    period=data.get("period",""); docs=data.get("documents_detected",[])
    bg,fg,border=health_palette(label); bar="█"*score+"░"*(10-score)
    tags="".join(
        f"<span style='background:#21262d;color:#8b949e;border-radius:4px;"
        f"padding:0.1rem 0.5rem;font-size:0.72rem;margin-right:0.3rem;'>{d}</span>"
        for d in docs
    )
    docs_html=f"<div style='margin-top:0.5rem;'>{tags}</div>" if docs else ""
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {border};border-radius:12px;
                padding:1.8rem 2rem;margin-bottom:1.5rem;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem;">
            <div>
                <div style="color:#8b949e;font-size:0.7rem;font-weight:700;letter-spacing:1.5px;margin-bottom:0.4rem;">
                    OVERALL FINANCIAL HEALTH</div>
                <div style="font-size:1.9rem;font-weight:700;color:{fg};line-height:1.1;">{label}</div>
                <div style="color:#8b949e;font-size:0.83rem;margin-top:0.3rem;">
                    {company}&nbsp;&nbsp;·&nbsp;&nbsp;{period}</div>
                {docs_html}
            </div>
            <div style="text-align:right;">
                <div style="color:#8b949e;font-size:0.7rem;font-weight:700;letter-spacing:1.5px;">HEALTH SCORE</div>
                <div style="font-size:2.4rem;font-weight:800;color:{fg};line-height:1.1;">
                    {score}<span style="font-size:1rem;color:#8b949e;font-weight:400;">&thinsp;/ 10</span></div>
                <div style="font-family:monospace;color:{fg};font-size:0.95rem;letter-spacing:2px;margin-top:0.2rem;">{bar}</div>
            </div>
        </div>
        <div style="margin-top:1.1rem;padding-top:1.1rem;border-top:1px solid {border};
                    color:#c9d1d9;font-size:0.93rem;line-height:1.65;">{summary}</div>
    </div>""", unsafe_allow_html=True)


def render_kpis(kpis):
    section_label("KEY FINANCIAL METRICS")
    order=[("revenue","Revenue"),("net_profit","Net Profit"),("gross_margin","Gross Margin"),
           ("net_margin","Net Margin"),("ebitda","EBITDA"),("operating_cashflow","Operating Cash Flow"),
           ("current_ratio","Current Ratio"),("debt_to_equity","Debt / Equity"),
           ("working_capital","Working Capital"),("total_debt","Total Debt")]
    for rs in range(0,len(order),5):
        chunk=order[rs:rs+5]; cols=st.columns(len(chunk))
        for col,(key,label) in zip(cols,chunk):
            item=kpis.get(key,{}); value=item.get("value","N/A"); note=item.get("note","")
            dc="inverse" if any(w in note.lower() for w in ["pressure","decline","high","weak","low"]) else "normal"
            with col: st.metric(label=label,value=value,delta=note if note else None,delta_color=dc)
        st.markdown("<div style='margin-bottom:0.4rem'></div>",unsafe_allow_html=True)


def render_analysis_card(title, section):
    headline=section.get("headline",""); points=section.get("points",[])
    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;
                padding:1.2rem 1.5rem;margin-bottom:0.5rem;">
        <div style="color:#f0f6fc;font-size:0.85rem;font-weight:700;
                    letter-spacing:0.5px;margin-bottom:0.5rem;">{title.upper()}</div>
        <div style="color:#8b949e;font-size:0.82rem;line-height:1.5;
                    border-left:3px solid #2e5eaa;padding-left:0.7rem;font-style:italic;">{headline}</div>
    </div>""", unsafe_allow_html=True)
    for pt in points:
        st.markdown(f"<div style='color:#c9d1d9;font-size:0.84rem;padding:0.25rem 0 0.25rem 1rem;"
                    f"border-left:2px solid #30363d;margin-bottom:0.3rem;'>{pt}</div>", unsafe_allow_html=True)
    st.markdown("")


def render_investor_view(text):
    section_label("INVESTOR VIEW — WHAT IS REALLY GOING ON")
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #4a4a8a;
                border-radius:10px;padding:1.4rem 1.8rem;color:#d0d0f0;
                font-size:0.95rem;line-height:1.7;">{text}</div>""", unsafe_allow_html=True)


def render_risks(risks):
    section_label("KEY RISKS & CONCERNS")
    for risk in risks:
        with st.expander(risk.get("title","Risk")):
            st.markdown(f"**Issue:** {risk.get('detail','')}")
            st.markdown(f"**Suggested Action:** {risk.get('fix','')}")


def render_positives(positives):
    section_label("POSITIVE SIGNALS")
    for pos in positives:
        st.markdown(f"""
        <div style="background:#0d2818;border:1px solid #238636;border-radius:8px;
                    padding:0.9rem 1.1rem;margin-bottom:0.6rem;">
            <div style="color:#3fb950;font-weight:600;font-size:0.87rem;margin-bottom:0.3rem;">{pos.get('title','')}</div>
            <div style="color:#8b949e;font-size:0.82rem;">{pos.get('detail','')}</div>
        </div>""", unsafe_allow_html=True)


def render_recommendations(recs):
    section_label("RECOMMENDATIONS")
    for i,rec in enumerate(recs,1):
        st.markdown(f"""
        <div style="background:#161b22;border-left:4px solid #2e5eaa;
                    border-radius:0 8px 8px 0;padding:0.9rem 1.2rem;margin-bottom:0.7rem;">
            <div style="color:#58a6ff;font-weight:600;font-size:0.9rem;">{i}.&nbsp;{rec.get('action','')}</div>
            <div style="color:#8b949e;font-size:0.83rem;margin-top:0.3rem;">{rec.get('rationale','')}</div>
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────────────────────────────────────

inject_styles()
nav_bar("analyser")

st.markdown("""
<div style="text-align:center;padding:2.5rem 1rem 1.5rem;">
    <div style="display:inline-block;background:rgba(46,94,170,0.15);color:#58a6ff;
                border:1px solid rgba(46,94,170,0.4);border-radius:20px;
                padding:0.25rem 1rem;font-size:0.72rem;font-weight:700;
                letter-spacing:1.5px;margin-bottom:0.9rem;">
        POWERED BY GROQ — FREE TO USE
    </div>
    <h1 style="font-size:2.3rem;font-weight:800;color:#f0f6fc;margin:0 0 0.5rem;letter-spacing:-0.5px;">
        Financial Statement Analyser
    </h1>
    <p style="color:#8b949e;font-size:0.97rem;margin:0;">
        Upload all three statements — Income, Balance Sheet, Cash Flow — for a complete forensic analysis.
    </p>
</div>""", unsafe_allow_html=True)

api_key = os.getenv("GROQ_API_KEY","")
if not api_key:
    with st.expander("Groq API Key  —  free at console.groq.com", expanded=True):
        api_key = st.text_input("Key", type="password", placeholder="gsk_...", label_visibility="collapsed")
        st.caption("Get your free key at [console.groq.com](https://console.groq.com) → API Keys → Create Key")
    if not api_key:
        st.info("Enter your Groq API key above to get started.")

st.divider()

col_l, col_r = st.columns(2, gap="large")
with col_l:
    st.markdown("<div style='color:#f0f6fc;font-size:0.9rem;font-weight:600;margin-bottom:0.4rem;'>"
                "Upload Financial Statements</div>", unsafe_allow_html=True)
    st.caption("PDF, CSV or TXT — upload all three statements at once for the best results")
    uploaded_files = st.file_uploader("files", type=["pdf","csv","txt"],
                                      accept_multiple_files=True, label_visibility="collapsed")
    if uploaded_files:
        for f in uploaded_files:
            kb = len(f.getvalue()) / 1024
            st.markdown(f"<small style='color:#8b949e'>{f.name} — {kb:.1f} KB</small>", unsafe_allow_html=True)

with col_r:
    st.markdown("<div style='color:#f0f6fc;font-size:0.9rem;font-weight:600;margin-bottom:0.4rem;'>"
                "Or Paste Financial Data</div>", unsafe_allow_html=True)
    st.caption("Paste raw text, numbers, or CSV rows directly")
    pasted_text = st.text_area("paste", height=155,
        placeholder="Revenue: $10.5M\nNet Profit: $1.8M\n...", label_visibility="collapsed")

st.divider()
_, btn_col, _ = st.columns([1, 2, 1])
with btn_col:
    go = st.button("Analyse Financial Statements", use_container_width=True)

if go:
    if not api_key:
        st.error("Please enter your Groq API key.")
        st.stop()

    parts = []
    if uploaded_files:
        for uf in uploaded_files:
            uf.seek(0)
            parts.append(f"=== DOCUMENT: {uf.name} ===\n{extract_text(uf)}")
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

    section_label("DOWNLOAD REPORT")
    report_lines = [
        "FINANCIAL ANALYSIS REPORT — FINSIGHT","="*60,
        f"Company : {data.get('company_name','N/A')}",
        f"Period  : {data.get('period','N/A')}",
        f"Health  : {data.get('health_label','N/A')}   Score: {data.get('health_score','N/A')} / 10",
        "","EXECUTIVE SUMMARY","-"*40,data.get("health_summary",""),
        "","INVESTOR VIEW","-"*40,data.get("investor_view",""),
        "","KEY METRICS","-"*40,
    ]
    kpi_labels = {"revenue":"Revenue","net_profit":"Net Profit","gross_margin":"Gross Margin",
                  "net_margin":"Net Margin","ebitda":"EBITDA","operating_cashflow":"Operating Cash Flow",
                  "current_ratio":"Current Ratio","debt_to_equity":"Debt / Equity",
                  "working_capital":"Working Capital","total_debt":"Total Debt"}
    kpis = data.get("kpis",{})
    for k,lbl in kpi_labels.items():
        v=kpis.get(k,{}).get("value","N/A"); n=kpis.get(k,{}).get("note","")
        report_lines.append(f"  {lbl:<24} {v:<14} {n}")
    report_lines+=["","KEY RISKS","-"*40]
    for r in data.get("risks",[]):
        report_lines+=[f"  Risk: {r.get('title','')}",f"        {r.get('detail','')}",f"  Fix:  {r.get('fix','')}",""]
    report_lines+=["RECOMMENDATIONS","-"*40]
    for i,rec in enumerate(data.get("recommendations",[]),1):
        report_lines+=[f"  {i}. {rec.get('action','')}",f"     {rec.get('rationale','')}",""]

    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button("Download Report (.txt)", "\n".join(report_lines),
                           "financial_analysis.txt", "text/plain", use_container_width=True)
    with dl2:
        slug = re.sub(r"[^a-z0-9]","_",data.get("company_name","report").lower())
        st.download_button("Download Report (.xlsx)", build_excel_report(data),
                           f"{slug}_financial_analysis.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    with dl3:
        st.download_button("Download Raw Data (.json)", json.dumps(data,indent=2),
                           "financial_analysis.json","application/json", use_container_width=True)

st.divider()
st.markdown("<p style='text-align:center;color:#484f58;font-size:0.76rem;'>"
            "FinSight &nbsp;·&nbsp; Powered by Groq (LLaMA 3.3 70B) &nbsp;·&nbsp;"
            "For informational purposes only — not financial advice.</p>", unsafe_allow_html=True)
