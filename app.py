import streamlit as st
from groq import Groq
import io
import os
import csv

# ── PDF extraction ────────────────────────────────────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        clean = [str(c).strip() if c else "" for c in row]
                        text_parts.append(" | ".join(clean))
        return "\n".join(text_parts)
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def extract_text_from_csv(file_bytes: bytes) -> str:
    try:
        content = file_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(content))
        rows = [" | ".join(row) for row in reader]
        return "\n".join(rows)
    except Exception as e:
        return f"[CSV extraction error: {e}]"


def extract_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(raw)
    if name.endswith(".csv"):
        return extract_text_from_csv(raw)
    return raw.decode("utf-8", errors="replace")


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a highly skilled financial analyst and forensic accountant.
Your task is to analyse a company's financial statements (Income Statement, Balance Sheet,
and Cash Flow Statement) and extract key financial data, then provide a structured output
and a clear, insightful analysis.

IMPORTANT:
- Be precise and conservative. Do not invent numbers.
- If a number is missing, state "Not provided".
- Standardise all extracted values into clean, readable format.
- Focus on what actually matters economically, not just accounting presentation.

STEP 1: EXTRACT KEY METRICS
From the statements provided, extract and clearly present:

Profitability:
- Revenue
- Cost of Goods Sold (COGS)
- Gross Profit
- Operating Expenses
- EBITDA (if possible, otherwise approximate)
- Net Profit
- Tax Expense

Cash Flow:
- Operating Cash Flow
- Investing Cash Flow
- Financing Cash Flow
- Net Change in Cash

Balance Sheet:
- Cash
- Accounts Receivable
- Inventory
- Accounts Payable
- Total Debt
- Total Assets
- Total Liabilities
- Equity

Derived / Analytical:
- Gross Margin
- Net Margin
- Working Capital (Current Assets - Current Liabilities)
- Operating Working Capital (AR + Inventory - AP)
- Cash Conversion (compare Net Profit vs Operating Cash Flow)

STEP 2: NORMALISED SUMMARY TABLE
Create a clean, structured table like this:
=== FINANCIAL SUMMARY ===
[Clearly formatted table of all extracted and calculated metrics]

STEP 3: ANALYSIS (THIS IS THE MOST IMPORTANT PART)
Write a concise but sharp analysis covering:
1. Profit Quality — Is profit real or accounting-driven? Compare net profit vs cash flow. Highlight red flags.
2. Cash Health — Is the business generating cash? Any reliance on financing?
3. Working Capital Dynamics — Is cash being trapped in receivables/inventory? Is the business funding customers?
4. Cost Structure — Are margins strong or under pressure? Any notable inefficiencies?
5. Balance Sheet Strength — Debt levels and risk. Liquidity position.

STEP 4: WHAT IS REALLY GOING ON
Provide a blunt, investor-style interpretation:
- What kind of business is this really?
- Is it healthy, fragile, or misleading?
- What would concern a private equity investor?

STEP 5: RED FLAGS & KEY INSIGHTS
List:
- Top 3 risks
- Top 3 positive signals

OUTPUT STYLE:
- Structured
- No fluff
- Clear headings
- Analytical, not descriptive
- Think like a private equity investor reviewing a deal
"""


# ── Groq API call ─────────────────────────────────────────────────────────────
def analyse_financials(financial_text: str, api_key: str) -> str:
    client = Groq(api_key=api_key)

    # Truncate if too long (Groq context limit ~32k tokens)
    max_chars = 24000
    if len(financial_text) > max_chars:
        financial_text = financial_text[:max_chars] + "\n\n[Document truncated due to length]"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Please analyse the following financial statements:\n\n{financial_text}",
            },
        ],
    )
    return response.choices[0].message.content


# ── Section parser ────────────────────────────────────────────────────────────
def parse_sections(analysis: str) -> dict:
    sections = {
        "summary": "",
        "analysis": "",
        "whats_going_on": "",
        "red_flags": "",
        "raw": analysis,
    }

    lines = analysis.split("\n")
    current = "summary"
    buffer: list[str] = []

    def flush(key):
        sections[key] = "\n".join(buffer).strip()
        buffer.clear()

    for line in lines:
        upper = line.upper()
        if "STEP 3" in upper or ("ANALYSIS" in upper and "STEP 3" in upper):
            flush(current); current = "analysis"
        elif "STEP 4" in upper or "WHAT IS REALLY GOING ON" in upper:
            flush(current); current = "whats_going_on"
        elif "STEP 5" in upper or "RED FLAGS" in upper:
            flush(current); current = "red_flags"
        buffer.append(line)

    flush(current)
    return sections


# ── Streamlit UI ──────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Financial Statement Analyzer",
        page_icon="📊",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .main { background: #0f1117; }

        .hero {
            background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
            border: 1px solid #2d3748;
            border-radius: 16px;
            padding: 2.5rem 2rem;
            margin-bottom: 2rem;
            text-align: center;
        }
        .hero h1 {
            font-size: 2.4rem;
            font-weight: 700;
            color: #f0f6fc;
            margin: 0 0 0.5rem 0;
            letter-spacing: -0.5px;
        }
        .hero p { color: #8b949e; font-size: 1.05rem; margin: 0; }
        .hero .badge {
            display: inline-block;
            background: rgba(249,115,22,0.12);
            color: #f97316;
            border: 1px solid rgba(249,115,22,0.25);
            border-radius: 20px;
            padding: 0.2rem 0.8rem;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 1rem;
        }

        .section-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 1.5rem 1.8rem;
            margin-bottom: 1.5rem;
        }
        .section-card h2 {
            color: #f0f6fc;
            font-size: 1.15rem;
            font-weight: 600;
            margin: 0 0 1rem 0;
        }
        .section-card pre {
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 1rem;
            color: #c9d1d9;
            font-size: 0.85rem;
            white-space: pre-wrap;
            word-break: break-word;
            overflow: auto;
        }

        div[data-testid="stButton"] > button {
            background: linear-gradient(135deg, #ea580c 0%, #f97316 100%);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0.7rem 2.5rem;
            font-size: 1rem;
            font-weight: 600;
            width: 100%;
            transition: opacity 0.2s;
        }
        div[data-testid="stButton"] > button:hover { opacity: 0.85; }

        textarea {
            background: #0d1117 !important;
            border: 1px solid #30363d !important;
            color: #c9d1d9 !important;
            border-radius: 8px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Hero ─────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="hero">
            <div class="badge">⚡ POWERED BY GROQ · FREE TO USE</div>
            <h1>📊 Financial Statement Analyzer</h1>
            <p>Upload financial statements and get institutional-grade forensic analysis in seconds.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── API Key ───────────────────────────────────────────────────────────────
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        with st.expander("🔑 Enter your Groq API Key", expanded=True):
            api_key = st.text_input(
                "Groq API Key",
                type="password",
                placeholder="gsk_...",
                help="Free at console.groq.com — set GROQ_API_KEY env var to skip this step.",
            )
            st.markdown(
                "<small style='color:#6e7681'>Get a free key at "
                "<a href='https://console.groq.com' target='_blank' style='color:#f97316'>"
                "console.groq.com</a> → API Keys → Create Key</small>",
                unsafe_allow_html=True,
            )
        if not api_key:
            st.info("Enter your free Groq API key above to get started.", icon="ℹ️")

    st.divider()

    # ── Input ─────────────────────────────────────────────────────────────────
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### 📁 Upload Financial Statements")
        st.caption("Supported formats: PDF, CSV, TXT — upload one or more documents")
        uploaded_files = st.file_uploader(
            "Drop files here",
            type=["pdf", "csv", "txt"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded_files:
            for f in uploaded_files:
                size_kb = len(f.getvalue()) / 1024
                icon = "📄" if f.name.endswith(".pdf") else "📋"
                st.markdown(
                    f"<small style='color:#8b949e'>{icon} {f.name} — {size_kb:.1f} KB</small>",
                    unsafe_allow_html=True,
                )

    with col_right:
        st.markdown("### ✍️ Or Paste Financial Data")
        st.caption("Paste raw text, CSV rows, or any formatted financial data")
        pasted_text = st.text_area(
            "Paste here",
            height=180,
            placeholder="Revenue: $10.5M\nCOGS: $6.2M\nNet Profit: $1.8M\n...",
            label_visibility="collapsed",
        )

    st.divider()

    # ── Analyse button ────────────────────────────────────────────────────────
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        analyse_clicked = st.button("⚡ Analyse Financial Statements", use_container_width=True)

    # ── Run analysis ──────────────────────────────────────────────────────────
    if analyse_clicked:
        if not api_key:
            st.error("Please enter your Groq API key above.")
            st.stop()

        all_text_parts = []
        if uploaded_files:
            for uf in uploaded_files:
                uf.seek(0)
                extracted = extract_text(uf)
                all_text_parts.append(f"=== {uf.name} ===\n{extracted}")
        if pasted_text.strip():
            all_text_parts.append(f"=== Pasted Data ===\n{pasted_text.strip()}")
        if not all_text_parts:
            st.warning("Please upload at least one file or paste financial data.")
            st.stop()

        combined_text = "\n\n".join(all_text_parts)

        with st.spinner("Analysing with Groq AI (LLaMA 3.3 70B)…"):
            try:
                raw_analysis = analyse_financials(combined_text, api_key)
            except Exception as e:
                err = str(e).lower()
                if "invalid api key" in err or "authentication" in err or "401" in err:
                    st.error("❌ Invalid Groq API key. Please check it and try again.")
                elif "rate limit" in err or "429" in err:
                    st.error("⏳ Rate limit hit. Please wait a moment and try again.")
                else:
                    st.error(f"Error calling Groq API: {e}")
                st.stop()

        sections = parse_sections(raw_analysis)
        st.success("Analysis complete!", icon="✅")
        st.divider()

        # 1. Summary table
        st.markdown("<div class='section-card'><h2>📋 Financial Summary Table</h2>", unsafe_allow_html=True)
        summary_text = sections["summary"] or raw_analysis.split("STEP 3")[0]
        st.markdown(f"<pre>{summary_text}</pre>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # 2. Analysis
        if sections["analysis"]:
            st.markdown("<div class='section-card'><h2>🔍 Detailed Analysis</h2>", unsafe_allow_html=True)
            st.markdown(sections["analysis"])
            st.markdown("</div>", unsafe_allow_html=True)

        # 3. What's really going on
        if sections["whats_going_on"]:
            st.markdown("<div class='section-card'><h2>🎯 What Is Really Going On</h2>", unsafe_allow_html=True)
            st.markdown(sections["whats_going_on"])
            st.markdown("</div>", unsafe_allow_html=True)

        # 4. Red flags
        if sections["red_flags"]:
            st.markdown("<div class='section-card'><h2>🚦 Red Flags & Key Insights</h2>", unsafe_allow_html=True)
            st.markdown(sections["red_flags"])
            st.markdown("</div>", unsafe_allow_html=True)

        # 5. Raw output
        with st.expander("📄 Full Raw Analysis Output"):
            st.text(raw_analysis)

        st.download_button(
            label="⬇️ Download Full Analysis (.txt)",
            data=raw_analysis,
            file_name="financial_analysis.txt",
            mime="text/plain",
            use_container_width=True,
        )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<p style='text-align:center;color:#484f58;font-size:0.8rem;'>"
        "Financial Statement Analyzer · Powered by Groq (LLaMA 3.3 70B) · "
        "Not financial advice — for analytical purposes only."
        "</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
